"""Recompute frozen rolling-reference gates from saved native traces."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np

PLAN = Path('validation/flybody-persistent-plan.json')
RESULT = Path('validation/flybody-persistent-experiment.json')
OUTPUT = Path('validation/flybody-persistent-validation.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan, report = json.loads(PLAN.read_text()), json.loads(RESULT.read_text())
    checks = []
    def check(name, passed, detail=None):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))
    check('plan_identity', report['plan_sha256'] == digest(PLAN))
    for path, expected in plan['files'].items():
        check('unchanged:' + path, digest(path) == expected)
    check('all_trials_finished', report['complete'] and len(report['trials']) == 4)
    traces = {}
    trials = {row['case']: row for row in report['trials']}
    for case, row in trials.items():
        check(case + ':has_trace', 'trace' in row, row.get('failure'))
        if 'trace' not in row:
            continue
        check(case + ':trace_hash', digest(row['trace']) == row['trace_sha256'])
        trace = traces[case] = np.load(row['trace'])
        long = case.endswith('12')
        expected = 6001 if long else 1001
        check(case + ':complete_without_failure', row['failure'] is None and len(trace['tick']) == expected, row.get('failure'))
        check(case + ':native_clock', np.max(abs(trace['native_time_s'] - trace['tick'] * .002)) < 1e-10)
        check(case + ':task_counter', np.array_equal(trace['tick'], trace['task_counter']))
        check(case + ':uninterrupted_ticks', np.array_equal(trace['tick'], np.arange(len(trace['tick']))))
        physical = ('qpos', 'qvel', 'qacc', 'act', 'ctrl', 'native_action', 'canonical_action', 'actor')
        check(case + ':finite', bool(trace['finite'].all()) and all(np.isfinite(trace[key]).all() for key in physical))
        check(case + ':warnings_zero', not np.any(trace['warnings']))
        check(case + ':no_source_termination', not np.any(trace['source_terminated']))
        check(case + ':physical_guard_probes', row['guards'] == dict(baseline=False, qacc_above=True, velocimeter_above=True, gyro_above=True, reference_above=True), row['guards'])
        check(case + ':guards_preserved_in_trace', np.max(trace['source_linvel_cm_s']) <= 50 and np.max(trace['source_angvel_rad_s']) <= 200 and np.max(trace['reference_error_cm']) <= .3 and np.max(np.linalg.norm(trace['qacc'], axis=1)) <= 1e14)
        check(case + ':actor_shape', trace['actor'].shape == (len(trace['tick']), 741) and row['actor_shapes']['walker/ref_displacement'] == [65, 3] and row['actor_shapes']['walker/ref_root_quat'] == [65, 4])
        check(case + ':native_clocks_config', row['native_clock_max_error_s'] < 1e-10 and row['source']['versions']['mujoco'] == '3.2.7')
        off = ~trace['command_on'][1:]
        native = trace['native_action'][1:][off]
        check(case + ':off_neutral_stance', np.array_equal(native[:, :6], np.ones_like(native[:, :6])) and not np.any(native[:, 6:]))
        target_expected = trace['target_pose_cm_quat'][:-1].copy()
        target_expected[:, 0] += trace['command_on'][1:] * .004
        check(case + ':continuous_integrated_target', np.array_equal(trace['target_pose_cm_quat'][1:], target_expected))
        offset = 0
        for name in row['actor_keys']:
            size = int(np.prod(row['actor_shapes'][name]))
            if name == 'walker/ref_displacement':
                actor_reference = trace['actor'][1:, offset:offset + size].reshape(-1, 65, 3)
            offset += size
        preview_span = np.linalg.norm(actor_reference[:, -1] - actor_reference[:, 0], axis=1)
        check(case + ':actual_actor_current_command_span', np.allclose(preview_span, trace['command_on'][1:] * .256, rtol=0, atol=1e-6))
        check(case + ':actual_actor_current_target_error', np.allclose(np.linalg.norm(actor_reference[:, 0], axis=1), trace['reference_error_cm'][:-1], rtol=0, atol=1e-7))
        if case.startswith('rolling'):
            check(case + ':fixed_storage', np.array_equal(trace['ref_shape'], np.tile([66, 7], (len(trace['tick']), 1))) and row['task_episode_steps'] is None and row['composer_time_limit'] == 'infinite')
            check(case + ':actor_preview_causal_storage', row['actor_shapes']['walker/ref_displacement'][0] == 65)
        if long:
            check(case + ':crosses_original_10s_limit', trace['native_time_s'][-1] > 10 and np.any((trace['native_time_s'][:-1] <= 10) & (trace['native_time_s'][1:] > 10)), float(trace['native_time_s'][-1]))
    parity = {}
    if all(k in traces for k in ('bounded_parity', 'rolling_parity')):
        left, right = traces['bounded_parity'], traces['rolling_parity']
        for key in ('actor', 'canonical_action', 'native_action', 'qpos', 'qvel', 'qacc', 'act', 'ctrl', 'target_pose_cm_quat', 'native_time_s'):
            equal = np.array_equal(left[key], right[key])
            err = float(np.max(abs(left[key] - right[key]))) if left[key].shape == right[key].shape else None
            parity[key] = dict(bitwise_equal=equal, max_absolute_error=err)
            check('parity:' + key, equal, err)
        a, b = trials['bounded_parity'], trials['rolling_parity']
        check('parity:actor_keys_and_shapes', a['actor_keys'] == b['actor_keys'] and a['actor_shapes'] == b['actor_shapes'])
        check('parity:all_exposed_numeric_model_arrays', a['compiled_numeric_arrays'] == b['compiled_numeric_arrays'], len(a['compiled_numeric_arrays']))
        for key in ('cached_displacement', 'cached_quaternion'):
            check('parity:' + key + ':first64', np.array_equal(left[key][:, :64], right[key][:, :64]))
            parity[key] = dict(first64_bitwise_equal=bool(np.array_equal(left[key][:, :64], right[key][:, :64])),
                final_row_different_samples=int(np.count_nonzero(np.any(left[key][:, -1] != right[key][:, -1], axis=1))),
                final_row_max_absolute_difference=float(np.max(abs(left[key][:, -1] - right[key][:, -1]))))
        # Source model is the comparison target; same plan inputs must preserve
        # worker provenance, although this prototype's bookkeeping is separate.
        check('parity:source_and_weights', a['source'] == b['source'])
    windows = {}
    for case in ('rolling_rest12', 'rolling_switch12'):
        if case not in traces:
            continue
        trace = traces[case]
        times = trace['native_time_s'][1:]
        pose = trace['pose_cm_quat'][:, :2] * 10
        speed = np.linalg.norm(np.diff(pose, axis=0), axis=1) / .002
        requested = [('stop', .3, 12.)] if case.endswith('rest12') else [
            ('stop', .85, 1.2), ('stop', 3.25, 3.6), ('stop', 6.25, 6.6), ('stop', 9.25, 10.6),
            ('resume', 1.5, 3.), ('resume', 3.9, 6.), ('resume', 6.9, 9.), ('resume', 10.9, 12.)]
        rows = []
        for kind, start, end in requested:
            complete = trace['native_time_s'][-1] >= end - 1e-10
            mask = (times >= start - 1e-10) & (times <= end + 1e-10)
            samples = np.flatnonzero((trace['native_time_s'] >= start - 1e-10) & (trace['native_time_s'] <= end + 1e-10))
            median = float(np.median(speed[mask])) if mask.any() else None
            drift = float(np.linalg.norm(pose[samples[-1]] - pose[samples[0]])) if len(samples) else None
            passed = complete and median is not None and (median <= 1 and drift <= .5 if kind == 'stop' else 16 <= median <= 24)
            item = dict(kind=kind, window_s=[start, end], complete=bool(complete), median_raw_chord_speed_mm_s=median, net_displacement_mm=drift, passed=bool(passed), diagnostic_only=case.endswith('rest12'))
            rows.append(item)
            if not item['diagnostic_only']:
                check(case + ':' + kind + ':' + str(start), passed, item)
        windows[case] = rows
    output = dict(passed=all(row['passed'] for row in checks), plan_sha256=digest(PLAN),
        result_sha256=digest(RESULT), checker_sha256=digest(__file__),
        checks=checks, parity=parity, windows=windows,
        runtime_promoted=False, full_brain_tested=False)
    OUTPUT.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print('Checks', len(checks), 'passed', sum(row['passed'] for row in checks))
    for row in checks:
        if not row['passed']:
            print('FAIL', row['name'], row['detail'])
    if not output['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
