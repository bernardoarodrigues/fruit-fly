#!/usr/bin/env python3
"""Review saved airflow evidence using source XML and NumPy kinematics only.

Does not import MuJoCo, FlyBody, the producer, the policy, or fruitfly runtime.
Does not construct or advance a simulator. Rewrites only its review receipt.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/flybody/source'


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def vector(value):
    return np.fromstring(value, sep=' ')


def quat_matrix(q):
    w, x, y, z = np.asarray(q) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
                     [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
                     [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])


def axis_rotation(axis, angle):
    x, y, z = np.asarray(axis) / np.linalg.norm(axis)
    k = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + np.sin(angle)*k + (1-np.cos(angle))*(k@k)


def xml_bodies(joint_rows):
    """Resolve source default inheritance, body transforms and hinge order."""
    xml = ET.parse(SOURCE / 'flybody/fruitfly/assets/fruitfly.xml').getroot()
    assert xml.find('compiler').attrib['angle'] == 'radian'
    defaults = {}

    def visit(node, inherited):
        attrs = dict(inherited)
        joint = node.find('joint')
        if joint is not None:
            attrs.update(joint.attrib)
        defaults[node.attrib.get('class', 'main')] = attrs
        for child in node.findall('default'):
            visit(child, attrs)

    visit(xml.find('default'), {})
    rows = {r['name'].removeprefix('walker/'): r for r in joint_rows}
    result = {}
    for name in ['head', 'antenna_left', 'antenna_right', 'abdomen']:
        node = xml.find('.//worldbody//body[@name="' + name + '"]')
        body = dict(pos=vector(node.attrib.get('pos', '0 0 0')),
                    rotation=quat_matrix(vector(node.attrib.get('quat', '1 0 0 0'))), joints=[])
        if name != 'abdomen':
            for joint in node.findall('joint'):
                attrs = {**defaults[joint.attrib.get('class', node.attrib.get('childclass', 'head'))],
                         **joint.attrib}
                row = rows[attrs['name']]
                axis = vector(attrs.get('axis', '0 0 1'))
                anchor = vector(attrs.get('pos', '0 0 0'))
                assert attrs.get('type', 'hinge') == 'hinge' and row['type'] == 3
                assert np.array_equal(anchor, np.zeros(3))
                assert np.array_equal(anchor, row['anchor_body_cm'])
                assert np.array_equal(axis, row['axis_body'])
                assert float(attrs.get('ref', 0)) == 0
                assert float(attrs.get('stiffness', 0)) == row['stiffness']
                assert float(attrs.get('damping', 0)) == row['damping']
                body['joints'].append(dict(axis=axis, q=row['qposadr'], v=row['dofadr']))
        result[name] = body
    return result


def kinematics(qpos, qvel, bodies, basis, root_rotation=None, root_position=None, root_linear=None):
    """Analytic serial hinge kinematics; MuJoCo free angular qvel is local."""
    root_r = quat_matrix(qpos[3:7]) if root_rotation is None else root_rotation
    root_p = qpos[:3] if root_position is None else root_position
    root_v = qvel[:3] if root_linear is None else root_linear
    root_w = root_r @ qvel[3:6]
    head = bodies['head']
    offset = root_r @ head['pos']
    head_p = root_p + offset
    head_v = root_v + np.cross(root_w, offset)
    head_r = root_r @ head['rotation']
    head_w = root_w.copy()
    for joint in head['joints']:
        head_w += head_r @ joint['axis'] * qvel[joint['v']]
        head_r = head_r @ axis_rotation(joint['axis'], qpos[joint['q']])
    out = []
    for name in ['antenna_left', 'antenna_right']:
        body = bodies[name]
        arm = head_r @ body['pos']
        origin = head_p + arm
        velocity = head_v + np.cross(head_w, arm)
        ant_r = head_r @ body['rotation']
        ant_w = head_w.copy()
        for joint in body['joints']:
            ant_w += ant_r @ joint['axis'] * qvel[joint['v']]
            ant_r = ant_r @ axis_rotation(joint['axis'], qpos[joint['q']])
        out.append(dict(origin=origin, velocity=velocity, rotation=ant_r, omega=ant_w))
    return out, head_r @ basis


def main():
    plan_path = 'validation/flybody-airflow-plan.json'
    result_path = 'validation/flybody-airflow-geometry.json'
    original_plan_path = 'validation/flybody-airflow-hash-v0-plan.json'
    original_result_path = 'validation/flybody-airflow-hash-v0-result.json'
    plan, result, old_plan, old = map(read, (plan_path, result_path, original_plan_path, original_result_path))
    checks = []

    def check(name, passed, detail=None):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))
        assert passed, name

    def close(name, actual, expected, tol=1e-12):
        actual, expected = np.asarray(actual), np.asarray(expected)
        error = float(np.max(abs(actual-expected)))
        check(name, actual.shape == expected.shape and np.isfinite(actual).all() and error <= tol, error)
        return error

    check('producer_hash_chain', result['plan_sha256'] == sha(plan_path)
          and result['script_sha256'] == plan['script_sha256'] == sha('scripts/audit_flybody_airflow.py')
          and result['geometry_sha256'] == sha(result['geometry_file']))
    check('original_hash_chain', old['plan_sha256'] == sha(original_plan_path)
          and old['script_sha256'] == old_plan['script_sha256'] == sha('validation/flybody-airflow-hash-v0-script.py'))
    check('original_failure_preserved', not old['passed'] and len(old['checks']) == 41
          and [c['name'] for c in old['checks'] if not c['passed']] == ['no_live_data_mutation'])
    check('amendment_same_numerical_evidence', old['geometry_sha256'] == result['geometry_sha256']
          and old['probes'] == result['probes'] and old['landmarks'] == result['landmarks']
          and old['sign_checks'] == result['sign_checks'])
    check('amendment_same_plan_parameters',
          {k:v for k,v in old_plan.items() if k not in ('created_at','script_sha256')}
          == {k:v for k,v in plan.items() if k not in ('created_at','script_sha256','amendment')})
    check('producer_completion_41_checks', result['complete'] and result['passed']
          and len(result['checks']) == 41 and all(c['passed'] for c in result['checks']))
    for path, expected in plan['frozen_files'].items():
        data = subprocess.run(['git', 'show', plan['repository_revision'] + ':' + path],
                              cwd=ROOT, check=True, capture_output=True).stdout
        cached = 'data/raw/flybody/airflow-source/' + plan['repository_revision'] + '/' + Path(path).name
        check('frozen_source:' + path, hashlib.sha256(data).hexdigest() == expected == sha(cached))
    manifest = read('validation/flybody-source-manifest.json')
    check('source_manifest_hash', sha('validation/flybody-source-manifest.json') == result['source']['source_manifest_sha256'])
    bad_source = [r['path'] for r in manifest['files'] if sha('data/raw/flybody/source/' + r['path']) != r['sha256']]
    check('all_upstream_files', not bad_source, dict(checked=len(manifest['files']), mismatches=bad_source))
    check('upstream_and_worker_identity', manifest['source_commit'] == plan['source_commit'] == result['source']['source_commit']
          and result['source']['worker_sha256'] == plan['frozen_files']['fruitfly/flybody_worker.py'])
    with np.load(ROOT / result['geometry_file'], allow_pickle=False) as archive:
        geometry = {key: archive[key] for key in archive.files}
    check('geometry_all_finite', all(np.isfinite(v).all() for v in geometry.values()))
    for name, landmark in result['landmarks'].items():
        points = geometry[name]
        check(name + ':vertex_count', points.shape == (landmark['vertices'], 3))
        for label, actual in [('vertex_mean_cm',points.mean(0)), ('min_cm',points.min(0)), ('max_cm',points.max(0))]:
            close(name + ':' + label, actual, landmark[label])
    basis = np.asarray(result['anatomical_basis_in_head'])
    close('basis_proper', basis.T @ basis, np.eye(3))
    check('basis_positive_determinant', abs(np.linalg.det(basis)-1) < 1e-12)
    close('neutral_operational_axes', geometry['head_to_world'], np.eye(3))
    close('neutral_head_calibration', np.asarray(result['neutral_head_to_world']) @ basis, np.eye(3))
    bodies = xml_bodies(result['joints'])
    check('all_nine_hinges_match_XML_axes_anchors_parameters', sum(len(v['joints']) for v in bodies.values()) == 9)
    close('neutral_head_rotation_from_XML', bodies['head']['rotation'], result['neutral_head_to_world'])
    lateral = geometry['antenna_origins'][0]-geometry['antenna_origins'][1]
    dorsal = geometry['head_ocelli'].mean(0)-geometry['rostrum'].mean(0)
    anterior = bodies['head']['pos']-bodies['abdomen']['pos']
    for name, actual in [('ant_left_minus_right',lateral), ('abdomen_to_head',anterior), ('rostrum_mean_to_ocelli_mean',dorsal)]:
        close('landmark_vector:' + name, actual, result['landmark_vectors_cm'][name])
    check('forward_left_dorsal_signs', anterior[0] > max(abs(anterior[1:]))
          and lateral[1] > max(abs(lateral[[0,2]])) and dorsal[2] > abs(dorsal[0])
          and geometry['head_ocelli'][:,2].min() > geometry['head'].mean(0)[2]
          and geometry['rostrum'][:,2].max() < geometry['head'].mean(0)[2])
    antenna_rows = [r for r in result['joints'] if 'antenna' in r['name']]
    check('passive_antenna_receipt', len(antenna_rows) == 6
          and all(r['stiffness'] == 0 and r['damping'] == .0003 and not r['native_actuator_names'] for r in antenna_rows)
          and not any('antenna' in name for name in result['observable_joint_names']))
    check('probes_exact_order', [p['case'] for p in result['probes']] == plan['probes'])
    rows, local_centers = [], []
    turn = axis_rotation([-.4,1.,.2], 1.1)
    boost, shift, air = np.array([7.,-3.,2.]), np.array([1.3,-.4,.7]), np.array([-4.,3.,.7])

    def check_flow(name, value, relative):
        error = close(name + ':relative_vector', value['relative_velocity_head_mm_s'], relative, 1e-10)
        horizontal = np.linalg.norm(relative[:,:2], axis=1)
        close(name + ':horizontal_speed', value['horizontal_speed_mm_s'], horizontal, 1e-10)
        angles = [float(np.rad2deg(np.arctan2(v[1], -v[0]))) if h > 1e-9 else None
                  for v,h in zip(relative,horizontal)]
        if any(a is None for a in angles):
            check(name + ':azimuth', angles == value['source_azimuth_deg'])
        else:
            close(name + ':azimuth', value['source_azimuth_deg'], angles, 1e-10)
        check(name + ':labels', value['antenna_order'] == ['L','R'] and value['head_axes'] == ['forward','left','up'])
        return error

    for probe in result['probes']:
        case = probe['case']
        q, v = np.asarray(probe['qpos']), np.asarray(probe['qvel'])
        check(case + ':state_shape_and_clock', q.shape == (116,) and v.shape == (114,)
              and np.isfinite(q).all() and np.isfinite(v).all() and probe['native_time_s'] == 0)
        expected, rotation = kinematics(q, v, bodies, basis)
        rotation_error = close(case + ':source_XML_head_rotation', probe['head_to_world'], rotation)
        origin_errors, velocity_errors, fd_errors, center_errors = [], [], [], []
        for i, (calculated, saved) in enumerate(zip(expected, probe['antennae'])):
            key = case + ':' + ['L','R'][i]
            origin_errors.append(close(key + ':source_XML_origin', saved['position_world_cm'], calculated['origin']))
            velocity_errors.append(close(key + ':analytic_origin_velocity', saved['origin_velocity_jacobian_cm_s'], calculated['velocity']))
            close(key + ':analytic_body_angular_velocity', saved['angular_velocity_world_rad_s'], calculated['omega'])
            if case == 'neutral_zero':
                local_centers.append(calculated['rotation'].T @
                    (np.asarray(saved['inertial_center_world_cm'])-calculated['origin']))
                close(key + ':NPZ_origin', geometry['antenna_origins'][i], calculated['origin'])
                close(key + ':NPZ_center', geometry['antenna_inertial_centers'][i], saved['inertial_center_world_cm'])
            arm = calculated['rotation'] @ local_centers[i]
            close(key + ':rigid_center_position', saved['inertial_center_world_cm'], calculated['origin']+arm)
            close(key + ':rigid_center_velocity', saved['inertial_center_velocity_cm_s'],
                  calculated['velocity']+np.cross(calculated['omega'],arm))
            correction = np.asarray(saved['inertial_center_velocity_cm_s']) + np.cross(
                saved['angular_velocity_world_rad_s'], np.asarray(saved['position_world_cm'])-saved['inertial_center_world_cm'])
            close(key + ':saved_center_correction', saved['origin_velocity_from_center_cm_s'], correction)
            center_errors.append(close(key + ':center_correction_vs_Jacobian', correction,
                                       saved['origin_velocity_jacobian_cm_s'], plan['tolerances']['inertial_velocity_correction_cm_s']))
            fd = np.asarray(saved['finite_difference_cm_s'])
            check(key + ':FD_shape', fd.shape == (len(plan['finite_difference_h_s']),3))
            fd_errors.append(close(key + ':saved_FD_vs_analytic', fd,
                np.tile(calculated['velocity'],(len(fd),1)), plan['tolerances']['jacobian_fd_cm_s']))
            close(key + ':saved_FD_error', saved['max_fd_error_cm_s'], float(np.max(abs(fd-saved['origin_velocity_jacobian_cm_s']))))
            close(key + ':saved_correction_error', saved['max_inertial_correction_error_cm_s'], center_errors[-1])
            close(key + ':COM_origin_speed_difference', saved['inertial_center_vs_origin_speed_difference_cm_s'],
                  np.linalg.norm(np.asarray(saved['inertial_center_velocity_cm_s'])-saved['origin_velocity_jacobian_cm_s']))
            check(key + ':own_hinge_pivot_Jacobian', saved['antenna_hinge_jacobian_max'] == 0)
        relative = (air-np.asarray([p['velocity'] for p in expected])*10) @ rotation
        flow_error = check_flow(case + ':flow', probe['flow'], relative)
        moved, moved_r = kinematics(q,v,bodies,basis, root_rotation=turn@quat_matrix(q[3:7]),
            root_position=turn@q[:3]+shift, root_linear=turn@v[:3]+boost/10)
        moved_relative = (turn@air+boost-np.asarray([p['velocity'] for p in moved])*10) @ moved_r
        moved_error = check_flow(case + ':transformed_flow', probe['transformed_flow'], moved_relative)
        invariant_error = close(case + ':independent_rigid_boost_invariance', moved_relative, relative, plan['tolerances']['invariance_mm_s'])
        saved_covariance = float(np.max(abs(np.asarray(probe['flow']['relative_velocity_head_mm_s'])-
            probe['transformed_flow']['relative_velocity_head_mm_s'])))
        close(case + ':saved_covariance_metric', probe['covariance_max_error_mm_s'], saved_covariance)
        rows.append(dict(case=case, max_source_XML_origin_error_cm=max(origin_errors),
            max_analytic_velocity_error_cm_s=max(velocity_errors), head_rotation_error=rotation_error,
            max_saved_FD_vs_analytic_cm_s=max(fd_errors), max_center_correction_error_cm_s=max(center_errors),
            flow_error_mm_s=flow_error, transformed_flow_error_mm_s=moved_error,
            analytic_invariance_error_mm_s=invariant_error, saved_covariance_error_mm_s=saved_covariance))
    for i, sign in enumerate(result['sign_checks']):
        if 'source_deg' in sign:
            angle = np.deg2rad(sign['source_deg'])
            relative = -5*np.array([np.cos(angle),-np.sin(angle),0.])
            close('sign:' + str(i) + ':opposite_velocity', sign['air_head_mm_s'], relative)
        else:
            relative = np.array([0.,0.,3. if sign['case'] == 'vertical_only' else 0.])
        check_flow('sign:' + str(i), sign['result'], np.tile(relative,(2,1)))
    excluded = result['excluded_python_owned_arrays']
    empty = [x for x in excluded if np.prod(x['shape']) == 0]
    nonempty = [x for x in excluded if np.prod(x['shape']) != 0]
    island_names = {'dof_island','dof_islandind','efc_island','island_dofind','island_efcind'}
    check('excluded_data_inventory', len(excluded) == 25 and len(empty) == 20
          and {x['name'] for x in nonempty} == island_names
          and all(x['owns_data'] and x['base_is_none'] and not x['raw_values_inspected'] for x in excluded)
          and all(not x['repeat_pointer_same'] for x in nonempty))
    check('islands_disabled_receipt', result['constraint_islands'] == dict(enableflags=0,nisland=0,enabled=False))
    header_path = 'tmp/flybody-env/lib/python3.10/site-packages/mujoco/include/mujoco/mjdata.h'
    header = (ROOT / header_path).read_text().split('// computed by mj_island')[1].split('// computed by mj_projectConstraint')[0]
    check('local_MuJoCo_header_island_fields', all(name + ';' in header for name in island_names))
    check('native_view_counts_receipt', result['live_numeric_data_arrays_checked'] == 119
          and result['live_numeric_model_arrays_checked'] == 246
          and old['live_numeric_data_arrays_checked'] == 144 and old['live_numeric_model_arrays_checked'] == 380)
    tree = ast.parse((ROOT / 'scripts/audit_flybody_airflow.py').read_text())
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
    check('producer_source_no_physics_advance_calls', not any(name in calls for name in ('step','mj_step','mj_step1','mj_step2','advance')))
    check('zero_step_and_disabled_receipt', result['physics_steps'] == result['actual_policy_steps'] == 0
          and not result['runtime_enabled'] and result['original_physics_timestep_s'] == .0002
          and result['original_control_timestep_s'] == .002)
    artifacts = [plan_path,result_path,original_plan_path,original_result_path,
        'scripts/audit_flybody_airflow.py','validation/flybody-airflow-hash-v0-script.py',result['geometry_file'],
        'validation/flybody-airflow-geometry.png','validation/flybody-airflow-ASSET-NOTICE.md',
        'validation/flybody-airflow-LICENSE-Apache-2.0.txt','validation/flybody-source-manifest.json',header_path]
    receipt = dict(created_at=datetime.now(timezone.utc).isoformat(), reviewer_sha256=sha('scripts/review_flybody_airflow.py'),
        passed=True, scope='Saved geometry/kinematics/source review; no new MuJoCo construction, physics or neural run.',
        artifact_sha256={p:sha(p) for p in artifacts}, checks=checks, check_count=len(checks),
        upstream_files_checked=len(manifest['files']), probes=rows,
        center_offsets_local_cm=[v.tolist() for v in local_centers],
        geometry_basis='Neutral thorax-aligned forward/left/up signs; articulated head follows source XML hinges.',
        visual_review='Two-panel PNG inspected: mm labels, origin/center markers, and anatomical signs are legible.',
        filter_review=dict(excluded_data_empty=len(empty), excluded_data_nonempty=[r['name'] for r in nonempty],
                           excluded_model_count=380-246, excluded_model_inventory_retained=False),
        limitations=[
            'Finite-difference velocities are retained, but plus/minus native positions and full Jacobians are not. Analytic XML velocities independently support their values; native API internals are not replayed.',
            'Transformed native qpos/qvel/Jacobians are not retained. NumPy source-kinematic rotation/boost reconstruction supports the saved transformed local flows.',
            'COM offsets use the saved neutral compiled inertial centers. This independently verifies rigid-body velocity propagation, not source mesh mass compilation.',
            'Native model/data before-after per-field hashes and physical arrays are not retained. No-mutation is producer evidence plus detached-copy source inspection, not an independently reconstructed state comparison.',
            'The five nonempty excluded data fields are documented disabled island outputs; the twenty remaining excluded data fields are empty. The 134 excluded model fields have no retained names/shapes, so their complete irrelevance is not independently established.',
            'Exact initial differing field names efc_island and island_efcind are an author diagnostic observation outside versioned receipts. The retained original result proves only the broad data-hash failure.',
            'The native-view filter is configuration-specific evidence, not a general assertion that every owning getter is meaningless or that all MuJoCo state was hashed.',
            'Antenna body origins are passive hinge pivots, not distal arista/sensillum receptor points. No aerodynamic response, physical antenna calibration, male/female transfer, or neural airflow gain is validated.'
        ])
    output = ROOT / 'validation/flybody-airflow-independent-review.json'
    output.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks),upstream_files=len(manifest['files']),probes=rows),indent=2))


if __name__ == '__main__':
    main()
