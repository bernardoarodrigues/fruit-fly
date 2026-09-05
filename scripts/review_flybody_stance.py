"""Independent saved-trace stance review; source initialization, never rollout.

Run using tmp/flybody-env/bin/python -m scripts.review_flybody_stance.
Does not import the experiment, its checker, or its numerical metric helpers.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d

REPO = Path('/tmp/fruit-fly-research-flybody')
OUT = Path('validation/flybody-stance-independent-review.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def independent_window(raw, start, stop):
    """Scalar quaternion heading and unsmoothed position differences."""
    q = raw['pose'][round(start / .002):round(stop / .002) + 1]
    speed = np.linalg.norm(np.diff(q[:, :2], axis=0), axis=1) * 10 / .002
    quat = q[:, 3:] / np.linalg.norm(q[:, 3:], axis=1)[:, None]
    w, x, y, z = quat.T
    heading = np.unwrap(np.arctan2(2 * (x * y + w * z), 1 - 2 * (y*y + z*z)))
    yaw = np.diff(gaussian_filter1d(heading, 3.75, mode='reflect')) / .002 * 180 / np.pi
    return {'speed_median_mm_s': float(np.median(speed)),
            'absolute_yaw_median_deg_s': float(np.median(np.abs(yaw))),
            'net_displacement_mm': float(np.linalg.norm(q[-1, :2] - q[0, :2]) * 10)}


def main():
    plan_path = Path('validation/flybody-stance-plan.json')
    result_path = Path('validation/flybody-stance-experiment.json')
    plan, result = read(plan_path), read(result_path)
    dependencies = {
        'scripts/experiment_flybody_stance.py': 'script_sha256',
        'validation/flybody-stance-actuator-audit.json': 'actuator_audit_sha256',
        'scripts/compare_flybody_motor.py': 'comparison_script_sha256',
        'scripts/benchmark_freewalking.py': 'metrics_script_sha256',
        'validation/flybody-motor-comparison.json': 'baseline_results_sha256',
        'validation/flybody-source-manifest.json': 'source_manifest_sha256',
        'validation/flybody-walking-acquisition.json': 'policy_receipt_sha256',
        'validation/flybody-inference-requirements.lock': 'requirements_lock_sha256',
    }
    for path, key in dependencies.items():
        assert sha(path) == plan[key], path
    assert result['complete'] and result['plan_sha256'] == sha(plan_path)
    assert result['script_sha256'] == plan['script_sha256']
    source = read('validation/flybody-source-manifest.json')
    for row in source['files']:
        assert sha(REPO / row['path']) == row['sha256']
    for row in read('validation/flybody-walking-acquisition.json')['members']:
        assert sha(row['local_path']) == row['sha256']
    evidence_paths = [str(plan_path), str(result_path), *dependencies,
                      'scripts/audit_flybody_stance_actuators.py',
                      'scripts/check_flybody_stance.py',
                      'scripts/plot_flybody_stance.py',
                      'validation/flybody-stance-validation.json',
                      'validation/flybody-stance-failure-diagnostic.json',
                      'validation/flybody-stance-experiment.png',
                      'docs/flybody-stance-experiment.md']
    hashes = {p: sha(p) for p in evidence_paths}
    sys.path.insert(0, str(REPO))
    import mujoco
    from flybody.fly_envs import walk_imitation
    from dm_control.mujoco import engine

    # This constructs and resets the original source model once. No env.step,
    # physics.step, mj_step, or advancing state integration is called here.
    env = walk_imitation(random_state=np.random.RandomState(11))
    env.reset()
    try:
        m, d = env.physics.model, env.physics.data
        assert d.time == 0
        assert m.opt.integrator == mujoco.mjtIntegrator.mjINT_EULER
        assert m.opt.timestep == plan['physics_dt_s'] == .0002
        assert env.control_timestep() == plan['control_dt_s'] == .002
        spec = env.action_spec()
        names = spec.name.split()
        ids = np.array([m.name2id('walker/' + n, 'actuator') for n in names])
        assert len(names) == len(set(ids)) == 59 and np.all(ids >= 0)
        assert np.array_equal(ids, np.r_[np.arange(53, 59), np.arange(53)])
        lo, hi = spec.minimum.astype(np.float32), spec.maximum.astype(np.float32)
        recorded_audit = read('validation/flybody-stance-actuator-audit.json')['rows']
        mappings = []
        length_matrix = np.zeros((m.nq, 59))
        for ai, (name, aid) in enumerate(zip(names, ids)):
            old = recorded_audit[ai]
            assert (old['action_index'], old['name'], old['compiled_actuator_id']) == (ai, name, aid)
            for key, actual in [('gain', m.actuator_gainprm[aid, :3]),
                                ('bias', m.actuator_biasprm[aid, :3]),
                                ('gear', m.actuator_gear[aid])]:
                np.testing.assert_array_equal(old[key], actual)
            trn = int(m.actuator_trntype[aid])
            assert old['trntype'] == trn
            assert np.array_equal(m.actuator_gear[aid], [1, 0, 0, 0, 0, 0])
            assert m.actuator_dyntype[aid] == mujoco.mjtDyn.mjDYN_FILTER
            assert m.actuator_actadr[aid] >= 0 and not m.actuator_actlimited[aid]
            coordinate = []
            if trn == mujoco.mjtTrn.mjTRN_JOINT:
                joints = [(int(m.actuator_trnid[aid, 0]), 1.)]
            elif trn == mujoco.mjtTrn.mjTRN_TENDON:
                tid = int(m.actuator_trnid[aid, 0])
                adr, num = m.tendon_adr[tid], m.tendon_num[tid]
                assert np.all(m.wrap_type[adr:adr+num] == mujoco.mjtWrap.mjWRAP_JOINT)
                joints = [(int(m.wrap_objid[k]), float(m.wrap_prm[k])) for k in range(adr, adr+num)]
            else:
                assert trn == mujoco.mjtTrn.mjTRN_BODY and ai < 6
                joints = []
            for jid, coefficient in joints:
                assert m.jnt_type[jid] == mujoco.mjtJoint.mjJNT_HINGE
                qadr = int(m.jnt_qposadr[jid])
                length_matrix[qadr, ai] += coefficient
                coordinate.append({'joint': m.id2name(jid, 'joint'), 'qpos_index': qadr, 'coefficient': coefficient})
            if ai >= 6:
                assert m.actuator_gaintype[aid] == mujoco.mjtGain.mjGAIN_FIXED
                assert m.actuator_biastype[aid] == mujoco.mjtBias.mjBIAS_AFFINE
                gain = m.actuator_gainprm[aid, 0]
                assert gain > 0
                np.testing.assert_array_equal(m.actuator_biasprm[aid, :3], [0, -gain, 0])
            mappings.append({'action_index': ai, 'name': name, 'compiled_id': int(aid),
                             'transmission_type': trn, 'length_terms': coordinate,
                             'activation_tau_s': float(m.actuator_dynprm[aid, 0]),
                             'control_range': m.actuator_ctrlrange[aid].tolist()})
        assert np.count_nonzero(m.actuator_trntype[ids] == 0) == 45
        assert np.count_nonzero(m.actuator_trntype[ids] == 3) == 8
        assert np.count_nonzero(m.actuator_trntype[ids] == 5) == 6
        tau = m.actuator_dynprm[ids, 0]
        np.testing.assert_array_equal(tau, np.r_[np.full(6, .007), np.full(53, .01)])
        assert np.all(m.actuator_ctrllimited[ids])
        floor_ids = [m.name2id(g.full_identifier, 'geom') for g in env.task._arena.ground_geoms]
        assert all(i >= 0 for i in floor_ids)
        floors = {str(i): m.id2name(i, 'geom') for i in floor_ids}
        body_weight = float(env.task.walker.weight)
        decay = (1 - m.opt.timestep / tau)**10
        control_bounds = m.actuator_ctrlrange[ids].copy()
        initial_activation = d.act[m.actuator_actadr[ids]].copy()
        assert d.time == 0
        env.close()
    finally:
        env.close()

    raw_by_key, trials = {}, []
    assert len(result['trials']) == 12
    assert {(r['variant'], r['assay']) for r in result['trials']} == {
        (v, a) for v in plan['variants'] for a in plan['assays']}
    for row in result['trials']:
        assert sha(row['trace']) == row['trace_sha256']
        with np.load(row['trace'], allow_pickle=False) as archive:
            raw = {k: archive[k] for k in archive.files}
        key = row['variant'], row['assay']
        raw_by_key[key] = raw
        n = len(raw['native_action'])
        assert raw['pose'].shape == (n+1, 7) and raw['native_action'].shape == (n, 59)
        assert all(np.isfinite(a).all() for a in raw.values())
        assert n == (613 if 'failure' in row else 1000)
        gate = np.zeros(n, bool)
        if row['assay'] != 'zero_start':
            gate[:300] = True
            if row['assay'] == 'walk_stop_resume':
                gate[600:] = True
        np.testing.assert_array_equal(raw['motor_enabled'], gate)
        np.testing.assert_allclose(np.diff(raw['target_pose'][:, :3], axis=0),
                                   np.c_[gate[:-1] * .004, np.zeros((n-1, 2))], rtol=0, atol=1e-12)
        np.testing.assert_array_equal(raw['target_pose'][:, 3:], np.tile([1, 0, 0, 0], (n, 1)))
        canonical = raw['shadow_canonical']
        policy_native = lo + np.float32(.5)*(np.clip(canonical, -1, 1)+1)*(hi-lo)
        used = np.ones(n, bool) if row['variant'] == 'policy_zero' else gate
        np.testing.assert_array_equal(raw['native_action'][used], policy_native[used])
        np.testing.assert_array_equal(raw['actuator_activation'][0], initial_activation)
        held = None
        if row['variant'] != 'policy_zero':
            assert len(row['captures']) == 1
            cap = row['captures'][0]
            edge = 0 if row['assay'] == 'zero_start' else 300
            assert cap['time_s'] == edge*.002
            previous = raw['native_action'][edge-1] if edge else np.zeros(59)
            measured = raw['actuator_length'][edge]
            np.testing.assert_array_equal(cap['last_native'], previous)
            np.testing.assert_array_equal(cap['measured_length'], measured)
            unc = {'last_target': previous, 'measured_length': measured,
                   'neutral_zero': np.zeros(59)}[row['variant']].copy()
            unc[:6] = 1
            held = np.clip(unc, lo, hi).astype(np.float32)
            np.testing.assert_array_equal(cap['unclipped'], unc)
            np.testing.assert_array_equal(np.asarray(cap['native'], np.float32), held)
            np.testing.assert_array_equal(raw['native_action'][~gate], np.tile(held, (sum(~gate), 1)))
            np.testing.assert_array_equal(held[:6], np.ones(6))
        computed_lengths = raw['qpos'] @ length_matrix
        length_error = float(np.max(np.abs(computed_lengths - raw['actuator_length'])))
        assert length_error < 1e-12
        # MuJoCo clamps each float32 submitted command to its compiled float64
        # native bounds before the source FILTER update. This matters at roundoff.
        effective = np.clip(raw['native_action'].astype(float), control_bounds[:, 0], control_bounds[:, 1])
        predicted_act = effective + (raw['actuator_activation'][:-1] - effective) * decay
        activation_error = float(np.max(np.abs(predicted_act - raw['actuator_activation'][1:])))
        assert activation_error < 1e-12
        windows = {}
        for name, (start, stop) in plan['windows'][row['assay']].items():
            if stop > n*.002:
                continue
            values = independent_window(raw, start, stop)
            if name == 'stop':
                passed = values['speed_median_mm_s'] <= 1 and values['net_displacement_mm'] <= .5
            else:
                passed = (16 <= values['speed_median_mm_s'] <= 24 and
                          values['absolute_yaw_median_deg_s'] <= plan['rules']['resume_absolute_yaw_ceiling_deg_s'])
            if 'windows' in row:
                old = row['windows'][name]
                for value, saved in [(values['speed_median_mm_s'], old['speed_mm_s']['median']),
                                     (values['absolute_yaw_median_deg_s'], old['absolute_yaw_deg_s']['median']),
                                     (values['net_displacement_mm'], old['net_displacement_mm'])]:
                    assert abs(value-saved) < 1e-8
                assert passed == old['pass']
            windows[name] = dict(values, passed=passed)
        physical = {'min_up_z': float(raw['up_z'][150:].min()),
                    'min_height_mm': float(raw['pose'][150:, 2].min()*10),
                    'unsupported_fraction': float(np.mean(raw['support_dyne'][150:].max(axis=1) <= 1e-8)),
                    'support_over_weight_mean': float(np.mean(raw['support_dyne'][150:].sum(axis=1))/body_weight)}
        if 'failure' not in row:
            for k, value in physical.items():
                assert abs(value-row['physical'][k]) < 1e-12
            passed = (physical['min_up_z'] >= .5 and physical['min_height_mm'] >= .5 and
                      physical['unsupported_fraction'] <= .01 and not any(row['physical']['warnings']))
            assert passed == row['physical_pass']
        trials.append({'variant': key[0], 'assay': key[1], 'trace_sha256': row['trace_sha256'],
                       'samples': n+1, 'reconstructed_duration_s': n*.002,
                       'max_transmission_length_error_native': length_error,
                       'max_activation_error_native': activation_error,
                       'gate_policy_latch_verified': True, 'all_retained_arrays_finite': True,
                       'physical_recomputed': physical, 'windows': windows,
                       'retained_failure': row.get('failure')})
    prefix_checks = {}
    for variant in plan['variants']:
        a, b = raw_by_key[variant, 'walk_stop'], raw_by_key[variant, 'walk_stop_resume']
        assert np.array_equal(a['qpos'][:601], b['qpos'][:601])
        for assay in ['walk_stop', 'walk_stop_resume']:
            np.testing.assert_array_equal(raw_by_key[variant, assay]['qpos'][:301], raw_by_key['policy_zero', assay]['qpos'][:301])
        prefix_checks[variant] = True
    zero = raw_by_key['last_target', 'zero_start']
    for v in ['measured_length', 'neutral_zero']:
        for field in zero:
            np.testing.assert_array_equal(zero[field], raw_by_key[v, 'zero_start'][field])
    decisions = {}
    for variant in plan['variants']:
        rows = [r for r in trials if r['variant'] == variant]
        passed = variant != 'policy_zero' and all(
            r['retained_failure'] is None and all(w['passed'] for w in r['windows'].values()) and
            next(x for x in result['trials'] if (x['variant'], x['assay']) == (r['variant'], r['assay']))['physical_pass']
            for r in rows)
        old = next(r for r in result['decisions'] if r['variant'] == variant)
        assert passed == old['all_declared_gates_pass'] and not old['runtime_promoted']
        decisions[variant] = passed
    failed = raw_by_key['last_target', 'walk_stop_resume']
    final_reference = failed['target_pose'][-1, :3] + [.004, 0, 0]
    failure = {'reference_distance_cm': float(np.linalg.norm(final_reference-failed['pose'][-1, :3])),
               'root_linear_speed_cm_s': float(np.linalg.norm(failed['qvel'][-1, :3])),
               'root_angular_speed_rad_s': float(np.linalg.norm(failed['qvel'][-1, 3:6]))}
    diagnostic = read('validation/flybody-stance-failure-diagnostic.json')
    assert failure['reference_distance_cm'] == diagnostic['source_reference_distance_cm'] > .3
    assert failure['root_linear_speed_cm_s'] == diagnostic['final_root_linear_speed_cm_s'] < 50
    assert failure['root_angular_speed_rad_s'] == diagnostic['final_root_angular_speed_rad_s'] < 200
    assert not result['runtime_changed'] and not result['biological_stance_claim']
    for p, value in hashes.items():
        assert sha(p) == value, f'Review input changed during inspection: {p}'
    for row in source['files']:
        assert sha(REPO / row['path']) == row['sha256']
    receipt = {
        'passed': True, 'scope': 'Independent scalar/array review of all frozen traces plus source initialization; no physics rerun, training, fitting, or runtime integration.',
        'reviewer_script_sha256': sha(__file__), 'reviewed_file_sha256': hashes,
        'source_commit': source['source_commit'], 'source_files_verified_count': len(source['files']),
        'versions': {k: importlib.metadata.version(k) for k in ['mujoco', 'dm-control', 'numpy', 'scipy']},
        'dm_control_engine_sha256': sha(engine.__file__),
        'seed_for_source_initialization': 11, 'source_model_time_after_initialization_s': 0,
        'physics_integration_calls': 0,
        'physics_step_s': .0002, 'control_step_s': .002, 'source_substeps_per_control': 10,
        'activation_equation': 'a_next = clamp(u) + (a - clamp(u)) * (1 - 0.0002/tau)^10; source Euler FILTER, tau adhesion0.007/position0.01s; float64 compiled control bounds',
        'exact_action_order_and_transmission_map': mappings, 'ground_geometry_ids': floors,
        'trials': trials, 'identical_until_command_edge': prefix_checks,
        'all_three_zero_start_holds_bitwise_identical': True,
        'recomputed_decisions': decisions, 'recomputed_failure_diagnostic': failure,
        'plot_visually_inspected': 'validation/flybody-stance-experiment.png',
        'limits': [
            'One deterministic state, speed, surface and stop phase. No biological stance or general robustness validation.',
            'Current actuator_length follows terminal mj_step1; raw actuator_force is preceding force-stage telemetry, not simultaneous with retained poststep activation/length.',
            'No native data.time series is retained; trace time is reconstructed from action count and compiled source steps.',
            'Ground contact forces were recomputed by source experiment using mj_forward on a detached data copy. This review checks IDs/code and saved aggregate gates, not an independent force solve.',
            'Support sums absolute world-vertical contact forces including artificial maximum adhesion; not net weight balance or physiological force evidence.',
            'Failure qacc/warnings unrecorded; reference-distance threshold explains termination but does not exclude simultaneous source conditions.',
            'Sampled 500Hz geometry/support and interval displacement speeds do not establish continuous-time extrema or continuous contact.',
            'Heading uses declared 7.5ms Gaussian with reflected window edges; displayed 11-sample speed median is cosmetic only.',
            'Source validator skips most failed-trace checks. This review includes its finite state, mapping, filter, command/latch and available stop window.',
        ],
    }
    OUT.write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'passed': True, 'trials': len(trials), 'decisions': decisions,
                      'max_length_error': max(r['max_transmission_length_error_native'] for r in trials),
                      'max_activation_error': max(r['max_activation_error_native'] for r in trials),
                      'receipt': str(OUT)}, indent=2))


if __name__ == '__main__':
    main()
