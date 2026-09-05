"""Audit released optic-lobe columns and tentative R1-R6 cartridge assignments.

No camera/visual-angle mapping or neural input is installed by this analysis.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome


def main():
    path = Path("data/processed/malecns_v1")
    graph = Connectome.load(path, verify=True)
    contacts = np.load(path/"contact_counts.npy", mmap_mode="r", allow_pickle=False)
    cells = graph.neurons
    sides = cells.rootSide.fillna(cells.somaSide)
    hexes = cells[["assignedOlHex1", "assignedOlHex2"]].to_numpy(float)
    assigned = np.isfinite(hexes).all(axis=1)
    assert np.all(hexes[assigned] == np.rint(hexes[assigned]))
    types = cells.type.to_numpy()
    output = {"scope": __doc__, "completed": False,
        "anatomical_source": "MaleCNS v1.0; column labels are released annotations",
        "source_hashes": {name: meta["sha256"] for name, meta in
                          (graph.manifest["arrays"] | graph.manifest["metadata"]).items()},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "assignment_rule": {"types": ["R1-R6"], "postsynaptic_types": ["L1", "L2"],
            "same_side_only": True, "minimum_contacts_per_target_type": 10,
            "minimum_dominant_column_fraction_per_type": .9,
            "require_unique_top_column_and_L1_L2_agreement": True,
            "status": "exploratory connectivity inference, not measured retinal receptive fields"},
        "inventory": {}, "inferred_R1_R6": []}
    inventory_types = ["R1-R6", "R7p", "R7y", "R7_unclear", "R8p", "R8y", "R8_unclear",
                       "L1", "L2", "L3", "L5", "Mi1", "Mi4", "Mi9", "C3", "T1", "Tm1", "Tm2", "Tm9", "Tm20", "T4a", "T5a"]
    for kind in inventory_types:
        mask = types == kind
        output["inventory"][kind] = {"total": int(mask.sum()), "by_side": {side: {
            "count": int((mask & sides.eq(side)).sum()),
            "assigned_hex_count": int((mask & sides.eq(side) & assigned).sum()),
            "unique_assigned_columns": len({tuple(x) for x in hexes[mask & sides.eq(side) & assigned]})}
            for side in ("L", "R")},
            "transmitter_counts": cells.loc[mask, "consensus_nt"].fillna("unknown").value_counts().to_dict()}
    for source in np.flatnonzero(types == "R1-R6"):
        side = sides.iloc[source]
        start, end = graph.indptr[source:source+2]
        targets, counts = graph.targets[start:end], contacts[start:end]
        record = {"bodyId": int(graph.neuron_ids[source]), "side": side, "target_evidence": {}}
        selected = []
        for kind in ("L1", "L2"):
            mask = (types[targets] == kind) & sides.iloc[targets].eq(side).to_numpy() & assigned[targets]
            columns = Counter()
            for target, count in zip(targets[mask], counts[mask]):
                columns[tuple(int(x) for x in hexes[target])] += int(count)
            ranked = sorted(columns.items(), key=lambda kv: (-kv[1], kv[0]))
            total = sum(columns.values())
            top, strength = ranked[0] if ranked else (None, 0)
            unique = bool(ranked and (len(ranked) == 1 or ranked[1][1] < strength))
            accepted = bool(total >= 10 and unique and strength/total >= .9)
            record["target_evidence"][kind] = {"contacts_to_assigned_columns": total,
                "dominant_column": top, "dominant_contacts": strength,
                "dominant_fraction": strength/total if total else None,
                "column_count": len(columns), "passes_rule": accepted}
            selected.append(top if accepted else None)
        agree = selected[0] is not None and selected[0] == selected[1]
        record["inferred_column"] = selected[0] if agree else None
        output["inferred_R1_R6"].append(record)
    output["summary"] = {}
    for side in ("L", "R"):
        rows = [r for r in output["inferred_R1_R6"] if r["side"] == side]
        accepted = [r for r in rows if r["inferred_column"] is not None]
        coverage = Counter(tuple(r["inferred_column"]) for r in accepted)
        output["summary"][side] = {"retained_R1_R6": len(rows), "inferred_R1_R6": len(accepted),
            "unresolved_R1_R6": len(rows)-len(accepted), "covered_columns": len(coverage),
            "accepted_R1_R6_count_per_column_histogram": dict(sorted(Counter(coverage.values()).items())),
            "coverage": [{"hex1": h1, "hex2": h2, "inferred_R1_R6_count": count}
                         for (h1, h2), count in sorted(coverage.items())]}
    output["completed"] = True
    Path("validation/visual-column-audit.json").write_text(json.dumps(output, indent=2, allow_nan=False)+"\n")
    print(json.dumps({side: {k: v for k, v in value.items() if k != "coverage"}
                      for side, value in output["summary"].items()}, indent=2))


if __name__ == "__main__":
    main()
