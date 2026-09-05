"""Prespecified JO-F afferent activation and source-output suppression assay.

Uses the full retained MaleCNS graph and unchanged Shiu baseline. This is an
artificial neural-input diagnostic, not a calibrated mechanical stimulus.
"""
from dataclasses import asdict
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome, sha256
from fruitfly.neural import LIFNetwork, SparseDrive
from fruitfly.sensors import MotorDecoder, SensoryEncoder, SensoryParameters
from check_grooming_gate import intervals


GRAPH = Path("data/processed/malecns_v1")
F_TYPES = ["JO-FD1", "JO-FD2", "JO-FV"]


def metadata(graph, indices):
    columns = ["bodyId", "type", "rootSide", "somaSide", "instance", "entryNerve",
               "subclass", "synonyms", "status", "statusLabel", "consensus_nt", "model_sign"]
    return json.loads(graph.neurons.iloc[indices][columns].to_json(orient="records"))


def anatomy(graph, source, dns):
    """Count exact contacts and two-edge walks, retaining inhibitory candidates.

    The product is a contact-count path score, not physiological efficacy.
    No weight changes, path selection or inferred intermediate cell aliases.
    """
    contacts = np.load(GRAPH / "contact_counts.npy", mmap_mode="r")
    first = np.zeros(len(graph.neuron_ids), dtype=np.int64)
    for i in source:
        a, b = graph.indptr[i:i+2]
        first[graph.targets[a:b]] += contacts[a:b]
    records = []
    for dn in dns:
        paths = []
        for mid in np.flatnonzero(first):
            a, b = graph.indptr[mid:mid+2]
            local = np.searchsorted(graph.targets[a:b], dn)
            if local < b-a and graph.targets[a+local] == dn:
                count = int(contacts[a+local])
                row = metadata(graph, [mid])[0]
                row.update(source_to_intermediate_contacts=int(first[mid]),
                           intermediate_to_dn_contacts=count,
                           contact_product=int(first[mid])*count,
                           intermediate_to_dn_model_weight_mv=float(graph.weights[a+local]))
                paths.append(row)
        paths.sort(key=lambda p: -p["contact_product"])
        records.append({"dn": metadata(graph, [dn])[0],
                        "direct_contacts_from_source_union": int(first[dn]),
                        "two_edge_intermediate_count": len(paths),
                        "two_edge_intermediates": paths})
    return {"source_cells": metadata(graph, source), "dn_cells": metadata(graph, dns),
            "all_F_annotation_counts": json.loads(graph.neurons.iloc[graph.select(F_TYPES)]
               .groupby(["type", "rootSide", "subclass"], dropna=False).size()
               .reset_index(name="count").to_json(orient="records")),
            "source_outgoing_pairs": int(sum(graph.indptr[i+1]-graph.indptr[i] for i in source)),
            "source_outgoing_contacts": int(first.sum()),
            "source_unique_immediate_targets": int(np.count_nonzero(first)),
            "two_edge_walk_caveat": "Anatomical contact paths, not measured functional connections; model signs are declared approximations; intermediates include recurrent/descending nodes where present.",
            "targets": records}


def run(graph, source, dns, seed, rate_hz, blocked):
    dt_ms, duration_ms, discard_ms = 5., 1250., 100.
    brain = LIFNetwork.from_connectome(graph, seed=seed)
    motor = MotorDecoder(graph, tau_s=.05, enable_grooming=True, grooming_threshold_hz=10.)
    sensory = SensoryEncoder(graph, SensoryParameters(odor_baseline_hz=0., odor_max_increment_hz=0.))
    observation = {"antenna_odor": [0., 0.], "taste_food": False, "taste_water": False}
    odor = sensory.encode(observation, dt_ms/1000)
    assert graph.neuron_ids[motor.groups["grooming_left"]].tolist() == [13624, 14537]
    drive_indices = np.r_[odor.indices, source]
    assert len(np.intersect1d(drive_indices, dns)) == 0
    assert len(np.unique(drive_indices)) == len(drive_indices)
    drive = SparseDrive(drive_indices, rates_hz=np.r_[odor.rates_hz, np.full(len(source), rate_hz)])
    outputs = np.unique(np.r_[source, dns, np.concatenate(list(motor.groups.values()))])
    brain.advance(brain.parameters.dt_ms, outputs=[])
    brain.reset(seed=seed)
    if blocked:
        brain.ablate(source)
    counts = np.zeros(len(outputs), dtype=np.int64)
    monitored = np.r_[source, dns]
    spike_times = {int(cell): [] for cell in graph.neuron_ids[monitored]}
    trace, network_spikes, traversed_edges = [], 0, 0
    started = perf_counter()
    for step in range(round(duration_ms/dt_ms)):
        batch = brain.advance(dt_ms, drive=drive, outputs=outputs)
        action = motor.decode(batch, dt_ms/1000, observation)
        counts += batch.counts(outputs)
        network_spikes += batch.total_spikes
        traversed_edges += batch.traversed_edges
        for index, body_id in zip(monitored, graph.neuron_ids[monitored]):
            spike_times[int(body_id)].extend(batch.times_ms[batch.indices == index].tolist())
        assert np.all(np.isfinite(brain.voltage_mv)) and np.all(np.isfinite(brain.synaptic_mv))
        trace.append({"sample_time_ms": float((step+1)*dt_ms),
                      "held_action_start_ms": float(step*dt_ms),
                      "grooming_left_filtered_hz": motor.rates["grooming_left"],
                      "behavior": action["behavior"],
                      "dn_voltage_mv": brain.voltage_mv[dns].tolist(),
                      "source_voltage_min_mv": float(brain.voltage_mv[source].min()),
                      "network_voltage_min_mv": float(brain.voltage_mv.min()),
                      "network_voltage_max_mv": float(brain.voltage_mv.max())})
    gate = np.array([row["behavior"] == "groom" for row in trace])
    kept = round(discard_ms/dt_ms)
    on, off = intervals(gate, dt_ms), intervals(~gate[kept:], dt_ms, discard_ms)
    longest = max((r["duration_ms"] for r in on), default=0.)
    source_count = int(counts[np.searchsorted(outputs, source)].sum())
    return {"seed": seed, "source_per_cell_poisson_hz": rate_hz,
            "source_outgoing_suppressed": blocked, "duration_ms": duration_ms,
            "discard_for_late_stats_ms": discard_ms, "coupling_ms": dt_ms,
            "parameters": asdict(brain.parameters),
            "input_order_body_ids": graph.neuron_ids[drive_indices].tolist(),
            "zero_rate_odor_neurons": len(odor.indices),
            "network_spikes": network_spikes, "source_spikes": source_count,
            "source_mean_actual_spike_hz": source_count/len(source)/(duration_ms/1000),
            "non_source_network_spikes": network_spikes-source_count,
            "traversed_edges": traversed_edges, "wall_seconds": perf_counter()-started,
            "gate_fraction_after_100ms": float(gate[kept:].mean()),
            "longest_below_or_equal_threshold_gap_after_100ms_ms": max((r["duration_ms"] for r in off), default=0.),
            "longest_continuous_gate_ms": longest,
            "has_continuous_750ms_gate": longest >= 750.,
            "maximum_filtered_grooming_rate_hz": max(r["grooming_left_filtered_hz"] for r in trace),
            "gated_intervals": on, "below_threshold_intervals_after_100ms": off,
            "network_voltage_min_at_5ms_samples_mv": min(r["network_voltage_min_mv"] for r in trace),
            "network_voltage_max_at_5ms_samples_mv": max(r["network_voltage_max_mv"] for r in trace),
            "recorded_cells": [{"body_id": int(graph.neuron_ids[i]), "type": graph.neurons.type.iloc[i],
                                "source": bool(i in source), "spikes": len(spike_times[int(graph.neuron_ids[i])]),
                                "spike_times_ms": spike_times[int(graph.neuron_ids[i])]}
                               for i in monitored], "trace": trace}


def main():
    graph = Connectome.load(GRAPH, verify=True)
    source = graph.select(F_TYPES, side="L", nerve="AN")
    dns = graph.select(["DNg62", "DNge078"])
    assert len(source) == 42
    assert graph.neuron_ids[dns].tolist() == [13624, 14537, 15148, 36541]
    # Frozen small diagnostic, declared before any run; no adaptive rate search.
    conditions = [(rate, blocked, seed) for rate in (0., 40., 100.)
                  for blocked in ((False,) if rate == 0 else (False, True))
                  for seed in (11, 12)]
    files = ["fruitfly/neural.py", "fruitfly/sensors.py", "fruitfly/data.py",
             "scripts/check_grooming_gate.py", "scripts/check_grooming_sensory_route.py",
             "tmp/grooming-audit/hampel2015.xml", "tmp/grooming-audit/shiu2024.xml"]
    report = {"completed": False, "purpose": "Full-graph JO-F afferent activation diagnostic; no direct DN stimulation, rate fitting or runtime changes",
              "graph": {"manifest_sha256": sha256(GRAPH / "manifest.json"), "manifest": graph.manifest},
              "source_sha256": {p: sha256(Path(p)) for p in files},
              "prespecified_conditions": conditions,
              "protocol": "Left AN JO-FD1/FD2/FV anatomical union; full Shiu graph; 105 actual zero-rate ORN indices (L then R) followed by 42 JO-F indices. No taste/proprioceptive/DN drive. Each condition starts from rest and identical seed. Source-output suppression retains incoming connections and afferent spikes.",
              "input_limit": "Rates are arbitrary independent Poisson inputs, not measured JO-F rates or a touch/dust transducer. Shiu applies large direct voltage events and disables refractory time for every listed input, including zero-rate ORNs. DNs remain undriven and keep default refractory dynamics.",
              "gate_semantics": "Actual MotorDecoder: mean across exact left DNg62/DNge078, 50 ms exponential filter, strict >10 Hz. Decoded bins correspond to held actions in the runner. Voltage extrema sampled only every 5 ms. A 750 ms gate checks scheduling only, not movement.",
              "source_identity_limit": "Hampel2020 renamed aJO as JO-F; experimental JO-F drivers additionally label a small JO-EVP population. No verified mapping of older FVA/FDL/FVL/FDA/FDP subdivisions onto male FD1/FD2/FV. All 42 anatomical F cells retained, including two FD2 with wind_gravity subclass.",
              "primary_sources": ["https://doi.org/10.7554/eLife.08758", "https://doi.org/10.7554/eLife.59976", "https://doi.org/10.1038/s41586-024-07763-9", "https://doi.org/10.1016/j.cell.2026.08.015"],
              "anatomy": anatomy(graph, source, dns), "conditions": []}
    output = Path("validation/grooming-sensory-route.json")
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    for rate, blocked, seed in conditions:
        result = run(graph, source, dns, seed, rate, blocked)
        report["conditions"].append(result)
        output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
        print(rate, "blocked", blocked, "seed", seed, "source", result["source_spikes"],
              "DN", [c["spikes"] for c in result["recorded_cells"] if not c["source"]],
              "gate", result["gate_fraction_after_100ms"], "longest", result["longest_continuous_gate_ms"], flush=True)
    paired_checks = []
    for rate in (40., 100.):
        for seed in (11, 12):
            intact, suppressed = [c for c in report["conditions"]
                                  if c["source_per_cell_poisson_hz"] == rate and c["seed"] == seed]
            def sources(c):
                return [(v["body_id"], v["spike_times_ms"]) for v in c["recorded_cells"] if v["source"]]
            matched = sources(intact) == sources(suppressed)
            assert matched, "Source spike trains changed in paired control; interpret separately"
            assert suppressed["non_source_network_spikes"] == 0
            paired_checks.append({"source_per_cell_poisson_hz": rate, "seed": seed,
                                  "all_source_spike_times_identical": matched,
                                  "suppressed_non_source_spikes": suppressed["non_source_network_spikes"],
                                  "input_order_identical": intact["input_order_body_ids"] == suppressed["input_order_body_ids"]})
    report["paired_checks"] = paired_checks
    report["completed"] = True
    report["sources_unchanged_after_run"] = all(sha256(Path(p)) == h for p,h in report["source_sha256"].items())
    assert report["sources_unchanged_after_run"]
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    plot(report)


def plot(report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True, sharey=True)
    for row, rate in enumerate((40., 100.)):
        for col, seed in enumerate((11, 12)):
            ax = axes[row, col]
            for blocked, color, label in ((False, "#2166ac", "Intact JO-F output"),
                                          (True, "#737373", "JO-F output suppressed")):
                result = next(c for c in report["conditions"] if c["seed"] == seed
                              and c["source_per_cell_poisson_hz"] == rate
                              and c["source_outgoing_suppressed"] == blocked)
                times = [t["held_action_start_ms"] / 1000 for t in result["trace"]]
                filtered = [t["grooming_left_filtered_hz"] for t in result["trace"]]
                ax.step(times, filtered, where="post", color=color, label=label, linewidth=1.3)
            ax.axhline(10., color="#d95f02", linestyle="--", linewidth=1, label="Gate >10 Hz")
            ax.set_title(f"JO-F input {rate:g} Hz/cell · seed {seed}", fontsize=10)
            ax.grid(alpha=.2)
            ax.set_xlim(0, 1.25)
            if row == 1:
                ax.set_xlabel("Held action time (s)")
            if col == 0:
                ax.set_ylabel("Left grooming readout (Hz)\n50 ms filtered mean of 2 DNs")
    axes[0, 0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Artificial JO-F activation reaches a sustained model gate at 100 Hz", fontsize=12)
    fig.text(.5, .01, "Full MaleCNS · unchanged Shiu baseline · arbitrary neural inputs · no physical stimulus or body simulated", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, .96))
    fig.savefig("validation/grooming-sensory-route.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
