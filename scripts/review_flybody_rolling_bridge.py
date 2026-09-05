"""Read-only journal review; never imports or executes simulation/runtime code.

Reviewer authored the earlier standalone reference task, but did not author
the rolling bridge/runtime integration or its primary comparison checker.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/flybody-rolling-bridge'
PHYSICAL = ('qpos', 'qvel', 'qacc', 'act', 'ctrl', 'native_action', 'canonical_action',
            'target_pose_cm_quat', 'native_time_s', 'pose_cm_quat',
            'velocity_world_mm_s', 'angular_velocity_world_rad_s', 'up_z')
LEGS = ('LF', 'LM', 'LH', 'RF', 'RM', 'RH')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ieee_equal(value, reference):
    array = np.asarray(value, dtype=reference.dtype)
    return array.shape == reference.shape and array.tobytes() == reference.tobytes()


def review_case(case, result, plan):
    checks = []
    def check(name, value, detail=None):
        checks.append(dict(name=name, passed=bool(value), detail=detail))
    reference_path = ROOT / case['reference']
    check('reference_sha256', sha(reference_path) == case['reference_sha256'])
    journal_path = ROOT / result['journal']
    check('journal_sha256', sha(journal_path) == result['journal_sha256'])
    with np.load(reference_path) as archive:
        reference = {key: archive[key] for key in (*PHYSICAL, 'actor', 'command_on', 'tick')}
    errors = {name: [] for name in PHYSICAL}
    per_tick = {name: [] for name in ('actor_hash', 'actor_finite', 'counters', 'buffer_shape',
        'buffer_origin', 'clock', 'native_finite', 'warnings', 'terminated', 'command',
        'continuous_target', 'action_order', 'resource_inventory', 'resource_residual',
        'native_force_finite', 'contact_support_aggregate', 'contact_ground_aggregate')}
    initial = reset = metadata = previous = None
    events, samples, max_residual, max_clock = [], 0, 0., 0.
    contact_rows, force_values = 0, 0
    resource_values = []
    with journal_path.open() as stream:
        for line in stream:
            row = json.loads(line)
            kind = row['event']
            events.append(kind)
            if kind == 'initial':
                initial, metadata = row['state'], row['metadata']
                continue
            if kind == 'reset':
                reset = row['state']
                continue
            if kind != 'sample':
                check('unexpected_event', False, row)
                continue
            tick, state = row['tick'], row['state']
            if tick >= len(reference['tick']):
                check('extra_sample', False, tick)
                continue
            def tick_check(name, passed):
                if not passed:
                    per_tick[name].append(tick)
            for name in PHYSICAL:
                if not ieee_equal(state[name], reference[name][tick]):
                    errors[name].append(tick)
            actor = np.asarray(reference['actor'][tick], dtype='<f4')
            expected_hash = hashlib.sha256(actor.tobytes()).hexdigest()
            tick_check('actor_hash', actor.shape == (741,) and state['actor_input_sha256'] == expected_hash)
            tick_check('actor_finite', np.isfinite(actor).all())
            tick_check('counters', tick == samples == state['tick'] == state['source_control_tick'])
            frames = 66 if case['config']['reference_mode'] == 'rolling' else 1100
            tick_check('buffer_shape', state['reference_qpos_shape'] == [frames, 7] and state['reference_qvel_shape'] == [frames, 6])
            expected_origin = max(0, tick - 1) if frames == 66 else None
            tick_check('buffer_origin', state['reference_buffer_origin'] == expected_origin)
            clock_error = abs(state['native_time_s'] - .002 * tick)
            max_clock = max(max_clock, clock_error)
            tick_check('clock', clock_error <= 1e-10 and (previous is None or state['native_time_s'] > previous['native_time_s']))
            tick_check('native_finite', state['finite'] and all(np.isfinite(np.asarray(state[name])).all() for name in PHYSICAL))
            tick_check('warnings', not any(state['warnings']))
            tick_check('terminated', not state['source_terminated'])
            on = bool(reference['command_on'][tick])
            expected_command = dict(speed_mm_s=20. if on else 0., yaw_rad_s=0., policy_enabled=on, behavior='walk' if on else 'rest')
            tick_check('command', state['command'] == expected_command)
            if previous is not None:
                target = np.asarray(previous['target_pose_cm_quat']).copy()
                target[0] += .004 if on else 0.
                tick_check('continuous_target', ieee_equal(state['target_pose_cm_quat'], target))
            tick_check('action_order', state['action_names'] == metadata['action_names'] and state['actuator_ids'] == initial['actuator_ids'])
            inventory = row['resources']
            tick_check('resource_inventory', all(inventory[kind]['name'] == kind and inventory[kind]['kind'] == kind and
                inventory[kind]['initial'] == inventory[kind]['remaining'] == case['config'][kind + '_amount'] for kind in ('food', 'water')))
            residual = row['resource_balance']
            values = np.asarray(list(residual.values()), float)
            max_residual = max(max_residual, float(np.max(abs(values))))
            tick_check('resource_residual', set(residual) == {'nutrient', 'water'} and np.isfinite(values).all() and np.max(abs(values)) <= 1e-8)
            resource_values.append([residual['nutrient'], residual['water']])
            raw_force = np.asarray(state['actuator_force_preceding_stage'], float)
            support, ground = np.zeros(6), np.zeros((6, 3))
            contact_finite = True
            for contact in state['contacts']:
                force = np.asarray(contact['force_world_dyne'], float)
                contact_finite &= bool(np.isfinite(force).all())
                li = LEGS.index(contact['leg'])
                support[li] += abs(force[2])
                ground[li] += force
                contact_rows += 1
                force_values += 3
            tick_check('native_force_finite', raw_force.shape == (59,) and np.isfinite(raw_force).all() and contact_finite and
                np.isfinite(np.asarray(state['support_dyne_by_leg'])).all() and np.isfinite(np.asarray(state['ground_force_g_mm_s2'])).all())
            tick_check('contact_support_aggregate', ieee_equal(state['support_dyne_by_leg'], support))
            tick_check('contact_ground_aggregate', ieee_equal(state['ground_force_g_mm_s2'], ground * 10))
            force_values += raw_force.size
            if tick == 0:
                check('initial_equals_sample0', state == initial)
            previous = state
            samples += 1
    for name, failed in errors.items():
        check('ieee_bit_parity:' + name, not failed, dict(samples=samples, failing_ticks=failed[:20]))
    for name, failed in per_tick.items():
        check('every_sample:' + name, not failed, dict(samples=samples, failing_ticks=failed[:20]))
    check('exact_journal_sequence', events == ['initial'] + ['sample'] * len(reference['tick']) + ['reset'])
    check('complete_interval_count', samples == len(reference['tick']) == result['checks']['samples'])
    check('explicit_native_reset_exact', reset == initial)
    check('primary_report_success', result['passed'] and result['failure'] is None)
    check('recomputed_residual_maximum', max_residual == result['checks']['max_resource_residual'])
    check('recomputed_clock_maximum', max_clock == result['checks']['max_clock_error_s'])
    check('metadata_actor_order_shape', list(metadata['actor_observation_shapes']) == case['actor_keys'] and metadata['actor_observation_shapes'] == case['actor_shapes'] and sum(int(np.prod(s)) for s in case['actor_shapes'].values()) == 741)
    check('metadata_mode_horizon', metadata['reference_mode'] == case['config']['reference_mode'] and metadata['horizon_s'] == case['config']['horizon_s'] and metadata['finite_horizon'] == (case['config']['horizon_s'] is not None))
    check('metadata_storage_preview', metadata['reference_frames'] == frames and metadata['preview_frames'] == 65)
    check('metadata_native_clock_units', metadata['physics_timestep_s'] == .0002 and metadata['control_timestep_s'] == metadata['physiology_sampling_s'] == .002 and metadata['gravity_cm_s2'] == [0., 0., -981.])
    check('metadata_source_versions', all(metadata[key] == case['source'][key] for key in ('source_commit', 'source_manifest_sha256', 'policy_receipt_sha256', 'versions', 'python')))
    check('metadata_current_worker_provenance', metadata['worker_sha256'] == plan['source_hashes']['fruitfly/flybody_worker.py'])
    check('metadata_rolling_task_provenance', metadata.get('rolling_task_sha256') == (plan['source_hashes']['fruitfly/flybody_persistent_task.py'] if frames == 66 else None))
    return dict(name=case['name'], passed=all(c['passed'] for c in checks), checks=checks,
        samples=samples, control_intervals=samples - 1, actor_float32_values_checked=samples * 741,
        contact_force_rows=contact_rows, individual_force_values_checked=int(force_values),
        max_resource_residual=max_residual, max_native_clock_error_s=max_clock,
        journal_sha256=sha(journal_path), reference_sha256=sha(reference_path),
        resource_residual_array_sha256=hashlib.sha256(np.asarray(resource_values, dtype='<f8').tobytes()).hexdigest())


def review_interruption():
    folder = ROOT / 'validation/flybody-rolling-bridge-initial-checker'
    result = json.loads((folder / 'results.json').read_text())
    row = next(r for r in result['cases'] if r['name'] == 'rolling_switch12')
    events, last_sample, failure = [], None, None
    with (ROOT / row['journal']).open() as stream:
        for line in stream:
            item = json.loads(line)
            events.append(item['event'])
            if item['event'] == 'sample':
                last_sample = item
            elif item['event'] == 'failure':
                failure = item
    checks = dict(prior_hash=sha(ROOT / row['journal']) == row['journal_sha256'],
        explicit_keyboard_interrupt=row['failure']['type'] == 'KeyboardInterrupt' and failure['failure']['type'] == 'KeyboardInterrupt',
        interrupted_during_npz_decompression='_decompressor.decompress' in row['failure']['traceback'],
        completed_prefix_count=row['checks']['samples'] == 2178,
        partial_case_not_passed=not row['passed'] and not result['passed'],
        finite_unterminated_native_state=failure['native']['finite'] and not failure['native']['source_terminated'] and not any(failure['native']['warnings']))
    return dict(passed=all(checks.values()), checks=checks, classification='Operational checker interruption; not a source physics/guard failure.',
        completed_checked_samples=row['checks']['samples'], recorded_samples=events.count('sample'),
        last_recorded_tick=last_sample['tick'], last_native_time_s=last_sample['state']['native_time_s'],
        journal_sha256=row['journal_sha256'], prior_results_sha256=sha(folder / 'results.json'))


def main():
    plan = json.loads((OUT / 'plan.json').read_text())
    result = json.loads((OUT / 'results.json').read_text())
    if not result['complete']:
        raise RuntimeError('Wait for the existing bridge experiment to finish; do not restart it')
    sources = {path: sha(ROOT / path) == expected for path, expected in plan['source_hashes'].items()}
    cases = [review_case(case, next(r for r in result['cases'] if r['name'] == case['name']), plan) for case in plan['cases']]
    interruption = review_interruption()
    report = dict(passed=all(r['passed'] for r in cases) and all(sources.values()) and interruption['passed'] and result['plan_sha256'] == sha(OUT / 'plan.json'),
        reviewer_role='Author of earlier standalone reference task/experiment; independent of root-authored runtime integration and primary bridge checker. This is saved-data review, not independent biological replication.',
        script_sha256=sha(__file__), plan_sha256=sha(OUT / 'plan.json'), results_sha256=sha(OUT / 'results.json'),
        source_hash_checks=sources, cases=cases, initial_checker_interruption=interruption,
        simulations_run=0, runtime_imported=False,
        limitations=['Actual bridge actor values are represented by SHA256; reference retains all741float32 values. The source hash calculation is reviewed, but bridge raw actor arrays are not retransmitted.',
            'Reference buffer shapes/counters are recorded each tick; full66/1100row buffer values are not transmitted. Actor-reference rows are covered by actor hash and standalone reference.',
            'Journals include native actuator forces from preceding stage and refreshed contact forces, permitting finiteness/aggregation checks. Standalone reference NPZ omits forces, so no force-parity claim.',
            'Resource journals retain patch inventories and computed balance residuals, not complete energy/hydration/crop/spent ledgers. Reported residuals are verified each tick; full independent conservation reconstruction is unavailable.',
            'Initial rendering and zero-duration advance rely on completed source assertions; frames and per-render states are not retained. Native reset state is retained and checked exactly. Host reserve reset is not independently journaled.',
            'Bounded overrun rejection is asserted by primary checker, but its exception is not a separate journal event. The source guard is reviewed; no new failure-injection test is performed.',
            'Host time is an accessor to native time, not an independent clock. Saved counters/native time agree; no brain or long neural coupling was executed by this bridge experiment.'])
    (OUT / 'independent-review.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('Independent bridge review', report['passed'], 'samples', sum(r['samples'] for r in cases), 'checks', sum(len(r['checks']) for r in cases))
    for row in cases:
        for check in row['checks']:
            if not check['passed']:
                print(row['name'], check['name'], check['detail'])
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
