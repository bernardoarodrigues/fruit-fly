#!/usr/bin/env python3
"""Independent saved-array review of the standalone rolling FlyBody task.

No simulator, learned policy, experiment/checker, or fruitfly runtime imports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def equal(left, right):
    left, right = np.asarray(left), np.asarray(right)
    assert left.shape == right.shape, (left.shape, right.shape)
    assert np.array_equal(left, right)
    return True


def rotation(quaternions):
    """World-from-body matrix for the saved unit wxyz root quaternion."""
    w, x, y, z = quaternions.T
    assert np.max(abs(np.sum(quaternions**2, axis=1)-1)) < 1e-12
    return np.array([[1-2*y*y-2*z*z, 2*x*y-2*w*z, 2*x*z+2*w*y],
                     [2*x*y+2*w*z, 1-2*x*x-2*z*z, 2*y*z-2*w*x],
                     [2*x*z-2*w*y, 2*y*z+2*w*x, 1-2*x*x-2*y*y]]).transpose(2, 0, 1)


def main():
    plan_path = "validation/flybody-persistent-plan.json"
    result_path = "validation/flybody-persistent-experiment.json"
    check_path = "validation/flybody-persistent-validation.json"
    guard_path = "validation/flybody-persistent-guard-restoration.json"
    plan, results, checked, guards = map(read, (plan_path, result_path, check_path, guard_path))
    assert results["complete"] and checked["passed"] and all(c["passed"] for c in checked["checks"])
    assert results["plan_sha256"] == checked["plan_sha256"] == sha(plan_path)
    assert checked["result_sha256"] == sha(result_path)
    assert checked["checker_sha256"] == sha("scripts/check_flybody_persistent.py")
    for path, expected in plan["files"].items():
        assert sha(path) == expected, path
    source = read("validation/flybody-source-manifest.json")
    for item in source["files"]:
        assert sha("data/raw/flybody/source/" + item["path"]) == item["sha256"]
    assert source["source_commit"] == "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
    actuator_rows = read("validation/flybody-stance-actuator-audit.json")["rows"]
    actuator_ids = [row["compiled_actuator_id"] for row in actuator_rows]
    ranges = np.asarray([row["range"] for row in actuator_rows], dtype=np.float32)
    lo, hi = ranges.T
    trials = {trial["case"]: trial for trial in results["trials"]}
    assert list(trials) == ["bounded_parity", "rolling_parity", "rolling_rest12", "rolling_switch12"]
    traces, rows = {}, []
    for case, trial in trials.items():
        assert trial["failure"] is None
        assert sha(trial["trace"]) == trial["trace_sha256"]
        data = traces[case] = np.load(ROOT / trial["trace"], allow_pickle=False)
        count = 1000 if case.endswith("parity") else 6000
        equal(data["tick"], np.arange(count+1))
        equal(data["task_counter"], data["tick"])
        clock_error = float(np.max(abs(data["native_time_s"]-np.arange(count+1)*.002)))
        assert clock_error < 1e-10
        assert trial["samples"] == count+1
        assert all(np.isfinite(data[key]).all() for key in data.files)
        assert data["finite"].all() and not data["warnings"].any() and not data["source_terminated"].any()
        equal(data["pose_cm_quat"], data["qpos"][:, :7])
        equal(data["native_action"], data["ctrl"][:, actuator_ids])
        assert data["actor"].shape == (count+1, 741) and data["actor"].dtype == np.float32
        steps = np.arange(count)
        if case == "rolling_rest12":
            on = np.zeros(count, bool)
        elif case.endswith("parity"):
            on = (steps < 300) | (steps >= 600)
        else:
            on = ((steps < 300) | ((steps >= 600) & (steps < 1500)) |
                  ((steps >= 1800) & (steps < 3000)) | ((steps >= 3300) & (steps < 4500)) |
                  (steps >= 5300))
        equal(data["command_on"][1:], on)
        off_actions = data["native_action"][1:][~on]
        equal(off_actions[:, :6], np.ones((len(off_actions), 6)))
        equal(off_actions[:, 6:], np.zeros((len(off_actions), 53)))
        actions = data["canonical_action"][1:][on].astype(np.float32)
        native_expected = lo + np.float32(.5)*(np.clip(actions, -1, 1)+1)*(hi-lo)
        equal(data["native_action"][1:][on], native_expected)
        target = data["target_pose_cm_quat"]
        equal(target[:, 3:], np.tile([1., 0., 0., 0.], (count+1, 1)))
        equal(target[:, 1:3], np.tile(target[0, 1:3], (count+1, 1)))
        expected_next = target[:-1, 0] + on*.004
        equal(target[1:, 0], expected_next)
        # Reconstruct every actual actor reference from the PREVIOUS native
        # pose and CURRENT command, independently of the cached observations.
        pose = data["pose_cm_quat"][:-1]
        preview = np.repeat(target[:-1, None, :3], 65, axis=1)
        for i in range(1, 65):
            preview[:, i, 0] = preview[:, i-1, 0]+on*.004
        expected_displacement = np.einsum("nij,njk->nik", preview-pose[:, None, :3], rotation(pose[:, 3:]))
        inverse = pose[:, 3:].copy()
        inverse[:, 1:] *= -1
        inverse /= np.sum(pose[:, 3:]**2, axis=1)[:, None]
        actor_slices, cursor = {}, 0
        for name in trial["actor_keys"]:
            shape = trial["actor_shapes"][name]
            size = int(np.prod(shape))
            actor_slices[name] = data["actor"][1:, cursor:cursor+size].reshape(count, *shape)
            cursor += size
        assert cursor == 741
        assert trial["actor_shapes"]["walker/ref_displacement"] == [65, 3]
        assert trial["actor_shapes"]["walker/ref_root_quat"] == [65, 4]
        equal(actor_slices["walker/ref_displacement"], expected_displacement.astype(np.float32))
        equal(actor_slices["walker/ref_root_quat"], np.repeat(inverse[:, None, :], 65, axis=1).astype(np.float32))
        reference_error = np.linalg.norm(target[:, :3]-data["pose_cm_quat"][:, :3], axis=1)
        error_error = float(np.max(abs(reference_error-data["reference_error_cm"])))
        assert error_error < 1e-12
        guard_values = {"linear_cm_s": float(data["source_linvel_cm_s"].max()),
                        "angular_rad_s": float(data["source_angvel_rad_s"].max()),
                        "reference_error_cm": float(reference_error.max()),
                        "qacc_norm_mixed_units": float(np.linalg.norm(data["qacc"], axis=1).max())}
        for key, value in guard_values.items():
            assert value <= plan["guards"][key]
        assert trial["guards"] == {"baseline": False, "qacc_above": True, "velocimeter_above": True,
                                   "gyro_above": True, "reference_above": True}
        if case.startswith("rolling"):
            equal(data["ref_shape"], np.tile([66, 7], (count+1, 1)))
            assert trial["task_episode_steps"] is None and trial["composer_time_limit"] == "infinite"
        if count == 6000:
            assert data["native_time_s"][-1] > 10
            assert data["tick"][5000] == 5000 and data["tick"][-1] == 6000
        rows.append({"case": case, "trace_sha256": sha(trial["trace"]), "completed_control_steps": count,
                     "clock_error_s": clock_error, "guard_maxima": guard_values,
                     "all_actual_actor_reference_rows_exact_float32": True,
                     "reference_error_reconstruction_error_cm": error_error,
                     "actual_actor_reference_rows_checked": count*65,
                     "target_final_x_cm": float(target[-1, 0]), "all_saved_array_checks_pass": True})
    a, b = traces["bounded_parity"], traces["rolling_parity"]
    parity_keys = ("actor", "canonical_action", "native_action", "qpos", "qvel", "qacc", "act", "ctrl",
                   "target_pose_cm_quat", "native_time_s", "pose_cm_quat", "velocity_world_mm_s", "angular_velocity_world_rad_s")
    for key in parity_keys:
        equal(a[key], b[key])
    assert trials["bounded_parity"]["actor_keys"] == trials["rolling_parity"]["actor_keys"]
    assert trials["bounded_parity"]["actor_shapes"] == trials["rolling_parity"]["actor_shapes"]
    assert trials["bounded_parity"]["compiled_numeric_arrays"] == trials["rolling_parity"]["compiled_numeric_arrays"]
    assert trials["bounded_parity"]["source"] == trials["rolling_parity"]["source"]
    cached = {}
    for key in ("cached_displacement", "cached_quaternion"):
        equal(a[key][:, :64], b[key][:, :64])
        cached[key] = {"final_row_different_samples": int(np.count_nonzero(np.any(a[key][:, -1] != b[key][:, -1], axis=1))),
                       "final_row_max_difference": float(np.max(abs(a[key][:, -1]-b[key][:, -1])))}
    windows = []
    for case, producer_windows in checked["windows"].items():
        data = traces[case]
        positions = data["pose_cm_quat"][:, :2]*10
        chord_speed = np.linalg.norm(np.diff(positions, axis=0), axis=1)/.002
        for w in producer_windows:
            lo_tick, hi_tick = [round(t/.002) for t in w["window_s"]]
            # Checker selects speed by completed interval END time, including
            # the interval that starts one tick before the lower endpoint.
            selected = chord_speed[lo_tick-1:hi_tick]
            median = float(np.median(selected))
            displacement = float(np.linalg.norm(positions[hi_tick]-positions[lo_tick]))
            assert median == w["median_raw_chord_speed_mm_s"] and displacement == w["net_displacement_mm"]
            passed = (median <= 1 and displacement <= .5) if w["kind"] == "stop" else 16 <= median <= 24
            assert passed and w["passed"]
            windows.append({"case": case, "kind": w["kind"], "window_s": w["window_s"],
                "speed_array_slice": [lo_tick-1, hi_tick], "speed_sample_count": len(selected),
                "median_chord_speed_mm_s": median, "net_displacement_mm": displacement,
                "diagnostic_only": w["diagnostic_only"]})
    guard_files = {"script_sha256": "scripts/audit_flybody_persistent_guard_restoration.py",
                   "experiment_sha256": "scripts/experiment_flybody_persistent.py",
                   "worker_sha256": "fruitfly/flybody_worker.py", "task_sha256": "scripts/flybody_persistent_task.py"}
    for key, path in guard_files.items():
        assert guards[key] == sha(path)
    for row in guards["rows"]:
        assert row["physics_steps"] == 0
        assert all(row[key] for key in ("data_arrays_identical", "model_arrays_identical", "reference_arrays_identical", "cached_observations_identical", "full_worker_state_identical"))
        assert row["task_scalar_differences"] == ({} if row["rolling"] else
            {"reached_traj_end_present": [False, True], "reached_traj_end": [None, False]})
    old_result_path = plan["amendment"]["prior_results"]
    old_plan_path = plan["amendment"]["prior_plan"]
    old_results = read(old_result_path)
    assert old_results["plan_sha256"] == sha(old_plan_path)
    assert old_results["complete"] and old_results["trials"][0]["failure"] is None
    initialization_failures = []
    for row in old_results["trials"][1:]:
        assert row["failure"] == "Trial process exit 1"
        log = (ROOT/row["log"]).read_text()
        assert "AttributeError" in log and "_rolling_origin" in log
        initialization_failures.append({"case": row["case"], "log_sha256": sha(row["log"]), "failure": row["failure"]})
    paths = [plan_path, result_path, check_path, guard_path, old_plan_path, old_result_path,
             "scripts/review_flybody_persistent.py", "scripts/flybody_persistent_task.py",
             "scripts/experiment_flybody_persistent.py", "scripts/check_flybody_persistent.py",
             "scripts/audit_flybody_persistent_guard_restoration.py"]
    receipt = {"scope": "Independent source inspection and saved-array calculations only; no physics, policy, or neural reruns",
        "passed_saved_array_checks": True, "artifact_hashes": {p: sha(p) for p in paths}, "trials": rows,
        "frozen_source_files_verified": len(source["files"]), "source_commit": source["source_commit"],
        "two_second_bitwise_parity_keys": list(parity_keys), "parity_actual_actor_shape": [1000, 741],
        "initial_unused_policy_evaluation_also_matches": True,
        "compiled_model_arrays_match": len(trials["bounded_parity"]["compiled_numeric_arrays"]),
        "cached_final_row_differences": cached, "windows": windows,
        "guard_restoration_producer_receipt_reviewed": guards,
        "initialization_failures_retained": initialization_failures,
        "source_review": {"physical_guards": "Source and rolling task use strict > for velocimeter norm50cm/s, gyro norm200rad/s, root reference error.3cm, and base qacc Euclidean norm1e14 mixed units. Only finite trajectory/time termination is removed.",
            "causality": "Every step installs66 current-command poses/velocities at the absolute counter; actor gets first65 rows at offset0. After native before_step increments the counter, post-step observables get rows1..65. Next actor explicitly refreshes both reference observables; unused cached row64 never becomes a future-command leak.",
            "target": "Target starts at the source initial reference and advances preview[1] from previous target each tick. It is never assigned actual fly pose during advance, so error can accumulate and physical guard remains meaningful.",
            "storage": "Recorded qpos reference shape is66x7 throughout. qvel is allocated66x6 and assigned in place by source, but its per-tick shape/values are not saved. Static500 trajectory visualization sites remain from initialization.",
            "guard_probe_side_effect": "Probe restores qacc, sensordata, reference qpos and any existing reached flag. Source initially lacks _reached_traj_end; check_termination creates False and probe leaves it present. _should_terminate and all audited numerical state remain unchanged. Exact whole-object restoration is therefore false for bounded source task.",
            "physical_failure_path": "Worker retains failed native cache and source exception and stops after LAST/nonfinite state. These completed trials and predicate probes do not exercise an actual failing native step or independently prove partial-failure recovery."},
        "limits": ["All source actuator/contact forces are not retained in NPZ; finite includes worker-side actuator_force/support/ground checks. Actor force sensor values are retained and finite, but are not the complete native force arrays.",
                   "Guard-restoration receipt stores comparison booleans/counts, not before/after arrays/hashes per array; its numerical restoration is source-reviewed producer evidence.",
                   "Only above-threshold predicate probes were executed; exact boundary empirical equivalence and source LAST handling were not tested here.",
                   "Guards and finite/warning evidence sampled every2ms, not at all0.2ms substeps.",
                   "One seed, straight20mm/s/rest schedules, flat floor; no turning, obstacles, fullbrain, biological stance, indefinite stability, or live runtime promotion.",
                   "The saved speed windows include a2ms interval preceding the nominal lower bound because selection uses interval end time; reported drift starts at the nominal lower bound."]}
    (ROOT/"validation/flybody-persistent-independent-review.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"passed_saved_array_checks": True, "control_steps": sum(x["completed_control_steps"] for x in rows),
        "actual_reference_rows_checked": sum(x["actual_actor_reference_rows_checked"] for x in rows),
        "cached_final_row_differences": cached}, indent=2))


if __name__ == "__main__":
    main()
