#!/usr/bin/env python3
"""Frozen four-arm, two-target replay of recorded presynaptic histories.

This is not a recurrent simulation. The caller never regenerates source spikes.
Only isolated experiment outputs are written; production defaults are untouched.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import traceback

import numpy as np
from numba import njit

from inhibitory_factorial_solver import (
    NODES32, WEIGHTS32, NODES64, WEIGHTS64, coefficients,
    hybrid_step, hybrid_reference, ode_reference,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-factorial-plan.json"
OUT = ROOT / "validation/inhibitory-factorial"
GRAPH = ROOT / "data/processed/malecns_v1"
RUN = ROOT / "runs/flybody-rolling-loop-3e5ca3ca6c91"
CONDITIONS = ("locomotor_feedback", "locomotor_sensory_block", "sensory_only")
ARMS = ("C0", "C1", "H0", "H1")
TARGET_IDS = (67052, 13314)
N_TICKS = 120000
# Disposition precedence: pending, blocked, unavailable (package 0), accepted.
ACCEPTED, BLOCKED, UNAVAILABLE, PENDING, UNPROCESSED = 0, 1, 2, 3, 4


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def baseline_path(condition):
    return ROOT / f"validation/negative-voltage-replay-{condition}-arrays.npz"


@njit(cache=True)
def event_inventory(source, stamps, mapping):
    """Expand source order, then target slot 0/1; include all potential edges."""
    ticks = np.empty(len(source) * 2, dtype=np.int32)
    edges = np.empty_like(ticks)
    source_event = np.empty_like(ticks)
    n = 0
    for k in range(len(source)):
        for j in range(2):
            edge = mapping[source[k], j]
            if edge >= 0:
                ticks[n], edges[n], source_event[n] = stamps[k] + 18, edge, k
                n += 1
    return ticks[:n], edges[:n], source_event[:n]


@njit(cache=True)
def replay(n_ticks, hybrid, package, event_ticks, event_edges, edge_targets,
           weights, edge_blocked, a, b, coefficient):
    # state columns: v, signed s (C) or positive p (H), inhibitory h (H only).
    state = np.zeros((n_ticks + 1, 2, 3), dtype=np.float64)
    state[0, :, 0] = -52.
    pre_threshold = np.empty((n_ticks, 2), dtype=np.float64)
    available = np.zeros((n_ticks, 2), dtype=np.bool_)
    delivery_eligible = np.zeros_like(available)
    fired = np.zeros_like(available)
    last_trace = np.full((n_ticks + 1, 2), -(2**60), dtype=np.int64)
    # tail, inverse residual, inverse iterations, cutoff, 32/64 local error,
    # available-step upper-bound excess. Zeros mark nonintegrated/C steps.
    diagnostics = np.zeros((n_ticks, 2, 6), dtype=np.float64)
    jumps = np.zeros((n_ticks, 2, 2), dtype=np.float64)
    disposition = np.full(len(event_ticks), UNPROCESSED, dtype=np.uint8)
    edge_counts = np.zeros((len(weights), 4), dtype=np.int64)
    failure = np.array([-1, -1], dtype=np.int64)  # failing macro tick / target slot
    cursor = 0
    for tick in range(n_ticks):
        state[tick + 1] = state[tick]
        last_trace[tick + 1] = last_trace[tick]
        for j in range(2):
            active = tick - last_trace[tick, j] >= 22
            available[tick, j] = active
            v, s, h = state[tick, j]
            if active:
                if hybrid:
                    try:
                        result = hybrid_step(v, s, h, .1, a, b, coefficient, NODES32, WEIGHTS32)
                        fine = hybrid_step(v, s, h, .1, a, b, coefficient, NODES64, WEIGHTS64)
                    except Exception:
                        failure[0], failure[1] = tick, j
                        # Retain every completed macro tick and the failing input
                        # state. Discard only this partially integrated tick.
                        return (state[:tick + 1], pre_threshold[:tick], available[:tick],
                                delivery_eligible[:tick], fired[:tick], last_trace[:tick + 1],
                                diagnostics[:tick], jumps[:tick], disposition, edge_counts, failure)
                    state[tick + 1, j, 0] = result[0]
                    state[tick + 1, j, 1] = result[1]
                    state[tick + 1, j, 2] = result[2]
                    diagnostics[tick, j, 0] = result[3]
                    diagnostics[tick, j, 1] = result[4]
                    diagnostics[tick, j, 2] = result[5]
                    diagnostics[tick, j, 3] = result[6]
                    diagnostics[tick, j, 4] = abs(result[0] - fine[0])
                    diagnostics[tick, j, 5] = result[0] - max(v, -52. + s)
                else:
                    # Preserve the baseline's exact expression and single signed sum.
                    state[tick + 1, j, 0] = -52. + (v + 52.) * a + s * coefficient + 0. * (1. - a)
                    state[tick + 1, j, 1] = s * b
            elif package == 1:
                state[tick + 1, j, 0] = -52.
                state[tick + 1, j, 1] = s * b
                state[tick + 1, j, 2] = h * b
            pre_threshold[tick, j] = state[tick + 1, j, 0]
            if active and pre_threshold[tick, j] > -45.:
                fired[tick, j] = True
                last_trace[tick + 1, j] = tick
            delivery_eligible[tick, j] = package == 1 or (active and not fired[tick, j])
        while cursor < len(event_ticks) and event_ticks[cursor] == tick:
            edge = event_edges[cursor]
            j = edge_targets[edge]
            if edge_blocked[edge]:
                code = BLOCKED
            elif not delivery_eligible[tick, j]:
                code = UNAVAILABLE
            else:
                code = ACCEPTED
                w = weights[edge]
                if hybrid and w < 0.:
                    state[tick + 1, j, 2] += -w * (1. / 23.)
                else:
                    state[tick + 1, j, 1] += w
                jumps[tick, j, 0 if w >= 0. else 1] += w
            disposition[cursor] = code
            edge_counts[edge, code] += 1
            cursor += 1
        for j in range(2):
            if fired[tick, j]:
                state[tick + 1, j, 0] = -52.
                if package == 0:
                    state[tick + 1, j, 1:] = 0.
    for k in range(cursor, len(event_ticks)):
        disposition[k] = PENDING
        edge_counts[event_edges[k], PENDING] += 1
    return (state, pre_threshold, available, delivery_eligible, fired, last_trace,
            diagnostics, jumps, disposition, edge_counts, failure)


ARRAY_NAMES = ("state", "pre_threshold_voltage_mv", "available_before_step",
               "delivery_eligible", "fired", "last_spike_tick", "diagnostics",
               "accepted_positive_negative_jump_mv", "event_disposition", "edge_disposition_counts", "solver_failure_tick_target")


def prepare():
    if PLAN.exists() or OUT.exists():
        raise FileExistsError("Preserve earlier plan and results")
    for name in ["inhibitory-factorial-solver-results.json", "inhibitory-factorial-input-audit.json"]:
        if not json.loads((ROOT / "validation" / name).read_text())["passed"]:
            raise ValueError("Prerequisite did not pass: " + name)
    paths = [Path(__file__).resolve(), ROOT / "scripts/inhibitory_factorial_solver.py",
             ROOT / "fruitfly/neural.py", ROOT / "docs/inhibitory-factorial-design-review.md",
             ROOT / "docs/inhibitory-factorial-driver-review.md",
             ROOT / "validation/inhibitory-factorial-solver-plan.json",
             ROOT / "validation/inhibitory-factorial-solver-results.json",
             ROOT / "validation/inhibitory-factorial-input-audit.json",
             ROOT / "validation/negative-voltage-replay-plan.json",
             ROOT / "validation/negative-voltage-replay-results.json",
             ROOT / "validation/negative-voltage-replay-independent-review.json",
             ROOT / "validation/negative-voltage-replay-incoming-edges.csv",
             GRAPH / "manifest.json"]
    paths += [GRAPH / f"{name}.npy" for name in ("neuron_ids", "indptr", "targets", "weights", "contact_counts", "signs")]
    for condition in CONDITIONS:
        paths += [baseline_path(condition), RUN / condition / "condition-summary.json",
                  RUN / condition / "brain-final-or-failure.npz",
                  ROOT / f"validation/negative-voltage-replay-{condition}-edge-balance.csv"]
    baseline_plan = json.loads((ROOT / "validation/negative-voltage-replay-plan.json").read_text())
    plan = {"schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "inputs": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in paths},
            "graph_sha256": baseline_plan["graph_sha256"], "conditions": CONDITIONS,
            "targets": TARGET_IDS, "arms": ARMS, "neural_ticks": N_TICKS,
            "parameters": {"dt_ms": .1, "tau_m_ms": 20., "tau_s_ms": 5., "rest_reset_mv": -52.,
                "threshold_strict_greater_mv": -45., "refractory_ticks": 22, "delay_ticks": 18,
                "inhibitory_reversal_mv": -75., "negative_jump_h": "-float64(float32_weight)*(1/23)",
                "gains": 1, "initial_synaptic_states": 0, "initial_last_spike_tick": -(2**60)},
            "arm_semantics": {"C0": "original signed current + freeze/reject/reset",
                "C1": "same signed current + always decay/receive/retain",
                "H0": "inhibition driving force only + freeze/reject/reset",
                "H1": "inhibition driving force only + always decay/receive/retain"},
            "primary_baseline_gate": "C0 bitwise all120001x2 v/s, spikes, accepted ticks/edges/jumps, finalv/s/last/refractory/current, allperedge dispositions; no altered arm until allthree pass",
            "source_boundary": "Retained raw source-index/tick arrays, not accepted-only. Original exogenous histories including target self/cross sources; fixed source-output masks established by prior journal/checkpoint audit. No direct target inputs or RNG, no source spike regeneration.",
            "event_order": "Ordered recorded source event then targetslot0/1. Threshold before delayed delivery; reset after. Savepoststate tick+1, spikestamp tick*.1. Pending precedence before future mask, then in-horizon blocked/unavailable/accepted. All weights includingzero preserved.",
            "production_solver": "Exact signed-current coefficient with canonical original operation order; H positive32point attenuation quadrature; compare64 from same own preceding state on EVERY available H step; no clamps or macroclock refinement",
            "reference_selection": "For each H arm/history/target, available ticks divisibleby1000 plus first/lastavailable, maxprecedingh, maxprecedingp, maximumstiffness(same ash), closest abs(prethreshold+45). argmax/argminfirstties; sortedunique. Adaptivequad+Brent and independent DOP853/Radau plus2/4internal subdivisions of each selected event-free interval, thresholds onlymacroclock.",
            "tolerances_mv": {"32_vs_64": 1e-8, "production_vs_quad": 1e-8,
                "ode_vs_quad": 2e-8, "quad_error_estimate": 1e-9, "subdivision": 1e-8,
                "bounds": 1e-10, "tail": 1.01e-13},
            "synthetic_boundary_control": "Two targets; no-input pass; deliveries at18(positive1e5),19(firing),20(refractory),40(lastrefractory),41(release),62 and beyondhorizon80. Sharedpositive23,negative-23,zero andblockededges. Check knownfirstfire19, availability at19/20/40/41, beforearrival threshold18, reset retention/decay and disposition precedence; excitation-only C/H exact equality acrosspackages; moderate23mV singleimpulse vs analytic passive response within1e-10mV.",
            "summaries": "Everytarget: min/maxprethreshold/poststate, meanandendpointv, spikes/rate/first/last, maxp/s/h andstiffness, lowerboundfractions, thresholdmargin, early[0,500), middle[500,11000), late[11000,12000)spikes andmeanv, accepted/rejected/pending events. Within eachhistory H0-C0,H1-C1 anddifferenceofdifferences for min/mean/endv andspikecount; C1-C0,H1-H0also shown. No pooling asreplicate seeds.",
            "failure_policy": "Retain rawtraces, checks and exceptionreceipt. Caught H interval-solver failure returns all completedmacroticks plusfailinginputstate, failing tick/target and unprocessed disposition4; no partialfailingstep is representedascompleted. Processkill/allocationfailures cannotpromise a prefix. Stopbeforealteredarms if C0 mismatch orsyntheticfailure. Do not silentlytune gains,changeinputs, solver,tolerances ordropfailedtrials. Failednumerics disqualifyinterpretation.",
            "claim_limit": "Conditional two-cell fixed-source factorial, one original seed. No physiology fit, seed robustness, recurrent test, body benchmark or default promotion. Lowerbound prior is engineering, no universal0mVupperbound."}
    write(PLAN, plan)
    print(json.dumps({"plan_sha256": sha(PLAN), "inputs": len(paths)}), flush=True)


def check(report, name, value, **details):
    report["checks"].append({"name": name, "pass": bool(value), **details})


def controls():
    report = {"checks": [], "arms": {}}
    a, b, coefficient = coefficients(.1)
    weights = np.array([1e5, 23., -23., 0., 23.])
    targets = np.array([0, 0, 0, 0, 1], dtype=np.int32)
    blocked = np.array([False, False, False, False, True])
    ticks = np.array([18] + [t for t in [19, 20, 40, 41, 62, 80] for _ in range(4)], dtype=np.int32)
    edges = np.array([0] + [e for _ in range(6) for e in [1, 2, 3, 4]], dtype=np.int32)
    archives = {}
    for arm in ARMS:
        hybrid, package = arm[0] == "H", int(arm[1])
        data = dict(zip(ARRAY_NAMES, replay(64, hybrid, package, ticks, edges, targets, weights, blocked, a, b, coefficient)))
        archives[arm] = data
        s, f = data["state"], data["fired"]
        eligible = data["delivery_eligible"]
        check(report, arm + ":first_fire19_before_delivery", np.flatnonzero(f[:, 0])[0] == 19 and not f[18, 0])
        check(report, arm + ":refractory_release41", np.array_equal(data["available_before_step"][[19, 20, 40, 41], 0], [True, False, False, True]))
        check(report, arm + ":explicit_firing_refractory_eligibility", np.array_equal(eligible[[19, 20, 40], 0], [bool(package)] * 3) and eligible[41, 0])
        check(report, arm + ":reset_voltage", s[20, 0, 0] == -52.)
        check(report, arm + ":blocked_target_at_rest", np.all(s[:, 1, 0] == -52.) and not f[:, 1].any())
        expected = []
        for t, e in zip(ticks, edges):
            expected.append(PENDING if t >= 64 else BLOCKED if blocked[e] else ACCEPTED if eligible[t, targets[e]] else UNAVAILABLE)
        check(report, arm + ":all_dispositions", np.array_equal(data["event_disposition"], expected))
        if package == 0:
            check(report, arm + ":clear_then_freeze", np.all(s[20:42, 0, 1:] == 0.))
        else:
            check(report, arm + ":retained_firing_input", s[20, 0, 1] > 0. and (not hybrid or s[20, 0, 2] == 1.))
            expected_s = s[20, 0, 1] * b + (23. if hybrid else 0.)
            check(report, arm + ":refractory_decay_receive", abs(s[21, 0, 1] - expected_s) <= 1e-10)
            if hybrid:
                check(report, arm + ":refractory_h_decay_receive", s[21, 0, 2] == s[20, 0, 2] * b + 1.)
        zero = dict(zip(ARRAY_NAMES, replay(64, hybrid, package, ticks[:0], edges[:0], targets, weights, blocked, a, b, coefficient)))
        check(report, arm + ":no_input_passive", np.all(zero["state"][:, :, 0] == -52.) and not zero["fired"].any())
        report["arms"][arm] = {"spike_ticks": np.flatnonzero(f[:, 0]).tolist(), "event_disposition": data["event_disposition"].tolist()}
        np.savez_compressed(OUT / f"control-{arm}.npz", **data, event_ticks=ticks, event_edges=edges, weights=weights, edge_targets=targets, blocked=blocked)
    # Excitation-only exact C/H equivalence, including firing/refractory boundaries.
    excitation_weights = np.abs(weights)
    for package in [0, 1]:
        c = replay(64, False, package, ticks, edges, targets, excitation_weights, blocked, a, b, coefficient)
        h = replay(64, True, package, ticks, edges, targets, excitation_weights, blocked, a, b, coefficient)
        check(report, f"package{package}:excitation_only_bitwise", all(c[k].tobytes() == h[k].tobytes() for k in [0, 1, 2, 3, 4, 5, 7, 8, 9]))
        impulse = replay(64, False, package, np.array([18], dtype=np.int32), np.array([1], dtype=np.int32), targets, weights, blocked, a, b, coefficient)
        elapsed = np.arange(46) * .1
        expected_v = -52. + 23. * 5. / 15. * (np.exp(-elapsed / 20.) - np.exp(-elapsed / 5.))
        expected_s = 23. * np.exp(-elapsed / 5.)
        check(report, f"package{package}:single_impulse_analytic", np.max(np.abs(impulse[0][19:, 0, 0] - expected_v)) <= 1e-10 and np.max(np.abs(impulse[0][19:, 0, 1] - expected_s)) <= 1e-10 and not impulse[4].any())
    # Deliberate invalid synthetic input verifies failure-prefix preservation.
    bad_weights = weights.copy()
    bad_weights[0] = np.inf
    failure_data = dict(zip(ARRAY_NAMES, replay(64, True, 1, ticks, edges, targets, bad_weights, blocked, a, b, coefficient)))
    check(report, "synthetic_failure_prefix", np.array_equal(failure_data["solver_failure_tick_target"], [19, 0]) and failure_data["state"].shape == (20, 2, 3) and failure_data["pre_threshold_voltage_mv"].shape == (19, 2) and np.all(failure_data["event_disposition"][1:] == UNPROCESSED))
    np.savez_compressed(OUT / "control-expected-invalid-input.npz", **failure_data)
    write(OUT / "controls.json", report)
    return report


def load_edges():
    with (ROOT / "validation/negative-voltage-replay-incoming-edges.csv").open() as f:
        rows = list(csv.DictReader(f))
    ids = np.load(GRAPH / "neuron_ids.npy", mmap_mode="r")
    weights = np.array([struct.unpack("<f", bytes.fromhex(r["weight_float32_hex"]))[0] for r in rows])
    edge_targets = np.array([int(r["target_slot"]) for r in rows], dtype=np.int32)
    edge_sources = np.array([int(r["source_index"]) for r in rows], dtype=np.int32)
    mapping = np.full((len(ids), 2), -1, dtype=np.int32)
    for k, row in enumerate(rows):
        assert int(row["row"]) == k and mapping[edge_sources[k], edge_targets[k]] == -1
        mapping[edge_sources[k], edge_targets[k]] = k
    return ids, rows, weights, edge_targets, edge_sources, mapping


def reference_checks(data, report):
    state, pre = data["state"], data["pre_threshold_voltage_mv"]
    references = []
    for j in range(2):
        active = np.flatnonzero(data["available_before_step"][:, j])
        selected = set(active[active % 1000 == 0].tolist())
        selected.update([int(active[0]), int(active[-1]),
                         int(active[np.argmax(state[active, j, 2])]),
                         int(active[np.argmax(state[active, j, 1])]),
                         int(active[np.argmin(np.abs(pre[active, j] + 45.))])])
        for tick in sorted(selected):
            v, p, h = state[tick, j]
            ref, estimate = hybrid_reference(v, p, h, .1)
            ode, method, nfev = ode_reference(v, p, h, .1)
            sub_errors = []
            for pieces in [2, 4]:
                vv, pp, hh = v, p, h
                for _ in range(pieces):
                    vv, pp, hh, *_ = hybrid_step(vv, pp, hh, .1 / pieces, *coefficients(.1 / pieces), NODES32, WEIGHTS32)
                sub_errors.append(float(abs(vv - pre[tick, j])))
            row = {"target_id": TARGET_IDS[j], "tick": tick, "preceding_v_p_h": [v, p, h],
                   "production_mv": float(pre[tick, j]), "quad_mv": ref, "quad_error_estimate_mv": estimate,
                   "ode_mv": ode, "ode_method": method, "ode_nfev": nfev,
                   "production_quad_error_mv": float(abs(pre[tick, j] - ref)),
                   "ode_quad_error_mv": abs(ode - ref), "subdivision_errors_mv": sub_errors}
            references.append(row)
    tolerances = report["tolerances_mv"]
    check(report, "selected_steps:production_quad", max(r["production_quad_error_mv"] for r in references) <= tolerances["production_vs_quad"])
    check(report, "selected_steps:ode_quad", max(r["ode_quad_error_mv"] for r in references) <= tolerances["ode_vs_quad"])
    check(report, "selected_steps:quad_error_estimate", max(r["quad_error_estimate_mv"] for r in references) <= tolerances["quad_error_estimate"])
    check(report, "selected_steps:subdivision", max(max(r["subdivision_errors_mv"]) for r in references) <= tolerances["subdivision"])
    return references


def summarize(data, edge_targets, event_edges):
    cells = []
    for j, target in enumerate(TARGET_IDS):
        state, pre = data["state"][:, j], data["pre_threshold_voltage_mv"][:, j]
        spikes = np.flatnonzero(data["fired"][:, j])
        selected_events = edge_targets[event_edges] == j
        code = data["event_disposition"][selected_events]
        active = data["available_before_step"][:, j]
        cells.append({"target_id": target, "minimum_voltage_mv": float(state[:, 0].min()),
            "maximum_voltage_mv": float(state[:, 0].max()), "mean_voltage_mv": float(state[1:, 0].mean()),
            "endpoint_voltage_mv": float(state[-1, 0]), "minimum_pre_threshold_mv": float(pre.min()),
            "maximum_pre_threshold_mv": float(pre.max()), "spike_count": len(spikes), "rate_hz": len(spikes) / 12.,
            "first_spike_ms": float(spikes[0] * .1) if len(spikes) else None,
            "last_spike_ms": float(spikes[-1] * .1) if len(spikes) else None,
            "min_signed_or_positive_state_mv": float(state[:, 1].min()),
            "max_signed_or_positive_state_mv": float(state[:, 1].max()), "max_h": float(state[:, 2].max()),
            "max_stiffness": float((1. + state[:-1, 2].max()) * .1 / 20.),
            "pre_threshold_below_minus75_fraction": float(np.mean(pre < -75. - 1e-10)),
            "closest_threshold_margin_mv": float(np.min(np.abs(pre[active] + 45.))),
            "event_counts": {name: int(np.sum(code == k)) for k, name in enumerate(["accepted", "source_blocked", "target_unavailable", "pending"])},
            "windows": [{"start_ms": start, "end_ms": end,
                "spikes": int(np.sum((spikes >= start * 10) & (spikes < end * 10))),
                "mean_post_voltage_mv": float(state[start * 10 + 1:end * 10 + 1, 0].mean())}
                for start, end in [(0, 500), (500, 11000), (11000, 12000)]]})
    return cells


def run():
    if OUT.exists():
        raise FileExistsError("Preserve prior executed output")
    OUT.mkdir()
    plan = json.loads(PLAN.read_text())
    results = {"plan_sha256": sha(PLAN), "complete": False, "checks": [], "trials": [], "error": None,
               "claim_limit": plan["claim_limit"]}
    try:
        for name, record in plan["inputs"].items():
            if sha(ROOT / name) != record["sha256"]:
                raise ValueError("Frozen input changed: " + name)
        control = controls()
        check(results, "synthetic_boundary_controls", all(r["pass"] for r in control["checks"]))
        if not results["checks"][-1]["pass"]:
            raise ValueError("Synthetic control failure; recorded replay not started")
        ids, rows, weights, targets, sources, mapping = load_edges()
        target_indices = np.searchsorted(ids, TARGET_IDS)
        a, b, coefficient = coefficients(.1)
        baseline_results = json.loads((ROOT / "validation/negative-voltage-replay-results.json").read_text())
        # All three C0 baselines must pass before the altered-arm stage begins.
        for arm in ARMS:
            for condition in CONDITIONS:
                summary = json.loads((RUN / condition / "condition-summary.json").read_text())
                blocked = np.zeros(len(ids), dtype=np.bool_)
                for group in summary["design"]["outgoing_blocks"]:
                    blocked[summary["groups"][group]["indices"]] = True
                with np.load(baseline_path(condition)) as z:
                    baseline = {name: z[name] for name in z.files}
                ticks, edges, source_events = event_inventory(baseline["recorded_source_indices"], baseline["recorded_source_spike_ticks"], mapping)
                if arm == "C0":
                    np.savez_compressed(OUT / f"{condition}-events.npz", delivery_ticks=ticks, edge_rows=edges,
                                        recorded_source_event_index=source_events, source_blocked=blocked)
                hybrid, package = arm[0] == "H", int(arm[1])
                data = dict(zip(ARRAY_NAMES, replay(N_TICKS, hybrid, package, ticks, edges, targets, weights, blocked[sources], a, b, coefficient)))
                archive = OUT / f"{condition}-{arm}.npz"
                np.savez_compressed(archive, **data)
                if data["solver_failure_tick_target"][0] >= 0:
                    raise ValueError("H interval solver rejected input or did not converge; completed prefix retained in " + str(archive.relative_to(ROOT)) + "; tick/target=" + str(data["solver_failure_tick_target"].tolist()))
                report = {"arm": arm, "condition": condition, "checks": [], "tolerances_mv": plan["tolerances_mv"],
                          "archive_sha256": sha(archive), "cells": summarize(data, targets, edges)}
                state, diag = data["state"], data["diagnostics"]
                check(report, "finite_states_prethreshold_diagnostics", all(np.isfinite(data[k]).all() for k in ["state", "pre_threshold_voltage_mv", "diagnostics", "accepted_positive_negative_jump_mv"]))
                check(report, "all_events_partitioned", int(data["edge_disposition_counts"].sum()) == len(edges) and np.array_equal(data["edge_disposition_counts"].sum(axis=1), np.bincount(edges, minlength=len(weights))))
                check(report, "own_threshold_and_availability", np.array_equal(data["fired"], data["available_before_step"] & (data["pre_threshold_voltage_mv"] > -45.)) and np.array_equal(data["available_before_step"], np.arange(N_TICKS)[:, None] - data["last_spike_tick"][:-1] >= 22))
                if arm == "C0":
                    for label, actual, expected in [("all_voltage", state[:, :, 0], baseline["voltage_mv"]),
                        ("all_signed_state", state[:, :, 1], baseline["synaptic_mv"]),
                        ("spikes", data["fired"], baseline["emitted_spikes_by_tick"]),
                        ("accepted_jumps", data["accepted_positive_negative_jump_mv"], baseline["accepted_positive_negative_jump_mv_by_tick"]),
                        ("accepted_ticks", ticks[data["event_disposition"] == ACCEPTED], baseline["accepted_delivery_ticks"]),
                        ("accepted_edges", edges[data["event_disposition"] == ACCEPTED], baseline["accepted_edge_rows"])]:
                        check(report, "C0_bitwise:" + label, actual.shape == expected.shape and actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes())
                    with np.load(RUN / condition / "brain-final-or-failure.npz") as checkpoint:
                        check(report, "C0_final_checkpoint", state[-1, :, 0].tobytes() == checkpoint["voltage_mv"][target_indices].tobytes() and state[-1, :, 1].tobytes() == checkpoint["synaptic_mv"][target_indices].tobytes() and np.array_equal(data["last_spike_tick"][-1], checkpoint["last_spike_tick"][target_indices]) and np.array_equal(blocked, checkpoint["ablated"]) and np.array_equal(checkpoint["refractory_ticks"][target_indices], [22, 22]) and np.array_equal(checkpoint["current_mv"][target_indices], [0., 0.]))
                    with (ROOT / f"validation/negative-voltage-replay-{condition}-edge-balance.csv").open() as f:
                        balance = list(csv.DictReader(f))
                    expected_counts = np.array([[int(r[k]) for k in ["accepted_events", "source_blocked_events", "target_unavailable_events", "beyond_horizon_events"]] for r in balance])
                    check(report, "C0_every_edge_disposition", np.array_equal(data["edge_disposition_counts"], expected_counts))
                    old = next(r for r in baseline_results["conditions"] if r["condition"] == condition)
                    check(report, "C0_no_direct_target_drive_provenance", old["selected_targets_in_any_input_list"] is False)
                if hybrid:
                    check(report, "H_nonnegative_synapses", np.all(state[:, :, 1:] >= 0.))
                    check(report, "H_lower_bound_all_states_and_prethreshold", state[:, :, 0].min() >= -75. - 1e-10 and data["pre_threshold_voltage_mv"].min() >= -75. - 1e-10)
                    check(report, "H_interval_upper_bound", diag[:, :, 5].max() <= 1e-10)
                    check(report, "H_every_available_step32_vs64", diag[:, :, 4].max() <= 1e-8, max_error_mv=float(diag[:, :, 4].max()))
                    check(report, "H_tail_bound", diag[:, :, 0].max() <= 1.01e-13)
                    check(report, "H_inverse_residual_iterations", np.all(diag[:, :, 1] <= 1e-13 * (1. + diag[:, :, 3])) and diag[:, :, 2].max() <= 48)
                    report["max_diagnostics"] = {name: float(diag[:, :, k].max()) for k, name in enumerate(["tail_bound_mv", "inverse_residual", "inverse_iterations", "attenuation_cutoff", "production32_64_error_mv", "upper_bound_excess_mv"])}
                    report["references"] = reference_checks(data, report)
                check(report, "package1_accepts_all_unblocked_in_horizon" if package else "package0_rejects_unavailable", not np.any(data["event_disposition"] == UNAVAILABLE) if package else np.array_equal(data["delivery_eligible"], data["available_before_step"] & ~data["fired"]))
                report["passed"] = all(r["pass"] for r in report["checks"])
                write(OUT / f"{condition}-{arm}.json", report)
                results["trials"].append({k: v for k, v in report.items() if k != "references"})
                write(OUT / "results.json", results)
                print(json.dumps({"arm": arm, "condition": condition, "passed": report["passed"], "spikes": [c["spike_count"] for c in report["cells"]], "min_mv": [c["minimum_voltage_mv"] for c in report["cells"]]}), flush=True)
                if not report["passed"]:
                    raise ValueError("Retained trial failed numerical/integrity gates: " + condition + " " + arm)
        contrasts = []
        for condition in CONDITIONS:
            trial = {r["arm"]: r for r in results["trials"] if r["condition"] == condition}
            for j, target in enumerate(TARGET_IDS):
                for metric in ["minimum_voltage_mv", "mean_voltage_mv", "endpoint_voltage_mv", "spike_count"]:
                    value = {arm: trial[arm]["cells"][j][metric] for arm in ARMS}
                    contrasts.append({"condition": condition, "target_id": target, "metric": metric,
                        "values": value, "H0-C0": value["H0"] - value["C0"], "H1-C1": value["H1"] - value["C1"],
                        "C1-C0": value["C1"] - value["C0"], "H1-H0": value["H1"] - value["H0"],
                        "interaction": (value["H1"] - value["C1"]) - (value["H0"] - value["C0"])})
        results["contrasts"] = contrasts
        check(results, "frozen_inputs_unchanged_after", all(sha(ROOT / name) == record["sha256"] for name, record in plan["inputs"].items()))
        results["complete"] = len(results["trials"]) == 12
    except Exception as exc:
        results["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    results["passed"] = results["complete"] and results["error"] is None and all(r["pass"] for r in results["checks"]) and all(r["passed"] for r in results["trials"])
    results["completed_utc"] = datetime.now(timezone.utc).isoformat()
    results["artifacts"] = {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(OUT.glob("*")) if p.name != "results.json"}
    write(OUT / "results.json", results)
    print(json.dumps({"passed": results["passed"], "trials": len(results["trials"]), "error": results["error"]}), flush=True)
    if not results["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    args = parser.parse_args()
    prepare() if args.mode == "prepare" else run()
