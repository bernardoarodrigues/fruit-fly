"""Optional dimensionless world-light validation; no neural input/radiometry."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.illumination import WorldIlluminationConfig, add_world_illumination
from fruitfly.multiview import CubeEyeSampler, EyePose, eye_pose_from_body


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture_protocol(outdir):
    spec = mujoco.MjSpec.from_string('''<mujoco><visual>
      <global offwidth="258" offheight="258"/><quality offsamples="0" shadowsize="2048"/>
      <map znear=".001"/></visual><worldbody>
      <geom name="floor" type="plane" size="5 5 .1" rgba=".8 .8 .8 1"/>
      <geom name="occluder" type="box" pos="0 0 1" size=".5 .5 1" rgba=".4 .4 .4 1"/>
      </worldbody></mujoco>''')
    config = WorldIlluminationConfig()
    add_world_illumination(spec, config)
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    origin = np.array([3., -4., 5.])
    targets = np.array([[-1.5, 0, 0], [.8, -.2, 0]])
    world_axes = targets-origin
    world_axes /= np.linalg.norm(world_axes, axis=1, keepdims=True)
    rows, all_samples, panels = [], [], []
    poses = ((0, 0, 0), (21, -38, 63))
    for pose_index, angles in enumerate(poses):
        rotation = Rotation.from_euler("xyz", angles, degrees=True).as_matrix()
        with CubeEyeSampler(model, world_axes @ rotation) as sampler:
            samples = []
            for gain in (1., .5, 0.):
                model.light_ambient[:] = np.asarray(config.ambient_rgb)*gain
                model.light_diffuse[:] = np.asarray(config.diffuse_rgb)*gain
                faces = sampler.render_faces(data, EyePose(origin, rotation))
                values = sampler.mapping.sample(faces)
                samples.append(values)
                if pose_index == 0:
                    panels.append((gain, faces[5]))
                for target_index, target in enumerate(("lit_floor", "world_shadow")):
                    rows.append({"pose_index": pose_index, "light_gain": gain, "target": target,
                        "cube_face_zero_based": int(sampler.mapping.face[target_index]),
                        **dict(zip(("red", "green", "blue"), values[target_index].tolist()))})
            all_samples.append(samples)
    values = np.asarray(all_samples)
    pd.DataFrame(rows).to_csv(outdir/"fixture-rgb.csv", index=False)
    checks = {"lit_patch_above100": bool(values[0, 0, 0].min() > 100),
        "world_shadow_below40": bool(values[0, 0, 1].max() < 40),
        "half_gain_rgb_within1": bool(np.max(abs(values[:, 1]-.5*values[:, 0])) <= 1),
        "zero_gain_surfaces_black": bool(not values[:, 2].any()),
        "world_point_rgb_head_rotation_within1": bool(np.max(abs(values[0]-values[1])) <= 1),
        "headlight_disabled": model.vis.headlight.active == 0}
    result = {"configuration": asdict(config), "origin_world_model_units": origin.tolist(),
        "targets_world_model_units": targets.tolist(), "head_euler_xyz_deg": poses,
        "sample_axes_follow_world_targets": "head_axis = world_axis @ head_to_world; world points and world light stay fixed while head/cube cameras rotate",
        "cube_face_indices_for_pose1": [r["cube_face_zero_based"] for r in rows if r["pose_index"] == 1 and r["light_gain"] == 1],
        "rgb": values.tolist(), "checks": checks,
        "max_half_gain_rgb_error": float(np.max(abs(values[:, 1]-.5*values[:, 0]))),
        "max_head_rotation_rgb_difference": float(np.max(abs(values[0]-values[1]))),
        "limits": "Two interior surface samples, three coefficient gains and two head orientations. Does not establish arbitrary-texture/seam radiometric fidelity. Quantization and clipping prevent global exact linear RGB scaling."}
    return result, panels


def body_protocol(outdir):
    """Run only after BodyConfig integration is authorized and installed."""
    from fruitfly.body import BodyRuntime
    legacy = BodyRuntime(seed=7, config={"enable_vision": True})
    lit = None
    try:
        lit = BodyRuntime(seed=7, config={"enable_vision": True, "world_illumination": asdict(WorldIlluminationConfig())})
        compared, differences = [], []
        for name in dir(legacy.model):
            if name.startswith(("_", "light_", "name_")) or name in ("names", "names_map"):
                continue
            a, b = getattr(legacy.model, name), getattr(lit.model, name)
            if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
                compared.append(name)
                if not np.array_equal(a, b):
                    differences.append(name)
        state_samples = []
        for step in range(21):
            if step:
                legacy.advance(.005, .8, 1., "walk")
                lit.advance(.005, .8, 1., "walk")
            state_samples.append({"time_s": legacy.time_s,
                "qpos_max_absolute_difference": float(np.max(abs(legacy.data.qpos-lit.data.qpos))),
                "qvel_max_absolute_difference": float(np.max(abs(legacy.data.qvel-lit.data.qvel))),
                "contact_count_equal": legacy.data.ncon == lit.data.ncon})
        # Rendering state at a shared reset pose; changing light never moves it.
        legacy.reset(7)
        lit.reset(7)
        template = pd.read_csv(ROOT/"validation/visual-retinotopy/zhao-female-right-eye-directions.csv")
        directions = template[["unit_x_forward", "unit_y_left", "unit_z_dorsal"]].to_numpy()
        rgb_samples, images, native_samples = [], [], []
        with CubeEyeSampler(lit.model, directions) as sampler:
            for gain in (1., .5, 0., 1.):
                qpos_before = lit.data.qpos.copy()
                lit.set_stimulus("light", gain)
                faces = sampler.render_faces(lit.data, eye_pose_from_body(lit))
                values = sampler.mapping.sample(faces)
                native = lit.sim.get_ommatidia_readouts(lit.fly.name)
                native_samples.append(native.copy())
                rgb_samples.append({"gain": gain, "rgb_min": float(values.min()), "rgb_max": float(values.max()),
                    "fully_black_axes": int(np.all(values == 0, axis=1).sum()),
                    "ambient": lit.model.light_ambient.tolist(), "diffuse": lit.model.light_diffuse.tolist(),
                    "qpos_unchanged": bool(np.array_equal(qpos_before, lit.data.qpos)),
                    "native_retina_shape": list(native.shape), "native_retina_range": [float(native.min()), float(native.max())],
                    "native_retina_finite": bool(np.isfinite(native).all()),
                    "headlight_active": int(lit.model.vis.headlight.active)})
                if len(images) < 3:
                    images.append((gain, faces[3]))
            lit.set_stimulus("light", 0)
            lit.reset(7)
            reset_restores = (np.allclose(lit.model.light_ambient[0], WorldIlluminationConfig().ambient_rgb)
                              and np.allclose(lit.model.light_diffuse[0], WorldIlluminationConfig().diffuse_rgb)
                              and lit.model.vis.headlight.active == 0)
        result = {"legacy_light_count": int(legacy.model.nlight), "opt_in_light_count": int(lit.model.nlight),
            "legacy_snapshot_illumination": legacy.snapshot()["illumination"],
            "opt_in_snapshot_illumination": lit.snapshot()["illumination"],
            "legacy_headlight_active": int(legacy.model.vis.headlight.active), "opt_in_headlight_active": int(lit.model.vis.headlight.active),
            "equal_model_ndarray_names": compared, "model_array_differences": differences,
            "comparison_exclusions": "Private storage arrays (including _sizes), light arrays and global name-table/name-offset arrays; public numerical geometry, inertia, contacts, actuators, cameras, sensors and other model ndarray fields are compared exactly.",
            "changed_public_count_or_storage_scalars": {name: [int(getattr(legacy.model, name)), int(getattr(lit.model, name))]
                for name in dir(legacy.model) if name.startswith("n") and isinstance(getattr(legacy.model, name), (int, np.integer))
                and getattr(legacy.model, name) != getattr(lit.model, name)},
            "equal_timestep": legacy.model.opt.timestep == lit.model.opt.timestep,
            "gravity_equal": bool(np.array_equal(legacy.model.opt.gravity, lit.model.opt.gravity)),
            "simulated_s": .1, "physics_steps": 1000, "drive": [.8, 1.], "state_samples": state_samples,
            "light_gain_samples": rgb_samples, "reset_restores_opt_in_base_coefficients": bool(reset_restores),
            "native_retina_max_gain1_vs0_difference": float(np.max(abs(native_samples[0]-native_samples[2]))),
            "native_retina_max_restored_gain1_difference": float(np.max(abs(native_samples[0]-native_samples[3]))),
            "checks": {"default_preserved": legacy.model.nlight == 0 and legacy.model.vis.headlight.active == 1,
                "snapshot_modes_identify_configuration": legacy.snapshot()["illumination"]["mode"] == "legacy_camera_headlight"
                    and lit.snapshot()["illumination"]["mode"] == "fixed_world_directional",
                "one_fixed_light_only_opt_in": lit.model.nlight == 1 and lit.model.vis.headlight.active == 0,
                "all_compared_nonlight_arrays_equal": not differences,
                "1000_physics_steps_exact": all(t["qpos_max_absolute_difference"] == 0 and t["qvel_max_absolute_difference"] == 0 and t["contact_count_equal"] for t in state_samples),
                "native_retina_responds_and_restores": bool(np.max(abs(native_samples[0]-native_samples[2])) > .05
                    and np.array_equal(native_samples[0], native_samples[3]) and all(np.isfinite(v).all() for v in native_samples)),
                "gain_and_reset_preserved": bool(reset_restores and all(t["qpos_unchanged"] for t in rgb_samples)
                    and rgb_samples[0]["ambient"] == rgb_samples[3]["ambient"] and rgb_samples[0]["diffuse"] == rgb_samples[3]["diffuse"])}}
        return result, images
    finally:
        legacy.close()
        if lit is not None:
            lit.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", action="store_true", help="Also validate opt-in BodyConfig integration")
    args = parser.parse_args()
    outdir = ROOT/"validation/world-illumination"
    outdir.mkdir(parents=True, exist_ok=True)
    fixture, panels = fixture_protocol(outdir)
    body, body_panels = body_protocol(outdir) if args.body else (None, [])
    result = {"scope": __doc__, "fixture": fixture, "body": body,
        "body_integration_validated": args.body, "mujoco_version": mujoco.__version__,
        "background_caveat": "Fixed skybox/background/emissive surfaces are not light coefficients and may remain visible at zero gain.",
        "engineering_parameters": True, "biological_radiometry": False, "neural_input_installed": False,
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/"fruitfly/illumination.py", ROOT/"fruitfly/multiview.py")},
        "source_body_sha256_if_tested": sha(ROOT/"fruitfly/body.py") if args.body else None}
    (outdir/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    fig, axes = plt.subplots(2 if args.body else 1, 3, figsize=(13, 8 if args.body else 4), squeeze=False, layout="constrained")
    for ax, (gain, rgb) in zip(axes[0], panels, strict=True):
        ax.imshow(rgb)
        ax.set(title=f"Known occluder/floor; gain {gain}", xlabel="Cube -z pixel column", ylabel="Pixel row")
    if args.body:
        for ax, (gain, rgb) in zip(axes[1], body_panels, strict=True):
            ax.imshow(rgb)
            ax.set(title=f"Opt-in actual body; gain {gain}", xlabel="Cube -y pixel column", ylabel="Pixel row")
    fig.suptitle("Explicit fixed world illumination: dimensionless renderer coefficients\nCamera headlight disabled; geometry and world-light position remain fixed")
    fig.savefig(outdir/"diagnostic.png", dpi=140)
    plt.close(fig)
    checks = {**fixture["checks"], **(body["checks"] if body else {})}
    print(json.dumps({"body_tested": args.body, "checks": checks}, indent=2))
    if not all(checks.values()):
        raise AssertionError("World illumination validation failed; inspect retained results")


if __name__ == "__main__":
    main()
