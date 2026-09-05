#!/usr/bin/env python3
"""Verify the optional airflow reader against four saved native geometry probes.

Run with the pinned FlyBody Python environment. No body/policy/neural steps.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from audit_flybody_airflow import load_pinned, CONFIG
import numpy as np

OUT = ROOT / "validation/flybody-airflow-module"
PLAN = OUT / "plan.json"
RESULT = OUT / "result.json"
SOURCES = ("scripts/check_flybody_airflow_module.py", "fruitfly/flybody_airflow.py",
           "scripts/audit_flybody_airflow.py", "validation/flybody-airflow-geometry.json",
           "validation/flybody-airflow-independent-review.json", "validation/flybody-source-manifest.json")
STATE = ("qpos", "qvel", "qacc", "act", "ctrl", "xpos", "xmat", "cvel", "sensordata")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.plan:
        if PLAN.exists() or RESULT.exists():
            raise FileExistsError("Retain existing module proof")
        OUT.mkdir(exist_ok=True)
        write(PLAN, {"source_sha256": {p: sha(ROOT / p) for p in SOURCES},
            "native_worker_revision": "f433f4f", "seed": 11, "physics_steps": 0,
            "tests": "New reader against all four previously independently reviewed native geometry probes; exact native state bytes and actor observations before/after; detached forwarded copies only",
            "tolerance": 1e-12, "runtime_integration": False,
            "claim_limit": "Read-only point geometry; no distal receptor calibration, wind force, neural input or body runtime promotion"})
        print("Frozen module plan", sha(PLAN), flush=True)
        return
    if RESULT.exists():
        raise FileExistsError("Retain existing module proof")
    plan = json.loads(PLAN.read_text())
    for p, h in plan["source_sha256"].items():
        if sha(ROOT / p) != h:
            raise ValueError("Source changed: " + p)
    old = json.loads((ROOT / "validation/flybody-airflow-geometry.json").read_text())
    review = json.loads((ROOT / "validation/flybody-airflow-independent-review.json").read_text())
    assert old["passed"] and review["passed"]
    worker_module = load_pinned("fruitfly/flybody_worker.py", "airflow_module_frozen_worker")
    worker = worker_module.Worker(CONFIG, plan["seed"])
    import mujoco
    from fruitfly.flybody_airflow import FlyBodyAirflow
    live = worker.d.ptr
    initial_state = {k: np.asarray(getattr(live, k)).tobytes().hex() for k in STATE}
    initial_obs = {k: np.asarray(v).tobytes().hex() for k, v in worker.step_result.observation.items()}
    initial_time = float(live.time)
    neutral = copy.copy(live)
    mujoco.mj_forward(worker.m.ptr, neutral)
    reader = FlyBodyAirflow(worker.m.ptr, neutral)
    np.testing.assert_allclose(reader.basis, old["anatomical_basis_in_head"], rtol=0, atol=plan["tolerance"])
    probes = []
    for probe in old["probes"]:
        data = copy.copy(live)
        data.qpos[:] = probe["qpos"]
        data.qvel[:] = probe["qvel"]
        mujoco.mj_forward(worker.m.ptr, data)
        before = {k: np.asarray(getattr(data, k)).tobytes().hex() for k in STATE}
        sample = reader.sample(data)
        errors = {}
        refs = {"antenna_origin_positions_mm": np.asarray([a["position_world_cm"] for a in probe["antennae"]]) * 10,
                "antenna_origin_velocity_world_mm_s": np.asarray([a["origin_velocity_jacobian_cm_s"] for a in probe["antennae"]]) * 10,
                "head_to_world": probe["head_to_world"]}
        for key, expected in refs.items():
            error = float(np.max(abs(np.asarray(sample[key]) - expected)))
            assert error <= plan["tolerance"], (probe["case"], key, error)
            errors[key] = error
        after = {k: np.asarray(getattr(data, k)).tobytes().hex() for k in STATE}
        assert before == after
        probes.append({"case": probe["case"], "qpos": probe["qpos"], "qvel": probe["qvel"],
            "sample": sample, "max_abs_errors": errors, "data_before": before, "data_after": after,
            "time_s": float(data.time), "state_unchanged": before == after})
    final_state = {k: np.asarray(getattr(live, k)).tobytes().hex() for k in STATE}
    final_obs = {k: np.asarray(v).tobytes().hex() for k, v in worker.step_result.observation.items()}
    assert initial_state == final_state and initial_obs == final_obs and initial_time == live.time == 0.
    assert all(sha(ROOT / p) == h for p, h in plan["source_sha256"].items())
    write(RESULT, {"passed": True, "plan_sha256": sha(PLAN), "module_sha256": sha(ROOT / "fruitfly/flybody_airflow.py"),
        "metadata": reader.metadata, "source_revision": "f433f4f", "physics_steps": 0,
        "mujoco": mujoco.__version__, "numpy": np.__version__, "probes": probes,
        "native_state_before": initial_state, "native_state_after": final_state,
        "actor_observation_before": initial_obs, "actor_observation_after": final_obs,
        "initial_time_s": initial_time, "final_time_s": float(live.time),
        "source_hashes_unchanged": True, "runtime_integration": False,
        "state_byte_encoding": "Native little-endian float64 raw bytes encoded as hex; shape follows source arrays. These are the explicit nine arrays named in the plan script, not all MuJoCo state."})
    print(json.dumps({"passed": True, "probes": len(probes), "physics_steps": 0}), flush=True)


if __name__ == "__main__":
    main()
