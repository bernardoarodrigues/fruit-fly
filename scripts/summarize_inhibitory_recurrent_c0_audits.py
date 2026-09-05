#!/usr/bin/env python3
"""Aggregate already completed independent C0 audits; no project imports/reruns."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-c0-audit-summary.json"
ACTIVE_SHA = "2329e31a90bfaae48372a36ce3ccd03146bdec785dff9c511737c10bead81226"
QUIET_SHA = "1e2d91757813372de3fa3d5df100690ab7ac6d3805fe7f7035e3ebc5f6424da8"
PLAN_SHA = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
EDGES = [0, 500, 5000, 10000, 15000, 20000, 25000, 30000]
checks = []
pins = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rec(path):
    path = Path(path)
    b = path.read_bytes()
    v = {"path": str(path.relative_to(ROOT)), "bytes": len(b), "sha256": sha(b)}
    pins[v["path"]] = v
    return v


def read(path):
    rec(path)
    return json.loads(Path(path).read_text())


def check(name, truth):
    checks.append({"name": name, "passed": bool(truth)})
    if not truth:
        raise AssertionError(name)


def verified_small_chunk(directory, ordinal, artifact_map):
    stem = directory / f"chunk-{ordinal:04d}"
    marker = read(stem.with_suffix(".complete.json"))
    meta = read(stem.with_suffix(".json"))
    check(f"boundary bundle transaction {directory.name} {ordinal}", marker["complete"] and marker["transaction"] == meta["transaction"])
    for item in marker["artifacts"]:
        check("boundary artifact " + item["path"], rec(ROOT / item["path"]) == item == artifact_map[item["path"]])
    check("boundary marker pinned " + directory.name, rec(stem.with_suffix(".complete.json")) == artifact_map[str(stem.with_suffix(".complete.json").relative_to(ROOT))])
    ns = dict(meta["tree"]["items"])
    with np.load(stem.with_suffix(".npz"), allow_pickle=False) as z:
        packed = z[meta["tree"]["spikes"]["array"]["key"]]
        data = {name: z[ns[name]["array"]["key"]] for name in ["candidate", "applied", "selected_v", "selected_s", "selected_prethreshold_v", "selected_fired"]}
    return packed, data


def summarize(out):
    plan = read(PLAN)
    check("exact frozen plan", pins[str(PLAN.relative_to(ROOT))]["sha256"] == PLAN_SHA)
    active_path = ROOT / "scripts/review_inhibitory_recurrent_panel_active.py"
    quiet_path = ROOT / "scripts/review_inhibitory_recurrent_panel_trial.py"
    check("unchanged independent readers", rec(active_path)["sha256"] == ACTIVE_SHA and rec(quiet_path)["sha256"] == QUIET_SHA)
    check("exact C0 panel and windows", plan["window_edges_ticks"] == EDGES and plan["seeds"] == [11, 12, 13] and
          len(plan["order"][:15]) == 15 and all(t["arm"] == "C0" for t in plan["order"][:15]))
    run = ROOT / plan["run_dir"]
    selection = read(run / "selection.json")
    rec(run / "selection.npz")
    for path in [run / "selection.json", run / "selection.npz"]:
        check("frozen selection " + path.name, pins[str(path.relative_to(ROOT))] == plan["sources"][str(path.relative_to(ROOT))])
    sn = dict(selection["tree"]["items"])
    with np.load(run / "selection.npz", allow_pickle=False) as z:
        source = z[sn["inputs"]["array"]["key"]]
        selected = z[sn["selected"]["array"]["key"]]
        selected_ids = z[sn["selected_body_ids"]["array"]["key"]]
        cn = dict(sn["cohorts"]["items"])
        bn = dict(sn["cohort_body_ids"]["items"])
        cohorts = {name: z[node["array"]["key"]] for name, node in cn.items()}
        bodyids = {name: z[node["array"]["key"]] for name, node in bn.items()}
    trials = []
    by_seed_condition = {}
    boundaries = []
    component_checks = 0
    for spec in plan["order"][:15]:
        directory = run / spec["name"]
        suffix = "independent-review" if spec["ordinal"] == 0 else "active-review"
        rp = ROOT / "validation" / ("inhibitory-recurrent-panel-" + spec["name"] + "-" + suffix + ".json")
        audit = read(rp)
        terminal = read(directory / "terminal.json")
        result = read(directory / "result.json")
        check("passed audit and terminal " + spec["name"], audit["passed"] and not audit["failures"] and audit["error"] is None and
              terminal["complete"] and terminal["status"] == "complete" and result["complete"] and result["status"] == "complete" and not result["errors"])
        check("audit identity and hashes " + spec["name"], audit["trial"] == spec and audit["plan_sha256"] == PLAN_SHA and
              audit["terminal_sha256"] == pins[str((directory / "terminal.json").relative_to(ROOT))]["sha256"] and
              audit["result_sha256"] == pins[str((directory / "result.json").relative_to(ROOT))]["sha256"] == terminal["result"]["sha256"] and
              audit["source_sha256"][str(quiet_path.relative_to(ROOT))] == QUIET_SHA and
              (spec["ordinal"] == 0 or audit["source_sha256"][str(active_path.relative_to(ROOT))] == ACTIVE_SHA))
        check("all audit categories pass " + spec["name"], all(v["checked"] == v["passed"] for v in audit["categories"].values()) and
              sum(v["checked"] for v in audit["categories"].values()) == audit["check_count"])
        category = "quiet_cohort_metrics" if spec["ordinal"] == 0 else "raw_cohort_metrics"
        check("independent raw count metrics certified " + spec["name"], audit["categories"][category]["passed"] == (12 if spec["ordinal"] == 0 else 84))
        summary = result["summary"]
        check("all seven complete windows " + spec["name"], summary["window_edges_ticks"] == EDGES and summary["window_complete"] == [True] * 7 and
              summary["complete_window_count"] == 7 and result["counts_end_tick"] == summary["completed_tick"] == 30000)
        cohort_summary = {}
        for name, idx in cohorts.items():
            rows = summary["cohort_metrics"][name]
            counts = [row["spike_count"] for row in rows]
            check("cohort identity and nonmissing counts " + spec["name"] + " " + name, len(rows) == 7 and
                  sha(idx.astype("<i8").tobytes()) == summary["cohort_index_sha256"][name] and
                  all(isinstance(c, int) and c >= 0 and row["complete"] and row["population_size"] == len(idx)
                      for c, row in zip(counts, rows)))
            # Integers and fixed durations fully specify rates; no producer helper.
            rates = [c / ((hi - lo) * .0001 * len(idx)) for c, lo, hi in zip(counts, EDGES[:-1], EDGES[1:])]
            cohort_summary[name] = {"n": len(idx), "counts": counts, "mean_rates_hz": rates,
                                    "active_cells": [r["recruited_cells"] for r in rows]}
        trial = {"spec": spec, "review": pins[str(rp.relative_to(ROOT))], "review_check_count": audit["check_count"],
                 "terminal_sha256": audit["terminal_sha256"], "result_sha256": audit["result_sha256"],
                 "spikes": result["spike_count"], "candidates": result["candidate_count"], "applied": result["applied_count"],
                 "cohorts": cohort_summary}
        component_checks += audit["check_count"]
        trials.append(trial)
        by_seed_condition[(spec["seed"], spec["condition"])] = trial
        if sum(cohort_summary["source"]["counts"][4:]):
            amap = {r["path"]: r for r in result["artifacts"]}
            _, previous = verified_small_chunk(directory, 299, amap)
            packed, first_off = verified_small_chunk(directory, 300, amap)
            observed = packed[np.isin(packed["index"], source)]
            check("first off chunk covers all source off spikes " + spec["name"], len(observed) == sum(cohort_summary["source"]["counts"][4:]))
            events = []
            for spike in observed:
                i, tick = int(spike["index"]), int(spike["tick"])
                col = int(np.flatnonzero(source == i)[0]); j = int(np.flatnonzero(selected == i)[0])
                event = {"tick": tick, "graph_index": i, "body_id": int(selected_ids[j]), "source_column": col,
                         "candidate14999": bool(previous["candidate"][49, col]), "applied14999": bool(previous["applied"][49, col]),
                         "fired14999": bool(previous["selected_fired"][49, j]), "prethreshold14999_mv": float(previous["selected_prethreshold_v"][49, j]),
                         "post14999_mv": float(previous["selected_v"][50, j]), "s_before_after14999": previous["selected_s"][49:51, j].tolist(),
                         "prethreshold15000_mv": float(first_off["selected_prethreshold_v"][0, j]), "fired15000": bool(first_off["selected_fired"][0, j]),
                         "post15000_mv": float(first_off["selected_v"][1, j]), "first_off_chunk_candidates": int(first_off["candidate"].sum()),
                         "first_off_chunk_applied": int(first_off["applied"].sum())}
                event["last_pre_off_direct_then_threshold_supported"] = (tick == 15000 and event["applied14999"] and not event["fired14999"] and
                    event["prethreshold14999_mv"] <= -45 and event["post14999_mv"] == event["prethreshold14999_mv"] + 68.75 and
                    event["prethreshold15000_mv"] > -45 and event["fired15000"] and event["post15000_mv"] == -52 and
                    event["first_off_chunk_candidates"] == event["first_off_chunk_applied"] == 0)
                events.append(event)
            boundaries.append({"spec": spec, "events": events})
    contrasts = []
    for seed in [11, 12, 13]:
        for name in cohorts:
            rows = {condition: by_seed_condition[(seed, condition)]["cohorts"][name] for condition in plan["condition_order"]}
            constant = rows["constant_baseline"]["mean_rates_hz"]
            ea = rows["ethyl_acetate"]["mean_rates_hz"]
            ia = rows["isoamyl_acetate"]["mean_rates_hz"]
            blocked = rows["ethyl_acetate_source_outputs_blocked"]["mean_rates_hz"]
            contrasts.append({"seed": seed, "cohort": name,
                "pulse_minus_own_baseline_hz": {c: r["mean_rates_hz"][2] - r["mean_rates_hz"][1] for c, r in rows.items()},
                "EA_minus_constant_pulse_hz": ea[2] - constant[2], "IA_minus_constant_pulse_hz": ia[2] - constant[2],
                "EA_minus_IA_pulse_hz": ea[2] - ia[2], "EA_minus_blocked_pulse_hz": ea[2] - blocked[2],
                "EA_pulse_response_minus_constant_pulse_response_hz": (ea[2] - ea[1]) - (constant[2] - constant[1]),
                "IA_pulse_response_minus_constant_pulse_response_hz": (ia[2] - ia[1]) - (constant[2] - constant[1]),
                "EA_minus_IA_off_mean_rates_hz": [ea[w] - ia[w] for w in [4, 5, 6]],
                "EA_minus_blocked_off_mean_rates_hz": [ea[w] - blocked[w] for w in [4, 5, 6]],
                "withdrawal": {c: {"off_counts": r["counts"][4:], "off_mean_rates_hz": r["mean_rates_hz"][4:],
                    "early_off_minus_recovery_hz": r["mean_rates_hz"][4] - r["mean_rates_hz"][3],
                    "late_minus_early_off_hz": r["mean_rates_hz"][6] - r["mean_rates_hz"][4],
                    "strictly_increasing_three_off_bins": r["counts"][4] < r["counts"][5] < r["counts"][6]} for c, r in rows.items()}})
    rec(Path(__file__))
    check("all retained aggregate inputs unchanged", all(sha((ROOT / path).read_bytes()) == record["sha256"] for path, record in pins.items()))
    out.update(passed=True, independently_reviewed_trials=15, component_check_count=component_checks,
               trials=trials, contrasts=contrasts, off_source_boundary_evidence=boundaries,
               cohort_identity={name: {"n": len(idx), "index_i64_sha256": sha(idx.astype("<i8").tobytes()),
                                      "body_ids_i64_sha256": sha(bodyids[name].astype("<i8").tobytes()),
                                      **({"body_ids": bodyids[name].tolist()} if len(idx) <= 36 else {})} for name, idx in cohorts.items()})


def main():
    if OUT.exists():
        raise FileExistsError("Preserve the first aggregate execution")
    out = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "window_edges_ticks": EDGES, "dt_s": .0001,
           "method": "Aggregate previously passed independent saved-data readers. Their reconstructed per-neuron counts and cohort-rate equality certify the pinned result summary operands used here. No raw stream or model rerun during aggregation; only neighboring boundary source arrays are read separately.",
           "comparison_semantics": "Rates divide exact integer counts by fixed full-cohort size and duration. Baseline is [0.05,0.5), pulse [0.5,1), recovery [1,1.5), then three 0.5-second off windows. Every operand must be a complete certified window; complete zero remains zero, unavailable evidence causes aggregate failure rather than zero substitution.",
           "limits": ["Three specified seeds and C0 only; no altered-arm comparison or promotion.",
                      "No claim of indefinite persistence, attractor stability or biological plausibility from the 3-second runs.",
                      "Fixed motor group spikes are neural readouts, not movement or feeding.",
                      "Differences are descriptive paired arithmetic, not significance tests or calibrated physiological targets.",
                      "Active reader reconstructs selected48 state algebra and own-history queues but not all intermediate global voltage states; exact global accepted/unavailable dispositions beyond selected events are not independently reconstructed."]}
    try:
        summarize(out)
    except Exception as e:
        out["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
    out.update(checks=checks, check_count=len(checks), input_receipts=pins)
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"passed": out["passed"], "checks": len(checks), "receipt_sha256": sha(OUT.read_bytes()), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
