"""A bounded measured-angle replay diagnostic, separate from neural control.

Female source trajectories and the current NMF geometry are not a male motor
model. Antennae remain rigid here because the paper's passive configuration has
not been recovered for this body revision. This cannot reproduce contact forces
from the paper; it can test the explicit joint conversion and position actuation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import mujoco
import numpy as np
from flygym import Simulation
from flygym import assets_dir
from flygym.anatomy import (ActuatedDOFPreset, AnatomicalJoint, AxisOrder,
                           BodySegment, ContactBodiesPreset, JointPreset, Skeleton)
from flygym.compose import (ActuatorType, FlatGroundWorld, KinematicPosePreset,
                           NeuroMechFly)
from flygym.compose.physics import ContactParams
from flygym.utils.math import Rotation3D
from flygym_demo.complex_terrain import PreprogrammedSteps


SOURCE_TO_CHILD = {"ThC": "coxa", "CTr": "trochanterfemur",
                   "FTi": "tibia", "TiTa": "tarsus1"}


def source_joint_map() -> dict[str, tuple[str, float]]:
    """Source names -> FlyGym DOF names/signs, before any dynamics.

    SeqIKPy orders ThC rotations x/y/z (yaw/pitch/roll), then CTr y/z.
    FlyGym YPR matches that order but flips right non-pitch hinge axes.
    Source head roll is physical x; FlyGym's generic x-axis label is yaw.
    """
    result = {}
    for leg in ("LF", "RF"):
        prefix = leg.lower()
        for joint, axes, parent in (("ThC", ("yaw", "pitch", "roll"), "c_thorax"),
                ("CTr", ("pitch", "roll"), prefix + "_coxa"),
                ("FTi", ("pitch",), prefix + "_trochanterfemur"),
                ("TiTa", ("pitch",), prefix + "_tibia")):
            child = prefix + "_" + SOURCE_TO_CHILD[joint]
            for axis in axes:
                sign = -1.0 if leg == "RF" and axis != "pitch" else 1.0
                result[f"Angle_{leg}_{joint}_{axis}"] = (f"{parent}-{child}-{axis}", sign)
    result["Angle_head_roll"] = ("c_thorax-c_head-yaw", 1.0)
    result["Angle_head_pitch"] = ("c_thorax-c_head-pitch", 1.0)
    return result


@dataclass(frozen=True)
class ReplayConfig:
    timestep_s: float = 1e-4
    settling_s: float = .25
    entry_blend_s: float = .25
    exit_blend_s: float = .25
    position_gain: float = 45.0
    actuator_force_limit_native: float = 65.0
    leg_stiffness: float = .05
    leg_damping: float = .06
    passive_tarsus_stiffness: float = 7.5
    passive_tarsus_damping: float = .01
    supporting_leg_adhesion_gain: float = 40.0
    max_source_jump_deg_per_sample: float = 30.0

    def __post_init__(self):
        if not all(math.isfinite(value) and value > 0 for value in asdict(self).values()):
            raise ValueError("Replay parameters must be finite and positive")
        if self.timestep_s > 1e-4:
            raise ValueError("Grooming diagnostic requires a physics timestep of 0.1 ms or finer")


FIDELITY = ["measured female motor template", "female-derived NeuroMechFly body surrogate",
            "rigid antennae", "engineering position actuation and adhesion", "not natural grooming validation"]


class GroomingPlayback:
    """Gate a single measured traversal, with withdrawal and no tonic looping.

    Targets use the explicit source_joint_map order. This class has no neural,
    food, coordinate, or behavior-selection input: its only trigger is a gate.
    Blend timings are engineering controls, not fitted fly behavior parameters.
    """

    def __init__(self, trace_path: Path, neutral_targets, config: ReplayConfig = ReplayConfig()):
        self.config = config
        self.trace = load_trace(Path(trace_path), max_jump_deg=config.max_source_jump_deg_per_sample)
        self.neutral = np.asarray(neutral_targets, dtype=float).copy()
        mapping = source_joint_map()
        if self.neutral.shape != (len(mapping),) or not np.isfinite(self.neutral).all():
            raise ValueError("Neutral targets must contain all 16 finite mapped angles")
        names = self.trace["joint_names"].tolist()
        self.samples = np.column_stack([self.trace["angles_rad"][:, names.index(name)] * sign
                                       for name, (_, sign) in mapping.items()])
        self.times = self.trace["time_relative_s"]
        self.duration_s = float(self.times[-1])
        self.reset()

    def reset(self):
        self.phase = "ready"
        self.armed = True
        self.requested = False
        self.elapsed = 0.0
        self.source_time_s = None
        self.completed_count = 0
        self.cancelled_count = 0
        self.target = self.neutral.copy()
        self._blend_from = self.neutral.copy()
        self.tracking_active = False

    @property
    def active(self):
        return self.phase in ("entering", "playing", "exiting")

    def step(self, requested: bool, current_targets, dt: float):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("Playback timestep must be finite and positive")
        current = np.asarray(current_targets, dtype=float)
        if current.shape != self.neutral.shape or not np.isfinite(current).all():
            raise ValueError("Current targets must contain 16 finite angles")
        rising = bool(requested and not self.requested)
        self.requested = bool(requested)
        self.tracking_active = False
        if not requested:
            self.armed = True
            if self.phase == "held":
                self.phase = "ready"
            elif self.phase in ("entering", "playing"):
                self.cancelled_count += 1
                self.phase, self.elapsed = "exiting", 0.0
                self._blend_from = current.copy()
        if rising and self.armed and self.phase == "ready":
            self.armed = False
            self.phase, self.elapsed = "entering", 0.0
            self._blend_from = current.copy()
            self.source_time_s = 0.0
        if not self.active:
            return None
        self.elapsed += dt
        if self.phase in ("entering", "exiting"):
            entering = self.phase == "entering"
            duration = self.config.entry_blend_s if entering else self.config.exit_blend_s
            u = min(self.elapsed / duration, 1.0)
            destination = self.samples[0] if entering else self.neutral
            self.target = self._blend_from + u*u*(3-2*u) * (destination-self._blend_from)
            if self.elapsed >= duration - 1e-12:
                self.elapsed = 0.0
                if entering:
                    self.phase = "playing"
                else:
                    self.phase = "held" if requested else "ready"
                    self.armed = not requested
                    self.source_time_s = None
        else:
            self.source_time_s = min(self.elapsed, self.duration_s)
            # Equidistant source samples: vector interpolation avoids 16 calls
            # to np.interp at every 0.1 ms physics tick.
            at = self.source_time_s / .01
            lo = min(int(at), len(self.samples)-2)
            frac = min(at-lo, 1.0)
            self.target = self.samples[lo] + frac*(self.samples[lo+1]-self.samples[lo])
            self.tracking_active = True
            if self.elapsed >= self.duration_s - 1e-12:
                self.completed_count += 1
                self.phase, self.elapsed = "exiting", 0.0
                self._blend_from = self.target.copy()
        return self.target.copy()

    def snapshot(self):
        return {"enabled": True, "state": self.phase, "armed": self.armed,
                "requested": self.requested, "actual_active": self.active,
                "source_time_s": self.source_time_s, "source_duration_s": self.duration_s,
                "completed_count": self.completed_count, "cancelled_count": self.cancelled_count,
                "fidelity": FIDELITY.copy()}


def load_trace(path: Path, *, max_jump_deg: float = 30.0) -> dict:
    """Reject corrupt/outlier input; never repair or silently clip a source trace."""
    path = Path(path)
    provenance = json.loads((path.parent / "provenance.json").read_text())
    metadata = provenance["examples"][path.stem]
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Curated trajectory hash does not match provenance")
    with np.load(path, allow_pickle=False) as data:
        trace = {key: data[key].copy() for key in data.files}
    names = trace["joint_names"].tolist()
    required = list(source_joint_map())
    if any(name not in names for name in required):
        raise ValueError("Source lacks a required foreleg/head angle")
    values = trace["angles_deg"][:, [names.index(name) for name in required]]
    times = trace["time_relative_s"]
    if len(times) < 2 or not np.isfinite(values).all() or not np.isfinite(times).all():
        raise ValueError("Nonfinite or empty trajectory")
    if not np.allclose(np.diff(times), .01, atol=1e-10, rtol=0):
        raise ValueError("Source samples must be contiguous at 100 Hz")
    jumps = np.abs(np.diff(values, axis=0))
    if np.any(jumps > max_jump_deg):
        frame, channel = np.argwhere(jumps > max_jump_deg)[0]
        raise ValueError(f"IK outlier guard: {required[channel]} changes {jumps[frame, channel]:.2f} degrees "
                         f"at source frame {trace['frame'][frame]}; trace rejected")
    # Generic bounded-angle integrity check, not a fitted motor range.
    if np.any(np.abs(values) > 180):
        raise ValueError("Source joint angle is outside the IK domain [-180,180] degrees")
    trace["metadata"] = metadata
    trace["max_mapped_jump_deg"] = float(jumps.max())
    return trace


def make_grooming_fly(config: ReplayConfig, *, name="grooming"):
    """Compose the optional female-derived body; no world or controller state."""
    order = AxisOrder.YAW_PITCH_ROLL
    neutral = KinematicPosePreset.NEUTRAL.get_pose_by_axis_order(order)
    joints = JointPreset.LEGS_ONLY.to_joint_list()
    joints.append(AnatomicalJoint("c_thorax", "c_head", ["yaw", "pitch"]))
    skeleton = Skeleton(axis_order=order, anatomical_joints=joints)
    fly = NeuroMechFly(name=name)
    elements = fly.add_joints(skeleton, neutral_pose=neutral,
                             stiffness=config.leg_stiffness, damping=config.leg_damping)
    for dof, element in elements.items():
        if dof.child.link in ("tarsus2", "tarsus3", "tarsus4", "tarsus5"):
            element.stiffness[0] = config.passive_tarsus_stiffness
            element.damping[0] = config.passive_tarsus_damping
    active = skeleton.get_actuated_dofs_from_preset(ActuatedDOFPreset.LEGS_ACTIVE_ONLY)
    active += [dof for dof in skeleton.iter_jointdofs() if dof.child.name == "c_head"]
    fly.add_actuators(active, ActuatorType.POSITION, neutral_input=neutral,
                     kp=config.position_gain,
                     forcerange=(-config.actuator_force_limit_native,
                                 config.actuator_force_limit_native))
    fly.add_leg_adhesion(gain=config.supporting_leg_adhesion_gain)
    fly.colorize()
    return fly


def add_grooming_contacts(world, fly):
    """Add 72 explicit foreleg/antenna collision pairs after adding fly to world."""
    contact = ContactParams()
    pair_labels = {}
    for leg in ("lf", "rf"):
        for segment in ("tibia", "tarsus1", "tarsus2", "tarsus3", "tarsus4", "tarsus5"):
            for side in ("l", "r"):
                for antenna in ("pedicel", "funiculus", "arista"):
                    a, b = f"{fly.name}/{leg}_{segment}", f"{fly.name}/{side}_{antenna}"
                    world.mjcf_root.add_pair(name=f"{leg}_{segment}-{side}_{antenna}",
                        geomname1=a, geomname2=b, friction=contact.get_friction_tuple(),
                        solref=contact.get_solref_tuple(), solimp=contact.get_solimp_tuple(),
                        margin=contact.margin)
                    pair_labels[(a, b)] = f"{leg}_{segment}:{side}_{antenna}"
    return pair_labels


def build_replay(config: ReplayConfig):
    """Current NMF diagnostic with explicit head axes and foreleg self-contacts."""
    fly = make_grooming_fly(config)
    world = FlatGroundWorld(half_size=5)
    world.add_fly(fly, (0, 0, .8), Rotation3D("quat", [1, 0, 0, 0]),
                  bodysegs_with_ground_contact=ContactBodiesPreset.LEGS_THORAX_ABDOMEN_HEAD,
                  add_ground_contact_sensors=False)
    pair_labels = add_grooming_contacts(world, fly)
    sim = Simulation(world, timestep=config.timestep_s)
    return fly, sim, pair_labels


def audit_foreleg_forward_kinematics(trace_path: Path) -> dict:
    """Compare source markers to the mapped current body, without fitting it.

    Relative-to-coxa coordinates remove the global origin only. Segment lengths,
    angle offsets, and rotations are not fitted to improve this diagnostic.
    """
    trace = load_trace(trace_path)
    fly, sim, _ = build_replay(ReplayConfig())
    model, data = sim.mj_model, sim.mj_data
    qpos_by_name = dict(zip((d.name for d in fly.get_jointdofs_order()),
                           sim._intern_qposadrs_by_fly[fly.name]))
    names, pose_names = trace["joint_names"].tolist(), trace["pose_names"].tolist()
    body_names = [f"{leg}_{link}" for leg in ("lf", "rf")
                  for link in ("coxa", "trochanterfemur", "tibia", "tarsus1")]
    body_ids = {name: mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY,
                                      "grooming/" + name) for name in body_names}
    outputs = {}
    try:
        for correct_signs in (True, False):
            errors = []
            for row in range(len(trace["time_relative_s"])):
                mujoco.mj_resetDataKeyframe(model, data, sim._neutral_keyframe_id)
                for source, (target, sign) in source_joint_map().items():
                    data.qpos[qpos_by_name[target]] = trace["angles_rad"][row, names.index(source)] * (sign if correct_signs else 1)
                mujoco.mj_forward(model, data)
                for leg in ("LF", "RF"):
                    origin = data.xpos[body_ids[leg.lower() + "_coxa"]]
                    source_origin = trace["pose_source"][row, [pose_names.index(
                        f"Pose_{leg}_Coxa_{axis}") for axis in "xyz"]]
                    for src, dst in (("Femur", "trochanterfemur"), ("Tibia", "tibia"), ("Tarsus", "tarsus1")):
                        observed = trace["pose_source"][row, [pose_names.index(
                            f"Pose_{leg}_{src}_{axis}") for axis in "xyz"]] - source_origin
                        predicted = data.xpos[body_ids[leg.lower() + "_" + dst]] - origin
                        errors.append(float(np.linalg.norm(observed-predicted)))
            outputs["documented_axis_map" if correct_signs else "no_right_axis_correction_control"] = {
                "marker_count": len(errors), "rms_euclidean_error_mm": float(np.sqrt(np.mean(np.square(errors)))),
                "mean_euclidean_error_mm": float(np.mean(errors)), "max_euclidean_error_mm": max(errors)}
        return {"scope": "foreleg source markers relative to each coxa; no geometric fit; no head/antenna calibration", **outputs}
    finally:
        sim.close()


def run_replay(trace_path: Path, *, config: ReplayConfig = ReplayConfig(),
               frame_callback=None) -> dict:
    """Replay once using actual position actuators; return numerical diagnostics."""
    trace = load_trace(trace_path, max_jump_deg=config.max_source_jump_deg_per_sample)
    fly, sim, pair_labels = build_replay(config)
    model, data = sim.mj_model, sim.mj_data
    actuator_order = fly.get_actuated_jointdofs_order("position")
    actuator_ids = np.asarray(sim._intern_actuatorids_by_type_by_fly[ActuatorType.POSITION][fly.name])
    qpos_by_name = dict(zip((d.name for d in fly.get_jointdofs_order()),
                           sim._intern_qposadrs_by_fly[fly.name]))
    qvel_by_name = dict(zip((d.name for d in fly.get_jointdofs_order()),
                           sim._intern_qveladrs_by_fly[fly.name]))
    actuator_by_name = {dof.name: int(actuator_ids[i]) for i, dof in enumerate(actuator_order)}
    neutral = np.asarray([fly.jointdof_to_neutralangle[dof] for dof in actuator_order])
    leg_indices = [i for i, dof in enumerate(actuator_order) if dof.child.is_leg()]
    neutral[leg_indices] = PreprogrammedSteps().default_pose_by_dof_order(
        [actuator_order[i] for i in leg_indices])
    mapped = source_joint_map()
    names = trace["joint_names"].tolist()
    source = np.column_stack([trace["angles_rad"][:, names.index(name)] * sign
                              for name, (_, sign) in mapped.items()])
    target_act = np.asarray([actuator_by_name[name] for name, _ in mapped.values()])
    target_qpos = np.asarray([qpos_by_name[name] for name, _ in mapped.values()])
    target_qvel = np.asarray([qvel_by_name[name] for name, _ in mapped.values()])
    adhesion_ids = sim._intern_adhesionactuatorids_by_fly[fly.name]
    legs = ("lf", "lm", "lh", "rf", "rm", "rh")
    geom_leg = {i: next((leg for leg in legs if (mujoco.mj_id2name(model,
        mujoco.mjtObj.mjOBJ_GEOM, i) or "").startswith(f"grooming/{leg}_")), None)
        for i in range(model.ngeom)}
    pairs = {frozenset((mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, a),
                       mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, b))): label
             for (a, b), label in pair_labels.items()}
    ground = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
    if ground < 0:
        ground = next(i for i in range(model.ngeom) if model.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE)
    thorax = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "grooming/c_thorax")
    mujoco.mj_resetDataKeyframe(model, data, sim._neutral_keyframe_id)
    data.ctrl[actuator_ids] = neutral
    data.ctrl[adhesion_ids] = [0, 1, 1, 0, 1, 1]
    begin = config.settling_s + config.entry_blend_s
    duration = float(trace["time_relative_s"][-1])
    errors, velocities, supports, heights, positions, times, targets, actuals = [], [], [], [], [], [], [], []
    contact_duration, contact_impulse = {}, {}
    wrench = np.zeros(6)
    source_neutral = data.ctrl[target_act].copy()
    try:
        total_steps = round((begin + duration) / config.timestep_s)
        for step in range(total_steps):
            t = (step + 1) * config.timestep_s
            if t < config.settling_s:
                target = source_neutral
            elif t < begin:
                u = (t - config.settling_s) / config.entry_blend_s
                blend = u*u*(3-2*u)
                target = source_neutral + blend * (source[0] - source_neutral)
            else:
                rel = min(t-begin, duration)
                target = np.asarray([np.interp(rel, trace["time_relative_s"], source[:, j])
                                     for j in range(source.shape[1])])
            data.ctrl[target_act] = target
            mujoco.mj_step(model, data)
            mujoco.mj_forward(model, data)
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise RuntimeError("Nonfinite MuJoCo state")
            if t >= begin:
                ground_force = {leg: 0.0 for leg in legs}
                active_pairs = set()
                for index in range(data.ncon):
                    c = data.contact[index]
                    a, b = int(c.geom1), int(c.geom2)
                    mujoco.mj_contactForce(model, data, index, wrench)
                    normal = max(float(wrench[0]), 0.0)
                    label = pairs.get(frozenset((a, b)))
                    if label is not None and normal > 0:
                        active_pairs.add(label)
                        contact_impulse[label] = contact_impulse.get(label, 0.0) + normal*config.timestep_s
                    if a == ground or b == ground:
                        leg = geom_leg[b if a == ground else a]
                        if leg is not None:
                            ground_force[leg] += normal
                for label in active_pairs:
                    contact_duration[label] = contact_duration.get(label, 0.0) + config.timestep_s
                if (step + 1) % 100 == 0:
                    value = data.qpos[target_qpos].copy()
                    errors.append(value-target)
                    velocities.append(data.qvel[target_qvel].copy())
                    supports.append([ground_force[x] for x in legs])
                    heights.append(float(data.xpos[thorax, 2]))
                    positions.append(data.xpos[thorax].copy())
                    times.append(t-begin)
                    targets.append(target.copy())
                    actuals.append(value)
                    if frame_callback is not None:
                        frame_callback(model, data, t-begin)
        e = np.asarray(errors)
        result = {
            "status": "physical actuator diagnostic only; rigid antennae; not paper replication",
            "source": trace["metadata"], "source_sex": "female", "model": "current female-derived NeuroMechFly",
            "config": asdict(config), "mujoco": mujoco.__version__,
            "flygym": importlib.metadata.version("flygym"),
            "rigging_sha256": hashlib.sha256((assets_dir / "model/neuromechfly/rigging.yaml").read_bytes()).hexdigest(),
            "physics": {"solver": mujoco.mjtSolver(int(model.opt.solver)).name,
                        "iterations": int(model.opt.iterations), "noslip_iterations": int(model.opt.noslip_iterations),
                        "gravity_mm_s2": model.opt.gravity.tolist(), "native_mass_g": float(model.body_mass.sum()),
                        "contact_parameters": "FlyGym 2.1.0 ContactParams defaults; explicit 72 foreleg-antenna pairs"},
            "source_max_jump_deg_per_sample": trace["max_mapped_jump_deg"],
            "duration_replayed_s": duration, "loop_count": 1,
            "mapping": {key: {"target": value[0], "sign": value[1]} for key, value in mapped.items()},
            "antenna_mechanics": "fixed relative to head; missing paper passive parameters for current revision",
            "measured_actuation_channels": 16, "head_yaw": "fixed at model rest",
            "position_tracking_rms_deg": float(np.rad2deg(np.sqrt(np.mean(e*e)))),
            "position_tracking_max_abs_deg": float(np.rad2deg(np.abs(e).max())),
            "per_joint_tracking_rms_deg": dict(zip(mapped, np.rad2deg(np.sqrt(np.mean(e*e, axis=0))).tolist())),
            "ground_force_unit": "native g*mm/s^2", "contact_impulse_unit": "native g*mm/s",
            "mean_ground_normal_force_by_leg": dict(zip(legs, np.mean(supports, axis=0).tolist())),
            "head_leg_collision_duration_s_by_pair": contact_duration,
            "head_leg_collision_normal_impulse_by_pair": contact_impulse,
            "thorax_height_range_mm": [min(heights), max(heights)],
            "thorax_displacement_mm": (positions[-1]-positions[0]).tolist(),
            "finite": True,
            "traces": {"time_s": times, "target_rad": np.asarray(targets).tolist(),
                       "actual_rad": np.asarray(actuals).tolist(),
                       "ground_normal_force": supports, "thorax_height_mm": heights},
        }
        return result
    finally:
        sim.close()
