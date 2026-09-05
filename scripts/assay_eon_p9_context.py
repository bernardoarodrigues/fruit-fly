#!/usr/bin/env python3
"""Frozen neural-only P9 × known male LgAG2 panel; no body or parameter fitting."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.data import Connectome
from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive, _uniform
from fruitfly.sensors import MotorDecoder

PLAN = ROOT / "validation/eon-p9-context-plan.json"
OUT = ROOT / "validation/eon-p9-context"
GRAPH = ROOT / "data/processed/malecns_v1"
CONDITIONS = {
    "no_events": {"p9_hz": 0., "taste_hz": 0., "outgoing_block": None},
    "taste_only": {"p9_hz": 0., "taste_hz": 200., "outgoing_block": None},
    "p9_only": {"p9_hz": 100., "taste_hz": 0., "outgoing_block": None},
    "p9_plus_taste": {"p9_hz": 100., "taste_hz": 200., "outgoing_block": None},
    "p9_only_p9_outputs_blocked": {"p9_hz": 100., "taste_hz": 0., "outgoing_block": "p9"},
    "p9_plus_taste_taste_outputs_blocked": {"p9_hz": 100., "taste_hz": 200., "outgoing_block": "taste"},
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


@njit(cache=True)
def uniforms(state, ticks, columns):
    result = np.empty((ticks, columns), dtype=np.float64)
    for t in range(ticks):
        for c in range(columns):
            result[t, c] = _uniform(state)
    return result


def groups(graph):
    p9 = graph.select(["DNp09"])
    taste = graph.select(["LgAG2"])
    p9 = p9[np.argsort(graph.neuron_ids[p9])]
    taste = taste[np.argsort(graph.neuron_ids[taste])]
    motor = MotorDecoder(graph)
    result = {"p9": p9, "taste": taste, **motor.groups}
    for kind in ["DNa01", "DNa02", "DNg97", "MN9"]:
        for side in ["L", "R"]:
            result[kind + "_" + side] = graph.select([kind], side=side)
    selected = np.unique(np.concatenate(list(result.values())))
    # Retain the two earlier negative-voltage targets separately, without input.
    selected = np.unique(np.r_[selected, np.searchsorted(graph.neuron_ids, [67052, 13314])]).astype(np.int32)
    return p9, taste, result, selected


def prepare(graph):
    if PLAN.exists() or OUT.exists():
        raise FileExistsError("Preserve prior plan/results")
    p9, taste, readouts, selected = groups(graph)
    assert graph.neuron_ids[p9].tolist() == [10783, 11177]
    assert graph.neuron_ids[taste].tolist() == [87710, 91221, 91302, 92929, 93294, 94367, 123191, 151556, 162704, 219573, 526151]
    source = np.r_[p9, taste]
    net = LIFNetwork.from_connectome(graph, seed=11)
    paths = [Path(__file__).resolve(), ROOT / "fruitfly/neural.py", ROOT / "fruitfly/data.py", ROOT / "fruitfly/sensors.py",
             GRAPH / "manifest.json", GRAPH / "neurons.feather"]
    paths += [GRAPH / (n + ".npy") for n in ["neuron_ids", "indptr", "targets", "weights", "contact_counts", "signs"]]
    notebook = ROOT / "data/raw/eon-public-code/drosophila_brain_model_lif/source/results/eon_1/demo_notebook.ipynb"
    paths.append(notebook)
    plan = {"schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "purpose": "Eon-inspired P9 locomotor-context × known male LgAG2 activation; neural-only, not natural walking or an embodied-demo reproduction",
        "source_recipe": {"commit": "c976c7a9", "notebook_cells": [9, 14, 16, 35, 36],
            "difference": "Use only eleven verified male LgAG2 cells; omit Eon's two separately named ascending-leg inputs and do not substitute LgLG4. Source displayed means use another graph, duration and trial count."},
        "seeds": [11, 12], "duration_ms": 500., "sample_interval_ms": 1., "neural_ticks": 5000,
        "conditions": CONDITIONS, "condition_order": list(CONDITIONS),
        "parameters": asdict(net.parameters), "graph_sha256": net.graph_sha256,
        "neurons": net.n_neurons, "edges": net.n_edges,
        "source_indices": source.tolist(), "source_ids": graph.neuron_ids[source].tolist(),
        "source_types": graph.neurons.iloc[source]["type"].tolist(),
        "taste_root_sides": graph.neurons.iloc[taste]["rootSide"].tolist(),
        "taste_entry_nerves": graph.neurons.iloc[taste]["entryNerve"].tolist(),
        "groups": {k: {"indices": v.tolist(), "ids": graph.neuron_ids[v].tolist()} for k, v in readouts.items()},
        "selected_indices": selected.tolist(), "selected_ids": graph.neuron_ids[selected].tolist(),
        "drive": {"order": "Two ascending-numeric-ID DNp09, then eleven ascending-numeric-ID LgAG2; identical13-cell union every step and condition",
            "current_mv": None, "poisson_weight_mv": None, "disable_refractory": True,
            "other_inputs": [], "zero_rate_convention": "All13 listed cells receive zero refractory even at zero rate; no-events is a common-eligibility control, not an untouched-physiology claim",
            "event_accounting": "Reconstruct candidate Bernoulli arrivals with frozen _uniform on a separate RNG copy; same-tick source spikes identify arrivals rejected by source API. Applied events are inferred from pinned ordering, not newly instrumented kernel writes."},
        "samples": "Initial and every1ms selected voltage/synaptic/refractory/last-spike states, global voltage extrema/mean, actual group counts; all network ordered spike indices and integer0.1ms ticks; full initial/final checkpoint; candidate/applied external-event masks and RNG per1ms",
        "analysis_windows_ms": [[0., 50.], [50., 500.], [0., 500.]],
        "checks": ["exact graph/source hashes and thirteen IDs", "all5000ticks and500one_ms samples", "full ordered spike stream and selected/all-cell count reconciliation", "all13source refractory0/current0", "RNG shadow/endpoints equal eachsample and acrossconditions", "external candidate events partition by same-tick threshold firing", "outgoing mask exact and delayed edge-visit counts reconstructed", "final last-spike/pending queues from ordered spikes", "noevents no network spikes", "P9-output block leaves no nonP9 spikes with onlyP9 input", "source files unchanged after panel"],
        "not_success_gates": ["DN recruitment, effect direction, physiological voltage range or model rate", "matching source author1s/30trial means", "body movement, navigation, feeding or inhibition-model selection"],
        "limits": ["No body or decoder action is run", "No source/weight/neural parameter change or search", "Source spike count is not configured input-event rate", "1ms selected states are sampled; every0.1ms interior membrane state is not retained", "No additional experiment after this panel; retain all failures"],
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}}
    assert len(source) == len(set(source.tolist())) == 13
    assert net.graph_sha256 == "e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8"
    write(PLAN, plan)
    print(json.dumps({"plan_sha256": sha(PLAN), "trials": 12, "sources": plan["source_ids"]}), flush=True)


def verify(plan):
    for p, expected in plan["source_sha256"].items():
        if sha(ROOT / p) != expected:
            raise ValueError("Frozen source changed: " + p)


def checkpoint(net, path):
    state = net.state_dict()
    arrays = {k: v for k, v in state.items() if isinstance(v, np.ndarray)}
    metadata = {k: v for k, v in state.items() if not isinstance(v, np.ndarray)}
    np.savez_compressed(path, metadata=json.dumps(metadata, sort_keys=True), **arrays)


def trial(graph, plan, seed, name):
    start = time.perf_counter()
    folder = OUT / f"seed-{seed}" / name
    folder.mkdir(parents=True)
    spec = plan["conditions"][name]
    p9, taste, readouts, selected = groups(graph)
    sources = np.r_[p9, taste]
    rates = np.r_[np.full(2, spec["p9_hz"]), np.full(11, spec["taste_hz"])]
    net = LIFNetwork.from_connectome(graph, parameters=LIFParameters(**plan["parameters"]), seed=seed)
    blocked = np.zeros(net.n_neurons, dtype=bool)
    if spec["outgoing_block"] is not None:
        net.ablate(readouts[spec["outgoing_block"]]); blocked[readouts[spec["outgoing_block"]]] = True
    checkpoint(net, folder / "initial.npz")
    initial_rng = int(net._rng_state[0])
    drive = SparseDrive(sources, rates_hz=rates)
    source_column = np.full(net.n_neurons, -1, dtype=np.int32)
    source_column[sources] = np.arange(13)
    samples, spikes_i, spikes_t, arrivals, applied = [], [], [], [], []
    vs, gs, lasts, refrs, uniforms_saved = [], [], [], [], []
    checks = {k: True for k in ["clock", "finite_sampled_state", "ordered_spikes", "spike_grid", "rng_shadow", "drive_contract", "arrival_partition"]}
    error = None
    def sample_states():
        vs.append(net.voltage_mv[selected].copy()); gs.append(net.synaptic_mv[selected].copy())
        lasts.append(net.last_spike_tick[selected].copy()); refrs.append(net.refractory_ticks[selected].copy())
    sample_states()
    with (folder / "samples.jsonl").open("w") as stream:
        try:
            for ms in range(500):
                first_tick = net.tick
                shadow = net._rng_state.copy()
                u = uniforms(shadow, 10, 13)
                candidate = u < (rates * .1 / 1000.)
                before_rng = int(net._rng_state[0])
                batch = net.advance(1., drive=drive)
                ticks = np.rint(batch.times_ms / .1).astype(np.int64)
                fired_input = np.zeros((10, 13), dtype=bool)
                sc = source_column[batch.indices]
                keep = sc >= 0
                fired_input[ticks[keep] - first_tick, sc[keep]] = True
                delivered = candidate & ~fired_input
                counts = np.bincount(batch.indices, minlength=net.n_neurons)
                checks["clock"] &= net.tick == (ms + 1) * 10 and batch.start_ms == float(ms) and batch.end_ms == float(ms + 1)
                checks["finite_sampled_state"] &= np.isfinite(net.voltage_mv).all() and np.isfinite(net.synaptic_mv).all()
                checks["spike_grid"] &= np.array_equal(ticks * .1, batch.times_ms) and ((ticks >= first_tick) & (ticks < net.tick)).all()
                checks["ordered_spikes"] &= bool(np.all((np.diff(ticks) > 0) | ((np.diff(ticks) == 0) & (np.diff(batch.indices) > 0))))
                checks["rng_shadow"] &= np.array_equal(shadow, net._rng_state)
                checks["drive_contract"] &= np.array_equal(net._previous_drive, sources) and np.all(net.refractory_ticks[sources] == 0) and not np.any(net._current_mv) and np.array_equal(net.ablated, blocked)
                checks["arrival_partition"] &= np.array_equal(candidate, delivered | (candidate & fired_input))
                row = {"start_tick": first_tick, "end_tick": net.tick, "start_ms": float(ms), "end_ms": float(ms + 1),
                    "rng_before": before_rng, "rng_after": int(net._rng_state[0]), "total_spikes": batch.total_spikes,
                    "traversed_edges": batch.traversed_edges, "voltage_min_mv": float(net.voltage_mv.min()),
                    "voltage_max_mv": float(net.voltage_mv.max()), "voltage_mean_mv": float(net.voltage_mv.mean()),
                    "group_counts": {k: int(counts[v].sum()) for k, v in readouts.items()},
                    "source_counts": counts[sources].tolist(), "candidate_events": candidate.sum(axis=0).tolist(),
                    "applied_events_inferred": delivered.sum(axis=0).tolist()}
                stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                samples.append(row); sample_states()
                spikes_i.append(batch.indices.copy()); spikes_t.append(ticks)
                uniforms_saved.append(u); arrivals.append(candidate); applied.append(delivered)
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(), "tick": net.tick}
    indices = np.concatenate(spikes_i) if spikes_i else np.empty(0, dtype=np.int32)
    ticks = np.concatenate(spikes_t) if spikes_t else np.empty(0, dtype=np.int64)
    counts = np.bincount(indices, minlength=net.n_neurons)
    np.savez_compressed(folder / "spikes.npz", indices=indices, ticks=ticks)
    np.savez_compressed(folder / "states.npz", sample_ms=np.arange(len(vs), dtype=np.float64),
                        selected_indices=selected, selected_ids=graph.neuron_ids[selected], voltage_mv=np.asarray(vs),
                        synaptic_mv=np.asarray(gs), last_spike_tick=np.asarray(lasts), refractory_ticks=np.asarray(refrs), all_neuron_spike_counts=counts)
    np.savez_compressed(folder / "inputs.npz", source_indices=sources, source_ids=graph.neuron_ids[sources], rates_hz=rates,
                        uniforms=np.asarray(uniforms_saved).reshape((-1, 13)), candidate=np.asarray(arrivals).reshape((-1, 13)),
                        applied_inferred=np.asarray(applied).reshape((-1, 13)))
    checkpoint(net, folder / "final-or-failure.npz")
    checks["complete_500ms"] = net.tick == 5000 and len(samples) == 500 and error is None
    checks["total_count_reconciles"] = len(indices) == int(counts.sum()) == sum(r["total_spikes"] for r in samples)
    checks["last_spike_ticks_from_complete_stream"] = True
    expected_last = np.full(net.n_neurons, -(2**60), dtype=np.int64)
    np.maximum.at(expected_last, indices, ticks)
    checks["last_spike_ticks_from_complete_stream"] = np.array_equal(expected_last, net.last_spike_tick)
    outdegree = np.diff(graph.indptr)
    delivery_ticks = ticks + net.delay_ticks
    delivered = (delivery_ticks < net.tick) & ~blocked[indices]
    visits = np.zeros(len(samples), dtype=np.int64)
    np.add.at(visits, delivery_ticks[delivered] // 10, outdegree[indices[delivered]])
    checks["delayed_unblocked_edge_visits_each_ms"] = np.array_equal(visits, [r["traversed_edges"] for r in samples])
    state = net.state_dict()
    pending = [indices[(delivery_ticks >= net.tick) & (delivery_ticks % 19 == slot)] for slot in range(19)]
    checks["pending_ring_counts_and_order"] = np.array_equal(state["pending_count"], [len(x) for x in pending]) and np.array_equal(state["pending"], np.concatenate(pending))
    checks["source_counts_reconcile"] = np.array_equal(counts[sources], np.asarray([r["source_counts"] for r in samples]).sum(axis=0))
    if name == "no_events":
        checks["zero_events_zero_spikes"] = len(indices) == 0 and not np.asarray(arrivals).any()
    if name == "p9_only_p9_outputs_blocked":
        checks["blocked_p9_no_other_cells_spike"] = np.isin(indices, p9).all()
    windows = []
    for left, right in plan["analysis_windows_ms"]:
        chosen = (ticks >= round(left / .1)) & (ticks < round(right / .1))
        wc = np.bincount(indices[chosen], minlength=net.n_neurons)
        windows.append({"start_ms": left, "end_ms": right, "duration_s": (right - left) / 1000,
            "groups": {k: {"count": int(wc[v].sum()), "per_cell_counts": wc[v].tolist(),
                "mean_rate_hz": float(wc[v].mean() / ((right - left) / 1000))} for k, v in readouts.items()}})
    result = {"seed": seed, "condition": name, "config": spec, "plan_sha256": sha(PLAN), "complete": error is None and net.tick == 5000,
        "checks": {k: bool(v) for k, v in checks.items()}, "passed": bool(all(checks.values())), "error": error,
        "wall_seconds": time.perf_counter() - start, "neural_ticks": net.tick, "total_spikes": len(indices),
        "selected_states_shape": list(np.asarray(vs).shape), "voltage_min_sampled_mv": min([r["voltage_min_mv"] for r in samples], default=-52.),
        "voltage_max_sampled_mv": max([r["voltage_max_mv"] for r in samples], default=-52.),
        "initial_rng": initial_rng, "final_rng": int(net._rng_state[0]), "expected_rng_draws": net.tick * 13,
        "source_ids": graph.neuron_ids[sources].tolist(), "actual_source_spikes": counts[sources].tolist(),
        "candidate_events": np.asarray(arrivals).reshape((-1, 13)).sum(axis=0).tolist(),
        "applied_events_inferred": np.asarray(applied).reshape((-1, 13)).sum(axis=0).tolist(),
        "windows": windows, "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in sorted(folder.iterdir())}}
    write(folder / "summary.json", result)
    print(json.dumps({k: result[k] for k in ["seed", "condition", "passed", "total_spikes", "voltage_min_sampled_mv", "wall_seconds"]}), flush=True)
    return result


def run(graph):
    if OUT.exists():
        raise FileExistsError("Preserve prior execution artifacts")
    plan = json.loads(PLAN.read_text()); verify(plan); OUT.mkdir()
    report = {"plan_sha256": sha(PLAN), "complete": False, "trials": [], "checks": {}}
    for seed in plan["seeds"]:
        for name in plan["condition_order"]:
            report["trials"].append(trial(graph, plan, seed, name))
            write(OUT / "results.json", report)
    for seed in plan["seeds"]:
        rows = [r for r in report["trials"] if r["seed"] == seed]
        report["checks"][f"seed{seed}:same_rng_endpoints_and_draw_counts"] = len({(r["initial_rng"], r["final_rng"], r["expected_rng_draws"]) for r in rows}) == 1
        for unblocked, blocked in [("p9_only", "p9_only_p9_outputs_blocked"), ("p9_plus_taste", "p9_plus_taste_taste_outputs_blocked")]:
            a = next(r for r in rows if r["condition"] == unblocked)
            b = next(r for r in rows if r["condition"] == blocked)
            pa = OUT / f"seed-{seed}" / unblocked / "inputs.npz"
            pb = OUT / f"seed-{seed}" / blocked / "inputs.npz"
            with np.load(pa) as za, np.load(pb) as zb:
                report["checks"][f"seed{seed}:{unblocked}:blocked_pair_same_order_uniforms_candidates"] = all(np.array_equal(za[k], zb[k]) for k in ["source_ids", "source_indices", "rates_hz", "uniforms", "candidate"])
    verify(plan); report["checks"]["frozen_sources_unchanged"] = True
    report["complete"] = len(report["trials"]) == 12 and all(r["complete"] for r in report["trials"])
    report["passed"] = report["complete"] and all(report["checks"].values()) and all(r["passed"] for r in report["trials"])
    report["check_count"] = len(report["checks"]) + sum(len(r["checks"]) for r in report["trials"])
    report["scope"] = plan["purpose"]
    report["claim_limits"] = plan["limits"]
    write(OUT / "results.json", report)
    print(json.dumps({k: report[k] for k in ["complete", "passed", "check_count"]}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    graph = Connectome.load(GRAPH, verify=True)
    prepare(graph) if args.prepare else run(graph)
