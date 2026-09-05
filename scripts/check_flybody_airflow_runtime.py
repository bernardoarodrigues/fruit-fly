#!/usr/bin/env python3
"""Verify opt-in airflow through a fixed 2 s full-neural original-prefix replay."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import check_flybody_rolling_loop as recorder

OUT = ROOT / "validation/flybody-airflow-runtime"
PLAN = OUT / "plan.json"
RESULT = OUT / "result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def prepare():
    if PLAN.exists() or RESULT.exists():
        raise FileExistsError("Retain the previous airflow runtime evidence")
    previous = read(ROOT / "validation/flybody-rolling-loop/results.json")
    if not previous.get("complete") or not previous.get("all_declared_gates_pass"):
        raise ValueError("Finish the three unchanged longer neural trials first")
    prior_plan = read(ROOT / "validation/flybody-rolling-loop/plan.json")
    module_result = read(ROOT / "validation/flybody-airflow-module/result.json")
    assert module_result["passed"] and module_result["module_sha256"] == sha(ROOT / "fruitfly/flybody_airflow.py")
    plan = {k: copy.deepcopy(prior_plan[k]) for k in ("config", "expected_neurons", "expected_edges", "seed",
        "graph_sha256", "neural_parameters", "references")}
    plan["config"]["body"]["enable_wind"] = True
    files = ["scripts/check_flybody_airflow_runtime.py", "scripts/check_flybody_rolling_loop.py", "scripts/check_flybody_loop.py",
        "fruitfly/flybody_airflow.py", "fruitfly/flybody_bridge.py", "fruitfly/flybody_worker.py", "fruitfly/flybody_persistent_task.py",
        "fruitfly/simulation.py", "fruitfly/neural.py", "fruitfly/sensors.py", "fruitfly/proprioception.py", "fruitfly/wind.py",
        "fruitfly/body.py", "fruitfly/physiology.py", "fruitfly/data.py", "pyproject.toml", "uv.lock",
        "validation/flybody-airflow-module/plan.json", "validation/flybody-airflow-module/result.json",
        "validation/flybody-rolling-loop/plan.json", "validation/flybody-rolling-loop/results.json",
        "validation/flybody-source-manifest.json", "validation/flybody-walking-acquisition.json",
        "data/processed/malecns_v1/manifest.json", "data/processed/malecns_v1/neurons.feather"]
    plan.update(source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        ticks=1000, duration_s=2., coupling_s=.002,
        condition={"name": "locomotor_feedback", "assay": "motor_probe", "outgoing_blocks": [], "motor_mute": True},
        mute_intervals_ticks=[[300, 600]],
        source_sha256={p: sha(ROOT / p) for p in files},
        recorder_adapter="Reuse unchanged rolling run_condition/LosslessCapture/OriginalPrefix; set its PLAN to this file and MUTES to the sole 0.6–1.2 s interval. Add a read-only airflow check around inspect_physical. No engine/encoder wrapper changes.",
        gates=["Exact original 1000-tick physical/action/input/RNG/spike prefix with airflow enabled",
               "Lossless spikes, actual failure/final checkpoint, original lifecycle/clock/resource/source guard checks",
               "Observed head frame is a proper rotation; native origin positions equal odor points; independent relative-flow algebra and source azimuth match at every observed state",
               "New geometry finiteness; exactly 1001 distinct native ticks checked; source hashes unchanged"],
        limits="Two-second integration regression only, no wind force, neural transduction, arista/sensillum position, measured female transfer or biological behavior claim")
    OUT.mkdir(exist_ok=True)
    write(PLAN, plan)
    print("Frozen airflow integration plan", sha(PLAN), flush=True)


def run():
    if RESULT.exists():
        raise FileExistsError("Retain prior run")
    plan = read(PLAN)
    for p, h in plan["source_sha256"].items():
        if sha(ROOT / p) != h:
            raise ValueError("Changed source: " + p)
    # The frozen recorder exposes these script-level output/schedule controls.
    recorder.PLAN = PLAN
    recorder.MUTES = tuple(tuple(x) for x in plan["mute_intervals_ticks"])
    original = recorder.inspect_physical
    ticks = set()
    errors = {"origin_position_mm": 0., "relative_flow_mm_s": 0., "source_azimuth_deg": 0.}

    def inspect(runner):
        d = original(runner)
        geometry = d["airflow_geometry"]
        wind = runner.body.observe()["wind"]
        assert wind["enabled"] is True and runner.body.snapshot()["capabilities"]["head_frame_wind"] is True
        point = np.asarray(geometry["antenna_origin_positions_mm"])
        velocity = np.asarray(geometry["antenna_origin_velocity_world_mm_s"])
        rotation = np.asarray(geometry["head_to_world"])
        assert point.shape == velocity.shape == (2, 3) and rotation.shape == (3, 3)
        assert all(np.isfinite(a).all() for a in (point, velocity, rotation))
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12, rtol=0)
        assert abs(np.linalg.det(rotation) - 1) < 1e-12
        delta = np.r_[runner.body.config.wind_mm_s, 0.] - velocity
        relative = np.column_stack([delta @ rotation[:, i] for i in range(3)])
        horizontal = np.sqrt(np.sum(relative[:, :2] ** 2, axis=1))
        azimuths = [float(np.rad2deg(np.arctan2(v[1], -v[0]))) if speed > 1e-9 else None
                   for v, speed in zip(relative, horizontal)]
        errors["origin_position_mm"] = max(errors["origin_position_mm"], float(np.max(abs(point - d["antenna_positions_mm"]))))
        errors["relative_flow_mm_s"] = max(errors["relative_flow_mm_s"], float(np.max(abs(relative - wind["relative_velocity_head_mm_s"]))))
        np.testing.assert_allclose(horizontal, wind["horizontal_speed_mm_s"], atol=1e-12, rtol=0)
        for actual, expected in zip(wind["source_azimuth_deg"], azimuths):
            if expected is None:
                assert actual is None
            else:
                errors["source_azimuth_deg"] = max(errors["source_azimuth_deg"], abs(actual - expected))
        assert max(errors.values()) < 1e-10
        ticks.add(d["tick"])
        return d

    recorder.inspect_physical = inspect
    folder = ROOT / "runs" / ("flybody-airflow-runtime-" + sha(PLAN)[:12])
    folder.mkdir()
    record = recorder.run_condition(plan["condition"], plan, folder)
    unchanged = {p: sha(ROOT / p) == h for p, h in plan["source_sha256"].items()}
    report = {"complete": True, "passed": record["all_condition_gates_pass"] and ticks == set(range(1001)) and all(unchanged.values()),
        "plan_sha256": sha(PLAN), "condition": record,
        "observed_native_tick_count": len(ticks), "observed_native_tick_range": [min(ticks), max(ticks)] if ticks else None,
        "max_abs_errors": errors, "sources_unchanged": unchanged, "biological_behavior_validated": False}
    write(RESULT, report)
    print(json.dumps({"passed": report["passed"], "ticks": len(ticks), "errors": errors}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    prepare() if args.plan else run()
