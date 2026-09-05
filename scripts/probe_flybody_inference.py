"""Isolated CPU inference and short original-FlyBody walking compatibility probe.

Run with tmp/flybody-env/bin/python, not the project's main virtual environment.
Weights/graphs are never edited. The only deserialization shim registers the
same TFP Independent class under its archived fully-qualified TypeSpec name.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_sources(repo):
    manifest = json.loads(Path("validation/flybody-source-manifest.json").read_text())
    for item in manifest["files"]:
        if digest(repo / item["path"]) != item["sha256"]:
            raise ValueError(f"Upstream source/asset differs: {item['path']}")
    acquired = json.loads(Path("validation/flybody-walking-acquisition.json").read_text())
    for item in acquired["members"]:
        if digest(item["local_path"]) != item["sha256"]:
            raise ValueError(f"Policy file differs: {item['local_path']}")
    return {"source_manifest_sha256": digest("validation/flybody-source-manifest.json"),
        "policy_receipt_sha256": digest("validation/flybody-walking-acquisition.json"),
        "source_commit": manifest["source_commit"]}


def numpy_mean(observations, variables, epsilon):
    """Exact deterministic mean architecture from this pinned graph, in NumPy.

    The archived variables retain creation/object order. Do not identify head
    variables by their duplicate display names. All intermediates stay float32.
    """
    import numpy as np
    arrays = [np.asarray(observations[k], np.float32) for k in sorted(observations)]
    x = np.concatenate([a.reshape(a.shape[0], -1) for a in arrays], axis=-1)
    x = x @ variables[1] + variables[0]
    mean = np.mean(x, axis=-1, keepdims=True)
    variance = np.mean(np.square(x - mean), axis=-1, keepdims=True)
    inverse = (np.float32(1) / np.sqrt(variance + epsilon)) * variables[3]
    x = np.tanh(x * inverse + (variables[2] - mean * inverse))
    for index in (4, 6, 8):
        x = x @ variables[index + 1] + variables[index]
        negative = x < 0
        x[negative] = np.expm1(x[negative])
    return x @ variables[11] + variables[10]


def run(repo, output_dir):
    import numpy as np
    import tensorflow as tf
    import tensorflow_probability as tfp
    import mujoco
    tf.config.set_visible_devices([], "GPU")
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    report = {"schema_version": 1, "scope": "inference compatibility and 0.5 s physical smoke",
        "plan_sha256": digest("validation/flybody-inference-plan.json"),
        "script_sha256": digest(__file__), **verify_sources(repo),
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
        "runtime_versions": {name: importlib.metadata.version(name) for name in
            ["tensorflow", "tensorflow-probability", "dm-control", "mujoco", "numpy", "h5py"]},
        "visible_gpu_devices": [str(device) for device in tf.config.get_visible_devices("GPU")],
        "default_runtime_modified": False, "original_tensorflow_2_8_numerical_parity": "not tested"}
    sys.path.insert(0, str(repo.resolve()))
    from flybody.fly_envs import walk_imitation
    from flybody.tasks.synthetic_trajectories import constant_speed_trajectory

    # This public TFP API restores the original name/serialization of the same
    # distribution class. It does not alter any saved function, tensor or weight.
    tfp.experimental.auto_composite_tensor(tfp.distributions.Independent)
    _ = tfp.distributions.Normal
    report["compatibility_shim"] = {
        "api": "tfp.experimental.auto_composite_tensor(tfp.distributions.Independent)",
        "reason": "TFP 0.23 default registry lacks original fully-qualified Independent_ACTTypeSpec",
        "saved_files_modified": False}
    started = time.perf_counter()
    policy = tf.saved_model.load("data/raw/flybody/walking")
    report["load_wall_s"] = time.perf_counter() - started
    graph_audit = json.loads(Path("validation/flybody-policy-audit.json").read_text())["graph"]
    variable_specs = graph_audit["variables"]
    weights = []
    for variable, expected in zip(policy._variables, variable_specs, strict=True):
        assert variable.name == expected["name"] + ":0"
        assert list(variable.shape) == expected["shape"] and variable.dtype == tf.float32
        weights.append(variable.numpy())
    concrete = policy.__call__.concrete_functions[0]
    definition = concrete.graph.as_graph_def()
    graph_nodes = list(definition.node) + [node for function in definition.library.function for node in function.node_def]
    epsilon_nodes = [node for node in graph_nodes if node.name.endswith("layer_norm/batchnorm/add/y")]
    if len(epsilon_nodes) != 1:
        raise ValueError("Could not uniquely resolve LayerNorm epsilon from actual graph")
    epsilon = tf.make_ndarray(epsilon_nodes[0].attr["value"].tensor).astype(np.float32)
    report["actual_graph_layer_norm_epsilon"] = float(epsilon)
    expected_inputs = next(iter(graph_audit["functions"].values()))["input"][0][0]

    started = time.perf_counter()
    env = walk_imitation(random_state=np.random.RandomState(11))
    reference_qpos, reference_qvel = constant_speed_trajectory(330, speed=2, yaw_speed=0)
    env.task._traj_generator.set_next_trajectory(reference_qpos, reference_qvel)
    timestep = env.reset()
    report["environment_build_wall_s"] = time.perf_counter() - started
    spec = env.action_spec()
    report["action_spec"] = {"names": spec.name.split(), "minimum": spec.minimum.tolist(),
                              "maximum": spec.maximum.tolist(), "shape": list(spec.shape)}
    report["observation_spec"] = {name: {"shape": list(value.shape), "native_dtype": str(value.dtype),
        "policy_dtype": "float32"} for name, value in timestep.observation.items()}
    assert set(timestep.observation) == set(expected_inputs)
    assert sum(np.asarray(v).size for v in timestep.observation.values()) == 741
    assert spec.shape == (59,)
    for name, value in timestep.observation.items():
        assert list(value.shape) == expected_inputs[name]["shape"][1:]
    report["compiled_physics"] = {"nq": env.physics.model.nq, "nv": env.physics.model.nv,
        "nu": env.physics.model.nu, "physics_dt_s": env.physics.timestep(),
        "control_dt_s": env.control_timestep(), "gravity_cm_s2": env.physics.model.opt.gravity.tolist()}
    assert env.physics.timestep() == 0.0002 and env.control_timestep() == 0.002

    def batch(observation):
        return {name: tf.convert_to_tensor(np.asarray(value, np.float32)[None])
                for name, value in observation.items()}

    initial_input = batch(timestep.observation)
    warm = policy(initial_input)
    initial_mean = warm.mean().numpy()
    initial_std = warm.stddev().numpy()
    repeated = np.stack([policy(initial_input).mean().numpy() for _ in range(10)])
    deterministic_error = float(np.max(np.abs(repeated - initial_mean)))
    assert deterministic_error == 0 and np.isfinite(initial_mean).all()
    assert np.isfinite(initial_std).all() and (initial_std > 0).all()
    report["deterministic_same_observation_max_abs_difference"] = deterministic_error
    report["initial_mean"] = initial_mean[0].tolist()
    report["initial_std"] = initial_std[0].tolist()

    minimum, maximum = spec.minimum.astype(np.float32), spec.maximum.astype(np.float32)
    floor_names = [geom.full_identifier for geom in env.task._arena.ground_geoms]
    floor_ids = {env.physics.model.name2id(name, "geom") for name in floor_names}
    observations = {name: [] for name in expected_inputs}
    poses, upright, canonical, ground_counts, qpos_trace = [], [], [], [], []
    policy_s = physics_s = 0.
    initial_position, _ = env.task.walker.get_pose(env.physics)
    initial_position = initial_position.copy()
    started = time.perf_counter()
    for index in range(250):
        for name, value in timestep.observation.items():
            observations[name].append(np.asarray(value, np.float32).copy())
        before_policy = time.perf_counter()
        distribution = policy(batch(timestep.observation))
        action = distribution.mean().numpy()[0]
        policy_s += time.perf_counter() - before_policy
        if not np.isfinite(action).all():
            raise ValueError("Nonfinite policy action")
        native_action = minimum + np.float32(0.5) * (np.clip(action, -1, 1) + 1) * (maximum - minimum)
        before_physics = time.perf_counter()
        timestep = env.step(native_action)
        physics_s += time.perf_counter() - before_physics
        if not np.isfinite(env.physics.data.qpos).all() or not np.isfinite(env.physics.data.qvel).all():
            raise ValueError("Nonfinite body state")
        if timestep.last():
            raise ValueError(f"Unexpected early task termination at step {index + 1}")
        position, quaternion = env.task.walker.get_pose(env.physics)
        poses.append(np.r_[position, quaternion])
        upright.append(env.physics.bind(env.task.walker.root_body).xmat.reshape(3, 3)[2, 2])
        canonical.append(action.copy())
        ground_counts.append(sum(int(contact.geom1 in floor_ids or contact.geom2 in floor_ids)
                                 for contact in env.physics.data.contact))
        qpos_trace.append(env.physics.data.qpos.copy())
    total_s = time.perf_counter() - started
    poses, canonical = np.asarray(poses), np.asarray(canonical)
    warnings = [int(warning.number) for warning in env.physics.data.warning]
    observed_batch = {name: np.stack(values) for name, values in observations.items()}
    # Independent vectorized NumPy arithmetic, with the original graph run in TF
    # on the identical batch as reference. A batch-kernel roundoff comparison is
    # separately reported against the per-step TF actions used for physics.
    mean_numpy = numpy_mean(observed_batch, weights, epsilon)
    mean_tf = policy({name: tf.convert_to_tensor(value) for name, value in observed_batch.items()}).mean().numpy()
    mean_error = float(np.max(np.abs(mean_numpy - mean_tf)))
    report["mean_path_parity"] = {"samples": 250, "absolute_tolerance": 1e-5,
        "max_abs_numpy_vs_tf_batch": mean_error,
        "rms_numpy_vs_tf_batch": float(np.sqrt(np.mean(np.square(mean_numpy - mean_tf)))),
        "max_abs_tf_batch_vs_per_step": float(np.max(np.abs(mean_tf - canonical))),
        "passed": mean_error <= 1e-5,
        "scope": "actual checkpoint NumPy mean path vs original SavedModel graph under TF2.15.1, not TF2.8 reference"}
    positions = np.vstack([initial_position, poses[:, :3]])
    speed_mm_s = np.linalg.norm(np.diff(positions[:, :2], axis=0), axis=1) / 0.002 * 10
    w, x, y, z = poses[:, 3:].T
    headings = np.unwrap(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
    report["rollout"] = {"simulated_s": 0.5, "wall_s": total_s, "policy_wall_s": policy_s,
        "environment_step_wall_s": physics_s, "real_time_factor": 0.5 / total_s,
        "displacement_mm": ((poses[-1, :3] - initial_position) * 10).tolist(),
        "mean_planar_speed_mm_s": float(np.mean(speed_mm_s)),
        "median_planar_speed_mm_s": float(np.median(speed_mm_s)),
        "min_height_mm": float(np.min(poses[:, 2]) * 10),
        "min_upright_z": float(np.min(upright)),
        "net_heading_change_deg": float(np.rad2deg(headings[-1] - headings[0])),
        "ground_contact_count_min": int(min(ground_counts)),
        "ground_contact_count_max": int(max(ground_counts)),
        "fraction_steps_with_ground_contact": float(np.mean(np.asarray(ground_counts) > 0)),
        "canonical_action_clipped_fraction": float(np.mean(np.abs(canonical) > 1)),
        "canonical_action_max_abs": float(np.max(np.abs(canonical))),
        "mujoco_warning_counts": warnings, "finite": True,
        "biological_benchmark_pass": None}
    output_dir.mkdir(parents=True, exist_ok=True)
    trace = output_dir / "trace.npz"
    np.savez_compressed(trace, pose=poses, qpos=np.asarray(qpos_trace), canonical_action=canonical,
        upright_z=np.asarray(upright), ground_contact_count=np.asarray(ground_counts),
        **{key.replace("/", "_"): value for key, value in observed_batch.items()})
    report["trace"] = {"path": str(trace), "bytes": trace.stat().st_size, "sha256": digest(trace)}
    report["passed"] = bool(mean_error <= 1e-5 and not any(warnings))
    if not report["passed"]:
        report["failure"] = "Predeclared NumPy parity or MuJoCo warning criterion failed; preserve result"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/tmp/fruit-fly-research-flybody"))
    parser.add_argument("--output", type=Path, default=Path("validation/flybody-inference-probe.json"))
    parser.add_argument("--run-dir", type=Path, default=Path("runs/flybody-inference-probe"))
    args = parser.parse_args()
    try:
        report = run(args.repo, args.run_dir)
    except Exception as error:
        report = {"passed": False, "error_type": type(error).__name__, "error": str(error),
                  "traceback": traceback.format_exc(), "script_sha256": digest(__file__)}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ["passed", "error_type", "error", "mean_path_parity", "rollout"]
                      if key in report}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
