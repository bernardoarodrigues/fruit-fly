#!/usr/bin/env python3
"""Read current male interface identities and summarize already-recorded assays.

This does not rerun neural/physical dynamics, change the graph, or reconstruct
Eon's unavailable embodied interface. Superclasses describe whole neurons, not
the anatomical location of each synapse.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.data import Connectome, sha256
from fruitfly.sensors import MotorDecoder, TasteEncoder


def main():
    graph_dir = ROOT / "data/processed/malecns_v1"
    graph = Connectome.load(graph_dir, verify=True)
    cells = graph.neurons
    decoder = MotorDecoder(graph, enable_grooming=True)
    taste = TasteEncoder(graph)
    selected = np.unique(np.concatenate(list(decoder.groups.values())))
    edges = np.flatnonzero(np.isin(graph.targets, selected))
    sources = np.searchsorted(graph.indptr, edges, side="right") - 1
    contacts = np.load(graph_dir / "contact_counts.npy", mmap_mode="r")
    incoming = {}
    for index in selected:
        keep = graph.targets[edges] == index
        e, s = edges[keep], sources[keep]
        classes = cells.superclass.iloc[s].to_numpy()
        rows = []
        for superclass in sorted(set(classes)):
            take = classes == superclass
            w = graph.weights[e[take]]
            c = contacts[e[take]]
            rows.append({"source_superclass": superclass, "neuron_pair_edges": int(take.sum()),
                         "contacts": int(c.sum()), "positive_rule_contacts": int(c[w > 0].sum()),
                         "negative_rule_contacts": int(c[w < 0].sum()),
                         "zero_rule_contacts": int(c[w == 0].sum())})
        assert sum(r["neuron_pair_edges"] for r in rows) == len(e)
        assert sum(r["contacts"] for r in rows) == int(contacts[e].sum())
        incoming[str(int(cells.bodyId.iloc[index]))] = rows

    def identities(indices):
        names = ["bodyId", "type", "synonyms", "flywireType", "somaSide", "rootSide",
                 "superclass", "entryNerve", "consensus_nt", "model_sign"]
        return json.loads(cells.iloc[indices][names].to_json(orient="records"))

    old_path = ROOT / "validation/taste-contact/results.json"
    old = json.loads(old_path.read_text())
    summary = []
    for condition in old["conditions"]:
        start, end = condition["initial"], condition["final"]
        displacement = (np.array(end["pose"]["position_mm"]) -
                        np.array(start["pose"]["position_mm"]))
        summary.append({"condition": condition["condition"], "duration_s": end["t_s"],
                        "graph_sha256": end["neural"]["graph_sha256"],
                        "final_behavior": end["behavior"], "final_motor": end["motor"],
                        "final_smoothed_readout_rates_hz": end["neural"]["output_rates"],
                        "xy_net_displacement_mm": float(np.linalg.norm(displacement[:2])),
                        "food_ingested_normalized": end["physiology"]["food_ingested"],
                        "sampled_minimum_voltage_mv": condition["min_voltage_mv"]})
    # These names are cited in the earlier odor diagnostic. Classifying them is
    # an identity check; it does not recompute their dynamic contributions.
    names = ["VES104", "GNG127", "CB0677", "PS059", "MBON31", "MBON32"]
    inhibitory_sources = graph.select(names)
    assert set(cells.type.iloc[inhibitory_sources]) == set(names)
    assert cells.superclass.iloc[inhibitory_sources].eq("cb_intrinsic").all()
    assert set(graph.neuron_ids[decoder.groups["forward"]]) == {13805, 230783}
    assert all(r["duration_s"] == .5 for r in summary)
    assert all(r["food_ingested_normalized"] == 0 for r in summary if r["condition"] != "taste")
    paths = [Path(__file__), ROOT / "fruitfly/sensors.py", ROOT / "fruitfly/data.py",
             ROOT / "fruitfly/body.py", ROOT / "fruitfly/simulation.py", old_path,
             ROOT / "validation/motor-connectivity.json", graph_dir / "manifest.json"]
    result = {
        "purpose": "Current interface identities, static source classes and saved assay comparison; no new simulation",
        "inputs": {str(p.relative_to(ROOT)): {"sha256": sha256(p), "bytes": p.stat().st_size}
                   for p in paths},
        "graph": {k: graph.manifest[k] for k in ["dataset", "neurons", "edges", "retained_synaptic_contacts"]},
        "readouts": {name: identities(indices) for name, indices in decoder.groups.items()},
        "sweet_tarsal_inputs": {name: identities(indices) for name, indices in taste.groups.items()},
        "incoming_counts_by_source_superclass": incoming,
        "previously_named_odor_assay_inhibitors": identities(inhibitory_sources),
        "saved_taste_contact_assay": summary,
        "interpretation_limits": [
            "Same named output types do not prove the same specimen, stimulus, numerical dynamics or motor gain as Eon.",
            "A central-brain-intrinsic presynaptic cell can receive upstream activity influenced by the VNC; these counts cannot test its causal contribution.",
            "Whole-neuron superclasses do not locate individual input synapses; no brain-only or VNC-removal graph is constructed.",
            "Final readout rates are exponentially smoothed snapshots, not whole-trial firing rates.",
            "Net displacement from an on-food start is not successful food approach or a distance traveled measure.",
            "Muting motor outputs changes future physical contacts and afferents; these closed-loop conditions are not matched neural inputs.",
            "No literal Eon replication, parameter change, new biological fit or new behavior is claimed."
        ],
    }
    out = ROOT / "validation/eon-interface-comparison.json"
    if out.exists():
        raise FileExistsError(f"Preserve the existing comparison: {out}")
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(out.relative_to(ROOT)), "sha256": sha256(out),
                      "readout_neurons": len(selected), "incoming_edges": len(edges),
                      "taste_conditions": summary}, indent=2))


if __name__ == "__main__":
    main()
