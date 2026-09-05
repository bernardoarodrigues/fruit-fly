"""Audit actual FlyGym facet ray footprints; no neural/anatomical registration.

Decode the installed fisheye resampler with unique pixel codes. Independently
check pinhole geometry against MuJoCo-rendered sphere silhouettes at known rays.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flygym import assets_dir
from flygym.vision.retina import Retina
from fruitfly.body import BodyConfig, BodyRuntime


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lookup(retina):
    h, w = retina.nrows, retina.ncols
    codes = np.arange(1, h*w+1, dtype=np.uint32).reshape(h, w)
    encoded = np.stack([(codes >> shift) & 255 for shift in (0, 8, 16)], axis=-1).astype(np.uint8)
    transformed = retina.correct_fisheye(encoded).astype(np.int64)
    decoded = transformed[..., 0]+256*transformed[..., 1]+65536*transformed[..., 2]-1
    if not np.all((decoded >= -1) & (decoded < h*w)):
        raise AssertionError("Invalid decoded source-pixel index")
    return decoded


def ray_grid(h, w, fovy_deg):
    # MuJoCo perspective: camera +x right, +y up, view along -z.
    # The renderer's rows run down, with pixel centers offset by 0.5.
    row, col = np.indices((h, w))
    focal = .5*h/np.tan(np.deg2rad(fovy_deg)/2)
    rays = np.stack([(col+.5-w/2)/focal, (h/2-row-.5)/focal, -np.ones((h, w))], axis=-1)
    return rays/np.linalg.norm(rays, axis=-1, keepdims=True)


def facet_reduce(values, retina):
    ids = retina.ommatidia_id_map.ravel()
    total = np.bincount(ids, weights=values.ravel(), minlength=retina.num_ommatidia_per_eye+1)[1:]
    return total/retina.num_pixels_per_ommatidia


def sample_by_lookup(raw, source):
    out = np.zeros(source.shape, dtype=float)
    valid = source >= 0
    out[valid] = raw.ravel()[source[valid]]
    return out


def spherical_direction(azimuth_deg, elevation_deg):
    az, el = np.deg2rad([azimuth_deg, elevation_deg])
    return np.array([np.cos(el)*np.sin(az), np.sin(el), -np.cos(el)*np.cos(az)])


def main():
    outdir = ROOT/"validation/retina-rays"
    outdir.mkdir(parents=True, exist_ok=True)
    retina = Retina()
    h, w = retina.nrows, retina.ncols
    source = lookup(retina)
    valid = source >= 0
    facet_valid = facet_reduce(valid.astype(float), retina)
    # Independent random colors test the decoded lookup plus channel and weight
    # semantics against the complete upstream implementation.
    rng = np.random.default_rng(2081)
    parity_errors = []
    for _ in range(3):
        raw = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
        upstream = retina.raw_image_to_hex_pxls(retina.correct_fisheye(raw))
        predicted = np.zeros_like(upstream)
        for channel in (0, 1):
            mask = retina.pale_type_mask == channel
            values = facet_reduce(sample_by_lookup(raw[..., channel+1], source), retina)/255
            predicted[mask, channel] = values[mask]
        parity_errors.append(float(np.max(abs(upstream-predicted))))
    if max(parity_errors) > 1e-12:
        raise AssertionError("Decoded optical lookup does not reproduce actual facet readings")

    body = BodyRuntime(config=BodyConfig(enable_vision=True))
    try:
        cameras = []
        camera_ids = body.sim._intern_eye_camera_ids_by_fly[body.fly.name]
        for side, index in zip(("L", "R"), camera_ids, strict=True):
            if index < 0 or body.model.cam_projection[index] != 0 or np.any(body.model.cam_sensorsize[index]):
                raise AssertionError("Only audited fovy-based perspective cameras are supported")
            head_basis = body.data.geom_xmat[body._head_geom_id].reshape(3, 3) @ body._head_anatomical_basis
            cameras.append({"side": side, "camera_id": int(index),
                "name": mujoco.mj_id2name(body.model, mujoco.mjtObj.mjOBJ_CAMERA, index),
                "fovy_deg": float(body.model.cam_fovy[index]),
                "position_world_mm": body.data.cam_xpos[index].tolist(),
                "rotation_camera_to_world": body.data.cam_xmat[index].reshape(3, 3).tolist(),
                "rotation_camera_to_head_forward_left_up":
                    (head_basis.T @ body.data.cam_xmat[index].reshape(3, 3)).tolist()})
    finally:
        body.close()

    if cameras[0]["fovy_deg"] != cameras[1]["fovy_deg"]:
        raise AssertionError("This audit expects identical optics for both eyes")
    fovy = cameras[0]["fovy_deg"]
    rays = ray_grid(h, w, fovy)
    facet_means = np.column_stack([facet_reduce(sample_by_lookup(rays[..., axis], source), retina) for axis in range(3)])
    if np.any(np.linalg.norm(facet_means, axis=1) == 0):
        raise AssertionError("Facet lacks valid optical support")
    facet_means /= np.linalg.norm(facet_means, axis=1, keepdims=True)
    support_radius = []
    unique_sources = []
    for facet, mean in enumerate(facet_means, start=1):
        indices = source[retina.ommatidia_id_map == facet]
        indices = indices[indices >= 0]
        support_radius.append(float(np.rad2deg(np.arccos(np.clip(rays.reshape(-1, 3)[indices] @ mean, -1, 1))).max()))
        unique_sources.append(int(len(np.unique(indices))))

    # Predeclared geometric checks: 2 actual camera poses x 7 directions,
    # target angular radius 6 degrees, no fitting or camera adjustments.
    # Rasterized sphere meshes approximate curved silhouettes: allow 3% raw
    # union disagreement and 0.01 facet RMS; retain exact measured errors.
    directions = [(0, 0), (-55, 0), (55, 0), (0, -40), (0, 40), (-45, 30), (45, -30)]
    trials, panels = [], []
    for camera in cameras:
        rotation = np.asarray(camera["rotation_camera_to_world"])
        position = np.asarray(camera["position_world_mm"])
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, rotation.ravel())
        fmt = lambda values: " ".join(format(v, ".17g") for v in values)
        xml = f'''<mujoco><visual><global offwidth="{w}" offheight="{h}"/>
        <quality numslices="128" numstacks="128" offsamples="0"/></visual>
        <worldbody><camera name="eye" pos="{fmt(position)}" quat="{fmt(quat)}" fovy="{fovy}"/>
        <geom name="target" type="sphere" size="{20*np.sin(np.deg2rad(6))}" pos="0 0 -20"/>
        </worldbody></mujoco>'''
        model = mujoco.MjModel.from_xml_string(xml)
        data = mujoco.MjData(model)
        renderer = mujoco.Renderer(model, height=h, width=w)
        renderer.enable_segmentation_rendering()
        try:
            for az, el in directions:
                direction = spherical_direction(az, el)
                model.geom_pos[0] = position + rotation @ (20*direction)
                mujoco.mj_forward(model, data)
                renderer.update_scene(data, camera="eye")
                segmentation = renderer.render()
                actual = (segmentation[..., 0] == 0) & (segmentation[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM))
                expected = rays @ direction >= np.cos(np.deg2rad(6))
                union = actual | expected
                jaccard = float((actual & expected).sum()/union.sum())
                upstream = retina.raw_image_to_hex_pxls(retina.correct_fisheye(np.repeat((actual*255).astype(np.uint8)[..., None], 3, axis=2))).sum(axis=1)
                predicted = facet_reduce(sample_by_lookup(expected, source), retina)
                error = upstream-predicted
                trials.append({"eye": camera["side"], "azimuth_camera_right_deg": az,
                    "elevation_camera_up_deg": el, "angular_radius_deg": 6.,
                    "target_center_world_mm": model.geom_pos[0].tolist(),
                    "raw_predicted_pixels": int(expected.sum()), "raw_rendered_pixels": int(actual.sum()),
                    "raw_jaccard": jaccard, "facet_rms_error": float(np.sqrt(np.mean(error**2))),
                    "facet_max_absolute_error": float(abs(error).max()),
                    "geometry_check": bool(jaccard >= .97 and np.sqrt(np.mean(error**2)) <= .01)})
                if camera["side"] == "L" and (az, el) in [(0, 0), (55, 0), (-45, 30)]:
                    panels.append((az, el, actual, expected, upstream, predicted))
        finally:
            renderer.close()

    arrays = {"destination_to_source_pixel": source.astype(np.int32),
        "facet_id_map": retina.ommatidia_id_map, "facet_mean_camera_ray": facet_means,
        "facet_valid_fraction": facet_valid, "facet_max_support_radius_deg": np.asarray(support_radius),
        "facet_unique_source_pixels": np.asarray(unique_sources), "pale_type_mask": retina.pale_type_mask,
        "camera_to_head_rotation": np.asarray([c["rotation_camera_to_head_forward_left_up"] for c in cameras]),
        "camera_side": np.array(["L", "R"]), "pixel_convention": np.array("top-left origin; centers at column+0.5,row+0.5")}
    np.savez_compressed(outdir/"ray-footprints.npz", **arrays)
    files = [Path(__file__), ROOT/"fruitfly/body.py", Path(sys.modules[Retina.__module__].__file__),
        assets_dir/"model/neuromechfly/vision.yaml", assets_dir/"model/neuromechfly/compound_eye.npz"]
    result = {"scope": __doc__, "completed": True, "neural_input_installed": False,
        "anatomical_registration": None, "physiological_phototransduction": None,
        "mujoco_version": mujoco.__version__, "source_sha256": {str(p): sha(p) for p in files},
        "raw_image_shape": [h, w, 3], "facet_count_per_eye": retina.num_ommatidia_per_eye,
        "distortion_coefficient": retina.distortion_coefficient, "zoom": retina.zoom,
        "pixel_lookup_parity_errors": parity_errors, "cameras_at_initial_pose": cameras,
        "facet_valid_fraction_range": [float(facet_valid.min()), float(facet_valid.max())],
        "facets_with_any_invalid_pixels": int((facet_valid < 1).sum()),
        "facet_angular_support_radius_deg_range": [min(support_radius), max(support_radius)],
        "source_unique_pixels_per_facet_range": [min(unique_sources), max(unique_sources)],
        "checks": {"pixel_lookup_parity": max(parity_errors) <= 1e-12,
                   "all_14_rendered_geometry_trials": all(t["geometry_check"] for t in trials)},
        "rendered_geometry_trials": trials,
        "footprints_sha256": sha(outdir/"ray-footprints.npz"),
        "limits": ["Ray footprints describe the implemented artificial optics, not measured fly receptive fields.",
            "Mean ray alone discards finite facet support and duplicate pixel weights; retain lookup.",
            "Pale mask is shared across eyes and is not a mapped biological R7/R8 mosaic.",
            "Body pose changes require current camera/head transforms, not this initial world pose.",
            "Segmentation targets test geometry, not radiometry, renderer background, or body self-occlusion."]}
    (outdir/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    fig, axes = plt.subplots(3, 2, figsize=(12, 12), layout="constrained")
    for row, (az, el, actual, expected, upstream, predicted) in enumerate(panels):
        axes[row, 0].imshow(np.stack([expected, actual, np.zeros_like(actual)], axis=-1).astype(float))
        axes[row, 0].set_title(f"Known target: right {az}°, up {el}°\nRed analytic / green rendered / yellow agreement")
        axes[row, 0].set_xlabel("Raw image column")
        axes[row, 0].set_ylabel("Raw image row")
        axes[row, 1].plot(predicted, color="black", lw=1, label="Ray-footprint prediction")
        axes[row, 1].plot(upstream, color="tab:orange", lw=.8, ls="--", label="Actual renderer → FlyGym retina")
        axes[row, 1].set(xlabel="Facet index (not a MaleCNS column)", ylabel="Target coverage fraction", ylim=(-.03, 1.03))
        axes[row, 1].legend()
    fig.suptitle("Implemented retina geometry: independent rendered targets\nNo biological eye registration or neural phototransduction")
    fig.savefig(outdir/"rendered-checks.png", dpi=150)
    plt.close(fig)
    print(json.dumps({"checks": result["checks"], "invalid_facets": result["facets_with_any_invalid_pixels"],
        "support_radius_range_deg": result["facet_angular_support_radius_deg_range"],
        "worst_jaccard": min(t["raw_jaccard"] for t in trials),
        "worst_facet_rms": max(t["facet_rms_error"] for t in trials)}, indent=2))
    if not all(result["checks"].values()):
        raise AssertionError("Retina geometry audit failed; inspect retained results")


if __name__ == "__main__":
    main()
