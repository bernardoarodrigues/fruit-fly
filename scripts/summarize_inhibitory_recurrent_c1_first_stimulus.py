#!/usr/bin/env python3
"""Read certified C1 summaries and retained phase telemetry; no model imports."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-c1-first-stimulus-summary.json"
EXPECTED_PLAN = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
EXPECTED_READER = "2329e31a90bfaae48372a36ce3ccd03146bdec785dff9c511737c10bead81226"
pins, checks = {}, []


def record(path):
    path = Path(path)
    data = path.read_bytes()
    rec = {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    pins[rec["path"]] = rec
    return rec


def read(path):
    record(path)
    return json.loads(Path(path).read_text())


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    if not value:
        raise AssertionError(name)


def summarize(out):
    plan = read(PLAN)
    check("exact frozen panel plan", pins[str(PLAN.relative_to(ROOT))]["sha256"] == EXPECTED_PLAN)
    rp = ROOT / "scripts/review_inhibitory_recurrent_panel_active.py"
    check("unchanged frozen independent reader", record(rp)["sha256"] == EXPECTED_READER)
    run = ROOT / plan["run_dir"]
    trials = []
    for ordinal in [15, 18, 21, 24]:
        spec = plan["order"][ordinal]
        directory = run / spec["name"]
        receipt_path = ROOT / "validation" / ("inhibitory-recurrent-panel-" + spec["name"] + "-active-review.json")
        audit, terminal, result = read(receipt_path), read(directory / "terminal.json"), read(directory / "result.json")
        check("complete independently certified trial " + spec["name"], audit["passed"] and not audit["failures"] and audit["error"] is None and
              audit["trial"] == spec and audit["source_sha256"][str(rp.relative_to(ROOT))] == EXPECTED_READER and
              audit["plan_sha256"] == EXPECTED_PLAN and terminal["complete"] and terminal["status"] == "complete" and
              result["complete"] and result["status"] == "complete" and not result["errors"])
        check("certified result and terminal unchanged " + spec["name"], audit["result_sha256"] == record(directory / "result.json")["sha256"] == terminal["result"]["sha256"] and
              audit["terminal_sha256"] == record(directory / "terminal.json")["sha256"])
        check("all raw cohort metrics certified " + spec["name"], audit["categories"]["raw_cohort_metrics"]["passed"] == 84 and
              all(c["checked"] == c["passed"] for c in audit["categories"].values()))
        summary = result["summary"]
        check("seven complete windows " + spec["name"], summary["window_complete"] == [True] * 7 and
              summary["window_edges_ticks"] == plan["window_edges_ticks"] and summary["completed_tick"] == 30000)
        cohorts = {name: {"population_size": rows[0]["population_size"], "counts": [r["spike_count"] for r in rows],
                          "mean_rates_hz": [r["mean_cell_rate_hz"] for r in rows], "active_cells": [r["recruited_cells"] for r in rows]}
                   for name, rows in summary["cohort_metrics"].items()}
        trials.append({"spec": spec, "review": record(receipt_path), "review_check_count": audit["check_count"],
                       "spikes": result["spike_count"], "candidates": result["candidate_count"], "applied": result["applied_count"],
                       "cohorts": cohorts, "off_descriptive": summary["off_descriptive"]})
    directory = run / plan["order"][24]["name"]
    result = read(directory / "result.json")
    artifact_map = {r["path"]: r for r in result["artifacts"]}
    id_path = ROOT / "data/processed/malecns_v1/neuron_ids.npy"
    check("pinned graph ID vector", record(id_path) == plan["sources"][str(id_path.relative_to(ROOT))])
    ids = np.load(id_path, allow_pickle=False)
    phases = ["prethreshold", "postexternal", "postreset"]
    extremes = {name: None for name in phases}
    arrays = []
    for chunk in range(600):
        stem = directory / f"chunk-{chunk:04d}"
        meta = read(stem.with_suffix(".json"))
        check(f"phase chunk {chunk} metadata pinned", pins[str(stem.with_suffix(".json").relative_to(ROOT))] == artifact_map[str(stem.with_suffix(".json").relative_to(ROOT))])
        check(f"phase chunk {chunk} payload pinned", record(stem.with_suffix(".npz")) == artifact_map[str(stem.with_suffix(".npz").relative_to(ROOT))])
        top = dict(meta["tree"]["items"])
        per_tick = dict(top["per_tick"]["items"])
        with np.load(stem.with_suffix(".npz"), allow_pickle=False) as z:
            values = {}
            for name in ["phase_min", "phase_min_index"]:
                desc = per_tick[name]["array"]
                a = z[desc["key"]]
                check(f"phase chunk {chunk} {name} array hash", list(a.shape) == [50, 3] and
                      hashlib.sha256(a.tobytes()).hexdigest() == desc["sha256"])
                values[name] = a
            check(f"phase chunk {chunk} finite minima and valid identities", np.isfinite(values["phase_min"]).all() and
                  np.issubdtype(values["phase_min_index"].dtype, np.integer) and
                  np.all((values["phase_min_index"] >= 0) & (values["phase_min_index"] < len(ids))))
            for col, name in enumerate(phases):
                row = int(np.argmin(values["phase_min"][:, col]))
                value = float(values["phase_min"][row, col])
                index = int(values["phase_min_index"][row, col])
                if extremes[name] is None or value < extremes[name]["mv"]:
                    extremes[name] = {"mv": value, "tick": chunk * 50 + row, "graph_index": index, "body_id": int(ids[index]),
                                      "chunk": chunk, "row": row, "phase_column": col,
                                      "value_array_sha256": per_tick["phase_min"]["array"]["sha256"],
                                      "index_array_sha256": per_tick["phase_min_index"]["array"]["sha256"]}
        arrays.append({"chunk": chunk, "phase_min_sha256": per_tick["phase_min"]["array"]["sha256"],
                       "phase_min_index_sha256": per_tick["phase_min_index"]["array"]["sha256"]})
    record(Path(__file__))
    check("all retained evidence unchanged", all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == r["sha256"] for p, r in pins.items()))
    out.update(passed=True, trials=trials, retained_global_phase_minima=extremes,
               phase_array_manifest_sha256=hashlib.sha256(json.dumps(arrays, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
               phase_evidence_scope="Minimum of the producer's retained per-tick full-population phase-minimum telemetry over all 30000 ticks. Array and artifact hashes verified. Global phase extrema are not independently recomputed from full global states, which are saved only at checkpoints.")


def main():
    if OUT.exists():
        raise FileExistsError("Preserve first summary execution")
    out = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "method": "Read only previously passed independent C1 receipts and their pinned summaries; reduce retained per-tick phase minima for ordinal24. No producer metric/model imports or neural run.",
           "window_edges_ticks": [0, 500, 5000, 10000, 15000, 20000, 25000, 30000], "dt_s": .0001,
           "limits": ["Current-model engineering/numerical observations, not physiological voltages or calibrated natural behavior.",
                      "Three no-input seeds plus one stimulated C1 seed; no stimulated seed robustness or arm promotion.",
                      "Observed off activity over 1.5 seconds does not establish indefinite stability or growth.",
                      "Fixed motor-group spikes do not demonstrate movement or feeding."]}
    try:
        summarize(out)
    except Exception as e:
        out["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
    out.update(checks=checks, check_count=len(checks), input_receipts=pins)
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"passed": out["passed"], "checks": len(checks), "receipt_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
