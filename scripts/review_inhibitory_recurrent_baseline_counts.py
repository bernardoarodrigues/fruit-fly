#!/usr/bin/env python3
"""Independent count-only audit of one completed, immutable panel trial.

Imports no project code. Reads one packed spike array at a time and uses simple
half-open masks plus integer bincounts. Does not inspect neural event/state math.
"""
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260905T060501089987Z-inhibitory-recurrent-panel"
TRIAL = RUN / "01-C0-seed11-constant_baseline"
OUT = ROOT / "validation/inhibitory-recurrent-panel-baseline-count-review.json"
EDGES = [0, 500, 5000, 10000, 15000, 20000, 25000, 30000]
NAMES = ["startup", "baseline", "pulse", "recovery", "off_early", "off_middle", "off_late"]
DTYPE = np.dtype([("tick", "<i8"), ("index", "<i4")])
checks = []
pins = {}
verified_files = {}


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    if not value:
        raise AssertionError(name)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": sha(data)}


def pin(path):
    rec = file_record(path)
    pins[rec["path"]] = rec
    return rec


def verify_record(rec):
    path = ROOT / rec["path"]
    actual = file_record(path)
    if actual != rec:
        raise AssertionError("file receipt mismatch: " + rec["path"])
    verified_files[rec["path"]] = actual


def read_json(path):
    return json.loads(Path(path).read_text())


def bundle_meta(stem, artifact_map=None):
    meta_path = stem.with_suffix(".json")
    complete_path = stem.with_suffix(".complete.json")
    marker = read_json(complete_path)
    meta = read_json(meta_path)
    if not marker["complete"] or marker["transaction"] != meta["transaction"]:
        raise AssertionError("incomplete bundle: " + str(stem))
    for rec in marker["artifacts"]:
        verify_record(rec)
        if artifact_map is not None and artifact_map[rec["path"]] != rec:
            raise AssertionError("result/bundle receipt mismatch")
    if artifact_map is not None:
        verify_record(artifact_map[str(complete_path.relative_to(ROOT))])
    return meta


def nodes(tree):
    return dict(tree["items"])


def array(npz, node):
    desc = node["array"]
    a = npz[desc["key"]]
    if (list(a.shape) != desc["shape"] or a.dtype.str != desc["dtype"] or
            a.nbytes != desc["bytes"] or a.size != desc["count"] or
            a.dtype.itemsize != desc["itemsize"] or sha(a.tobytes()) != desc["sha256"]):
        raise AssertionError("array descriptor mismatch: " + desc["key"])
    return a


def ratio_record(value):
    return {"numerator": value.numerator, "denominator": value.denominator, "decimal": float(value)}


def audit(out):
    manifest = read_json(RUN / "manifest.json")
    verify_record(manifest["plan"])
    plan_path = ROOT / manifest["plan"]["path"]
    plan = read_json(plan_path)
    old_path = ROOT / "validation/or42a-summary-plan.json"
    id_path = ROOT / "data/processed/malecns_v1/neuron_ids.npy"
    for p in [plan_path, old_path, id_path, RUN / "manifest.json", RUN / "selection.json",
              RUN / "selection.npz", RUN / "selection.complete.json", TRIAL / "terminal.json",
              TRIAL / "result.json", Path(__file__)]:
        pin(p)
    for p in [old_path, id_path, RUN / "selection.json", RUN / "selection.npz", RUN / "selection.complete.json"]:
        verify_record(plan["sources"][str(p.relative_to(ROOT))])
    old = read_json(old_path)
    neuron_ids = np.load(id_path, allow_pickle=False)
    check("frozen plan fixed clock, windows and baseline schedule", plan["dt_ms"] == 0.1 and
          plan["chunk_ticks"] == 50 and plan["window_edges_ticks"] == EDGES and
          plan["condition_rates_hz"]["constant_baseline"] == [11., 11., 11., 0.] and
          plan["schedule_boundaries_ticks"] == [0, 5000, 10000, 15000, 30000])
    check("graph identity vector length and uniqueness", len(neuron_ids) == plan["neurons"] == 166700 and
          len(np.unique(neuron_ids)) == 166700)
    smeta = bundle_meta(RUN / "selection")
    snodes = nodes(smeta["tree"])
    with np.load(RUN / "selection.npz", allow_pickle=False) as z:
        inputs = array(z, snodes["inputs"])
        cnodes = nodes(snodes["cohorts"])
        bnodes = nodes(snodes["cohort_body_ids"])
        names = ["all", "source", "non_source"] + ["motor:" + k for k in old["motor_groups"]]
        cohorts = {name: array(z, cnodes[name]) for name in names}
        bodies = {name: array(z, bnodes[name]) for name in names}
    source = np.asarray(old["source_graph_indices"], dtype=np.int32)
    check("36 source indices and original IDs exact", len(source) == 36 and
          np.array_equal(inputs, source) and np.array_equal(cohorts["source"], source) and
          np.array_equal(neuron_ids[source], old["source_body_ids"]))
    expected_non_source = np.flatnonzero(~np.isin(np.arange(len(neuron_ids)), source))
    check("source and non-source partition all graph indices", np.array_equal(cohorts["all"], np.arange(166700)) and
          np.array_equal(cohorts["non_source"], expected_non_source) and len(expected_non_source) == 166664)
    for name in names:
        check("cohort ID join " + name, np.array_equal(neuron_ids[cohorts[name]], bodies[name]))
    for name, ids in old["motor_groups"].items():
        check("original motor group " + name, list(bodies["motor:" + name]) == ids and len(ids) == 2)
    terminal = read_json(TRIAL / "terminal.json")
    verify_record(terminal["result"])
    result = read_json(TRIAL / "result.json")
    amap = {r["path"]: r for r in result["artifacts"]}
    check("terminal and result complete, error free and exact trial identity", terminal["status"] == "complete" and
          terminal["complete"] and not terminal["errors"] and result["status"] == "complete" and
          result["complete"] and not result["errors"] and
          (result["arm"], result["seed"], result["condition"], result["ordinal"]) == ("C0", 11, "constant_baseline", 1))
    check("all saved coverage clocks at 30000", all(result[k] == 30000 for k in ["completed_tick",
          "last_durable_chunk_end_tick", "last_complete_checkpoint_tick", "confirmed_prefix_end_tick", "counts_end_tick"]))
    check("exactly 600 complete chunk markers", len(list(TRIAL.glob("chunk-*.complete.json"))) == 600)
    counts = np.zeros((7, len(neuron_ids)), dtype=np.int64)
    candidate_counts = np.zeros(7, dtype=np.int64)
    applied_counts = np.zeros(7, dtype=np.int64)
    stream_hash = hashlib.sha256()
    chunk_receipt_hash = hashlib.sha256()
    previous = None
    total = 0
    source_last = None
    for k in range(600):
        stem = TRIAL / f"chunk-{k:04d}"
        meta = bundle_meta(stem, amap)
        tree = meta["tree"]
        ns = nodes(tree)
        start, end = k * 50, (k + 1) * 50
        check(f"chunk {k:04d} complete contiguous clock", ns["start_tick"]["value"] == start and
              ns["end_tick"]["value"] == end and ns["completed_ticks"]["value"] == 50 and
              ns["status"]["value"] == "complete" and ns["coherent_state"]["value"] is True and ns["failure"]["value"] is None)
        with np.load(stem.with_suffix(".npz"), allow_pickle=False) as z:
            desc, head = tree["spikes"]["array"], tree["spikes"]["header"]
            packed = z[desc["key"]]
            raw = packed.tobytes()
            check(f"chunk {k:04d} packed exact header", packed.dtype == DTYPE and packed.ndim == 1 and
                  packed.dtype.itemsize == 12 and desc["shape"] == head["shape"] == [len(packed)] and
                  desc["count"] == head["count"] == len(packed) and desc["bytes"] == len(raw) and
                  head["version"] == 1 and head["itemsize"] == desc["itemsize"] == 12 and
                  desc["dtype"] == head["dtype"] == [["tick", "<i8"], ["index", "<i4"]] and
                  sha(raw) == desc["sha256"] == head["sha256"] and
                  sha(packed["tick"].astype(head["original_tick_dtype"]).tobytes()) == head["original_tick_sha256"] and
                  sha(packed["index"].astype(head["original_index_dtype"]).tobytes()) == head["original_index_sha256"])
            ticks, indices = packed["tick"], packed["index"]
            order_ok = bool(np.all((ticks[1:] > ticks[:-1]) | ((ticks[1:] == ticks[:-1]) & (indices[1:] > indices[:-1]))))
            check(f"chunk {k:04d} ordered unique records in bounds", np.all((ticks >= start) & (ticks < end)) and
                  np.all((indices >= 0) & (indices < len(neuron_ids))) and order_ok and
                  (not len(packed) or previous is None or previous < (int(ticks[0]), int(indices[0]))))
            if len(packed):
                previous = int(ticks[-1]), int(indices[-1])
            source_ticks = ticks[np.isin(indices, source)]
            if len(source_ticks):
                source_last = int(source_ticks[-1])
            candidates = array(z, ns["candidate"])
            applied = array(z, ns["applied"])
            check(f"chunk {k:04d} source mask shapes", candidates.dtype == applied.dtype == np.dtype(bool) and
                  candidates.shape == applied.shape == (50, 36) and not np.any(applied & ~candidates))
            for w, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
                chosen = (ticks >= lo) & (ticks < hi)
                counts[w] += np.bincount(indices[chosen], minlength=len(neuron_ids))
                row_mask = (np.arange(start, end) >= lo) & (np.arange(start, end) < hi)
                candidate_counts[w] += int(np.count_nonzero(candidates[row_mask]))
                applied_counts[w] += int(np.count_nonzero(applied[row_mask]))
            stream_hash.update(raw)
            total += len(packed)
            chunk_receipt_hash.update(json.dumps({"ordinal": k, "start": start, "end": end, "count": len(packed),
                "packed_sha256": sha(raw)}, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    for stem, field in [(TRIAL / "window-counts", "observed_window_counts"),
                        (TRIAL / "checkpoint-30000", "window_counts_observed")]:
        meta = bundle_meta(stem, amap)
        ns = nodes(meta["tree"])
        with np.load(stem.with_suffix(".npz"), allow_pickle=False) as z:
            saved = array(z, ns[field])
            check("all 1166900 per-neuron window counters equal " + stem.name, np.array_equal(saved, counts))
        pin(stem.with_suffix(".json")); pin(stem.with_suffix(".npz")); pin(stem.with_suffix(".complete.json"))
    check("raw total equals result and sum of counts", total == result["spike_count"] == int(counts.sum()))
    check("raw candidate/applied totals equal result", int(candidate_counts.sum()) == result["candidate_count"] and
          int(applied_counts.sum()) == result["applied_count"])
    check("off requested and applied inputs zero", not np.any(candidate_counts[4:]) and not np.any(applied_counts[4:]))
    summary = result["summary"]
    check("summary all seven windows complete with exact clock", summary["window_edges_ticks"] == EDGES and
          summary["window_names"] == NAMES and summary["window_complete"] == [True] * 7 and
          summary["complete_window_count"] == 7 and summary["completed_tick"] == 30000 and
          summary["dt_seconds"] == .0001 and summary["n_neurons"] == len(neuron_ids))
    outcome = {}
    for name in names:
        idx = cohorts[name]
        group = counts[:, idx]
        rows = []
        for w, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
            cnt = int(group[w].sum())
            recruited = int(np.count_nonzero(group[w]))
            poprate = Fraction(cnt * 10000, hi - lo)
            meanrate = poprate / len(idx)
            duration = Fraction(hi - lo, 10000)
            saved = summary["cohort_metrics"][name][w]
            check(f"summary {name} {NAMES[w]} exact counts and coverage", saved["spike_count"] == cnt == saved["observed_spikes"] and
                  saved["recruited_cells"] == recruited and saved["population_size"] == len(idx) and
                  saved["complete"] is True and saved["status"] == "complete" and
                  saved["nominal_duration_s"] == saved["observed_duration_s"] == float(duration))
            check(f"summary {name} {NAMES[w]} rate arithmetic", np.isclose(saved["population_rate_hz"], float(poprate), rtol=1e-14, atol=1e-12) and
                  np.isclose(saved["mean_cell_rate_hz"], float(meanrate), rtol=1e-14, atol=1e-12) and
                  np.isclose(saved["active_fraction"], recruited / len(idx), rtol=1e-14, atol=1e-12))
            rows.append({"window": NAMES[w], "half_open_ticks": [lo, hi], "duration_s": float(duration), "spikes": cnt,
                         "recruited_cells": recruited, "population_rate_hz": ratio_record(poprate), "mean_cell_rate_hz": ratio_record(meanrate)})
        outcome[name] = {"population_size": len(idx), "graph_index_dtype": str(idx.dtype), "graph_index_sha256": sha(idx.tobytes()),
                         "body_id_dtype": str(bodies[name].dtype), "body_id_sha256": sha(bodies[name].tobytes()), "windows": rows}
        if len(idx) <= 36:
            outcome[name].update(graph_indices=idx.tolist(), body_ids=bodies[name].tolist(), per_cell_window_counts=group.T.tolist())
    check("off source spikes absent", not np.any(counts[4:, source]))
    check("all pinned small evidence unchanged after streaming", all(file_record(ROOT / p) == rec for p, rec in pins.items()))
    out.update(passed=True, completed_tick=30000, chunks=600, spike_count=total, packed_stream_sha256=stream_hash.hexdigest(),
               ordered_chunk_header_receipt_sha256=chunk_receipt_hash.hexdigest(), all_window_count_sha256=sha(counts.tobytes()),
               count_matrix_shape=list(counts.shape), count_matrix_dtype=str(counts.dtype), candidate_counts=candidate_counts.tolist(),
               applied_counts=applied_counts.tolist(), source_last_spike_tick=source_last, cohorts=outcome,
               verified_artifact_count=len(verified_files), verified_artifact_total_bytes=sum(r["bytes"] for r in verified_files.values()),
               verified_artifact_manifest_sha256=sha(json.dumps(verified_files, sort_keys=True, separators=(",", ":")).encode()),
               frozen_graph_sha256=plan["graph_sha256"], input_rate_semantics=plan["input_semantics"])


def main():
    if OUT.exists():
        raise FileExistsError("Refusing to overwrite existing first audit receipt: " + str(OUT))
    out = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "trial": str(TRIAL.relative_to(ROOT)), "method": "Independent NumPy NPZ reads, 12-byte packed tick/index records, seven explicit half-open masks and int64 bincount; no producer metric/archive/model imports",
           "rate_definition": "population rate = count / duration; mean cell rate = count / (duration * entire fixed cohort size). Exact rational values retained; decimal comparison guard rtol 1e-14, atol 1e-12 is arithmetic only.",
           "scope_limits": ["One completed C0 seed11 constant-baseline realization only; no arm or seed robustness conclusion.",
                            "Count persistence through 3 seconds is descriptive, not proof of indefinite persistence, attractor stability or biological plausibility.",
                            "Motor group spike counts are readouts, not observed body movement or feeding.",
                            "No neural event transitions, intermediate global states, solver equations or biological thresholds assessed; no model rerun."]}
    try:
        audit(out)
    except Exception as exc:
        out.update(error={"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    out.update(checks=checks, check_count=len(checks), checks_passed=sum(c["passed"] for c in checks), input_receipts=pins)
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"passed": out["passed"], "check_count": len(checks), "spike_count": out.get("spike_count"),
                      "receipt": file_record(OUT), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
