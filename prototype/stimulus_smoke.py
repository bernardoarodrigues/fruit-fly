"""Sample an illustrative odor field and actual food contacts from two fly bodies.

This is a sensory instrumentation example, NOT a neural foraging controller.
The odor and generic receptor parameters are engineering assumptions. Locomotion
uses fixed commands; the sampled odor/taste does not yet drive a connectome.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from time import perf_counter

import mujoco
import numpy as np

from arena_smoke import (
    BodySegment, HybridControllerObservation, apply_locomotion_action,
    build_simulation, thorax_positions,
)


class PuffField:
    """Analytic, nonnegative Gaussian puffs above a reflecting z=0 floor.

    Inputs are SI. Units of concentration are arbitrary substance units/m^3.
    Lateral walls do not affect this open-half-space field. No fluid solver,
    turbulence, chemical reactions, or experimentally calibrated odor is implied.
    """

    def __init__(self, source_m=(0.010, 0.0, 0.00016), rate_hz=10.0,
                 puff_mass=1.0, diffusivity_m2_s=2e-6,
                 wind_m_s=(-0.002, 0.0, 0.0), initial_sigma_m=0.001):
        self.source = np.asarray(source_m, dtype=float)
        self.wind = np.asarray(wind_m_s, dtype=float)
        if self.source.shape != (3,) or self.wind.shape != (3,):
            raise ValueError("Source and wind must be 3-vectors")
        if not np.isfinite(np.r_[self.source, self.wind]).all():
            raise ValueError("Source and wind must be finite")
        params = np.array([rate_hz, puff_mass, diffusivity_m2_s, initial_sigma_m])
        if not np.isfinite(params).all() or np.any(params <= 0):
            raise ValueError("Field parameters must be finite and positive")
        if self.wind[2] != 0 or self.source[2] < 0:
            raise ValueError("Reflecting-floor example requires horizontal wind and z >= 0")
        self.rate, self.mass = rate_hz, puff_mass
        self.diffusivity, self.sigma0 = diffusivity_m2_s, initial_sigma_m

    def sample(self, positions_m, t_s):
        positions = np.asarray(positions_m, dtype=float)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions must have shape (n, 3)")
        if not np.isfinite(positions).all() or np.any(positions[:, 2] < 0):
            raise ValueError("Sensors must be finite and above the floor")
        if not np.isfinite(t_s) or t_s < 0:
            raise ValueError("Sample time must be finite and nonnegative")
        # Explicit 3 s emission prehistory; retain every emitted puff in this run.
        births = np.arange(-3.0, t_s + 1e-12, 1 / self.rate)
        age = t_s - births
        variance = self.sigma0**2 + 2 * self.diffusivity * age
        centres = self.source + age[:, None] * self.wind
        mirror = centres.copy()
        mirror[:, 2] *= -1
        normalization = self.mass / ((2 * np.pi * variance) ** 1.5)
        values = np.zeros(len(positions))
        for means in (centres, mirror):
            distance2 = ((positions[:, None, :] - means[None, :, :]) ** 2).sum(axis=-1)
            values += (np.exp(-distance2 / (2 * variance)) * normalization).sum(axis=1)
        return values


def add_food_scene(world):
    # These marker colors do not enter the chemical field or controller.
    food = world.mjcf_root.worldbody.add_geom(
        name="food_patch", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        pos=(10, 0, 0.08), size=(4.0, 0.08, 0),
        rgba=(0.91, 0.66, 0.14, 1), contype=0, conaffinity=0,
    )
    world.ground_geoms.append(food)
    water = world.mjcf_root.worldbody.add_geom(
        name="water_marker", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        pos=(-8, 7, 0.05), size=(2.0, 0.05, 0),
        rgba=(0.15, 0.55, 0.90, 1), contype=0, conaffinity=0,
    )
    world.ground_geoms.append(water)


def food_taste_contacts(sim, fly_names, food_id):
    """Only tarsal contacts with the food geom count as taste.

    This binary geometry-to-taste abstraction has no receptor identity, chemical
    selectivity, ingestion, gut model, or caloric transfer yet.
    """
    sensed = np.zeros(len(fly_names), dtype=bool)
    for contact in sim.mj_data.contact[:sim.mj_data.ncon]:
        if contact.dist > 0:  # exclude a positive-distance contact margin
            continue
        a, b = int(contact.geom1), int(contact.geom2)
        other = b if a == food_id else a if b == food_id else None
        if other is None:
            continue
        name = mujoco.mj_id2name(sim.mj_model, mujoco.mjtObj.mjOBJ_GEOM, other) or ""
        for i, fly_name in enumerate(fly_names):
            if name.startswith(fly_name + "/") and "tarsus" in name:
                sensed[i] = True
    return sensed


def check_field():
    """Check units-independent physical invariants of the illustrative field."""
    field = PuffField(source_m=(0, 0, .001), wind_m_s=(0, 0, 0))
    points = np.array([[.002, 0, .001], [-.002, 0, .001], [.1, 0, .001]])
    c = field.sample(points, 0)
    assert np.isfinite(c).all() and (c >= 0).all()
    assert np.isclose(c[0], c[1]), "Isotropic field should be symmetric"
    assert c[0] > c[2], "Concentration should decay away from source"
    doubled = PuffField(source_m=(0, 0, .001), wind_m_s=(0, 0, 0), puff_mass=2)
    assert np.allclose(doubled.sample(points, 0), 2 * c), "Emission must scale linearly"
    print("Field checks passed: positivity, symmetry, distance decay, source scaling")


def run(seconds, output, render=True):
    if not np.isfinite(seconds) or seconds <= 0:
        raise ValueError("seconds must be finite and positive")
    check_field()
    output.mkdir(parents=True, exist_ok=True)
    sim, flies, controllers = build_simulation(add_scene=add_food_scene)
    names = [f.name for f in flies]
    # Actual modeled antennal body origins; not thorax-based offsets.
    antenna_indices = [[f.get_bodysegs_order().index(BodySegment(f"{side}_funiculus"))
                        for side in ("l", "r")] for f in flies]
    food_id = mujoco.mj_name2id(sim.mj_model, mujoco.mjtObj.mjOBJ_GEOM, "food_patch")
    field = PuffField()
    adaptation = np.zeros((2, 2))
    sensor_stride = 10  # 1 ms with the pinned model's 0.1 ms physics step
    sample_dt = sensor_stride * sim.timestep
    rows, taste_counts = [], np.zeros(2, dtype=int)
    started = perf_counter()
    for tick in range(round(seconds / sim.timestep)):
        mujoco.mj_forward(sim.mj_model, sim.mj_data)
        # Sample before changing either fly's command, at one shared timestamp.
        if tick % sensor_stride == 0:
            t = tick * sim.timestep
            antenna_m = np.stack([
                sim.get_body_positions(f.name)[indices] * 1e-3
                for f, indices in zip(flies, antenna_indices)
            ])
            c = field.sample(antenna_m.reshape(-1, 3), t).reshape(2, 2)
            occupancy = c / (1e8 + c)  # illustrative virtual concentration scale
            rates = 5 + 95 * occupancy / (1 + 2 * adaptation)
            adaptation += (occupancy - adaptation) * (1 - np.exp(-sample_dt / .3))
            taste = food_taste_contacts(sim, names, food_id)
            taste_counts += taste
            for i, f in enumerate(flies):
                rows.append([t, f.name, *antenna_m[i].ravel(), *c[i], *rates[i], int(taste[i])])
        for f, controller in zip(flies, controllers):
            obs = HybridControllerObservation.from_sim(sim, f.name)
            action = controller.step(np.array([1.0, 1.0]), obs)
            apply_locomotion_action(sim, f.name, action)
        sim.step()
    wall_s = perf_counter() - started
    mujoco.mj_forward(sim.mj_model, sim.mj_data)
    if not np.isfinite(sim.mj_data.qpos).all() or not np.isfinite(sim.mj_data.qvel).all():
        raise RuntimeError("Nonfinite body state")
    with (output / "stimuli_trace.csv").open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "fly", "left_x_m", "left_y_m", "left_z_m",
                         "right_x_m", "right_y_m", "right_z_m", "left_c_arbitrary_per_m3",
                         "right_c_arbitrary_per_m3", "left_generic_rate_Hz",
                         "right_generic_rate_Hz", "tarsal_food_contact"])
        writer.writerows(rows)
    report = {
        "claim": "sampled odor and food contacts; fixed locomotion; no neural control or feeding",
        "simulated_s": round(seconds / sim.timestep) * sim.timestep,
        "wall_s_excluding_setup_and_render": wall_s,
        "sensor_period_s": sample_dt, "sample_rows": len(rows),
        "food_contact_sample_counts": dict(zip(names, taste_counts.tolist())),
        "field": "Gaussian puffs; reflecting floor; open lateral boundaries; SI coordinates",
        "receptor": "illustrative saturating adapting encoder; uncalibrated and no neuron ID",
        "morphology": "two copies of female-derived NeuroMechFly geometry",
        "final_thorax_mm": thorax_positions(sim, flies).tolist(), "finite": True,
    }
    if render:
        from PIL import Image
        renderer = mujoco.Renderer(sim.mj_model, height=480, width=640)
        renderer.update_scene(sim.mj_data, camera="overview")
        Image.fromarray(renderer.render()).save(output / "arena-food.png")
        renderer.close()
    (output / "stimuli_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    sim.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--output", type=Path, default=Path("prototype/output"))
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--check-field", action="store_true")
    args = parser.parse_args()
    if args.check_field:
        check_field()
    else:
        run(args.seconds, args.output, not args.no_render)
