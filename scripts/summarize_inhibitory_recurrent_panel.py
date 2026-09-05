#!/usr/bin/env python3
"""Reduce the completed factorial and passed saved-data audits; no neural runs.

The global phase extrema below are producer telemetry, independently reduced
from retained arrays. They are not reconstructed all-cell trajectories.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-combined-analysis.json"
PLAN_SHA = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
RESULT_SHA = "021bbc028ceec91611d97010fec48deae7940eb3b155649ba279a7ccf5f1916c"
EDGES = np.array([0, 500, 5000, 10000, 15000, 20000, 25000, 30000])
ARMS = ["C0", "C1", "H0", "H1"]
checks = 0
pins = {}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def check(ok, message):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(message)


def record(path):
    path = Path(path)
    b = path.read_bytes()
    row = dict(path=str(path.relative_to(ROOT)), bytes=len(b), sha256=sha(b))
    pins[row["path"]] = row
    return row


def read(path):
    record(path)
    return json.loads(Path(path).read_text())


def mapping(node):
    check(node["kind"] == "dict", "expected typed mapping")
    return dict(node["items"])


def array(node, archive):
    a = archive[node["array"]["key"]]
    r = node["array"]
    check(list(a.shape) == r["shape"] and a.dtype.str == r["dtype"] and
          a.nbytes == r["bytes"] and sha(a.tobytes()) == r["sha256"], "array payload integrity")
    return a


def run(out):
    plan = read(PLAN)
    check(record(PLAN)["sha256"] == PLAN_SHA, "frozen plan")
    run_dir = ROOT / plan["run_dir"]
    terminal = read(run_dir / "terminal.json")
    result = read(run_dir / "results.json")
    check(record(run_dir / "results.json") == terminal["results"] and
          terminal["results"]["sha256"] == RESULT_SHA, "authoritative final result")
    check(terminal["complete"] and terminal["status"] == "complete" and result["complete"] and
          result["status"] == "complete" and not result["errors"] and not result["contrast_exclusions"], "completed panel")
    check(len(result["trials"]) == len(plan["order"]) == 60, "full trial count")
    check(len({(x["arm"], x["seed"], x["condition"]) for x in result["trials"]}) == 60, "unique factorial cells")
    selection = read(run_dir / "selection.json")
    check(record(run_dir / "selection.json") == plan["sources"][plan["run_dir"] + "/selection.json"], "frozen cohort metadata")
    check(record(run_dir / "selection.npz") == plan["sources"][plan["run_dir"] + "/selection.npz"], "frozen cohort arrays")
    sn = mapping(selection["tree"])
    with np.load(run_dir / "selection.npz", allow_pickle=False) as z:
        cohorts = {name: array(node, z) for name, node in mapping(sn["cohorts"]).items()}
    trials = []
    component_checks = 0
    saved_digest = hashlib.sha256()
    saved_files = 0
    for spec, parent in zip(plan["order"], result["trials"]):
        name = spec["name"]
        directory = run_dir / name
        check(all(parent[k] == v for k, v in spec.items()), "ordered trial identity " + name)
        tr = read(directory / "result.json")
        tt = read(directory / "terminal.json")
        check(record(directory / "result.json") == parent["result"] == tt["result"] and
              record(directory / "terminal.json") == parent["terminal"], "trial receipt links " + name)
        check(tr["complete"] and tt["complete"] and tr["status"] == tt["status"] == "complete" and
              not tr["errors"] and tr["completed_tick"] == tr["counts_end_tick"] == 30000, "complete trial " + name)
        suffix = "independent-review" if spec["ordinal"] == 0 else ("H-review" if spec["arm"].startswith("H") else "active-review")
        rp = ROOT / "validation" / f"inhibitory-recurrent-panel-{name}-{suffix}.json"
        review = read(rp)
        check(review["passed"] and not review["failures"] and review["error"] is None and
              review["trial"] == spec and review["plan_sha256"] == PLAN_SHA and
              review["terminal_sha256"] == parent["terminal"]["sha256"] and
              review["result_sha256"] == parent["result"]["sha256"], "passed pinned independent audit " + name)
        check(all(c["checked"] == c["passed"] for c in review["categories"].values()) and
              sum(c["checked"] for c in review["categories"].values()) == review["check_count"], "audit totals " + name)
        component_checks += review["check_count"]
        summary = tr["summary"]
        check(summary == parent["summary"] and summary["window_edges_ticks"] == EDGES.tolist() and
              summary["window_complete"] == [True] * 7, "same complete summary " + name)
        # This terminal checkpoint's counts have also been recounted from all raw
        # spikes by the pinned independent reader. Here they supply distributions.
        artifact_map = {x["path"]: x for x in tr["artifacts"]}
        cp = read(directory / "checkpoint-30000.json")
        for path in [directory / "checkpoint-30000.json", directory / "checkpoint-30000.npz"]:
            check(record(path) == artifact_map[str(path.relative_to(ROOT))], "frozen final checkpoint " + name)
        with np.load(directory / "checkpoint-30000.npz", allow_pickle=False) as z:
            counts = array(mapping(cp["tree"])["window_counts_observed"], z)
        check(counts.shape == (7, plan["neurons"]) and counts.dtype.str == "<i8", "checkpoint count dimensions " + name)
        cm = {}
        for cohort, idx in cohorts.items():
            rows = summary["cohort_metrics"][cohort]
            c = counts[:, idx]
            totals = c.sum(axis=1)
            rates = totals / (np.diff(EDGES) * .0001 * len(idx))
            check(totals.tolist() == [x["spike_count"] for x in rows] and
                  sha(idx.astype("<i8").tobytes()) == summary["cohort_index_sha256"][cohort], "cohort counts and identity " + name + cohort)
            check(np.allclose(rates, [x["mean_cell_rate_hz"] for x in rows], rtol=1e-14, atol=1e-14), "rate normalization " + name + cohort)
            cell_rates = c / (np.diff(EDGES)[:, None] * .0001)
            cm[cohort] = dict(n=len(idx), counts=totals.tolist(), mean_rates_hz=rates.tolist(),
                active_cells=(c > 0).sum(axis=1).tolist(),
                all_cell_rate_quantiles_hz=np.quantile(cell_rates, [0, .5, .9, .99, 1], axis=1).T.tolist(),
                active_cell_median_rate_hz=[float(np.median(v[v > 0])) if np.any(v > 0) else None for v in cell_rates])
        phase_min = np.full(3, np.inf); phase_max = np.full(3, -np.inf)
        below = np.zeros(3, dtype=np.int64); nonfinite = below.copy(); invalid = np.zeros(2, dtype=np.int64)
        solver_max = np.zeros(4); candidates = np.zeros(7, dtype=np.int64); applied = candidates.copy()
        refs = 0; telemetry_cohort_counts = {c: np.zeros(7, dtype=np.int64) for c in cohorts}
        for ci in range(600):
            paths = [directory / f"chunk-{ci:04d}{suffix}" for suffix in [".json", ".npz"]]
            buffers = []
            for path in paths:
                b = path.read_bytes(); rel = str(path.relative_to(ROOT)); actual = dict(path=rel, bytes=len(b), sha256=sha(b))
                check(actual == artifact_map[rel], "chunk artifact integrity " + rel)
                saved_digest.update((rel + "\0" + actual["sha256"] + "\n").encode()); saved_files += 1
                buffers.append(b)
            nodes = mapping(json.loads(buffers[0])["tree"])
            check(nodes["start_tick"]["value"] == ci * 50 and nodes["end_tick"]["value"] == (ci+1)*50, "chunk coverage")
            per_tick = mapping(nodes["per_tick"])
            telem = mapping(nodes["panel_telemetry"])
            w = int(np.searchsorted(EDGES[1:], ci * 50, side="right"))
            with np.load(io.BytesIO(buffers[1]), allow_pickle=False) as z:
                phase_min = np.minimum(phase_min, array(per_tick["phase_min_mv"], z).min(axis=0))
                phase_max = np.maximum(phase_max, array(per_tick["phase_max_mv"], z).max(axis=0))
                below += array(per_tick["phase_below_reversal_count"], z).sum(axis=0)
                nonfinite += array(per_tick["phase_nonfinite_count"], z).sum(axis=0)
                invalid += array(per_tick["state_invalid_count"], z).sum(axis=0)
                solver_max = np.maximum(solver_max, array(per_tick["solver"], z).max(axis=0))
                candidates[w] += array(nodes["candidate"], z).sum()
                applied[w] += array(nodes["applied"], z).sum()
            for cohort, node in mapping(telem["cohort_spikes"]).items():
                telemetry_cohort_counts[cohort][w] += node["value"]
            refs += len(nodes["panel_reference_checks"]["items"])
        check(int(candidates.sum()) == tr["candidate_count"] and int(applied.sum()) == tr["applied_count"] and
              not candidates[4:].any() and not applied[4:].any(), "external counts and withdrawal " + name)
        check(refs == tr["reference_intervals"] and not nonfinite.any() and not invalid.any(), "references and finite telemetry " + name)
        check(all(v.tolist() == cm[c]["counts"] for c, v in telemetry_cohort_counts.items()), "chunk counts match independently audited totals " + name)
        if spec["arm"].startswith("H"):
            check(not below.any() and min(phase_min) >= -75 - 1e-10, "reported H bound " + name)
        trials.append(dict(spec=spec, review=record(rp), review_checks=review["check_count"],
            spikes=tr["spike_count"], candidates_by_window=candidates.tolist(), applied_by_window=applied.tolist(),
            reference_intervals=refs, threshold_ambiguities=tr["reference_threshold_ambiguities"],
            independent_reference_summary=review.get("statistics"), cohorts=cm,
            producer_telemetry_reduction=dict(phase_min_mv=phase_min.tolist(), phase_max_mv=phase_max.tolist(),
                below_reversal_cell_ticks_by_phase=below.tolist(), nonfinite_cell_ticks_by_phase=nonfinite.tolist(),
                invalid_state_cell_ticks=invalid.tolist(), solver_max=solver_max.tolist()),
            wall_seconds=tr["wall_seconds"], timing=tr["timing"], resources=tt["resources"]))
    lookup = {(t["spec"]["arm"], t["spec"]["seed"], t["spec"]["condition"]): t for t in trials}
    stimulus = []
    factorial = []
    factors = {"H0_minus_C0": {"H0":1,"C0":-1}, "H1_minus_C1": {"H1":1,"C1":-1},
               "C1_minus_C0": {"C1":1,"C0":-1}, "H1_minus_H0": {"H1":1,"H0":-1},
               "interaction": {"H1":1,"C1":-1,"H0":-1,"C0":1}}
    for seed in plan["seeds"]:
        for cohort in cohorts:
            for arm in ARMS:
                rows = {c: lookup[arm, seed, c]["cohorts"][cohort] for c in plan["condition_order"]}
                ea = np.array(rows["ethyl_acetate"]["mean_rates_hz"])
                ia = np.array(rows["isoamyl_acetate"]["mean_rates_hz"])
                base = np.array(rows["constant_baseline"]["mean_rates_hz"])
                stimulus.append(dict(arm=arm, seed=seed, cohort=cohort,
                    EA_minus_constant_hz=(ea-base).tolist(), IA_minus_constant_hz=(ia-base).tolist(),
                    EA_minus_IA_hz=(ea-ia).tolist(),
                    pulse_minus_own_baseline_hz={c:r["mean_rates_hz"][2]-r["mean_rates_hz"][1] for c,r in rows.items()}))
            for condition in plan["condition_order"]:
                rates = {a: np.array(lookup[a,seed,condition]["cohorts"][cohort]["mean_rates_hz"]) for a in ARMS}
                factorial.append(dict(seed=seed, cohort=cohort, condition=condition,
                    effects_hz={f:sum(k*rates[a] for a,k in coeff.items()).tolist() for f,coeff in factors.items()}))
    # Independently recompute every producer contrast from explicit operands.
    names = result["trials"][0]["summary"]["window_names"]
    for row in result["contrasts"]["rows"]:
        vals = []; active = []
        for op in row["operands"]:
            c = lookup[op["arm"], op["seed"], op["condition"]]["cohorts"][row["cohort"]]
            w = names.index(op["window"])
            vals.append(op["coefficient"] * c["mean_rates_hz"][w])
            active.append(op["coefficient"] * c["active_cells"][w]/c["n"])
        check(row["complete"] and not row["unavailable"] and
              abs(sum(vals)-row["difference_hz_per_cell"]) < 1e-10 and
              abs(sum(active)-row["difference_active_fraction"]) < 1e-12, "producer contrast arithmetic")
    out.update(trials=trials, stimulus_contrasts=stimulus, factorial_effects=factorial,
        factorial_coefficients=factors, independently_reviewed_trials=60, component_checks=component_checks,
        producer_contrasts_recomputed=len(result["contrasts"]["rows"]),
        saved_chunk_files_reduced=saved_files, saved_chunk_path_hash_digest=saved_digest.hexdigest(),
        terminal_resources=terminal["resources"], started_utc=result["started_utc"], finished_utc=terminal["finished_utc"])
    record(Path(__file__))
    check(all(sha((ROOT/p).read_bytes()) == v["sha256"] for p,v in pins.items()), "aggregate inputs unchanged")
    out["passed"] = True


def main():
    if OUT.exists():
        raise FileExistsError("Preserve the first aggregate execution")
    out = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), passed=False,
        window_edges_ticks=EDGES.tolist(), dt_s=.0001, quantiles=[0,.5,.9,.99,1],
        phases=["prethreshold","postexternal","postreset"],
        solver_columns=["inverse_residual_max","tail_bound_max_mv","h_max_before","stiffness_max_before"],
        methods="Counts and cohort metrics certified by existing independent raw-spike readers; terminal checkpoint distributions, chunk scalar telemetry and exact paired contrast arithmetic reduced separately here. No neural run, producer helper import, fit or gain change.",
        limits=["Global phase extrema and below-bound cell-ticks are retained producer telemetry, not independently reconstructed all-cell trajectories.",
                "H reference audits independently integrate the saved selected intervals, not every global interval or every selected48 interval.",
                "Three simulation RNG seeds are paired technical inputs, not biological replicates; effects are descriptive and include only three simulated seconds.",
                "Window means, rate quantiles and persistent finite activity do not establish indefinitely stable or uncontrolled activity, measured physiology or natural odor behavior.",
                "Motor cohorts are fixed neural readouts, not measured body movements. No Eon body integration or H1 promotion."])
    try:
        run(out)
    except Exception as exc:
        out["error"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    out.update(check_count=checks, input_receipts=pins)
    with OUT.open("x") as f:
        json.dump(out,f,indent=2,allow_nan=False); f.write("\n")
    print(json.dumps(dict(passed=out["passed"], checks=checks, output=str(OUT), sha256=sha(OUT.read_bytes()), error=out.get("error"))))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
