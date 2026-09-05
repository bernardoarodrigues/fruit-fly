"""Two physical fly bodies with a published hybrid walking controller.

This is an engineering baseline, not a connectome or whole-animal simulation.
Both instances use the same female-derived NeuroMechFly geometry. Sex-specific
anatomy, physiology, feeding and reproduction are not implemented here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
from time import perf_counter
from typing import Callable

import mujoco
import numpy as np
from flygym import Simulation
from flygym.anatomy import BodySegment, ContactBodiesPreset
from flygym.compose import FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym_demo.complex_terrain import (
    HybridControllerObservation, HybridTurningController, LocomotionAction,
    PreprogrammedSteps, apply_locomotion_action, make_locomotion_fly,
)

FLYGYM_COMMIT = "38c8ec61034cd59bc5ba0de20688d4a3c0000d60"


def build_simulation(fly_count: int = 2, add_scene: Callable | None = None):
    """Build a 50 x 30 mm walled arena; lengths exposed by FlyGym are mm.

    Optional add_scene(world) runs before attachment/compilation. Register new
    contact surfaces in world.ground_geoms before adding the flies. The control
    loop advances every fly's command, then steps the shared world exactly once.
    """
    if fly_count not in (1, 2):
        raise ValueError("This smoke example supports one or two flies.")
    world = FlatGroundWorld(half_size=25)
    # Floor is an infinite plane; these four physical walls bound the arena.
    for name, pos, size in (
        ("west", (-25, 0, 2), (0.3, 15, 2)),
        ("east", (25, 0, 2), (0.3, 15, 2)),
        ("south", (0, -15, 2), (25, 0.3, 2)),
        ("north", (0, 15, 2), (25, 0.3, 2)),
    ):
        wall = world.mjcf_root.worldbody.add_geom(
            name=name, type=mujoco.mjtGeom.mjGEOM_BOX, pos=pos, size=size,
            rgba=(0.45, 0.58, 0.65, 0.22), contype=0, conaffinity=0,
        )
        world.ground_geoms.append(wall)
    if add_scene is not None:
        add_scene(world)
    flies = []
    for i in range(fly_count):
        fly = make_locomotion_fly(name=f"fly_{i + 1}", add_adhesion=True, colorize=True)
        # FlyGym normally makes only explicit ground pairs. Add collision masks
        # so distinct flies can contact one another, without enabling self contact.
        for geometries in fly.bodyseg_to_mjcfgeom.values():
            for geom in geometries:
                geom.contype = 1 << i
                geom.conaffinity = (2 if i == 0 else 1) if fly_count == 2 else 0
        world.add_fly(
            fly, [0, (-3 if i == 0 else 3) if fly_count == 2 else 0, 0.8],
            Rotation3D("quat", [1, 0, 0, 0]),
            bodysegs_with_ground_contact=ContactBodiesPreset.LEGS_THORAX_ABDOMEN_HEAD,
            add_ground_contact_sensors=False,
        )
        flies.append(fly)
    world.mjcf_root.worldbody.add_camera(
        name="overview", pos=(6, -29, 28),
        xyaxes=(1, 0, 0, 0, 0.695, 0.719), fovy=45,
    )
    sim = Simulation(world)
    steps = PreprogrammedSteps()
    controllers = []
    for i, fly in enumerate(flies):
        order = fly.get_actuated_jointdofs_order("position")
        controller = HybridTurningController(
            timestep=sim.timestep, preprogrammed_steps=steps, output_dof_order=order,
        )
        controller.reset(seed=i)
        controllers.append(controller)
        apply_locomotion_action(
            sim, fly.name, LocomotionAction(
                joint_angles=steps.default_pose_by_dof_order(order),
                adhesion_onoff=np.ones(6, dtype=bool),
            ),
        )
    sim.warmup()
    mujoco.mj_forward(sim.mj_model, sim.mj_data)
    return sim, flies, controllers


def thorax_positions(sim, flies):
    return np.array([
        sim.get_body_positions(fly.name)[fly.get_bodysegs_order().index(BodySegment("c_thorax"))]
        for fly in flies
    ])


def run(seconds: float, output: Path, fly_count: int = 2, render: bool = True):
    if not np.isfinite(seconds) or seconds <= 0:
        raise ValueError("seconds must be a positive finite duration")
    output.mkdir(parents=True, exist_ok=True)
    sim, flies, controllers = build_simulation(fly_count)
    before = thorax_positions(sim, flies)
    trace = []
    nsteps = round(seconds / sim.timestep)
    started = perf_counter()
    for tick in range(nsteps):
        # mj_step leaves derived position/contact caches at its pre-step state.
        mujoco.mj_forward(sim.mj_model, sim.mj_data)
        for fly, controller in zip(flies, controllers):
            observation = HybridControllerObservation.from_sim(sim, fly.name)
            # Two dimensionless left/right drive values; a heuristic command.
            action = controller.step(np.array([1.0, 1.0]), observation)
            apply_locomotion_action(sim, fly.name, action)
        sim.step()
        if tick % 100 == 0:
            mujoco.mj_forward(sim.mj_model, sim.mj_data)
            trace.append([(tick + 1) * sim.timestep, *thorax_positions(sim, flies).ravel()])
    wall_s = perf_counter() - started
    mujoco.mj_forward(sim.mj_model, sim.mj_data)
    after = thorax_positions(sim, flies)
    finite = bool(np.isfinite(sim.mj_data.qpos).all() and np.isfinite(sim.mj_data.qvel).all())
    if not finite:
        raise RuntimeError("Nonfinite physics state encountered")
    report = {
        "claim": "physical body and heuristic locomotion smoke test; no neural emulation",
        "morphology": "same female-derived NeuroMechFly geometry for every instance",
        "controller": "FlyGym HybridTurningController with CPG and reflex corrections",
        "flygym_commit": FLYGYM_COMMIT, "mujoco": mujoco.__version__,
        "python": platform.python_version(), "machine": platform.machine(),
        "flies": fly_count, "timestep_s": sim.timestep,
        "simulated_s": nsteps * sim.timestep, "wall_s_excluding_setup_and_render": wall_s,
        "realtime_factor": nsteps * sim.timestep / wall_s,
        "nq": sim.mj_model.nq, "nv": sim.mj_model.nv, "nu": sim.mj_model.nu,
        "finite": finite, "displacement_mm": (after - before).tolist(),
        "final_thorax_mm": after.tolist(),
    }
    if render:
        from PIL import Image
        renderer = mujoco.Renderer(sim.mj_model, height=480, width=640)
        renderer.update_scene(sim.mj_data, camera="overview")
        Image.fromarray(renderer.render()).save(output / "arena.png")
        renderer.close()
    np.savetxt(output / "thorax_trace.csv", np.array(trace), delimiter=",",
               header="time_s," + ",".join(f"fly_{i+1}_{a}_mm" for i in range(fly_count) for a in "xyz"),
               comments="")
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    sim.close()
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--flies", type=int, choices=(1, 2), default=2)
    parser.add_argument("--output", type=Path, default=Path("prototype/output"))
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    run(args.seconds, args.output, args.flies, not args.no_render)
