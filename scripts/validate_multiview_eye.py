"""Six-view female optical-surrogate acquisition; no neural registration/input."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.body import BodyConfig, BodyRuntime
from fruitfly.multiview import (CubeEyeSampler, EyePose, FACE_NAMES,
                               cube_pixel_rays_head, eye_pose_from_body,
                               make_cube_mapping)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(values):
    return dict(zip(("min", "median", "p95", "max"),
                    np.quantile(values, [0, .5, .95, 1]).tolist()))


def rgb_world_light_probe():
    """A flat colored wall crosses +x/+y seam under one fixed world light.

    This tests preservation of renderer lights and sampling consistency, not
    photon units or a measured Drosophila spectral sensitivity.
    """
    model = mujoco.MjModel.from_xml_string('''<mujoco><visual>
      <global offwidth="258" offheight="258"/>
      <quality offsamples="0"/><headlight ambient=".9 .9 .9" diffuse="1 1 1" specular="1 1 1"/>
      </visual><worldbody>
      <light name="fixed_world_light" pos="0 0 0" dir="1 0 0" directional="true"
             ambient=".1 .1 .1" diffuse=".7 .5 .3" specular="0 0 0"/>
      <geom name="flat_colored_wall" type="box" pos="10 10 0" size=".1 4 4" rgba=".8 .5 .2 1"/>
      </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    rays = np.array([[1-1e-7, 1, 0], [1, 1, 0], [1+1e-7, 1, 0]])
    rays /= np.linalg.norm(rays, axis=1, keepdims=True)
    pose = EyePose([0, 0, 0], np.eye(3))
    result = {"description": rgb_world_light_probe.__doc__, "head_axes": rays.tolist(), "world_light_dir": [1, 0, 0],
              "world_light_ambient": [.1, .1, .1], "world_light_diffuse": [.7, .5, .3], "wall_rgba": [.8, .5, .2, 1]}
    model_light_dir = model.light_dir.copy()
    with CubeEyeSampler(model, rays) as sampler:
        mujoco.mj_forward(model, data)
        faces = sampler.render_faces(data, pose)
        lit = sampler.mapping.sample(faces)
        scene_lights = [{"id": int(l.id), "headlight": bool(l.headlight), "direction": l.dir.tolist(),
                         "ambient": l.ambient.tolist(), "diffuse": l.diffuse.tolist(),
                         "specular": l.specular.tolist(), "intensity": float(l.intensity)}
                        for l in sampler.renderer.scene.lights[:sampler.renderer.scene.nlight]]
        world = [l for l in scene_lights if not l["headlight"]]
        headlights = [l for l in scene_lights if l["headlight"]]
        preserve_world = (len(world) == 1 and world[0]["id"] == 0
                          and np.allclose(world[0]["direction"], model.light_dir[0])
                          and np.allclose(world[0]["ambient"], model.light_ambient[0])
                          and np.allclose(world[0]["diffuse"], model.light_diffuse[0]))
        headlight_zero = len(headlights) == 1 and all(not any(l[k]) for l in headlights for k in ("ambient", "diffuse", "specular"))
        model.light_active[0] = False  # isolated fixture's declared dark control
        mujoco.mj_forward(model, data)
        dark = sampler.sample(data, pose)
        # Intentionally huge model headlight remains configured but cannot
        # illuminate this private scene when the genuine world light is off.
        unchanged_model = bool(np.array_equal(model.light_dir, model_light_dir)
                               and np.allclose(model.vis.headlight.ambient, [.9]*3))
        seam_range = float(np.ptp(lit, axis=0).max())
        result.update({"selected_faces": [FACE_NAMES[i] for i in sampler.mapping.face], "scene_lights": scene_lights,
            "world_light_enabled_rgb": lit.tolist(), "world_light_disabled_rgb": dark.tolist(),
            "max_seam_channel_range_0_255": seam_range, "world_light_preserved": bool(preserve_world),
            "private_headlight_zeroed": bool(headlight_zero), "model_lights_not_overwritten": unchanged_model,
            "check": bool(preserve_world and headlight_zero and unchanged_model and seam_range <= 1
                          and lit.min() > 0 and (dark == 0).all())})
    return result


def main():
    outdir = ROOT/"validation/multiview-eye"
    outdir.mkdir(parents=True, exist_ok=True)
    template_path = ROOT/"validation/visual-retinotopy/zhao-female-right-eye-directions.csv"
    receipt_path = ROOT/"validation/visual-retinotopy/zhao-extraction.json"
    receipt = json.loads(receipt_path.read_text())
    if sha(template_path) != receipt["output"]["sha256"]:
        raise ValueError("Female template differs from its extraction receipt")
    table = pd.read_csv(template_path)
    if (len(table) != 852 or not table.sex.eq("female").all() or not table.eye.eq("R").all()
            or not np.array_equal(table.right_lens_index_1based, np.arange(1, 853))):
        raise ValueError("Expected coherent ordered 852-row female right-eye template")
    directions = table[["unit_x_forward", "unit_y_left", "unit_z_dorsal"]].to_numpy()
    mapping = make_cube_mapping(directions)
    support = mapping.support_rays_head()
    angle = np.degrees(np.arccos(np.clip(np.sum(support*directions[:, None, :], axis=-1), -1, 1)))
    cell_corners = mapping.support_cell_corners_head()
    cell_angle = np.degrees(np.arccos(np.clip(np.sum(cell_corners*directions[:, None, None, :], axis=-1), -1, 1)))
    mean = np.sum(support*mapping.weights[..., None], axis=1)
    mean /= np.linalg.norm(mean, axis=-1, keepdims=True)
    mean_error = np.degrees(np.arccos(np.clip(np.sum(mean*directions, axis=-1), -1, 1)))
    table["valid_axis"] = mapping.valid
    table["cube_face"] = np.asarray(FACE_NAMES)[mapping.face]
    for i in range(4):
        table[f"raw_row_{i}_zero_based"] = mapping.pixel_rows[:, i]
        table[f"raw_col_{i}_zero_based"] = mapping.pixel_cols[:, i]
        table[f"raw_weight_{i}"] = mapping.weights[:, i]
    table["support_max_pixel_center_offset_deg"] = angle.max(axis=1)
    table["support_max_pixel_cell_corner_offset_deg"] = cell_angle.max(axis=(1, 2))
    table["weighted_mean_direction_error_deg"] = mean_error

    # Continuous-coordinate seam test, independent of any renderer lighting or
    # anatomy. Cube tie order and +/-epsilon transitions are retained explicitly.
    seam_cases = []
    grid = cube_pixel_rays_head(256)
    for axis in ((1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, -1, -1),
                 (1, 1, 1), (-1, -1, -1)):
        triplet = np.tile(np.asarray(axis, dtype=float), (3, 1))
        dimension = int(np.flatnonzero(triplet[0])[0])
        triplet[:, dimension] += [-1e-7, 0, 1e-7]
        triplet /= np.linalg.norm(triplet, axis=1, keepdims=True)
        local = make_cube_mapping(triplet)
        values = local.sample(grid)
        seam_cases.append({"axis": axis, "perturbed_dimension": dimension, "epsilon": 1e-7,
            "selected_faces": [FACE_NAMES[i] for i in local.face],
            "max_coordinate_field_error": float(abs(values-triplet).max()),
            "max_transition_component_range": float(np.ptp(values, axis=0).max())})

    # Bare synthetic sphere fixture: target angle is known analytically. Two
    # independent poses include translation and all three rotation dimensions.
    # These are numerical probes, not acceptance angles or physical eye lenses.
    sphere_radius_deg = 4.
    distance = 20.
    xml = f'''<mujoco><visual><global offwidth="258" offheight="258"/>
      <quality numslices="128" numstacks="128" offsamples="0"/></visual><worldbody>
      <geom name="target" type="sphere" size="{distance*np.sin(np.deg2rad(sphere_radius_deg))}" pos="20 0 0"/>
      </worldbody></mujoco>'''
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    geometric_directions = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
        (1, 1, 0), (1, -1, 0), (1, 0, 1), (1, 0, -1), (0, 1, 1), (0, -1, -1), (1, 1, 1), (-1, -1, -1)], dtype=float)
    geometric_directions /= np.linalg.norm(geometric_directions, axis=1, keepdims=True)
    source_indices = (1, 200, 395, 600, 852)
    targets = np.vstack((geometric_directions, directions[np.array(source_indices)-1]))
    labels = [f"cube_{i}" for i in range(len(geometric_directions))] + [f"female_lens_{i}" for i in source_indices]
    trials, geometry_panels = [], []
    with CubeEyeSampler(model, targets) as sampler:
        for pose_index, euler in enumerate(((0, 0, 0), (23, -37, 61))):
            pose = EyePose([.71, -.29, 1.37], Rotation.from_euler("xyz", euler, degrees=True).as_matrix())
            for target_index, (label, target) in enumerate(zip(labels, targets, strict=True)):
                model.geom_pos[0] = pose.origin_world + pose.head_to_world @ (distance*target)
                mujoco.mj_forward(model, data)
                segmentation = sampler.render_faces(data, pose, segmentation=True)
                actual = (segmentation[..., 0] == 0) & (segmentation[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM))
                expected = grid @ target >= np.cos(np.deg2rad(sphere_radius_deg))
                jaccard = float((actual & expected).sum()/(actual | expected).sum())
                center = float(sampler.mapping.sample(actual.astype(float))[target_index])
                trials.append({"pose_index": pose_index, "target": label, "head_axis": target.tolist(),
                    "head_to_world": pose.head_to_world.tolist(), "origin_world_model_units": pose.origin_world.tolist(),
                    "target_center_world_model_units": model.geom_pos[0].tolist(), "sphere_angular_radius_deg": sphere_radius_deg,
                    "analytic_pixel_count": int(expected.sum()), "rendered_pixel_count": int(actual.sum()),
                    "jaccard_across_six_images": jaccard, "bilinear_mask_value_at_target_axis": center,
                    "check": bool(jaccard >= .97 and center == 1)})
                if pose_index == 1 and target_index in (0, 6, 12):
                    face = int(sampler.mapping.face[target_index])
                    geometry_panels.append((label, FACE_NAMES[face], expected[face], actual[face]))

    rgb_light_check = rgb_world_light_probe()

    # Live compiled body with movable head joints. Pose changes are imposed only
    # in this isolated diagnostic; no simulator defaults or integration edits.
    body = BodyRuntime(config=BodyConfig(enable_vision=True, enable_grooming=True))
    body_trials, images = [], []
    try:
        sampler = CubeEyeSampler(body.model, directions)
        try:
            initial_qpos = body.data.qpos.copy()
            initial_pose = eye_pose_from_body(body)
            for pose_name, yaw_deg, pitch_deg in (("initial", 0., 0.), ("head_yaw25_pitch-15", 25., -15.)):
                body.data.qpos[:] = initial_qpos
                for joint, delta in (("yaw", yaw_deg), ("pitch", pitch_deg)):
                    index = mujoco.mj_name2id(body.model, mujoco.mjtObj.mjOBJ_JOINT, f"fly/c_thorax-c_head-{joint}")
                    if index < 0:
                        raise ValueError("Movable diagnostic head joint is absent")
                    body.data.qpos[body.model.jnt_qposadr[index]] += np.deg2rad(delta)
                mujoco.mj_forward(body.model, body.data)
                pose = eye_pose_from_body(body)
                before_qpos, before_qvel = body.data.qpos.copy(), body.data.qvel.copy()
                before_cam_pos, before_cam_quat = body.model.cam_pos.copy(), body.model.cam_quat.copy()
                started = time.perf_counter()
                rgb = sampler.render_faces(body.data, pose)
                elapsed = time.perf_counter()-started
                values = mapping.sample(rgb)
                # Check actual current-pose provider against independently read
                # camera position and geometry rotation. Capture changes as data.
                for before, after in ((before_qpos, body.data.qpos), (before_qvel, body.data.qvel),
                                      (before_cam_pos, body.model.cam_pos), (before_cam_quat, body.model.cam_quat)):
                    if not np.array_equal(before, after):
                        raise AssertionError("Optical acquisition modified physics/model cameras")
                world_rays = directions @ pose.head_to_world.T
                rotation_angle = np.degrees(np.arccos(np.clip((np.trace(initial_pose.head_to_world.T @ pose.head_to_world)-1)/2, -1, 1)))
                body_trials.append({"pose": pose_name, "head_yaw_offset_deg": yaw_deg, "head_pitch_offset_deg": pitch_deg,
                    "origin_world_mm": pose.origin_world.tolist(), "head_to_world": pose.head_to_world.tolist(),
                    "origin_displacement_from_initial_mm": float(np.linalg.norm(pose.origin_world-initial_pose.origin_world)),
                    "head_rotation_from_initial_deg": float(rotation_angle),
                    "render_six_faces_wall_s": elapsed, "sample_shape": list(values.shape),
                    "valid_axis_count": int(mapping.valid.sum()), "all_rgb_finite": bool(np.isfinite(values).all()),
                    "rgb_range": [float(values.min()), float(values.max())],
                    "rgb_zero_sample_count": int(np.all(values == 0, axis=1).sum()),
                    "world_ray_norm_max_error": float(abs(np.linalg.norm(world_rays, axis=1)-1).max()),
                    "model_camera_and_qpos_qvel_unchanged": True,
                    "near_plane_mm": float(body.model.vis.map.znear*body.model.stat.extent),
                    "far_plane_mm": float(body.model.vis.map.zfar*body.model.stat.extent),
                    "model_world_light_count": int(body.model.nlight),
                    "scene_lights": [{"id": int(l.id), "headlight": bool(l.headlight), "ambient": l.ambient.tolist(),
                                      "diffuse": l.diffuse.tolist(), "specular": l.specular.tolist()}
                                     for l in sampler.renderer.scene.lights[:sampler.renderer.scene.nlight]],
                    "geomgroup_visibility": sampler.scene_option.geomgroup.tolist()})
                images.append((pose_name, rgb, values))
                for c, channel in enumerate(("red", "green", "blue")):
                    table[f"{pose_name}_rendered_{channel}_0_255"] = values[:, c]
        finally:
            sampler.close()
    finally:
        body.close()

    csv_path = outdir/"female-right-ray-sampling.csv"
    table.to_csv(csv_path, index=False)
    support_path = outdir/"cube-support.npz"
    np.savez_compressed(support_path, valid=mapping.valid, face_zero_based=mapping.face,
        rows_zero_based=mapping.pixel_rows, cols_zero_based=mapping.pixel_cols, weights=mapping.weights,
        pixel_center_rays_head=support, pixel_cell_corners_head=cell_corners,
        source_right_lens_index_1based=table.right_lens_index_1based.to_numpy())
    checks = {"all_852_unit_axes_retained": len(mapping.valid) == 852 and bool(mapping.valid.all()),
        "all_source_support_inside_rendered_images": bool((mapping.pixel_cols >= 0).all() and (mapping.pixel_cols < 258).all()
            and (mapping.pixel_rows >= 0).all() and (mapping.pixel_rows < 258).all()),
        "unit_weight_sums": bool(np.allclose(mapping.weights.sum(axis=1), 1, atol=1e-15)),
        "all_38_rendered_targets": all(t["check"] for t in trials),
        "seam_smooth_field_error_under_1e-5": all(t["max_coordinate_field_error"] < 1e-5 and t["max_transition_component_range"] < 1e-5 for t in seam_cases),
        "rgb_world_light_and_seam_probe": rgb_light_check["check"],
        "actual_body_all_axes_finite": all(t["all_rgb_finite"] for t in body_trials),
        "actual_head_rotation_exceeds20deg_and_eye_origin_moves": body_trials[1]["head_rotation_from_initial_deg"] > 20 and body_trials[1]["origin_displacement_from_initial_mm"] > .01,
        "render_does_not_mutate_body_or_model_cameras": all(t["model_camera_and_qpos_qvel_unchanged"] for t in body_trials)}
    result = {"scope": __doc__, "completed": True, "checks": checks, "mujoco_version": mujoco.__version__,
        "source": {"title": "Zhao et al.2025 Eye structure shapes neuron function in Drosophila motion vision",
            "doi": "10.1038/s41586-025-09276-5", "repository": "https://github.com/reiserlab/eyemap_T4",
            "commit": "99d2a43123db636cedb55af9ff31a59657e7d17e", "source_sex": "female", "sample": "20240701", "eye": "R",
            "source_ray_count": 852, "source_index": "right lens index1..852; source array and rendered pixel indices otherwise zero-based",
            "coordinate_system": "x forward / y left / z dorsal; no plot-y reflection",
            "template_to_body": "Canonical head bases identified as a declared different-specimen female body-optics surrogate; no landmark fit or male cell assignment."},
        "acquisition": {"core_resolution": 256, "guard_pixels_per_edge": 1, "rendered_image_shape_per_face": [258, 258, 3],
            "rendered_fovy_deg": mapping.fovy_deg, "core_fovy_deg": 90, "face_order": FACE_NAMES,
            "pixel_centers": "column+0.5,row+0.5; upper-left image origin", "query": "Bilinear RGB from four raw pixel centres in the max-positive-dot face; deterministic FACE_NAMES tie order.",
            "normalization": "All finite unit axes have four valid weights summing to1. No outside-face padding, missing support renormalization, or nearest-facet substitution.",
            "invalid_contract": "Rows with nonfinite coordinates or norm differing from1 by more than1e-6 remain present: validFalse, face/pixel indices-1, weights0, sampleNaN. Not encountered in the verified source.",
            "origin": "Current right-eye MuJoCo camera origin; six colocated monocular views with no stereo offset.",
            "model_changes": "None. Only independently owned renderer.scene GL camera structs are overwritten after geometry update.",
            "occlusion": "Exactly FlyGym default MjvOption minus groups1/2; visibility vector[1,0,0,0,0,0]. Hidden markers/selected body segments, other group0 body parts occlude.",
            "lighting": "All world lights retained; camera-attached headlight contribution zeroed only in private scene. Avoids retaining unrelated default-free-camera illumination or rotating artificial illumination at cube seams; model/default eye headlight unchanged.",
            "data_state": "Caller must supply current forward kinematics and must not advance physics concurrently during six-frame acquisition."},
        "pixel_center_support_max_angle_deg": summary(angle.max(axis=1)),
        "pixel_cell_corner_support_max_angle_deg": summary(cell_angle.max(axis=(1, 2))),
        "weighted_mean_direction_error_deg": summary(mean_error),
        "source_count_by_face": dict(zip(FACE_NAMES, np.bincount(mapping.face, minlength=6).tolist())),
        "seam_tests": seam_cases, "rendered_target_tests": trials, "rgb_world_light_probe": rgb_light_check, "actual_body_tests": body_trials,
        "neural_input_installed": False, "male_registration": None, "physiological_transfer": None,
        "limits": ["Full angular acquisition is an engineering change, not a reconstruction of the physiological eye.",
            "Individual lens origins, refraction, aberration, measured acceptance functions, spectral sensitivities, adaptation and phototransduction are absent.",
            "Finite raw pixel rasterization and four-pixel bilinear interpolation approximate point-direction queries; kernel size varies with cube position and has no measured optical interpretation.",
            "Guard pixels remove undefined seam support, but independent face rasterization can still differ for high-frequency textures or geometry exactly at seams; tests quantify geometry/smooth fields only.",
            "RGB includes renderer lighting, material/texture and anti-aliasing conventions. It is display RGB, not photon flux or neural current/release.",
            "Existing selected-body hiding and clipping may omit real near-field occluders. Complete geometric direction coverage does not mean every direction sees the environment rather than body/background.",
            "The tested actual body has no independent model world lights; suppressing its headlight makes non-emissive floor/resource/body surfaces black. This is retained as valid dark RGB, not padding; no hidden diagnostic lamp is added to that body scene.",
            "Female template and female-derived body are different specimens; no male neural column identities assigned. Runtime body/viewer/neural defaults are untouched."],
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/"fruitfly/multiview.py", ROOT/"fruitfly/body.py", template_path, receipt_path)},
        "outputs": {p.name: sha(p) for p in (csv_path, support_path)}}
    (outdir/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")

    fig, axes = plt.subplots(3, 3, figsize=(13, 11), layout="constrained")
    for ax, (label, face, expected, actual) in zip(axes[0], geometry_panels, strict=True):
        ax.imshow(np.stack((expected, actual, np.zeros_like(actual)), axis=-1).astype(float))
        ax.set(title=f"{label}, face {face}: known 4° sphere", xlabel="Raw pixel column", ylabel="Raw pixel row")
    az = table.azimuth_deg_positive_left.to_numpy()
    az = np.where(az > 90, az-360, az)
    elevation = table.elevation_deg.to_numpy()
    for row, (pose_name, rgb, values) in enumerate(images, start=1):
        for col, face in enumerate((0, 3)):
            axes[row, col].imshow(rgb[face])
            axes[row, col].set(title=f"{pose_name}: cube{FACE_NAMES[face]}", xlabel="Raw pixel column", ylabel="Raw pixel row")
        axes[row, 2].scatter(az, elevation, c=np.clip(values/255, 0, 1), s=11, edgecolors=".6", linewidths=.1)
        axes[row, 2].set(title=f"All 852 sampled axes: {pose_name}", xlabel="Head azimuth (°, positive left)", ylabel="Elevation (°)", facecolor=".8")
    fig.suptitle("Isolated cube acquisition of female right-eye optical template\nRed/green/yellow = analytic/rendered/agreement; body RGB has no neural or radiometric calibration")
    fig.savefig(outdir/"diagnostic.png", dpi=140)
    plt.close(fig)
    print(json.dumps({"checks": checks, "worst_target_jaccard": min(t["jaccard_across_six_images"] for t in trials),
        "max_pixel_support_angle_deg": float(angle.max()), "max_weighted_mean_direction_error_deg": float(mean_error.max()),
        "body_acquisition_wall_s": [t["render_six_faces_wall_s"] for t in body_trials]}, indent=2))
    if not all(checks.values()):
        raise AssertionError("Multiview diagnostic failed; inspect retained results")


if __name__ == "__main__":
    main()
