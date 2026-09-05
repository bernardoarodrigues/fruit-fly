#!/usr/bin/env python3
"""Audit retained Or42a artifacts for recurrent comparison; no neural execution."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/inhibitory-recurrent-input-audit.json"
PLAN = ROOT / "validation/or42a-summary-plan.json"
CONDITIONS = ("no_input", "constant_baseline", "ethyl_acetate", "isoamyl_acetate", "ethyl_acetate_source_outputs_blocked")
MATCHED = ("constant_baseline", "ethyl_acetate", "isoamyl_acetate")
KEYS = ("source_body_ids", "source_graph_indices", "all_spike_graph_indices", "all_spike_ticks",
        "requested_arrival_ticks", "requested_arrival_source_column", "applied_direct_voltage_arrival",
        "all_neuron_window_spike_counts", "source_spike_ticks", "source_spike_body_ids", "final_voltage_mv",
        "final_synaptic_mv", "initial_rng_state", "final_rng_state", "reconstructed_edge_visits_by5ms", "actual_edge_visits_by5ms")
SAMPLE_KEYS = {"chunk", "start_tick", "end_tick", "window", "rate_hz", "rng_before", "rng_after", "rng_draws",
               "requested_arrivals", "applied_direct_voltage_arrivals", "same_tick_spike_rejected_arrivals",
               "actual_source_spikes", "all_spikes", "actual_edge_visits", "global_voltage_min_mv", "global_voltage_max_mv",
               "source_voltage_min_mv", "source_voltage_max_mv", "all_state_finite", "motor_rates_hz", "unrealized_motor_command"}
R = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(), "checks": [], "inputs": {}, "trials": [],
     "prefix_pairs": [], "errors": [], "neural_execution": False, "duplicate_arrays_written": False,
     "larger_rolling_spike_archive_opened": False,
     "method": "Saved Or42a data only; independent integer xorshift64* reconstruction, graph joins and per-window/per-sample spike/event counts. No engine/producer import or execution.",
     "limits": [
         "50 ms has no complete retained v/s checkpoint. Prefix parity can compare exact spikes, candidates/applied flags, 10 five-ms samples and reconstructible pending/last-spike identities; it cannot establish full 50 ms state parity from old artifacts.",
         "1500 ms has full voltage and synaptic arrays, but no stored complete last-spike, refractory, current, source mask or pending checkpoint. Last-spike/pending identities can be reconstructed from complete spikes; configured current/mask/refractory semantics rely on frozen source and reported drive checks.",
         "Applied-arrival flags are inferred from candidate events and same-tick source spikes under the inspected zero-source-refractory C0 schedule, not instrumented direct voltage writes. Altered arms must derive their own eligibility from fixed candidates.",
         "Per-five-ms finite flags and extrema are producer observations; internal per-tick extrema and intermediate complete state arrays are unavailable. Finite is not physiologically plausible.",
         "Edge visits include inactive postsynaptic targets and zero-weight edges. Accepted postsynaptic increments are not recorded.",
         "Result.json hashes are newly recorded and their complete JSON values match the historically retained outer trial records; older receipts independently pin trace.npz and samples.jsonl, not separate result.json bytes.",
         "Only three positive-baseline unblocked conditions have identical prefixes; zero-Hz no_input is excluded. The blocked condition shares candidates/RNG but may have different recurrent output.",
         "Excitation-event rates combine different biological summaries and are not clamped source firing rates. Three simulation seeds are not biological replicates. This audit provides no body or physiology validation."]}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path):
    path = Path(path); key = str(path.relative_to(ROOT))
    if key not in R["inputs"]:
        R["inputs"][key] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    return R["inputs"][key]


def read(path):
    record(path)
    return json.loads(Path(path).read_text())


def ck(name, value):
    R["checks"].append({"name": name, "passed": bool(value)})


def exact(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def array_hash(a):
    return hashlib.sha256(a.tobytes()).hexdigest()


def uniforms(seed):
    # Pure Python integer arithmetic, independently applying uint64 wrapping.
    initial = int(np.random.SeedSequence(seed).generate_state(1, dtype=np.uint64)[0]) or 1
    state, mask = initial, (1 << 64) - 1
    u = np.empty(540000, dtype=np.float64); boundaries = []
    for k in range(len(u)):
        state ^= state >> 12
        state ^= (state << 25) & mask
        state ^= state >> 27
        u[k] = (((state * 2685821657736338717) & mask) >> 11) / float(1 << 53)
        if (k + 1) % 1800 == 0:
            boundaries.append(state)
    return initial, u.reshape(15000, 36), boundaries


def main():
    plan = read(PLAN); result = read(ROOT / "validation/or42a-summary-experiment.json")
    prior = read(ROOT / "validation/or42a-summary-independent-review.json")
    ck("frozen_plan_hash", sha(PLAN) == result["plan_sha256"] == "32a0f8f33d61b532c871a025b975945c7d79530d123b4ee5f7753ea54a0dd41e")
    ck("complete_15_trials", result["complete"] and len(result["trials"]) == 15 and all(result["checks"].values()) and prior["passed"])
    ck("design_clock_and_seeds", plan["seeds"] == [11, 12, 13] and plan["condition_order"] == list(CONDITIONS) and plan["duration_ms"] == 1500 and plan["sample_interval_ms"] == 5 and plan["window_edges_ms"] == [0, 500, 1000, 1500])
    for name, expected in {**plan["source_sha256"], **prior["artifact_hashes"]}.items():
        ck("frozen:" + name, record(ROOT / name)["sha256"] == expected)
    graph = ROOT / "data/processed/malecns_v1"
    arrays = {}
    fingerprint = hashlib.sha256()
    for name in ("neuron_ids", "indptr", "targets", "weights"):
        record(graph / (name + ".npy")); a = np.load(graph / (name + ".npy"), mmap_mode="r")
        arrays[name] = a; fingerprint.update(str(a.shape).encode()); fingerprint.update(memoryview(a).cast("B"))
    ids, ptr, dest = arrays["neuron_ids"], arrays["indptr"], arrays["targets"]
    neurons = pd.read_feather(graph / "neurons.feather")
    ck("graph_and_metadata_identity", fingerprint.hexdigest() == plan["graph_sha256"] == prior["graph_sha256_recomputed"] and len(ids) == plan["neurons"] == 166700 and len(dest) == plan["edges"] == 25582938 and np.array_equal(ids, neurons.bodyId.to_numpy()))
    sources = np.flatnonzero(neurons.type.eq("ORN_VM7d")).astype(np.int32)
    sources = sources[np.argsort(ids[sources])]
    first = np.setdiff1d(np.unique(np.concatenate([dest[ptr[s]:ptr[s + 1]] for s in sources])), sources)
    ck("exact36_ordered_sources", len(sources) == 36 and np.array_equal(sources, plan["source_graph_indices"]) and np.array_equal(ids[sources], plan["source_body_ids"]))
    ck("source_side_nerve_identity", Counter(neurons.iloc[sources].rootSide) == {"L": 18, "R": 18} and neurons.iloc[sources].rootSide.tolist() == plan["source_sides"] and neurons.iloc[sources].entryNerve.tolist() == plan["source_nerves"] == ["MxLbN"] * 36)
    ck("exact365_first_hop", len(first) == 365 and np.array_equal(ids[first], plan["first_hop_body_ids"]))
    motor = {}
    for group, types, side in (("forward", ["DNg97"], None), ("turn_left", ["DNa01", "DNa02"], "L"), ("turn_right", ["DNa01", "DNa02"], "R"), ("feeding", ["MN9"], None), ("escape", ["DNp01"], None)):
        selected = neurons.type.isin(types)
        if side:
            selected &= neurons.rootSide.fillna(neurons.somaSide).eq(side)
        motor[group] = np.flatnonzero(selected).astype(np.int32)
    ck("exact_current_default_motor_groups", {k: ids[v].tolist() for k, v in motor.items()} == plan["motor_groups"] and sum(map(len, motor.values())) == 10)
    ck("no_source_motor_overlap", not np.intersect1d(sources, np.concatenate(list(motor.values()))).size)
    ck("source_drive_contract", plan["drive"] == {"rates_explicit_including_zero": True, "current_mv": None, "poisson_weight_mv": None, "disable_refractory": True, "ordering": "Ascending numeric source body IDs, all36 in every interval and control"})
    R["graph"] = {"sha256": fingerprint.hexdigest(), "neurons": len(ids), "edges": len(dest),
        "source_body_ids": ids[sources].tolist(), "source_graph_indices": sources.tolist(), "first_hop_body_ids": ids[first].tolist(),
        "motor_groups": plan["motor_groups"], "motor_grooming_enabled": False, "source_count": 36, "first_hop_count": 365,
        "source_side_counts": dict(Counter(neurons.iloc[sources].rootSide)), "source_nerve": "MxLbN"}
    R["parameters"] = plan["parameters"]
    source_column = np.full(len(ids), -1, dtype=np.int32); source_column[sources] = np.arange(36)
    degree = np.diff(ptr); total_spikes = 0; prefixes = {}; rng_summary = {}
    for seed in plan["seeds"]:
        initial, u, boundaries = uniforms(seed)
        rng_summary[str(seed)] = {"initial": initial, "after_50ms": boundaries[9], "after_1500ms": boundaries[-1], "draws_50ms": 18000, "draws_1500ms": 540000}
        for condition in CONDITIONS:
            label = f"seed{seed}:{condition}"
            trial = next(t for t in result["trials"] if t["seed"] == seed and t["condition"] == condition)
            folder = ROOT / trial["run_dir"]
            saved = read(folder / "result.json")
            ck(label + ":result_exact_outer_record", saved == trial and trial["complete"] and trial["error"] is None and all(trial["checks"].values()))
            for name in ("trace.npz", "samples.jsonl"):
                path = folder / name; meta = record(path)
                ck(label + ":artifact:" + name, meta == trial["files"][name] and meta["sha256"] == prior["archive_files"][str(path.relative_to(ROOT))])
            with np.load(folder / "trace.npz", allow_pickle=False) as z:
                d = {k: z[k] for k in z.files}
            samples = [json.loads(line) for line in (folder / "samples.jsonl").read_text().splitlines()]
            i, t = d["all_spike_graph_indices"], d["all_spike_ticks"]
            at, ac, applied = d["requested_arrival_ticks"], d["requested_arrival_source_column"], d["applied_direct_voltage_arrival"]
            count, arrivals, srcspikes = len(i), len(at), len(d["source_spike_ticks"])
            spec = {"source_body_ids": ((36,), "int64"), "source_graph_indices": ((36,), "int32"),
                    "all_spike_graph_indices": ((count,), "int32"), "all_spike_ticks": ((count,), "int64"),
                    "requested_arrival_ticks": ((arrivals,), "int64"), "requested_arrival_source_column": ((arrivals,), "int64"), "applied_direct_voltage_arrival": ((arrivals,), "bool"),
                    "all_neuron_window_spike_counts": ((3, len(ids)), "int64"), "source_spike_ticks": ((srcspikes,), "int64"), "source_spike_body_ids": ((srcspikes,), "int64"),
                    "final_voltage_mv": ((len(ids),), "float64"), "final_synaptic_mv": ((len(ids),), "float64"),
                    "initial_rng_state": ((1,), "uint64"), "final_rng_state": ((1,), "uint64"),
                    "reconstructed_edge_visits_by5ms": ((300,), "int64"), "actual_edge_visits_by5ms": ((300,), "int64")}
            ck(label + ":trace_schema", tuple(d) == KEYS and all(d[k].shape == shape and str(d[k].dtype) == dtype for k, (shape, dtype) in spec.items()))
            ck(label + ":sample_schema_clock", len(samples) == 300 and all(set(s) == SAMPLE_KEYS and s["chunk"] == k and s["start_tick"] == k * 50 and s["end_tick"] == (k + 1) * 50 and s["window"] == k // 100 for k, s in enumerate(samples)))
            ck(label + ":source_identity", exact(d["source_graph_indices"], sources) and np.array_equal(d["source_body_ids"], ids[sources]))
            ck(label + ":spike_ranges_order_unique", np.all((0 <= i) & (i < len(ids))) and np.all((0 <= t) & (t < 15000)) and np.all((np.diff(t) > 0) | ((np.diff(t) == 0) & (np.diff(i) > 0))))
            rates = np.repeat(plan["conditions"][condition], 5000)
            expected_t, expected_c = np.nonzero(u < rates[:, None] * .1 / 1000.)
            ck(label + ":all_candidate_events_from_RNG", exact(at, expected_t.astype(np.int64)) and exact(ac, expected_c.astype(np.int64)))
            ck(label + ":RNG_all_boundaries", int(d["initial_rng_state"][0]) == trial["initial_rng_state"] == initial and int(d["final_rng_state"][0]) == trial["final_rng_state"] == boundaries[-1] and trial["rng_draws"] == 540000 and all(s["rng_before"] == (initial if k == 0 else boundaries[k - 1]) and s["rng_after"] == boundaries[k] and s["rng_draws"] == 1800 for k, s in enumerate(samples)))
            src = source_column[i] >= 0
            ck(label + ":source_spike_arrays", exact(d["source_spike_ticks"], t[src]) and exact(d["source_spike_body_ids"], np.asarray(ids[i[src]])))
            fired_source = np.zeros((15000, 36), dtype=bool); fired_source[t[src], source_column[i[src]]] = True
            ck(label + ":applied_C0_candidate_partition", exact(applied, ~fired_source[at, ac]))
            ck(label + ":candidate_and_source_hashes", hashlib.sha256(at.astype('<i8').tobytes() + ac.astype('<i8').tobytes()).hexdigest() == trial["requested_arrival_sha256"] and hashlib.sha256(t[src].astype('<i8').tobytes() + ids[i[src]].astype('<i8').tobytes()).hexdigest() == trial["actual_source_spike_sha256"])
            counts = np.zeros((3, len(ids)), dtype=np.int64); np.add.at(counts, (t // 5000, i), 1)
            ck(label + ":all_window_counts", exact(counts, d["all_neuron_window_spike_counts"]))
            delivered = t + 18 < 15000
            if condition.endswith("outputs_blocked"):
                delivered &= ~src
            visits = np.zeros(300, dtype=np.int64); np.add.at(visits, (t[delivered] + 18) // 50, degree[i[delivered]])
            ck(label + ":all_delayed_edge_visits", exact(visits, d["actual_edge_visits_by5ms"]) and exact(visits, d["reconstructed_edge_visits_by5ms"]))
            chunks = {"all_spikes": np.bincount(t // 50, minlength=300), "actual_source_spikes": np.bincount(t[src] // 50, minlength=300),
                      "requested_arrivals": np.bincount(at // 50, minlength=300), "applied_direct_voltage_arrivals": np.bincount(at[applied] // 50, minlength=300),
                      "same_tick_spike_rejected_arrivals": np.bincount(at[~applied] // 50, minlength=300), "actual_edge_visits": visits}
            ck(label + ":all_sample_event_counts_rates", all(np.array_equal(values, [s[k] for s in samples]) for k, values in chunks.items()) and all(s["rate_hz"] == plan["conditions"][condition][k // 100] for k, s in enumerate(samples)))
            ck(label + ":window_source_firsthop_motor_counts", all(w["all_spikes"] == int(counts[k].sum()) and w["non_source_spikes"] == int(counts[k].sum() - counts[k, sources].sum()) and w["actual_source_spikes"] == int(counts[k, sources].sum()) and w["actual_source_counts_by_body_id_order"] == counts[k, sources].tolist() and w["first_hop_non_source_spikes"] == int(counts[k, first].sum()) and w["motor_group_spikes"] == {g: int(counts[k, group].sum()) for g, group in motor.items()} for k, w in enumerate(trial["windows"])))
            ck(label + ":final_full_state_and_last_sample_extrema", np.isfinite(d["final_voltage_mv"]).all() and np.isfinite(d["final_synaptic_mv"]).all() and float(d["final_voltage_mv"].min()) == samples[-1]["global_voltage_min_mv"] and float(d["final_voltage_mv"].max()) == samples[-1]["global_voltage_max_mv"] and float(d["final_voltage_mv"][sources].min()) == samples[-1]["source_voltage_min_mv"] and float(d["final_voltage_mv"][sources].max()) == samples[-1]["source_voltage_max_mv"] and all(s["all_state_finite"] for s in samples))
            if condition == "no_input":
                ck(label + ":zero_control", count == arrivals == 0 and np.all(d["final_voltage_mv"] == -52.) and not np.any(d["final_synaptic_mv"]))
            prefix_i, prefix_t = i[t < 500], t[t < 500]
            prefix_a = at < 500
            pending = (prefix_t + 18) >= 500
            prefix = {"spike_indices": prefix_i.copy(), "spike_ticks": prefix_t.copy(), "candidate_ticks": at[prefix_a].copy(), "candidate_columns": ac[prefix_a].copy(), "applied_flags": applied[prefix_a].copy(), "samples": samples[:10]}
            prefixes[seed, condition] = prefix
            item = {"seed": seed, "condition": condition, "run_dir": trial["run_dir"], "spikes": count, "candidate_arrivals": arrivals, "applied_arrivals": int(applied.sum()), "samples": len(samples),
                "initial_rng_state": initial, "final_rng_state": boundaries[-1],
                "prefix_50ms": {"spikes": len(prefix_i), "source_spikes": int(np.sum(source_column[prefix_i] >= 0)), "candidate_arrivals": int(prefix_a.sum()), "applied_arrivals": int(applied[prefix_a].sum()), "rng_state": samples[9]["rng_after"],
                    "ordered_spike_indices_sha256": array_hash(prefix_i), "ordered_spike_ticks_sha256": array_hash(prefix_t), "pending_source_events": int(pending.sum()),
                    "pending_indices_sha256": array_hash(prefix_i[pending]), "pending_delivery_ticks_sha256": array_hash(prefix_t[pending] + 18), "last_sample": samples[9]},
                "final_voltage_sha256": array_hash(d["final_voltage_mv"]), "final_synaptic_sha256": array_hash(d["final_synaptic_mv"])}
            R["trials"].append(item); total_spikes += count
            print(label, "audited", flush=True)
        reference = prefixes[seed, MATCHED[0]]
        for condition in MATCHED[1:]:
            other = prefixes[seed, condition]
            equal = all(reference[k] == other[k] if k == "samples" else exact(reference[k], other[k]) for k in reference)
            ck(f"seed{seed}:50ms_identical_positive_unblocked:{condition}", equal)
            R["prefix_pairs"].append({"seed": seed, "reference": MATCHED[0], "condition": condition, "all_spikes_candidates_applied_and10_samples_exact": equal})
        blocked = prefixes[seed, CONDITIONS[-1]]
        ck(f"seed{seed}:50ms_blocked_same_candidates", exact(reference["candidate_ticks"], blocked["candidate_ticks"]) and exact(reference["candidate_columns"], blocked["candidate_columns"]))
    R["rng_states"] = rng_summary; R["all_spikes_inspected"] = total_spikes
    R["prefix_probe_reference"] = next(t for t in R["trials"] if t["seed"] == 11 and t["condition"] == "constant_baseline")
    ck("all15_exact_trial_identities", {(t["seed"], t["condition"]) for t in R["trials"]} == {(s, c) for s in (11, 12, 13) for c in CONDITIONS})
    ck("inputs_unchanged_at_completion", all(sha(ROOT / p) == meta["sha256"] for p, meta in R["inputs"].items()))


if __name__ == "__main__":
    if OUT.exists():
        raise FileExistsError("Preserve prior audit")
    record(Path(__file__).resolve())
    try:
        main()
    except Exception as exc:
        R["errors"].append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    R["completed_utc"] = datetime.now(timezone.utc).isoformat()
    R["check_count"] = len(R["checks"])
    R["passed"] = not R["errors"] and bool(R["checks"]) and all(c["passed"] for c in R["checks"])
    OUT.write_text(json.dumps(R, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": R["passed"], "checks": R["check_count"], "failures": [c["name"] for c in R["checks"] if not c["passed"]], "errors": R["errors"]}), flush=True)
    raise SystemExit(0 if R["passed"] else 1)
