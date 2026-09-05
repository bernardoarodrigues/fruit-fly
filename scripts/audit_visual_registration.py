"""Check the official MaleCNS column join; enumerate unselected lattice maps.

This never assigns a visual direction to a MaleCNS cell. Lattice symmetries are
bookkeeping alternatives, not a fit to coverage, neural output, or behaviour.
"""
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "dbafc73124b5c96e96429cdf2a89d067cae841bc"


def main():
    source_path = "results/exchange/ME_assigned_columns.csv"
    url = f"https://raw.githubusercontent.com/reiserlab/male-drosophila-visual-system-connectome-code/{COMMIT}/{source_path}"
    local = ROOT/"data/raw/visual-retinotopy/nern2025/ME_assigned_columns.csv"
    if not local.exists():
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(300_001)
        if len(content) > 300_000:
            raise ValueError("Source exceeds the declared small-file limit")
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
    old = pd.read_csv(local)
    metadata_path = ROOT/"data/processed/malecns_v1/neurons.feather"
    new = pd.read_feather(metadata_path)
    joined = old.merge(new[["bodyId", "type", "rootSide", "somaSide", "assignedOlHex1", "assignedOlHex2"]],
                       on="bodyId", how="left", validate="one_to_one", indicator=True)
    assigned = joined.assignedOlHex1.notna() & joined.assignedOlHex2.notna()
    agrees = joined.assigned_hex1.eq(joined.assignedOlHex1) & joined.assigned_hex2.eq(joined.assignedOlHex2)
    checks = {"every_bodyId_retained": bool(joined._merge.eq("both").all()),
              "every_cell_right_side": bool(joined.rootSide.fillna(joined.somaSide).eq("R").all()),
              "every_type_agrees": bool(joined.neuron_type.eq(joined.type).all()),
              "every_hex_pair_agrees": bool((assigned & agrees).all())}
    if not all(checks.values()):
        raise AssertionError(checks)
    # Axial coordinates whose basis vectors subtend120 degrees. Rotation is
    # one60-degree step; reflection swaps the two axes. No preferred map.
    rotation = np.array([[0, 1], [-1, 1]], dtype=np.int64)
    reflection = np.array([[0, 1], [1, 0]], dtype=np.int64)
    alternatives = []
    for reflected in (False, True):
        for turns in range(6):
            matrix = np.linalg.matrix_power(rotation, turns)
            if reflected:
                matrix = reflection @ matrix
            preserves_up = np.array_equal(matrix @ np.array([1, 1]), [1, 1])
            alternatives.append({"rotation_steps_60deg": turns, "reflected": reflected,
                "matrix_on_column_vector_pq": matrix.tolist(),
                "status": "unresolved" if preserves_up else "conditionally_rejected",
                "reason": "No homologous male-to-template origin/anterior landmark proven" if preserves_up
                    else "Would change the positive vertical diagonal if both source grids share that anatomical convention"})
    result = {
        "source": {"url": url, "commit": COMMIT, "bytes": local.stat().st_size,
                   "sha256": hashlib.sha256(local.read_bytes()).hexdigest()},
        "malecns_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_cells": len(old), "unique_right_columns": len(old[["assigned_hex1", "assigned_hex2"]].drop_duplicates()),
        "checks": checks,
        "nern_display_convention": "Docs label hex1→q, hex2→p and origin[18,19]. Centering gives p=hex2-19,q=hex1-18; this alone is not a Zhao registration.",
        "geometric_alternatives": alternatives,
        "unresolved_translation_family": "With a common equator row imposed, integer(k,-k) shifts still preserve that row. The cross-specimen central-meridian origin is not verified; k is not selected. Without matched upper/lower equator rows there is an additional one-row phase ambiguity. This is not an exhaustive nonrigid registration model.",
        "orientation_caveat": "Nern diagram places +p toward upper left and +q upper right; Zhao's plotted basis places +p upper right and +q upper left. A plotting reflection must not silently become an anatomical side swap.",
        "selected_transform": None,
        "rejection_of_automatic_selection": "Grid overlap, matched-facet count, visual attractiveness or useful neural output cannot resolve missing biological landmarks.",
        "remaining_evidence": ["Male right-eye upper and lower equator row identities tied to the source chirality/count audit",
                               "A homologous anterior/posterior landmark and central-meridian column in the male and female grids",
                               "Explicit handling of different eye/column counts and local lattice defects",
                               "A documented head-coordinate transform from female optical template to physical camera/body"],
        "completed": True, "registration_completed": False,
    }
    output = ROOT/"validation/visual-retinotopy/registration-boundary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"source_cells": len(old), "checks": checks, "selected_transform": None, "output": str(output)}))


if __name__ == "__main__":
    main()
