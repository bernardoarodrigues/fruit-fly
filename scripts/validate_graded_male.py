"""Numerical full-graph mixed-backend assay, not a fit to measured APN2 physiology."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.conductance import ConductanceDrive, ConductanceNetwork, ConductanceParameters
from fruitfly.data import Connectome
from fruitfly.graded import GradedPopulationSpec, MixedNetwork


def main():
    graph = Connectome.load(Path("data/processed/malecns_v1"), verify=True)
    candidates = graph.select(["SAD003", "SAD004"])
    assert len(candidates) == 16
    # ALL values below are explicit illustrative hypotheses, not fitted constants.
    spec = GradedPopulationSpec(tuple(graph.neuron_ids[candidates]), resting_mv=-35,
        membrane_tau_ms=20, release_reference_mv=-35, release_baseline_hz_equiv=20,
        release_gain_hz_equiv_per_mv=2, release_max_hz_equiv=100, release_tau_ms=10)
    p = ConductanceParameters()
    report = {"scope": __doc__, "complete": False,
        "identity": "SAD003/SAD004 are putative APN2 morphological candidates; female-to-male transfer unresolved",
        "parameter_status": "Every graded and release parameter is an engineering hypothesis; no empirical fit",
        "graded_specification": asdict(spec), "conductance_parameters": asdict(p),
        "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path("fruitfly/graded.py"), Path("fruitfly/conductance.py"))},
        "neurons": len(graph.neuron_ids), "edges": len(graph.weights), "conditions": []}
    output = Path("validation/graded-male-smoke.json")
    output.parent.mkdir(exist_ok=True)
    for name in ("spiking_reference_no_input", "graded_tonic", "graded_outputs_blocked", "graded_hyperpolarized"):
        net = (ConductanceNetwork.from_connectome(graph, parameters=p, seed=11)
               if name == "spiking_reference_no_input" else
               MixedNetwork.from_connectome(graph, parameters=p, seed=11, graded_populations=[spec]))
        net.step(outputs=[])
        net.reset(seed=11)
        if name == "graded_outputs_blocked":
            net.ablate(candidates)
        samples = []
        spikes = candidate_spikes = edge_visits = 0
        start = time.perf_counter()
        for step in range(80):
            current = -10 if name == "graded_hyperpolarized" and step >= 40 else 0
            batch = net.advance(5, drive=ConductanceDrive(candidates, current_mv=current), outputs=candidates)
            candidate_spikes += len(batch.indices)
            spikes += batch.total_spikes
            edge_visits += batch.traversed_edges
            sample = {"t_ms": net.time_ms, "imposed_current_mv": current,
                "candidate_voltage_mv": net.voltage_mv[candidates].tolist(),
                "release_hz_equiv": net.release_hz_equiv.tolist() if isinstance(net, MixedNetwork) else None,
                "network_spikes": batch.total_spikes,
                "voltage_min_mv": float(net.voltage_mv.min()), "voltage_max_mv": float(net.voltage_mv.max())}
            samples.append(sample)
            if not (np.isfinite(net.voltage_mv).all() and np.isfinite(net.excitatory_g).all()
                    and np.isfinite(net.inhibitory_g).all()):
                raise AssertionError("Nonfinite neural state")
        elapsed = time.perf_counter()-start
        condition = {"name": name, "graph_sha256": net.graph_sha256, "duration_ms": net.time_ms,
            "wall_seconds_excluding_load_compile_hash": elapsed,
            "total_spikes": spikes, "candidate_spikes": candidate_spikes,
            "traversed_edges": edge_visits, "final_conductance_sum_gleak": float(net.excitatory_g.sum()+net.inhibitory_g.sum()),
            "samples": samples}
        report["conditions"].append(condition)
        output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
        print(name, {k: v for k, v in condition.items() if k != "samples"}, flush=True)
    conditions = {c["name"]: c for c in report["conditions"]}
    mixed = [c for c in report["conditions"] if c["name"].startswith("graded_")]
    report["checks"] = {
        "same_full_graph": len({c["graph_sha256"] for c in report["conditions"]}) == 1,
        "graded_candidates_never_spike": all(c["candidate_spikes"] == 0 for c in mixed),
        "graded_output_transmits": conditions["graded_tonic"]["final_conductance_sum_gleak"] > 0,
        "blocked_sources_have_no_network_output": conditions["graded_outputs_blocked"]["total_spikes"] == 0
            and conditions["graded_outputs_blocked"]["final_conductance_sum_gleak"] == 0,
        "unstimulated_spiking_reference_silent": conditions["spiking_reference_no_input"]["total_spikes"] == 0,
        "release_nonnegative_bounded": all(0 <= value <= spec.release_max_hz_equiv
            for c in mixed for sample in c["samples"] for value in sample["release_hz_equiv"]),
    }
    report["complete"] = True
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["checks"], indent=2))
    if not all(report["checks"].values()):
        raise SystemExit("Mixed-backend full-graph check failed; retain and inspect evidence")


if __name__ == "__main__":
    main()
