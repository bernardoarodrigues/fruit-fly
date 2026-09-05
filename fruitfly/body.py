"""Persistent single-fly MuJoCo body, local stimuli and finite resources.

Male CNS experiments use a clearly labeled female-derived NMF body surrogate.
The frozen hybrid walking controller is a motor abstraction, not a VNC model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Mapping

import mujoco
import numpy as np
from flygym import Simulation
from flygym.anatomy import BodySegment, ContactBodiesPreset
from flygym.compose import ActuatorType, FlatGroundWorld
from flygym.utils.math import Rotation3D
from flygym_demo.complex_terrain import (
    HybridControllerObservation, HybridTurningController, PreprogrammedSteps,
    make_locomotion_fly,
)

from .physiology import Physiology, PhysiologyConfig, ResourcePatch
from .illumination import WorldIlluminationConfig, add_world_illumination, illumination_snapshot
from .wind import local_airflow, MeasuredAntennaReference


@dataclass(frozen=True)
class BodyConfig:
    physics_dt_s: float = 0.0001
    arena_half_size_mm: float = 20.0
    initial_position_mm: tuple[float, float, float] = (-4.0, 0.0, 0.8)
    initial_heading_rad: float = 0.0
    food_position_mm: tuple[float, float] = (6.0, 0.0)
    food_radius_mm: float = 3.0
    food_amount: float = 1.5
    water_position_mm: tuple[float, float] = (5.0, 7.0)
    water_radius_mm: float = 2.0
    water_amount: float = 1.5
    wind_mm_s: tuple[float, float] = (-2.0, 0.0)
    odor_emission_interval_s: float = .1
    odor_prehistory_s: float = 3.0
    odor_puff_lifetime_s: float = 8.0
    wind_reference_path: str | None = None
    wind_reference_allow_sex_transfer: bool = False
    drive_limit: float = 1.2
    intended_sex: str = "male"
    body_profile: str = "female-derived NeuroMechFly morphology surrogate"
    width: int = 800
    height: int = 560
    enable_grooming: bool = False
    grooming_trace_path: str = "data/grooming/unilateral_left.npz"
    enable_vision: bool = False
    vision_period_s: float = .02
    world_illumination: WorldIlluminationConfig | None = None
    physiology: PhysiologyConfig = field(default_factory=PhysiologyConfig)

    def __post_init__(self):
        if isinstance(self.world_illumination, Mapping):
            object.__setattr__(self, "world_illumination", WorldIlluminationConfig(**self.world_illumination))
        if self.world_illumination is not None and not isinstance(self.world_illumination, WorldIlluminationConfig):
            raise ValueError("world_illumination must be a configuration object or None")
        scalars = (self.physics_dt_s, self.arena_half_size_mm, self.food_radius_mm,
                   self.water_radius_mm, self.drive_limit)
        if not all(math.isfinite(v) and v > 0 for v in scalars):
            raise ValueError("Timestep, arena, patch radii and drive limit must be positive")
        if self.physics_dt_s > .0001:
            raise ValueError("This body has only been tested at 0.1 ms or finer physics")
        if self.drive_limit > 1.2:
            raise ValueError("Drive limit exceeds the engineering safety bound 1.2")
        if self.width < 64 or self.height < 64:
            raise ValueError("Render dimensions must be at least 64")
        if (not math.isfinite(self.vision_period_s) or self.vision_period_s < self.physics_dt_s
                or not math.isclose(round(self.vision_period_s / self.physics_dt_s) * self.physics_dt_s,
                                    self.vision_period_s, abs_tol=1e-10)):
            raise ValueError("Vision period must be a positive integer number of physics steps")
        for name, expected in (("initial_position_mm", 3), ("food_position_mm", 2),
                               ("water_position_mm", 2), ("wind_mm_s", 2)):
            values = getattr(self, name)
            if len(values) != expected or not np.isfinite(values).all():
                raise ValueError(f"{name} must contain {expected} finite values")
        if not math.isfinite(self.initial_heading_rad):
            raise ValueError("Heading must be finite")
        if (not all(math.isfinite(v) and v > 0 for v in
                    (self.odor_emission_interval_s, self.odor_puff_lifetime_s))
                or not math.isfinite(self.odor_prehistory_s)
                or not 0 <= self.odor_prehistory_s <= self.odor_puff_lifetime_s):
            raise ValueError("Odor emission/lifetime must be positive; prehistory must lie in [0,lifetime]")
        if self.odor_puff_lifetime_s / self.odor_emission_interval_s > 100_000:
            raise ValueError("Puff resolution exceeds the supported 100,000 active-puff budget")
        for position, radius in ((self.food_position_mm, self.food_radius_mm),
                                 (self.water_position_mm, self.water_radius_mm)):
            if any(abs(v) + radius >= self.arena_half_size_mm - .2 for v in position):
                raise ValueError("Resource patches must fit inside the physical arena")
        if not all(math.isfinite(v) and v >= 0 for v in (self.food_amount, self.water_amount)):
            raise ValueError("Resources must be finite and nonnegative")
        if self.intended_sex != "male" or self.body_profile != "female-derived NeuroMechFly morphology surrogate":
            raise ValueError("Only the explicitly labeled intended-male surrogate is implemented")


class PuffField:
    """Gaussian puffs with horizontal advection and reflecting-floor images.

    Field coordinates are SI; concentration uses arbitrary mass/m^3. Emission
    is sampled at 10 Hz by default, with 3 s of initialization prehistory. Lateral
    boundaries are open even though the locomotion arena has physical walls.
    Puffs leave after 8 s by default; removed mass is explicitly tracked.
    Depleting food stops new release and does not erase old airborne puffs.
    """

    def __init__(self, source_m, wind_m_s, initial_fraction=1.0, *,
                 emission_interval_s=.1, prehistory_s=3.0, lifetime_s=8.0):
        if (not all(math.isfinite(v) and v > 0 for v in (emission_interval_s, lifetime_s))
                or not math.isfinite(prehistory_s) or not 0 <= prehistory_s <= lifetime_s
                or lifetime_s / emission_interval_s > 100_000):
            raise ValueError("Invalid puff time resolution or retention window")
        self.source = np.asarray(source_m, dtype=float)
        self.wind = np.asarray(wind_m_s, dtype=float)
        self.emission_interval_s = emission_interval_s
        self.lifetime_s = lifetime_s
        # Keep a 10 arbitrary-mass-unit/s source when refining emission timing.
        self.mass_per_puff = 10 * emission_interval_s
        count = int(math.floor(prehistory_s / emission_interval_s + 1e-10))
        self.births = [index * emission_interval_s for index in range(-count, 0)]
        self.masses = [initial_fraction * self.mass_per_puff] * len(self.births)
        self.emission_index = 0
        self.next_emission = 0.0
        self.retired_mass = 0.0

    def advance(self, t_s, source_fraction):
        while self.next_emission <= t_s + 1e-12:
            self.births.append(self.next_emission)
            self.masses.append(source_fraction * self.mass_per_puff)
            self.emission_index += 1
            self.next_emission = self.emission_index * self.emission_interval_s
        while self.births and self.births[0] < t_s - self.lifetime_s:
            self.births.pop(0)
            self.retired_mass += self.masses.pop(0)

    def sample(self, positions_m, t_s):
        positions = np.asarray(positions_m, dtype=float)
        if positions.ndim != 2 or positions.shape[1] != 3 or not np.isfinite(positions).all():
            raise ValueError("Sensor positions must be a finite (n,3) array")
        # Mesh origins can be microscopically beneath a compliant contact floor.
        positions = positions.copy()
        positions[:, 2] = np.maximum(0, positions[:, 2])
        ages = t_s - np.asarray(self.births)
        variance = .001**2 + 2 * 2e-6 * ages
        centres = self.source + ages[:, None] * self.wind
        scale = np.asarray(self.masses) / (2 * np.pi * variance)**1.5
        values = np.zeros(len(positions))
        for sign in (1, -1):
            mirrored = centres.copy()
            mirrored[:, 2] *= sign
            distances = ((positions[:, None, :] - mirrored[None, :, :])**2).sum(axis=-1)
            values += (np.exp(-distances / (2 * variance)) * scale).sum(axis=1)
        return values


class BodyRuntime:
    """Persistent physics. See docs/body-runtime.md for the fidelity contract."""

    def __init__(self, seed: int = 0, config: BodyConfig | Mapping | None = None):
        if isinstance(config, Mapping):
            config = dict(config)
            if isinstance(config.get("physiology"), Mapping):
                config["physiology"] = PhysiologyConfig(**config["physiology"])
            config = BodyConfig(**config)
        self.config = config or BodyConfig()
        self.seed = int(seed)
        self._renderer = None
        self._closed = False
        self.wind_reference = (MeasuredAntennaReference(self.config.wind_reference_path,
            intended_sex=self.config.intended_sex,
            allow_sex_transfer=self.config.wind_reference_allow_sex_transfer)
            if self.config.wind_reference_path else None)
        self._build()
        self.reset(seed)

    @property
    def timestep(self):
        return self.config.physics_dt_s

    @property
    def time_s(self):
        return self._ticks * self.timestep

    def _build(self):
        cfg = self.config
        world = FlatGroundWorld(half_size=cfg.arena_half_size_mm)
        h = cfg.arena_half_size_mm
        for name, pos, size in (
            ("west", (-h, 0, 1.5), (.2, h, 1.5)),
            ("east", (h, 0, 1.5), (.2, h, 1.5)),
            ("south", (0, -h, 1.5), (h, .2, 1.5)),
            ("north", (0, h, 1.5), (h, .2, 1.5)),
        ):
            geom = world.mjcf_root.worldbody.add_geom(name=name, type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=pos, size=size, rgba=(.3, .43, .5, .25), contype=0, conaffinity=0)
            world.ground_geoms.append(geom)
        for name, xy, radius, rgba in (
            ("food_patch", cfg.food_position_mm, cfg.food_radius_mm, (.95, .65, .15, 1)),
            ("water_patch", cfg.water_position_mm, cfg.water_radius_mm, (.15, .55, .95, 1)),
        ):
            geom = world.mjcf_root.worldbody.add_geom(name=name,
                type=mujoco.mjtGeom.mjGEOM_CYLINDER, pos=(*xy, .035), size=(radius, .035, 0),
                rgba=rgba, contype=0, conaffinity=0)
            world.ground_geoms.append(geom)
        # A visual landmark is not a source signal or target observation.
        landmark = world.mjcf_root.worldbody.add_geom(name="landmark", type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=(-13, 12, 1), size=(.8, .8, 1), rgba=(.7, .25, .4, 1), contype=0, conaffinity=0)
        world.ground_geoms.append(landmark)
        if cfg.enable_grooming:
            from .grooming import ReplayConfig, make_grooming_fly
            self._grooming_config = ReplayConfig(timestep_s=cfg.physics_dt_s)
            self.fly = make_grooming_fly(self._grooming_config, name="fly")
        else:
            self.fly = make_locomotion_fly(name="fly", add_adhesion=True, colorize=True)
        if cfg.enable_vision:
            self.fly.add_vision()
        angle = cfg.initial_heading_rad / 2
        world.add_fly(self.fly, cfg.initial_position_mm,
            Rotation3D("quat", [math.cos(angle), 0, 0, math.sin(angle)]),
            bodysegs_with_ground_contact=ContactBodiesPreset.LEGS_THORAX_ABDOMEN_HEAD,
            add_ground_contact_sensors=False)
        grooming_pairs = {}
        if cfg.enable_grooming:
            from .grooming import add_grooming_contacts
            grooming_pairs = add_grooming_contacts(world, self.fly)
        world.mjcf_root.worldbody.add_camera(name="overview", pos=(0, -32, 39),
            xyaxes=(1, 0, 0, 0, .773, .634), fovy=49)
        if cfg.world_illumination is not None:
            add_world_illumination(world.mjcf_root, cfg.world_illumination)
        self.sim = Simulation(world, timestep=cfg.physics_dt_s)
        self.model, self.data = self.sim.mj_model, self.sim.mj_data
        self.model.vis.global_.offwidth = max(cfg.width, self.model.vis.global_.offwidth)
        self.model.vis.global_.offheight = max(cfg.height, self.model.vis.global_.offheight)
        steps = PreprogrammedSteps()
        full_order = self.fly.get_actuated_jointdofs_order("position")
        leg_indices = [i for i, dof in enumerate(full_order) if dof.child.is_leg()]
        order = [full_order[i] for i in leg_indices]
        self.controller = HybridTurningController(timestep=cfg.physics_dt_s,
            preprogrammed_steps=steps, output_dof_order=order)
        self._neutral_angles = steps.default_pose_by_dof_order(order)
        full_actuator_ids = np.asarray(self.sim._intern_actuatorids_by_type_by_fly[ActuatorType.POSITION][self.fly.name])
        self._position_actuator_ids = full_actuator_ids[leg_indices]
        head_indices = [i for i, dof in enumerate(full_order) if dof.child.name == "c_head"]
        self._head_position_actuator_ids = full_actuator_ids[head_indices]
        self._head_neutral_angles = np.asarray([self.fly.jointdof_to_neutralangle[full_order[i]] for i in head_indices])
        self._grooming = None
        self._grooming_pair_labels = list(grooming_pairs.values())
        self._grooming_pair_lookup = np.full((self.model.ngeom, self.model.ngeom), -1, dtype=np.int16) if cfg.enable_grooming else None
        if cfg.enable_grooming:
            from .grooming import GroomingPlayback, source_joint_map
            by_name = {dof.name: int(full_actuator_ids[i]) for i, dof in enumerate(full_order)}
            self._grooming_actuator_ids = np.asarray([by_name[name] for name, _ in source_joint_map().values()])
            neutral = np.zeros(self.model.nu)
            neutral[self._position_actuator_ids] = self._neutral_angles
            neutral[self._head_position_actuator_ids] = self._head_neutral_angles
            path = Path(cfg.grooming_trace_path)
            if not path.is_absolute():
                path = Path(__file__).resolve().parents[1] / path
            self._grooming = GroomingPlayback(path, neutral[self._grooming_actuator_ids], self._grooming_config)
            for index, (a, b) in enumerate(grooming_pairs):
                ia, ib = (mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, name) for name in (a, b))
                if min(ia, ib) < 0:
                    raise RuntimeError("Missing grooming collision geometry")
                self._grooming_pair_lookup[ia, ib] = self._grooming_pair_lookup[ib, ia] = index
        self._adhesion_actuator_ids = self.sim._intern_adhesionactuatorids_by_fly[self.fly.name]
        body_order = self.fly.get_bodysegs_order()
        body_ids = self.sim._internal_bodyids_by_fly[self.fly.name]
        id_for = lambda name: body_ids[body_order.index(BodySegment(name))]
        self._thorax_id = id_for("c_thorax")
        # Fixed head bodies may be fused by MuJoCo's compiler. Its named geom
        # survives fusion; a missing body ID (-1) must never index the last leg.
        self._head_geom_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "fly/c_head")
        self._antenna_ids = [id_for(side + "_funiculus") for side in ("l", "r")]
        if min(self._thorax_id, self._head_geom_id, *self._antenna_ids) < 0:
            raise RuntimeError("Required thorax, head or antenna frame is missing after compilation")
        if len(set(self._antenna_ids)) != 2:
            raise RuntimeError("Left and right antenna frames must be distinct")
        # Imported head mesh axes are not forward/left/up. Define that basis
        # from the neutral keyframe's thorax, then let it follow head rotation.
        reference = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, reference, self.sim._neutral_keyframe_id)
        mujoco.mj_forward(self.model, reference)
        self._head_anatomical_basis = (reference.geom_xmat[self._head_geom_id].reshape(3, 3).T
                                      @ reference.xmat[self._thorax_id].reshape(3, 3))
        self._antenna_jacobian = np.empty((3, self.model.nv))
        self._tarsus5_ids = [id_for(leg + "_tarsus5") for leg in self.controller.legs]
        if min(self._tarsus5_ids) < 0:
            raise RuntimeError("Required distal leg frame is missing after compilation")
        geom_map = self.sim._internal_geomid_by_bodyseg_by_fly[self.fly.name]
        self._stumble_map = np.full(self.model.ngeom, -1, dtype=int)
        for index, segment in enumerate(BodySegment(f"{leg}_{link}")
                for leg in self.controller.legs for link in ("tibia", "tarsus1", "tarsus2")):
            self._stumble_map[geom_map[segment]] = index
        self._leg_map = np.full(self.model.ngeom, -1, dtype=int)
        for segment, geom_id in geom_map.items():
            for leg_index, leg in enumerate(self.controller.legs):
                if segment.name.startswith(leg + "_"):
                    self._leg_map[geom_id] = leg_index
        joint_order = self.fly.get_jointdofs_order()
        qpos_ids = self.sim._intern_qposadrs_by_fly[self.fly.name]
        qvel_ids = self.sim._intern_qveladrs_by_fly[self.fly.name]
        if cfg.enable_grooming:
            qpos_by_name = dict(zip((dof.name for dof in joint_order), qpos_ids))
            self._grooming_qpos_ids = np.asarray([qpos_by_name[name] for name, _ in source_joint_map().values()])
        self._proprio_joint_qpos = {}
        self._proprio_joint_qvel = {}
        for label, child in (("coxa_pitch", "coxa"),
                             ("femur_pitch", "trochanterfemur"), ("tibia_pitch", "tibia")):
            indices = [next(i for i, joint in enumerate(joint_order)
                            if joint.child.name == f"{leg}_{child}" and joint.axis.value == "pitch")
                       for leg in self.controller.legs]
            self._proprio_joint_qpos[label] = np.asarray(qpos_ids)[indices]
            self._proprio_joint_qvel[label] = np.asarray(qvel_ids)[indices]
        self._is_tarsus = np.array(["tarsus" in (mujoco.mj_id2name(self.model,
            mujoco.mjtObj.mjOBJ_GEOM, i) or "") for i in range(self.model.ngeom)])
        self._is_ground = np.zeros(self.model.ngeom, dtype=bool)
        self._is_ground[self.sim._internal_ground_geom_ids] = True
        self._food_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "food_patch")
        self._water_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "water_patch")
        self._forces = np.zeros((18, 3))
        self._support_forces = np.zeros((6, 3))
        self._wrench = np.zeros(6)
        self._body_velocity = np.zeros(6)
        self._original_diffuse = self.model.light_diffuse.copy()
        self._original_ambient = self.model.light_ambient.copy()
        self._original_headlight = {name: getattr(self.model.vis.headlight, name).copy()
                                    for name in ("ambient", "diffuse", "specular")}
        self._vision_stride = round(cfg.vision_period_s / cfg.physics_dt_s)

    def reset(self, seed: int | None = None):
        if seed is not None:
            self.seed = int(seed)
        if self._closed:
            raise RuntimeError("Runtime is closed")
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.sim._neutral_keyframe_id)
        self.controller.reset(seed=self.seed)
        self.data.ctrl[self._position_actuator_ids] = self._neutral_angles
        self.data.ctrl[self._head_position_actuator_ids] = self._head_neutral_angles
        if self._grooming is not None:
            self._grooming.reset()
        self._grooming_contact_force = np.zeros(len(self._grooming_pair_labels))
        self._grooming_contact_s = np.zeros(len(self._grooming_pair_labels))
        self._grooming_any_contact_s = 0.0
        self._grooming_error_squared_sum = 0.0
        self._grooming_error_count = 0
        self._grooming_error_max_rad = 0.0
        self.data.ctrl[self._adhesion_actuator_ids] = 1
        self.sim.warmup(.05)
        self.data.time = 0
        mujoco.mj_forward(self.model, self.data)
        self._ticks = 0
        self._mode = "rest"
        self._drive = np.zeros(2)
        self._stimuli = {"odor": 1.0, "light": 1.0}
        self.model.light_diffuse[:] = self._original_diffuse
        self.model.light_ambient[:] = self._original_ambient
        for name, values in self._original_headlight.items():
            getattr(self.model.vis.headlight, name)[:] = values
        self.physiology = Physiology(self.config.physiology)
        self.food = ResourcePatch("food", "food", self.config.food_amount)
        self.water = ResourcePatch("water", "water", self.config.water_amount)
        self.field = PuffField((*np.asarray(self.config.food_position_mm) * .001, .00007),
                              (*np.asarray(self.config.wind_mm_s) * .001, 0), self.food.fraction,
                              emission_interval_s=self.config.odor_emission_interval_s,
                              prehistory_s=self.config.odor_prehistory_s,
                              lifetime_s=self.config.odor_puff_lifetime_s)
        self.field.advance(0, self.food.fraction)
        self._update_contact_cache()
        self._vision = None
        self._vision_time_s = None
        if self.config.enable_vision:
            self._sample_vision()
        return self.observe()

    def _update_contact_cache(self):
        """Same ground-force semantics as FlyGym, with precompiled lookup arrays."""
        self._forces.fill(0)
        self._support_forces.fill(0)
        contacts, n = self.data.contact, self.data.ncon
        g1, g2 = contacts.geom1[:n], contacts.geom2[:n]
        valid = contacts.exclude[:n] == 0
        a, b = self._stumble_map[g1], self._stumble_map[g2]
        leg_a, leg_b = self._leg_map[g1], self._leg_map[g2]
        active = valid & (((leg_a >= 0) & self._is_ground[g2]) |
                          ((leg_b >= 0) & self._is_ground[g1]))
        for k in np.flatnonzero(active):
            mujoco.mj_contactForce(self.model, self.data, int(k), self._wrench)
            force = contacts.frame[k].reshape(3, 3).T @ self._wrench[:3]
            if a[k] >= 0:
                self._forces[a[k]] -= force
            if b[k] >= 0:
                self._forces[b[k]] += force
            if leg_a[k] >= 0:
                self._support_forces[leg_a[k]] -= force
            if leg_b[k] >= 0:
                self._support_forces[leg_b[k]] += force
        actual = valid & (contacts.dist[:n] <= 0)
        def taste(patch_id):
            sensed = actual & (((g1 == patch_id) & self._is_tarsus[g2]) |
                               ((g2 == patch_id) & self._is_tarsus[g1]))
            touched_legs = np.where(g1 == patch_id, leg_b, leg_a)[sensed]
            by_leg = np.zeros(6, dtype=bool)
            by_leg[touched_legs[touched_legs >= 0]] = True
            return by_leg
        self._food_contact_by_leg = taste(self._food_id)
        self._water_contact_by_leg = taste(self._water_id)
        self._food_contact = bool(self._food_contact_by_leg.any())
        self._water_contact = bool(self._water_contact_by_leg.any())
        if self._grooming is not None:
            self._grooming_contact_force.fill(0)
            pairs = self._grooming_pair_lookup[g1, g2]
            for k in np.flatnonzero(valid & (pairs >= 0)):
                mujoco.mj_contactForce(self.model, self.data, int(k), self._wrench)
                self._grooming_contact_force[pairs[k]] += max(float(self._wrench[0]), 0.0)

    def _controller_observation(self):
        return HybridControllerObservation(
            thorax_z=float(self.data.xpos[self._thorax_id, 2]),
            tarsus5_z=self.data.xpos[self._tarsus5_ids, 2],
            stumbling_contact_forces=self._forces.reshape(6, 3, 3),
            fly_heading=self.data.xmat[self._thorax_id].reshape(3, 3)[:, 0],
        )

    def _velocity(self):
        mujoco.mj_objectVelocity(self.model, self.data, mujoco.mjtObj.mjOBJ_BODY,
                                self._thorax_id, self._body_velocity, 0)
        return self._body_velocity

    def advance(self, duration_s: float, drive_left: float = 1.0,
                drive_right: float = 1.0, behavior: str = "walk") -> dict:
        if self._closed:
            raise RuntimeError("Runtime is closed")
        if behavior not in ("walk", "rest", "feed", "groom"):
            raise ValueError("Supported motor modes: walk, rest, feed, groom")
        if behavior == "groom" and self._grooming is None:
            raise ValueError("Grooming requires BodyConfig(enable_grooming=True)")
        if not math.isfinite(duration_s) or duration_s < 0:
            raise ValueError("Duration must be finite and nonnegative")
        count = round(duration_s / self.timestep)
        if not math.isclose(count * self.timestep, duration_s, abs_tol=1e-10):
            raise ValueError("Duration must be an integer number of physics timesteps")
        requested = np.asarray([drive_left, drive_right], dtype=float)
        if not np.isfinite(requested).all():
            raise ValueError("Drive must be finite")
        self._drive = np.clip(requested, -self.config.drive_limit, self.config.drive_limit)
        for _ in range(count):
            grooming_target = None
            if self._grooming is not None:
                grooming_target = self._grooming.step(behavior == "groom" and self.physiology.alive,
                    self.data.ctrl[self._grooming_actuator_ids], self.timestep)
            self._mode = ("groom" if self._grooming is not None and self._grooming.active
                          else "rest" if behavior == "groom" else behavior)
            if behavior == "walk" and self.physiology.alive and grooming_target is None:
                action = self.controller.step(self._drive, self._controller_observation())
                self.data.ctrl[self._position_actuator_ids] = action.joint_angles
                self.data.ctrl[self._adhesion_actuator_ids] = action.adhesion_onoff
            else:
                # Smoothly return to the published standing pose; hold actuators.
                alpha = 1 - math.exp(-self.timestep / .02)
                current = self.data.ctrl[self._position_actuator_ids]
                self.data.ctrl[self._position_actuator_ids] = current + alpha * (self._neutral_angles - current)
                self.data.ctrl[self._adhesion_actuator_ids] = 1
            self.data.ctrl[self._head_position_actuator_ids] = self._head_neutral_angles
            if grooming_target is not None:
                self.data.ctrl[self._grooming_actuator_ids] = grooming_target
                # Keep the four unrecorded legs standing; release foreleg pads.
                self.data.ctrl[self._adhesion_actuator_ids] = [0, 1, 1, 0, 1, 1]
            self.sim.step()
            self._ticks += 1
            # mj_step's derived caches are pre-integration; refresh exactly once
            # before controller, sensory and ingestion observations of this time.
            mujoco.mj_forward(self.model, self.data)
            self._update_contact_cache()
            if self._grooming is not None:
                contacts = self._grooming_contact_force > 0
                self._grooming_contact_s += contacts * self.timestep
                self._grooming_any_contact_s += float(contacts.any()) * self.timestep
                if self._grooming.tracking_active:
                    errors = self.data.qpos[self._grooming_qpos_ids] - grooming_target
                    self._grooming_error_squared_sum += float(np.square(errors).sum())
                    self._grooming_error_count += len(errors)
                    self._grooming_error_max_rad = max(self._grooming_error_max_rad, float(np.abs(errors).max()))
            speed = float(np.linalg.norm(self._velocity()[3:5]))
            self.physiology.advance(self.timestep, speed_mm_s=speed,
                food_contact=self._food_contact, water_contact=self._water_contact,
                feed_requested=self._mode == "feed", food=self.food, water=self.water)
            self.field.advance(self.time_s, self.food.fraction * self._stimuli["odor"])
            if self.config.enable_vision and self._ticks % self._vision_stride == 0:
                self._sample_vision()
        if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all():
            raise RuntimeError("Nonfinite body state")
        return self.observe()

    def observe(self) -> dict:
        antenna_m = self.data.xpos[self._antenna_ids] * .001
        heading = self.data.xmat[self._thorax_id].reshape(3, 3)[:, 0]
        velocity = self._velocity()
        thorax_rotation = self.data.xmat[self._thorax_id].reshape(3, 3)
        return {
            "t_s": self.time_s,
            "antenna_odor": self.field.sample(antenna_m, self.time_s).tolist(),
            "wind": self._observe_wind(),
            "taste_food": bool(self._food_contact and self.food.remaining > 0),
            "taste_water": bool(self._water_contact and self.water.remaining > 0),
            "food_contact_by_leg": {leg.upper(): bool(contact and self.food.remaining > 0)
                                    for leg, contact in zip(self.controller.legs, self._food_contact_by_leg)},
            "water_contact_by_leg": {leg.upper(): bool(contact and self.water.remaining > 0)
                                     for leg, contact in zip(self.controller.legs, self._water_contact_by_leg)},
            "light_intensity": self._stimuli["light"],
            "proprioception": {
                "speed_mm_s": float(np.linalg.norm(velocity[3:5])),
                "yaw_rate_rad_s": float(velocity[2]),
                "tarsus_height_mm": self.data.xpos[self._tarsus5_ids, 2].tolist(),
                "ground_force_by_leg": self._support_forces.tolist(),
                "joint_angles_rad": {key: self.data.qpos[ids].tolist()
                                     for key, ids in self._proprio_joint_qpos.items()},
                "joint_velocities_rad_s": {key: self.data.qvel[ids].tolist()
                                           for key, ids in self._proprio_joint_qvel.items()},
                "body_angular_velocity_rad_s": (thorax_rotation.T @ velocity[:3]).tolist(),
            },
            "pose": {"position_mm": self.data.xpos[self._thorax_id].tolist(),
                     "heading_rad": math.atan2(heading[1], heading[0])},
            "physiology": self.physiology.snapshot(),
            "motor": {"mode": self._mode, "drive": self._drive.tolist()},
            "grooming": self._observe_grooming(),
            "vision": {"enabled": self.config.enable_vision, "sample_t_s": self._vision_time_s,
                       "shape": list(self._vision.shape) if self._vision is not None else None,
                       "mean_by_eye": self._vision.mean(axis=(1, 2)).tolist() if self._vision is not None else None},
        }

    def _observe_grooming(self):
        if self._grooming is None:
            return {"enabled": False, "state": "disabled", "requested": False,
                    "actual_active": False, "armed": False, "source_time_s": None,
                    "completed_count": 0, "cancelled_count": 0}
        return {**self._grooming.snapshot(),
                "contact_count": int(np.count_nonzero(self._grooming_contact_force)),
                "contact_by_pair": {label: float(force) for label, force in
                    zip(self._grooming_pair_labels, self._grooming_contact_force) if force > 0},
                "contact_force_unit": "native g mm/s^2; constraint normal force, not experimentally calibrated",
                "contact_s": self._grooming_any_contact_s,
                "contact_s_by_pair": {label: float(seconds) for label, seconds in
                    zip(self._grooming_pair_labels, self._grooming_contact_s) if seconds > 0},
                "tracking_sample_count": self._grooming_error_count // 16,
                "tracking_rms_deg": (math.degrees(math.sqrt(self._grooming_error_squared_sum /
                    self._grooming_error_count)) if self._grooming_error_count else None),
                "tracking_max_deg": math.degrees(self._grooming_error_max_rad) if self._grooming_error_count else None}

    def _observe_wind(self):
        velocities = np.empty((2, 3))
        for index, body_id in enumerate(self._antenna_ids):
            # Jacobian at the same body origin used for odor sampling. This
            # includes base translation, rotation and antennal joint motion.
            mujoco.mj_jacBody(self.model, self.data, self._antenna_jacobian, None, body_id)
            velocities[index] = self._antenna_jacobian @ self.data.qvel
        head_to_world = (self.data.geom_xmat[self._head_geom_id].reshape(3, 3)
                         @ self._head_anatomical_basis)
        observation = local_airflow((*self.config.wind_mm_s, 0), velocities, head_to_world)
        if self.wind_reference is not None:
            observation["antenna_reference"] = self.wind_reference.evaluate(observation)
        return observation

    def _sample_vision(self):
        self._vision = self.sim.get_ommatidia_readouts(self.fly.name)
        if not np.isfinite(self._vision).all():
            raise RuntimeError("Nonfinite compound-eye readings")
        self._vision_time_s = self.time_s

    def vision_readouts(self) -> np.ndarray | None:
        """Cached actual left/right compound eyes, ordered yellow/pale channels.

        Arrays preserve the pinned FlyGym retina's native intensity convention.
        This method never advances physics or renders an additional frame.
        """
        return self._vision.copy() if self._vision is not None else None

    def set_stimulus(self, name: str, value: float):
        if name not in self._stimuli:
            raise ValueError("Stimulus must be odor or light")
        if not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError("Stimulus gain must be finite and in [0,10]")
        self._stimuli[name] = float(value)
        if name == "light":
            self.model.light_diffuse[:] = self._original_diffuse * value
            self.model.light_ambient[:] = self._original_ambient * value
            for name, values in self._original_headlight.items():
                getattr(self.model.vis.headlight, name)[:] = values * value

    def snapshot(self) -> dict:
        """Observer/evaluator state. Never pass this privileged world data to brain."""
        return {"observation": self.observe(), "config": asdict(self.config),
                "illumination": illumination_snapshot(self.model, self.config.world_illumination, self._stimuli["light"]),
                "wind_reference": self.wind_reference.provenance if self.wind_reference else None,
                "grooming_reference": ({"source": self._grooming.trace["metadata"],
                    "control": asdict(self._grooming_config)} if self._grooming is not None else None),
                "stimuli": self._stimuli.copy(),
                "resources": {"food": asdict(self.food), "water": asdict(self.water)},
                "resource_balance": self.physiology.balance_residuals(self.food, self.water),
                "physics": {"nq": self.model.nq, "nv": self.model.nv, "nu": self.model.nu,
                            "contacts": self.data.ncon, "timestep_s": self.timestep,
                            "initialization_settling_s": .05},
                "controller": {"name": "FlyGym HybridTurningController CPG/reflex surrogate",
                               "phases": self.controller.cpg_network.curr_phases.tolist(),
                               "magnitudes": self.controller.cpg_network.curr_magnitudes.tolist()},
                "field": {"puffs": len(self.field.births),
                          "retired_arbitrary_mass": self.field.retired_mass},
                "seed": self.seed}

    def render(self, camera: str = "follow") -> np.ndarray:
        if camera not in ("follow", "overview", "side"):
            raise ValueError("Camera must be follow, overview or side")
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=self.config.height, width=self.config.width)
        if camera == "overview":
            selected = "overview"
        else:
            selected = mujoco.MjvCamera()
            selected.type = mujoco.mjtCamera.mjCAMERA_FREE
            selected.lookat[:] = self.data.xpos[self._thorax_id]
            selected.distance = 11.0 if camera == "follow" else 7.0
            selected.azimuth = 135 if camera == "follow" else 90
            selected.elevation = -36 if camera == "follow" else -12
        self._renderer.update_scene(self.data, camera=selected)
        return self._renderer.render().copy()

    def close(self):
        if not self._closed:
            if self._renderer is not None:
                self._renderer.close()
                self._renderer = None
            self.sim.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
