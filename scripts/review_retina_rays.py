"""Independently review the saved artificial-retina geometry calibration.

Read root calibration artifacts without modifying them. Reconstruct the local
FlyGym sampling formula, reduce facets separately, query a fresh BodyRuntime,
and test peripheral rendered spheres using world-space quadratic intersections.
This does not register biological facets or validate phototransduction.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flygym import assets_dir
from flygym.vision.retina import Retina
from fruitfly.body import BodyConfig, BodyRuntime


SEED = 419
PERIPHERAL_TARGETS_DEG = [(74, 0), (-74, 0), (0, 73), (0, -73), (60, 40), (-60, -40)]
TOLERANCES = {
    "source_index_mismatches": 0,
    "facet_mean_ray_max_absolute_error": 1e-12,
    "facet_support_radius_max_absolute_error_deg": 1e-9,
    "facet_valid_fraction_max_absolute_error": 1e-12,
    "facet_readout_max_absolute_error": 1e-12,
    "fresh_camera_pose_max_absolute_error": 1e-12,
    "rotation_orthogonality_max_absolute_error": 1e-12,
    "peripheral_raw_jaccard_min": .97,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def upstream_source_indices(retina):
    """Separate translation of installed nearest-pixel fisheye equations.

    Upstream int() truncates toward zero, including for negative coordinates.
    Do not replace with floor(), interpolate, or drop repeated source samples.
    """
    row, col = np.indices((retina.nrows, retina.ncols))
    y = ((2 * row - retina.nrows) / retina.nrows) / retina.zoom
    x = ((2 * col - retina.ncols) / retina.ncols) / retina.zoom
    denominator = 1 - retina.distortion_coefficient * (x*x + y*y) + 1e-6
    sr = np.trunc((y / denominator + 1) * retina.nrows / 2).astype(int)
    sc = np.trunc((x / denominator + 1) * retina.ncols / 2).astype(int)
    valid = (sr >= 0) & (sr < retina.nrows) & (sc >= 0) & (sc < retina.ncols)
    return np.where(valid, sr * retina.ncols + sc, -1)


def pinhole_rays(rows, cols, height, width, focal):
    rays = np.column_stack(((cols + .5 - width/2) / focal,
                           (height/2 - rows - .5) / focal,
                           -np.ones(np.size(rows))))
    return rays / np.linalg.norm(rays, axis=1, keepdims=True)


def peripheral_checks(cameras, height, width, rays):
    trials = []
    fmt = lambda values: " ".join(format(v, ".17g") for v in values)
    for camera in cameras:
        rotation = np.asarray(camera["rotation_camera_to_world"])
        position = np.asarray(camera["position_world_mm"])
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, rotation.ravel())
        radius = 20 * np.sin(np.deg2rad(6))
        xml = f'''<mujoco><visual><global offwidth="{width}" offheight="{height}"/>
        <quality numslices="128" numstacks="128" offsamples="0"/></visual>
        <worldbody><camera name="eye" pos="{fmt(position)}" quat="{fmt(quat)}"
        fovy="{camera['fovy_deg']}"/>
        <geom name="target" type="sphere" size="{radius}" pos="0 0 -20"/>
        </worldbody></mujoco>'''
        model = mujoco.MjModel.from_xml_string(xml)
        data = mujoco.MjData(model)
        renderer = mujoco.Renderer(model, height=height, width=width)
        try:
            renderer.enable_segmentation_rendering()
            world_rays = rays @ rotation.T
            for azimuth, elevation in PERIPHERAL_TARGETS_DEG:
                az, el = np.deg2rad([azimuth, elevation])
                direction = np.array([np.sin(az)*np.cos(el), np.sin(el), -np.cos(az)*np.cos(el)])
                center = position + rotation @ (20 * direction)
                model.geom_pos[0] = center
                mujoco.mj_forward(model, data)
                renderer.update_scene(data, camera="eye")
                segmentation = renderer.render()
                actual = (segmentation[..., 0] == 0) & (segmentation[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM))
                # Independent world-space ray/sphere quadratic discriminant,
                # rather than the calibration's angular dot-product threshold.
                offset = center - position
                dot = world_rays @ offset
                discriminant = dot**2 - (offset @ offset - radius**2)
                expected = (discriminant >= 0) & (dot > 0)
                union = int((actual | expected).sum())
                if not union:
                    raise AssertionError("Peripheral target must have visible support")
                trials.append({"eye": camera["side"], "azimuth_camera_right_deg": azimuth,
                    "elevation_camera_up_deg": elevation, "angular_radius_deg": 6.,
                    "distance_model_mm": 20., "sphere_radius_model_mm": float(radius),
                    "target_center_world_mm": center.tolist(),
                    "raw_predicted_pixels": int(expected.sum()), "raw_rendered_pixels": int(actual.sum()),
                    "raw_jaccard": float((actual & expected).sum()/union)})
        finally:
            renderer.close()
    return trials


def main():
    directory = ROOT / "validation/retina-rays"
    result_path = directory / "results.json"
    footprint_path = directory / "ray-footprints.npz"
    calibration = json.loads(result_path.read_text())
    protected = [ROOT / "scripts/calibrate_retina_rays.py", result_path,
                 footprint_path, directory / "rendered-checks.png"]
    protected_before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    source_matches = {p: sha(p) == digest for p, digest in calibration["source_sha256"].items()}
    with np.load(footprint_path, allow_pickle=False) as archive:
        saved = {key: archive[key].copy() for key in archive.files}
    retina = Retina()
    height, width = retina.nrows, retina.ncols
    source = saved["destination_to_source_pixel"]
    ids = saved["facet_id_map"]
    assert source.shape == ids.shape == (height, width)
    assert np.array_equal(ids, retina.ommatidia_id_map)
    assert np.array_equal(saved["pale_type_mask"], retina.pale_type_mask)
    assert np.array_equal(saved["camera_side"], ["L", "R"])
    assert saved["pixel_convention"].item() == "top-left origin; centers at column+0.5,row+0.5"
    assert calibration["raw_image_shape"] == [height, width, 3]
    cameras = calibration["cameras_at_initial_pose"]
    assert [c["side"] for c in cameras] == ["L", "R"]
    assert len({c["fovy_deg"] for c in cameras}) == 1
    assert np.array_equal(saved["camera_to_head_rotation"],
                          [c["rotation_camera_to_head_forward_left_up"] for c in cameras])
    focal = .5 * height / np.tan(np.deg2rad(cameras[0]["fovy_deg"]) / 2)

    rng = np.random.default_rng(SEED)
    raw = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    actual = retina.raw_image_to_hex_pxls(retina.correct_fisheye(raw))
    white = retina.raw_image_to_hex_pxls(retina.correct_fisheye(np.full_like(raw, 255))).sum(axis=1)
    means, radii, valid_fractions = [], [], []
    random_errors, white_errors, deduplicated_errors = [], [], []
    repeated_facets, incomplete_facets = 0, []
    unique_counts = []
    for facet in range(1, retina.num_ommatidia_per_eye + 1):
        samples = source[ids == facet]
        valid = samples[samples >= 0]
        assert len(valid) > 0
        vectors = pinhole_rays(valid // width, valid % width, height, width, focal)
        mean = vectors.sum(axis=0)
        mean /= np.linalg.norm(mean)
        means.append(mean)
        radii.append(float(np.rad2deg(np.arccos(np.clip(vectors @ mean, -1, 1))).max()))
        valid_fractions.append(len(valid)/len(samples))
        channel = int(retina.pale_type_mask[facet-1])
        predicted = raw.reshape(-1, 3)[valid, channel+1].sum()/len(samples)/255
        random_errors.append(float(abs(predicted-actual[facet-1, channel])))
        white_errors.append(float(abs(white[facet-1]-len(valid)/len(samples))))
        unique = np.unique(valid)
        unique_counts.append(len(unique))
        # Deliberately wrong comparator quantifies information lost by uniform
        # weighting of distinct pixels; this is not the implemented reduction.
        wrong = raw.reshape(-1, 3)[unique, channel+1].mean()/255
        deduplicated_errors.append(float(abs(predicted-wrong)))
        repeated_facets += int(len(unique) < len(valid))
        if len(valid) < len(samples):
            incomplete_facets.append({"facet_id_one_based": facet,
                "invalid_destination_pixels": int(len(samples)-len(valid)),
                "destination_pixels": int(len(samples))})

    pose_checks = []
    body = BodyRuntime(config=BodyConfig(enable_vision=True))
    try:
        for camera, index in zip(cameras, body.sim._intern_eye_camera_ids_by_fly[body.fly.name], strict=True):
            assert index >= 0
            head = body.data.geom_xmat[body._head_geom_id].reshape(3, 3) @ body._head_anatomical_basis
            world_rotation = body.data.cam_xmat[index].reshape(3, 3)
            head_rotation = head.T @ world_rotation
            name = mujoco.mj_id2name(body.model, mujoco.mjtObj.mjOBJ_CAMERA, index)
            assert name == camera["name"] == f"fly/{camera['side'].lower()}_eye_cam_camera"
            assert body.model.cam_projection[index] == 0 and not np.any(body.model.cam_sensorsize[index])
            assert body.model.cam_fovy[index] == camera["fovy_deg"]
            pose_checks.append({"eye": camera["side"], "camera_name": name,
                "world_position_max_absolute_error_mm": float(abs(body.data.cam_xpos[index]-camera["position_world_mm"]).max()),
                "world_rotation_max_absolute_error": float(abs(world_rotation-camera["rotation_camera_to_world"]).max()),
                "head_rotation_max_absolute_error": float(abs(head_rotation-camera["rotation_camera_to_head_forward_left_up"]).max()),
                "orthogonality_max_absolute_error": float(abs(head_rotation.T @ head_rotation-np.eye(3)).max()),
                "determinant": float(np.linalg.det(head_rotation)),
                "optical_forward_head_forward_left_up": (-head_rotation[:, 2]).tolist()})
    finally:
        body.close()

    rows, cols = np.indices((height, width))
    rays = pinhole_rays(rows.ravel(), cols.ravel(), height, width, focal).reshape(height, width, 3)
    trials = peripheral_checks(cameras, height, width, rays)
    metrics = {
        "source_index_mismatches": int((upstream_source_indices(retina) != source).sum()),
        "facet_mean_ray_max_absolute_error": float(abs(np.asarray(means)-saved["facet_mean_camera_ray"]).max()),
        "facet_support_radius_max_absolute_error_deg": float(abs(np.asarray(radii)-saved["facet_max_support_radius_deg"]).max()),
        "facet_valid_fraction_max_absolute_error": float(abs(np.asarray(valid_fractions)-saved["facet_valid_fraction"]).max()),
        "random_rgb_readout_max_absolute_error": max(random_errors),
        "white_field_readout_max_absolute_error": max(white_errors),
        "incorrect_uniform_unique_pixel_readout_max_absolute_error": max(deduplicated_errors),
        "facets_with_repeated_source_pixels": repeated_facets,
        "incomplete_facets": incomplete_facets,
        "peripheral_raw_jaccard_min": min(t["raw_jaccard"] for t in trials),
    }
    checks = {key: metrics[key] <= TOLERANCES[key] for key in (
        "source_index_mismatches", "facet_mean_ray_max_absolute_error",
        "facet_support_radius_max_absolute_error_deg", "facet_valid_fraction_max_absolute_error")}
    checks.update({
        "calibration_source_hashes_match": all(source_matches.values()),
        "footprint_hash_matches": sha(footprint_path) == calibration["footprints_sha256"],
        "unique_source_counts_match": np.array_equal(unique_counts, saved["facet_unique_source_pixels"]),
        "random_rgb_parity": max(random_errors) <= TOLERANCES["facet_readout_max_absolute_error"],
        "white_field_parity": max(white_errors) <= TOLERANCES["facet_readout_max_absolute_error"],
        "fresh_camera_poses": all(max(p[k] for k in ("world_position_max_absolute_error_mm", "world_rotation_max_absolute_error", "head_rotation_max_absolute_error")) <= TOLERANCES["fresh_camera_pose_max_absolute_error"] for p in pose_checks),
        "proper_rotations": all(p["orthogonality_max_absolute_error"] <= TOLERANCES["rotation_orthogonality_max_absolute_error"] and abs(p["determinant"]-1) <= TOLERANCES["rotation_orthogonality_max_absolute_error"] for p in pose_checks),
        "eyes_face_outward": pose_checks[0]["optical_forward_head_forward_left_up"][1] > 0 and pose_checks[1]["optical_forward_head_forward_left_up"][1] < 0,
        "all_12_peripheral_geometry_trials": len(trials) == 12 and min(t["raw_jaccard"] for t in trials) >= TOLERANCES["peripheral_raw_jaccard_min"],
        "root_artifacts_unchanged": all(sha(ROOT/p) == digest for p, digest in protected_before.items()),
    })
    files = [Path(__file__), ROOT/"fruitfly/body.py", Path(sys.modules[Retina.__module__].__file__),
             Path(sys.modules["flygym.simulation"].__file__),
             assets_dir/"model/neuromechfly/vision.yaml", assets_dir/"model/neuromechfly/compound_eye.npz"]
    result = {"schema_version": 1, "scope": __doc__, "completed": True,
        "seed": SEED, "thresholds": TOLERANCES,
        "versions": {name: importlib.metadata.version(name) for name in ("mujoco", "numpy", "flygym")},
        "review_source_sha256": {str(p): sha(p) for p in files},
        "reviewed_artifact_sha256": protected_before, "calibration_source_hash_matches": source_matches,
        "metrics": metrics, "fresh_camera_checks": pose_checks, "peripheral_trials": trials, "checks": checks,
        "limits": ["Local implementation audit; no biological retinal registration or phototransduction validation.",
            "Render checks use segmentation and tessellated spheres; they do not validate radiometry or body self-occlusion.",
            "Camera positions and head transforms are checked at initialization, not every articulated pose.",
            "Per-facet means are descriptive; finite support, duplicate weights and invalid destination samples remain necessary.",
            "The wrong uniform-unique-pixel comparator also omits invalid-sample attenuation; its error is diagnostic, not a pure duplicate-weight ablation."]}
    (directory/"independent-review.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"checks": checks, "metrics": metrics}, indent=2))
    if not all(checks.values()):
        raise AssertionError("Independent retina review failed; inspect saved receipt")


if __name__ == "__main__":
    main()
