#!/usr/bin/env python3
"""Independent saved-bin review; no producer import, extraction or parameter search."""
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import traceback

import mpmath as mp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/ln-inhibitory-linear-filter-independent-review.json"
PREFIX = ROOT / "validation/ln-inhibitory-linear-filter"
PINS = {
    "scripts/check_ln_inhibitory_linear_filter.py": "66ecca05fbb32d63029d78a56216ce7deea68f3eb739f35f5fbb08cadadbfeb7",
    "validation/ln-inhibitory-linear-filter-plan.json": "5a06f97accebbe83e47c3f1265db680b480cba24e944cad1fa14cf7e999b4b92",
    "validation/ln-inhibitory-linear-filter-results.json": "ab0be9499bf73e6463194401cd5ac1d050e31aa6398d48311380486e69c0fefa",
    "validation/ln-inhibitory-linear-filter-bounds.json.gz": "6ee2adea5ddad8ee56d9047d410bcd028acca74e5f365fed503978f8a37abfa6",
}
R = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(), "inputs": {}, "checks": [], "errors": [],
     "method": "Independent 100-digit mpmath integration of the pointwise window-response kernel and recomputation of all saved calibration corners/signed interval bounds. No producer functions or extraction are executed.",
     "mpmath_version": mp.__version__, "mpmath_digits": 100, "producer_execution": False, "re_extraction": False,
     "time_constant_search": False, "model_fit": False,
     "limits": [
         "This checks the one frozen 5 ms positive-gain displayed-summary mapping, with unknown finite nonnegative initial filter state. It is not a neural network simulation or a rejection of a biological receptor or recurrent mechanism.",
         "E and F are separate five/nine-cell female LN cohorts, not paired input-output recordings; D repeats F's same current cohort.",
         "E is displayed with 100 ms acausal Hanning smoothing. The calculation treats that displayed curve as mathematical input without deconvolution or equating it to transmitter release.",
         "Ink/anchor/bin envelopes are graphical sensitivity ranges, not SEM, confidence intervals or guaranteed errors of the original recordings. Relaxing common calibration and within-bin structure enlarges the input family.",
         "The 1e-10 guard is numerically cross-checked, not a machine-certified interval-arithmetic proof. The conditional sign margin is many orders larger than numerical discrepancies.",
         "No gain, initial-state value, conductance, pA prediction or alternative time constant is selected. Negative baseline lower bounds are retained; the initial-state extremum at zero is a mathematical bound, not a measured zero baseline."]}


def rec(path):
    path = Path(path); key = str(path.relative_to(ROOT))
    if key not in R["inputs"]:
        data = path.read_bytes()
        R["inputs"][key] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return R["inputs"][key]


def read(path):
    rec(path)
    return json.loads(Path(path).read_text(), parse_float=Decimal)


def ck(name, value, **details):
    R["checks"].append({"name": name, "passed": bool(value), **details})


def m(x):
    return mp.mpf(str(x))


def string(x):
    return mp.nstr(x, 100)


def main():
    mp.mp.dps = 100
    tau, t0 = m(".005"), m("-.197")
    early, late = (m(".05"), m(".15")), (m(".25"), m(".35"))
    plan = read(str(PREFIX) + "-plan.json")
    result = read(str(PREFIX) + "-results.json")
    attempt = read(str(PREFIX) + "-attempt.json")
    for name, expected in PINS.items():
        ck("pin:" + name, rec(ROOT / name)["sha256"] == expected)
    receipts = plan["inputs"] + [result["plan"], result["attempt"], attempt["plan"], attempt["script"], result["full_bounds_and_quad_evidence"]]
    for row in receipts:
        actual = rec(ROOT / row["path"])
        ck("receipt:" + row["path"], actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"])
    ck("one_frozen_completed_attempt", plan["frozen_utc"] < attempt["started_utc"] <= result["started_utc"] < result["completed_utc"] and result["passed"] and result["real_input_evaluated"] and not result["fit_or_time_constant_search"])
    ck("fixed_equation_and_windows", plan["tau_s"] == "0.005" and plan["t0_s"] == "-0.197" and plan["windows_s"]["early"] == ["0.05", "0.15"] and plan["windows_s"]["late"] == ["0.25", "0.35"] and plan["absolute_unit_gain_guard"] == "1e-10")
    decoded = gzip.decompress(Path(str(PREFIX) + "-bounds.json.gz").read_bytes())
    ck("decoded_bounds_receipt", hashlib.sha256(decoded).hexdigest() == result["full_bounds_and_quad_evidence"]["uncompressed_sha256"] and len(decoded) == result["full_bounds_and_quad_evidence"]["uncompressed_bytes"])
    raw = json.loads(decoded, parse_float=Decimal)
    source = read(ROOT / "data/raw/ln-inhibitory-transfer/phase2/ink-bins.json")["E_mean"]
    source_result = read(ROOT / "validation/ln-inhibitory-transfer-phase2-results.json")
    selected = [r for r in source if m(r["time_s"][0]) >= t0 and m(r["time_s"][1]) <= late[1]]
    anchors = source_result["calibration"]["E_mean"]
    a20, a60 = list(map(m, anchors["y20_ink_pt"])), list(map(m, anchors["y60_ink_pt"]))
    ck("547_contiguous_supported_bins", len(selected) == 547 and m(selected[0]["time_s"][0]) == t0 and m(selected[-1]["time_s"][1]) == late[1] and all(r["y_ink_enclosure_pt"] is not None and abs(m(r["time_s"][1]) - m(r["time_s"][0]) - m(".001")) < m("1e-99") for r in selected) and all(a["time_s"][1] == b["time_s"][0] for a, b in zip(selected, selected[1:])))
    ck("positive_calibration_denominator", min(a20) > max(a60))

    # Independent pointwise window impulse response; integrate this function
    # directly, rather than reusing the producer's analytic bin antiderivatives.
    def window_response(window, s):
        a, b = window
        if s >= b:
            return mp.mpf(0)
        if s < a:
            return mp.exp((s-a)/tau) * (-mp.expm1(-(b-a)/tau)) / (b-a)
        return -mp.expm1((s-b)/tau) / (b-a)

    def kernel(s):
        return window_response(late, s) - window_response(early, s)

    star = mp.findroot(kernel, (m(".149"), m(".15")))
    initial_window = lambda w: tau / (w[1]-w[0]) * mp.exp((t0-w[0])/tau) * (-mp.expm1(-(w[1]-w[0])/tau))
    alpha = initial_window(late) - initial_window(early)
    ck("initial_coefficient_sign_and_shift_identity", alpha < 0 and abs(alpha - initial_window(early) * mp.expm1(-m(".2")/tau)) < m("1e-99"))
    ck("unique_crossing_location_and_signs", early[0] < star < early[1] and kernel(t0) < 0 and kernel((early[0]+star)/2) < 0 and kernel((star+early[1])/2) > 0 and kernel((early[1]+late[0])/2) > 0 and kernel((late[0]+late[1])/2) > 0 and kernel(late[1]) == 0)
    summaries = raw["precision_summaries"]
    ck("summaries_match_result", summaries == result["precision_summaries"])
    ck("saved_alpha_and_crossing", abs(alpha-m(summaries[1]["initial_state_coefficient_alpha"])) < m("1e-85") and abs(star-m(summaries[1]["kernel_sign_crossing_s"])) < m("1e-85"))

    table = raw["bins_at_90_digits"]
    ck("both_precision_tables_complete", len(table) == len(raw["bins_at_60_digits"]) == 547)
    totals = [mp.mpf(0), mp.mpf(0)]; saved_totals = [mp.mpf(0), mp.mpf(0)]
    mass_totals = [mp.mpf(0), mp.mpf(0)]
    max_corner = max_mass = max_contribution = mp.mpf(0)
    corners_ok = source_ok = signs_ok = True
    negative_pre_zero = split_bins = pieces_count = 0
    for src, row in zip(selected, table):
        lo, hi = map(m, row["time_s"])
        source_ok &= list(map(m, src["time_s"])) == [lo, hi] and list(map(m, src["y_ink_enclosure_pt"])) == list(map(m, row["ink_y_interval_pt"]))
        expected_corners = list(itertools.product(a20, a60, map(m, src["y_ink_enclosure_pt"])))
        corners = []
        corners_ok &= len(row["all_anchor_ink_corners"]) == 8
        for (a, b, y), saved in zip(expected_corners, row["all_anchor_ink_corners"]):
            value = (60*a - 20*b - 40*y) / (a-b)
            corners.append(value)
            corners_ok &= [a,b,y] == [m(saved[k]) for k in ("anchor20_pt", "anchor60_pt", "ink_y_pt")]
            max_corner = max(max_corner, abs(value-m(saved["rate_spikes_per_s"])))
        lower, upper = min(corners), max(corners)
        max_corner = max(max_corner, abs(lower-m(row["rate_lower"])), abs(upper-m(row["rate_upper"])))
        if hi <= 0 and lower < 0:
            negative_pre_zero += 1
        points = sorted({lo, hi, *[p for p in (*early, *late, star) if lo < p < hi]})
        plus = minus = mp.mpf(0)
        for a,b in zip(points, points[1:]):
            mass = mp.quad(kernel, [a,b], method="gauss-legendre")
            signs_ok &= mass * kernel((a+b)/2) >= 0
            if mass > 0:
                plus += mass
            else:
                minus += mass
            pieces_count += 1
        split_bins += int(plus > 0 and minus < 0)
        max_mass = max(max_mass, abs(plus-m(row["positive_kernel_mass"])), abs(minus-m(row["negative_kernel_mass"])))
        low, high = plus*lower + minus*upper, plus*upper + minus*lower
        max_contribution = max(max_contribution, abs(low-m(row["lower_contribution"])), abs(high-m(row["upper_contribution"])))
        totals[0] += low; totals[1] += high
        saved_totals[0] += m(row["lower_contribution"]); saved_totals[1] += m(row["upper_contribution"])
        mass_totals[0] += plus; mass_totals[1] += minus
    ck("every_bin_identity_and_all8_corners", source_ok and corners_ok and max_corner < m("1e-85"), maximum_error=string(max_corner))
    ck("all_signed_kernel_integrals_independent", signs_ok and pieces_count == 548 and split_bins == 1 and max_mass < m("1e-85"), intervals=pieces_count, mixed_sign_bins=split_bins, maximum_error=string(max_mass))
    ck("every_signed_corner_contribution", max_contribution < m("1e-85"), maximum_error=string(max_contribution))
    ck("baseline_negative_enclosures_retained", negative_pre_zero > 0, bins_ending_at_or_before_zero_with_negative_lower=negative_pre_zero)
    ck("global_bound_sums", all(abs(totals[j]-m(summaries[1][k])) < m("1e-84") and abs(saved_totals[j]-m(summaries[1][k])) < m("1e-84") for j,k in enumerate(("unit_gain_B_lower", "unit_gain_B_upper"))))
    ck("integrated_kernel_mass_identity", abs(sum(mass_totals)+alpha) < m("1e-90"), residual=string(sum(mass_totals)+alpha))
    ck("initial_state_and_constant_equilibrium", alpha < 0 and sum(mass_totals) > 0 and abs(17*(sum(mass_totals)+alpha)) < m("1e-89"))
    guard = m(plan["absolute_unit_gain_guard"])
    ck("guarded_bound_arithmetic_and_negative_upper", abs(totals[0]-guard-m(summaries[1]["guarded_lower"])) < m("1e-84") and abs(totals[1]+guard-m(summaries[1]["guarded_upper"])) < m("1e-84") and totals[1]+guard < 0)
    qrows = raw["normalized_quad_checks"]
    q_arithmetic = all(abs(abs(float(q["quad_normalized"])-float(q["analytic_normalized"]))-float(q["normalized_difference"])) <= 1e-30 and math.isclose(float(q["normalization_width_times_scale"])*(float(q["normalized_difference"])+float(q["quad_normalized_error_estimate"])), float(q["raw_difference_bound_from_normalized"]), rel_tol=2e-15, abs_tol=1e-95) for q in qrows)
    maximum_rate = max(abs(m(row[k])) for row in table for k in ("rate_lower", "rate_upper"))
    propagated = float(maximum_rate)*math.fsum(float(q["raw_difference_bound_from_normalized"]) for q in qrows)
    saved_error = next(c["conservative_unit_gain_error"] for c in result["checks"] if c["name"] == "guard dominates propagated independent integral disagreement")
    ck("saved_quadrature_error_arithmetic_and_guard", len(qrows) == 548 and q_arithmetic and all(q["passed"] for q in qrows) and propagated == float(saved_error) and propagated < float(guard))
    precision_error = max(abs(m(a[k])-m(b[k])) for a,b in zip(raw["bins_at_60_digits"],table) for k in ("rate_lower", "rate_upper", "positive_kernel_mass", "negative_kernel_mass", "lower_contribution", "upper_contribution"))
    ck("60_90_digit_saved_agreement", precision_error < m("1e-30"), maximum_bin_difference=string(precision_error))
    impulse_error = mp.mpf(0)
    for manufactured in result["manufactured"]:
        tolerance = m("1e-55") if manufactured["decimal_digits"] == 60 else m("1e-85")
        for impulse in manufactured["impulses"]:
            s = m(impulse["source_time_s"])
            errors = [abs(kernel(s)-m(impulse["signed_window_weight"]))]
            errors += [abs(window_response(w,s)-m(v["analytic"])) for w,v in zip((early,late),impulse["window_integrals"])]
            impulse_error = max(impulse_error,*errors)
            ck(f"manufactured_impulse:{manufactured['decimal_digits']}:{s}", max(errors) < tolerance)
    ck("reported_numerical_checks_pass", all(c["passed"] for c in result["checks"]) and all(t["passed"] and all(c["passed"] for c in t["checks"]) for t in result["manufactured"]))
    observed = source_result["signals"]["F_mean"]["differences"]["late_minus_early"]["graphical_interval"]
    ck("conditional_decision_matches_inequalities", m(observed[0]) > 0 and alpha < 0 and totals[1]+guard < 0 and result["decision"]["classification"] == "conditionally_incompatible_displayed_summary_filter")
    R["independent_summary"] = {"B_lower": string(totals[0]), "B_upper": string(totals[1]), "guarded_lower": string(totals[0]-guard), "guarded_upper": string(totals[1]+guard),
        "alpha": string(alpha), "kernel_zero_s": string(star), "positive_kernel_mass": string(mass_totals[0]), "negative_kernel_mass": string(mass_totals[1]),
        "selected_bins": 547, "signed_intervals": pieces_count, "maximum_kernel_mass_difference": string(max_mass),
        "propagated_reported_quadrature_error": propagated, "F_displayed_difference_pA": list(map(str,observed)),
        "statement": "For this input family, fixed tau=.005s, every G>0 and finite x0>=0, alpha*x0+G*B is strictly negative. This conflicts only with the declared direct mapping to the separately recorded positive F displayed change."}
    ck("input_bytes_unchanged", all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == info["sha256"] for p,info in R["inputs"].items()))


if __name__ == "__main__":
    if OUT.exists():
        raise FileExistsError("Preserve prior independent review")
    rec(Path(__file__).resolve())
    try:
        main()
    except Exception as exc:
        R["errors"].append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    R["completed_utc"] = datetime.now(timezone.utc).isoformat()
    R["check_count"] = len(R["checks"])
    R["passed"] = not R["errors"] and bool(R["checks"]) and all(c["passed"] for c in R["checks"])
    OUT.write_text(json.dumps(R, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"passed": R["passed"], "checks": R["check_count"], "failed": [c["name"] for c in R["checks"] if not c["passed"]], "errors": R["errors"]}), flush=True)
    raise SystemExit(0 if R["passed"] else 1)
