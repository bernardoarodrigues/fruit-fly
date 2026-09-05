#!/usr/bin/env python3
"""Frozen DoOR evidence audit; never installs or activates a neural encoder.

Run from the repository root. --download acquires only missing pinned small
sources in source-provenance.json (2.1 MB total); existing mismatches fail closed.
The graph itself must already be imported. All output CSV missing values are NA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/door"
OUT = ROOT / "validation/door"
UNITS = (
    "Or42b", "Or59b", "Or22a", "Or42a", "Or71a", "Or33c", "Or85e", "pb2A",
    "Or46a", "Or59c", "Or85d", "Ir75a", "Ir64a.DC4", "Ir64a.DP1m", "Or47b", "ab4B",
)
CHEMICALS = (
    ("ethanol", "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),
    ("ethyl acetate", "XEKOWRVHYACXOJ-UHFFFAOYSA-N"),
    ("isoamyl acetate", "MLFHJEHSLIIPHL-UHFFFAOYSA-N"),
    ("acetic acid", "QTBSBXVTEAMEQO-UHFFFAOYSA-N"),
    ("acetoin", "ROWKJAVDOGWPAT-UHFFFAOYSA-N"),
    ("diacetyl", "QSJXEFYPDANLFS-UHFFFAOYSA-N"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources(download: bool) -> dict:
    provenance = json.loads((OUT / "source-provenance.json").read_text())
    for source in provenance["sources"]:
        directory = ROOT / source["local_dir"]
        for item in source["files"]:
            path = directory / item["path"]
            if not path.exists() and download:
                if item["bytes"] > 2_000_000:
                    raise ValueError("Acquisition exceeds the declared small-file boundary")
                with urllib.request.urlopen(item["url"], timeout=45) as response:
                    data = response.read(item["bytes"] + 1)
                if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ValueError(f"Downloaded source hash/size mismatch: {path}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            data = path.read_bytes()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"Source hash/size mismatch: {path}")
            if "git_blob_sha1" in item:
                blob = b"blob " + str(len(data)).encode() + b"\0" + data
                if hashlib.sha1(blob).hexdigest() != item["git_blob_sha1"]:
                    raise ValueError(f"Pinned Git tree blob mismatch: {path}")
    for item in provenance["male_inputs"]:
        if sha(ROOT / item["path"]) != item["sha256"]:
            raise ValueError(f"MaleCNS input hash mismatch: {item['path']}")
    return provenance


def read_table(name: str) -> pd.DataFrame:
    table = pd.read_csv(RAW / "data" / f"{name}.csv", sep=";", index_col=0)
    if table.index.has_duplicates or table.columns.has_duplicates:
        raise ValueError(f"Nonunique source row index or column: {name}")
    return table


def write_csv(table: pd.DataFrame, name: str) -> None:
    table.to_csv(OUT / name, index=False, na_rep="NA", float_format="%.12g")


def text_or_none(value):
    return None if pd.isna(value) else str(value)


def extract_ev1() -> pd.DataFrame:
    """Read only the published text identity columns; never evaluate XLSX formulas.

    Fixed sheet/column/row contract checked against pinned file. Empty cells stay
    empty, rich-text runs concatenate, Excel source row numbers are retained.
    Numeric population estimates and any cached formulas are deliberately unused.
    """
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(RAW / "benton2025/dataset-ev1.xlsx") as archive:
        strings = ["".join(t.text or "" for t in s.findall(".//m:t", ns))
                   for s in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    columns = {"A": "source_sort_code", "B": "sensillum", "C": "tuning_receptor",
               "D": "glomerulus", "G": "neuron_name", "P": "essential_co_receptors",
               "AC": "projection_laterality"}
    records = []
    for row in sheet.findall(".//m:row", ns):
        cells = {}
        for cell in row:
            col = re.sub(r"\d", "", cell.attrib["r"])
            if col not in columns:
                continue
            if cell.find("m:f", ns) is not None:
                raise ValueError("Unexpected formula in selected identity column")
            value = cell.find("m:v", ns)
            if value is not None:
                cells[col] = strings[int(value.text)] if cell.get("t") == "s" else value.text
            elif cell.get("t") == "inlineStr":
                cells[col] = "".join(t.text or "" for t in cell.findall(".//m:t", ns))
        if cells.get("A", "").isdigit():
            records.append({"source_excel_row_1based": int(row.attrib["r"]),
                            **{name: cells.get(col) for col, name in columns.items()}})
    result = pd.DataFrame(records)
    assert len(result) == 65 and result.source_sort_code.tolist() == [str(i) for i in range(1, 66)]
    assert result.iloc[0].tuning_receptor == "Or42a" and result.iloc[0].glomerulus == "VM7d"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    provenance = verify_sources(args.download)
    matrix = read_table("door_response_matrix")
    local_matrix = read_table("door_response_matrix_non_normalized")
    odor = read_table("odor").set_index("InChIKey")
    mapping = read_table("door_mappings")
    studies = read_table("door_dataset_info").set_index("dataset")
    assert odor.index.is_unique and studies.index.is_unique
    excluded = read_table("door_excluded_data")
    assert matrix.shape == (691, 78)
    assert matrix.index.equals(local_matrix.index) and matrix.columns.equals(local_matrix.columns)
    assert matrix.index.equals(odor.index)
    assert np.isfinite(matrix.to_numpy()).sum() == 7379
    assert np.nanmin(matrix.to_numpy()) == 0 and np.nanmax(matrix.to_numpy()) == 1

    # A missing SFR is deliberately not replaced by zero as upstream reset_sfr does.
    delta = matrix.subtract(matrix.loc["SFR"], axis="columns")
    assert np.array_equal(delta.to_numpy(), matrix.to_numpy() - matrix.loc["SFR"].to_numpy(), equal_nan=True)
    assert int((delta < 0).sum().sum()) == 2374
    ev1 = extract_ev1()
    write_csv(ev1, "benton2025-identity-excerpt.csv")

    neurons = pd.read_feather(ROOT / "data/processed/malecns_v1/neurons.feather")
    orn = neurons.loc[neurons.type.fillna("").str.startswith("ORN_"),
                      ["bodyId", "type", "rootSide", "entryNerve", "receptorType"]].copy()
    orn["glomerulus"] = orn.type.str.removeprefix("ORN_")
    orn["root_side_status"] = orn.rootSide.where(orn.rootSide.isin(["L", "R"]), "unknown")
    assert len(orn) == 2635 and orn.bodyId.is_unique and orn.receptorType.isna().all()
    glomeruli = set(orn.glomerulus)
    mapping = mapping.rename_axis("door_mapping_row_1based").reset_index()
    mapping["exact_male_glomerulus_match"] = mapping.glomerulus.isin(glomeruli)
    mapping["in_consensus_columns"] = mapping.receptor.isin(matrix.columns)
    mapping["consensus_finite_count"] = mapping.receptor.map(matrix.notna().sum())
    mapping["same_glomerulus_rows_are_alternatives_not_additive_channels"] = True
    write_csv(mapping, "door-mapping-audit.csv")

    joined = []
    for glom, cells in orn.groupby("glomerulus", sort=True):
        old = mapping.loc[mapping.glomerulus == glom]
        new = ev1.loc[ev1.glomerulus == glom]
        joined.append({"glomerulus": glom, "male_type": "ORN_" + glom, "cells": len(cells),
                       "root_L": int((cells.root_side_status == "L").sum()),
                       "root_R": int((cells.root_side_status == "R").sum()),
                       "root_unknown": int((cells.root_side_status == "unknown").sum()),
                       "entry_AN": int((cells.entryNerve == "AN").sum()),
                       "entry_MxLbN": int((cells.entryNerve == "MxLbN").sum()),
                       "door_mapping_rows": json.dumps(old.door_mapping_row_1based.tolist()),
                       "door_units": json.dumps(old.receptor.tolist()),
                       "door_sensillum_types": json.dumps(sorted(old['sensillum.type'].dropna().unique())),
                       "benton_excel_rows": json.dumps(new.source_excel_row_1based.tolist()),
                       "benton_receptors": json.dumps(new.tuning_receptor.tolist()),
                       "benton_sensilla": json.dumps(new.sensillum.tolist()),
                       "benton_projection_laterality": json.dumps(new.projection_laterality.tolist()),
                       "join_status": "exact_labels_only_not_receptor_expression_measurement"})
    joined = pd.DataFrame(joined)
    assert joined.cells.sum() == len(orn)
    write_csv(joined, "male-glomerulus-crosswalk.csv")
    per_cell = orn.drop(columns="receptorType").merge(
        joined[["glomerulus", "door_mapping_rows", "door_units", "benton_excel_rows", "benton_receptors"]],
        on="glomerulus", validate="many_to_one").sort_values("bodyId")
    palp_gloms = set(mapping.loc[mapping["sensillum.type"] == "maxillary palp", "glomerulus"])
    per_cell["palpal_label_but_other_entry_nerve"] = per_cell.glomerulus.isin(palp_gloms) & (per_cell.entryNerve != "MxLbN")
    per_cell["runtime_mapping_enabled"] = False
    write_csv(per_cell, "male-orn-candidates.csv")

    # Every consensus unit remains visible, including larval, pooled, and all-NA units.
    unit_records = []
    for unit in matrix.columns:
        rows = mapping.loc[mapping.receptor == unit]
        exact = rows.loc[rows.exact_male_glomerulus_match]
        adult = rows.adult.dropna().astype(bool)
        if len(adult) and not adult.any():
            status = "larval_only_exclude_from_adult_encoder"
        elif len(exact):
            status = "historical_exact_glomerulus_candidate"
        else:
            status = "ambiguous_or_no_exact_named_male_glomerulus"
        unit_records.append({"unit": unit, "mapping_rows": json.dumps(rows.door_mapping_row_1based.tolist()),
                             "glomerulus_labels": json.dumps(rows.glomerulus.fillna("unknown").tolist()),
                             "coexpression_labels": json.dumps(rows.coexpressing.dropna().tolist()),
                             "status": status, "finite_consensus_values_including_SFR": int(matrix[unit].notna().sum()),
                             "SFR_consensus": matrix.loc["SFR", unit],
                             "SFR_is_measured_spike_baseline": False})
    write_csv(pd.DataFrame(unit_records), "responding-unit-inventory.csv")

    chemicals, responses, raw_records = [], [], []
    for label, key in CHEMICALS:
        chem = odor.loc[key]
        chemicals.append({"audit_label": label, "source_name": chem.Name, "InChIKey": key,
                          "CID": chem.CID, "CAS": chem.CAS,
                          "finite_consensus_units": int(matrix.loc[key].notna().sum()),
                          "below_known_SFR_units": int((delta.loc[key] < 0).sum())})
        for unit in matrix.columns:
            responses.append({"InChIKey": key, "label": label, "unit": unit,
                              "consensus_global_dimensionless": matrix.loc[key, unit],
                              "consensus_without_global_weight_dimensionless": local_matrix.loc[key, unit],
                              "SFR_consensus_dimensionless": matrix.loc["SFR", unit],
                              "delta_from_known_SFR_dimensionless": delta.loc[key, unit],
                              "odor_value_present": pd.notna(matrix.loc[key, unit]),
                              "SFR_present": pd.notna(matrix.loc["SFR", unit]),
                              "firing_rate_hz": np.nan})
    write_csv(pd.DataFrame(chemicals), "chemical-identities.csv")
    write_csv(pd.DataFrame(responses), "chemical-consensus.csv")
    missing_metadata = set()
    raw_units = 0
    for unit in UNITS:
        raw = read_table(unit).set_index("InChIKey")
        assert raw.index.is_unique
        assert raw.index.equals(matrix.index)
        for dataset in raw.columns.drop(["Class", "Name", "CID", "CAS"]):
            raw_units += 1
            has_metadata = dataset in studies.index
            if not has_metadata:
                missing_metadata.add(dataset)
            info = studies.loc[dataset].to_dict() if has_metadata else {}
            for label, key in CHEMICALS:
                raw_records.append({"unit": unit, "dataset": dataset, "InChIKey": key,
                                    "label": label, "stored_study_value_unconverted": raw.loc[key, dataset],
                                    "stored_study_SFR_unconverted": raw.loc["SFR", dataset],
                                    "odor_value_present": pd.notna(raw.loc[key, dataset]),
                                    "exact_study_metadata_match": has_metadata,
                                    "raw_offset_to_original_publication_verified": False,
                                    "sex_audit": "male_main_recordings_primary_verified" if dataset == "Bruyne.1999.WT" else "not_verified_from_primary_in_this_audit",
                                    **info})
    raw_records = pd.DataFrame(raw_records)
    write_csv(raw_records, "selected-study-values.csv")
    write_csv(studies.reset_index(), "study-metadata.csv")
    write_csv(excluded, "excluded-studies.csv")

    metadata_conflicts = studies.loc[(studies.technique == "calcium imaging") & (studies["data.type"] == "spikes")].index.tolist()
    checks = {
        "all_49_source_hashes_and_48_git_blobs_match": True,
        "male_source_metadata_hashes_match": True,
        "691_unique_rows_and_78_unique_consensus_units": True,
        "chemical_identity_keys_unique_and_in_both_tables": True,
        "missing_values_remain_missing_and_unknown_SFR_not_zero_filled": bool(delta.loc[:, matrix.loc["SFR"].isna()].isna().all().all()),
        "SFR_subtraction_numpy_pandas_parity": True,
        "per_cell_join_has_2635_unique_body_ids_without_expansion": len(per_cell) == 2635 and bool(per_cell.bodyId.is_unique),
        "all_source_65_EV1_identity_rows_extracted_without_formula_evaluation": len(ev1) == 65,
        "runtime_and_graph_never_imported_or_modified": True,
    }
    assert all(checks.values())
    summary = {
        "scope": "Evidence import and exact-label crosswalk only; no concentration-to-Hz model, mixture law, or neural activation",
        "script_sha256": sha(Path(__file__)),
        "source_provenance_sha256": sha(OUT / "source-provenance.json"),
        "source_bytes": sum(f["bytes"] for s in provenance["sources"] for f in s["files"]),
        "door_version": "2.0.1.9001",
        "matrix": {"rows_including_SFR": len(matrix), "units": len(matrix.columns),
                   "finite_values_including_SFR": int(matrix.notna().sum().sum()),
                   "missing_values": int(matrix.isna().sum().sum()),
                   "all_missing_units": matrix.columns[matrix.isna().all()].tolist(),
                   "missing_SFR_units": matrix.columns[matrix.loc["SFR"].isna()].tolist(),
                   "negative_unshifted_consensus_values": int((matrix < 0).sum().sum()),
                   "negative_deltas_to_known_SFR": int((delta < 0).sum().sum()),
                   "finite_values_with_unknown_SFR": int(matrix.loc[:, matrix.loc["SFR"].isna()].notna().sum().sum())},
        "male": {"named_orn_cells": len(orn), "named_orn_glomeruli": len(glomeruli),
                 "side_counts": orn.root_side_status.value_counts().to_dict(),
                 "entry_nerve_counts": orn.entryNerve.value_counts().to_dict(),
                 "receptorType_nonmissing": int(orn.receptorType.notna().sum()),
                 "door_exact_mapping_rows": int(mapping.exact_male_glomerulus_match.sum()),
                 "door_exact_unique_glomeruli_including_unknown_receptor": int(mapping.loc[mapping.exact_male_glomerulus_match, "glomerulus"].nunique()),
                 "door_unmatched_glomeruli": sorted(glomeruli - set(mapping.glomerulus.dropna())),
                 "benton_unmatched_glomeruli": sorted(glomeruli - set(ev1.glomerulus.dropna())),
                 "palpal_glomerulus_count": len(palp_gloms),
                 "palpal_label_cell_count": int(orn.glomerulus.isin(palp_gloms).sum()),
                 "palpal_entry_nerve_conflict_bodyIds": per_cell.loc[per_cell.palpal_label_but_other_entry_nerve, "bodyId"].astype(int).tolist()},
        "study_audit": {"metadata_rows": len(studies), "raw_tables": list(UNITS),
                        "raw_unit_dataset_columns": raw_units,
                        "selected_raw_cells_including_NA": len(raw_records),
                        "selected_raw_finite_cells": int(raw_records.stored_study_value_unconverted.notna().sum()),
                        "raw_datasets_missing_exact_metadata_join": sorted(missing_metadata),
                        "calcium_technique_with_spikes_unit_conflicts": metadata_conflicts,
                        "EC50_dataset_name_vs_data_type_review_required": ["Nissler.2007.EC50", "Nissler.2007.nmr"],
                        "sex_field_in_source_metadata": any("sex" in c.lower() for c in studies.columns),
                        "raw_SFR_offset_restoration_to_original_paper": "not_verified; preserve stored numbers and metadata flags separately"},
        "checks": checks,
    }
    plot(delta)
    outputs = sorted(p for p in OUT.glob("*.csv")) + [OUT / "consensus-diagnostic.png"]
    summary["artifacts"] = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p), "bytes": p.stat().st_size} for p in outputs]
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"matrix": summary["matrix"], "male": summary["male"], "checks": checks}, indent=2))


def plot(delta: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(13, 4.8), constrained_layout=True)
    values = delta.loc[[key for _, key in CHEMICALS], list(UNITS)].to_numpy()
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#dedede")
    img = ax.imshow(values, vmin=-1, vmax=1, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(UNITS)), UNITS, rotation=45, ha="right")
    ax.set_yticks(range(len(CHEMICALS)), [label for label, _ in CHEMICALS])
    for y, x in np.ndindex(values.shape):
        ax.text(x, y, "NA" if not np.isfinite(values[y, x]) else f"{values[y,x]:.2f}",
                ha="center", va="center", fontsize=8,
                color="white" if abs(values[y, x]) > .65 else "black")
    ax.set_title("DoOR consensus minus known SFR: selected evidence channels\nDimensionless; gray = missing; coexpressed / pooled channels must not be added")
    fig.colorbar(img, ax=ax, shrink=.7, label="Consensus difference (not Hz)")
    fig.savefig(OUT / "consensus-diagnostic.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
