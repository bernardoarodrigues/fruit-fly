#!/usr/bin/env python3
"""Independently inspect saved bridge parity data; no physics or policy imports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LEGS = ("LF", "LM", "LH", "RF", "RM", "RH")


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def maximum_error(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        raise AssertionError(f"Shape mismatch {a.shape} != {b.shape}")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise AssertionError("Nonfinite comparison input")
    return float(np.max(np.abs(a - b))) if a.size else 0.


def main():
    plan_path = "validation/flybody-bridge-plan.json"
    receipt_path = "validation/flybody-bridge-validation.json"
    plan = json.loads((ROOT / plan_path).read_text())
    receipt = json.loads((ROOT / receipt_path).read_text())
    assert receipt["complete"] and receipt["passed"]
    assert sha(plan_path) == receipt["plan_sha256"]
    for path, expected in plan["files"].items():
        assert sha(path) == expected, path
    sources = {s["assay"]: s for s in plan["source_trials"]}
    trials = []
    for record in receipt["trials"]:
        source = sources[record["assay"]]
        assert sha(record["trace"]) == record["trace_sha256"]
        assert sha(source["trace"]) == source["trace_sha256"]
        with (ROOT / record["trace"]).open() as stream:
            rows = [json.loads(line) for line in stream]
        assert len(rows) == 1001
        native = np.load(ROOT / source["trace"], allow_pickle=False)
        errors = {}
        for bridge_key, source_key in {
            "qpos": "qpos", "qvel": "qvel", "pose_cm_quat": "pose",
            "actuator_length": "actuator_length", "actuator_activation": "actuator_activation",
            "tibia_rad": "tibia_rad", "claw_positions_mm": "tips_mm",
            "up_z": "up_z", "support_dyne_by_leg": "support_dyne",
        }.items():
            errors[bridge_key] = maximum_error([row[bridge_key] for row in rows], native[source_key])
        errors["native_action"] = maximum_error([row["native_action"] for row in rows[1:]], native["native_action"])
        errors["shadow_canonical_action"] = maximum_error([row["canonical_action"] for row in rows[1:]], native["shadow_canonical"])
        errors["native_action_vs_ctrl"] = max(maximum_error(
            np.asarray(row["ctrl"])[row["actuator_ids"]], row["native_action"]) for row in rows)
        errors["reference_target_before_next_action"] = maximum_error(
            [row["target_pose_cm_quat"] for row in rows[:-1]], native["target_pose"])
        time_error = maximum_error([row["native_time_s"] for row in rows], np.arange(1001) * .002)
        assert time_error < 1e-10
        assert [row["tick"] for row in rows] == list(range(1001))
        assert all(row["finite"] and not row["source_terminated"] and not any(row["warnings"]) for row in rows)
        contact_error = force_error = 0.
        active_tarsal_entries = 0
        for row in rows:
            support = np.zeros(6)
            ground = np.zeros((6, 3))
            for contact in row["contacts"]:
                leg = LEGS.index(contact["leg"])
                vector = np.asarray(contact["force_world_dyne"])
                support[leg] += abs(vector[2])
                ground[leg] += vector * 10
                active_tarsal_entries += bool(contact["active"] and contact["is_tarsal"])
                if contact["active"]:
                    assert contact["dist_cm"] <= 0
            contact_error = max(contact_error, maximum_error(support, row["support_dyne_by_leg"]))
            force_error = max(force_error, maximum_error(ground, row["ground_force_g_mm_s2"]))
        assert max(errors.values()) == 0., errors
        assert contact_error < 1e-12 and force_error < 1e-12
        trials.append({"assay": record["assay"], "all_samples": len(rows),
                       "action_samples": len(rows) - 1, "max_absolute_errors": errors,
                       "native_time_error_s": time_error,
                       "contact_sum_error_dyne": contact_error,
                       "ground_force_conversion_error_g_mm_s2": force_error,
                       "active_tarsal_contact_entries": active_tarsal_entries,
                       "native_trace": source["trace"], "native_trace_sha256": sha(source["trace"]),
                       "bridge_trace": record["trace"], "bridge_trace_sha256": sha(record["trace"])})
    paths = [plan_path, receipt_path, "fruitfly/flybody_bridge.py", "fruitfly/flybody_worker.py",
             "fruitfly/simulation.py", "tests/test_flybody_bridge.py", "tests/test_simulation.py",
             "scripts/review_flybody_bridge.py", "data/raw/flybody/source/flybody/fly_envs.py",
             "data/raw/flybody/source/flybody/tasks/base.py",
             "data/raw/flybody/source/flybody/tasks/walk_imitation.py",
             "data/raw/flybody/source/flybody/tasks/synthetic_trajectories.py",
             "data/raw/flybody/source/flybody/tasks/task_utils.py"]
    output = {"review_scope": "Read-only source review and independent calculations on saved arrays; no new physics, policy inference, or fullbrain run",
              "passed_saved_array_checks": True,
              "producer_metric_helpers_imported": False, "trials": trials,
              "files": {path: sha(path) for path in paths},
              "primary_velocity_point_source": "https://github.com/google-deepmind/mujoco/blob/3.2.7/src/engine/engine_support.c#L1171-L1181",
              "velocity_point_limit": "mjOBJ_BODY samples thorax inertial-center velocity; public pose is the free-joint attachment origin. They are not interchangeable derivative measurements.",
              "reported_defects_addressed_by_owners": [
                  "Whole-duration horizon guard before neural/sensor mutation",
                  "Cached body failure receipt when normal snapshot is invalid",
                  "Partial native-step failures preserve original worker error without a full host physiology tick",
                  "EOF/timeout/framing failure makes the transport terminal"],
              "unvalidated": ["Physical rest robustness beyond the two saved schedules",
                              "Natural male behavior or a biological DN-to-motor law",
                              "Physiological receptor positions, thermal/light/wind transduction",
                              "Continuous contact occupancy between 2ms samples",
                              "Independent contact solve; saved diagnostic force consistency is checked",
                              "Arbitrary forced worker kill, fragmented write, or exhausted disk during this review"]}
    (ROOT / "validation/flybody-bridge-independent-review.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"passed": True, "trials": [{"assay": r["assay"], "max_array_error": max(r["max_absolute_errors"].values()),
          "time_error_s": r["native_time_error_s"]} for r in trials]}, indent=2))


if __name__ == "__main__":
    main()
