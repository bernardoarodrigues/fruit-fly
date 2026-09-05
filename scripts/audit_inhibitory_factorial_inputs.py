#!/usr/bin/env python3
"""Audit retained factorial inputs; no simulator imports or state integration.

Only compact replay NPZs and final checkpoints are decompressed. Full original
spike/journal archives are hashed as compressed bytes and otherwise left closed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GRAPH = Path("data/processed/malecns_v1")
RUN = Path("runs/flybody-rolling-loop-3e5ca3ca6c91")
PREFIX = "validation/negative-voltage-replay"
CONDITIONS = ("locomotor_feedback", "locomotor_sensory_block", "sensory_only")
TARGET_IDS = np.array([67052, 13314], dtype=np.int64)


def sha(path):
    h = hashlib.sha256()
    with (ROOT / path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads((ROOT / path).read_text())


def descriptor(array):
    return {"shape": list(array.shape), "dtype": array.dtype.str,
            "c_order_bytes_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def audit(report):
    checks = report["checks"]

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        if not passed:
            raise ValueError(name)

    def receipt(path, expected=None):
        path = str(path)
        actual = {"sha256": sha(path), "bytes": (ROOT / path).stat().st_size}
        report["inputs"][path] = {**actual, "expected": expected}
        if expected is not None:
            check("source receipt: " + path, actual == expected)
        return actual

    plan = read_json(PREFIX + "-plan.json")
    old = read_json(PREFIX + "-results.json")
    review = read_json(PREFIX + "-independent-review.json")
    rolling = read_json("validation/flybody-rolling-loop/plan.json")
    receipt(PREFIX + "-plan.json")
    receipt(PREFIX + "-independent-review.json")
    receipt("scripts/audit_inhibitory_factorial_inputs.py")
    old_expected = review["inputs"][PREFIX + "-results.json"]
    receipt(PREFIX + "-results.json", {"sha256": old_expected["expected_sha256"], "bytes": old_expected["bytes"]})
    check("original producer and independent review passed", old["passed"] and review["passed"]
          and all(c["pass"] for c in old["checks"]) and all(c["passed"] for c in review["checks"]))
    check("original plan hash agrees with both receipts", sha(PREFIX + "-plan.json") == old["plan_sha256"] == review["plan_sha256"])
    check("original graph and clock agree", plan["graph_sha256"] == rolling["graph_sha256"]
          and plan["parameters"] == rolling["neural_parameters"]
          and plan["neural_ticks"] == 120000 and plan["coupling_intervals"] == 6000
          and plan["parameters"]["dt_ms"] == .1 and plan["parameters"]["delay_ms"] == 1.8
          and plan["parameters"]["refractory_ms"] == 2.2)
    paths = ["scripts/negative-voltage-replay.py", "validation/flybody-rolling-loop/plan.json"]
    paths += [str(GRAPH / (name + suffix)) for name, suffix in (
        ("manifest", ".json"), ("neurons", ".feather"), ("neuron_ids", ".npy"),
        ("indptr", ".npy"), ("targets", ".npy"), ("weights", ".npy"),
        ("contact_counts", ".npy"), ("signs", ".npy"))]
    for path in paths:
        receipt(path, plan["inputs"][path])
    receipt("scripts/review_negative_voltage_replay.py")
    check("original reviewer source hash", sha("scripts/review_negative_voltage_replay.py") == review["reviewer_sha256"])
    edge_path = PREFIX + "-incoming-edges.csv"
    receipt(edge_path, old["artifacts"][edge_path])
    edges = pd.read_csv(ROOT / edge_path, float_precision="round_trip")
    ids, indptr, graph_targets, weights, contacts, signs = [
        np.load(ROOT / GRAPH / (name + ".npy"), mmap_mode="r", allow_pickle=False)
        for name in ("neuron_ids", "indptr", "targets", "weights", "contact_counts", "signs")]
    annotations = pd.read_feather(ROOT / GRAPH / "neurons.feather")
    ti = np.searchsorted(ids, TARGET_IDS)
    check("graph identities and target order", np.array_equal(ids[ti], TARGET_IDS)
          and np.array_equal(annotations.bodyId, ids)
          and annotations.iloc[ti].type.tolist() == ["lLN2T_b", "M_vPNml50"])
    check("graph CSR shapes", len(indptr) == len(ids) + 1 and indptr[0] == 0
          and indptr[-1] == len(weights) == len(graph_targets) == len(contacts)
          and bool((np.diff(indptr) >= 0).all()) and weights.dtype.str == "<f4")
    graph_edges = np.concatenate([np.flatnonzero(graph_targets == index) for index in ti])
    slots = np.concatenate([np.full(np.count_nonzero(graph_targets == index), j) for j, index in enumerate(ti)])
    sources = np.searchsorted(indptr, graph_edges, side="right") - 1
    expected = {"row": np.arange(len(edges)), "graph_edge_index": graph_edges,
                "source_index": sources, "source_id": ids[sources], "target_slot": slots,
                "target_index": ti[slots], "target_id": TARGET_IDS[slots],
                "contacts": contacts[graph_edges], "source_model_sign": signs[sources]}
    for column, values in expected.items():
        check("complete ordered edge column: " + column, np.array_equal(edges[column], values))
    for column, ann_column, missing in (("source_type", "type", "[untyped]"),
            ("source_class", "class", "[unassigned]"), ("source_superclass", "superclass", None),
            ("source_consensus_nt", "consensus_nt", "unknown")):
        values = annotations.iloc[sources][ann_column]
        if missing is not None:
            values = values.fillna(missing)
        check("source annotation: " + column, values.tolist() == edges[column].tolist())
    check("target type annotations", edges.target_type.tolist() == [plan["target_types"][j] for j in slots])
    check("unique source/target edges", not edges.duplicated(["source_index", "target_slot"]).any())
    raw_weights = b"".join(bytes.fromhex(x) for x in edges.weight_float32_hex)
    decoded_weights = np.frombuffer(raw_weights, dtype="<f4")
    check("float32 weight hex bytes match graph", raw_weights == np.asarray(weights[graph_edges]).tobytes())
    check("decimal weight round trip and exact float64 promotion", np.array_equal(edges.weight_mv, decoded_weights.astype(np.float64)))
    check("weights match original sign/contact normalization", np.array_equal(decoded_weights,
          contacts[graph_edges].astype(np.float32) * np.float32(.275) * signs[sources]))
    mapping = np.full((len(ids), 2), -1, dtype=np.int32)
    mapping[sources, slots] = np.arange(len(edges), dtype=np.int32)
    needed = (mapping >= 0).any(axis=1)
    report["graph"] = {"graph_sha256": plan["graph_sha256"], "neurons": len(ids),
        "directed_pairs": len(weights), "targets": [{"slot": j, "id": int(target), "graph_index": int(ti[j]),
        "incoming_edges": int((slots == j).sum()), "contacts": int(contacts[graph_edges[slots == j]].sum()),
        "zero_weight_edges": int((decoded_weights[slots == j] == 0).sum())} for j, target in enumerate(TARGET_IDS)],
        "unique_relevant_sources": int(needed.sum()), "source_mapping": descriptor(mapping),
        "weight_float32_bytes_sha256": hashlib.sha256(raw_weights).hexdigest(),
        "self_or_cross_target_edges": edges[edges.source_id.isin(TARGET_IDS)].to_dict("records"),
        "edge_inventory_order": "Target-major [67052, 13314]; increasing original CSR edge index within each target",
        "potential_delivery_order": "Original source-event order, then target slot 0 followed by 1 where an edge exists; each target retains its original source order"}
    old_conditions = {c["condition"]: c for c in old["conditions"]}
    review_conditions = {c["condition"]: c for c in review["conditions"]}
    reviewed = {c["name"]: c["passed"] for c in review["checks"]}
    report["clock"] = {"dt_ms": .1, "neural_ticks": 120000, "delay_ticks": 18,
        "refractory_ticks": 22, "sample_count": 120001, "seed": rolling["seed"]}
    for name in CONDITIONS:
        folder = RUN / name
        summary_path = str(folder / "condition-summary.json")
        checkpoint_path = str(folder / "brain-final-or-failure.npz")
        for path in (summary_path, checkpoint_path, str(folder / "events.jsonl.gz"), str(folder / "spikes.bin.gz")):
            receipt(path, plan["inputs"][path])
        summary = read_json(summary_path)
        check(name + ": original condition design", summary["design"] == next(c for c in rolling["conditions"] if c["name"] == name))
        check(name + ": original completion", summary["complete"] and summary["all_condition_gates_pass"]
              and summary["completed_physical_ticks"] == 6000 and not summary["failures"])
        mask = np.zeros(len(ids), dtype=np.bool_)
        group_counts = {}
        for group, row in summary["groups"].items():
            indices = np.asarray(row["indices"], dtype=np.int64)
            check(name + ": group identity: " + group, np.array_equal(ids[indices], row["neuron_ids"]))
            group_counts[group] = len(indices)
            if group in summary["design"]["outgoing_blocks"]:
                mask[indices] = True
        for filename in ("events.jsonl.gz", "spikes.bin.gz", "brain-final-or-failure.npz"):
            check(name + ": summary source receipt: " + filename,
                  {k: summary["files"][filename][k] for k in ("sha256", "bytes")} == plan["inputs"][str(folder / filename)])
        with np.load(ROOT / checkpoint_path, allow_pickle=False) as checkpoint:
            meta = json.loads(str(checkpoint["metadata"]))
            check(name + ": checkpoint clock/graph/parameters", meta["tick"] == 120000
                  and meta["graph_sha256"] == plan["graph_sha256"] and meta["parameters"] == plan["parameters"])
            check(name + ": entire reconstructed source-output mask", np.array_equal(mask, checkpoint["ablated"]))
            check(name + ": final target no-direct-drive and refractory evidence",
                  not np.isin(ti, checkpoint["previous_drive"]).any()
                  and np.array_equal(checkpoint["current_mv"][ti], [0., 0.])
                  and np.array_equal(checkpoint["refractory_ticks"][ti], [22, 22]))
            npz_path = PREFIX + "-" + name + "-arrays.npz"
            balance_path = PREFIX + "-" + name + "-edge-balance.csv"
            for path in (npz_path, balance_path):
                receipt(path, old["artifacts"][path])
            balance = pd.read_csv(ROOT / balance_path, float_precision="round_trip")
            for column in edges.columns:
                check(name + ": balance inventory: " + column, edges[column].equals(balance[column]))
            with np.load(ROOT / npz_path, allow_pickle=False) as data:
                src = data["recorded_source_indices"]
                ticks = data["recorded_source_spike_ticks"]
                check(name + ": source array shape/type", src.dtype.str == ticks.dtype.str == "<i4" and src.ndim == 1 and src.shape == ticks.shape)
                check(name + ": source IDs in complete incoming set", bool(((src >= 0) & (src < len(ids))).all()) and bool(needed[src].all()))
                check(name + ": source ticks range and nondecreasing order", bool(((ticks >= 0) & (ticks < 120000)).all()) and bool((np.diff(ticks) >= 0).all()))
                check(name + ": compact array target order and clock", np.array_equal(data["target_ids"], TARGET_IDS)
                      and np.array_equal(data["sample_time_ms"], np.arange(120001) * .1))
                check(name + ": source count against original receipts", len(src) == old_conditions[name]["recorded_relevant_source_events"] == review_conditions[name]["relevant_source_spikes"])
                for field in ("voltage_mv", "synaptic_mv"):
                    check(name + ": retained endpoint against checkpoint: " + field,
                          data[field][-1].tobytes() == checkpoint[field][ti].tobytes()
                          and data["checkpoint_selected_" + field].tobytes() == checkpoint[field][ti].tobytes())
                recorded = [data[f"recorded_target{j}_spike_ticks"] for j in range(2)]
                check(name + ": saved emitted decisions agree with target records", all(
                    np.array_equal(np.flatnonzero(data["emitted_spikes_by_tick"][:, j]), recorded[j]) for j in range(2)))
                # Expand source events to potential target-edge deliveries only in memory.
                candidates = mapping[src].ravel()
                exists = candidates >= 0
                candidate_ticks = np.repeat(ticks.astype(np.int64) + 18, 2)[exists]
                candidate_edges = candidates[exists]
                candidate_sources = sources[candidate_edges]
                candidate_slots = slots[candidate_edges]
                # Baseline disposition uses retained spikes; no voltage/state integration.
                future = candidate_ticks >= 120000
                blocked = ~future & mask[candidate_sources]
                unavailable = np.zeros(len(candidate_edges), dtype=np.bool_)
                for j in range(2):
                    select = candidate_slots == j
                    last = np.r_[np.int64(-2**60), recorded[j].astype(np.int64)]
                    pos = np.searchsorted(recorded[j], candidate_ticks[select], side="right")
                    unavailable[select] = candidate_ticks[select] - last[pos] < 22
                unavailable &= ~future & ~blocked
                accepted = ~future & ~blocked & ~unavailable
                check(name + ": ordered baseline accepted ticks and edges",
                      np.array_equal(candidate_ticks[accepted], data["accepted_delivery_ticks"])
                      and np.array_equal(candidate_edges[accepted], data["accepted_edge_rows"]))
                categories = {"accepted_events": accepted, "source_blocked_events": blocked,
                              "target_unavailable_events": unavailable, "beyond_horizon_events": future}
                for column, selected in categories.items():
                    check(name + ": per-edge disposition: " + column,
                          np.array_equal(np.bincount(candidate_edges[selected], minlength=len(edges)), balance[column]))
                check(name + ": each potential delivery classified once", np.array_equal(
                    np.bincount(src, minlength=len(ids))[sources], balance[list(categories)].sum(axis=1)))
                future_source = ticks.astype(np.int64) + 18 >= 120000
                boundaries = np.r_[0, np.cumsum(checkpoint["pending_count"])]
                for ring_slot in range(19):
                    expected_pending = src[future_source & ((ticks + 18) % 19 == ring_slot)]
                    actual_pending = checkpoint["pending"][boundaries[ring_slot]:boundaries[ring_slot + 1]]
                    actual_pending = actual_pending[needed[actual_pending]]
                    check(name + f": pending source order, ring slot {ring_slot}", np.array_equal(expected_pending, actual_pending))
                inherited = ["all-ordered-drives-and-block-metadata", "all-6000-spike-blocks-order-hashes-clocks",
                             "source-indices-from-original", "source-ticks-from-original"]
                check(name + ": full-archive proof retained in prior independent review", all(reviewed[name + ":" + k] for k in inherited))
                check(name + ": prior all-interval target exclusion", old_conditions[name]["selected_targets_in_any_input_list"] is False
                      and old_conditions[name]["source_blocked_count"] == int(mask.sum()))
                counts = {key: int(value.sum()) for key, value in categories.items()}
                check(name + ": delivery totals match prior independent review", counts == {
                    "accepted_events": review_conditions[name]["accepted_deliveries"],
                    "source_blocked_events": review_conditions[name]["source_blocked_deliveries"],
                    "target_unavailable_events": review_conditions[name]["unavailable_deliveries"],
                    "beyond_horizon_events": review_conditions[name]["beyond_horizon_deliveries"]})
                report["conditions"].append({"condition": name, "group_counts": group_counts,
                    "source_output_mask": {"blocked_groups": summary["design"]["outgoing_blocks"],
                        "count": int(mask.sum()), "blocked_indices": np.flatnonzero(mask).tolist(),
                        "blocked_neuron_ids": ids[mask].tolist(), **descriptor(mask)},
                    "raw_source_indices": descriptor(src), "raw_source_spike_ticks": descriptor(ticks),
                    "source_event_count": len(src), "minimum_spike_tick": int(ticks.min()), "maximum_spike_tick": int(ticks.max()),
                    "equal_tick_adjacent_events": int((np.diff(ticks) == 0).sum()),
                    "potential_edge_deliveries": len(candidate_edges), "delivery_counts": counts,
                    "zero_weight_potential_deliveries": int((decoded_weights[candidate_edges] == 0).sum()),
                    "baseline_unavailable_tick_edge_pairs": np.column_stack([candidate_ticks[unavailable], candidate_edges[unavailable]]).tolist(),
                    "future_relevant_source_events": int(future_source.sum()),
                    "input_list_union_count_from_prior_receipt": old_conditions[name]["input_list_union_count"],
                    "selected_targets_in_any_input_list_from_prior_receipt": False,
                    "inherited_full_archive_check_names": [name + ":" + k for k in inherited],
                    "per_target_delivery_counts": [{"target_id": int(TARGET_IDS[j]),
                        "potential": int((candidate_slots == j).sum()),
                        **{k: int((v & (candidate_slots == j)).sum()) for k, v in categories.items()}} for j in range(2)]})
    report["sufficient_for_conditional_factorial"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "validation/inhibitory-factorial-input-audit.json")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing audit receipt: " + str(args.output))
    report = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
        "method": "Read-only verification of retained source arrays, graph/weight identities, constant masks and baseline delivery bookkeeping; no state recurrence",
        "full_spike_or_journal_decompression": False, "model_execution": False,
        "duplicate_event_arrays_written": False, "inputs": {}, "checks": [], "conditions": [],
        "limits": [
            "Raw selected-source order and exclusion of direct target inputs across all 6000 intervals rely on the retained independent full-archive review and matching compressed-file hashes; not re-read here.",
            "The whole mask is reconstructed from the original constant condition design and group IDs and exactly matches the final checkpoint. Earlier journals recorded total blocked count and all-sensory flag, not a full membership bitset each interval.",
            "Baseline acceptance is reconstructed from saved target spikes only for input accounting. Changed arms must recompute their own threshold, refractory and acceptance decisions.",
            "Source events remain exogenous, including any target self/cross events. This does not support recurrent intervention predictions or physiological calibration.",
            "Beyond-horizon events are pending before any future mask/availability decision; motor readout muting is not neural output blocking."
        ]}
    try:
        audit(report)
    except Exception as error:
        report["failure"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    report["passed"] = not report.get("failure") and all(c["passed"] for c in report["checks"])
    report["check_count"] = len(report["checks"])
    report["completed_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"passed": report["passed"], "checks": report["check_count"], "output": str(args.output), "failure": report.get("failure")}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
