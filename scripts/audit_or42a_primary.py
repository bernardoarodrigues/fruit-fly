#!/usr/bin/env python3
"""Read-only, frozen single-paper olfactory offset audit; never runs a network."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/or42a-primary"
EA = "XEKOWRVHYACXOJ-UHFFFAOYSA-N"
IA = "MLFHJEHSLIIPHL-UHFFFAOYSA-N"
DATASET = "Bruyne.1999.WT"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = OUT / "source-provenance.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["files"]:
        path = ROOT / item["path"]
        if path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError(f"Frozen source changed: {path}")
    source = pd.read_csv(ROOT / "data/raw/door/data/Or42a.csv", sep=";", index_col=0)
    historical = pd.read_csv(ROOT / "data/raw/or42a-primary/Or42a-1999-reintroduction.csv", sep=";", index_col=0)
    current = source.loc[source[DATASET].notna(), ["Name", "InChIKey", "CID", "CAS", DATASET]].copy()
    old = historical.loc[historical[DATASET].notna(), ["InChIKey", DATASET]].copy()
    assert not current.InChIKey.duplicated().any() and not old.InChIKey.duplicated().any()
    comparison = current.merge(old, on="InChIKey", suffixes=("_current", "_historical"), validate="one_to_one")
    assert len(comparison) == len(current) == len(old) == 18
    assert np.array_equal(comparison[f"{DATASET}_current"], comparison[f"{DATASET}_historical"])
    baseline = float(current.set_index("InChIKey").loc["SFR", DATASET])
    assert baseline == 11
    current = current.rename(columns={DATASET: "door_stored_value"})
    current["candidate_delta_if_baseline_restored"] = current.door_stored_value - baseline
    current["offset_status"] = "consistent_with_restoration_but_exact_original_offset_unverified"
    current.to_csv(OUT / "door-study-comparison.csv", index=False, lineterminator="\n")

    m = manifest["manual_figure5_measurement"]
    pixels = np.array(Image.open(ROOT / "data/raw/or42a-primary/figure5.jpg").convert("L"))
    assert list(pixels.shape[::-1]) == m["image_wh"]
    ticks = np.array(m["axis_tick_x"], dtype=float)
    rates = np.array(m["axis_tick_rates_hz"], dtype=float)
    slope, intercept = np.polyfit(ticks, rates, 1)
    bound = m["point_reading_bound_pixels"]
    extracted = []
    for prefix, key in [("ethyl_acetate", EA), ("isoamyl_acetate", IA)]:
        mean_x = m[f"{prefix}_mean_bar_x"]
        cap_x = m[f"{prefix}_sd_cap_x"]
        lo, hi = m[f"{prefix}_bar_y_interval"]
        edge_counts = (pixels[lo:hi, mean_x - 1:mean_x + 2] < 80).sum(axis=0)
        assert edge_counts.max() >= (hi - lo) * .9
        perturbations = []
        for signs in itertools.product([-1, 1], repeat=6):
            a, b = np.polyfit(ticks + np.array(signs[:5]) * bound, rates, 1)
            perturbations.append(a * (mean_x + signs[5] * bound) + b)
        mean = float(slope * mean_x + intercept)
        extracted.append(dict(
            odor=prefix.replace("_", " "), InChIKey=key,
            figure="de Bruyne 1999 Fig.5", n=13, response_measure="500ms rate minus 500ms prestimulus rate",
            delta_mean_hz=mean, delta_sd_hz=float(slope * (cap_x - mean_x)),
            endpoint_sensitivity_min_hz=min(perturbations), endpoint_sensitivity_max_hz=max(perturbations),
            uncertainty_type="manual raster reading sensitivity, not biological CI",
            source_exact_text_mean_hz=138.0 if key == EA else None,
            source_exact_text_sd_hz=32.0 if key == EA else None,
        ))
    assert abs(extracted[0]["delta_mean_hz"] - 138) < 1
    assert abs(extracted[0]["delta_sd_hz"] - 32) < 1
    pd.DataFrame(extracted).to_csv(OUT / "figure5-estimates.csv", index=False, na_rep="NA", lineterminator="\n")
    neurons = pd.read_feather(ROOT / "data/processed/malecns_v1/neurons.feather")
    selected = neurons.loc[neurons.type.eq("ORN_VM7d"), ["bodyId", "type", "rootSide", "entryNerve"]].sort_values("bodyId")
    assert len(selected) == selected.bodyId.nunique() == 36
    assert selected.rootSide.value_counts().to_dict() == {"L": 18, "R": 18}
    assert selected.entryNerve.eq("MxLbN").all()
    selected.to_csv(OUT / "male-vm7d-population.csv", index=False, lineterminator="\n")
    metadata = pd.read_csv(ROOT / "data/raw/door/data/door_dataset_info.csv", sep=";", index_col=0)
    row = metadata.loc[metadata.dataset.eq(DATASET)].iloc[0]
    table = current.set_index("InChIKey")
    contrasts = []
    for estimate in extracted:
        key = estimate["InChIKey"]
        reference = 138 if key == EA else estimate["delta_mean_hz"]
        stored = float(table.loc[key, "door_stored_value"])
        contrasts.append(dict(InChIKey=key, door_stored=stored,
                              primary_delta_reference_hz=reference,
                              stored_minus_primary_delta=stored-reference,
                              stored_minus_sfr_minus_primary_delta=stored-baseline-reference))
    output = dict(
        schema_version=1, source_manifest_sha256=sha(manifest_path), script_sha256=sha(Path(__file__)),
        source_files_verified=len(manifest["files"]), historical_value_count_unchanged=18,
        source_metadata={str(k): None if pd.isna(v) else v for k, v in row.items()},
        primary_baseline=dict(unit="pb1A", figure=6, mean_hz=11, sd_hz=1, n=17,
                              extraction="verbatim numeric figure label, visually inspected; caption identifies SD"),
        primary_response=dict(unit="pb1A", figure=5, odor="ethyl acetate", delta_mean_hz=138, delta_sd_hz=32, n=13,
                              extraction="explicit numbers in Results text, corroborated against figure"),
        digitization=dict(slope_hz_per_pixel=float(slope), intercept_hz=float(intercept),
                          maximum_tick_residual_hz=float(np.max(np.abs(slope*ticks+intercept-rates))), estimates=extracted),
        offset_comparison=contrasts,
        exact_offset_restoration_verified=False,
        exact_pre_import_original_trials_available=False,
        suggested_primary_summary_boundary=dict(status="PROPOSAL_ONLY_NOT_EXECUTED",
            baseline_hz=11, ethyl_acetate_total_rate_hz=149,
            isoamyl_acetate_total_rate_hz=11+extracted[1]["delta_mean_hz"],
            caveat="Combines Fig.6 baseline (n17) with Fig.5 delta (n13); not a reported matched-cohort total rate. Isoamyl value is raster-estimated. DoOR totals are not substituted.",
            exact_MaleCNS_cells=36, side_counts={"L":18,"R":18}, input_organ="maxillary palp",
            neural_run_performed=False, concentration_encoder_calibrated=False),
        checks=dict(source_hashes=True, historical_current_equality=True, bar_edge_evidence=True,
                    digitized_EA_agrees_with_explicit_text=True, exact_male_population=True,
                    original_offset_reconciled=False),
        output_sha256={name:sha(OUT/name) for name in ["door-study-comparison.csv", "figure5-estimates.csv", "male-vm7d-population.csv"]},
    )
    (OUT / "results.json").write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"source_checks":"PASS", "exact_original_offset":"UNRESOLVED", "heldout_odor_delta":extracted[1], "male_cells":len(selected)}, indent=2))


if __name__ == "__main__":
    main()
