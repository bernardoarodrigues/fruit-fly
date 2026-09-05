"""Fixed full-MaleCNS grooming probe; no gain selection or body simulation."""
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


def intervals(mask, dt_ms, start_ms=0.):
    """Contiguous half-open held-action intervals, including clipped endpoints."""
    padded = np.r_[False, mask, False].astype(np.int8)
    changes = np.diff(padded)
    starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
    return [{"start_ms": float(start_ms + a*dt_ms), "end_ms": float(start_ms + b*dt_ms),
             "duration_ms": float((b-a)*dt_ms)} for a, b in zip(starts, ends)]


def run(graph, seed, rate_hz):
    dt_ms, duration_ms, discard_ms = 5., 1250., 100.
    brain = LIFNetwork.from_connectome(graph, seed=seed)
    motor = MotorDecoder(graph, enable_grooming=True, grooming_threshold_hz=10.)
    sensory = SensoryEncoder(graph, SensoryParameters(odor_baseline_hz=0., odor_max_increment_hz=0.))
    observation = {"antenna_odor": [0., 0.], "taste_food": False, "taste_water": False}
    odor = sensory.encode(observation, dt_ms/1000)
    probe = motor.groups["grooming_left"]
    assert graph.neuron_ids[probe].tolist() == [13624, 14537]
    drive_indices = np.r_[odor.indices, probe]
    drive = SparseDrive(drive_indices, rates_hz=np.r_[odor.rates_hz, np.full(len(probe), rate_hz)])
    outputs = np.unique(np.concatenate(list(motor.groups.values())))
    # Same compile-and-reset sequence as SimulationRunner; no experiment state
    # or random draws survive this warm-up.
    brain.advance(brain.parameters.dt_ms, outputs=[])
    brain.reset(seed=seed)
    counts = np.zeros(len(probe), dtype=np.int64)
    spikes = {int(cell): [] for cell in graph.neuron_ids[probe]}
    trace, network_spikes, traversed_edges = [], 0, 0
    started = perf_counter()
    for step in range(round(duration_ms/dt_ms)):
        batch = brain.advance(dt_ms, drive=drive, outputs=outputs)
        action = motor.decode(batch, dt_ms/1000, observation)
        counts += batch.counts(probe)
        network_spikes += batch.total_spikes
        traversed_edges += batch.traversed_edges
        for index, body_id in zip(probe, graph.neuron_ids[probe]):
            spikes[int(body_id)].extend(batch.times_ms[batch.indices == index].tolist())
        assert np.all(np.isfinite(brain.voltage_mv)) and np.all(np.isfinite(brain.synaptic_mv))
        trace.append({"neural_sample_time_ms": float((step+1)*dt_ms),
                      "held_action_start_ms": float(step*dt_ms),
                      "held_action_end_ms": float((step+1)*dt_ms),
                      "grooming_rate_hz": motor.rates["grooming_left"],
                      "behavior": action["behavior"],
                      "probe_voltage_mv": brain.voltage_mv[probe].tolist(),
                      "network_voltage_min_mv": float(brain.voltage_mv.min()),
                      "network_voltage_max_mv": float(brain.voltage_mv.max())})
    wall_seconds = perf_counter()-started
    gate = np.array([row["behavior"] == "groom" for row in trace])
    rates = np.array([row["grooming_rate_hz"] for row in trace])
    voltage = np.array([row["probe_voltage_mv"] for row in trace])
    kept = round(discard_ms/dt_ms)
    on, off = intervals(gate, dt_ms), intervals(~gate[kept:], dt_ms, discard_ms)
    longest = max((r["duration_ms"] for r in on), default=0.)
    return {"seed": seed, "probe_hz": rate_hz, "duration_ms": duration_ms,
            "discard_for_late_stats_ms": discard_ms, "coupling_ms": dt_ms,
            "parameters": asdict(brain.parameters), "input_order_body_ids": graph.neuron_ids[drive_indices].tolist(),
            "zero_rate_odor_neurons": len(odor.indices),
            "network_spikes": network_spikes, "traversed_edges": traversed_edges,
            "wall_seconds": wall_seconds, "gate_fraction": float(gate.mean()),
            "gate_fraction_after_100ms": float(gate[kept:].mean()),
            "minimum_filtered_rate_after_100ms_hz": float(rates[kept:].min()),
            "longest_below_or_equal_threshold_gap_after_100ms_ms": max((r["duration_ms"] for r in off), default=0.),
            "longest_continuous_gate_ms": longest,
            "has_continuous_750ms_gate": longest >= 750.,
            "gated_intervals": on, "below_threshold_intervals_after_100ms": off,
            "network_voltage_min_at_5ms_samples_mv": min(r["network_voltage_min_mv"] for r in trace),
            "network_voltage_max_at_5ms_samples_mv": max(r["network_voltage_max_mv"] for r in trace),
            "probe_cells": [{"body_id": int(body_id), "type": graph.neurons.type.iloc[index],
                             "spikes": int(count), "output_rate_hz": float(count/(duration_ms/1000)),
                             "voltage_sample_min_mv": float(voltage[:,j].min()),
                             "voltage_sample_mean_mv": float(voltage[:,j].mean()),
                             "voltage_final_mv": float(voltage[-1,j]), "spike_times_ms": spikes[int(body_id)]}
                            for j,(index,body_id,count) in enumerate(zip(probe,graph.neuron_ids[probe],counts))],
            "trace": trace}


def main():
    graph = Connectome.load("data/processed/malecns_v1", verify=True)
    report = {"completed": False, "purpose": "Prespecified direct-stimulation grooming positive-control diagnostic; no gain selection",
              "graph": {"neurons": len(graph.neuron_ids), "edges": len(graph.targets), "manifest": graph.manifest},
              "source_sha256": {p: sha256(Path(p)) for p in ["fruitfly/neural.py", "fruitfly/sensors.py", "fruitfly/simulation.py", "configs/male-grooming-probe.json"]},
              "protocol": "Full graph, Shiu baseline, rates 0/40/100 Hz, seeds 11/12, continuous 1.25 s, actual SensoryEncoder zero-rate odor indices in L then R order followed by left grooming indices; taste/proprioception absent",
              "gate_semantics": "Actual MotorDecoder with 50 ms exponential filter and strict >10 Hz mean across 2 cells; no hysteresis. Each decoded value is held for the following body 5 ms step in SimulationRunner.",
              "sampling_limit": "Spike times are exact engine timestamps. Voltage extrema are sampled only at 5 ms coupling boundaries, not every neural integration step.",
              "body_limit": "750 ms uninterrupted gate is a necessary scheduling condition for 250 ms entry + 500 ms playback if withdrawal cancels; body dynamics and completion are not simulated here.",
              "conditions": []}
    output = Path("validation/grooming-gate.json")
    for rate in (0.,40.,100.):
        for seed in (11,12):
            result = run(graph,seed,rate)
            report["conditions"].append(result)
            output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
            print(rate,seed, "probe_spikes", [c["spikes"] for c in result["probe_cells"]],
                  "gate_late",round(result["gate_fraction_after_100ms"],3),
                  "max_off_ms",result["longest_below_or_equal_threshold_gap_after_100ms_ms"],
                  "max_on_ms",result["longest_continuous_gate_ms"],flush=True)
    report["completed"] = True
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
