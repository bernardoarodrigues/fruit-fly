"""Optional FlyBody adapter with bounded or rolling references; host biology plus isolated native physics.

The source body is female-derived. Its pretrained motor policy and engineering
posture hold are not a male VNC or a biological descending-neuron controller.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import select
import struct
import subprocess
import tempfile
import time
from typing import Mapping

import numpy as np

from .physiology import Physiology, PhysiologyConfig, ResourcePatch

ROOT = Path(__file__).resolve().parents[1]
LEGS = ("LF", "LM", "LH", "RF", "RM", "RH")
PROFILE = "female-derived FlyBody morphology surrogate"


class FlyBodyWorkerError(RuntimeError):
    """A framed native-task error, distinct from a broken transport."""


@dataclass(frozen=True)
class FlyBodyConfig:
    physics_dt_s: float = .0002
    horizon_s: float | None = 2.
    reference_mode: str = "bounded"
    source_path: str = "data/raw/flybody/source"
    worker_python: str = "tmp/flybody-env/bin/python"
    initial_position_mm: tuple[float, float, float] = (0., 0., 1.278)
    initial_heading_rad: float = 0.
    food_position_mm: tuple[float, float] = (6., 0.)
    food_radius_mm: float = 3.
    food_amount: float = 1.5
    water_position_mm: tuple[float, float] = (5., 7.)
    water_radius_mm: float = 2.
    water_amount: float = 1.5
    wind_mm_s: tuple[float, float] = (-2., 0.)
    odor_emission_interval_s: float = .1
    odor_prehistory_s: float = 3.
    odor_puff_lifetime_s: float = 8.
    drive_limit: float = 1.2
    intended_sex: str = "male"
    body_profile: str = PROFILE
    width: int = 800
    height: int = 560
    enable_grooming: bool = False
    enable_vision: bool = False
    world_illumination: None = None
    wind_reference_path: None = None
    wind_reference_allow_sex_transfer: bool = False
    physiology: PhysiologyConfig = field(default_factory=PhysiologyConfig)

    def __post_init__(self):
        if isinstance(self.physiology, Mapping):
            object.__setattr__(self, "physiology", PhysiologyConfig(**self.physiology))
        if not isinstance(self.physiology, PhysiologyConfig):
            raise ValueError("physiology must be a PhysiologyConfig or mapping")
        if self.physics_dt_s != .0002:
            raise ValueError("FlyBody physics step is fixed to 0.2 ms")
        if self.reference_mode not in ("bounded", "rolling"):
            raise ValueError("FlyBody reference mode must be bounded or rolling")
        if (self.reference_mode == "bounded" and self.horizon_s != 2.
                or self.reference_mode == "rolling" and self.horizon_s is not None):
            raise ValueError("Bounded FlyBody requires a 2 s horizon; rolling requires explicit null")
        if tuple(self.initial_position_mm) != (0., 0., 1.278) or self.initial_heading_rad != 0.:
            raise ValueError("First FlyBody backend preserves source initial pose")
        if self.drive_limit != 1.2 or self.intended_sex != "male" or self.body_profile != PROFILE:
            raise ValueError("FlyBody requires the explicit intended-male female-derived profile and1.2 drive bound")
        if self.enable_grooming or self.enable_vision or self.world_illumination is not None or self.wind_reference_path is not None or self.wind_reference_allow_sex_transfer:
            raise ValueError("FlyBody grooming, ommatidia, world illumination and empirical wind transfer are not implemented")
        for name in ("food_position_mm", "water_position_mm", "wind_mm_s"):
            values = getattr(self, name)
            if len(values) != 2 or not np.isfinite(values).all():
                raise ValueError(name + " must contain two finite values")
        for name in ("food_radius_mm", "water_radius_mm", "odor_emission_interval_s", "odor_puff_lifetime_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(name + " must be positive and finite")
        for name in ("food_amount", "water_amount", "odor_prehistory_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(name + " must be nonnegative and finite")
        if self.odor_prehistory_s > self.odor_puff_lifetime_s or self.odor_puff_lifetime_s / self.odor_emission_interval_s > 100_000:
            raise ValueError("Invalid puff lifetime/prehistory/resolution")
        if any(not isinstance(v, int) or not 64 <= v <= 2048 for v in (self.width, self.height)):
            raise ValueError("Integer render dimensions must lie in[64,2048]")

    @property
    def timestep(self):
        return self.physics_dt_s


def map_drive(left, right, behavior):
    """Frozen engineering map; accepts no physical or world observations."""
    if behavior not in ("walk", "rest", "feed"):
        raise ValueError("FlyBody supports walk, rest and abstract feed only")
    if not all(math.isfinite(v) for v in (left, right)):
        raise ValueError("Motor drive must be finite")
    drive = np.clip([left, right], -1.2, 1.2)
    speed = 20. * float(np.clip(drive.mean(), 0, 1))
    yaw = 2. * float(np.clip((drive[1] - drive[0]) / 1.2, -1, 1))
    if behavior != "walk":
        speed = yaw = 0.
    return drive, speed, yaw


class FlyBodyRuntime:
    control_timestep_s = .002
    wind_reference = None

    def __init__(self, seed=0, config=None, log_path=None):
        self.config = FlyBodyConfig(**dict(config)) if isinstance(config, Mapping) else (config or FlyBodyConfig())
        if not isinstance(self.config, FlyBodyConfig):
            raise TypeError("Expected FlyBodyConfig")
        self.seed = int(seed)
        self._closed = False
        self._proc = None
        self._request_id = 0
        self._state = None
        self._observation = None
        self._drive = np.zeros(2)
        self._mode = "rest"
        self._last_error = None
        self._transport_failed = None
        self._initialize_host()
        if log_path is None:
            fd, name = tempfile.mkstemp(prefix="fruitfly-flybody-", suffix=".log")
            os.close(fd)
            self.log_path = Path(name)
        else:
            self.log_path = Path(log_path).resolve()
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("ab", buffering=0)
        config_dict = asdict(self.config)
        interpreter = Path(self.config.worker_python)
        if not interpreter.is_absolute():
            interpreter = ROOT / interpreter
        source = Path(self.config.source_path)
        if not source.is_absolute():
            source = ROOT / source
        config_dict["source_path"] = str(source)
        try:
            self._proc = subprocess.Popen([str(interpreter), str(ROOT / "fruitfly/flybody_worker.py")],
                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log, bufsize=0)
            reply = self._rpc("init", config=config_dict, seed=self.seed)
            self._metadata = reply["metadata"]
            self._accept_state(reply["state"])
        except BaseException:
            self.close()
            raise

    @property
    def timestep(self):
        return self.config.physics_dt_s

    @property
    def time_s(self):
        return self._state["native_time_s"] if self._state is not None else 0.

    def _initialize_host(self):
        # This dependency stays in Python3.12; the native worker never imports
        # the FlyGym/new-MuJoCo body module.
        from .body import PuffField
        self.food = ResourcePatch("food", "food", self.config.food_amount)
        self.water = ResourcePatch("water", "water", self.config.water_amount)
        self.physiology = Physiology(self.config.physiology)
        self._stimuli = {"odor": 1., "light": 1.}
        self.field = PuffField((*np.asarray(self.config.food_position_mm) * .001, .00007),
            (*np.asarray(self.config.wind_mm_s) * .001, 0.),
            initial_fraction=self.food.fraction,
            emission_interval_s=self.config.odor_emission_interval_s,
            prehistory_s=self.config.odor_prehistory_s,
            lifetime_s=self.config.odor_puff_lifetime_s)
        self.field.advance(0, self.food.fraction)

    def _read_exact(self, count, deadline):
        chunks = []
        while count:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self._proc.stdout], [], [], max(0, remaining))[0]:
                raise TimeoutError("FlyBody worker timed out; see " + str(self.log_path))
            chunk = os.read(self._proc.stdout.fileno(), count)
            if not chunk:
                raise RuntimeError("FlyBody worker closed its pipe; see " + str(self.log_path))
            chunks.append(chunk)
            count -= len(chunk)
        return b"".join(chunks)

    def _rpc(self, op, **arguments):
        if self._transport_failed:
            raise RuntimeError("FlyBody transport is terminal: " + self._transport_failed)
        try:
            return self._exchange(op, **arguments)
        except FlyBodyWorkerError:
            raise
        except (OSError, RuntimeError, TimeoutError, ValueError, struct.error) as error:
            # A late reply after timeout could be mistaken for the next request.
            # Stop this process; only a new runtime can restore framing safely.
            self._transport_failed = str(error)
            self._last_error = str(error)
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
            raise

    def _exchange(self, op, **arguments):
        if self._closed or self._proc is None:
            raise RuntimeError("FlyBody worker is closed")
        self._request_id += 1
        request = {"version": 1, "id": self._request_id, "op": op, **arguments}
        raw = json.dumps(request, allow_nan=False, separators=(",", ":")).encode()
        self._proc.stdin.write(struct.pack("!I", len(raw)) + raw)
        deadline = time.monotonic() + (60 if op in ("init", "reset", "render") else 15)
        size = struct.unpack("!I", self._read_exact(4, deadline))[0]
        if size > 4_000_000:
            raise RuntimeError("Oversized FlyBody response")
        reply = json.loads(self._read_exact(size, deadline))
        if reply.get("version") != 1 or reply.get("id") != self._request_id:
            raise RuntimeError("FlyBody protocol/request mismatch")
        if reply.get("binary_bytes", 0):
            count = reply["binary_bytes"]
            if count != self.config.width * self.config.height * 3:
                raise RuntimeError("Invalid FlyBody frame size")
            reply["rgb"] = np.frombuffer(self._read_exact(count, deadline), np.uint8).reshape(reply["image_shape"]).copy()
        if not reply["ok"]:
            self._last_error = reply["error"]
            if "state" in reply:
                self._accept_state(reply["state"], failed=True)
            raise FlyBodyWorkerError(reply["error"] + "; see " + str(self.log_path))
        return reply

    def _contacts(self, state, kind):
        xy = np.asarray(getattr(self.config, kind + "_position_mm"))
        radius = getattr(self.config, kind + "_radius_mm")
        contacts = {leg: False for leg in LEGS}
        for c in state["contacts"]:
            if c["active"] and c["is_tarsal"] and np.linalg.norm(np.asarray(c["position_mm"][:2]) - xy) <= radius:
                contacts[c["leg"]] = True
        return contacts

    def _accept_state(self, state, failed=False):
        previous = self.time_s
        self._state = state
        if not state["finite"]:
            # Retain raw failure diagnostics without inventing a finite sensor
            # observation for a failed physics step.
            return
        food, water = self._contacts(state, "food"), self._contacts(state, "water")
        speed = float(np.linalg.norm(state["velocity_world_mm_s"][:2]))
        dt = state["native_time_s"] - previous
        if dt > 0:
            if not math.isclose(dt, self.control_timestep_s, abs_tol=1e-10):
                if failed:
                    # A failing partial native step cannot be presented as a
                    # completed host physiology tick. Raw clock/state remain.
                    self._cache_observation(food, water, speed)
                    return
                raise RuntimeError("Worker did not return exactly one2ms control step")
            self.physiology.advance(self.control_timestep_s, speed_mm_s=speed,
                food_contact=any(food.values()), water_contact=any(water.values()),
                feed_requested=self._mode == "feed", food=self.food, water=self.water)
            self.field.advance(self.time_s, self.food.fraction * self._stimuli["odor"])
        self._cache_observation(food, water, speed)

    def _cache_observation(self, food=None, water=None, speed=None):
        state = self._state
        if state is None or not state["finite"]:
            return
        food = self._contacts(state, "food") if food is None else food
        water = self._contacts(state, "water") if water is None else water
        food = {leg: contact and self.food.remaining > 0 for leg, contact in food.items()}
        water = {leg: contact and self.water.remaining > 0 for leg, contact in water.items()}
        if speed is None:
            speed = float(np.linalg.norm(state["velocity_world_mm_s"][:2]))
        angles = {"tibia_pitch": state["tibia_rad"], "source_coxa": state["joint_angles_rad"]["coxa"],
                  "source_femur": state["joint_angles_rad"]["femur"]}
        velocities = {"tibia_pitch": state["tibia_velocity_rad_s"], "source_coxa": state["joint_velocities_rad_s"]["coxa"],
                      "source_femur": state["joint_velocities_rad_s"]["femur"]}
        self._observation = {"t_s": self.time_s,
            "pose": {"position_mm": (np.asarray(state["pose_cm_quat"][:3]) * 10).tolist(), "heading_rad": state["heading_rad"]},
            "antenna_odor": self.field.sample(np.asarray(state["antenna_positions_mm"]) * .001, self.time_s).tolist(),
            "taste_food": any(food.values()), "taste_water": any(water.values()),
            "food_contact_by_leg": food, "water_contact_by_leg": water,
            "physiology": self.physiology.snapshot(), "motor": {"mode": self._mode, "drive": self._drive.tolist()},
            "light_intensity": self._stimuli["light"],
            "proprioception": {"speed_mm_s": speed, "yaw_rate_rad_s": state["angular_velocity_world_rad_s"][2],
                "tarsus_height_mm": [v[2] for v in state["claw_positions_mm"]],
                "ground_force_by_leg": state["ground_force_g_mm_s2"], "joint_angles_rad": angles,
                "joint_velocities_rad_s": velocities, "body_angular_velocity_rad_s": state["body_angular_velocity_rad_s"],
                "leg_order": list(LEGS), "tarsus_height_site": "source claw site; differs from NMF tarsus5 origin"},
            "wind": {"enabled": False, "reason": "FlyBody anatomical head-frame basis not yet verified; odor advection remains enabled"},
            "vision": {"enabled": False, "sample_t_s": None, "shape": None, "mean_by_eye": None},
            "grooming": {"enabled": False, "state": "disabled", "requested": False, "actual_active": False,
                         "armed": False, "source_time_s": None, "completed_count": 0, "cancelled_count": 0}}

    def observe(self):
        if self._observation is None or not self._state["finite"]:
            raise RuntimeError("No finite FlyBody observation; inspect diagnostics")
        return copy.deepcopy(self._observation)

    def diagnostics(self):
        """Cached native state for evaluators only; never feed this to brain."""
        return copy.deepcopy(self._state)

    def advance(self, duration_s, drive_left=1., drive_right=1., behavior="walk"):
        if not math.isfinite(duration_s) or duration_s < 0:
            raise ValueError("Duration must be finite and nonnegative")
        ticks = round(duration_s / self.control_timestep_s)
        if not math.isclose(duration_s, ticks * self.control_timestep_s, abs_tol=1e-12):
            raise ValueError("FlyBody duration must contain complete2ms policy ticks")
        if self.config.horizon_s is not None and self.time_s + duration_s > self.config.horizon_s + 1e-10:
            raise RuntimeError("Bounded FlyBody horizon is2s; reset explicitly, no automatic recentering")
        drive, speed, yaw = map_drive(drive_left, drive_right, behavior)
        for _ in range(ticks):
            self._mode = behavior if self.physiology.alive else "rest"
            self._drive = drive.copy() if self._mode == "walk" else np.zeros(2)
            reply = self._rpc("advance", speed_mm_s=speed, yaw_rad_s=yaw, behavior=self._mode)
            self._accept_state(reply["state"])
        return self.observe()

    def set_stimulus(self, name, value):
        if name not in ("odor", "light") or not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError("Stimulus must be odor/light with finite gain in[0,10]")
        if name == "light":
            self._rpc("light", value=float(value))
        self._stimuli[name] = float(value)
        self._cache_observation()

    def snapshot(self):
        state = self._state
        physics = {key: state[key] for key in ("native_time_s", "tick", "finite", "warnings", "up_z", "source_terminated", "contact_count")}
        physics.update(nq=self._metadata["nq"], nv=self._metadata["nv"], nu=self._metadata["nu"],
            timestep_s=self.timestep, control_timestep_s=self.control_timestep_s,
            max_abs_qacc=max(abs(v) for v in state["qacc"] if v is not None),
            initialization_settling_s=0., horizon_s=self.config.horizon_s, last_error=self._last_error)
        return {"observation": self.observe(), "config": asdict(self.config), "seed": self.seed,
            "illumination": self._illumination_snapshot(),
            "wind_reference": None, "resources": {"food": asdict(self.food), "water": asdict(self.water)},
            "resource_balance": self.physiology.balance_residuals(self.food, self.water),
            "stimuli": self._stimuli.copy(), "physics": physics,
            "backend": {"name": "flybody", **self._metadata, "profile": PROFILE, "intended_sex": "male",
                "worker_log": str(self.log_path), "finite_horizon": self.config.horizon_s is not None,
                "controller": "Frozen pretrained mean policy; native neutral-zero position hold with adhesion1",
                "command_map": "speed=20*clip((L+R)/2,0,1); yaw=2*clip((R-L)/1.2,-1,1)",
                "physiology_sampling_s": .002, "force_units": "g mm/s^2 (native dyne multiplied by10)"},
            "capabilities": {"walk": True, "engineering_stance": True, "abstract_feeding": True,
                "odor": True, "tarsal_taste": True, "club_proprioception": True,
                "grooming": False, "compound_vision": False, "head_frame_wind": False,
                "world_illumination": False, "persistent_reference": self.config.reference_mode == "rolling"},
            "field": {"puffs": len(self.field.births), "retired_arbitrary_mass": self.field.retired_mass}}

    def _illumination_snapshot(self):
        original = self._metadata["original_lighting"]
        gain = self._stimuli["light"]
        return {"mode": "source_native_flybody", "relative_gain": gain, "nlight": original["nlight"],
            **{name: (np.asarray(original[name]) * gain).tolist() for name in
               ("light_diffuse", "light_ambient", "light_specular")},
            "headlight": {name: (np.asarray(value) * gain).tolist() for name, value in original["headlight"].items()}}

    def reset(self, seed=None):
        self.seed = self.seed if seed is None else int(seed)
        reply = self._rpc("reset", seed=self.seed)
        self._state = None
        self._drive = np.zeros(2)
        self._mode = "rest"
        self._last_error = None
        self._initialize_host()
        self._accept_state(reply["state"])
        return self.observe()

    def vision_readouts(self):
        return None

    def render(self, camera="follow"):
        if camera not in ("follow", "overview", "side"):
            raise ValueError("Camera must be follow, overview or side")
        return self._rpc("render", camera=camera)["rgb"]

    def close(self):
        if self._closed:
            return
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._rpc("close")
                    self._proc.wait(timeout=3)
            except (OSError, RuntimeError, TimeoutError, subprocess.TimeoutExpired):
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=3)
            for stream in (self._proc.stdin, self._proc.stdout):
                if stream:
                    stream.close()
        self._closed = True
        if getattr(self, "_log", None) is not None:
            self._log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
