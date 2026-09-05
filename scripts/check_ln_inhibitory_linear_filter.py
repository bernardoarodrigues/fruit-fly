#!/usr/bin/env python3
"""Frozen bounds for a descriptive 5 ms filter of published rate ink.

No fitted input trace, gain, physiological conductance, or neural simulation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal as D, localcontext
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback
import warnings

import numpy as np
import scipy
from scipy.integrate import IntegrationWarning, quad

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "validation/ln-inhibitory-linear-filter"
SOURCE_BINS = ROOT / "data/raw/ln-inhibitory-transfer/phase2/ink-bins.json"
SOURCE_RESULTS = ROOT / "validation/ln-inhibitory-transfer-phase2-results.json"
TAU, T0 = D("0.005"), D("-0.197")
EARLY, LATE = (D("0.05"), D("0.15")), (D("0.25"), D("0.35"))
WIDTH = D("0.1")
GUARD = D("1e-10")


def now():
    return datetime.now(timezone.utc).isoformat()


def receipt(path):
    p = Path(path)
    return {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def write(path, data):
    with Path(path).open("x") as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write("\n")


def parse(path):
    return json.loads(Path(path).read_text(), parse_float=D)


def prepare():
    inputs = [SOURCE_BINS, SOURCE_RESULTS, ROOT / "validation/ln-inhibitory-transfer-phase2-plan.json",
              ROOT / "validation/ln-inhibitory-transfer-phase2-validation.json",
              ROOT / "docs/ln-inhibitory-linear-filter-design.md", Path(__file__).resolve()]
    plan = {"schema": 1, "frozen_utc": now(), "inputs": [receipt(p) for p in inputs],
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__},
        "tau_s": "0.005", "t0_s": "-0.197", "initial_state": "unknown, finite, nonnegative; no upper bound",
        "gain": "fixed positive, unspecified; never fitted or selected", "constant_observation_offset": "cancels in the difference",
        "windows_s": {"baseline": ["-0.15", "-0.05"], "early": ["0.05", "0.15"], "late": ["0.25", "0.35"]},
        "decimal_precisions": [60, 90], "absolute_unit_gain_guard": "1e-10",
        "precision_agreement_absolute_tolerance": "1e-30",
        "quad": {"epsabs": 1e-12, "epsrel": 1e-12, "limit": 100,
                 "normalized_agreement_tolerance": 1e-10, "maximum_normalized_error_estimate": 1e-10},
        "rate_rule": "For every needed 1 ms bin, retain all eight corners of q=20+40*(anchor20-y)/(anchor20-anchor60). Use the original full y-ink and anchor intervals. No baseline clipping, common-anchor fit, midpoint trace or resampling. Independently relaxed per-bin bounds are a conservative superset, not a realizable witness.",
        "kernel_rule": "Analytic window impulse integrals in Decimal, splitting each bin at early/late endpoints and the exact single signed-kernel crossing. Sum positive and negative kernel masses separately and pair each with the correct rate bound. Retain 60/90-digit results and all 90-digit per-bin masses/corners/contributions.",
        "initial_state_rule": "alpha=A_early*(exp(-0.2/tau)-1)<0. Unknown x0>=0 can only decrease the output difference. It is not set to zero observationally and its coefficient is never discarded.",
        "quad_rule": "Crosscheck every analytic sign-constant interval with SciPy quadrature on u in [0,1], normalizing by interval width and maximal endpoint kernel magnitude. Evaluate the integrand independently with piecewise exp/expm1 formulas in local coordinates; use stable offsets around the sign crossing. Report normalized comparisons and corresponding raw integral errors.",
        "manufactured_cases": ["zero source with arbitrary nonnegative initial state", "constant source plus its equilibrium initial state", "constant source from zero state retains its small transient", "impulses at -0.1,0.1,0.15,0.3 s via separately integrated window responses", "signed enclosure on disjoint negative/positive kernel intervals, all four constant-corner assignments", "kernel mass identity integral(K)=-alpha and initial-state monotonicity"],
        "decision": "Only if all numerical/coverage checks pass and B_upper+1e-10<0: this displayed-summary mapping is conditionally incompatible with positive F late-minus-early current for every positive gain and nonnegative initial state. Otherwise not excluded, or unresolved on failure. Never infer a match from relaxed bounds.",
        "attempts": "One recorded run; an attempt marker precedes all checks. Failures retain their partial evidence before any reviewed amendment. The same source is evaluated at two frozen precision levels, not two tuned attempts.",
        "limits": ["Displayed E is acausally smoothed over 100 ms; no deconvolution", "E and F are different five/nine-cell cohorts", "Broad NP3056 female LN populations, no exact male targets", "No pA/nS conversion, per-spike gain, receptor rejection, fitted trace, time-constant search, or full-network claim"]}
    write(str(PREFIX) + "-plan.json", plan)
    print(json.dumps(receipt(str(PREFIX) + "-plan.json"), indent=2))


def crossing():
    return EARLY[1] - TAU * (1 + (-(LATE[0] - EARLY[1]) / TAU).exp() *
                             (1 - (-(LATE[1] - LATE[0]) / TAU).exp())).ln()


def a_window(window):
    a, b = window
    return TAU / (b - a) * ((-(a - T0) / TAU).exp() - (-(b - T0) / TAU).exp())


def h_point(window, s):
    a, b = window
    if s >= b:
        return D(0)
    if s < a:
        return ((-(a - s) / TAU).exp() - (-(b - s) / TAU).exp()) / (b - a)
    return (1 - (-(b - s) / TAU).exp()) / (b - a)


def h_integral(window, lo, hi):
    a, b = window
    total = D(0)
    end = min(hi, a)
    if lo < end:
        total += TAU / (b - a) * (((end - a) / TAU).exp() - ((end - b) / TAU).exp()
                                           - ((lo - a) / TAU).exp() + ((lo - b) / TAU).exp())
    start, end = max(lo, a), min(hi, b)
    if start < end:
        total += ((end - start) - TAU * (((end - b) / TAU).exp() - ((start - b) / TAU).exp())) / (b - a)
    return total


def split(lo, hi):
    return sorted({lo, hi, *[p for p in (*EARLY, *LATE, crossing()) if lo < p < hi]})


def signed_masses(lo, hi):
    pieces = []
    points = split(lo, hi)
    for a, b in zip(points, points[1:]):
        mass = h_integral(LATE, a, b) - h_integral(EARLY, a, b)
        sign = -1 if (a + b) / 2 < crossing() else 1
        if mass * sign < 0:
            raise ArithmeticError("Analytic mass has wrong sign")
        pieces.append((a, b, mass))
    return sum((m for _, _, m in pieces if m > 0), D(0)), sum((m for _, _, m in pieces if m < 0), D(0)), pieces


def quad_piece(lo, hi, analytic):
    """Independent quadrature in local normalized coordinates, never raw tiny mass."""
    mid, star = (lo + hi) / 2, crossing()
    d = (hi - lo) / TAU
    if mid < EARLY[0]:
        c = (1 - (-(LATE[0] - EARLY[0]) / TAU).exp()) * (1 - (-WIDTH / TAU).exp()) / WIDTH
        scale = c * ((hi - EARLY[0]) / TAU).exp()
        f = lambda u: -math.exp(float(d) * (u - 1))
    elif mid < EARLY[1]:
        offset = (lo - star) / TAU
        endpoint_values = [((s - star) / TAU).exp() - 1 for s in (lo, hi)]
        norm = max(abs(v) for v in endpoint_values)
        scale = norm / WIDTH
        f = lambda u: math.expm1(float(offset) + float(d) * u) / float(norm)
    elif mid < LATE[0]:
        scale = (1 - (-WIDTH / TAU).exp()) / WIDTH * ((hi - LATE[0]) / TAU).exp()
        f = lambda u: math.exp(float(d) * (u - 1))
    else:
        offset = (lo - LATE[1]) / TAU
        norm = 1 - offset.exp()
        scale = norm / WIDTH
        f = lambda u: -math.expm1(float(offset) + float(d) * u) / float(norm)
    with warnings.catch_warnings():
        warnings.simplefilter("error", IntegrationWarning)
        estimate, error = quad(f, 0., 1., epsabs=1e-12, epsrel=1e-12, limit=100)
    expected = analytic / ((hi - lo) * scale)
    delta = abs(estimate - float(expected))
    return {"lo_s": str(lo), "hi_s": str(hi), "analytic_mass": str(analytic),
        "normalization_width_times_scale": str((hi - lo) * scale),
        "analytic_normalized": str(expected), "quad_normalized": estimate,
        "quad_normalized_error_estimate": error, "normalized_difference": delta,
        "raw_difference_bound_from_normalized": float((hi - lo) * scale) * (delta + error),
        "passed": delta <= 1e-10 and error <= 1e-10}


def manufactured():
    alpha = a_window(LATE) - a_window(EARLY)
    positive, negative, pieces = signed_masses(T0, LATE[1])
    checks = []

    def check(name, passed, **extra):
        checks.append({"name": name, "passed": bool(passed), **extra})

    check("initial-state coefficient strictly negative", alpha < 0, alpha=str(alpha))
    check("initial state monotonicity for 0,1,1e30", 0 > alpha > D("1e30") * alpha)
    check("zero source leaves alpha*x0 only", D(3) * alpha < 0, difference_at_x0_3=str(3 * alpha))
    check("constant-source mass identity", abs(positive + negative + alpha) < D("1e-50"), residual=str(positive + negative + alpha))
    constant = D(17) * (positive + negative)
    check("constant source equilibrium cancellation", abs(constant + D(17) * alpha) < D("1e-49"))
    check("zero-state constant transient not discarded", constant > 0, transient=str(constant))
    interval_defs = [(D("-0.01"), D("0.1"), D(-3), D(2)), (D("0.26"), D("0.35"), D(-1), D(7))]
    lower = upper = D(0); masses = []
    for a, b, lo, hi in interval_defs:
        plus, minus, _ = signed_masses(a, b)
        lower += plus * lo + minus * hi; upper += plus * hi + minus * lo
        masses.append(plus + minus)
    corners = [masses[0] * r0 + masses[1] * r1 for r0 in (D(-3), D(2)) for r1 in (D(-1), D(7))]
    check("manufactured signed rectangle reaches all corner bounds", min(corners) == lower and max(corners) == upper,
          lower=str(lower), upper=str(upper), corners=[str(v) for v in corners])
    reference_checks = [quad_piece(a, b, mass) for a, b, mass in pieces]
    check("manufactured normalized signed-kernel quadrature", all(c["passed"] for c in reference_checks))
    impulses = []
    for s in (D("-0.1"), D("0.1"), D("0.15"), D("0.3")):
        by_window = []
        for window in (EARLY, LATE):
            a, b = window; lo = max(a, s)
            if lo >= b:
                by_window.append({"analytic": "0", "passed": h_point(window, s) == 0}); continue
            scale = ((s - lo) / TAU).exp() / (TAU * (b - a))
            duration = b - lo
            value, error = quad(lambda u: math.exp(-float(duration / TAU) * u), 0, 1,
                                epsabs=1e-12, epsrel=1e-12, limit=100)
            normalized = h_point(window, s) / (duration * scale)
            by_window.append({"analytic": str(h_point(window, s)), "normalized_difference": abs(value - float(normalized)),
                              "quad_error": error, "passed": abs(value - float(normalized)) < 1e-10 and error < 1e-10})
        impulses.append({"source_time_s": str(s), "window_integrals": by_window,
                         "signed_window_weight": str(h_point(LATE, s) - h_point(EARLY, s))})
    check("manufactured impulse responses via independent window quadrature", all(v["passed"] for i in impulses for v in i["window_integrals"]))
    return {"checks": checks, "kernel_quad": reference_checks, "impulses": impulses,
            "passed": all(c["passed"] for c in checks)}


def evaluate(rows, anchors, digits, crosscheck=False):
    with localcontext() as context:
        context.prec = digits
        a20 = anchors["y20_ink_pt"]; a60 = anchors["y60_ink_pt"]
        table, quadrature = [], []
        lower = upper = D(0)
        for row in rows:
            lo, hi = row["time_s"]; y = row["y_ink_enclosure_pt"]
            plus, minus, pieces = signed_masses(lo, hi)
            corners = [{"anchor20_pt": str(a), "anchor60_pt": str(b), "ink_y_pt": str(v),
                        "rate_spikes_per_s": str(D(20) + D(40) * (a - v) / (a - b))}
                       for a in a20 for b in a60 for v in y]
            rates = [D(c["rate_spikes_per_s"]) for c in corners]
            l, u = min(rates), max(rates)
            low, high = plus * l + minus * u, plus * u + minus * l
            lower += low; upper += high
            table.append({"time_s": [str(lo), str(hi)], "ink_y_interval_pt": [str(v) for v in y],
                "all_anchor_ink_corners": corners, "rate_lower": str(l), "rate_upper": str(u),
                "positive_kernel_mass": str(plus), "negative_kernel_mass": str(minus),
                "lower_contribution": str(low), "upper_contribution": str(high)})
            if crosscheck:
                quadrature.extend(quad_piece(a, b, m) for a, b, m in pieces)
        alpha = a_window(LATE) - a_window(EARLY)
        summary = {"decimal_digits": digits, "unit_gain_B_lower": str(lower), "unit_gain_B_upper": str(upper),
            "initial_state_coefficient_alpha": str(alpha), "kernel_sign_crossing_s": str(crossing()),
            "positive_kernel_mass_total": str(sum((D(r["positive_kernel_mass"]) for r in table), D(0))),
            "negative_kernel_mass_total": str(sum((D(r["negative_kernel_mass"]) for r in table), D(0))),
            "guarded_lower": str(lower - GUARD), "guarded_upper": str(upper + GUARD)}
        return summary, table, quadrature


def run():
    plan_path = Path(str(PREFIX) + "-plan.json")
    attempt_path = Path(str(PREFIX) + "-attempt.json")
    output = Path(str(PREFIX) + "-results.json")
    raw_path = Path(str(PREFIX) + "-bounds.json.gz")
    if any(p.exists() for p in (attempt_path, output, raw_path)):
        raise FileExistsError("Preserve the single recorded filter attempt")
    plan = json.loads(plan_path.read_text())
    write(attempt_path, {"started_utc": now(), "plan": receipt(plan_path), "script": receipt(Path(__file__).resolve()),
                         "real_E_bins_evaluated_yet": False, "historical_marker_not_final_status": True})
    result = {"schema": 1, "started_utc": now(), "plan": receipt(plan_path), "attempt": receipt(attempt_path),
              "checks": [], "real_input_evaluated": False, "fit_or_time_constant_search": False}
    raw = {}

    def check(name, passed, **details):
        result["checks"].append({"name": name, "passed": bool(passed), **details})
        if not passed:
            raise ValueError(name)

    try:
        for item in plan["inputs"]:
            check("frozen input: " + item["path"], receipt(ROOT / item["path"]) == item)
        check("runtime versions", plan["runtime"] == {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__})
        manufactured_reports = []
        for precision in (60, 90):
            with localcontext() as context:
                context.prec = precision
                test = manufactured(); test["decimal_digits"] = precision
                manufactured_reports.append(test)
        result["manufactured"] = manufactured_reports
        check("all manufactured cases pass at both precisions", all(t["passed"] for t in manufactured_reports))
        # First real source-bin parsing occurs only after the frozen plan and tests.
        all_rows = parse(SOURCE_BINS)["E_mean"]
        source = parse(SOURCE_RESULTS)
        selected = [r for r in all_rows if r["time_s"][0] >= T0 and r["time_s"][1] <= LATE[1]]
        check("full required prefix coverage", len(selected) == 547 and selected[0]["time_s"][0] == T0
              and selected[-1]["time_s"][1] == LATE[1]
              and all(r["y_ink_enclosure_pt"] is not None and r["time_s"][1] - r["time_s"][0] == D("0.001") for r in selected)
              and all(a["time_s"][1] == b["time_s"][0] for a, b in zip(selected, selected[1:])))
        f_interval = source["signals"]["F_mean"]["differences"]["late_minus_early"]["graphical_interval"]
        check("retained F graphical difference strictly positive", f_interval[0] > 0)
        result["real_input_evaluated"] = True
        summaries, tables = [], []
        for precision in (60, 90):
            summary, table, qc = evaluate(selected, source["calibration"]["E_mean"], precision, crosscheck=precision == 90)
            summaries.append(summary); tables.append(table)
            if precision == 90:
                raw["normalized_quad_checks"] = qc
        raw["precision_summaries"] = summaries
        raw["bins_at_60_digits"] = tables[0]
        raw["bins_at_90_digits"] = tables[1]
        raw["source_coverage"] = {"all_display_bins": len(all_rows), "selected_bins": len(selected),
            "t0_s": str(T0), "last_needed_time_s": str(LATE[1]), "missing_selected_bins": 0,
            "unsupported_display_bins": sum(r["y_ink_enclosure_pt"] is None for r in all_rows)}
        result["precision_summaries"] = summaries
        with localcontext() as context:
            context.prec = 90
            precision_errors = [abs(D(a[key]) - D(b[key])) for a, b in zip(tables[0], tables[1])
                for key in ("rate_lower", "rate_upper", "positive_kernel_mass", "negative_kernel_mass", "lower_contribution", "upper_contribution")]
            precision_errors += [abs(D(summaries[0][key]) - D(summaries[1][key])) for key in
                ("unit_gain_B_lower", "unit_gain_B_upper", "initial_state_coefficient_alpha", "kernel_sign_crossing_s")]
            check("60/90 digit absolute agreement", max(precision_errors) < D("1e-30"), maximum_absolute_difference=str(max(precision_errors)))
            check("all rate anchor corners retained", all(len(r["all_anchor_ink_corners"]) == 8 for t in tables for r in t))
            check("negative baseline lower bounds retained", any(D(r["rate_lower"]) < 0 for r in tables[1] if D(r["time_s"][1]) <= 0))
            qc = raw["normalized_quad_checks"]
            check("all real-bin normalized quadratures pass", all(c["passed"] for c in qc), count=len(qc),
                  maximum_normalized_difference=max(c["normalized_difference"] for c in qc),
                  maximum_quad_error_estimate=max(c["quad_normalized_error_estimate"] for c in qc))
            # Each interval belongs to exactly one source bin. A conservative global
            # bound uses the largest absolute admitted rate for every quadrature error.
            maximum_rate = max(abs(D(v)) for r in tables[1] for v in (r["rate_lower"], r["rate_upper"]))
            propagated_error = float(maximum_rate) * math.fsum(c["raw_difference_bound_from_normalized"] for c in qc)
            check("guard dominates propagated independent integral disagreement", propagated_error < float(GUARD),
                  conservative_unit_gain_error=propagated_error, absolute_guard=str(GUARD))
            alpha = D(summaries[1]["initial_state_coefficient_alpha"])
            mass_residual = D(summaries[1]["positive_kernel_mass_total"]) + D(summaries[1]["negative_kernel_mass_total"]) + alpha
            check("real partition total kernel mass identity", abs(mass_residual) < D("1e-50"), residual=str(mass_residual))
            guarded = D(summaries[1]["guarded_upper"])
            result["decision"] = {"classification": "conditionally_incompatible_displayed_summary_filter" if guarded < 0 else "not_excluded_by_bounds",
                "guarded_upper_unit_gain_scale": str(guarded), "alpha_strictly_negative": alpha < 0,
                "gain": "all fixed G>0, not estimated", "initial_state": "all finite x0>=0, not assigned a measured value",
                "observed_F_late_minus_early_pA": [str(v) for v in f_interval],
                "statement": "A negative guarded B upper bound and alpha<0 exclude a positive output difference for every admitted input, G>0 and x0>=0. This is only the declared mapping of separately recorded displayed means."}
        result["passed"] = True
    except Exception as error:
        result["passed"] = False
        result["failure"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        result["decision"] = {"classification": "unresolved_due_to_retained_failure"}
    if raw:
        encoded = json.dumps(raw, separators=(",", ":"), allow_nan=False).encode()
        with raw_path.open("xb") as f:
            f.write(gzip.compress(encoded, mtime=0))
        result["full_bounds_and_quad_evidence"] = {**receipt(raw_path), "uncompressed_bytes": len(encoded),
             "uncompressed_sha256": hashlib.sha256(encoded).hexdigest()}
    result["completed_utc"] = now()
    result["check_count"] = len(result["checks"])
    result["limits"] = plan["limits"]
    write(output, result)
    print(json.dumps({"passed": result["passed"], "checks": result["check_count"], "decision": result.get("decision"), "failure": result.get("failure"), "results": receipt(output)}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    args = parser.parse_args()
    {"plan": prepare, "run": run}[args.mode]()
