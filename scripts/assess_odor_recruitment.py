"""Frozen broad-versus-sparse ORN recruitment diagnostic; no motor fitting.

All ORN_* includes 53 named types, not an exact Orco-GAL4 experimental map.
Equal-per-cell and equal-total-event conditions distinguish recruitment from
input quantity. No wind or body is present in this brain-only experiment.
"""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.conductance import ConductanceNetwork, ConductanceParameters
from fruitfly.data import Connectome
from fruitfly.neural import SparseDrive


def main():
    graph = Connectome.load("data/processed/malecns_v1", verify=True)
    sparse = graph.select(["ORN_DM1", "ORN_DM4"])
    broad = np.flatnonzero(graph.neurons.type.fillna("").str.startswith("ORN_")).astype(np.int32)
    dn = np.flatnonzero(graph.neurons.superclass.eq("descending_neuron")).astype(np.int32)
    if (len(broad), len(dn), len(sparse)) != (2635, 1314, 106):
        raise ValueError("Sensory or descending inventory changed; inspect before running")
    named = graph.select(["DNg97", "DNa01", "DNa02", "DNb05", "DNg34", "DNp09"])
    outputs = np.unique(np.r_[broad, dn, named])
    params = ConductanceParameters(dt_ms=.2, voltage_method="pade22")
    brain = ConductanceNetwork.from_connectome(graph, parameters=params, seed=11)
    brain.advance(.2, outputs=[])
    conditions = [("no_input", sparse, 0., False),
                  ("two_glomeruli_100", sparse, 100., False),
                  ("broad_equal_per_cell", broad, 100., False),
                  ("broad_equal_total", broad, 100 * len(sparse) / len(broad), False),
                  ("broad_output_blocked", broad, 100., True)]
    result = {"scope": __doc__, "graph_sha256": brain.graph_sha256,
              "neurons": len(graph.neuron_ids), "edges": len(graph.targets),
              "parameters": asdict(params), "seeds": [11, 12],
              "input_ids": {"two_glomeruli": graph.neuron_ids[sparse].tolist(),
                            "all_named_orns": graph.neuron_ids[broad].tolist()},
              "conditions": [], "complete": False, "selected_motor_policy": None}
    path = Path("validation/odor-recruitment.json")
    for seed in result["seeds"]:
        for name, sources, rate, blocked in conditions:
            brain.reset(seed=seed)
            if blocked:
                brain.ablate(sources)
            trial = {"name": name, "seed": seed, "input_count": len(sources),
                     "input_event_rate_hz": rate, "outgoing_blocked": blocked, "phases": []}
            for phase, duration_ms, event_rate in (("baseline", 50, 0), ("on", 100, rate), ("off", 100, 0)):
                start = time.perf_counter()
                drive = SparseDrive(sources, rates_hz=np.full(len(sources), event_rate))
                spikes = brain.advance(duration_ms, drive=drive, outputs=outputs)
                counts = np.bincount(spikes.indices, minlength=brain.n_neurons)
                rates = counts * 1000 / duration_ms
                trial["phases"].append({"name": phase, "duration_ms": duration_ms,
                    "wall_seconds": time.perf_counter() - start, "total_spikes": spikes.total_spikes,
                    "mean_input_population_rate_hz": float(rates[sources].mean()),
                    "active_dn_count": int(np.count_nonzero(counts[dn])),
                    "mean_dn_rate_hz": float(rates[dn].mean()),
                    "max_dn_rate_hz": float(rates[dn].max()),
                    "voltage_min_mv": float(brain.voltage_mv.min()),
                    "named_rates": [{"id": int(graph.neuron_ids[i]),
                                     "type": graph.neurons.type.iloc[i], "rate_hz": float(rates[i])}
                                    for i in named]})
            result["conditions"].append(trial)
            path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            print(seed, name, [(p["name"], p["total_spikes"], round(p["mean_dn_rate_hz"], 2))
                              for p in trial["phases"]], flush=True)
    result["complete"] = True
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
