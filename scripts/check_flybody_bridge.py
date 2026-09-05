"""Compare optional RPC body with frozen native neutral-zero stance traces.

Run --plan-only before --run. Uses the project's Python3.12; bridge owns3.10.
This is engineering parity, not a new biological validation or controller fit.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback
import numpy as np
from fruitfly.flybody_bridge import FlyBodyConfig, FlyBodyRuntime

PLAN = Path("validation/flybody-bridge-plan.json")
RESULT = Path("validation/flybody-bridge-validation.json")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan():
    old = json.loads(Path("validation/flybody-stance-experiment.json").read_text())
    rows = [row for row in old["trials"] if row["variant"] == "neutral_zero" and row["assay"] in ("zero_start", "walk_stop_resume")]
    return {"created_at": datetime.now(timezone.utc).isoformat(), "seed": 11,
        "source_trials": [{key: row[key] for key in ("assay", "trace", "trace_sha256")} for row in rows],
        "files": {p: digest(p) for p in ("fruitfly/flybody_bridge.py", "fruitfly/flybody_worker.py",
            "scripts/check_flybody_bridge.py", "validation/flybody-source-manifest.json", "validation/flybody-walking-acquisition.json")},
        "duration_s": 2., "control_s": .002, "config": {"width": 800, "height": 560},
        "tolerance_absolute": 1e-10,
        "rules": ["Compare all1001 qpos/qvel/pose/actuator-length/activation samples and1000 native actions to frozen trace.",
            "No fit; physical arrays all finite, warningszero, native clock exact to1e-10.",
            "Render follow/side/overview during trace: worker asserts qpos/qvel/qacc/act/ctrl/sensordata/time unchanged.",
            "Cached observe/snapshot/diagnostics and advance0 cannot advance worker, host field or physiology.",
            "Partial2ms ticks and beyond2s errors must preserve state; reset returns native clock0 and initialqpos.",
            "Actual tarsal-plane contact controls taste; preserve each leg's positive/negative contact condition.",
            "Resource balances within1e-10. Source failures retained in trace, never substituted."]}


def run(p):
    for path, expected in p["files"].items():
        if digest(path) != expected:
            raise ValueError("Changed after plan: " + path)
    folder = Path("runs") / ("flybody-bridge-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    folder.mkdir(parents=True)
    results = []
    for case in p["source_trials"]:
        if digest(case["trace"]) != case["trace_sha256"]:
            raise ValueError("Frozen trace changed")
        raw, frames, failure = [], [], None
        started = time.perf_counter()
        with FlyBodyRuntime(seed=11, config=p["config"], log_path=folder / (case["assay"] + ".log")) as body:
            initial = body.diagnostics()
            raw.append(initial)
            try:
                for tick in range(1000):
                    t = tick * .002
                    on = case["assay"] != "zero_start" and (t < .6 or t >= 1.2)
                    observation = body.advance(.002, 1., 1., "walk" if on else "rest")
                    d = body.diagnostics()
                    raw.append(d)
                    assert d["finite"] and not any(d["warnings"])
                    assert abs(d["native_time_s"] - (tick + 1) * .002) < 1e-10
                    assert max(abs(v) for v in body.snapshot()["resource_balance"].values()) < 1e-10
                    for kind in ("food", "water"):
                        actual = body._contacts(d, kind)
                        assert observation[kind + "_contact_by_leg"] == actual
                    if tick in (199, 399, 599):
                        camera = ("follow", "side", "overview")[(199, 399, 599).index(tick)]
                        frame = body.render(camera)
                        assert frame.shape == (560, 800, 3) and frame.dtype == np.uint8
                        from PIL import Image
                        path = folder / (case["assay"] + "-" + camera + ".png")
                        Image.fromarray(frame).save(path)
                        frames.append(str(path))
                        assert body.diagnostics() == d
                        snapshot = body.snapshot()
                        assert body.advance(0) == observation
                        assert body.snapshot() == snapshot
                        assert body.observe() == observation
                        with_invalid = False
                        try:
                            body.advance(.001)
                        except ValueError:
                            with_invalid = True
                        assert with_invalid and body.diagnostics() == d
                before = body.diagnostics()
                try:
                    body.advance(.002)
                except RuntimeError as error:
                    assert "horizon" in str(error)
                else:
                    raise AssertionError("Horizon not enforced")
                assert body.diagnostics() == before
                body.reset(seed=11)
                np.testing.assert_array_equal(body.diagnostics()["qpos"], initial["qpos"])
                assert body.time_s == 0.
            except Exception as error:
                failure = type(error).__name__ + ": " + str(error)
                (folder / (case["assay"] + "-failure.txt")).write_text(traceback.format_exc())
                failed = body.diagnostics()
                if not raw or failed != raw[-1]:
                    raw.append(failed)
            metadata = body.snapshot()["backend"]
        trace_path = folder / (case["assay"] + ".jsonl")
        trace_path.write_text("".join(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n" for row in raw))
        source = np.load(case["trace"])
        errors = {}
        for old_key, new_key in (("qpos", "qpos"), ("qvel", "qvel"), ("pose", "pose_cm_quat"),
                ("actuator_length", "actuator_length"), ("actuator_activation", "actuator_activation")):
            value = np.asarray([row[new_key] for row in raw])
            errors[old_key] = float(np.max(abs(value - source[old_key][:len(value)])))
        actions = np.asarray([row["native_action"] for row in raw[1:]])
        errors["native_action"] = float(np.max(abs(actions - source["native_action"][:len(actions)]))) if len(actions) else None
        passed = failure is None and len(raw) == 1001 and all(error is not None and error <= p["tolerance_absolute"] for error in errors.values())
        results.append({"assay": case["assay"], "passed": bool(passed), "failure": failure,
            "samples": len(raw), "max_absolute_error": errors, "trace": str(trace_path),
            "trace_sha256": digest(trace_path), "frames": frames, "wall_s": time.perf_counter() - started,
            "metadata": metadata})
        RESULT.write_text(json.dumps({"complete": False, "plan_sha256": digest(PLAN), "trials": results}, indent=2) + "\n")
        print(case["assay"], "passed", passed, "max_error", max(e for e in errors.values() if e is not None), failure, flush=True)
    report = {"complete": True, "passed": all(row["passed"] for row in results), "plan_sha256": digest(PLAN), "trials": results}
    RESULT.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.plan_only:
        if PLAN.exists():
            raise FileExistsError("Existing parity plan")
        PLAN.write_text(json.dumps(plan(), indent=2) + "\n")
        print(PLAN)
    elif args.run:
        report = run(json.loads(PLAN.read_text()))
        if not report["passed"]:
            raise SystemExit(1)
    else:
        parser.error("Choose --plan-only or --run")


if __name__ == "__main__":
    main()
