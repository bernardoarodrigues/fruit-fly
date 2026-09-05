#!/usr/bin/env python3
"""Check report numbers against frozen summaries and saved reference arrays."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/inhibitory-recurrent-panel-results.md"
ANALYSIS = ROOT / "validation/inhibitory-recurrent-panel-combined-analysis.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-results-independent-review.json"
EXPECTED = "bb42919231572491e2adbd4adfa67f53c1ce0b87bdd5a8f229628b0797488d29"
checks, inputs = [], {}


def record(path):
    b = path.read_bytes()
    r = {"path": str(path.relative_to(ROOT)), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    inputs[r["path"]] = r
    return r


def read(path):
    record(path)
    return json.loads(path.read_text())


def ck(name, passed):
    checks.append({"name": name, "passed": bool(passed)})
    if not passed:
        raise AssertionError(name)


def number(v, digits=4):
    return f"{v:.{digits}f}".replace("-", "−")


def review(out, visual_sha):
    d = read(ANALYSIS)
    record(REPORT)
    doc = REPORT.read_text()
    ck("frozen combined evidence", inputs[str(ANALYSIS.relative_to(ROOT))]["sha256"] == EXPECTED and d["passed"])
    for value in [d["component_checks"], d["check_count"], d["producer_contrasts_recomputed"], sum(t["spikes"] for t in d["trials"])]:
        ck("reported exact count " + str(value), f"{value:,}" in doc)
    ck("sixty reviews and 36000 reduced chunk pairs", d["independently_reviewed_trials"] == 60 and d["saved_chunk_files_reduced"] == 72000 and "36,000 chunk pairs" in doc)
    arms = ["C0", "C1", "H0", "H1"]
    driven = ["constant_baseline", "ethyl_acetate", "isoamyl_acetate"]
    trial = {(t["spec"]["arm"], t["spec"]["seed"], t["spec"]["condition"]): t for t in d["trials"]}
    expected_keys = {(a, s, c) for a in arms for s in [11, 12, 13] for c in driven + ["no_input", "ethyl_acetate_source_outputs_blocked"]}
    ck("exact 4x5x3 coverage", set(trial) == expected_keys and len(d["trials"]) == 60)
    for arm in arms:
        all_arm = [t for t in d["trials"] if t["spec"]["arm"] == arm]
        active = [t for t in all_arm if t["spec"]["condition"] in driven]
        low = min(min(t["producer_telemetry_reduction"]["phase_min_mv"]) for t in all_arm)
        ranges = []
        for cohort in ["non_source", "first_hop_non_source"]:
            values = [v for t in active for v in t["cohorts"][cohort]["mean_rates_hz"][4:]]
            ranges.append(number(min(values)) + "–" + number(max(values)))
        line = f"| {arm} | {sum(t['spikes'] for t in all_arm):,} | {number(low)} | {ranges[0]} | {ranges[1]} |"
        ck("arm numerical table " + arm, line in doc)
        ratios = [100 * t["cohorts"]["non_source"]["mean_rates_hz"][6] / t["cohorts"]["non_source"]["mean_rates_hz"][3] for t in active]
        ck("withdrawal ratio range " + arm, f"{min(ratios):.2f}–{max(ratios):.2f}% for {arm}" in doc)
        fh_contrasts = [r for r in d["stimulus_contrasts"] if r["arm"] == arm and r["cohort"] == "first_hop_non_source"]
        fh_contrasts.sort(key=lambda r: r["seed"])
        row = f"| {arm} | " + " / ".join(number(r["EA_minus_constant_hz"][2]) for r in fh_contrasts) + " | " + " / ".join(number(r["IA_minus_constant_hz"][2]) for r in fh_contrasts) + " |"
        ck("first hop contrast table " + arm, row in doc and all(r["EA_minus_constant_hz"][2] > r["IA_minus_constant_hz"][2] > 0 for r in fh_contrasts))
        ck("no input and blocked nonsource zero " + arm, all(not any(t["cohorts"]["non_source"]["counts"]) for t in all_arm if t["spec"]["condition"] not in driven))
        ck("all driven off windows positive " + arm, all(v > 0 for t in active for v in t["cohorts"]["non_source"]["counts"][4:]))
        for t in all_arm:
            ck("off inputs and source boundary counts " + t["spec"]["name"], t["candidates_by_window"][4:] == t["applied_by_window"][4:] == [0, 0, 0] and
               t["cohorts"]["source"]["counts"][4:] == ([1, 0, 0] if t["spec"]["seed"] == 12 and t["spec"]["condition"] != "no_input" else [0, 0, 0]))
            ck("forward and escape silent " + t["spec"]["name"], not any(t["cohorts"]["motor:forward"]["counts"]) and not any(t["cohorts"]["motor:escape"]["counts"]))
    ck("feeding group totals", " / ".join(f"{sum(sum(t['cohorts']['motor:feeding']['counts']) for t in d['trials'] if t['spec']['arm'] == a):,}" for a in arms) in doc)
    expected_targets = {("target_13314", "H0", 13, c) for c in driven} | {("target_67052", "H1", 11, c) for c in driven}
    observed_targets = set()
    for t in d["trials"]:
        for target in ["target_13314", "target_67052"]:
            counts = t["cohorts"][target]["counts"]
            if any(counts):
                ck("rare target baseline only " + t["spec"]["name"], counts == [0, 1, 0, 0, 0, 0, 0])
                observed_targets.add((target, t["spec"]["arm"], t["spec"]["seed"], t["spec"]["condition"]))
    ck("exact rare target identities and seeds", observed_targets == expected_targets)
    for arm in ["C0", "H0", "H1"]:
        values = [r["EA_minus_IA_hz"][2] for r in d["stimulus_contrasts"] if r["arm"] == arm and r["cohort"] == "non_source"]
        ck("population EA IA sign varies " + arm, min(values) < 0 < max(values))
    fh = lambda a, s: trial[(a, s, "constant_baseline")]["cohorts"]["first_hop_non_source"]
    ck("H1 active median 434 each seed", [fh("H1", s)["active_cell_median_rate_hz"][6] for s in [11, 12, 13]] == [434] * 3)
    ck("H1 all-cell p90 and maximum", all(fh("H1", s)["all_cell_rate_quantiles_hz"][6][2] == 454 and fh("H1", s)["all_cell_rate_quantiles_hz"][6][4] == 456 for s in [11, 12, 13]))
    ck("other active firsthop medians", [fh("C1", s)["active_cell_median_rate_hz"][6] for s in [11, 12, 13]] == [398] * 3 and
       sorted(fh("C0", s)["active_cell_median_rate_hz"][6] for s in [11, 12, 13]) == [219, 220, 221] and
       sorted(fh("H0", s)["active_cell_median_rate_hz"][6] for s in [11, 12, 13]) == [257, 258, 258])
    fractions = [trial[("H1", s, "constant_baseline")]["cohorts"]["non_source"]["active_cells"][6] / 166664 for s in [11, 12, 13]]
    ck("about 7.3 percent nonsource active", all(abs(v - .073) < .001 for v in fractions))
    ck("finite window refractory count arithmetic", (5000 - 1) // 22 + 1 == 228 and 228 / .5 == 456 and abs(10000 / 22 - 454.5) < .05)
    factors = sorted([r for r in d["factorial_effects"] if r["condition"] == "constant_baseline" and r["cohort"] == "non_source"], key=lambda r: r["seed"])
    for field in ["H0_minus_C0", "H1_minus_C1", "C1_minus_C0", "H1_minus_H0", "interaction"]:
        text = " | ".join(number(r["effects_hz"][field][6]) for r in factors)
        ck("factor table " + field, text in doc)
    ck("handling contrasts larger for stated endpoint", all(min(abs(r["effects_hz"][f][6]) for f in ["C1_minus_C0", "H1_minus_H0"]) >
       max(abs(r["effects_hz"][f][6]) for f in ["H0_minus_C0", "H1_minus_C1"]) for r in factors))
    reference_max = {a: {"production_quad": 0., "ode_quad": 0.} for a in ["H0", "H1"]}
    rows = 0
    for t in d["trials"]:
        if t["spec"]["arm"] not in reference_max:
            continue
        tele = t["producer_telemetry_reduction"]
        ck("reported H bound and finiteness " + t["spec"]["name"], not any(tele["below_reversal_cell_ticks_by_phase"]) and
           not any(tele["nonfinite_cell_ticks_by_phase"]) and not any(tele["invalid_state_cell_ticks"]))
        a = read(ROOT / t["review"]["path"])
        ck("pinned H reader " + t["spec"]["name"], record(ROOT / t["review"]["path"]) == t["review"] and a["passed"])
        rf = a["independent_references"]
        path = ROOT / rf["artifact"]["path"]
        ck("pinned saved references " + t["spec"]["name"], record(path) == rf["artifact"])
        with np.load(path, allow_pickle=False) as z:
            values = z["values"]
        col = {v: i for i, v in enumerate(rf["columns"])}
        pq = np.abs(values[:, col["production_v_mv"]] - values[:, col["independent_quad_v_mv"]])
        oq = np.abs(values[:, col["independent_ode_v_mv"]] - values[:, col["independent_quad_v_mv"]])
        ck("reference row counts and margin " + t["spec"]["name"], len(values) == rf["records"] == t["reference_intervals"] and
           np.all(values[:, col["threshold_margin_mv"]] > np.maximum(pq, oq)) and not values[:, col["timing_unresolved"]].any())
        arm = t["spec"]["arm"]
        reference_max[arm]["production_quad"] = max(reference_max[arm]["production_quad"], float(pq.max()))
        reference_max[arm]["ode_quad"] = max(reference_max[arm]["ode_quad"], float(oq.max()))
        rows += len(values)
    ck("reported total reference rows", rows == 75342 and "75,342" in doc)
    for arm in reference_max:
        expected = f"{reference_max[arm]['production_quad']:.3e}".replace("-", "−")
        ck("reported reference error " + arm, expected in doc)
    worst_ode = max(r["ode_quad"] for r in reference_max.values())
    ck("reported ODE discrepancy and tolerance", f"{worst_ode:.3e}".replace("-", "−") in doc and worst_ode < 2e-8)
    for arm in ["C1", "H1"]:
        maximum = max(t["producer_telemetry_reduction"]["phase_max_mv"][0] for t in d["trials"] if t["spec"]["arm"] == arm)
        ck("positive prethreshold overshoot " + arm, number(maximum) in doc)
    # This records an actual visual inspection supplied by the reviewer, not an image classifier.
    image_link = re.search(r"!\[Full factorial comparison\]\(([^)]+)\)", doc).group(1)
    image_path = (REPORT.parent / image_link).resolve()
    ck("report image equals visually inspected file", record(image_path)["sha256"] == visual_sha)
    for p in ["docs/inhibitory-factorial-design-review.md", "docs/ln-inhibitory-linear-filter-results.md", "docs/inhibitory-promotion-gates.md",
              "validation/inhibitory-recurrent-panel-results-review-visual-v2.json"]:
        record(ROOT / p)
    ck("explicit physiology and promotion limits", all(s in doc for s in ["H1 is not promoted", "Physiological response amplitude and timing remain unvalidated", "three changes remain bundled",
       "not biological replicates", "does not certify every unsaved interval", "not an inferred reversal potential", "not fitted physiological parameters"]))
    ck("fixed source analysis and report unchanged", all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == r["sha256"] for p, r in inputs.items()))
    out.update(passed=True, reviewed_reference_rows=rows, independent_saved_reference_maxima=reference_max,
               visual_qa={"png": record(image_path), "passed": True, "method": "Assistant inspected the actual PNG using view_image; no clipped text or artificial closing drop at 3 s in the corrected figure."})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visual-qa-sha", required=True)
    args = parser.parse_args()
    if OUT.exists():
        raise FileExistsError("Preserve first final report review receipt")
    out = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "scope": "Report number/interpretation and corrected figure review against frozen combined evidence and saved references; no model execution, producer import, fitting or source acquisition.",
           "interpretation_review": ["The two within-handling inhibitory contrasts and their interaction support conditional model attribution; three handling mechanisms remain bundled.",
                                     "Persistence is restricted to the observed 1.5-second off interval; neither indefinite stability nor uncontrolled growth is established.",
                                     "Three numerical seeds are not biological replicates; population ranking and rare target responses remain seed dependent.",
                                     "Engineering reversal and at-rest normalization do not supply measured inhibitory pA/nS or receptor calibration; the earlier 5 ms test concerns a conditional displayed-summary mapping.",
                                     "The finite-window 456 Hz rate is compatible with 22-tick spacing and does not imply a refractory violation."],
           "limits": ["This review checks the report against retained evidence and independently reduces saved scalar references; it does not reconstruct unsaved global trajectories or rerun integrators.",
                      "Automation pause state, Git publication history and broader project completion are operational statements outside this numerical/scientific review."]}
    try:
        review(out, args.visual_qa_sha)
    except Exception as e:
        out["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
    out.update(checks=checks, check_count=len(checks), input_receipts=inputs, script=record(Path(__file__)))
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"passed": out["passed"], "checks": len(checks), "receipt": record(OUT), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
