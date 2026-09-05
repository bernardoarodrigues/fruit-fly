"""Zero-step audit of pinned FlyBody antenna origins and anatomical head axes.

Use isolated Python 3.10 for --plan-only/--run; plotting can use the main venv.
Never call env.step, mj_step, or change live runtime/source files.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

for key, value in {'TF_CPP_MIN_LOG_LEVEL': '2', 'CUDA_VISIBLE_DEVICES': '-1',
                   'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}.items():
    os.environ[key] = value
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f433f4f'
PLAN = ROOT / 'validation/flybody-airflow-plan.json'
RESULT = ROOT / 'validation/flybody-airflow-geometry.json'
GEOMETRY = ROOT / 'validation/flybody-airflow-geometry.npz'
PINNED = ('fruitfly/flybody_worker.py', 'fruitfly/wind.py')
CONFIG = dict(source_path=str(ROOT / 'data/raw/flybody/source'), width=800, height=560,
              food_position_mm=[6., 0.], food_radius_mm=3., water_position_mm=[5., 7.], water_radius_mm=2.)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_bytes(path):
    return subprocess.run(['git', 'show', REVISION + ':' + path], cwd=ROOT,
                          check=True, capture_output=True).stdout


def load_pinned(path, name):
    folder = ROOT / 'data/raw/flybody/airflow-source' / REVISION
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / Path(path).name
    content = git_bytes(path)
    if target.exists() and target.read_bytes() != content:
        raise ValueError('Changed frozen audit source: ' + str(target))
    target.write_bytes(content)
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Relocate asset lookup only; the frozen worker's functions stay identical.
    module.ROOT = ROOT
    return module


def make_plan():
    return dict(created_at=datetime.now(timezone.utc).isoformat(),
        script_sha256=digest(__file__), repository_revision=REVISION,
        frozen_files={p: hashlib.sha256(git_bytes(p)).hexdigest() for p in PINNED},
        source_commit='d015e9bfe441bd90ae431bac24c55cb74bdbce26',
        seed=11, physics_steps=0, finite_difference_h_s=[1e-5, 1e-6, 1e-7],
        probes=['neutral_zero', 'root_translation', 'antenna_rotation_only', 'root_head_antenna_motion'],
        basis='Reference thorax +x/+y/+z as forward/left/up; validate sign using head/abdomen positions, bilateral antenna origins, ocelli/head/rostrum mesh landmarks. Express this fixed neutral basis in the actual head body, then follow articulated head orientation.',
        velocities='mj_jac at actual antenna body origin times qvel; compare central finite differences and inertial-center velocity plus omega cross origin-minus-center.',
        invariance='Apply one common arbitrary proper rotation, translation and boost to actual clone root state and wind; head-frame relative air must remain invariant.',
        signs='Zero anterior, -90 left, +90 right wind-source azimuth; air velocity points opposite source; vertical-only and zero relative flow have null azimuth.',
        limits='Geometry only: no force/drag, wind-data download, measured angle fitting, neural mapping, male biomechanics or native policy/clock change. Anatomy basis stays disabled if signed landmark checks fail.',
        tolerances=dict(jacobian_fd_cm_s=2e-8, inertial_velocity_correction_cm_s=1e-10, invariance_mm_s=1e-9, basis=1e-12))


def numeric_arrays(owner):
    arrays = {}
    for name in dir(owner):
        if name.startswith('_'):
            continue
        try:
            value = getattr(owner, name)
        except Exception:
            continue
        if isinstance(value, np.ndarray) and value.dtype.kind in 'biuf':
            arrays[name] = hashlib.sha256(value.tobytes()).hexdigest()
    return arrays


def rotation_quaternion(axis, radians):
    axis = np.asarray(axis, float)
    axis /= np.linalg.norm(axis)
    return np.r_[np.cos(radians / 2), np.sin(radians / 2) * axis]


def mesh_world(m, d, name):
    gid = m.name2id('walker/' + name, 'geom')
    mesh = int(m.geom_dataid[gid])
    vertices = m.mesh_vert[int(m.mesh_vertadr[mesh]):int(m.mesh_vertadr[mesh]) + int(m.mesh_vertnum[mesh])]
    return vertices @ d.geom_xmat[gid].reshape(3, 3).T + d.geom_xpos[gid]


def run():
    plan = json.loads(PLAN.read_text())
    if digest(__file__) != plan['script_sha256']:
        raise ValueError('Audit script changed after plan')
    for path, expected in plan['frozen_files'].items():
        if hashlib.sha256(git_bytes(path)).hexdigest() != expected:
            raise ValueError('Frozen Git source changed')
    worker_module = load_pinned(PINNED[0], 'airflow_frozen_worker')
    wind_module = load_pinned(PINNED[1], 'airflow_frozen_wind')
    worker = worker_module.Worker(CONFIG, 11)
    import mujoco
    m, live = worker.m, worker.d
    before_data, before_model = numeric_arrays(live), numeric_arrays(m)
    before_state = worker.collect()
    before_observation = {k: np.asarray(v).copy() for k, v in worker.step_result.observation.items()}
    initial = copy.copy(live.ptr)
    head = m.name2id('walker/head', 'body')
    root = m.name2id('walker/thorax', 'body')
    abdomen = m.name2id('walker/abdomen', 'body')
    antenna = [m.name2id('walker/antenna_' + s, 'body') for s in ('left', 'right')]
    if min(head, root, abdomen, *antenna) < 0 or len(set(antenna)) != 2:
        raise ValueError('Required distinct frame missing')
    basis = initial.xmat[head].reshape(3, 3).T @ initial.xmat[root].reshape(3, 3)
    geometry = {name: mesh_world(m, initial, name) for name in ('thorax', 'head', 'head_ocelli', 'rostrum', 'antenna_left', 'antenna_right')}
    landmarks = {name: dict(vertex_mean_cm=v.mean(0).tolist(), min_cm=v.min(0).tolist(), max_cm=v.max(0).tolist(), vertices=len(v)) for name, v in geometry.items()}
    lateral = initial.xpos[antenna[0]] - initial.xpos[antenna[1]]
    anterior = initial.xpos[head] - initial.xpos[abdomen]
    dorsal = geometry['head_ocelli'].mean(0) - geometry['rostrum'].mean(0)
    head_center = geometry['head'].mean(0)
    checks = []
    def check(name, passed, detail=None):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))
    check('neutral_thorax_axes_world_identity', np.allclose(initial.xmat[root].reshape(3, 3), np.eye(3), atol=1e-12, rtol=0))
    check('forward_landmark', anterior[0] > 0 and abs(anterior[0]) > max(abs(anterior[1:])))
    check('left_landmark', lateral[1] > 0 and abs(lateral[1]) > max(abs(lateral[[0, 2]])))
    check('dorsal_landmarks', dorsal[2] > abs(dorsal[0]) and geometry['head_ocelli'][:, 2].min() > head_center[2] and geometry['rostrum'][:, 2].max() < head_center[2])
    check('proper_neutral_head_basis', np.allclose(basis.T @ basis, np.eye(3), atol=1e-12, rtol=0) and abs(np.linalg.det(basis) - 1) < 1e-12)
    axis_resolution = all(c['passed'] for c in checks)
    joint_rows = []
    head_ids, antenna_ids = [], []
    for jid in range(m.njnt):
        name = m.id2name(jid, 'joint') or ''
        if name.startswith('walker/') and ('head' in name or 'antenna' in name):
            row = dict(name=name, id=jid, body_id=int(m.jnt_bodyid[jid]), type=int(m.jnt_type[jid]),
                qposadr=int(m.jnt_qposadr[jid]), dofadr=int(m.jnt_dofadr[jid]),
                axis_body=m.jnt_axis[jid].tolist(), anchor_body_cm=m.jnt_pos[jid].tolist(),
                stiffness=float(m.jnt_stiffness[jid]), damping=float(m.dof_damping[m.jnt_dofadr[jid]]),
                native_actuator_names=[n for n in worker.names if n == name.removeprefix('walker/')])
            joint_rows.append(row)
            (antenna_ids if 'antenna' in name else head_ids).append(jid)
    check('retained_antenna_hinges', len(antenna_ids) == 6 and all(m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE for j in antenna_ids))
    check('no_native_antenna_actuators', not any('antenna' in name for name in worker.names))
    observable_joint_names = [joint.name for joint in worker.env.task.walker.observable_joints]
    check('antenna_joints_omitted_direct_actor_joint_observations', not any('antenna' in name for name in observable_joint_names))
    root_jid = int(np.flatnonzero(m.jnt_type == mujoco.mjtJoint.mjJNT_FREE)[0])
    root_q, root_v = int(m.jnt_qposadr[root_jid]), int(m.jnt_dofadr[root_jid])
    def measure(d):
        values = []
        for aid in antenna:
            point = d.xpos[aid].copy()
            jacp, jacr = np.empty((3, m.nv)), np.empty((3, m.nv))
            mujoco.mj_jac(m.ptr, d, jacp, jacr, point, aid)
            velocity = jacp @ d.qvel
            six = np.empty(6)
            mujoco.mj_objectVelocity(m.ptr, d, mujoco.mjtObj.mjOBJ_BODY, aid, six, 0)
            correction = six[3:] + np.cross(six[:3], point - d.xipos[aid])
            fd = []
            for h in plan['finite_difference_h_s']:
                plus, minus = copy.copy(d), copy.copy(d)
                mujoco.mj_integratePos(m.ptr, plus.qpos, d.qvel, h)
                mujoco.mj_integratePos(m.ptr, minus.qpos, d.qvel, -h)
                mujoco.mj_forward(m.ptr, plus)
                mujoco.mj_forward(m.ptr, minus)
                fd.append(((plus.xpos[aid] - minus.xpos[aid]) / (2 * h)).tolist())
            values.append(dict(position_world_cm=point.tolist(), inertial_center_world_cm=d.xipos[aid].tolist(),
                origin_velocity_jacobian_cm_s=velocity.tolist(), inertial_center_velocity_cm_s=six[3:].tolist(),
                angular_velocity_world_rad_s=six[:3].tolist(), origin_velocity_from_center_cm_s=correction.tolist(),
                finite_difference_cm_s=fd, max_fd_error_cm_s=float(np.max(abs(np.asarray(fd) - velocity))),
                max_inertial_correction_error_cm_s=float(np.max(abs(correction - velocity))),
                inertial_center_vs_origin_speed_difference_cm_s=float(np.linalg.norm(six[3:] - velocity)),
                antenna_hinge_jacobian_max=float(np.max(abs(jacp[:, m.jnt_dofadr[antenna_ids]])))))
        rotation = d.xmat[head].reshape(3, 3) @ basis
        return values, rotation
    probes = []
    for case in plan['probes']:
        d = copy.copy(initial)
        d.qvel[:] = 0
        if case == 'root_translation':
            d.qvel[root_v:root_v + 3] = [.3, -.2, .1]
        elif case == 'antenna_rotation_only':
            d.qvel[m.jnt_dofadr[antenna_ids]] = [3, -4, 5, -2, 6, -3]
        elif case == 'root_head_antenna_motion':
            d.qpos[root_q:root_q + 3] += [.3, -.2, .15]
            d.qpos[root_q + 3:root_q + 7] = rotation_quaternion([1, -2, 3], .7)
            d.qpos[m.jnt_qposadr[head_ids]] = [.12, -.35, .18]
            d.qpos[m.jnt_qposadr[antenna_ids]] = [.2, .04, .1, .3, -.04, .2]
            d.qvel[root_v:root_v + 6] = [.8, -.3, .2, 1.1, -.7, .5]
            d.qvel[m.jnt_dofadr[head_ids]] = [1.4, -.8, 1.1]
            d.qvel[m.jnt_dofadr[antenna_ids]] = [3, -4, 5, -2, 6, -3]
        mujoco.mj_forward(m.ptr, d)
        values, rotation = measure(d)
        check(case + ':finite_difference', all(v['max_fd_error_cm_s'] < 2e-8 for v in values))
        check(case + ':inertial_center_correction', all(v['max_inertial_correction_error_cm_s'] < 1e-10 for v in values))
        check(case + ':proper_head_rotation', np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12, rtol=0) and abs(np.linalg.det(rotation) - 1) < 1e-12)
        check(case + ':hinge_origins_zero_own_rotation_jacobian', all(v['antenna_hinge_jacobian_max'] < 1e-12 for v in values))
        if case == 'antenna_rotation_only':
            check('body_origin_is_not_inertial_center', min(v['inertial_center_vs_origin_speed_difference_cm_s'] for v in values) > .001)
        velocity = np.asarray([v['origin_velocity_jacobian_cm_s'] for v in values]) * 10
        air = np.array([-4., 3., .7])
        flow = wind_module.local_airflow(air, velocity, rotation)
        moved = copy.copy(d)
        quat = rotation_quaternion([-.4, 1., .2], 1.1)
        mat_flat = np.empty(9)
        mujoco.mju_quat2Mat(mat_flat, quat)
        turn = mat_flat.reshape(3, 3)
        shift = np.array([1.3, -.4, .7])
        boost_mm_s = np.array([7., -3., 2.])
        moved.qpos[root_q:root_q + 3] = turn @ d.qpos[root_q:root_q + 3] + shift
        mujoco.mju_mulQuat(moved.qpos[root_q + 3:root_q + 7], quat, d.qpos[root_q + 3:root_q + 7])
        # MuJoCo free-joint angular qvel is local; only linear qvel rotates.
        moved.qvel[root_v:root_v + 3] = turn @ d.qvel[root_v:root_v + 3] + boost_mm_s / 10
        mujoco.mj_forward(m.ptr, moved)
        moved_values, moved_rotation = measure(moved)
        moved_velocity = np.asarray([v['origin_velocity_jacobian_cm_s'] for v in moved_values]) * 10
        moved_flow = wind_module.local_airflow(turn @ air + boost_mm_s, moved_velocity, moved_rotation)
        covariance_error = float(np.max(abs(np.asarray(moved_flow['relative_velocity_head_mm_s']) - flow['relative_velocity_head_mm_s'])))
        check(case + ':actual_model_rigid_frame_covariance', covariance_error < 1e-9)
        probes.append(dict(case=case, qpos=d.qpos.tolist(), qvel=d.qvel.tolist(), native_time_s=float(d.time),
            antennae=values, head_to_world=rotation.tolist(), flow=flow, transformed_flow=moved_flow,
            covariance_max_error_mm_s=covariance_error))
    signs = []
    for source_deg in [-90., -45., 0., 45., 90., 180.]:
        angle = np.deg2rad(source_deg)
        source = np.array([np.cos(angle), -np.sin(angle), 0.])
        flow = wind_module.local_airflow(-source * 5, np.zeros((2, 3)), np.eye(3))
        signs.append(dict(source_deg=source_deg, air_head_mm_s=(-source * 5).tolist(), result=flow))
        check('source_sign:' + str(source_deg), np.allclose(flow['source_azimuth_deg'], [source_deg] * 2, rtol=0, atol=1e-10))
    for name, air in [('zero', [0., 0., 0.]), ('vertical_only', [0., 0., 3.])]:
        flow = wind_module.local_airflow(air, np.zeros((2, 3)), np.eye(3))
        signs.append(dict(case=name, result=flow))
        check(name + ':undefined_azimuth', flow['source_azimuth_deg'] == [None, None])
    check('no_live_data_mutation', numeric_arrays(live) == before_data)
    check('no_live_model_mutation', numeric_arrays(m) == before_model)
    check('no_live_observation_mutation', all(np.array_equal(v, worker.step_result.observation[k]) for k, v in before_observation.items()))
    check('no_live_state_or_clock_mutation', worker.collect() == before_state and float(live.time) == 0. and worker.tick == 0)
    geometry.update(antenna_origins=initial.xpos[antenna], antenna_inertial_centers=initial.xipos[antenna],
                    head_origin=initial.xpos[head], head_to_world=initial.xmat[head].reshape(3, 3) @ basis)
    np.savez_compressed(GEOMETRY, **geometry)
    report = dict(complete=True, passed=all(c['passed'] for c in checks), plan_sha256=digest(PLAN),
        source=worker.provenance, frozen_worker_revision=REVISION, script_sha256=digest(__file__),
        geometry_file=str(GEOMETRY.relative_to(ROOT)), geometry_sha256=digest(GEOMETRY),
        basis_resolved_for_engineering_geometry=axis_resolution, runtime_enabled=False,
        anatomical_basis_in_head=basis.tolist(), neutral_head_to_world=initial.xmat[head].reshape(3, 3).tolist(),
        head_body_id=head, thorax_body_id=root, antenna_body_ids=antenna, landmarks=landmarks,
        landmark_vectors_cm=dict(ant_left_minus_right=lateral.tolist(), abdomen_to_head=anterior.tolist(), rostrum_mean_to_ocelli_mean=dorsal.tolist()),
        joints=joint_rows, observable_joint_names=observable_joint_names, probes=probes, sign_checks=signs, checks=checks,
        original_physics_timestep_s=worker.env.physics.timestep(), original_control_timestep_s=worker.env.control_timestep(),
        live_numeric_data_arrays_checked=len(before_data), live_numeric_model_arrays_checked=len(before_model),
        physics_steps=0, actual_policy_steps=0,
        limitations=['Neutral thorax-aligned engineering head basis, not a measured arista-receptor frame or exact anatomical-axis calibration.',
                     'Model preserves passive antenna joints but removes their actuators/actor observations; generic passive dynamics are not calibrated to wind experiments.',
                     'Body origins are proximal hinge anchors, not distal odor receptors or arista centers. Own antenna rotation has zero velocity at that origin.',
                     'Vertex means are mesh landmarks for sign checks, not mass centers; inertial centers use compiled body_ipos/xipos.',
                     'No aerodynamic forces, near-body CFD, measured female curve, neural gains or male-specific biomechanics are applied.'])
    RESULT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    worker.close()
    print('Airflow checks', len(checks), 'passed', sum(c['passed'] for c in checks))
    for c in checks:
        if not c['passed']:
            print('FAIL', c)


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    z = np.load(GEOMETRY)
    fig, axs = plt.subplots(1, 2, figsize=(12, 5.2), constrained_layout=True)
    colors = dict(thorax='#86919f', head='#bd8446', head_ocelli='#2d2c26', rostrum='#deb783', antenna_left='#249682', antenna_right='#8264b4')
    for ax, (a, b, title) in zip(axs, [(0, 1, 'Dorsal projection: forward / left'), (0, 2, 'Side projection: forward / up')]):
        for name, color in colors.items():
            v = z[name] * 10
            ax.scatter(v[:, a], v[:, b], s=1, c=color, alpha=.25, rasterized=True, label=name.replace('_', ' '))
        origins, centers = z['antenna_origins'] * 10, z['antenna_inertial_centers'] * 10
        ax.scatter(origins[:, a], origins[:, b], marker='x', c='red', s=90, linewidths=2, label='antenna body origins')
        ax.scatter(centers[:, a], centers[:, b], marker='+', c='blue', s=90, linewidths=2, label='antenna inertial centers')
        for p, q in zip(origins, centers):
            ax.plot([p[a], q[a]], [p[b], q[b]], color='#526273', linewidth=1)
        ax.set(xlabel='Forward x (mm)', ylabel=('Left y (mm)' if b == 1 else 'Up z (mm)'), title=title)
        ax.set_aspect('equal')
        ax.grid(alpha=.15)
    axs[0].legend(fontsize=8, loc='lower left', ncol=2)
    fig.suptitle('Pinned FlyBody geometry at native reset — no physics step\nRed origins differ from blue inertial centers; axes calibrated to neutral thorax', fontsize=12)
    path = ROOT / 'validation/flybody-airflow-geometry.png'
    fig.savefig(path, dpi=180)
    plt.close(fig)
    print(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-only', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    if args.plan_only:
        if PLAN.exists():
            raise FileExistsError('Existing audit plan')
        PLAN.write_text(json.dumps(make_plan(), indent=2) + '\n')
        print('Saved plan', digest(PLAN))
    elif args.run:
        run()
    elif args.plot:
        plot()
    else:
        parser.error('Choose --plan-only, --run or --plot')
