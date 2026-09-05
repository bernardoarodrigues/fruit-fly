"""Inspect installed NeuroMechFly proboscis geometry at its source zero pose.

The two pitch hinges are an explicitly selected composition-API subset, not a
published biological two-DOF model. Source supplies no oral motion limits or
extension trajectory. Only zero pose and infinitesimal Jacobian checks are used.
No dynamic rollout, neural mapping, mouth assignment, fluid or ingestion.
"""
from importlib.metadata import distribution, version
import hashlib
import inspect
import json
from pathlib import Path
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np
import yaml
from scipy.spatial import cKDTree

from flygym import assets_dir
from flygym.anatomy import AnatomicalJoint, Skeleton, AxisOrder, JointPreset
from flygym.compose.fly import NeuroMechFly, ActuatorType
from flygym.compose.fly.base_fly import BaseFly
from flygym.compose.pose import KinematicPosePreset

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"validation/proboscis-mechanics"
PARTS = ("c_head", "c_rostrum", "c_haustellum")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stl_vertices(p):
    raw = p.read_bytes()
    n = int.from_bytes(raw[80:84], "little")
    if len(raw) != 84+50*n:
        raise ValueError("Expected bundled binary STL")
    triangles = np.frombuffer(raw, dtype=np.dtype([("normal", "<f4", (3,)),
        ("vertex", "<f4", (3, 3)), ("attribute", "<u2")]), offset=84, count=n)
    return np.unique(triangles["vertex"].reshape(-1, 3), axis=0).astype(float)*BaseFly.SCALE


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model_dir = assets_dir/"model/neuromechfly"
    mesh_dir = model_dir/"meshes/simplified_max2000faces"
    paths = [Path(inspect.getfile(x)) for x in (NeuroMechFly, BaseFly, Skeleton, KinematicPosePreset)]
    paths += [model_dir/x for x in ("rigging.yaml", "mujoco_globals.yaml", "vision.yaml", "pose/neutral/yaw_pitch_roll.yaml")]
    paths += list(mesh_dir.glob("*.stl"))
    package = distribution("flygym")
    license_path = package.locate_file(next(p for p in package.files if str(p).endswith("licenses/LICENSE")))
    paths.append(license_path)
    (OUTPUT/"LICENSE-FlyGym.txt").write_bytes(license_path.read_bytes())
    hashes = {str(p): sha(p) for p in paths}
    rigging = yaml.safe_load((model_dir/"rigging.yaml").read_text())
    neutral = KinematicPosePreset.NEUTRAL.get_pose_by_axis_order(AxisOrder.YAW_PITCH_ROLL)
    source_proboscis_dofs = [d.name for j in JointPreset.ALL_BIOLOGICAL.to_joint_list()
                            if j.child.is_proboscis() for d in j.iter_dofs(AxisOrder.YAW_PITCH_ROLL)]
    # Empty thorax-head edge connects the requested tree without adding a head
    # hinge. Every other segment stays at the source mesh rigging pose.
    anatomical = [AnatomicalJoint("c_thorax", "c_head", []),
        AnatomicalJoint("c_head", "c_rostrum", ["pitch"]),
        AnatomicalJoint("c_rostrum", "c_haustellum", ["pitch"])]
    skeleton = Skeleton(axis_order=AxisOrder.YAW_PITCH_ROLL, anatomical_joints=anatomical)
    fly = NeuroMechFly(name="proboscis_diagnostic")
    joints = fly.add_joints(skeleton, neutral_pose=neutral)
    fly.add_actuators(joints.keys(), ActuatorType.POSITION, neutral_input=neutral)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model, data = fly.compile()
    mujoco.mj_resetDataKeyframe(model, data, model.key("neutral").id)
    mujoco.mj_forward(model, data)
    checks = {"explicit_two_pitch_dofs_only": model.nq == model.nv == model.nu == 2,
              "source_neutral_has_no_proboscis_angles": not any("rostrum" in k or "haustellum" in k for k in neutral.joint_angles_lookup_rad),
              "source_preset_offers_six_proboscis_dofs": len(source_proboscis_dofs) == 6,
              "no_joint_limits_supplied": not model.jnt_limited.any(),
              "no_actuator_ctrl_limits_supplied": not model.actuator_ctrllimited.any(),
              "zero_source_qpos": np.array_equal(data.qpos, [0., 0.])}
    parts, clouds = {}, {}
    for name in PARTS:
        body, geom = model.body(name).id, model.geom(name).id
        mesh = model.geom_dataid[geom]
        vertices = model.mesh_vert[model.mesh_vertadr[mesh]:model.mesh_vertadr[mesh]+model.mesh_vertnum[mesh]]
        world = vertices @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom]
        clouds[name] = world.copy()
        raw = stl_vertices(mesh_dir/f"{name}.stl")
        source_world = raw @ data.xmat[body].reshape(3, 3).T + data.xpos[body]
        mesh_error = max(cKDTree(source_world).query(world)[0].max(), cKDTree(world).query(source_world)[0].max())
        checks[name+"_compiled_mesh_matches_scaled_stl"] = mesh_error < 2e-7
        parts[name] = {"body_id": body, "geom_id": geom, "source_rigging": rigging[name],
            "body_origin_world_mm": data.xpos[body].tolist(), "body_rotation_world": data.xmat[body].reshape(3, 3).tolist(),
            "geom_pose_world_mm": data.geom_xpos[geom].tolist(), "geom_rotation_world": data.geom_xmat[geom].reshape(3, 3).tolist(),
            "geom_local_position_mm": model.geom_pos[geom].tolist(), "geom_local_quaternion": model.geom_quat[geom].tolist(),
            "mesh_vertices": int(model.mesh_vertnum[mesh]), "mesh_faces": int(model.mesh_facenum[mesh]),
            "source_to_compiled_vertex_max_error_mm": float(mesh_error),
            "world_min_mm": world.min(0).tolist(), "world_max_mm": world.max(0).tolist(),
            "contype": int(model.geom_contype[geom]), "conaffinity": int(model.geom_conaffinity[geom]),
            "geom_group": int(model.geom_group[geom]), "mass_native": float(model.body_mass[body])}
    body = model.body("c_haustellum").id
    distal_index = int(np.argmax(np.linalg.norm(clouds["c_haustellum"]-data.xpos[body], axis=1)))
    distal = clouds["c_haustellum"][distal_index]
    point_body = data.xmat[body].reshape(3, 3).T @ (distal-data.xpos[body])
    jacobian, rotjac = np.empty((3, model.nv)), np.empty((3, model.nv))
    mujoco.mj_jac(model, data, jacobian, rotjac, distal, body)
    analytic = np.column_stack([np.cross(data.xaxis[j], distal-data.xanchor[j]) for j in range(model.njnt)])
    finite = np.empty_like(jacobian)
    eps = 1e-6
    for j in range(model.nq):
        values = []
        for sign in (-1, 1):
            data.qpos[:] = 0
            data.qpos[j] = sign*eps
            mujoco.mj_forward(model, data)
            values.append(data.xpos[body] + data.xmat[body].reshape(3, 3) @ point_body)
        finite[:, j] = (values[1]-values[0])/(2*eps)
    data.qpos[:] = 0
    mujoco.mj_forward(model, data)
    jac_error = float(abs(jacobian-finite).max())
    analytic_error = float(abs(jacobian-analytic).max())
    checks["mesh_point_jacobian_finite_difference"] = jac_error < 1e-8
    checks["mesh_point_jacobian_independent_cross_product"] = analytic_error < 1e-12
    checks["no_dynamic_steps_or_contacts"] = data.time == 0 and data.ncon == 0
    checks["default_proboscis_collision_masks_disabled"] = all(parts[n]["contype"] == parts[n]["conaffinity"] == 0 for n in PARTS[1:])
    joint_table = []
    for j in range(model.njnt):
        a = next(a for a in range(model.nu) if model.actuator_trnid[a, 0] == j)
        joint_table.append({"name": model.joint(j).name, "axis_local": model.jnt_axis[j].tolist(),
            "anchor_world_mm": data.xanchor[j].tolist(), "axis_world": data.xaxis[j].tolist(),
            "limited": bool(model.jnt_limited[j]), "unused_range_rad": model.jnt_range[j].tolist(),
            "stiffness_native": float(np.ravel(model.jnt_stiffness[j])[0]),
            "damping_native": float(np.ravel(model.dof_damping[j])[0]), "armature_native": float(model.dof_armature[j]),
            "springref_rad": float(model.qpos_spring[j]), "position_actuator_name": model.actuator(a).name,
            "actuator_ctrl_limited": bool(model.actuator_ctrllimited[a]), "unused_ctrlrange": model.actuator_ctrlrange[a].tolist(),
            "actuator_force_limited": bool(model.actuator_forcelimited[a]), "actuator_forcerange_native": model.actuator_forcerange[a].tolist(),
            "actuator_gainprm": model.actuator_gainprm[a].tolist(), "actuator_biasprm": model.actuator_biasprm[a].tolist()})
    # Renderer colors/camera are diagnostic display choices only.
    for n, rgba in (("c_rostrum", (.9, .5, .12, 1)), ("c_haustellum", (.08, .65, .8, 1))):
        model.geom_rgba[model.geom(n).id] = rgba
    images = []
    with mujoco.Renderer(model, height=600, width=800) as renderer:
        for azimuth, elevation in ((90, 0), (180, 0), (110, 45)):
            camera = mujoco.MjvCamera()
            camera.type = mujoco.mjtCamera.mjCAMERA_FREE
            camera.lookat[:] = [.78, 0, 1.18]
            camera.distance, camera.azimuth, camera.elevation = 1.6, azimuth, elevation
            renderer.update_scene(data, camera=camera)
            images.append(renderer.render())
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for ax, img, label in zip(axes.flat, images, ("Side view", "Front view", "Ventral oblique")):
        ax.imshow(img); ax.axis("off"); ax.set_title(label+" — source zero pose")
    ax = axes[1, 1]
    for n, color in (("c_head", "#9da7af"), ("c_rostrum", "#dc861a"), ("c_haustellum", "#159eb5")):
        ax.scatter(clouds[n][:, 0], clouds[n][:, 2], s=1, c=color, label=n.removeprefix("c_"))
    anchors = data.xanchor
    ax.plot(anchors[:, 0], anchors[:, 2], "ko--", label="Joint origins")
    ax.plot(distal[0], distal[2], "*", color="#ae44ca", ms=13, label="Farthest mesh vertex")
    ax.set(xlabel="Source world x (mm)", ylabel="Source world z (mm)", title="Geometry diagnostic; mouth opening unassigned")
    ax.axis("equal"); ax.legend(fontsize=8); ax.grid(alpha=.2)
    fig.suptitle("NeuroMechFly proboscis: original geometry, no extension trajectory\nOrange rostrum / cyan haustellum; pitch-only diagnostic subset", fontsize=13)
    fig.savefig(OUTPUT/"source-geometry.png", dpi=150); plt.close(fig)
    np.savez_compressed(OUTPUT/"geometry.npz", **clouds, mesh_point_world_mm=distal, mesh_point_local_mm=point_body,
                        point_jacobian_mm_per_rad=jacobian, finite_difference_jacobian_mm_per_rad=finite)
    checks["source_files_unchanged"] = all(sha(Path(p)) == h for p, h in hashes.items())
    report = {"scope": __doc__, "script_sha256": sha(Path(__file__)), "versions": {p: version(p) for p in ("flygym", "mujoco", "numpy")},
        "source_license_expression": package.metadata.get("License-Expression"),
        "source_sha256": hashes, "source_proboscis_dofs_all_biological_preset": source_proboscis_dofs,
        "diagnostic_joint_selection": "Two pitch hinges selected via API; no source-specific biological two-DOF preset",
        "compile_warnings": [str(w.message) for w in caught], "joints": joint_table, "parts": parts,
        "source_poses_tested_rad": [[0., 0.]], "finite_difference_epsilon_rad": eps, "simulation_time_s": data.time,
        "mesh_point": {"selection": "Farthest compiled haustellum mesh vertex from its hinge origin; geometric fiducial, NOT identified mouth/contact aperture",
            "compiled_vertex_index": distal_index, "local_body_mm": point_body.tolist(), "world_mm": distal.tolist(),
            "distance_from_haustellum_origin_mm": float(np.linalg.norm(point_body)),
            "jacobian_mm_per_rad": jacobian.tolist(), "finite_difference_max_error_mm_per_rad": jac_error,
            "analytic_cross_product_max_error_mm_per_rad": analytic_error},
        "checks": {k: bool(v) for k, v in checks.items()},
        "claim_ceiling": "Source geometry and infinitesimal mechanics only; no validated extension range, actuator physiology, mouth point, pumping, swallowing or neural-to-muscle mapping."}
    (OUTPUT/"results.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["checks"], indent=2))
    if not all(checks.values()):
        raise AssertionError("Proboscis geometry audit failed; inspect receipt")


if __name__ == "__main__":
    main()
