#!/usr/bin/env python3
"""Independent saved-data review; never imports or executes either producer.

All local recurrences condition on saved preceding states, never on newly
generated states. H checks integrate only the archived selected reference
intervals (plus the tiny saved controls), using a different time-domain formula.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import traceback

import numpy as np
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/inhibitory-factorial-independent-review.json"
DATA = ROOT / "validation/inhibitory-factorial"
PLAN = ROOT / "validation/inhibitory-factorial-plan.json"
EXPECTED_PLAN = "add6680e275f4540a3f21ff2d9422313a918fc63ca29bc5dbc59b4501cb1e9fc"
CONDITIONS = ("locomotor_feedback", "locomotor_sensory_block", "sensory_only")
ARMS = ("C0", "C1", "H0", "H1")
TARGETS = (67052, 13314)
N = 120000
A, B = float(np.exp(-.1 / 20.)), float(np.exp(-.1 / 5.))
C = 5. / 15. * (A - B)
INITIAL_LAST = -(2**60)
NAMES = ("state", "pre_threshold_voltage_mv", "available_before_step", "delivery_eligible",
         "fired", "last_spike_tick", "diagnostics", "accepted_positive_negative_jump_mv",
         "event_disposition", "edge_disposition_counts", "solver_failure_tick_target")
R = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
     "method": "Independent vectorized saved-state conditional arithmetic and direct time-domain H quadrature; no producer imports, recurrent simulation, or two-cell replay",
     "independence": "Reviewer previously authored the original negative-voltage replay and source-reviewed this driver; did not author the factorial driver or interval solver. Baseline parity is a cross-artifact check, not independent biological validation.",
     "checks": [], "inputs": {}, "trials": [], "controls": [], "errors": [],
     "full_graph_rerun": False, "replay_rerun": False,
     "limits": [
         "One original seed, three conditional source histories, two selected cells. Altered target outputs never feed back into the sources; self/cross-target original spikes remain exogenous.",
         "All C local voltage transitions and all arms' synaptic/reset/event transitions are independently checked. H voltage integration is independently checked only at the 1488 archived reference intervals plus the saved mixed controls, not every H interval.",
         "Stored 32/64 absolute differences, residual maxima, inverse iteration counts and subdivision errors lack their raw internal solver operands. Their finite bounds and summary arithmetic can be checked; every internal solver computation cannot be reconstructed from this archive.",
         "No-input, excitation-only and moderate single-impulse controls have reported booleans but no separate retained raw trajectories. They are source-inspected reported results; four mixed controls and the expected invalid prefix do retain arrays.",
         "The fixed source mask matches design and full final checkpoints. Its constancy throughout the original source runs relies additionally on the prior frozen journal/input audits, not per-interval full masks in these replay archives.",
         "Passing numerical/integrity checks does not establish physiological accuracy, a measured inhibitory reversal potential for these cells, behavior, generality, or grounds for default promotion. H lower bound is an engineering prior."]}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path):
    path = Path(path)
    key = str(path.relative_to(ROOT))
    if key not in R["inputs"]:
        R["inputs"][key] = {"sha256": digest(path), "bytes": path.stat().st_size}
    return R["inputs"][key]


def check(name, value, **details):
    R["checks"].append({"name": name, "pass": bool(value), **details})


def same(name, actual, expected):
    ok = actual.shape == expected.shape and actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes()
    detail = {}
    if actual.shape == expected.shape and actual.dtype.kind == "f" and np.isfinite(actual).all() and np.isfinite(expected).all():
        detail["max_absolute_difference"] = float(np.max(np.abs(actual - expected))) if actual.size else 0.
    check(name, ok, **detail)


def load(path):
    record(path)
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def json_read(path):
    record(path)
    return json.loads(Path(path).read_text())


def time_reference(v, p, h):
    # y=v-E_I, A(t)=integral_0^t (1+h*exp(-u/5))/20 du.
    # y(dt)=exp(-A(dt))*y(0)+integral_0^dt exp(-(A(dt)-A(u)))
    #                                  *(23+p*exp(-u/5))/20 du.
    # Direct time quadrature needs neither attenuation inversion nor GL nodes.
    def attenuation(t):
        return t / 20. - h * .25 * np.expm1(-t / 5.)
    end = attenuation(.1)
    integral, estimate = quad(lambda t: np.exp(attenuation(t) - end) *
                              (23. + p * np.exp(-t / 5.)) / 20.,
                              0., .1, epsabs=1e-11, epsrel=1e-13)
    return float(-75. + np.exp(-end) * (v + 75.) + integral), float(estimate)


def inspect_trace(label, arm, d, ticks, edges, weights, edge_targets, blocked, n):
    hybrid, package = arm[0] == "H", int(arm[1])
    spec = {
        "state": ((n + 1, 2, 3), "float64"), "pre_threshold_voltage_mv": ((n, 2), "float64"),
        "available_before_step": ((n, 2), "bool"), "delivery_eligible": ((n, 2), "bool"),
        "fired": ((n, 2), "bool"), "last_spike_tick": ((n + 1, 2), "int64"),
        "diagnostics": ((n, 2, 6), "float64"), "accepted_positive_negative_jump_mv": ((n, 2, 2), "float64"),
        "event_disposition": ((len(ticks),), "uint8"), "edge_disposition_counts": ((len(weights), 4), "int64"),
        "solver_failure_tick_target": ((2,), "int64")}
    check(label + ":array_schema", all(k in d and d[k].shape == shape and str(d[k].dtype) == dtype for k, (shape, dtype) in spec.items()))
    check(label + ":finite", all(np.isfinite(d[k]).all() for k in NAMES))
    s, pre, fired = d["state"], d["pre_threshold_voltage_mv"], d["fired"]
    initial = np.zeros((2, 3)); initial[:, 0] = -52.
    same(label + ":initial_state", s[0], initial)
    last = np.maximum.accumulate(np.where(fired, np.arange(n)[:, None], INITIAL_LAST), axis=0)
    expected_last = np.vstack((np.full((1, 2), INITIAL_LAST, dtype=np.int64), last))
    same(label + ":own_last_spike_trace", d["last_spike_tick"], expected_last)
    active = np.arange(n)[:, None] - expected_last[:-1] >= 22
    same(label + ":own_availability", d["available_before_step"], active)
    same(label + ":own_strict_threshold", fired, active & (pre > -45.))
    eligible = np.ones((n, 2), dtype=bool) if package else active & ~fired
    same(label + ":delivery_eligibility", d["delivery_eligible"], eligible)
    same(label + ":post_reset_voltage", s[1:, :, 0], np.where(fired, -52., pre))
    same(label + ":held_refractory_voltage", pre[~active], (-52. * np.ones_like(pre) if package else s[:-1, :, 0])[~active])
    check(label + ":no_solver_failure", np.array_equal(d["solver_failure_tick_target"], [-1, -1]))

    codes = np.full(len(ticks), 3, dtype=np.uint8)
    within = ticks < n
    local = np.flatnonzero(within)
    codes[local] = np.where(blocked[edges[local]], 1, np.where(eligible[ticks[local], edge_targets[edges[local]]], 0, 2))
    same(label + ":every_event_disposition", d["event_disposition"], codes)
    counts = np.bincount(edges.astype(np.int64) * 4 + codes, minlength=len(weights) * 4).reshape(-1, 4)
    same(label + ":every_edge_disposition_count", d["edge_disposition_counts"], counts)
    accepted = codes == 0
    t, j, w = ticks[accepted], edge_targets[edges[accepted]], weights[edges[accepted]]
    jump = np.zeros((n, 2, 2))
    np.add.at(jump, (t, j, (w < 0.).astype(np.int64)), w)
    same(label + ":every_signed_increment", d["accepted_positive_negative_jump_mv"], jump)
    # Each row starts from its own retained preceding state, then decays and
    # receives recorded events in original order; no simulated state feeds onward.
    syn = s[:-1, :, 1:].copy()
    decay = np.ones_like(active) if package else active
    syn[decay] *= B
    pos = w >= 0. if hybrid else np.ones(len(w), dtype=bool)
    np.add.at(syn, (t[pos], j[pos], np.zeros(np.sum(pos), dtype=np.int64)), w[pos])
    if hybrid:
        np.add.at(syn, (t[~pos], j[~pos], np.ones(np.sum(~pos), dtype=np.int64)), -w[~pos] * (1. / 23.))
    if not package:
        syn[fired] = 0.
    same(label + ":every_conditional_synaptic_transition", s[1:, :, 1:], syn)
    diag = d["diagnostics"]
    if not hybrid:
        expected = -52. + (s[:-1, :, 0] + 52.) * A + s[:-1, :, 1] * C + 0. * (1. - A)
        same(label + ":all_C_analytic_voltage_transitions", pre[active], expected[active])
        check(label + ":C_h_and_diagnostics_zero", not np.any(s[:, :, 2]) and not np.any(diag))
    else:
        zero_h = active & (s[:-1, :, 2] == 0.)
        expected = -52. + (s[:-1, :, 0] + 52.) * A + s[:-1, :, 1] * C + 0. * (1. - A)
        same(label + ":H_zero_h_C_analytic_transition", pre[zero_h], expected[zero_h])
        check(label + ":H_nonnegative_and_lower_bound", np.all(s[:, :, 1:] >= 0.) and np.min(s[:, :, 0]) >= -75. - 1e-10 and np.min(pre) >= -75. - 1e-10)
        excess = pre - np.maximum(s[:-1, :, 0], -52. + s[:-1, :, 1])
        same(label + ":H_upper_bound_excess_arithmetic", diag[:, :, 5][active], excess[active])
        check(label + ":H_upper_bound", np.max(excess[active]) <= 1e-10)
        check(label + ":inactive_diagnostics_zero", not np.any(diag[~active]))
        check(label + ":H_stored_32_64_bounds", np.all(diag[:, :, 4] >= 0.) and np.max(diag[:, :, 4]) <= 1e-8)
        check(label + ":H_stored_inverse_bounds", np.all(diag[:, :, 1] >= 0.) and np.all(diag[:, :, 1] <= 1e-13 * (1. + diag[:, :, 3])) and np.all(diag[:, :, 2] == np.floor(diag[:, :, 2])) and np.max(diag[:, :, 2]) <= 48)
        attenuation = .1 / 20. - s[:-1, :, 2] * .25 * np.expm1(-.1 / 5.)
        cutoff = np.minimum(attenuation, np.log(23. + s[:-1, :, 1]) - np.log(1e-13))
        check(label + ":H_cutoff_arithmetic", np.max(np.abs(diag[:, :, 3][active] - cutoff[active])) <= 1e-15)
        tail = np.where(cutoff < attenuation, (23. + s[:-1, :, 1]) * np.exp(-cutoff), 0.)
        check(label + ":H_tail_arithmetic_and_bound", np.max(np.abs(diag[:, :, 0][active] - tail[active])) <= 1e-25 and np.max(diag[:, :, 0]) <= 1.01e-13)
    return {"label": label, "poststate_rows": n + 1, "target_intervals": n * 2,
            "expanded_source_events": len(ticks), "event_counts": np.bincount(codes, minlength=4).tolist(),
            "spike_ticks": [np.flatnonzero(fired[:, j]).tolist() for j in range(2)],
            "minimum_post_voltage_mv": s[:, :, 0].min(axis=0).tolist(),
            "maximum_stored_32_64_difference_mv": float(diag[:, :, 4].max())}


def summarize(d, ticks, edges, edge_targets):
    cells = []
    for j, target in enumerate(TARGETS):
        s, pre = d["state"][:, j], d["pre_threshold_voltage_mv"][:, j]
        spikes = np.flatnonzero(d["fired"][:, j])
        code = d["event_disposition"][edge_targets[edges] == j]
        active = d["available_before_step"][:, j]
        cells.append({"target_id": target, "minimum_voltage_mv": float(s[:, 0].min()),
            "maximum_voltage_mv": float(s[:, 0].max()), "mean_voltage_mv": float(s[1:, 0].mean()),
            "endpoint_voltage_mv": float(s[-1, 0]), "minimum_pre_threshold_mv": float(pre.min()),
            "maximum_pre_threshold_mv": float(pre.max()), "spike_count": len(spikes), "rate_hz": len(spikes) / 12.,
            "first_spike_ms": float(spikes[0] * .1) if len(spikes) else None,
            "last_spike_ms": float(spikes[-1] * .1) if len(spikes) else None,
            "min_signed_or_positive_state_mv": float(s[:, 1].min()), "max_signed_or_positive_state_mv": float(s[:, 1].max()),
            "max_h": float(s[:, 2].max()), "max_stiffness": float((1. + s[:-1, 2].max()) * .1 / 20.),
            "pre_threshold_below_minus75_fraction": float(np.mean(pre < -75. - 1e-10)),
            "closest_threshold_margin_mv": float(np.min(np.abs(pre[active] + 45.))),
            "event_counts": {name: int(np.sum(code == k)) for k, name in enumerate(("accepted", "source_blocked", "target_unavailable", "pending"))},
            "windows": [{"start_ms": lo, "end_ms": hi, "spikes": int(np.sum((spikes >= lo * 10) & (spikes < hi * 10))),
                         "mean_post_voltage_mv": float(s[lo * 10 + 1:hi * 10 + 1, 0].mean())}
                        for lo, hi in ((0, 500), (500, 11000), (11000, 12000))]})
    return cells


def inspect_references(label, d, report):
    expected_keys = []
    for j, target in enumerate(TARGETS):
        active = np.flatnonzero(d["available_before_step"][:, j])
        selection = set(active[active % 1000 == 0].tolist())
        selection.update((int(active[0]), int(active[-1]),
                          int(active[np.argmax(d["state"][active, j, 1])]),
                          int(active[np.argmax(d["state"][active, j, 2])]),
                          int(active[np.argmin(np.abs(d["pre_threshold_voltage_mv"][active, j] + 45.))])))
        expected_keys += [(target, tick) for tick in sorted(selection)]
    refs = report["references"]
    check(label + ":exact_reference_selection", [(r["target_id"], r["tick"]) for r in refs] == expected_keys)
    errors, estimates = [], []
    state_ok = arith_ok = tolerances_ok = True
    for row in refs:
        j, tick = TARGETS.index(row["target_id"]), row["tick"]
        state = d["state"][tick, j]
        production = float(d["pre_threshold_voltage_mv"][tick, j])
        state_ok &= np.array_equal(state, row["preceding_v_p_h"]) and production == row["production_mv"]
        arith_ok &= row["production_quad_error_mv"] == abs(production - row["quad_mv"]) and row["ode_quad_error_mv"] == abs(row["ode_mv"] - row["quad_mv"])
        tolerances_ok &= row["production_quad_error_mv"] <= 1e-8 and row["ode_quad_error_mv"] <= 2e-8 and 0. <= row["quad_error_estimate_mv"] <= 1e-9 and len(row["subdivision_errors_mv"]) == 2 and all(0. <= x <= 1e-8 for x in row["subdivision_errors_mv"]) and row["ode_method"] in ("DOP853", "Radau") and row["ode_nfev"] > 0
        value, estimate = time_reference(*state)
        errors.append(abs(value - production)); estimates.append(estimate)
    check(label + ":references_match_actual_own_input_states", state_ok)
    check(label + ":reference_error_arithmetic", arith_ok)
    check(label + ":all_stored_reference_tolerances", tolerances_ok)
    check(label + ":independent_time_quadrature", max(errors) <= 1e-8 and max(estimates) <= 1e-9,
          intervals=len(errors), max_error_mv=max(errors), max_quadrature_estimate_mv=max(estimates))
    names = ("tail_bound_mv", "inverse_residual", "inverse_iterations", "attenuation_cutoff", "production32_64_error_mv", "upper_bound_excess_mv")
    check(label + ":diagnostic_summary_arithmetic", report["max_diagnostics"] == {name: float(d["diagnostics"][:, :, k].max()) for k, name in enumerate(names)})
    return {"intervals": len(errors), "max_independent_time_quadrature_error_mv": max(errors), "max_quadrature_error_estimate_mv": max(estimates)}


def run():
    plan, results = json_read(PLAN), json_read(DATA / "results.json")
    check("frozen_plan_digest", digest(PLAN) == EXPECTED_PLAN == results["plan_sha256"])
    check("completed_12_trials", results["complete"] and results["passed"] and results["error"] is None and len(results["trials"]) == 12)
    check("declared_targets_histories_arms_clock", plan["targets"] == list(TARGETS) and plan["conditions"] == list(CONDITIONS) and plan["arms"] == list(ARMS) and plan["neural_ticks"] == N)
    for name, meta in {**plan["inputs"], **results["artifacts"]}.items():
        actual = record(ROOT / name)
        check("pinned:" + name, actual == {"sha256": meta["sha256"], "bytes": meta["bytes"]})
    check("producer_reported_gates", all(x["pass"] for x in results["checks"]) and all(t["passed"] and all(x["pass"] for x in t["checks"]) for t in results["trials"]))
    graph = ROOT / "data/processed/malecns_v1"
    arrays = {k: np.load(graph / (k + ".npy"), mmap_mode="r") for k in ("neuron_ids", "indptr", "targets", "weights", "contact_counts", "signs")}
    with (ROOT / "validation/negative-voltage-replay-incoming-edges.csv").open() as f:
        rows = list(csv.DictReader(f))
    sources = np.array([int(r["source_index"]) for r in rows], dtype=np.int32)
    dest = np.array([int(r["target_slot"]) for r in rows], dtype=np.int32)
    edge_index = np.array([int(r["graph_edge_index"]) for r in rows], dtype=np.int64)
    weights = np.array([struct.unpack("<f", bytes.fromhex(r["weight_float32_hex"]))[0] for r in rows])
    target_idx = np.searchsorted(arrays["neuron_ids"], TARGETS)
    check("incoming_inventory_row_identity_unique", all(int(r["row"]) == k for k, r in enumerate(rows)) and len(set(zip(sources.tolist(), dest.tolist()))) == len(rows) == 2695)
    check("incoming_inventory_complete_graph_join", np.array_equal(np.flatnonzero(np.isin(arrays["targets"], target_idx)), np.sort(edge_index)))
    check("incoming_inventory_source_target_ids", all(int(arrays["neuron_ids"][s]) == int(r["source_id"]) and int(r["target_id"]) == TARGETS[j] and int(r["target_index"]) == target_idx[j] and arrays["indptr"][s] <= e < arrays["indptr"][s + 1] and arrays["targets"][e] == target_idx[j] for r, s, j, e in zip(rows, sources, dest, edge_index)))
    same("incoming_exact_float32_weights", weights.astype(np.float32), np.asarray(arrays["weights"][edge_index]))
    check("incoming_contacts_and_model_sign", np.array_equal(arrays["contact_counts"][edge_index], [int(r["contacts"]) for r in rows]) and np.array_equal(arrays["signs"][sources], [int(r["source_model_sign"]) for r in rows]))
    mapping = np.full((len(arrays["neuron_ids"]), 2), -1, dtype=np.int32)
    mapping[sources, dest] = np.arange(len(rows), dtype=np.int32)
    old_results = json_read(ROOT / "validation/negative-voltage-replay-results.json")
    audit = json_read(ROOT / "validation/inhibitory-factorial-input-audit.json")
    check("prior_input_audit_passed", audit["passed"] and all(c["pass"] for c in audit["checks"]))
    cells = {}
    for condition in CONDITIONS:
        base = load(ROOT / f"validation/negative-voltage-replay-{condition}-arrays.npz")
        event = load(DATA / f"{condition}-events.npz")
        raw_source, raw_tick = base["recorded_source_indices"], base["recorded_source_spike_ticks"]
        expanded = mapping[raw_source]
        event_source, event_slot = np.nonzero(expanded >= 0)
        same(condition + ":every_source_event_identity_order", event["recorded_source_event_index"], event_source.astype(np.int32))
        same(condition + ":every_source_edge_order", event["edge_rows"], expanded[event_source, event_slot])
        same(condition + ":every_18_tick_delivery", event["delivery_ticks"], raw_tick[event_source] + np.int32(18))
        ticks, edges = event["delivery_ticks"], event["edge_rows"]
        summary = json_read(ROOT / f"runs/flybody-rolling-loop-3e5ca3ca6c91/{condition}/condition-summary.json")
        checkpoint = load(ROOT / f"runs/flybody-rolling-loop-3e5ca3ca6c91/{condition}/brain-final-or-failure.npz")
        blocked = np.zeros(len(arrays["neuron_ids"]), dtype=bool)
        for group in summary["design"]["outgoing_blocks"]:
            blocked[summary["groups"][group]["indices"]] = True
        same(condition + ":source_mask_design", event["source_blocked"], blocked)
        same(condition + ":source_mask_original_checkpoint", blocked, checkpoint["ablated"])
        check(condition + ":original_target_current_refractory", np.array_equal(checkpoint["current_mv"][target_idx], [0., 0.]) and np.array_equal(checkpoint["refractory_ticks"][target_idx], [22, 22]))
        check(condition + ":prior_no_direct_target_inputs", next(c for c in old_results["conditions"] if c["condition"] == condition)["selected_targets_in_any_input_list"] is False)
        all_spikes, all_dispositions = [], []
        for arm in ARMS:
            label = condition + ":" + arm
            d = load(DATA / f"{condition}-{arm}.npz")
            report = json_read(DATA / f"{condition}-{arm}.json")
            check(label + ":exact_keys", tuple(d) == NAMES)
            check(label + ":archive_digest", report["archive_sha256"] == record(DATA / f"{condition}-{arm}.npz")["sha256"])
            item = inspect_trace(label, arm, d, ticks, edges, weights, dest, blocked[sources], N)
            observed = summarize(d, ticks, edges, dest)
            check(label + ":every_cell_summary_and_window", observed == report["cells"])
            check(label + ":outer_report_consistency", {k: v for k, v in report.items() if k != "references"} == next(t for t in results["trials"] if t["condition"] == condition and t["arm"] == arm))
            cells[condition, arm] = observed
            if arm == "C0":
                for field, expected in ((d["state"][:, :, 0], base["voltage_mv"]), (d["state"][:, :, 1], base["synaptic_mv"]), (d["fired"], base["emitted_spikes_by_tick"]), (d["accepted_positive_negative_jump_mv"], base["accepted_positive_negative_jump_mv_by_tick"]), (ticks[d["event_disposition"] == 0], base["accepted_delivery_ticks"]), (edges[d["event_disposition"] == 0], base["accepted_edge_rows"])):
                    same(label + ":baseline_bitwise:" + str(field.shape), field, expected)
                for j in range(2):
                    same(label + f":original_target{j}_timestamps", np.flatnonzero(d["fired"][:, j]).astype(np.int32), base[f"recorded_target{j}_spike_ticks"])
                same(label + ":checkpoint_voltage", d["state"][-1, :, 0], checkpoint["voltage_mv"][target_idx])
                same(label + ":checkpoint_synaptic", d["state"][-1, :, 1], checkpoint["synaptic_mv"][target_idx])
                same(label + ":checkpoint_last_spike", d["last_spike_tick"][-1], checkpoint["last_spike_tick"][target_idx])
                with (ROOT / f"validation/negative-voltage-replay-{condition}-edge-balance.csv").open() as f:
                    balance = list(csv.DictReader(f))
                counts = np.array([[int(r[k]) for k in ("accepted_events", "source_blocked_events", "target_unavailable_events", "beyond_horizon_events")] for r in balance], dtype=np.int64)
                same(label + ":original_per_edge_dispositions", d["edge_disposition_counts"], counts)
            if arm[0] == "H":
                item["independent_H_references"] = inspect_references(label, d, report)
            all_spikes.append(d["fired"].copy())
            all_dispositions.append(d["event_disposition"].copy())
            R["trials"].append(item)
            print(label, "reviewed", flush=True)
        check(condition + ":all_arms_spike_timestamps_identical", all(np.array_equal(all_spikes[0], v) for v in all_spikes[1:]))
        check(condition + ":same_package_dispositions_identical", np.array_equal(all_dispositions[0], all_dispositions[2]) and np.array_equal(all_dispositions[1], all_dispositions[3]))
    contrasts = []
    for condition in CONDITIONS:
        for j, target in enumerate(TARGETS):
            for metric in ("minimum_voltage_mv", "mean_voltage_mv", "endpoint_voltage_mv", "spike_count"):
                v = {arm: cells[condition, arm][j][metric] for arm in ARMS}
                contrasts.append({"condition": condition, "target_id": target, "metric": metric, "values": v,
                                  "H0-C0": v["H0"] - v["C0"], "H1-C1": v["H1"] - v["C1"],
                                  "C1-C0": v["C1"] - v["C0"], "H1-H0": v["H1"] - v["H0"],
                                  "interaction": (v["H1"] - v["C1"]) - (v["H0"] - v["C0"])})
    check("all_24_factorial_contrasts_exact", results["contrasts"] == contrasts)
    R["contrasts"] = contrasts
    inspect_controls()
    check("all_reviewed_inputs_unchanged_at_end", all(digest(ROOT / path) == meta["sha256"] for path, meta in R["inputs"].items()))


def inspect_controls():
    report = json_read(DATA / "controls.json")
    expected_ticks = np.array([18] + [t for t in (19, 20, 40, 41, 62, 80) for _ in range(4)], dtype=np.int32)
    expected_edges = np.array([0] + [e for _ in range(6) for e in (1, 2, 3, 4)], dtype=np.int32)
    for arm in ARMS:
        label = "control:" + arm
        d = load(DATA / f"control-{arm}.npz")
        check(label + ":input_protocol", np.array_equal(d["event_ticks"], expected_ticks) and np.array_equal(d["event_edges"], expected_edges) and np.array_equal(d["weights"], [1e5, 23., -23., 0., 23.]) and np.array_equal(d["edge_targets"], [0, 0, 0, 0, 1]) and np.array_equal(d["blocked"], [False, False, False, False, True]))
        item = inspect_trace(label, arm, d, d["event_ticks"], d["event_edges"], d["weights"], d["edge_targets"], d["blocked"], 64)
        spikes = np.flatnonzero(d["fired"][:, 0]).tolist()
        check(label + ":exact_expected_spikes", spikes == ([19] if arm[1] == "0" else [19, 41, 63]))
        check(label + ":explicit_release_boundary", np.array_equal(d["available_before_step"][[19, 20, 40, 41], 0], [True, False, False, True]))
        check(label + ":blocked_target_rest", np.all(d["state"][:, 1, 0] == -52.) and not d["fired"][:, 1].any())
        check(label + ":control_report_summary", report["arms"][arm] == {"spike_ticks": spikes, "event_disposition": d["event_disposition"].tolist()})
        if arm[0] == "H":
            errors = [abs(time_reference(*d["state"][tick, j])[0] - d["pre_threshold_voltage_mv"][tick, j]) for tick, j in zip(*np.nonzero(d["available_before_step"]))]
            check(label + ":all_active_intervals_independent_time_quadrature", max(errors) <= 1e-8, intervals=len(errors), max_error_mv=max(errors))
        R["controls"].append(item)
    bad = load(DATA / "control-expected-invalid-input.npz")
    check("expected_invalid:prefix_shapes", bad["state"].shape == (20, 2, 3) and bad["last_spike_tick"].shape == (20, 2) and all(bad[k].shape[0] == 19 for k in ("pre_threshold_voltage_mv", "available_before_step", "delivery_eligible", "fired", "diagnostics", "accepted_positive_negative_jump_mv")))
    check("expected_invalid:failure_tick_target", np.array_equal(bad["solver_failure_tick_target"], [19, 0]))
    initial = np.zeros((20, 2, 3)); initial[:, :, 0] = -52.; initial[19, 0, 1] = np.inf
    same("expected_invalid:retained_exact_input_state", bad["state"], initial)
    check("expected_invalid:no_partial_failed_step", np.all(bad["pre_threshold_voltage_mv"] == -52.) and not bad["fired"].any() and np.all(bad["last_spike_tick"] == INITIAL_LAST) and bad["available_before_step"].all() and bad["delivery_eligible"].all())
    check("expected_invalid:unprocessed_not_pending", np.array_equal(bad["event_disposition"], np.array([0] + [4] * 24, dtype=np.uint8)))
    counts = np.zeros((5, 4), dtype=np.int64); counts[0, 0] = 1
    same("expected_invalid:processed_edge_counts", bad["edge_disposition_counts"], counts)
    jumps = np.zeros((19, 2, 2)); jumps[18, 0, 0] = np.inf
    same("expected_invalid:exact_accepted_increment", bad["accepted_positive_negative_jump_mv"], jumps)
    check("control_report_all_reported_booleans", len(report["checks"]) == 40 and all(c["pass"] for c in report["checks"]))
    R["reported_only_controls"] = [c["name"] for c in report["checks"] if any(x in c["name"] for x in ("no_input_passive", "excitation_only_bitwise", "single_impulse_analytic"))]
    R["expected_invalid_control"] = {"failure_tick": 19, "target_slot": 0, "completed_macro_ticks": 19, "state_rows": 20,
        "accepted_events": 1, "unprocessed_events": 24, "physical_or_recorded_trial_failure": False,
        "meaning": "Deliberate infinite synthetic weight tests solver rejection and complete-prefix retention; its nonfinite input is expected, not a failed recorded-source trial."}


if __name__ == "__main__":
    if OUT.exists():
        raise FileExistsError("Preserve earlier review receipt")
    record(Path(__file__).resolve())
    try:
        run()
    except Exception as exc:
        R["errors"].append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    R["completed_utc"] = datetime.now(timezone.utc).isoformat()
    R["check_count"] = len(R["checks"])
    R["passed"] = not R["errors"] and bool(R["checks"]) and all(c["pass"] for c in R["checks"])
    OUT.write_text(json.dumps(R, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": R["passed"], "checks": R["check_count"], "failed": [c["name"] for c in R["checks"] if not c["pass"]], "errors": R["errors"]}), flush=True)
    raise SystemExit(0 if R["passed"] else 1)
