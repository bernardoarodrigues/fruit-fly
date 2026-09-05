#!/usr/bin/env python3
"""Independent MBON saved-data reduction review; never generates neural spikes.

Raw archives use the previously audited independent decoder. Synaptic states
are reconstructed from the immutable spike history, without voltage integration,
producer reducer imports, fitting, RNG draws, or graph-wide state propagation.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import time
import traceback

import numpy as np
import pandas as pd

from review_inhibitory_recurrent_panel_trial import Audit, exact, ROOT

PREFIX = ROOT / "validation/navigation-ladder-mbon-input"
OUTPUT = ROOT / "validation/navigation-ladder-mbon-input-independent-review.json"
PANEL = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
ANATOMY = ROOT / "validation/navigation-ladder-anatomy.json"
GRAPH = ROOT / "data/processed/malecns_v1"
ORDINALS = (26, 35, 29, 38, 32, 41)
TARGETS = np.array([246, 1749, 2550, 3477, 3513, 7264, 8528,
                    127463, 130136, 131044], np.int64)
WINDOWS = np.array([0, 500, 5000, 10000, 15000, 20000, 25000, 30000], np.int64)
DECAY = float(np.exp(-.1 / 5.))
DECODER_SHA = "1e2d91757813372de3fa3d5df100690ab7ac6d3805fe7f7035e3ebc5f6424da8"
ATOL, RTOL = 1e-9, 1e-12


def load(path):
    return json.loads(Path(path).read_text())


def file_record(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=h.hexdigest())


def nested_records(value):
    """Discover provenance records without assuming producer nesting layout."""
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= value.keys():
            yield {k: value[k] for k in ("path", "bytes", "sha256")}
        for child in value.values():
            yield from nested_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_records(child)


class Review(Audit):
    def __init__(self):
        super().__init__()
        self.maximum_errors = {}

    def require(self, name, value, context=None):
        if not self.ck(name, value, context):
            raise ValueError(name + ": " + str(context))

    def close(self, name, actual, expected, context=None):
        actual, expected = np.asarray(actual), np.asarray(expected)
        self.require(name + "_shape", actual.shape == expected.shape, context)
        difference = np.abs(actual - expected)
        worst = float(difference.max()) if difference.size else 0.
        self.maximum_errors[name] = max(worst, self.maximum_errors.get(name, 0.))
        self.require(name, np.isfinite(actual).all() and np.isfinite(expected).all()
                     and np.all(difference <= ATOL + RTOL * np.maximum(abs(actual), abs(expected))), context)


def incoming_edges(targets):
    """Independently select original CSR positions, preserving original order."""
    ptr = np.load(GRAPH / "indptr.npy", mmap_mode="r")
    destinations = np.load(GRAPH / "targets.npy", mmap_mode="r")
    weights = np.load(GRAPH / "weights.npy", mmap_mode="r")
    contacts = np.load(GRAPH / "contact_counts.npy", mmap_mode="r")
    rows = np.flatnonzero(np.isin(destinations, targets))
    sources = np.searchsorted(ptr, rows, side="right") - 1
    columns = np.searchsorted(targets, destinations[rows])
    unique, counts = np.unique(sources, return_counts=True)
    source_ptr = np.r_[0, np.cumsum(counts)].astype(np.int64)
    return dict(rows=rows, sources=sources, columns=columns,
                weights=np.array(weights[rows]), contacts=np.array(contacts[rows]),
                unique_sources=unique, source_ptr=source_ptr)


def expanded_edges(source_positions, source_ptr):
    """Ragged CSR gather, maintaining spike order then original edge order."""
    sizes = np.diff(source_ptr)[source_positions]
    beginning = np.repeat(source_ptr[source_positions], sizes)
    offsets = np.arange(int(sizes.sum())) - np.repeat(np.cumsum(sizes) - sizes, sizes)
    return beginning + offsets, sizes


def second_spike_isis(ticks, indices, targets=TARGETS):
    intervals = np.zeros((7, len(targets)), np.int64)
    at_limit = np.zeros_like(intervals)
    for column, target in enumerate(targets):
        own = ticks[indices == target]
        delta = np.diff(own)
        windows = np.searchsorted(WINDOWS, own[1:], side="right") - 1
        np.add.at(intervals[:, column], windows, 1)
        np.add.at(at_limit[:, column], windows[delta == 22], 1)
    return intervals, at_limit


class SynapticReduction:
    """Conditional H1 arithmetic only; stored spikes decide every event."""
    def __init__(self, graph, initial_p, initial_h, neurons):
        self.graph = graph
        self.source_position = np.full(neurons, -1, np.int64)
        self.source_position[graph["unique_sources"]] = np.arange(len(graph["unique_sources"]))
        self.target_position = np.full(neurons, -1, np.int64)
        self.target_position[TARGETS] = np.arange(len(TARGETS))
        self.p = np.empty((30001, len(TARGETS)), np.float64)
        self.h = np.empty_like(self.p)
        self.p[0], self.h[0] = initial_p, initial_h
        self.p_increment = np.zeros((30000, len(TARGETS)), np.float64)
        self.h_increment = np.zeros_like(self.p_increment)
        self.arrivals = np.zeros((7, len(graph["rows"])), np.int64)
        self.emissions = np.zeros((7, len(graph["unique_sources"])), np.int64)
        self.target_counts = np.zeros((7, len(TARGETS)), np.int64)
        self.target_last = np.full(len(TARGETS), -(2**60), np.int64)
        self.target_ticks, self.target_indices = [], []
        self.tail_ticks = np.empty(0, np.int64)
        self.tail_indices = np.empty(0, np.int32)
        self.tick = 0

    def consume(self, ticks, indices, end):
        start = self.tick
        positions = self.source_position[indices]
        relevant = positions >= 0
        bins = np.searchsorted(WINDOWS, ticks, side="right") - 1
        np.add.at(self.emissions, (bins[relevant], positions[relevant]), 1)
        columns = self.target_position[indices]
        own = columns >= 0
        np.add.at(self.target_counts, (bins[own], columns[own]), 1)
        np.maximum.at(self.target_last, columns[own], ticks[own])
        self.target_ticks.append(ticks[own].copy())
        self.target_indices.append(indices[own].copy())

        joined_ticks = np.r_[self.tail_ticks, ticks]
        joined_indices = np.r_[self.tail_indices, indices]
        delivery = joined_ticks + 18
        source_positions = self.source_position[joined_indices]
        visit = (delivery >= start) & (delivery < end) & (source_positions >= 0)
        edge_positions, multiplicity = expanded_edges(source_positions[visit], self.graph["source_ptr"])
        event_ticks = np.repeat(delivery[visit], multiplicity)
        event_columns = self.graph["columns"][edge_positions]
        event_weights = self.graph["weights"][edge_positions].astype(np.float64)
        event_bins = np.searchsorted(WINDOWS, event_ticks, side="right") - 1
        np.add.at(self.arrivals, (event_bins, edge_positions), 1)

        p, h = self.p[start].copy(), self.h[start].copy()
        cuts = np.searchsorted(event_ticks, np.arange(start, end + 1), side="left")
        for k, tick in enumerate(range(start, end)):
            p *= DECAY
            h *= DECAY
            weights = event_weights[cuts[k]:cuts[k + 1]]
            columns = event_columns[cuts[k]:cuts[k + 1]]
            negative = weights < 0.
            # np.add.at processes repeated indices in provided order; no grouped
            # sum is substituted into the bitwise state reconstruction.
            np.add.at(p, columns[~negative], weights[~negative])
            np.add.at(h, columns[negative], -weights[negative] * (1. / 23.))
            np.add.at(self.p_increment[tick], columns[~negative], weights[~negative])
            np.add.at(self.h_increment[tick], columns[negative], -weights[negative] * (1. / 23.))
            self.p[tick + 1], self.h[tick + 1] = p, h
        pending = delivery >= end
        self.tail_ticks, self.tail_indices = joined_ticks[pending], joined_indices[pending]
        self.tick = end

    def pending(self):
        slots = (self.tail_ticks + 18) % 19
        counts = np.bincount(slots, minlength=19).astype(np.int64)
        packed = np.concatenate([self.tail_indices[slots == s] for s in range(19)])
        return counts, packed


def rollup(arrivals, graph, edge_labels, labels):
    shape = (7, len(TARGETS), len(labels))
    totals = {k: np.zeros(shape, np.int64) for k in ("arrivals", "accepted", "blocked", "contacts")}
    totals.update({k: np.zeros(shape, np.float64) for k in ("p_increment", "h_increment")})
    codes = np.array([labels.index(v) for v in edge_labels], np.int64)
    weights = graph["weights"].astype(np.float64)
    for window in range(7):
        at = (graph["columns"], codes)
        np.add.at(totals["arrivals"][window], at, arrivals[window])
        np.add.at(totals["accepted"][window], at, arrivals[window])
        np.add.at(totals["contacts"][window], at, arrivals[window] * graph["contacts"].astype(np.int64))
        np.add.at(totals["p_increment"][window], at, arrivals[window] * np.where(weights >= 0., weights, 0.))
        np.add.at(totals["h_increment"][window], at, arrivals[window] * np.where(weights < 0., -weights * (1. / 23.), 0.))
    return totals


def label(value):
    return "<missing>" if pd.isna(value) else str(value)


def finite_array(value):
    if value.dtype.hasobject:
        return False
    if value.dtype.names:
        return all(finite_array(value[name]) for name in value.dtype.names)
    return value.dtype.kind in "biu" or (value.dtype.kind == "f" and np.isfinite(value).all())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path(str(PREFIX) + "-results.json"))
    args = parser.parse_args()
    if not args.results.exists():
        raise SystemExit("Awaiting completed producer output; no raw spike scan or receipt written")
    if OUTPUT.exists():
        raise SystemExit("Preserve the first independent review receipt")
    producer = load(args.results)
    plan_path = Path(str(PREFIX) + "-plan.json")
    plan, panel = load(plan_path), load(PANEL)
    R = Review()
    began = time.perf_counter()
    error, current = None, dict(stage="preflight")
    completed = []
    source_paths = [Path(__file__), ROOT / "scripts/review_inhibitory_recurrent_panel_trial.py",
                    ROOT / "scripts/analyze_navigation_ladder_mbon_inputs.py",
                    plan_path, args.results, PANEL, ANATOMY, GRAPH / "manifest.json",
                    GRAPH / "neurons.feather"]
    source_start = {str(p.relative_to(ROOT)): file_record(p) for p in source_paths}
    try:
        R.require("producer_complete", producer["passed"] and not producer.get("error")
                  and not producer.get("failure"))
        R.require("independent_decoder_pin", source_start["scripts/review_inhibitory_recurrent_panel_trial.py"]["sha256"] == DECODER_SHA)
        R.require("producer_plan_pin", producer["plan"] == file_record(plan_path))
        records = {r["path"]: r for r in nested_records(plan)}
        records.update({r["path"]: r for r in producer["artifacts"]})
        for r in records.values():
            R.require("producer_input_or_output_pin", R.record(r), r["path"])
        anatomy = load(ANATOMY)
        R.require("anatomy", anatomy["passed"] and anatomy["source_unchanged"]
                  and not anatomy["errors"] and anatomy["groups"]["MBON12_14"]["indices"] == TARGETS.tolist())
        manifest = load(GRAPH / "manifest.json")
        for name, r in manifest["arrays"].items():
            R.require("graph_array_pin", file_record(GRAPH / name)["sha256"] == r["sha256"], name)
        R.require("graph_metadata_pin", file_record(GRAPH / "neurons.feather")["sha256"] == manifest["metadata"]["neurons.feather"]["sha256"])
        with np.load(Path(str(PREFIX) + "-arrays.npz"), allow_pickle=False) as z:
            saved = {k: z[k] for k in z.files}
        R.require("output_array_domain", all(finite_array(v) for v in saved.values()))
        graph = incoming_edges(TARGETS)
        for key, expected in [("graph_indices", TARGETS), ("source_indices", graph["unique_sources"]),
                              ("edge_indices", graph["rows"]), ("edge_source_indices", graph["sources"]),
                              ("edge_target_columns", graph["columns"]), ("window_edges_ticks", WINDOWS)]:
            R.require("incoming_index_inventory", saved[key].dtype.kind in "iu" and np.array_equal(saved[key], expected), key)
        R.require("incoming_weights_exact", exact(saved["edge_weights"], graph["weights"]))
        R.require("incoming_contacts_exact", exact(saved["edge_contact_counts"], graph["contacts"]))
        R.require("incoming_order", np.all(np.diff(graph["rows"]) > 0)
                  and np.all(np.diff(graph["sources"]) >= 0)
                  and np.all(graph["weights"] == graph["weights"].astype(np.float32)))
        metadata = pd.read_feather(GRAPH / "neurons.feather")
        ids = np.load(GRAPH / "neuron_ids.npy")
        R.require("metadata_row_identity", np.array_equal(metadata["bodyId"].to_numpy(), ids))
        R.require("target_body_identity", exact(saved["body_ids"], ids[TARGETS])
                  and ids[TARGETS].tolist() == anatomy["groups"]["MBON12_14"]["body_ids"])
        with Path(str(PREFIX) + "-edges.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        R.require("edge_table_rows", len(rows) == len(graph["rows"]))
        for column, values in (("edge_index", graph["rows"]), ("source_index", graph["sources"]),
                               ("target_index", TARGETS[graph["columns"]]),
                               ("source_body_id", ids[graph["sources"]]),
                               ("target_body_id", ids[TARGETS[graph["columns"]]]),
                               ("contact_count", graph["contacts"])):
            R.require("edge_table_integer_join", np.array_equal([int(r[column]) for r in rows], values), column)
        R.require("edge_table_original_weights", exact(np.array([float(r["weight_float32"]) for r in rows]),
                  graph["weights"].astype(np.float64)))
        for column in ("type", "class", "consensus_nt", "model_sign"):
            R.require("edge_table_annotation_join", [r[column] for r in rows]
                      == [label(v) for v in metadata.iloc[graph["sources"]][column]], column)
        edge_labels = {"class": [label(v) for v in metadata.iloc[graph["sources"]]["class"]],
                       "nt": [label(v) for v in metadata.iloc[graph["sources"]]["consensus_nt"]]}
        for grouping in ("class", "nt"):
            R.require("group_label_inventory", len(set(producer["group_labels"][grouping])) == len(producer["group_labels"][grouping])
                      and set(producer["group_labels"][grouping]) == set(edge_labels[grouping]), grouping)
        run = ROOT / panel["run_dir"]
        selection = R.archive(run / "selection")
        R.require("no_continuous_MBON_trace_or_direct_input", not np.intersect1d(TARGETS, selection["selected"]).size
                  and not np.intersect1d(TARGETS, selection["inputs"]).size)
        R.require("frozen_windows", panel["window_edges_ticks"] == WINDOWS.tolist()
                  and panel["checkpoint_ticks"] == WINDOWS.tolist()
                  and panel["dt_ms"] == .1 and panel["chunk_ticks"] == 50)
        R.require("reducer_plan_contract", plan["window_edges_ticks"] == WINDOWS.tolist()
                  and plan["checkpoint_ticks"] == WINDOWS.tolist() and plan["delay_ticks"] == 18
                  and plan["dt_ms"] == .1 and plan["decay"] == DECAY
                  and plan["graph_sha256"] == panel["graph_sha256"]
                  and plan["targets"] == anatomy["groups"]["MBON12_14"]
                  and plan["independent_regrouped_tolerances"] == dict(atol=ATOL, rtol=RTOL))
        trials = {t["spec"]["ordinal"]: t for t in producer["trials"]}
        R.require("six_trial_scope", len(producer["trials"]) == len(trials) == 6
                  and set(trials) == set(ORDINALS)
                  and plan["trials"] == [panel["order"][i] for i in sorted(ORDINALS)])
        R.require("reported_anatomy", producer["anatomy"] == dict(incoming_edges=len(graph["rows"]),
                  distinct_sources=len(graph["unique_sources"]), contacts=int(graph["contacts"].sum()),
                  target_order=TARGETS.tolist()))

        def checkpoint(reduction, directory, tick, spec, initial=None):
            cp = initial if initial is not None else R.archive(directory / f"checkpoint-{tick:05d}")
            R.require("checkpoint_identity", cp["tick"] == tick and cp["time_ms"] == tick * .1
                      and cp["arm"] == "H1" and cp["seed"] == spec["seed"] and cp["coherent_state"]
                      and cp["failure"] is None and cp["graph_sha256"] == panel["graph_sha256"]
                      and cp["last_durable_chunk_end_tick"] == tick and cp["confirmed_prefix_end_tick"] == tick, [spec["ordinal"], tick])
            R.require("checkpoint_static_semantics", not cp["blocked"].any()
                      and np.all(cp["refractory"][TARGETS] == 22)
                      and cp["parameters"]["synapse_tau_ms"] == 5.
                      and cp["parameters"]["delay_ticks"] == 18, [spec["ordinal"], tick])
            current.update(stage="checkpoint", tick=tick,
                           reconstructed_p=reduction.p[tick].tolist(), reconstructed_h=reduction.h[tick].tolist(),
                           checkpoint_p=cp["s"][TARGETS].tolist(), checkpoint_h=cp["h"][TARGETS].tolist())
            R.require("checkpoint_bitwise_p_h", exact(reduction.p[tick], cp["s"][TARGETS])
                      and exact(reduction.h[tick], cp["h"][TARGETS]), [spec["ordinal"], tick])
            pc, pending = reduction.pending()
            R.require("checkpoint_full_pending_queue", exact(pc, cp["pending_count"])
                      and exact(pending, cp["pending"]), [spec["ordinal"], tick])
            R.require("checkpoint_target_counts_and_last", exact(reduction.target_counts, cp["window_counts_observed"][:, TARGETS])
                      and exact(reduction.target_last, cp["last"][TARGETS]), [spec["ordinal"], tick])
            if tick:
                decay = np.power(DECAY, np.arange(tick - 1, -1, -1))
                for name in ("p", "h"):
                    trace = getattr(reduction, name)
                    increments = getattr(reduction, name + "_increment")
                    convolved = trace[0] * DECAY ** tick + decay @ increments[:tick]
                    R.close("conditional_convolution_" + name, trace[tick], convolved, [spec["ordinal"], tick])

        for ordinal in ORDINALS:
            spec = panel["order"][ordinal]
            R.require("trial_fixed_scope", spec["arm"] == "H1" and spec["condition"] in ("constant_baseline", "ethyl_acetate")
                      and spec["seed"] in (11, 12, 13), ordinal)
            current = dict(stage="trial_preflight", ordinal=ordinal, trial=spec["name"])
            directory = run / spec["name"]
            terminal, native = load(directory / "terminal.json"), load(directory / "result.json")
            R.require("trial_terminal_complete", terminal["status"] == "complete" and terminal["complete"]
                      and native["status"] == "complete" and native["complete"] and not native["errors"], ordinal)
            R.require("trial_terminal_result_pin", R.record(terminal["result"]), ordinal)
            native_records = {r["path"]: r for r in native["artifacts"]}
            for r in native_records.values():
                R.require("raw_trial_artifact_pin", R.record(r), r["path"])
            prior_review = load(ROOT / "validation" / ("inhibitory-recurrent-panel-" + spec["name"] + "-H-review.json"))
            R.require("prior_independent_H_review", prior_review["passed"] and not prior_review["failures"]
                      and prior_review["terminal_sha256"] == R.sha(directory / "terminal.json")
                      and prior_review["result_sha256"] == R.sha(directory / "result.json"), ordinal)
            initial = R.archive(directory / "checkpoint-00000")
            reduction = SynapticReduction(graph, initial["s"][TARGETS], initial["h"][TARGETS], panel["neurons"])
            R.require("initial_synapses_zero", not reduction.p[0].any() and not reduction.h[0].any(), ordinal)
            checkpoint(reduction, directory, 0, spec, initial)
            raw_total = 0
            for chunk in range(600):
                start, end = chunk * 50, (chunk + 1) * 50
                current = dict(stage="chunk", ordinal=ordinal, chunk=chunk, completed_tick=start)
                raw = R.archive(directory / f"chunk-{chunk:04d}")
                R.require("raw_chunk_complete", raw["status"] == "complete" and raw["coherent_state"]
                          and raw["failure"] is None and raw["partial"] is None
                          and raw["start_tick"] == start and raw["end_tick"] == end
                          and raw["completed_ticks"] == 50 and raw["requested_ticks"] == 50, [ordinal, chunk])
                ticks, indices = raw["spike_ticks"], raw["spike_indices"]
                R.require("raw_spike_order", ticks.dtype == np.int64 and indices.dtype == np.int32
                          and ticks.shape == indices.shape and np.all((ticks >= start) & (ticks < end))
                          and np.all((indices >= 0) & (indices < panel["neurons"]))
                          and (len(ticks) < 2 or np.all((ticks[1:] > ticks[:-1]) |
                              ((ticks[1:] == ticks[:-1]) & (indices[1:] > indices[:-1])))), [ordinal, chunk])
                reduction.consume(ticks, indices, end)
                raw_total += len(ticks)
                if end in panel["checkpoint_ticks"]:
                    checkpoint(reduction, directory, end, spec)
            base = f"trial_{ordinal}_"
            R.require("complete_p_trace_bitwise", exact(reduction.p, saved[base + "p"]), ordinal)
            R.require("complete_h_trace_bitwise", exact(reduction.h, saved[base + "h"]), ordinal)
            for key, expected in (("edge_arrivals", reduction.arrivals), ("edge_accepted", reduction.arrivals),
                                  ("edge_blocked", np.zeros_like(reduction.arrivals)), ("source_emissions", reduction.emissions)):
                R.require("integer_arrival_and_emission_counts", exact(saved[base + key], expected), [ordinal, key])
            own_t, own_i = np.concatenate(reduction.target_ticks), np.concatenate(reduction.target_indices)
            packed = saved[base + "target_spikes"]
            R.require("target_packed_spikes", packed.dtype.descr == [("tick", "<i8"), ("index", "<i4")]
                      and packed.itemsize == 12 and np.array_equal(packed["tick"], own_t)
                      and np.array_equal(packed["index"], own_i), ordinal)
            isi_count, isi_22 = second_spike_isis(own_t, own_i)
            R.require("target_refractory_spacing", all(np.all(np.diff(own_t[own_i == target]) >= 22) for target in TARGETS), ordinal)
            trial = trials[ordinal]
            R.require("trial_summary_identity", trial["spec"] == spec and trial["total_raw_spikes"] == raw_total
                      and native["spike_count"] == raw_total, ordinal)
            for key, values in (("target_counts", reduction.target_counts), ("isi_interval_count", isi_count),
                                ("isi_at_22_ticks_count", isi_22)):
                R.require("trial_integer_summary", np.array_equal(trial[key], values), [ordinal, key])
            R.require("checkpoint_claims", trial["checkpoints"] == [dict(tick=int(t), p_bitwise=True,
                      h_bitwise=True, target_counts_exact=True, all_pending_spikes_exact=True) for t in WINDOWS], ordinal)
            pending_relevant = int(np.sum(reduction.source_position[reduction.tail_indices] >= 0))
            R.require("pending_relevant_summary", trial["pending_presynaptic_spikes"] == pending_relevant, ordinal)
            for key, values in (("p_peak", reduction.p.max(axis=0)), ("h_peak", reduction.h.max(axis=0)),
                                ("p_final", reduction.p[-1]), ("h_final", reduction.h[-1])):
                R.require("state_summary_exact", exact(np.array(trial["synaptic_state_summary"][key]), values), [ordinal, key])
            rankings = None
            for grouping in ("class", "nt"):
                labels = producer["group_labels"][grouping]
                expected = rollup(reduction.arrivals, graph, edge_labels[grouping], labels)
                for key, values in expected.items():
                    if key.endswith("increment"):
                        R.close("regrouped_" + key, saved[base + grouping + "_" + key], values, [ordinal, grouping])
                    else:
                        R.require("integer_group_rollup", exact(saved[base + grouping + "_" + key], values), [ordinal, grouping, key])
                if grouping == "class":
                    totals = expected["p_increment"][2:4].sum(axis=(0, 1))
                    rankings = sorted([(labels[i], float(v)) for i, v in enumerate(totals)], key=lambda x: (-x[1], x[0]))
            winner = rankings[0][0] if rankings and rankings[0][1] > 0 and (len(rankings) == 1 or rankings[0][1] > rankings[1][1]) else None
            R.require("positive_class_ranking_order", [r["label"] for r in trial["class_positive_ranking"]]
                      == [r[0] for r in rankings] and trial["unique_positive_class_winner"] == winner, ordinal)
            R.close("positive_class_ranking_values", [r["p_increment"] for r in trial["class_positive_ranking"]],
                    [r[1] for r in rankings], ordinal)
            completed.append(dict(spec=spec, checkpoint_ticks=panel["checkpoint_ticks"],
                                  target_window_spikes=reduction.target_counts.tolist(),
                                  isi_interval_count=isi_count.tolist(), isi_at_22_ticks_count=isi_22.tolist(),
                                  class_positive_increment_ranking=rankings, unique_positive_class_winner=winner,
                                  accepted_edge_arrivals=int(reduction.arrivals.sum()),
                                  final_relevant_pending_spikes=pending_relevant))
            R.require("trial_result_still_pinned", R.sha(directory / "result.json", False) == terminal["result"]["sha256"], ordinal)
        winners = [r["unique_positive_class_winner"] for r in completed]
        ready = len(winners) == 6 and winners[0] not in (None, "<missing>") and len(set(winners)) == 1
        chosen = graph["rows"][(np.asarray(edge_labels["class"]) == winners[0]) & (graph["weights"] > 0)] if ready else np.empty(0, np.int64)
        R.require("proposed_original_edge_selection", exact(saved["proposed_intervention_edge_indices"], chosen))
        producer_winners = [next(t for t in completed if t["spec"]["ordinal"] == s["ordinal"])["unique_positive_class_winner"] for s in plan["trials"]]
        R.require("unlaunched_intervention_gate", producer["intervention_gate"] == dict(passed=ready,
                  winners=producer_winners, selected_class=winners[0] if ready else None,
                  positive_edge_count=len(chosen), delivery_window_ticks=[5000, 15000],
                  status="eligible_for_separately_frozen_intervention" if ready else "ambiguous_no_intervention_selected",
                  launched=False))
        current = dict(stage="completed", all_six_checkpoint_gates=True,
                       consistent_nonmissing_unique_positive_class=ready,
                       proposed_class=winners[0] if ready else None)
    except (Exception, KeyboardInterrupt) as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    source_end = {str(p.relative_to(ROOT)): file_record(p) for p in source_paths}
    R.ck("review_source_stability", source_end == source_start)
    report = dict(schema=1, completed_utc=datetime.now(timezone.utc).isoformat(),
                  passed=not R.failures and error is None, error=error, progress=current,
                  check_count=sum(v["checked"] for v in R.categories.values()), categories=R.categories,
                  failures=R.failures, completed_trials=completed, source_start=source_start,
                  source_end=source_end, maximum_absolute_errors=R.maximum_errors,
                  decoded_archives=R.decoded_archives, decoded_arrays=R.decoded_arrays,
                  wall_seconds=time.perf_counter() - began,
                  scope="Ten targets, six archived H1 trials; ordered synaptic arithmetic only. No new voltage integration, spikes, fitting or root searches.",
                  limits=["MBON per-tick voltage and actual delivery logs were not retained; p/h reconstruction is conditional on saved source spikes and frozen H1 acceptance semantics.",
                          "Transmitter labels and signed weights are model annotations, not receptor-level physiology. Grouped weight totals are not causal effects.",
                          "A consistent class winner justifies a separately frozen intervention candidate; it does not prove unique causation or authorize automatic model promotion."])
    with OUTPUT.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(output=file_record(OUTPUT), passed=report["passed"],
                          checks=report["check_count"], error=error), indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
