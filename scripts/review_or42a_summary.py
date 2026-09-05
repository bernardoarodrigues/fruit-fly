#!/usr/bin/env python3
"""Review all saved Or42a excitation trials without executing a neural model."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT/path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with (ROOT/path).open("rb") as stream:
        while data := stream.read(8*1024*1024):
            digest.update(data)
    return digest.hexdigest()


def same(a, b):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape and np.array_equal(a, b)


def uniforms(initial):
    """Independent Python-integer xorshift64*; no producer RNG import."""
    state, mask = int(initial), (1 << 64)-1
    values, boundaries = np.empty((15000, 36)), [state]
    for tick in range(15000):
        for column in range(36):
            state ^= state >> 12
            state ^= (state << 25) & mask
            state ^= state >> 27
            values[tick, column] = ((state*2685821657736338717 & mask) >> 11)/9007199254740992.
        if (tick+1) % 50 == 0:
            boundaries.append(state)
    return values, boundaries


def main():
    plan_path = "validation/or42a-summary-plan.json"
    report_path = "validation/or42a-summary-experiment.json"
    environment_path = "validation/or42a-summary-environment.json"
    table_path = "validation/or42a-summary-window-table.csv"
    plan, report, environment = map(read, (plan_path, report_path, environment_path))
    assert report["complete"] and all(report["checks"].values())
    assert report["plan_sha256"] == sha(plan_path)
    assert environment["report_sha256"] == sha(report_path)
    assert environment["window_table_sha256"] == sha(table_path)
    for path, expected in plan["source_sha256"].items():
        assert sha(path) == expected, path
    graph_dir = "data/processed/malecns_v1/"
    manifest = read(graph_dir+"manifest.json")
    for name, detail in manifest["arrays"].items():
        assert sha(graph_dir+name) == detail["sha256"]
    arrays = {name: np.load(ROOT/(graph_dir+name+".npy"), mmap_mode="r", allow_pickle=False)
              for name in ("neuron_ids", "indptr", "targets", "weights")}
    fingerprint = hashlib.sha256()
    for array in arrays.values():
        fingerprint.update(str(array.shape).encode())
        fingerprint.update(memoryview(array).cast("B"))
    assert fingerprint.hexdigest() == plan["graph_sha256"]
    ids, indptr, targets = [arrays[k] for k in ("neuron_ids", "indptr", "targets")]
    assert len(ids) == plan["neurons"] == 166700 and len(targets) == plan["edges"] == 25582938
    neurons = pd.read_feather(ROOT/(graph_dir+"neurons.feather"))
    same(neurons.bodyId.values, ids)
    source_indices = np.flatnonzero(neurons.type.eq("ORN_VM7d").values)
    source_indices = source_indices[np.argsort(ids[source_indices])]
    same(source_indices, plan["source_graph_indices"])
    same(ids[source_indices], plan["source_body_ids"])
    assert len(source_indices) == 36 and Counter(neurons.iloc[source_indices].rootSide) == {"L": 18, "R": 18}
    assert set(neurons.iloc[source_indices].entryNerve) == {"MxLbN"}
    assert neurons.iloc[source_indices].rootSide.tolist() == plan["source_sides"]
    assert neurons.iloc[source_indices].entryNerve.tolist() == plan["source_nerves"]
    hop = np.setdiff1d(np.unique(np.concatenate([targets[indptr[i]:indptr[i+1]] for i in source_indices])), source_indices)
    same(ids[hop], plan["first_hop_body_ids"])
    assert len(hop) == 365
    side = neurons.rootSide.fillna(neurons.somaSide)
    motor_types = {"forward": (["DNg97"], None), "turn_left": (["DNa01", "DNa02"], "L"),
                   "turn_right": (["DNa01", "DNa02"], "R"), "feeding": (["MN9"], None), "escape": (["DNp01"], None)}
    motor = {}
    for key, (types, lateral) in motor_types.items():
        mask = neurons.type.isin(types)
        if lateral is not None:
            mask &= side.eq(lateral)
        motor[key] = np.flatnonzero(mask.values)
        same(ids[motor[key]], plan["motor_groups"][key])
    assert plan["parameters"] == {"dt_ms": .1, "resting_mv": -52., "reset_mv": -52., "threshold_mv": -45.,
        "membrane_tau_ms": 20., "synapse_tau_ms": 5., "refractory_ms": 2.2, "delay_ms": 1.8, "poisson_weight_mv": 68.75}
    assert plan["motor_observation"] == {"taste_food": False, "taste_water": False}
    primary = read("validation/or42a-primary/results.json")["suggested_primary_summary_boundary"]
    assert plan["conditions"] == {"no_input": [0., 0., 0.], "constant_baseline": [11., 11., 11.],
        "ethyl_acetate": [11., 149., 11.], "isoamyl_acetate": [11., primary["isoamyl_acetate_total_rate_hz"], 11.],
        "ethyl_acetate_source_outputs_blocked": [11., 149., 11.]}
    lookup_column = np.full(len(ids), -1, dtype=int)
    lookup_column[source_indices] = np.arange(36)
    degree = np.diff(indptr)
    rng_cache, summaries, paired, archive_files = {}, [], {}, {}
    window_table = list(csv.DictReader((ROOT/table_path).open()))
    assert len(window_table) == 45 and len(report["trials"]) == 15
    all_commands, all_middle_commands = Counter(), Counter()
    sampled_min, sampled_max = float("inf"), float("-inf")
    for trial_index, trial in enumerate(report["trials"]):
        seed, condition = trial["seed"], trial["condition"]
        assert (seed, condition) == (plan["seeds"][trial_index//5], plan["condition_order"][trial_index%5])
        assert trial["complete"] and trial["error"] is None and all(trial["checks"].values())
        folder = Path(trial["run_dir"])
        for name, detail in trial["files"].items():
            assert sha(folder/name) == detail["sha256"]
            assert (ROOT/folder/name).stat().st_size == detail["bytes"]
            archive_files[str(folder/name)] = detail["sha256"]
        assert read(folder/"result.json") == trial
        trace = np.load(ROOT/folder/"trace.npz", allow_pickle=False)
        samples = [json.loads(line) for line in (ROOT/folder/"samples.jsonl").read_text().splitlines()]
        assert len(samples) == 300 and trial["final_neural_time_ms"] == 1500
        same(trace["source_body_ids"], ids[source_indices])
        same(trace["source_graph_indices"], source_indices)
        initial = int(np.random.SeedSequence(seed).generate_state(1, dtype=np.uint64)[0]) or 1
        assert int(trace["initial_rng_state"][0]) == trial["initial_rng_state"] == initial
        if seed not in rng_cache:
            rng_cache[seed] = uniforms(initial)
        random_values, boundaries = rng_cache[seed]
        assert int(trace["final_rng_state"][0]) == trial["final_rng_state"] == boundaries[-1]
        assert trial["rng_draws"] == 540000
        rates = np.repeat(plan["conditions"][condition], 5000)
        requested_tick, requested_column = np.nonzero(random_values < rates[:, None]*.1/1000)
        same(requested_tick, trace["requested_arrival_ticks"])
        same(requested_column, trace["requested_arrival_source_column"])
        arrival_digest = hashlib.sha256(requested_tick.astype("<i8").tobytes()+requested_column.astype("<i8").tobytes()).hexdigest()
        assert arrival_digest == trial["requested_arrival_sha256"]
        indices, ticks = trace["all_spike_graph_indices"], trace["all_spike_ticks"]
        assert indices.shape == ticks.shape and indices.dtype.kind in "iu" and ticks.dtype.kind in "iu"
        assert np.all((indices >= 0) & (indices < len(ids))) and np.all((ticks >= 0) & (ticks < 15000))
        assert np.all(np.diff(ticks) >= 0)
        assert np.all(np.diff(indices)[np.diff(ticks) == 0] > 0)
        is_source = lookup_column[indices] >= 0
        same(trace["source_spike_ticks"], ticks[is_source])
        same(trace["source_spike_body_ids"], ids[indices[is_source]])
        source_digest = hashlib.sha256(ticks[is_source].astype("<i8").tobytes()+ids[indices[is_source]].astype("<i8").tobytes()).hexdigest()
        assert source_digest == trial["actual_source_spike_sha256"]
        source_fired = np.zeros((15000, 36), bool)
        source_fired[ticks[is_source], lookup_column[indices[is_source]]] = True
        applied = ~source_fired[requested_tick, requested_column]
        same(applied, trace["applied_direct_voltage_arrival"])
        counts = np.bincount(indices+(ticks//5000)*len(ids), minlength=3*len(ids)).reshape(3, len(ids))
        same(counts, trace["all_neuron_window_spike_counts"])
        delivery_tick = ticks+18
        eligible = delivery_tick < 15000
        if condition.endswith("outputs_blocked"):
            eligible &= ~is_source
            assert is_source.all(), "Blocked trial contains downstream activity"
        visits = np.zeros(300, dtype=np.int64)
        np.add.at(visits, delivery_tick[eligible]//50, degree[indices[eligible]])
        same(visits, trace["reconstructed_edge_visits_by5ms"])
        same(visits, trace["actual_edge_visits_by5ms"])
        for key in ("final_voltage_mv", "final_synaptic_mv"):
            assert trace[key].shape == (166700,) and np.isfinite(trace[key]).all()
        if condition == "no_input":
            assert len(ticks) == len(requested_tick) == 0
            same(trace["final_voltage_mv"], np.full(166700, -52.))
            same(trace["final_synaptic_mv"], np.zeros(166700))
        motor_rates = {key: 0. for key in motor}
        commands = []
        for chunk, sample in enumerate(samples):
            assert (sample["chunk"], sample["start_tick"], sample["end_tick"], sample["window"]) == (chunk, chunk*50, (chunk+1)*50, chunk//100)
            assert sample["rate_hz"] == plan["conditions"][condition][chunk//100]
            assert (sample["rng_before"], sample["rng_after"], sample["rng_draws"]) == (boundaries[chunk], boundaries[chunk+1], 1800)
            event_slice = slice(np.searchsorted(ticks, chunk*50), np.searchsorted(ticks, (chunk+1)*50))
            arrival_slice = slice(np.searchsorted(requested_tick, chunk*50), np.searchsorted(requested_tick, (chunk+1)*50))
            chunk_indices = indices[event_slice]
            chunk_applied = applied[arrival_slice]
            assert sample["requested_arrivals"] == len(chunk_applied)
            assert sample["applied_direct_voltage_arrivals"] == int(chunk_applied.sum())
            assert sample["same_tick_spike_rejected_arrivals"] == int((~chunk_applied).sum())
            assert sample["actual_source_spikes"] == int(is_source[event_slice].sum())
            assert sample["all_spikes"] == len(chunk_indices)
            assert sample["actual_edge_visits"] == int(visits[chunk])
            assert sample["all_state_finite"]
            for key in ("global_voltage_min_mv", "global_voltage_max_mv", "source_voltage_min_mv", "source_voltage_max_mv"):
                assert np.isfinite(sample[key])
            assert sample["global_voltage_min_mv"] <= sample["source_voltage_min_mv"] <= sample["source_voltage_max_mv"] <= sample["global_voltage_max_mv"]
            for key, group_indices in motor.items():
                count = np.count_nonzero(np.isin(chunk_indices, group_indices))
                motor_rates[key] += (1-np.exp(-.005/.05))*(count/len(group_indices)/.005-motor_rates[key])
                assert abs(motor_rates[key]-sample["motor_rates_hz"][key]) < 1e-12
            forward = np.clip(motor_rates["forward"]/40, 0, 1)
            turn = np.clip((motor_rates["turn_left"]-motor_rates["turn_right"])/50, -.6, .6)
            command = ({"behavior": "rest", "left": 0., "right": 0.} if forward < .05 and abs(turn) < .05 else
                       {"behavior": "walk", "left": float(np.clip(forward-turn, -1.2, 1.2)), "right": float(np.clip(forward+turn, -1.2, 1.2))})
            assert command == sample["unrealized_motor_command"]
            commands.append(command["behavior"])
        final = samples[-1]
        assert float(trace["final_voltage_mv"].min()) == final["global_voltage_min_mv"]
        assert float(trace["final_voltage_mv"].max()) == final["global_voltage_max_mv"]
        assert float(trace["final_voltage_mv"][source_indices].min()) == final["source_voltage_min_mv"]
        assert float(trace["final_voltage_mv"][source_indices].max()) == final["source_voltage_max_mv"]
        for window, w in enumerate(trial["windows"]):
            tick_mask = (requested_tick >= window*5000) & (requested_tick < (window+1)*5000)
            ss = samples[window*100:(window+1)*100]
            assert w["window"] == window and w["requested_hz_per_source"] == plan["conditions"][condition][window]
            assert w["expected_Bernoulli_arrivals"] == w["requested_hz_per_source"]*.5*36
            assert w["realized_arrivals"] == int(tick_mask.sum())
            assert w["applied_direct_voltage_arrivals"] == int(applied[tick_mask].sum())
            assert w["actual_source_spikes"] == int(counts[window, source_indices].sum())
            assert w["actual_source_mean_rate_hz"] == w["actual_source_spikes"]/18
            same(w["actual_source_counts_by_body_id_order"], counts[window, source_indices])
            assert w["actual_source_spikes_by_side"] == {s: int(counts[window, source_indices][neurons.iloc[source_indices].rootSide.eq(s)].sum()) for s in ("L", "R")}
            assert w["non_source_spikes"] == int(counts[window].sum()-counts[window, source_indices].sum())
            assert w["first_hop_non_source_spikes"] == int(counts[window, hop].sum())
            assert w["all_spikes"] == int(counts[window].sum())
            assert w["motor_group_spikes"] == {k: int(counts[window, v].sum()) for k, v in motor.items()}
            assert w["unrealized_motor_command_counts"] == dict(Counter(commands[window*100:(window+1)*100]))
            assert w["actual_edge_visits"] == int(visits[window*100:(window+1)*100].sum())
            assert w["sampled_global_min_voltage_mv"] == min(s["global_voltage_min_mv"] for s in ss)
            assert w["sampled_global_max_voltage_mv"] == max(s["global_voltage_max_mv"] for s in ss)
            for key, value in window_table[trial_index*3+window].items():
                if key == "condition":
                    assert value == condition
                elif key == "seed":
                    assert int(value) == seed
                else:
                    assert float(value) == w[key], (key, value, w[key])
        assert trial["accepted_postsynaptic_updates"] is None
        all_commands.update(commands)
        all_middle_commands.update(commands[100:200])
        sampled_min = min(sampled_min, min(s["global_voltage_min_mv"] for s in samples))
        sampled_max = max(sampled_max, max(s["global_voltage_max_mv"] for s in samples))
        summaries.append({"seed": seed, "condition": condition, "samples_checked": len(samples),
            "all_spikes_checked": len(ticks), "requested_arrivals_checked": len(requested_tick),
            "applied_arrivals_checked": int(applied.sum()), "rejected_same_tick_arrivals": int((~applied).sum()),
            "pending_after_end_spikes": int((delivery_tick >= 15000).sum()), "all_delivered_edge_visits_checked": int(visits.sum()),
            "source_spikes_checked": int(is_source.sum()), "all_trial_checks_pass": True})
        paired[(seed, condition)] = {"requested_tick": requested_tick, "requested_column": requested_column,
            "spike_tick": ticks.copy(), "spike_index": indices.copy(), "source_digest": source_digest,
            "initial_rng": initial, "final_rng": boundaries[-1]}
    pairs = []
    for seed in plan["seeds"]:
        a, b = [paired[(seed, c)] for c in ("ethyl_acetate", "ethyl_acetate_source_outputs_blocked")]
        same(a["requested_tick"], b["requested_tick"])
        same(a["requested_column"], b["requested_column"])
        assert len({(paired[(seed, c)]["initial_rng"], paired[(seed, c)]["final_rng"]) for c in plan["conditions"]}) == 1
        baseline = paired[(seed, "constant_baseline")]
        for c in ("ethyl_acetate", "isoamyl_acetate"):
            other = paired[(seed, c)]
            for key in ("spike_tick", "spike_index"):
                same(baseline[key][baseline["spike_tick"] < 5000], other[key][other["spike_tick"] < 5000])
        pairs.append({"seed": seed, "EA_block_requested_events_exact": True, "all_conditions_rng_states_exact": True,
            "unblocked_baseline_prefix_all_spikes_exact": True,
            "EA_block_source_spike_lists_differ": a["source_digest"] != b["source_digest"]})
    assert all_commands == {"rest": 4374, "walk": 126} and all_middle_commands == {"rest": 1500}
    paths = [plan_path, report_path, environment_path, table_path, "scripts/review_or42a_summary.py", "validation/or42a-summary-ATTRIBUTION.md"]
    receipt = {"scope": "Independent all15 saved-trial review; pure Python RNG reconstruction, no neural/physics/policy reruns",
        "passed": True, "artifact_hashes": {p: sha(p) for p in paths}, "source_hashes_verified": plan["source_sha256"],
        "graph_sha256_recomputed": fingerprint.hexdigest(), "source_body_ids": ids[source_indices].tolist(),
        "source_sides": dict(Counter(neurons.iloc[source_indices].rootSide)), "source_nerve": "MxLbN", "first_hop_non_source_cells": len(hop),
        "archive_files": archive_files, "trials": summaries, "pairs": pairs,
        "all_sampled_commands": dict(all_commands), "all_middle_sampled_commands": dict(all_middle_commands),
        "sampled_global_min_mv": sampled_min, "sampled_global_max_mv": sampled_max,
        "source_review": {"input_semantics": "Listed36sources receive Bernoulli voltage arrivals with probability rate*.0001 each tick and default68.75mV increment. Sources have zero refractory interval, but are inactive during their own spike tick. Applied events are reconstructed from this active-mask rule, not instrumented kernel counters.",
            "RNG": "Independent64bit integer xorshift64* reconstruction from stored/SeedSequence initial state verifies all540000draws per trial, every1800draw interval endpoint and requested ordered event list. Producer shadow RNG did not mutate live state.",
            "delivery": "Presynaptic events enter source queue, deliver18ticks later, and are blocked at delivery by source mask. Per5ms visits independently reconstruct from full ordered spike events and CSR outdegree, including across500ms windows and excluding pending final deliveries. Visits do not establish accepted postsynaptic increments.",
            "source_outputs": "Only exactVM7d sources are passed to net.ablate; source spikes/incoming edges/direct excitation remain. Full blocked mask is not saved; source-code intervention and visit equality support this claim.",
            "motor": "Filtered motor diagnostic recomputed from complete spikes with false synthetic taste gates. Initial unblocked prefix equality explains the shared turn transient; no commands reached a body."},
        "limits": ["Configured excitation rates combine biological firing summaries from differing cohorts;149Hz and57.679Hz are engineering totals, not matched-cohort measured totals or clamped afferent firing.",
                   "Independent RNG reconstruction verifies arrivals, not actual membrane increments directly; applied masks rely on saved source-spike list and inspected kernel scheduling.",
                   "All spike times are retained as integer0.1ms ticks. Floating millisecond batch values and per-interval drive/refractory/current arrays are not separately stored; their exact contract is source-reviewed producer evidence.",
                   "Intermediate complete voltage/synaptic arrays are not stored. Per5ms finite flags/extrema are producer observations; final full arrays are independently checked. Extrema are sampled boundaries, not continuous-time extrema.",
                   "No accepted-postsynaptic-update counts are available; edge visits include inactive targets and zero-weight edges.",
                   "No body, concentration mapping, odor plume, biological recovery, attraction, feeding, or learned held-out chemical prediction. Three simulation seeds are not three biological cohorts."]}
    (ROOT/"validation/or42a-summary-independent-review.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"passed": True, "trials": len(summaries), "samples": sum(x["samples_checked"] for x in summaries),
                      "sampled_min_mv": sampled_min, "sampled_max_mv": sampled_max, "commands": dict(all_commands)}, indent=2))


if __name__ == "__main__":
    main()
