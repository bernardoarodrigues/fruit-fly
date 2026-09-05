#!/usr/bin/env python3
"""Replay only two target cells from frozen full-graph recorded spike streams.

No neural/body simulator is imported or rerun. Presynaptic events are replayed,
including any recorded spikes from the selected targets, rather than regenerated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import traceback

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "validation/negative-voltage-replay"
GRAPH = ROOT / "data/processed/malecns_v1"
RUN = ROOT / "runs/flybody-rolling-loop-3e5ca3ca6c91"
CONDITIONS = ("locomotor_feedback", "locomotor_sensory_block", "sensory_only")
TARGET_IDS = (67052, 13314)
SENSORY = ("odor", "sweet", "club")
BLOCK = struct.Struct("<QQdd")


def path(suffix):
    return Path(str(PREFIX)+suffix)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(p, obj):
    p.write_text(json.dumps(obj, indent=2, allow_nan=False)+"\n")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def source_paths():
    base = [Path(__file__).resolve(), ROOT/"fruitfly/neural.py", ROOT/"fruitfly/data.py",
            ROOT/"scripts/check_flybody_rolling_loop.py", ROOT/"scripts/check_flybody_loop.py",
            ROOT/"validation/flybody-rolling-loop/plan.json", ROOT/"validation/flybody-rolling-loop/results.json",
            ROOT/"validation/flybody-rolling-loop/independent-review.json", GRAPH/"manifest.json", GRAPH/"neurons.feather"]
    base += [GRAPH/(s+".npy") for s in ("neuron_ids", "indptr", "targets", "weights", "contact_counts", "signs")]
    for c in CONDITIONS:
        base += [RUN/c/f for f in ("condition-summary.json", "events.jsonl.gz", "spikes.bin.gz", "brain-final-or-failure.npz", "actual-state-before-cleanup.json")]
    return base


def prepare():
    if path("-plan.json").exists():
        raise FileExistsError("Preserve frozen plan")
    old = json.loads((ROOT/"validation/flybody-rolling-loop/plan.json").read_text())
    assert sha(ROOT/"fruitfly/neural.py") == old["source_sha256"]["fruitfly/neural.py"]
    plan = {"schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "inputs": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in source_paths()},
            "original_plan_sha256": sha(ROOT/"validation/flybody-rolling-loop/plan.json"),
            "graph_sha256": old["graph_sha256"], "parameters": old["neural_parameters"],
            "target_ids": TARGET_IDS, "target_types": ["lLN2T_b", "M_vPNml50"],
            "conditions": CONDITIONS, "neural_ticks": 120000, "coupling_intervals": 6000,
            "state_reconstruction": "Initialize only two targets at source reset (-52mV, g0, lastspike=-2**60), with no direct drive. Replay all direct incoming edges in recorded presynaptic order with18tick delay. First integrate available cells with exact source coefficient, threshold strictly>, mark newly fired unavailable, deliver unblocked events to available targets, reset v/g after delivery. Refractory22ticks, both states frozen while unavailable.",
            "recorded_input_checks": "Every actual neural_start list excludes both targets, current drive is null, ordered index/bodyID hash is valid. Source-output masks resolved per interval from recorded sensory-all-blocked flag plus total blocked count and condition group identities, checked against final checkpoint. Motor readout mute is not a source-output block.",
            "spike_checks": "Verify framed ordered spike bytes against each journaled full-event hash, exact0.1ms tick stamps and2ms block clocks. Keep source order, including selected target self/cross spikes as recorded external inputs. Compare predicted target spike ticks against complete recording.",
            "state_checks": {"primary": "bitwise float64 endpoint voltage and synaptic state, integer last-spike and refractory states", "diagnostic_absolute_tolerance_mv": 1e-9, "mismatch_policy": "Retain result and traces even if exact or tolerance checks fail; do not tune or replace inputs"},
            "balance": "All direct edge contact/NT/sign/weight rows; accepted, source-blocked, target-refractory/newly-fired-rejected, and beyond-horizon events per edge. Positive/negative accepted state jumps per tick and cumulatively; rank source type+NT+sign by cumulative accepted magnitude. Also calculate fixed-acceptance endpoint linear contributions after last target reset using analytic impulse response; this is conditional arithmetic, not intervention causality.",
            "endpoint_attribution": "For accepted jump at delivery tick d after final target reset, n=119999-d; g contribution=w*exp(-n*dt/tau_s), v-rest contribution=w*tau_s/(tau_m-tau_s)*(exp(-n*dt/tau_m)-exp(-n*dt/tau_s)). Accepted events cannot occur within final refractory interval; no later spike/reset. Check sums against replay states within1e-9mV.",
            "claim_limit": "Conditional numerical input-balance diagnostic only. Source spike generation is not recomputed; no biological cause, calibrated voltage, gain change or full-brain simulation claim."}
    write_json(path("-plan.json"), plan)
    print("Frozen plan sha256="+sha(path("-plan.json")), flush=True)


def journal_inputs(folder, summary, ids, target_indices, n_ticks):
    mask = np.zeros(len(ids), dtype=bool)
    for group in summary["design"]["outgoing_blocks"]:
        record = summary["groups"][group]
        index = np.asarray(record["indices"], dtype=int)
        assert np.array_equal(ids[index], record["neuron_ids"])
        mask[index] = True
    sensory = np.unique(np.concatenate([summary["groups"][g]["indices"] for g in SENSORY]))
    expected_all_sensory = bool(mask[sensory].all())
    start_ticks, complete_ticks, recorded_ticks = [], [], []
    hashes, block_counts, initials = [], [], []
    direct_list_union = set()
    # Decompress once; skip parsing unrelated large physical payloads.
    with gzip.open(folder/"events.jsonl.gz", "rb") as f:
        for line in f:
            if not any(tag in line[:160] for tag in (b'"event":"initial"', b'"event":"neural_start"', b'"event":"neural_complete"', b'"event":"ordered_spikes"')):
                continue
            row = json.loads(line)
            if row["event"] == "initial":
                initials.append(row)
                assert row["state"]["neural"]["voltage_mv"] == {"minimum": -52., "maximum": -52., "mean": -52.}
                assert row["state"]["neural"]["total_spikes"] == 0
            elif row["event"] == "neural_start":
                tick = row["tick"]; start_ticks.append(tick)
                drive = row["actual_drive"]
                assert drive["ordered_drive_sha256"] == hashlib.sha256(canonical({k:v for k,v in drive.items() if k!="ordered_drive_sha256"})).hexdigest()
                index = np.asarray(drive["indices"], dtype=int)
                assert np.array_equal(ids[index], drive["neuron_ids"])
                assert not np.isin(target_indices, index).any()
                assert drive["current_mv"] is None and drive["poisson_weight_mv"] is None
                direct_list_union.update(index.tolist())
                assert row["duration_ms"] == 2. and row["brain_t_ms"] == tick*2.
            elif row["event"] == "ordered_spikes":
                recorded_ticks.append(row["tick"])
                block_counts.append(row["events"])
                hashes.append(row["event_sha256"])
            elif row["event"] == "neural_complete":
                complete_ticks.append(row["tick"])
                assert row["blocked_neuron_count"] == int(mask.sum())
                assert row["sensory_outgoing_mask"] == expected_all_sensory
                assert row["full_event_sha256"] == hashes[-1]
                assert row["total_spikes"] == block_counts[-1]
    expected = list(range(n_ticks))
    assert start_ticks == complete_ticks == recorded_ticks == expected and len(initials)==1
    return mask, hashes, block_counts, sorted(direct_list_union)


def read_relevant_spikes(folder, ids, source_needed, target_indices, hashes, counts, original_plan_sha, graph_sha):
    source_events, stamp_events = [], []
    recorded_targets = [[], []]
    previous_tick = -1
    total_events = 0
    with gzip.open(folder/"spikes.bin.gz", "rb") as f:
        assert f.read(8) == b"FFSPK001"
        size_raw = f.read(4); assert len(size_raw)==4
        size = struct.unpack("<I", size_raw)[0]; assert size<65536
        header = json.loads(f.read(size))
        assert header["graph_sha256"] == graph_sha and header["plan_sha256"] == original_plan_sha
        for k in range(len(hashes)):
            raw = f.read(32); assert len(raw)==32
            block_tick, n, start, end = BLOCK.unpack(raw)
            assert (block_tick, n, start, end) == (k, counts[k], k*2., (k+1)*2.)
            raw_ids, raw_times = f.read(n*8), f.read(n*8)
            assert len(raw_ids)==len(raw_times)==n*8
            assert hashlib.sha256(struct.pack("<Q", n)+raw_ids+raw_times).hexdigest() == hashes[k]
            body_ids = np.frombuffer(raw_ids, dtype="<i8")
            times = np.frombuffer(raw_times, dtype="<f8")
            ticks = np.rint(times/.1).astype(np.int64)
            assert np.array_equal(ticks*.1, times)
            assert ((ticks>=k*20)&(ticks<(k+1)*20)).all()
            assert (np.diff(ticks)>=0).all()
            index = np.searchsorted(ids, body_ids)
            assert (index<len(ids)).all() and np.array_equal(ids[index], body_ids)
            if n:
                assert ticks[0]>=previous_tick
                same_time = ticks[1:]==ticks[:-1]
                assert (np.diff(index)[same_time]>0).all()
                previous_tick = ticks[-1]
            keep = source_needed[index]
            source_events.append(index[keep].astype(np.int32))
            stamp_events.append(ticks[keep].astype(np.int32))
            for j, target in enumerate(target_indices):
                recorded_targets[j].extend(ticks[index==target].tolist())
            total_events += n
        assert f.read(1)==b""
    return np.concatenate(source_events), np.concatenate(stamp_events), [np.asarray(x, dtype=np.int32) for x in recorded_targets], total_events


@njit(cache=True)
def replay(n_ticks, source_index, stamp_tick, source_to_edge, edge_target, weights, blocked, a, b, coefficient):
    v = np.full(2, -52., dtype=np.float64)
    g = np.zeros(2, dtype=np.float64)
    last = np.full(2, -(2**60), dtype=np.int64)
    trace_v = np.empty((n_ticks+1, 2), dtype=np.float64)
    trace_g = np.empty_like(trace_v)
    trace_v[0] = v; trace_g[0] = g
    spikes = np.zeros((n_ticks, 2), dtype=np.bool_)
    increments = np.zeros((n_ticks, 2, 2), dtype=np.float64)  # positive, negative
    accepted_counts = np.zeros(len(weights), dtype=np.int64)
    blocked_counts = np.zeros_like(accepted_counts)
    refractory_counts = np.zeros_like(accepted_counts)
    pending_counts = np.zeros_like(accepted_counts)
    accepted_tick = np.empty(len(source_index)*2, dtype=np.int32)
    accepted_edge = np.empty_like(accepted_tick)
    n_accepted = cursor = 0
    active = np.empty(2, dtype=np.bool_)
    for tick in range(n_ticks):
        for j in range(2):
            active[j] = tick-last[j] >= 22
            if active[j]:
                old_g = g[j]
                v[j] = -52. + (v[j]+52.)*a + old_g*coefficient + 0.*(1.-a)
                g[j] = old_g*b
                if v[j] > -45.:
                    spikes[tick, j] = True
                    last[j] = tick
                    active[j] = False
        while cursor<len(source_index) and stamp_tick[cursor]+18==tick:
            src = source_index[cursor]
            for j in range(2):
                edge = source_to_edge[src, j]
                if edge < 0:
                    continue
                if blocked[src]:
                    blocked_counts[edge] += 1
                elif not active[j]:
                    refractory_counts[edge] += 1
                else:
                    g[j] += weights[edge]
                    increments[tick, j, 0 if weights[edge]>=0 else 1] += weights[edge]
                    accepted_counts[edge] += 1
                    accepted_tick[n_accepted] = tick
                    accepted_edge[n_accepted] = edge
                    n_accepted += 1
            cursor += 1
        for j in range(2):
            if spikes[tick, j]:
                v[j] = -52.; g[j] = 0.
        trace_v[tick+1] = v; trace_g[tick+1] = g
    for k in range(cursor, len(source_index)):
        for j in range(2):
            edge = source_to_edge[source_index[k], j]
            if edge>=0:
                pending_counts[edge] += 1
    return (trace_v, trace_g, last, spikes, increments, accepted_counts, blocked_counts,
            refractory_counts, pending_counts, accepted_tick[:n_accepted], accepted_edge[:n_accepted])


def run():
    if path("-results.json").exists():
        raise FileExistsError("Preserve executed receipt")
    plan = json.loads(path("-plan.json").read_text())
    for name, record in plan["inputs"].items():
        assert sha(ROOT/name)==record["sha256"], name
    assert plan["parameters"] == {"dt_ms": .1, "resting_mv": -52., "reset_mv": -52., "threshold_mv": -45., "membrane_tau_ms": 20., "synapse_tau_ms": 5., "refractory_ms": 2.2, "delay_ms": 1.8, "poisson_weight_mv": 68.75}
    ids, indptr, targets, weights, counts = [np.load(GRAPH/(s+".npy"), mmap_mode="r") for s in ("neuron_ids", "indptr", "targets", "weights", "contact_counts")]
    annotations = pd.read_feather(GRAPH/"neurons.feather")
    target_indices = np.searchsorted(ids, TARGET_IDS)
    assert np.array_equal(ids[target_indices], TARGET_IDS)
    assert annotations.iloc[target_indices]["type"].tolist() == plan["target_types"]
    rows = []
    source_to_edge = np.full((len(ids), 2), -1, dtype=np.int32)
    for j, index in enumerate(target_indices):
        edge_indices = np.flatnonzero(targets==index)
        sources = np.searchsorted(indptr, edge_indices, side="right")-1
        for source, edge in zip(sources, edge_indices):
            ann = annotations.iloc[int(source)]
            row = len(rows)
            source_to_edge[source, j] = row
            rows.append({"row": row, "graph_edge_index": int(edge), "source_index": int(source), "source_id": int(ids[source]),
                         "target_slot": j, "target_index": int(index), "target_id": int(ids[index]),
                         "target_type": plan["target_types"][j], "source_type": str(ann["type"]) if pd.notna(ann["type"]) else "[untyped]",
                         "source_class": str(ann["class"]) if pd.notna(ann["class"]) else "[unassigned]", "source_superclass": ann["superclass"],
                         "source_consensus_nt": ann["consensus_nt"] if pd.notna(ann["consensus_nt"]) else "unknown",
                         "source_model_sign": int(ann["model_sign"]), "contacts": int(counts[edge]),
                         "weight_mv": float(weights[edge]), "weight_float32_hex": weights[edge].tobytes().hex()})
    edges = pd.DataFrame(rows)
    edges.to_csv(path("-incoming-edges.csv"), index=False)
    needed = (source_to_edge>=0).any(axis=1)
    edge_weights = edges.weight_mv.to_numpy(np.float32)
    edge_targets = edges.target_slot.to_numpy(np.int32)
    assert np.array_equal(edge_weights, edges.contacts.to_numpy(np.float32)*np.float32(.275)*edges.source_model_sign.to_numpy(np.int8))
    a, b = np.exp(-.1/20.), np.exp(-.1/5.)
    coefficient = 5./(20.-5.)*(a-b)
    results, all_checks, outputs = [], [], [path("-incoming-edges.csv")]
    for condition in CONDITIONS:
        print("Reading frozen journals/spikes:", condition, flush=True)
        folder = RUN/condition
        summary = json.loads((folder/"condition-summary.json").read_text())
        mask, hashes, block_counts, input_union = journal_inputs(folder, summary, ids, target_indices, plan["coupling_intervals"])
        source, stamps, recorded, total_events = read_relevant_spikes(folder, ids, needed, target_indices, hashes, block_counts, plan["original_plan_sha256"], plan["graph_sha256"])
        with np.load(folder/"brain-final-or-failure.npz") as f:
            checkpoint = {k:f[k] for k in f.files}
        metadata = json.loads(str(checkpoint.pop("metadata")))
        assert metadata["tick"]==plan["neural_ticks"] and metadata["parameters"]==plan["parameters"]
        assert metadata["graph_sha256"]==plan["graph_sha256"]
        assert np.array_equal(mask, checkpoint["ablated"])
        assert np.array_equal(checkpoint["current_mv"][target_indices], [0., 0.])
        assert np.array_equal(checkpoint["refractory_ticks"][target_indices], [22, 22])
        print("Replaying two target states:", condition, "selected source events", len(source), flush=True)
        v, g, last, emitted, increments, accepted, blocked, rejected, pending, accepted_ticks, accepted_edges = replay(plan["neural_ticks"], source, stamps, source_to_edge, edge_targets, edge_weights, mask, a, b, coefficient)
        condition_checks = []
        def check(name, value, **details):
            r = {"condition": condition, "name": name, "pass": bool(value), **details}
            condition_checks.append(r); all_checks.append(r)
        check("all_6000_recorded_drives_masks_and_spike_blocks_verified", len(hashes)==6000)
        check("recorded_total_matches_original", total_events==summary["lossless_spikes"]["events"])
        check("target_final_refractory_and_current", np.array_equal(checkpoint["refractory_ticks"][target_indices], [22,22]) and np.array_equal(checkpoint["current_mv"][target_indices], [0.,0.]))
        check("finite_replayed_states", np.isfinite(v).all() and np.isfinite(g).all())
        future = stamps+18 >= plan["neural_ticks"]
        predicted_pending = np.concatenate([source[future & ((stamps+18)%19==slot)] for slot in range(19)])
        boundaries = np.r_[0, np.cumsum(checkpoint["pending_count"])]
        actual_pending = np.concatenate([checkpoint["pending"][boundaries[slot]:boundaries[slot+1]][needed[checkpoint["pending"][boundaries[slot]:boundaries[slot+1]]]] for slot in range(19)])
        check("relevant_pending_sources_match_checkpoint_ring_order", np.array_equal(predicted_pending, actual_pending))
        balance = edges.copy()
        balance["accepted_events"] = accepted
        balance["source_blocked_events"] = blocked
        balance["target_unavailable_events"] = rejected
        balance["beyond_horizon_events"] = pending
        balance["accepted_signed_jump_mv_sum"] = accepted*edge_weights.astype(np.float64)
        # Attribute the endpoint after the final reset under the recorded input
        # history and the replayed acceptance decisions; not intervention effects.
        selected_last = last[edge_targets[accepted_edges]]
        keep = accepted_ticks>selected_last
        n = (plan["neural_ticks"]-1-accepted_ticks[keep]).astype(np.float64)
        w = edge_weights[accepted_edges[keep]].astype(np.float64)
        g_contrib = w*np.exp(-n*.1/5.)
        u_contrib = w*5./15.*(np.exp(-n*.1/20.)-np.exp(-n*.1/5.))
        balance["endpoint_g_contribution_mv"] = np.bincount(accepted_edges[keep], weights=g_contrib, minlength=len(edges))
        balance["endpoint_v_minus_rest_contribution_mv"] = np.bincount(accepted_edges[keep], weights=u_contrib, minlength=len(edges))
        for cutoff, label in ((100, "last_100ms"), (1000, "last_1s")):
            recent = accepted_ticks >= plan["neural_ticks"]-int(cutoff/.1)
            c = np.bincount(accepted_edges[recent], minlength=len(edges))
            balance[label+"_accepted_events"] = c
            balance[label+"_signed_jump_mv_sum"] = c*edge_weights.astype(float)
        balance.to_csv(path(f"-{condition}-edge-balance.csv"), index=False)
        group_columns = ["target_id", "target_type", "source_type", "source_consensus_nt", "source_model_sign"]
        numeric = ["contacts", "accepted_events", "source_blocked_events", "target_unavailable_events", "beyond_horizon_events", "accepted_signed_jump_mv_sum", "endpoint_g_contribution_mv", "endpoint_v_minus_rest_contribution_mv", "last_100ms_accepted_events", "last_100ms_signed_jump_mv_sum", "last_1s_accepted_events", "last_1s_signed_jump_mv_sum"]
        groups = balance.groupby(group_columns, dropna=False)[numeric].sum().reset_index()
        groups["abs_cumulative_accepted_jump"] = groups.accepted_signed_jump_mv_sum.abs()
        groups = groups.sort_values(["target_id", "abs_cumulative_accepted_jump"], ascending=[True, False])
        groups.to_csv(path(f"-{condition}-type-balance.csv"), index=False)
        cells = []
        for j, target_id in enumerate(TARGET_IDS):
            predicted = np.flatnonzero(emitted[:, j]).astype(np.int32)
            index = target_indices[j]
            expected_v, expected_g = float(checkpoint["voltage_mv"][index]), float(checkpoint["synaptic_mv"][index])
            verr, gerr = float(v[-1,j]-expected_v), float(g[-1,j]-expected_g)
            check(f"{target_id}:recorded_spike_ticks", np.array_equal(predicted, recorded[j]), predicted_count=len(predicted), recorded_count=len(recorded[j]))
            check(f"{target_id}:endpoint_voltage_bitwise", v[-1,j].tobytes()==checkpoint["voltage_mv"][index].tobytes(), difference_mv=verr)
            check(f"{target_id}:endpoint_synaptic_bitwise", g[-1,j].tobytes()==checkpoint["synaptic_mv"][index].tobytes(), difference_mv=gerr)
            check(f"{target_id}:endpoint_within_diagnostic_tolerance", max(abs(verr),abs(gerr))<=plan["state_checks"]["diagnostic_absolute_tolerance_mv"])
            check(f"{target_id}:last_spike_tick", last[j]==checkpoint["last_spike_tick"][index])
            e = balance[balance.target_id==target_id]
            u_sum = float(e.endpoint_v_minus_rest_contribution_mv.sum())
            g_sum = float(e.endpoint_g_contribution_mv.sum())
            check(f"{target_id}:conditional_endpoint_attribution", abs(u_sum-(v[-1,j]+52.))<1e-9 and abs(g_sum-g[-1,j])<1e-9, voltage_sum_error_mv=u_sum-(v[-1,j]+52.), synaptic_sum_error_mv=g_sum-g[-1,j])
            source_spike_counts = np.bincount(source, minlength=len(ids))
            total_incoming = source_spike_counts[e.source_index.to_numpy()]
            check(f"{target_id}:all_input_events_classified", np.array_equal(total_incoming, e.accepted_events+e.source_blocked_events+e.target_unavailable_events+e.beyond_horizon_events))
            positive = e.weight_mv>0; negative=e.weight_mv<0
            type_rows = groups[groups.target_id==target_id]
            cells.append({"id": target_id, "type": plan["target_types"][j], "incoming_edges": len(e), "contacts": int(e.contacts.sum()),
                          "recorded_spike_ticks": recorded[j].tolist(), "predicted_spike_ticks": predicted.tolist(),
                          "checkpoint_voltage_mv": expected_v, "checkpoint_synaptic_mv": expected_g,
                          "replayed_voltage_mv": float(v[-1,j]), "replayed_synaptic_mv": float(g[-1,j]),
                          "minimum_replayed_voltage_mv": float(v[:,j].min()),
                          "accepted_positive_events": int(e.loc[positive,"accepted_events"].sum()), "accepted_negative_events": int(e.loc[negative,"accepted_events"].sum()),
                          "accepted_zero_weight_events": int(e.loc[e.weight_mv==0,"accepted_events"].sum()),
                          "accepted_positive_jump_mv_sum": float(e.loc[positive,"accepted_signed_jump_mv_sum"].sum()),
                          "accepted_negative_jump_mv_sum": float(e.loc[negative,"accepted_signed_jump_mv_sum"].sum()),
                          "source_blocked_events": int(e.source_blocked_events.sum()), "target_unavailable_events": int(e.target_unavailable_events.sum()), "beyond_horizon_events": int(e.beyond_horizon_events.sum()),
                          "endpoint_positive_v_contribution_mv": float(e.loc[positive,"endpoint_v_minus_rest_contribution_mv"].sum()),
                          "endpoint_negative_v_contribution_mv": float(e.loc[negative,"endpoint_v_minus_rest_contribution_mv"].sum()),
                          "top_10_source_types_by_cumulative_magnitude": type_rows.head(10).to_dict("records")})
        arrays = {"sample_time_ms": np.arange(len(v))*.1, "target_ids": np.asarray(TARGET_IDS), "voltage_mv": v, "synaptic_mv": g,
                  "emitted_spikes_by_tick": emitted, "accepted_positive_negative_jump_mv_by_tick": increments,
                  "recorded_source_indices": source, "recorded_source_spike_ticks": stamps,
                  "accepted_delivery_ticks": accepted_ticks, "accepted_edge_rows": accepted_edges,
                  "recorded_target0_spike_ticks": recorded[0], "recorded_target1_spike_ticks": recorded[1],
                  "checkpoint_selected_voltage_mv": checkpoint["voltage_mv"][target_indices], "checkpoint_selected_synaptic_mv": checkpoint["synaptic_mv"][target_indices]}
        archive = path(f"-{condition}-arrays.npz")
        np.savez_compressed(archive, **arrays)
        outputs += [archive, path(f"-{condition}-edge-balance.csv"), path(f"-{condition}-type-balance.csv")]
        results.append({"condition": condition, "passed": all(c["pass"] for c in condition_checks), "input_list_union_count": len(input_union),
                        "selected_targets_in_any_input_list": False, "source_blocked_count": int(mask.sum()),
                        "recorded_all_graph_events": total_events, "recorded_relevant_source_events": len(source), "cells": cells})
        print(condition, "passed", results[-1]["passed"], "endpoint differences", [(c["replayed_voltage_mv"]-c["checkpoint_voltage_mv"], c["replayed_synaptic_mv"]-c["checkpoint_synaptic_mv"]) for c in cells], flush=True)
    unchanged = all(sha(ROOT/n)==r["sha256"] for n,r in plan["inputs"].items())
    all_checks.append({"name": "frozen_inputs_unchanged_after_replay", "pass": unchanged})
    result = {"schema": 1, "completed_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(path("-plan.json")),
              "passed": all(c["pass"] for c in all_checks), "checks": all_checks, "conditions": results,
              "runtime": {"numpy": np.__version__, "pandas": pd.__version__},
              "full_graph_rerun": False, "parameters_changed": False,
              "claim_limit": "Conditional replay and arithmetic attribution. Recorded source spike generation and recurrent counterfactual effects are not recomputed. No biological cause or calibrated membrane-voltage claim.",
              "artifacts": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in outputs}}
    write_json(path("-results.json"), result)
    print(json.dumps({"passed": result["passed"], "checks": len(all_checks)}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        try:
            run()
        except Exception as error:
            failure_path = path("-failure.json")
            if not failure_path.exists():
                write_json(failure_path, {"error_type": type(error).__name__, "error": str(error), "traceback": traceback.format_exc(),
                                         "plan_sha256": sha(path("-plan.json")) if path("-plan.json").exists() else None,
                                         "scope": "Retained operational/input-proof failure; do not infer full-graph or biological failure"})
            raise
