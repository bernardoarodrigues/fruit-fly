#!/usr/bin/env python3
"""Independent saved-record habitat audit; no controller or physics execution."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/flybody-habitat-independent-review.json'
PLAN_HASH = 'a9a5c7dc77124d6008d78ceb9c98b7785c02ff15ce47d3db926d262fd94c4397'
CHECKS = []
PINS = {}
ARRAY_FIELDS = ['qpos', 'qvel', 'qacc', 'act', 'ctrl', 'canonical_action', 'native_action',
    'pose_cm_quat', 'target_pose_cm_quat', 'actuator_force_preceding_stage', 'actuator_length',
    'actuator_activation', 'velocity_world_mm_s', 'angular_velocity_world_rad_s', 'support_dyne_by_leg',
    'ground_force_g_mm_s2', 'antenna_positions_mm', 'claw_positions_mm', 'warnings']
READONLY_FIELDS = ['qpos', 'qvel', 'qacc', 'act', 'ctrl', 'sensordata', 'xpos', 'xmat', 'cvel']


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(name, value, **details):
    CHECKS.append(dict(name=name, passed=bool(value), **details))
    if not value:
        raise AssertionError(name)


def exact(name, a, b):
    a, b = np.asarray(a), np.asarray(b)
    check(name, a.shape == b.shape and np.array_equal(a, b))


def close(name, a, b, tolerance=1e-10):
    a, b = np.asarray(a), np.asarray(b)
    error = float(np.max(np.abs(a-b))) if a.size else 0.
    check(name, a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
          and error <= tolerance, maximum_absolute_error=error, tolerance=tolerance)
    return error


def pin(name, expected):
    actual = sha(ROOT / name)
    PINS[name] = dict(expected_sha256=expected, actual_sha256=actual, bytes=(ROOT/name).stat().st_size)
    check('hash:' + name, actual == expected)


def geometry_review(label, case):
    meta = case['geometry']['metadata']
    config = case['config']['habitat']
    check(label + ':geometry-config', all(meta[k] == v for k, v in config.items()))
    center = np.array(config['center_mm'])
    half = np.array(config['inner_size_mm']) / 2.
    height, thick = config['wall_height_mm'], config['wall_thickness_mm']
    floor_z = meta['floor_z_mm']
    exact(label + ':visible-plane-center', meta['visible_floor_center_mm'], [*center, floor_z])
    close(label + ':visible-plane-half-size', meta['visible_floor_half_size_mm'], half + thick, 1e-13)
    expected_names = ['habitat_wall_' + axis + '_' + side for axis in ('x', 'y') for side in ('neg', 'pos')]
    check(label + ':four-walls-exact-name-order', [w['geom'] for w in meta['walls']] == expected_names)
    ids = [w['compiled_geom_id'] for w in meta['walls']]
    check(label + ':unique-positive-wall-ids', len(set(ids)) == 4 and min(ids) >= 0)
    for i, w in enumerate(meta['walls']):
        axis, side = i // 2, (-1 if i % 2 == 0 else 1)
        expected_center = np.r_[center, floor_z + height / 2]
        expected_center[axis] += side * (half[axis] + thick / 2)
        expected_size = np.r_[half, height / 2]
        expected_size[axis] = thick / 2
        if axis == 0:
            expected_size[1] += thick
        close(label + ':' + w['geom'] + ':center-mm', w['center_mm'], expected_center, 1e-13)
        close(label + ':' + w['geom'] + ':half-size-mm', w['half_size_mm'], expected_size, 1e-13)
        inner_face = w['center_mm'][axis] - side * w['half_size_mm'][axis]
        close(label + ':' + w['geom'] + ':inner-face-mm', inner_face, center[axis] + side * half[axis], 1e-13)
        check(label + ':' + w['geom'] + ':collision-settings', w['contype'] == w['conaffinity'] == 1
              and meta['wall_condim'][i] == meta['floor_condim'])
        for field in ('friction', 'solref', 'solimp'):
            exact(label + ':' + w['geom'] + ':' + field, w[field], meta['floor_contact_parameters']['geom_' + field])
    for kind in ('food', 'water'):
        resource = meta['resource_regions'][kind]
        xy = np.array(case['config'][kind + '_position_mm'])
        radius = case['config'][kind + '_radius_mm']
        close(label + ':' + kind + ':visual-center', resource['center_mm'], [*xy, floor_z + .001], 1e-13)
        close(label + ':' + kind + ':radius', resource['radius_mm'], radius, 1e-13)
        check(label + ':' + kind + ':planar-footprint-inside', (np.abs(xy-center) + radius <= half).all()
              and resource['separate_collision_geometry'] is False and resource['visual_half_thickness_mm'] == .001)
    check(label + ':metadata-matches-worker-export', case['metadata']['habitat'] == {k: meta[k] for k in case['metadata']['habitat']})
    return {w['geom']: w for w in meta['walls']}


def contacts_review(label, samples, walls):
    errors, orthogonal, contacts = [], [], []
    for sample_index, sample in enumerate(samples):
        for contact in sample['wall_contacts']:
            wall = walls[contact['wall']]
            gid = wall['compiled_geom_id']
            assert (contact['geom1'] == gid) != (contact['geom2'] == gid)
            assert contact['fly_geom'].startswith('walker/')
            sign = 1. if contact['geom1'] == gid else -1.
            frame = np.array(contact['frame_world_rows'])
            force = np.array(contact['local_force_torque_dyne_dyne_cm'])
            assert frame.shape == (3, 3) and force.shape == (6,)
            assert np.isfinite(frame).all() and np.isfinite(force).all()
            # Explicit linear combination of basis rows, independent of f @ R.
            reconstructed = sign * sum(force[k] * frame[k] for k in range(3))
            errors.append(float(np.max(abs(reconstructed - contact['force_world_dyne_on_fly']))))
            orthogonal.append(float(np.max(abs(frame @ frame.T - np.eye(3)))))
            assert np.isfinite([contact['dist_mm'], *contact['position_mm'], *contact['force_world_dyne_on_fly']]).all()
            assert not contact['active'] or contact['dist_mm'] <= 0.
            contacts.append((sample_index, contact, sign * frame[0]))
    check(label + ':all-saved-world-forces-reconstructed', max(errors, default=0.) < 1e-9,
          contacts=len(contacts), maximum_absolute_error_dyne=max(errors, default=0.))
    check(label + ':all-contact-frames-orthonormal', max(orthogonal, default=0.) < 1e-10,
          maximum_absolute_error=max(orthogonal, default=0.))
    return contacts


def readonly_review(label, record, initial):
    before, after = record['before'], record['after']
    check(label + ':named-live-state-hashes-equal', before == after and record['sampled_live_state_unchanged'])
    check(label + ':named-live-array-scope', sorted(before['arrays']) == sorted(READONLY_FIELDS))
    check(label + ':zero-time-and-actor-match', before['time'] == 0. and before['actor'] == initial['actor_input_sha256'])
    for key in ('qpos', 'qvel', 'qacc', 'act', 'ctrl'):
        expected = hashlib.sha256(np.asarray(initial[key], np.float64).tobytes()).hexdigest()
        check(label + ':initial-array-hash:' + key, expected == before['arrays'][key])


def floor_only_contract():
    # Execute only the isolated pure contact predicate, never import the runtime.
    source = ROOT / 'fruitfly/flybody_bridge.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FlyBodyRuntime')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_contacts')
    env = {'np': np, 'LEGS': ('LF', 'LM', 'LH', 'RF', 'RM', 'RH')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), env)
    instance = SimpleNamespace(config=SimpleNamespace(food_position_mm=(6., 0.), food_radius_mm=3., water_position_mm=(5., 7.), water_radius_mm=2.))
    for kind, center, radius in [('food', (6., 0.), 3.), ('water', (5., 7.), 2.)]:
        for active in (False, True):
            for tarsal in (False, True):
                for displacement in (0., radius, radius + .001):
                    contact = dict(active=active, is_tarsal=tarsal, leg='LF', position_mm=[center[0]+displacement, center[1], 0.])
                    state = {'contacts': [], 'habitat': {'wall_contacts': [contact]}}
                    assert not any(env['_contacts'](instance, state, kind).values())
                    state['contacts'] = [contact]
                    assert any(env['_contacts'](instance, state, kind).values()) == (active and tarsal and displacement <= radius)
    check('pure-floor-resource-boundary-contract-48-cases', True)


def shallow_review(original_case, initial, initial_actor, walls):
    plan_path = ROOT / 'validation/flybody-habitat-shallow-contact-plan.json'
    result_path = ROOT / 'validation/flybody-habitat-shallow-contact-results.json'
    plan, result = read(plan_path), read(result_path)
    expected_plan = '9886c5a0d3fb86c8451cc3aa27c8fd1049c513b68e229dde2db0f3d1eb3c56f9'
    check('shallow:frozen-plan', sha(plan_path) == result['plan_sha256'] == expected_plan)
    pin(str(plan_path.relative_to(ROOT)), expected_plan)
    pin(str(result_path.relative_to(ROOT)), sha(result_path))
    for path, digest in plan['source_sha256'].items():
        pin(path, digest)
    check('shallow:original-failed-receipt-retained', result['original_failure_retained'] == 'validation/flybody-habitat-results.json'
          and result['original_failure_receipt_sha256'] == sha(ROOT/result['original_failure_retained']))
    check('shallow:zero-integrated-steps', result['physics_steps'] == result['policy_advances'] == 0)
    check('shallow:sampled-live-hashes-identical', result['sampled_state_before'] == result['sampled_state_after'])
    check('shallow:nine-full-native-arrays-identical', result['native_arrays_before'] == result['native_arrays_after']
          and result['native_array_names'] == READONLY_FIELDS)
    for key, values in result['native_arrays_before'].items():
        array = np.asarray(values, np.float64)
        check('shallow:raw-native-hash:' + key, hashlib.sha256(array.tobytes()).hexdigest() == result['sampled_state_before']['arrays'][key])
        if key in initial:
            exact('shallow:original-initial:' + key, array, initial[key])
    exact('shallow:actual-initial-actor', np.asarray(result['initial_actor_values_f32'], np.float32), initial_actor)
    check('shallow:initial-actor-hash', hashlib.sha256(np.asarray(result['initial_actor_values_f32'], np.float32).tobytes()).hexdigest()
          == result['sampled_state_before']['actor'] == initial['actor_input_sha256'])
    check('shallow:same-compiled-metadata', result['metadata'] == original_case['metadata'])
    summaries = []
    for i, probe in enumerate(result['probes']):
        label = 'shallow:' + probe['wall']
        axis, side = i//2, (-1 if i%2 == 0 else 1)
        wall = walls[probe['wall']]
        assert probe['axis'] == axis and probe['outward_sign'] == side and probe['compiled_wall_geom_id'] == wall['compiled_geom_id']
        original_probe = original_case['detached_contact_probes']['probes'][i]
        exact(label + ':original-upper-bracket-translation', probe['upper_translation_cm'], original_probe['root_translation_cm'])
        check(label + ':original-bracket-evidence', not initial['habitat']['wall_contacts'] and original_probe['active_count'] > 0)
        low, high = 0., 1.
        history = probe['bisection_history']
        assert len(history) == plan['bisection_iterations'] == 40
        for j, step in enumerate(history):
            mid = (low+high)/2
            assert step['iteration'] == j and step['fraction'] == mid
            if step['target_active_contacts']:
                assert step['min_target_distance_mm'] is not None and step['min_target_distance_mm'] <= 0.
                high = mid
            else:
                assert step['min_target_distance_mm'] is None
                low = mid
        exact(label + ':all-40-bisection-branches', probe['final_bracket'], [low, high])
        delta = np.array(probe['upper_translation_cm'])*high
        delta[axis] += side*plan['additional_translation_mm']/10
        exact(label + ':frozen-extra-translation', probe['root_translation_cm'], delta)
        qpos = np.array(initial['qpos']); adr = probe['qpos_address']; qpos[adr:adr+2] += delta
        exact(label + ':translated-qpos', probe['qpos'], qpos)
        exact(label + ':qvel-unchanged', probe['qvel'], initial['qvel'])
        check(label + ':zero-native-time', probe['native_time_s'] == 0.)
        contacts = contacts_review(label, [probe['sample']], walls)
        target = [(c, normal) for _, c, normal in contacts if c['wall'] == probe['wall'] and c['active']]
        normals = [normal.tolist() for c, normal in target]
        exact(label + ':reported-normal-directions', probe['inward_normals_world'], normals)
        check(label + ':all-target-normals-inward', all(side*normal[axis] < 0. for c, normal in target))
        total = np.sum([c['force_world_dyne_on_fly'] for c, normal in target], axis=0)
        normal_force = np.sum([np.asarray(normal)*c['local_force_torque_dyne_dyne_cm'][0] for c, normal in target], axis=0)
        tangent_force = total - normal_force
        close(label + ':summed-world-force', total, probe['summed_force_world_dyne_on_fly'], 1e-10)
        plane = side*[15., 12.][axis]
        check(label + ':inner-plane-coordinate', probe['inner_plane_mm'] == plane)
        max_plane_error = max(abs(c['position_mm'][axis]-plane) for c, normal in target)
        min_distance = min(c['dist_mm'] for c, normal in target)
        check(label + ':shallow-inner-face-positions', max_plane_error <= plan['inner_plane_distance_tolerance_mm']
              and -plan['maximum_penetration_mm'] <= min_distance <= 0.)
        inward = bool(side*total[axis] < 0.)
        check(label + ':active-count-and-recorded-net-gate', len(target) == probe['active_target_count']
              and result['checks'][probe['wall']+'_active_inward_force'] == inward)
        summaries.append(dict(wall=probe['wall'], active_target_contacts=len(target), net_force_inward=inward,
            summed_world_force_dyne=total.tolist(), normal_component_world_dyne=normal_force.tolist(),
            tangent_component_world_dyne=tangent_force.tolist(),
            net_axis_outward_dyne=float(side*total[axis]), normal_axis_outward_dyne=float(side*normal_force[axis]),
            tangent_axis_outward_dyne=float(side*tangent_force[axis]),
            minimum_contact_distance_mm=min_distance, maximum_inner_plane_error_mm=max_plane_error,
            contact_positions_mm=[c['position_mm'] for c, normal in target],
            final_translation_cm=delta.tolist()))
    failed = [k for k, value in result['checks'].items() if not value]
    check('shallow:two-failed-y-force-gates-retained', result['passed'] is False and result['check_count'] == 31
          and failed == ['habitat_wall_y_neg_active_inward_force', 'habitat_wall_y_pos_active_inward_force'])
    return dict(producer_validation_passed=False, producer_check_count=31, producer_failed_gates=failed,
                probes=summaries, bisection_iterations_verified=160,
                limits='Final saved contact forces/normals and arithmetic are independently checked. Intermediate forward states were not retained, so bisection contact counts are recorded outcomes rather than independently recomputed geometry. Normal/tangent decomposition is algebra on fixed contacts, not frictionless counterfactual dynamics.')


def main():
    if OUT.exists():
        raise FileExistsError('Preserve completed independent review')
    report = dict(schema=1, started_utc=datetime.now(timezone.utc).isoformat(), reviewer_sha256=sha(__file__),
                  scope='Independent source inspection, saved native states/actor arrays/contact geometry and pure floor-contact predicate; no physics, policy or neural execution.',
                  cases=[], simulation_rerun=False)
    try:
        plan_path = ROOT / 'validation/flybody-habitat-execution-plan.json'
        plan = read(plan_path)
        result_path = ROOT / 'validation/flybody-habitat-results.json'
        result = read(result_path)
        report['plan_sha256'] = sha(plan_path)
        check('frozen-execution-plan', sha(plan_path) == PLAN_HASH and result['plan_sha256'] == PLAN_HASH)
        for name, expected in plan['source_sha256'].items():
            pin(name, expected)
        pin(plan['baseline']['path'], plan['baseline']['sha256'])
        pin(str(result_path.relative_to(ROOT)), sha(result_path))
        for name, expected in result['artifacts'].items():
            pin(name, expected)
        manifest = read(ROOT / 'validation/flybody-source-manifest.json')
        for item in manifest['files']:
            assert sha(ROOT / 'data/raw/flybody/source' / item['path']) == item['sha256']
        check('all-upstream-source-and-asset-files', True, files=len(manifest['files']))
        acquisition = read(ROOT / 'validation/flybody-walking-acquisition.json')
        for item in acquisition['members']:
            assert sha(ROOT / item['local_path']) == item['sha256']
        check('all-frozen-policy-members', True, members=len(acquisition['members']))
        states, arrays = {}, {}
        case_names = ['frozen_default', 'new_default', 'rolling_prefix', 'habitat_wall_push', 'offset_geometry']
        check('all-five-planned-cases', list(result['cases']) == case_names)
        lengths = dict(frozen_default=1001, new_default=1001, rolling_prefix=251, habitat_wall_push=385, offset_geometry=1)
        for name in case_names:
            case = result['cases'][name]
            folder = ROOT / result['data_directory']
            original_case = read(folder / (name + '.json'))
            # Summarizer adds mismatch lists only to copies of case receipts.
            check(name + ':case-receipt-preserved', all(case[k] == v for k, v in original_case.items()))
            assert case['operational_error'] is None and case['plan_sha256'] == PLAN_HASH
            with gzip.open(folder / (name + '-states.jsonl.gz'), 'rt') as f:
                rows = []
                for line in f:
                    assert line.endswith('\n')
                    rows.append(json.loads(line))
            with np.load(folder / (name + '-arrays.npz')) as z:
                arr = {k: z[k] for k in z.files}
            states[name], arrays[name] = rows, arr
            n = lengths[name]
            check(name + ':complete-sample-count', len(rows) == case['samples'] == n and case['completed_control_intervals'] == n-1)
            exact(name + ':consecutive-control-ticks', arr['tick'], np.arange(n))
            close(name + ':native-clock', arr['native_time_s'], np.arange(n)*.002)
            check(name + ':endpoint-receipt-exact', rows[-1] == case['endpoint'])
            for key in ARRAY_FIELDS + ['tick', 'native_time_s']:
                exact(name + ':journal-array:' + key, [r[key] for r in rows], arr[key])
            check(name + ':finite-raw-arrays', all(np.isfinite(a).all() for a in arr.values()) and all(r['finite'] for r in rows))
            check(name + ':warnings-zero', not arr['warnings'].any())
            actor = arr['actor']
            check(name + ':actual-actor-layout', actor.shape == (n, 741) and actor.dtype == np.dtype('<f4')
                  and case['actor_keys'] == list(case['actor_shapes']) and sum(np.prod(s) for s in case['actor_shapes'].values()) == 741)
            check(name + ':actual-actor-hashes', all(hashlib.sha256(a.tobytes()).hexdigest() == r['actor_input_sha256'] for a, r in zip(actor, rows)))
            assert rows[0]['command'] == dict(speed_mm_s=0., yaw_rad_s=0., policy_enabled=False, behavior='rest')
            lo = np.array(case['metadata']['action_minimum'], np.float32)
            hi = np.array(case['metadata']['action_maximum'], np.float32)
            for i, row in enumerate(rows[1:], 1):
                on = name not in ('frozen_default', 'new_default') or i-1 < 300 or i-1 >= 600
                assert row['command'] == dict(speed_mm_s=20. if on else 0., yaw_rad_s=0., policy_enabled=on, behavior='walk' if on else 'rest')
                canonical = np.array(row['canonical_action'], np.float32)
                expected = lo + np.float32(.5)*(np.clip(canonical, -1, 1)+1)*(hi-lo) if on else np.r_[np.ones(6, np.float32), np.zeros(53, np.float32)]
                assert np.array_equal(expected, row['native_action'])
                assert np.max(abs(np.array(row['target_pose_cm_quat']) - np.array(rows[i-1]['target_pose_cm_quat']) - np.array([.004 if on else 0., 0, 0, 0, 0, 0, 0]))) < 1e-12
            check(name + ':commands-native-action-map-and-integrated-targets', True)
            qacc_error, reference_error = [], []
            for row in rows:
                gd = row['guard_diagnostics']
                qacc_error.append(abs(np.linalg.norm(row['qacc']) - gd['qacc_norm']))
                reference_error.append(abs(np.linalg.norm(np.array(row['target_pose_cm_quat'][:3])-row['pose_cm_quat'][:3])-gd['reference_error_cm']))
                assert np.isfinite(list(gd.values())).all()
            check(name + ':qacc-guard-recomputed', max(qacc_error) < 1e-9, maximum_absolute_error=max(qacc_error))
            check(name + ':reference-error-recomputed', max(reference_error) < 1e-10, maximum_absolute_error=max(reference_error))
            if case['config']['reference_mode'] == 'rolling':
                check(name + ':rolling-reference-and-clock', all(r['reference_qpos_shape'] == [66, 7] and r['reference_qvel_shape'] == [66, 6]
                    and r['source_control_tick'] == r['tick'] and r['reference_buffer_origin'] == max(0, r['tick']-1) for r in rows))
            if case['config']['habitat'] is None:
                check(name + ':default-habitat-absent', 'habitat' not in case['metadata'] and all('habitat' not in r for r in rows))
            else:
                walls = geometry_review(name, case)
                for row in rows:
                    h = row['habitat']
                    xy = np.array(row['pose_cm_quat'][:2])*10
                    center = np.array(case['config']['habitat']['center_mm'])
                    half = np.array(case['config']['habitat']['inner_size_mm'])/2
                    clearance = np.r_[xy-center+half, center+half-xy]
                    assert np.array_equal(xy, h['root_position_mm'])
                    assert np.max(abs(clearance - h['root_clearance_mm_xneg_yneg_xpos_ypos'])) < 1e-12
                    assert h['root_inside_inner_xy'] == bool((clearance >= 0).all())
                check(name + ':all-root-containment-values-recomputed', True)
                contacts_review(name, [r['habitat'] for r in rows], walls)
            report['cases'].append(dict(case=name, saved_samples=n, native_intervals_reached=n-1, actor_values=actor.size,
                                        endpoint_time_s=rows[-1]['native_time_s'], native_failure=case.get('native_failure')))
        for a, b, count, label in [('frozen_default', 'new_default', 1001, 'default'), ('rolling_prefix', 'habitat_wall_push', 251, 'precontact')]:
            check(label + ':actor-key-order-and-shapes', result['cases'][a]['actor_keys'] == result['cases'][b]['actor_keys']
                  and result['cases'][a]['actor_shapes'] == result['cases'][b]['actor_shapes'])
            exact(label + ':all-actual-actor-values-exact', arrays[a]['actor'][:count], arrays[b]['actor'][:count])
            check(label + ':every-legacy-state-field-exact', all(all(row[k] == other[k] for k in row)
                  for row, other in zip(states[a][:count], states[b][:count])))
        wall_case = result['cases']['habitat_wall_push']
        rows = states['habitat_wall_push']
        walls = {w['geom']: w for w in wall_case['geometry']['metadata']['walls']}
        check('precontact:no-wall-records', all(not r['habitat']['wall_contacts'] for r in rows[:251]))
        all_contacts = [(i, c) for i, r in enumerate(rows) for c in r['habitat']['wall_contacts']]
        active = [(i, c) for i, c in all_contacts if c['active'] and np.linalg.norm(c['force_world_dyne_on_fly']) > 0.]
        derived = dict(end_time_s=rows[-1]['native_time_s'], endpoint_root_mm=rows[-1]['habitat']['root_position_mm'],
            first_contact_time_s=rows[all_contacts[0][0]]['native_time_s'], first_active_force_time_s=rows[active[0][0]]['native_time_s'],
            minimum_contact_distance_mm=min(c['dist_mm'] for i, c in all_contacts),
            maximum_contact_force_dyne=max(float(np.linalg.norm(c['force_world_dyne_on_fly'])) for i, c in all_contacts),
            active_contact_samples=len(set(i for i, c in active)), source_terminated=rows[-1]['source_terminated'],
            endpoint_guard_diagnostics=rows[-1]['guard_diagnostics'], native_failure=wall_case['native_failure'])
        check('wall-trial:all-outcome-fields-recomputed', all(result['wall_trial_outcome'][k] == v for k, v in derived.items()))
        check('wall-trial:root-contained-at-all-saved-endpoints', all(r['habitat']['root_inside_inner_xy'] for r in rows))
        check('wall-trial:only-positive-x-wall-contact', {c['wall'] for i, c in all_contacts} == {'habitat_wall_x_pos'})
        check('wall-trial:source-failure-kept', wall_case['native_failure']['attempted_interval'] == 383
              and wall_case['native_failure']['worker_failed'] and not any(r['source_terminated'] for r in rows[:-1]) and rows[-1]['source_terminated'])
        guard = rows[-1]['guard_diagnostics']
        check('wall-trial:reference-threshold-alone-crossed', guard['reference_error_cm'] > .3
              and guard['qacc_norm'] < 1e14 and guard['linear_cm_s'] < 50 and guard['angular_rad_s'] < 200
              and max(r['guard_diagnostics']['reference_error_cm'] for r in rows[:-1]) <= .3)
        check('wall-trial:failure-latch-source-receipt', wall_case['failure_latch']['sampled_state_unchanged']
              and 'reset explicitly' in wall_case['failure_latch']['message'])
        probes = wall_case['detached_contact_probes']
        readonly_review('detached-probes', probes, rows[0])
        probe_outcomes = []
        for i, probe in enumerate(probes['probes']):
            axis, side = i//2, (-1 if i%2 == 0 else 1)
            delta = np.array(probe['root_translation_cm'])
            expected_delta = np.zeros(2); expected_delta[axis] = side * ([1.5, 1.2][axis]-.02)
            close(probe['wall'] + ':prespecified-deep-probe-translation', delta, expected_delta, 1e-13)
            qpos = np.array(rows[0]['qpos']); adr = probe['qpos_address']; qpos[adr:adr+2] += delta
            exact(probe['wall'] + ':probe-qpos-only-translated-root', probe['qpos'], qpos)
            exact(probe['wall'] + ':probe-qvel-unchanged', probe['qvel'], rows[0]['qvel'])
            check(probe['wall'] + ':zero-step-clock', probe['native_time_s'] == 0. and probe['policy_steps'] == 0)
            converted = contacts_review('detached:' + probe['wall'], [probe['sample']], walls)
            relevant = [c for _, c, normal in converted if c['wall'] == probe['wall'] and c['active']]
            force = np.sum([c['force_world_dyne_on_fly'] for c in relevant], axis=0)
            close(probe['wall'] + ':summed-contact-force', force, probe['summed_force_world_dyne_on_fly'], 1e-9)
            inward = bool(side * force[axis] < 0.)
            check(probe['wall'] + ':reported-probe-status-correct', len(relevant) == probe['active_count'] and inward == probe['inward_normal_force'])
            normal_axes = [float(side * normal[axis]) for _, c, normal in converted if c['active']]
            probe_outcomes.append(dict(wall=probe['wall'], active_contacts=len(relevant), inward_force=inward,
                summed_force_world_dyne_on_fly=force.tolist(), minimum_distance_mm=min(c['dist_mm'] for c in relevant),
                normal_axes_with_wall_outward_sign=normal_axes))
        check('failed-positive-x-deep-probe-preserved', [p['wall'] for p in probe_outcomes if not p['inward_force']] == ['habitat_wall_x_pos'])
        reset = wall_case['reset']
        initial = {k: v for k, v in rows[0].items() if k != 'guard_diagnostics'}
        check('reset:raw-initial-state-exact', reset['initial_state'] == initial and reset['initial_state_exact'])
        check('reset:actor-hash-and-metadata-receipts', reset['initial_state']['actor_input_sha256'] == rows[0]['actor_input_sha256']
              and reset['actual_actor_exact'] and reset['metadata_geometry_exact'] and reset['failed_cleared'] and reset['time_s'] == 0.)
        check('reset:retained-endpoint', reset['retained_endpoint_equal'])
        check('render:all-three-source-nonmutation-receipts', set(wall_case['endpoint_render']) == {'overview', 'follow', 'side'}
              and all(v['sampled_state_unchanged'] for v in wall_case['endpoint_render'].values()))
        floor_only_contract()
        failed_gates = [k for k, v in result['checks'].items() if not v]
        check('producer-status-faithfully-failed', result['check_count'] == 65 and result['passed'] is False
              and failed_gates == ['all_four_wall_probes_inward_contact'])
        shallow = shallow_review(wall_case, rows[0], arrays['habitat_wall_push']['actor'][0], walls)
        report.update(passed=True, producer_validation_passed=False, producer_failed_gates=failed_gates,
                      wall_trial=derived, deep_probe_outcomes=probe_outcomes, shallow_addendum=shallow)
        report['limits'] = [
            'Independent-review passed means saved evidence agrees with source and claims, not that the producer validation passed: its positive-x deep-overlap probe fails.',
            'Controller trial stops at 0.768s after native reference-error termination, with no avoidance or sustained-control success claim.',
            'Root containment only at saved2ms endpoints; finite-height open top does not establish full-mesh or indefinite containment, and soft penetration is observed.',
            'Contact frame/local forces are retained for independent world-force arithmetic; efc_address is not retained, so active flags are partly grounded in source inspection.',
            'Detached probe before/after hashes cover nine named native arrays, actor hash, cached observations and clock, not every native model/data field.',
            'Render and failure-latch nonmutation are producer boolean receipts; their before/after hash dictionaries were not retained for independent equality reconstruction.',
            'Pure floor-only resource predicate checked in isolation; native trials do not run host ingestion physiology or wall-avoidance neural behavior.',
            'Compiled metadata and frozen source establish geometry; the complete compiled MuJoCo model was not archived for independent native recompilation.',
            'Air/odor transport remains unbounded; female-derived body and pretrained policy remain uncalibrated as male morphology or physiology.'
        ]
    except Exception as exc:
        report.update(passed=False, error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    report.update(completed_utc=datetime.now(timezone.utc).isoformat(), checks=CHECKS, check_count=len(CHECKS), inputs=PINS)
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('passed', 'check_count')}, indent=2), flush=True)
    if not report['passed']:
        print(report['traceback'], flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
