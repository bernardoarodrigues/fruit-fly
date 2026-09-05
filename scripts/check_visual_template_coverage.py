"""Female optical template versus implemented right-camera support, without fitting.

No MaleCNS angular registration or neural input. The declared surrogate assumes
the author x-forward/y-left/z-dorsal basis aligns with the body's head basis.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/"scripts"))
from calibrate_retina_rays import ray_grid, lookup
from flygym.vision.retina import Retina


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project(directions, height, width, focal):
    z = -directions[:, 2]
    col = np.full(len(z), np.nan)
    row = np.full(len(z), np.nan)
    forward = z > 0
    col[forward] = width/2 + focal*directions[forward, 0]/z[forward]
    row[forward] = height/2 - focal*directions[forward, 1]/z[forward]
    inside = forward & (col >= 0) & (col < width) & (row >= 0) & (row < height)
    index = np.full(len(z), -1, dtype=np.int64)
    index[inside] = np.floor(row[inside]).astype(int)*width + np.floor(col[inside]).astype(int)
    return inside, index, row, col


def cap_support(axis, radius_deg, radial, angular, used, height, width, focal):
    """Equal-solid-angle midpoint quadrature over a diagnostic spherical cap.

    Fractions refer to source-pixel cells, not a biological acceptance kernel.
    Projection determines raw aperture, then the saved lookup determines which
    raw pixel cells actually contribute to any facet.
    """
    helper = np.array([0., 0., 1.]) if abs(axis[2]) < .9 else np.array([1., 0., 0.])
    tangent = np.cross(axis, helper)
    tangent /= np.linalg.norm(tangent)
    second = np.cross(axis, tangent)
    cosine = 1-(np.arange(radial)+.5)/radial*(1-np.cos(np.deg2rad(radius_deg)))
    phi = 2*np.pi*(np.arange(angular)+.5)/angular
    around = np.cos(phi)[:, None]*tangent + np.sin(phi)[:, None]*second
    directions = cosine[:, None, None]*axis + np.sqrt(1-cosine**2)[:, None, None]*around
    inside, index, _, _ = project(directions.reshape(-1, 3), height, width, focal)
    sampled = np.zeros(len(index), dtype=bool)
    sampled[inside] = used[index[inside]]
    return np.array([inside.mean(), sampled.mean()])


def angle_from_distance(distance):
    return np.degrees(2*np.arcsin(np.clip(distance/2, 0, 1)))


def summary(values):
    values = np.asarray(values)
    return {**dict(zip(("min", "median", "p95", "max"), np.quantile(values, [0, .5, .95, 1]).tolist())),
            "mean": float(values.mean())}


def main():
    template_path = ROOT/"validation/visual-retinotopy/zhao-female-right-eye-directions.csv"
    extraction_path = ROOT/"validation/visual-retinotopy/zhao-extraction.json"
    camera_result_path = ROOT/"validation/retina-rays/results.json"
    footprints_path = ROOT/"validation/retina-rays/ray-footprints.npz"
    extraction = json.loads(extraction_path.read_text())
    calibration = json.loads(camera_result_path.read_text())
    if sha(template_path) != extraction["output"]["sha256"] or sha(footprints_path) != calibration["footprints_sha256"]:
        raise ValueError("Template or camera footprint hash does not match its receipt")
    if not all(calibration["checks"].values()):
        raise ValueError("Camera calibration did not pass")
    table = pd.read_csv(template_path)
    if len(table) != 852 or not table.sex.eq("female").all() or not table.eye.eq("R").all():
        raise ValueError("Expected coherent 852-row female right-eye template")
    head = table[["unit_x_forward", "unit_y_left", "unit_z_dorsal"]].to_numpy()
    camera = next(c for c in calibration["cameras_at_initial_pose"] if c["side"] == "R")
    rotation = np.asarray(camera["rotation_camera_to_head_forward_left_up"])
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12) or not np.isclose(np.linalg.det(rotation), 1):
        raise ValueError("Invalid calibrated camera-to-head rotation")
    rays_template = head @ rotation
    height, width, _ = calibration["raw_image_shape"]
    focal = .5*height/np.tan(np.deg2rad(camera["fovy_deg"])/2)
    raw_rays = ray_grid(height, width, camera["fovy_deg"]).reshape(-1, 3)
    with np.load(footprints_path, allow_pickle=False) as arrays:
        source = arrays["destination_to_source_pixel"].copy()
        facet_ids = arrays["facet_id_map"].copy()
        means = arrays["facet_mean_camera_ray"].copy()
    retina = Retina()
    if not np.array_equal(lookup(retina), source) or not np.array_equal(retina.ommatidia_id_map, facet_ids):
        raise ValueError("Installed retina differs from the calibrated lookup or facet mask")
    mask = facet_ids > 0
    destinations_per_facet = np.bincount(facet_ids[mask], minlength=722)[1:]
    valid = mask & (source >= 0)
    # Every repeated source occurrence retains its original destination-pixel
    # weight. Invalid mappings stay in the facet denominator as black padding.
    transfer = sparse.coo_matrix((1/destinations_per_facet[facet_ids[valid]-1],
                                 (facet_ids[valid]-1, source[valid])), shape=(721, height*width)).tocsr()
    used = np.asarray(transfer.sum(axis=0)).ravel() > 0
    inside, projected_pixel, row, col = project(rays_template, height, width, focal)
    sampled = np.zeros(len(table), dtype=bool)
    sampled[inside] = used[projected_pixel[inside]]
    nearest_distance, nearest_facet = cKDTree(means).query(rays_template)
    nearest_angle = angle_from_distance(nearest_distance)
    used_distance, _ = cKDTree(raw_rays[used]).query(rays_template)
    raw_tree = cKDTree(raw_rays)
    output = table.copy()
    output["inside_raw_camera_frustum"] = inside
    output["projected_raw_pixel_zero_based_or_minus1"] = projected_pixel
    output["projected_raw_row"] = row
    output["projected_raw_column"] = col
    output["point_direction_pixel_sampled_by_any_facet"] = sampled
    output["nearest_facet_index_zero_based"] = nearest_facet
    output["nearest_facet_mean_angular_error_deg"] = nearest_angle
    output["nearest_sampled_raw_pixel_center_error_deg"] = angle_from_distance(used_distance)
    radii = (1., 2., 4.)
    aperture_results = {}
    upstream_checks = []
    outdir = ROOT/"validation/visual-template-coverage"
    weights_dir = ROOT/"data/derived/visual-template-coverage"
    outdir.mkdir(parents=True, exist_ok=True)
    weights_dir.mkdir(parents=True, exist_ok=True)
    for radius in radii:
        name = f"cap{radius:g}deg"
        coarse = np.array([cap_support(axis, radius, 32, 128, used, height, width, focal) for axis in rays_template])
        fine = np.array([cap_support(axis, radius, 64, 256, used, height, width, focal) for axis in rays_template])
        error = abs(fine-coarse)
        matches = raw_tree.query_ball_point(rays_template, 2*np.sin(np.deg2rad(radius)/2))
        responses = np.vstack([np.asarray(transfer[:, pixels].sum(axis=1)).ravel() for pixels in matches])
        if radius == 2.:
            for source_index in (1, 200, 395, 600, 852):
                raw_mask = np.zeros(height*width, dtype=np.uint8)
                raw_mask[matches[source_index-1]] = 255
                rgb = np.repeat(raw_mask.reshape(height, width, 1), 3, axis=2)
                observed = retina.raw_image_to_hex_pxls(retina.correct_fisheye(rgb)).sum(axis=1)
                error_upstream = float(np.max(abs(observed-responses[source_index-1])))
                upstream_checks.append({"right_lens_index_1based": source_index,
                                        "radius_deg": radius, "max_facet_error": error_upstream})
                if error_upstream > 1e-12:
                    raise AssertionError("Sparse facet response differs from the actual upstream retina")
        mass = responses.sum(axis=1)
        normalized = np.divide(responses, mass[:, None], out=np.zeros_like(responses), where=mass[:, None] > 0)
        if not np.allclose(normalized.sum(axis=1), mass > 0, atol=1e-12):
            raise AssertionError("Diagnostic normalized rows must sum to one or remain exactly zero")
        if np.any(fine[:, 1] > fine[:, 0]) or np.any(fine < 0) or np.any(fine > 1):
            raise AssertionError("Support fraction must be bounded by the raw aperture")
        output[f"{name}_raw_frustum_solid_angle_fraction"] = fine[:, 0]
        output[f"{name}_sampled_pixel_cell_solid_angle_fraction"] = fine[:, 1]
        output[f"{name}_outside_frustum_loss_fraction"] = 1-fine[:, 0]
        output[f"{name}_inside_frustum_unsampled_loss_fraction"] = fine[:, 0]-fine[:, 1]
        output[f"{name}_total_geometric_support_loss_fraction"] = 1-fine[:, 1]
        output[f"{name}_unnormalized_sum_of_facet_responses"] = mass
        output[f"{name}_nonzero_facet_response_count"] = (responses > 0).sum(axis=1)
        output[f"{name}_unit_sum_weights_exist"] = mass > 0
        output[f"{name}_quadrature_max_absolute_change"] = error.max(axis=1)
        matrix_path = weights_dir/f"{name}-unit-sum-facet-response-weights.npz"
        sparse.save_npz(matrix_path, sparse.csr_matrix(normalized))
        aperture_results[name] = {
            "diagnostic_radius_deg": radius, "any_actual_facet_response_count": int((mass > 0).sum()),
            "zero_actual_facet_response_count": int((mass == 0).sum()),
            "zero_response_despite_axis_inside_frustum": int(((mass == 0) & inside).sum()),
            "raw_frustum_mass_fraction": summary(fine[:, 0]),
            "sampled_pixel_cell_mass_fraction": summary(fine[:, 1]),
            "geometric_support_loss_fraction": summary(1-fine[:, 1]),
            "less_than_half_cap_mass_sampled_count": int((fine[:, 1] < .5).sum()),
            "quadrature_max_absolute_change": float(error.max()),
            "quadrature_p95_absolute_change": float(np.quantile(error, .95)),
            "weights": {"path": str(matrix_path.relative_to(ROOT)), "sha256": sha(matrix_path),
                        "shape": list(normalized.shape), "nnz": int(np.count_nonzero(normalized)),
                        "row_order": "CSV order; right_lens_index_1based1..852", "column_order": "zero-based camera facet0..720",
                        "meaning": "Engineering diagnostic only: pixel-center top-hat facet responses divided by their row sum; a missing row stays zero. This normalization does not restore lost cap support."},
        }
    csv_path = outdir/"female-right-template-coverage.csv"
    output.to_csv(csv_path, index=False)
    result = {
        "scope": __doc__, "completed": True, "neural_input_installed": False, "male_cell_registration": None,
        "source_sex": "female", "source_sample": "20240701", "eye": "R",
        "body_surrogate": "Female-derived body geometry plus female optical template from another specimen; canonical head axes identified without fitted rotation/translation. Not a biological co-registration.",
        "camera_to_head_rotation": rotation.tolist(), "raw_camera_fovy_deg": camera["fovy_deg"],
        "raw_image_shape": [height, width, 3], "template_axes": len(table), "camera_facets": len(means),
        "point_axis_coverage": {"inside_raw_frustum": int(inside.sum()), "outside_raw_frustum": int((~inside).sum()),
            "inside_frustum_and_sampled_source_pixel": int(sampled.sum()),
            "inside_frustum_but_unsampled_source_pixel": int((inside & ~sampled).sum()),
            "distinct_sampled_raw_pixels": int(used.sum()), "total_raw_pixels": height*width},
        "nearest_facet_mean_error_deg": {"all": summary(nearest_angle), "inside_raw_frustum": summary(nearest_angle[inside]),
            "outside_raw_frustum": summary(nearest_angle[~inside])},
        "diagnostic_cap_protocol": {"radii_deg": radii, "kernel": "uniform spherical caps; analyst numerical probes, not biological acceptance angles",
            "solid_angle_support": "Equal-area cap quadrature; samples projected to raw source-pixel cells, then lookup membership. Includes missing frustum and unsampled pixels separately.",
            "coarse_grid": [32, 128], "fine_grid": [64, 256], "normalization": "Rows of actual pixel-center facet response normalized only when nonzero; preserve geometric loss metrics separately.",
            "rendering": "No additional renderer run. Uses existing14-target camera calibration and exact stored lookup; this audit only projects the released template through it."},
        "apertures": aperture_results,
        "synthetic_cap_image_upstream_parity": upstream_checks,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/"scripts/calibrate_retina_rays.py", template_path, extraction_path, camera_result_path, footprints_path)},
        "csv_sha256": sha(csv_path),
        "limits": ["Template canonical axes are a declared surrogate-to-body alignment, not measured common specimen landmarks.",
            "This is far-field angular coverage; individual lens origins and near-field parallax are not modelled.",
            "Point support is sensitive to gaps in a deterministic sparse pixel sampler; finite caps are reported separately.",
            "Geometric pixel-cell quadrature and actual pixel-center response are different discretizations; neither is a measured photoreceptor transfer.",
            "Unit-sum response weights discard their absolute response scale; use retained support/loss and original response mass when interpreting them.",
            "Nearest-facet errors describe sampling mismatch only, not a chosen neuronal registration.",
            "No additional rendering, optical-parameter fit, retina change, male column assignment, or neural simulation was performed."],
    }
    (outdir/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    # Plot canonical right-eye azimuth with posterior wrap kept contiguous.
    az = table.azimuth_deg_positive_left.to_numpy()
    az = np.where(az > 90, az-360, az)
    elevation = table.elevation_deg.to_numpy()
    facet_head = means @ rotation.T
    facet_az = np.degrees(np.arctan2(facet_head[:, 1], facet_head[:, 0]))
    facet_az = np.where(facet_az > 90, facet_az-360, facet_az)
    facet_el = np.degrees(np.arcsin(np.clip(facet_head[:, 2], -1, 1)))
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), layout="constrained")
    ax = axes[0, 0]
    ax.scatter(facet_az, facet_el, s=3, color="0.78", label="721 camera facet means")
    for mask, color, label in ((sampled, "#1b806d", "Axis source pixel sampled"),
                               (inside & ~sampled, "#d99b2b", "In frustum; source pixel not sampled"),
                               (~inside, "#b84747", "Outside raw camera frustum")):
        ax.scatter(az[mask], elevation[mask], s=11, color=color, label=f"{label} ({mask.sum()})")
    ax.legend(fontsize=8, loc="lower left")
    ax.set(title="Point-axis coverage under declared head-frame alignment", xlabel="Head azimuth (°, positive left)", ylabel="Elevation (°)")
    ax = axes[0, 1]
    dots = ax.scatter(az, elevation, c=nearest_angle, s=13, cmap="magma_r", vmin=0, vmax=32)
    fig.colorbar(dots, ax=ax, label="Nearest facet-mean angular error (°)")
    ax.set(title="Sampling mismatch; no registration inferred", xlabel="Head azimuth (°, positive left)", ylabel="Elevation (°)")
    ax = axes[1, 0]
    for radius, color in zip(radii, ("#416b99", "#ae5c39", "#725394")):
        name = f"cap{radius:g}deg"
        for kind, style in (("raw_frustum", "--"), ("sampled_pixel_cell", "-")):
            x = np.sort(output[f"{name}_{kind}_solid_angle_fraction"].to_numpy())
            ax.plot(x, np.arange(1, len(x)+1)/len(x), color=color, ls=style,
                    label=f"{radius:g}° {'raw aperture' if style=='--' else 'sampled support'}")
    ax.set(title="Finite angular probes preserve support loss", xlabel="Fraction of probe solid angle retained", ylabel="Fraction of 852 template axes", xlim=(-.02, 1.02))
    ax.legend(fontsize=8)
    ax = axes[1, 1]
    labels = ["Raw\nfrustum", "Point pixel\nsampled"]+[f"{r:g}° cap\nnonzero output" for r in radii]
    counts = [inside.sum(), sampled.sum()]+[aperture_results[f"cap{r:g}deg"]["any_actual_facet_response_count"] for r in radii]
    bars = ax.bar(labels, counts, color=["#7295b6", "#1b806d", "#416b99", "#ae5c39", "#725394"])
    ax.bar_label(bars)
    ax.axhline(852, color="0.3", ls=":", label="852 source axes")
    ax.set(ylim=(0, 910), ylabel="Template axes", title="Nonzero output does not mean complete angular support")
    ax.legend(fontsize=8)
    fig.suptitle("Female micro-CT optical template versus existing right-eye camera\nGeometric body surrogate only; no male cell assignment or neural input", fontsize=14)
    fig.savefig(outdir/"coverage.png", dpi=160)
    plt.close(fig)
    print(json.dumps({"point_axis_coverage": result["point_axis_coverage"],
        "nearest_facet_mean_error_deg": result["nearest_facet_mean_error_deg"],
        "apertures": {k: {x: v[x] for x in ("any_actual_facet_response_count", "less_than_half_cap_mass_sampled_count", "quadrature_max_absolute_change")} for k,v in aperture_results.items()}}, indent=2))


if __name__ == "__main__":
    main()
