#!/usr/bin/env python3
"""Exact MaleCNS wind-pathway annotation/contact inventory, not a sensor map."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome


def main():
    path = Path("data/processed/malecns_v1")
    graph = Connectome.load(path, verify=True)
    cells = graph.neurons
    contacts = np.load(path / "contact_counts.npy", mmap_mode="r", allow_pickle=False)
    jo = cells.type.fillna("").str.startswith("JO-")
    types = sorted(cells.loc[jo, "type"].unique())
    candidates = {"APN2_putative": ["SAD003", "SAD004"], "APN3_putative": ["SAD077"],
                  "WPN_putative": ["LHPV6q1"], "WLL_putative": ["LAL138"]}
    groups = {kind: graph.select([kind]) for kind in types}
    groups.update({kind: graph.select(names) for kind, names in candidates.items()})
    groups.update({"JO_C_anatomical_union": graph.select(["JO-CA1", "JO-CA2", "JO-CL", "JO-CM"]),
                   "JO_E_anatomical_union": graph.select([kind for kind in types if kind.startswith("JO-E")]),
                   "JO_F_former_aJO": graph.select([kind for kind in types if kind.startswith("JO-F")])})
    side = cells.rootSide.fillna(cells.somaSide)
    group_rows = {}
    for name, indices in groups.items():
        group_rows[name] = {"count": len(indices), "by_side": side.iloc[indices].value_counts(dropna=False).to_dict(),
                            "ids_by_side": {s: graph.neuron_ids[indices[side.iloc[indices].eq(s).to_numpy()]].tolist() for s in ["L", "R"]},
                            "types": sorted(cells.type.iloc[indices].dropna().unique()),
                            "subclass_counts": cells.subclass.iloc[indices].fillna("null").value_counts().to_dict(),
                            "transmitter_counts": cells.consensus_nt.iloc[indices].fillna("null").value_counts().to_dict()}
    selected = np.unique(np.concatenate(list(groups.values())))
    columns = ["bodyId", "type", "instance", "rootSide", "somaSide", "entryNerve", "superclass", "class", "subclass",
               "consensus_nt", "model_sign", "synonyms", "hemibrainType", "flywireType", "predicted_nt",
               "predicted_nt_confidence", "celltype_predicted_nt_confidence", "fruDsx"]
    node_records = json.loads(cells.iloc[selected][columns].to_json(orient="records"))
    for row, index in zip(node_records, selected):
        start, stop = graph.indptr[index:index+2]
        row.update(outgoing_neuron_pairs=int(stop-start),
                   outgoing_contacts=int(contacts[start:stop].sum()),
                   outgoing_nonzero_model_pairs=int(np.count_nonzero(graph.weights[start:stop])))

    destination_groups = {f"{name}_{s}": indices[side.iloc[indices].eq(s).to_numpy()]
                          for name, indices in groups.items() if name in candidates for s in ["L", "R"]}
    source_groups = {f"{name}_{s}": indices[side.iloc[indices].eq(s).to_numpy()]
                     for name, indices in groups.items() for s in ["L", "R"]}
    direct = []
    for source_name, source_indices in source_groups.items():
        for target_name, target_indices in destination_groups.items():
            raw_contacts = pairs = modeled_contacts = 0
            for source in source_indices:
                start, stop = graph.indptr[source:source+2]
                keep = np.isin(graph.targets[start:stop], target_indices)
                raw_contacts += int(contacts[start:stop][keep].sum())
                pairs += int(keep.sum())
                modeled_contacts += int(contacts[start:stop][keep & (graph.weights[start:stop] != 0)].sum())
            if pairs:
                direct.append({"source": source_name, "target": target_name, "neuron_pairs": pairs,
                               "raw_contacts": raw_contacts, "contacts_with_nonzero_model_weight": modeled_contacts})
    wpn_indices = groups["WPN_putative"]
    wpn_top_outputs = {}
    for source in wpn_indices:
        start, stop = graph.indptr[source:source+2]
        targets = graph.targets[start:stop]
        table = pd.DataFrame({"type": cells.type.iloc[targets].fillna("untyped").to_numpy(),
                              "side": side.iloc[targets].fillna("null").to_numpy(),
                              "contacts": contacts[start:stop], "weight_mv": graph.weights[start:stop]})
        wpn_top_outputs[str(int(graph.neuron_ids[source]))] = json.loads(
            table.groupby(["type", "side"], as_index=False).sum().sort_values("contacts", ascending=False).head(15).to_json(orient="records"))
    exact_alias_absent = {}
    for label in ["APN2", "APN3", "WPN", "aJO", "bJO"]:
        cols = ["type", "synonyms", "flywireType", "hemibrainType", "matchingNotes", "supertype", "instance"]
        found = pd.concat([cells[c].fillna("").astype(str).str.contains(label, case=False, regex=False) for c in cols], axis=1).any(axis=1)
        exact_alias_absent[label] = int(found.sum())
    result = {"completed": True, "dataset": graph.manifest["dataset"],
              "annotation_sha256": graph.manifest["metadata"]["neurons.feather"]["sha256"],
              "weight_sha256": graph.manifest["arrays"]["weights.npy"]["sha256"],
              "jo_total": int(jo.sum()), "jo_by_side": side.loc[jo].value_counts().to_dict(),
              "literal_alias_matches": exact_alias_absent, "groups": group_rows,
              "candidate_crosswalk": candidates, "crosswalk_source": "Hulse et al. eLife2021 Fig9, https://elifesciences.org/articles/66039/figures",
              "crosswalk_status": "Putative morphological correspondence; not exact identity of all recorded cells in Suver2019",
              "nodes": node_records, "direct_group_contacts": direct, "wpn_top_outputs": wpn_top_outputs,
              "interpretation": "Exact annotation and raw contact inventory. Anatomical JO-C/E unions do not establish subtype tuning. aJO was renamed JO-F; bJO unresolved. Consensus unclear WPN weights stay zero. No neural mapping, transmitter override or physiological calibration applied."}
    output = Path("validation/wind-annotation-audit.json")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("JO", result["jo_total"], result["jo_by_side"])
    for name in ["JO_C_anatomical_union", "JO_E_anatomical_union", "JO_F_former_aJO", *candidates]:
        print(name, {key: group_rows[name][key] for key in ["count", "by_side", "types", "subclass_counts"]})
    for row in node_records:
        if row["type"] == "LHPV6q1":
            print("WPN", row)
    print("Saved", output)


if __name__ == "__main__":
    main()
