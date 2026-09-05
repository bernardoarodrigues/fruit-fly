"""Extract a sex-labelled optical template; make no MaleCNS registration.

Reads the coherent author RData objects using rdata, without running R code.
Install rdata==1.1.0 and xarray==2026.7.0 in an optional separate directory and
pass --rdata-path if these readers are not in the active environment.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "99d2a43123db636cedb55af9ff31a59657e7d17e"
SOURCE_PATHS = ("data/eyemap.RData", "data/microCT/20240701.RData", "data/med_ixy.RData")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rdata-path", type=Path)
    parser.add_argument("--raw-dir", type=Path, default=ROOT/"data/raw/visual-retinotopy/zhao2025")
    parser.add_argument("--output-dir", type=Path, default=ROOT/"validation/visual-retinotopy")
    args = parser.parse_args()
    if args.rdata_path:
        sys.path.insert(0, str(args.rdata_path))
    import rdata
    from importlib.metadata import version

    receipts = []
    for source_path in SOURCE_PATHS:
        destination = args.raw_dir/source_path
        url = f"https://raw.githubusercontent.com/reiserlab/eyemap_T4/{COMMIT}/{source_path}"
        if not destination.exists():
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read(500_001)
            if len(content) > 500_000:
                raise ValueError("Source exceeds declared small-file limit")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        receipts.append({"path": source_path, "url": url, "bytes": destination.stat().st_size,
                         "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        eye = rdata.read_rda(args.raw_dir/SOURCE_PATHS[0])
        scan = rdata.read_rda(args.raw_dir/SOURCE_PATHS[1])
        med_grid = np.asarray(rdata.read_rda(args.raw_dir/SOURCE_PATHS[2])["med_ixy"])
    # R classes solve_LSAP and prcomp have no Python constructor; rdata exposes
    # their underlying array/list. We read the saved assignment and directions,
    # never evaluate those source functions or run serialized executable code.
    lens_grid = np.asarray(eye["lens_ixy"])
    pairing = np.asarray(eye["eyemap"])
    cone_to_lens = np.asarray(scan["i_match"])
    is_left = np.asarray(scan["ind_left_lens"])
    for values in (lens_grid, pairing, med_grid, cone_to_lens):
        if not np.isfinite(values).all() or not np.equal(values, np.rint(values)).all():
            raise ValueError("Expected finite integer-valued source indices/grid")
    lens_grid, pairing, med_grid = (x.astype(np.int64) for x in (lens_grid, pairing, med_grid))
    cone_to_lens = cone_to_lens.astype(np.int64)
    if is_left.dtype.kind != "b":
        raise ValueError("Expected a saved logical left-eye mask")
    if not np.array_equal(np.sort(cone_to_lens), np.arange(1, len(cone_to_lens)+1)):
        raise ValueError("Saved cone-to-lens assignment must be a one-based permutation")
    directions = np.asarray(scan["ucl_rot_sm"])[np.argsort(cone_to_lens)][~is_left]
    if not np.array_equal(np.sort(lens_grid[:, 0]), np.arange(1, len(directions)+1)):
        raise ValueError("Embedded right lens grid does not cover this coherent scan")
    if np.max(abs(np.linalg.norm(directions, axis=1)-1)) > 1e-12:
        raise ValueError("Saved optical directions are not unit vectors")
    if not np.array_equal(directions[pairing[:, 1]-1], np.asarray(eye["ucl_rot_sm"])):
        raise ValueError("Saved microCT and embedded EM-map directions disagree")
    med_by_index = {int(row[0]): tuple(row[1:]) for row in med_grid}
    lens_by_index = {int(row[0]): tuple(row[1:]) for row in lens_grid}
    if any(med_by_index[m] != lens_by_index[l] for m, l in pairing):
        raise ValueError("Saved EM/lens pairing does not preserve the published p/q grid")
    med_by_lens = {int(lens): int(med) for med, lens in pairing}
    upper = set(pairing[np.asarray(eye["ind_Up_ucl"]).astype(int)-1, 1].tolist())
    lower = set(pairing[np.asarray(eye["ind_Down_ucl"]).astype(int)-1, 1].tolist())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir/"zhao-female-right-eye-directions.csv"
    with output.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample", "sex", "eye", "right_lens_index_1based", "p", "q",
                         "unit_x_forward", "unit_y_left", "unit_z_dorsal",
                         "azimuth_deg_positive_left", "elevation_deg",
                         "fafb_mi1_array_index_1based", "upper_equator_marker", "lower_equator_marker"])
        for index, p, q in sorted(lens_grid.tolist()):
            x, y, z = directions[index-1]
            writer.writerow(["20240701", "female", "R", index, p, q, x, y, z,
                             np.degrees(np.arctan2(y, x)), np.degrees(np.arcsin(np.clip(z, -1, 1))),
                             med_by_lens.get(index, ""), index in upper, index in lower])
    result = {
        "source": "Zhao et al.2025, Eye structure shapes neuron function in Drosophila motion vision",
        "doi": "10.1038/s41586-025-09276-5", "repository_commit": COMMIT,
        "sources": receipts, "reader_versions": {name: version(name) for name in ("rdata", "xarray")},
        "reader_warnings": sorted({str(w.message) for w in caught}),
        "coordinate_convention": "Author canonical Cartesian: x forward, y left, z dorsal. azimuth=atan2(y,x), elevation=asin(z), degrees. Do not import y-reflected inside-out plotting coordinates.",
        "meaning": "Author smoothed lens-minus-photoreceptor-tip geometric optical-axis estimates from female microCT; not measured electrophysiological receptive fields or male facet identities.",
        "scope": "Right-eye female template extraction only; no chosen MaleCNS grid transform or runtime input.",
        "right_eye_lenses": len(directions), "left_eye_lenses_present_in_scan": int(is_left.sum()),
        "matched_fafb_mi1_rows": len(pairing), "unmatched_fafb_mi1_rows": len(med_grid)-len(pairing),
        "unmatched_right_eye_lenses": len(directions)-len(pairing),
        "coherent_directions_exactly_equal": True, "all_matched_pq_exactly_equal": True,
        "direction_norm_max_error": float(np.max(abs(np.linalg.norm(directions, axis=1)-1))),
        "equator": {"upper_marker_count": len(upper), "upper_p_plus_q": sorted({int(sum(lens_by_index[i])) for i in upper}),
                    "lower_marker_count": len(lower), "lower_p_plus_q": sorted({int(sum(lens_by_index[i])) for i in lower})},
        "no_identity_crosswalk": "FAFB Mi1 identifiers in eyemap are R array row indices, not MaleCNS bodyIds. No identity join is inferred.",
        "excluded_objects": ["utp_lens_rot: sphere-projected lens positions, not optical directions",
                             "*_aux: includes39 generated boundary-support points",
                             "standalone lens_ixy.RData: older786-row grid, incompatible with embedded852-row grid"],
        "output": {"name": output.name, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "completed": True,
    }
    (args.output_dir/"zhao-extraction.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"output": str(output), "right_eye_lenses": len(directions), "matched_fafb_rows": len(pairing)}))


if __name__ == "__main__":
    main()
