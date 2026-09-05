"""Private Python 3.10 owner of the frozen FlyBody physics and SavedModel.

Run only via FlyBodyRuntime. Stdout is a length-framed JSON/binary protocol;
library output goes to stderr. This module never imports FlyGym or host biology.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = 1
LEGS = ("LF", "LM", "LH", "RF", "RM", "RH")
LEG_SOURCE = dict(zip(LEGS, ("T1_left", "T2_left", "T3_left", "T1_right", "T2_right", "T3_right")))
PHYSICS_DT = .0002
CONTROL_DT = .002
MAX_TICKS = 1000
MANIFEST_SHA = "5e5d4a41322e85feea28537c6a9389f9aec29ea0f6a2c007741ceaf2342122f2"
RECEIPT_SHA = "b67e939aec74a566eb95bf036ae711dc38b0a1530a86387230c946cdc7a8e5a7"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_assets(source):
    result = {}
    for name, expected in (("flybody-source-manifest.json", MANIFEST_SHA),
                           ("flybody-walking-acquisition.json", RECEIPT_SHA)):
        path = ROOT / "validation" / name
        if digest(path) != expected:
            raise ValueError("Changed pinned receipt: " + name)
        result[name] = json.loads(path.read_text())
    manifest = result["flybody-source-manifest.json"]
    for item in manifest["files"]:
        if digest(source / item["path"]) != item["sha256"]:
            raise ValueError("Changed upstream source/asset: " + item["path"])
    for item in result["flybody-walking-acquisition.json"]["members"]:
        if digest(ROOT / item["local_path"]) != item["sha256"]:
            raise ValueError("Changed walking policy: " + item["local_path"])
    return {"source_commit": manifest["source_commit"], "source_manifest_sha256": MANIFEST_SHA,
            "policy_receipt_sha256": RECEIPT_SHA, "worker_sha256": digest(__file__),
            "code_license": "Apache-2.0", "policy_collection_license": "GPL-3.0-or-later"}


class Worker:
    def __init__(self, config, seed):
        global np, mujoco
        source = Path(config["source_path"]).resolve()
        self.provenance = verify_assets(source)
        expected_versions = {"tensorflow": "2.15.1", "tensorflow-probability": "0.23.0",
            "dm-control": "1.0.27", "mujoco": "3.2.7", "numpy": "1.26.4"}
        versions = {name: importlib.metadata.version(name) for name in expected_versions}
        if versions != expected_versions or sys.version_info[:2] != (3, 10):
            raise ValueError("Untested FlyBody inference environment: " + str(versions))
        sys.path.insert(0, str(source))
        import numpy as np
        import mujoco
        import tensorflow as tf
        import tensorflow_probability as tfp
        tf.config.set_visible_devices([], "GPU")
        tf.config.threading.set_intra_op_parallelism_threads(1)
        tf.config.threading.set_inter_op_parallelism_threads(1)
        tfp.experimental.auto_composite_tensor(tfp.distributions.Independent)
        _ = tfp.distributions.Normal
        self.tf = tf
        self.policy = tf.saved_model.load(str(ROOT / "data/raw/flybody/walking"))
        self.provenance["versions"] = versions
        self.provenance["python"] = sys.version
        self.config = config
        self.reference_mode = config.get("reference_mode", "bounded")
        if self.reference_mode not in ("bounded", "rolling"):
            raise ValueError("Unknown FlyBody reference mode")
        if self.reference_mode == "rolling" and "horizon_s" not in config:
            raise ValueError("Rolling worker requires an explicit null horizon")
        expected_horizon = 2. if self.reference_mode == "bounded" else None
        if config.get("horizon_s", expected_horizon) != expected_horizon:
            raise ValueError("Reference mode and trial horizon disagree")
        if self.reference_mode == "rolling":
            self.provenance["rolling_task_sha256"] = digest(ROOT / "fruitfly/flybody_persistent_task.py")
        self.env = None
        self.camera = None
        self.state = None
        self.reset(seed)

    def reset(self, seed):
        if self.reference_mode == "rolling":
            # The worker is launched by file path, so make its package root
            # explicit without importing the primary environment's body stack.
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from fruitfly.flybody_persistent_task import rolling_walk_imitation as walk_imitation
        else:
            from flybody.fly_envs import walk_imitation
        from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
        self.close()
        self.env = walk_imitation(random_state=np.random.RandomState(int(seed)))
        # Sites are strictly visual: no bodies, inertia, collision geoms or
        # actuators are added. Preserve all native physics IDs and dynamics.
        arena = self.env.task._arena.mjcf_model
        getattr(arena.visual, "global").offwidth = self.config["width"]
        getattr(arena.visual, "global").offheight = self.config["height"]
        for kind, color in (("food", (.95, .65, .15, .5)), ("water", (.15, .55, .95, .5))):
            xy = np.asarray(self.config[kind + "_position_mm"]) / 10
            arena.worldbody.add("site", name="resource_" + kind, type="cylinder",
                pos=(*xy, .0001), size=(self.config[kind + "_radius_mm"] / 10, .0001),
                rgba=color, group=0)
        qref, vref = constant_speed_trajectory(1100, speed=2.)
        self.env.task._traj_generator.set_next_trajectory(qref, vref)
        self.step_result = self.env.reset()
        self.m, self.d = self.env.physics.model, self.env.physics.data
        if self.env.physics.timestep() != PHYSICS_DT or self.env.control_timestep() != CONTROL_DT:
            raise ValueError("Source clock changed")
        spec = self.env.action_spec()
        self.names = spec.name.split()
        self.lo, self.hi = spec.minimum.astype(np.float32), spec.maximum.astype(np.float32)
        self.aids = np.asarray([self.m.name2id("walker/" + n, "actuator") for n in self.names])
        audit = json.loads((ROOT / "validation/flybody-stance-actuator-audit.json").read_text())
        if len(self.names) != 59:
            raise ValueError("Unexpected source action count")
        for i, row in enumerate(audit["rows"]):
            if self.names[i] != row["name"] or int(self.aids[i]) != row["compiled_actuator_id"]:
                raise ValueError("Native action ordering changed")
            np.testing.assert_array_equal(self.m.actuator_gainprm[self.aids[i], :3], row["gain"])
            np.testing.assert_array_equal(self.m.actuator_biasprm[self.aids[i], :3], row["bias"])
        self.floors = {self.m.name2id(g.full_identifier, "geom") for g in self.env.task._arena.ground_geoms}
        self.geom_leg, self.tarsal_geoms = {}, set()
        for i in range(self.m.ngeom):
            name = self.m.id2name(i, "geom") or ""
            if not name.startswith("walker/"):
                continue
            for leg, suffix in LEG_SOURCE.items():
                if suffix in name:
                    self.geom_leg[i] = leg
                    # Source names put segment number between T1 and left, so
                    # also resolve through the geometry's actual parent body.
        for i in range(self.m.ngeom):
            name = self.m.id2name(i, "geom") or ""
            body = self.m.id2name(int(self.m.geom_bodyid[i]), "body") or ""
            if not name.startswith("walker/"):
                continue
            for leg, suffix in LEG_SOURCE.items():
                segment, side = suffix.split("_")
                if segment + "_" in body and body.endswith("_" + side):
                    self.geom_leg[i] = leg
                    if "tarsus_" in body or "claw_" in body:
                        self.tarsal_geoms.add(i)
        self.antenna_ids = [self.m.name2id("walker/antenna_" + side, "body") for side in ("left", "right")]
        self.root_id = self.m.name2id(self.env.task.walker.root_body.full_identifier, "body")
        self.claws = [self.env.task.walker.mjcf_model.find("site", "claw_" + LEG_SOURCE[leg]) for leg in LEGS]
        if min(self.antenna_ids + [self.root_id]) < 0 or any(site is None for site in self.claws) or not self.tarsal_geoms:
            raise ValueError("Missing native sensory geometry")
        self.qids, self.vids = {}, {}
        for name in ("coxa", "femur", "tibia"):
            ids = [self.m.name2id("walker/" + name + "_" + LEG_SOURCE[leg], "joint") for leg in LEGS]
            if min(ids) < 0:
                raise ValueError("Missing proprioceptive joints")
            self.qids[name] = self.m.jnt_qposadr[ids]
            self.vids[name] = self.m.jnt_dofadr[ids]
        self.diffuse = self.m.light_diffuse.copy()
        self.ambient = self.m.light_ambient.copy()
        self.specular = self.m.light_specular.copy()
        self.headlight = {name: getattr(self.m.vis.headlight, name).copy() for name in ("diffuse", "ambient", "specular")}
        self.tick = 0
        self.failed = False
        self.target = qref[0].copy()
        self.native = self.d.ctrl[self.aids].copy()
        self.canonical = self._policy(self.step_result.observation)
        self.command = {"speed_mm_s": 0., "yaw_rad_s": 0., "policy_enabled": False, "behavior": "rest"}
        self.state = self.collect()
        return self.state

    def _policy(self, observation):
        values = {key: np.asarray(value, np.float32) for key, value in observation.items()}
        actor = np.concatenate([value.ravel() for value in values.values()]).astype('<f4', copy=False)
        self.actor_input_sha256 = hashlib.sha256(actor.tobytes()).hexdigest()
        self.actor_observation_shapes = {key: list(value.shape) for key, value in values.items()}
        batch = {key: self.tf.convert_to_tensor(value[None]) for key, value in values.items()}
        action = self.policy(batch).mean().numpy()[0]
        if action.shape != (59,) or not np.isfinite(action).all():
            raise RuntimeError("Invalid original policy action")
        return action

    def advance(self, speed_mm_s, yaw_rad_s, behavior):
        if self.failed:
            raise RuntimeError("Source task failed; reset explicitly before advancing")
        if self.reference_mode == "bounded" and self.tick >= MAX_TICKS:
            raise RuntimeError("Bounded FlyBody horizon reached (2 s)")
        if behavior not in ("walk", "rest", "feed"):
            raise ValueError("FlyBody supports only walk, rest and abstract feed")
        if not math.isfinite(speed_mm_s) or not 0 <= speed_mm_s <= 20 or not math.isfinite(yaw_rad_s) or abs(yaw_rad_s) > 2:
            raise ValueError("Invalid bounded motor command")
        on = behavior == "walk"
        if not on:
            speed_mm_s = yaw_rad_s = 0.
        self.command = {"speed_mm_s": speed_mm_s, "yaw_rad_s": yaw_rad_s, "policy_enabled": on, "behavior": behavior}
        from flybody.tasks.synthetic_trajectories import constant_speed_trajectory
        heading = 2 * np.arctan2(self.target[6], self.target[3])
        reference_frames = 66 if self.reference_mode == "rolling" else 65
        preview, pvel = constant_speed_trajectory(reference_frames, speed=speed_mm_s / 10,
            yaw_speed=yaw_rad_s, init_pos=self.target[:3], init_heading=heading)
        # Source helper returns yaw per step; reference qvel is rad/s. This
        # correction is already frozen in the independent motor comparison.
        pvel[:, 3:] = [0, 0, yaw_rad_s]
        if self.reference_mode == "rolling":
            self.env.task.install_preview(preview, pvel, self.tick)
        else:
            self.env.task._ref_qpos[self.tick:self.tick + 65] = preview
            self.env.task._ref_qvel[self.tick:self.tick + 65] = pvel
        observation = dict(self.step_result.observation)
        for key in ("walker/ref_displacement", "walker/ref_root_quat"):
            observation[key] = self.env.task.observables[key](self.env.physics)
        self.canonical = self._policy(observation)
        if on:
            self.native = self.lo + np.float32(.5) * (np.clip(self.canonical, -1, 1) + 1) * (self.hi - self.lo)
        else:
            self.native = np.zeros(59, np.float32)
            self.native[:6] = 1
        self.target = preview[1].copy()
        try:
            self.step_result = self.env.step(self.native.copy())
        except BaseException:
            # MuJoCo/composer can fail during a substep. Keep the true partial
            # native clock and raw state; never report the last good tick.
            self.failed = True
            self.tick = int(round(float(self.d.time) / CONTROL_DT))
            self.state = self.collect()
            raise
        self.tick += 1
        self.state = self.collect()
        if not self.state["finite"] or self.state["source_terminated"]:
            self.failed = True
            raise RuntimeError("Source physical failure at tick " + str(self.tick))
        return self.state

    def collect(self):
        m, d = self.m, self.d
        # dm-control finishes mj_step1; force-stage data in d precedes its
        # current contacts. A detached forward refresh cannot change policy.
        diagnostic = copy.copy(d.ptr)
        mujoco.mj_forward(m.ptr, diagnostic)
        contacts, support = [], np.zeros(6)
        ground = np.zeros((6, 3))
        force = np.zeros(6)
        for index, c in enumerate(diagnostic.contact):
            if c.geom1 in self.floors:
                gid, sign = int(c.geom2), 1.
            elif c.geom2 in self.floors:
                gid, sign = int(c.geom1), -1.
            else:
                continue
            leg = self.geom_leg.get(gid)
            if leg is None:
                continue
            mujoco.mj_contactForce(m.ptr, diagnostic, index, force)
            vector = sign * (force[:3] @ c.frame.reshape(3, 3))
            li = LEGS.index(leg)
            ground[li] += vector
            support[li] += abs(vector[2])
            contacts.append({"leg": leg, "geom": m.id2name(gid, "geom"),
                "dist_cm": float(c.dist), "position_mm": (c.pos * 10).tolist(),
                "force_world_dyne": vector.tolist(), "is_tarsal": gid in self.tarsal_geoms,
                "active": bool(c.efc_address >= 0 and c.dist <= 0)})
        position, quaternion = self.env.task.walker.get_pose(self.env.physics)
        rotation = d.xmat[self.root_id].reshape(3, 3)
        spatial = np.empty(6)
        mujoco.mj_objectVelocity(m.ptr, d.ptr, mujoco.mjtObj.mjOBJ_BODY, self.root_id, spatial, 0)
        state = {"native_time_s": float(d.time), "tick": self.tick,
            "actor_input_sha256": self.actor_input_sha256,
            "reference_qpos_shape": list(self.env.task._ref_qpos.shape),
            "reference_qvel_shape": list(self.env.task._ref_qvel.shape),
            "source_control_tick": self.env.task._step_counter,
            "reference_buffer_origin": getattr(self.env.task, "_rolling_origin", None),
            "qpos": d.qpos.tolist(), "qvel": d.qvel.tolist(), "qacc": d.qacc.tolist(),
            "act": d.act.tolist(), "ctrl": d.ctrl.tolist(), "warnings": [int(w.number) for w in d.warning],
            "native_action": self.native.tolist(), "canonical_action": self.canonical.tolist(),
            "actuator_ids": self.aids.tolist(), "action_names": self.names,
            "actuator_length": d.actuator_length[self.aids].tolist(),
            "actuator_activation": d.act[m.actuator_actadr[self.aids]].tolist(),
            "actuator_force_preceding_stage": d.actuator_force[self.aids].tolist(),
            "pose_cm_quat": np.r_[position, quaternion].tolist(), "up_z": float(rotation[2, 2]),
            "heading_rad": float(np.arctan2(rotation[1, 0], rotation[0, 0])),
            "velocity_world_mm_s": (spatial[3:] * 10).tolist(),
            "angular_velocity_world_rad_s": spatial[:3].tolist(),
            "body_angular_velocity_rad_s": (rotation.T @ spatial[:3]).tolist(),
            "support_dyne_by_leg": support.tolist(), "ground_force_g_mm_s2": (ground * 10).tolist(),
            "contacts": contacts, "antenna_positions_mm": (d.xpos[self.antenna_ids] * 10).tolist(),
            "claw_positions_mm": (self.env.physics.bind(self.claws).xpos * 10).tolist(),
            "joint_angles_rad": {key: d.qpos[ids].tolist() for key, ids in self.qids.items()},
            "joint_velocities_rad_s": {key: d.qvel[ids].tolist() for key, ids in self.vids.items()},
            "tibia_rad": d.qpos[self.qids["tibia"]].tolist(),
            "tibia_velocity_rad_s": d.qvel[self.vids["tibia"]].tolist(),
            "command": self.command.copy(), "target_pose_cm_quat": self.target.tolist(),
            "source_terminated": bool(self.step_result.last()), "contact_count": int(d.ncon)}
        state["finite"] = all(np.isfinite(a).all() for a in
            (d.qpos, d.qvel, d.qacc, d.act, d.ctrl, d.actuator_force, support, ground, spatial))
        return state

    def metadata(self):
        return {**self.provenance, "nq": self.m.nq, "nv": self.m.nv, "nu": self.m.nu,
            "physics_timestep_s": PHYSICS_DT, "control_timestep_s": CONTROL_DT,
            "horizon_s": 2. if self.reference_mode == "bounded" else None,
            "reference_mode": self.reference_mode, "initialization_settling_s": 0.,
            "reference_frames": len(self.env.task._ref_qpos), "preview_frames": 65,
            "actor_observation_shapes": self.actor_observation_shapes,
            "gravity_cm_s2": self.m.opt.gravity.tolist(), "body_weight_dyne": float(self.env.task.walker.weight),
            "original_lighting": {"mode": "source_native_flybody", "nlight": self.m.nlight,
                "light_diffuse": self.diffuse.tolist(), "light_ambient": self.ambient.tolist(),
                "light_specular": self.specular.tolist(),
                "headlight": {key: value.tolist() for key, value in self.headlight.items()}},
            "tarsal_geoms": [self.m.id2name(i, "geom") for i in sorted(self.tarsal_geoms)],
            "antenna_bodies": [self.m.id2name(i, "body") for i in self.antenna_ids],
            "action_names": self.names, "action_minimum": self.lo.tolist(), "action_maximum": self.hi.tolist()}

    def light(self, value):
        if not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError("Invalid light gain")
        self.m.light_diffuse[:] = self.diffuse * value
        self.m.light_ambient[:] = self.ambient * value
        self.m.light_specular[:] = self.specular * value
        for key, original in self.headlight.items():
            getattr(self.m.vis.headlight, key)[:] = original * value

    def render(self, name):
        from dm_control.mujoco.engine import MovableCamera
        if name not in ("follow", "overview", "side"):
            raise ValueError("Unknown camera")
        if self.camera is None:
            self.camera = MovableCamera(self.env.physics, height=self.config["height"], width=self.config["width"])
        position = np.asarray(self.state["pose_cm_quat"][:3])
        lookat = [0., 0., 0.] if name == "overview" else position
        distance = 5. if name == "overview" else (1.1 if name == "follow" else .7)
        self.camera.set_pose(lookat=lookat, distance=distance,
            azimuth=135 if name != "side" else 90, elevation=-55 if name == "overview" else (-36 if name == "follow" else -12))
        before = {key: getattr(self.d, key).copy() for key in ("qpos", "qvel", "qacc", "act", "ctrl", "sensordata")}
        old_time = float(self.d.time)
        result = self.camera.render().copy()
        if old_time != float(self.d.time) or any(not np.array_equal(value, getattr(self.d, key)) for key, value in before.items()):
            raise RuntimeError("Rendering unexpectedly changed native physics/sensors")
        return result

    def close(self):
        if self.camera is not None:
            self.camera = None
        if self.env is not None:
            self.env.close()
            self.env.physics.free()
            self.env = None


def clean_json(value):
    """Retain a failed reply: nonfinite numbers become null with finite=false."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    return value


def main():
    for key, value in {"TF_CPP_MIN_LOG_LEVEL": "2", "CUDA_VISIBLE_DEVICES": "-1",
                       "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}.items():
        os.environ[key] = value
    protocol = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)  # Native library prints cannot corrupt the private protocol.
    inp = sys.stdin.buffer
    worker = None
    try:
        while True:
            header = inp.read(4)
            if not header:
                break
            size = struct.unpack("!I", header)[0]
            if size > 1_000_000:
                raise ValueError("Oversized worker request")
            request = json.loads(inp.read(size))
            reply = {"version": PROTOCOL_VERSION, "id": request.get("id"), "ok": True}
            image_bytes = b""
            try:
                if request.get("version") != PROTOCOL_VERSION:
                    raise ValueError("Protocol version mismatch")
                op = request["op"]
                if op == "init":
                    if worker is not None:
                        raise ValueError("Worker already initialized")
                    worker = Worker(request["config"], request["seed"])
                    reply.update(state=worker.state, metadata=worker.metadata())
                elif worker is None:
                    raise ValueError("Worker not initialized")
                elif op == "advance":
                    reply["state"] = worker.advance(request["speed_mm_s"], request["yaw_rad_s"], request["behavior"])
                elif op == "reset":
                    reply["state"] = worker.reset(request["seed"])
                elif op == "light":
                    worker.light(request["value"])
                elif op == "render":
                    rgb = worker.render(request["camera"])
                    image_bytes = rgb.tobytes()
                    reply.update(image_shape=list(rgb.shape), binary_bytes=len(image_bytes))
                elif op != "close":
                    raise ValueError("Unknown worker operation")
            except Exception as error:
                traceback.print_exc(file=sys.stderr)
                reply.update(ok=False, error=type(error).__name__ + ": " + str(error))
                if worker is not None and worker.state is not None:
                    reply["state"] = worker.state
            payload = json.dumps(clean_json(reply), separators=(",", ":"), allow_nan=False).encode()
            output = memoryview(struct.pack("!I", len(payload)) + payload + image_bytes)
            while output:
                count = protocol.write(output)
                output = output[count:]
            if request.get("op") == "close":
                break
    finally:
        if worker is not None:
            worker.close()


if __name__ == "__main__":
    main()
