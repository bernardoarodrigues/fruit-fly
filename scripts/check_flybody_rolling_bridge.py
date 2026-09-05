"""Freeze and verify the rolling RPC runtime against saved native trajectories."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'validation/flybody-rolling-bridge'
PLAN = OUT / 'plan.json'
RESULT = OUT / 'results.json'
FIELDS = ('qpos', 'qvel', 'qacc', 'act', 'ctrl', 'native_action', 'canonical_action',
          'target_pose_cm_quat', 'native_time_s')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def make_plan():
    from fruitfly.flybody_bridge import FlyBodyConfig
    prior = json.loads((ROOT / 'validation/flybody-persistent-experiment.json').read_text())
    cases = []
    for mode, old in [('bounded', 'bounded_parity'), ('rolling', 'rolling_parity'),
                      ('rolling', 'rolling_switch12')]:
        row = next(x for x in prior['trials'] if x['case'] == old)
        config = FlyBodyConfig(reference_mode=mode, horizon_s=2. if mode == 'bounded' else None)
        cases.append(dict(name=old, config=asdict(config), reference=row['trace'],
                          reference_sha256=row['trace_sha256'], actor_keys=row['actor_keys'],
                          actor_shapes=row['actor_shapes'], source=row['source']))
    files = [*sorted(ROOT.glob('fruitfly/*.py')), Path(__file__),
             ROOT / 'validation/flybody-persistent-plan.json',
             ROOT / 'validation/flybody-persistent-experiment.json',
             ROOT / 'validation/flybody-persistent-independent-review.json',
             ROOT / 'validation/flybody-source-manifest.json',
             ROOT / 'validation/flybody-walking-acquisition.json']
    return dict(created_at=datetime.now(timezone.utc).isoformat(), seed=11,
        amendment={'prior_plan': 'validation/flybody-rolling-bridge-initial-checker/plan.json',
                   'prior_results': 'validation/flybody-rolling-bridge-initial-checker/results.json',
                   'reason': 'Load each immutable NPZ reference array once instead of decompressing it on every tick. Root interrupted the slow third comparison with SIGINT; two comparisons had already passed. Physics, schedules and gates unchanged.'},
        cases=cases, source_hashes={str(p.relative_to(ROOT)): sha(p) for p in files},
        comparison_fields=FIELDS,
        gates=['Bitwise physical/action/target/native-clock parity at every saved reference sample',
               'SHA256 of actual 741 float32 actor-input values equals independent saved reference at every sample',
               'Native reference storage is 1100 bounded or 66 rolling; actor sees65frames',
               'All native warning counters zero, finite state and no source termination',
               'Resource residuals <=1e-8 in host normalized units at every2ms tick',
               'Native and host time agree at every tick; no automatic reset/recenter',
               'Initial zero-step/render preserve exact native state; explicit reset restores exact initial state',
               'Horizon metadata matches explicit mode; bounded overrun rejected without state change'],
        limits=['Body/RPC regression only; no neural simulation or new biological claims',
                'Force finiteness includes native worker assertion; saved native reference lacks rawforces',
                'Renderer changes no physics; initial-only render checks',
                'Whole reference arrays are not transmitted; current shapes and buffer counters are checked each2ms'])


def run_case(case, folder):
    from fruitfly.flybody_bridge import FlyBodyRuntime
    if sha(ROOT / case['reference']) != case['reference_sha256']:
        raise ValueError('Changed standalone reference')
    with np.load(ROOT / case['reference']) as archive:
        trace = {key: archive[key] for key in (*FIELDS, 'tick', 'command_on', 'actor')}
    log = folder / (case['name'] + '.jsonl')
    checks = dict(samples=0, max_resource_residual=0., max_clock_error_s=0.)
    failure = None
    body = None
    started = time.perf_counter()
    with log.open('x', buffering=1) as stream:
        def event(kind, **values):
            stream.write(json.dumps(dict(event=kind, **values), allow_nan=False, separators=(',', ':'))+'\n')
            stream.flush()
        try:
            body = FlyBodyRuntime(seed=11, config=case['config'],
                                  log_path=folder / (case['name'] + '-worker.log'))
            initial = body.diagnostics()
            metadata = body.snapshot()['backend']
            assert metadata['reference_mode'] == case['config']['reference_mode']
            assert metadata['horizon_s'] == case['config']['horizon_s']
            assert metadata['reference_frames'] == (66 if metadata['reference_mode']=='rolling' else 1100)
            assert metadata['preview_frames'] == 65
            assert list(metadata['actor_observation_shapes']) == case['actor_keys']
            assert metadata['actor_observation_shapes'] == case['actor_shapes']
            for key in ('source_commit', 'source_manifest_sha256', 'policy_receipt_sha256', 'versions', 'python'):
                assert metadata[key] == case['source'][key], key
            body.advance(0., 0., 0., 'rest')
            for camera in ('follow', 'side', 'overview'):
                body.render(camera)
                assert body.diagnostics() == initial
            event('initial', state=initial, metadata=metadata)
            for tick in range(len(trace['tick'])):
                if tick:
                    on = bool(trace['command_on'][tick])
                    body.advance(.002, 1. if on else 0., 1. if on else 0., 'walk' if on else 'rest')
                state, snapshot = body.diagnostics(), body.snapshot()
                event('sample', tick=tick, state=state, resources=snapshot['resources'],
                      resource_balance=snapshot['resource_balance'])
                for key in FIELDS:
                    np.testing.assert_array_equal(state[key], trace[key][tick], err_msg=key + ':' + str(tick))
                expected = hashlib.sha256(np.asarray(trace['actor'][tick], dtype='<f4').tobytes()).hexdigest()
                assert state['actor_input_sha256'] == expected, ('actor_input', tick)
                frames = 66 if metadata['reference_mode'] == 'rolling' else 1100
                assert state['reference_qpos_shape'] == [frames, 7]
                assert state['reference_qvel_shape'] == [frames, 6]
                assert state['source_control_tick'] == tick
                if metadata['reference_mode'] == 'rolling':
                    assert state['reference_buffer_origin'] == max(0, tick-1)
                assert state['finite'] and not state['source_terminated'] and not any(state['warnings'])
                discrepancy = abs(state['native_time_s'] - tick*.002)
                assert discrepancy <= 1e-10
                checks['max_clock_error_s'] = max(checks['max_clock_error_s'], discrepancy)
                residual = max(abs(v) for v in snapshot['resource_balance'].values())
                assert residual <= 1e-8
                checks['max_resource_residual'] = max(checks['max_resource_residual'], residual)
                checks['samples'] += 1
            if case['config']['reference_mode'] == 'bounded':
                previous = body.diagnostics()
                try:
                    body.advance(.002, 1., 1., 'walk')
                except RuntimeError:
                    assert body.diagnostics() == previous
                else:
                    raise AssertionError('Bounded horizon was not enforced')
            body.reset(seed=11)
            assert body.diagnostics() == initial
            event('reset', state=body.diagnostics())
        except BaseException as error:
            failure = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
            event('failure', failure=failure, native=body.diagnostics() if body else None)
        finally:
            if body:
                body.close()
    return dict(name=case['name'], passed=failure is None, failure=failure, checks=checks,
                journal=str(log.relative_to(ROOT)), journal_sha256=sha(log),
                wall_s=time.perf_counter()-started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.plan:
        OUT.mkdir(exist_ok=True)
        if PLAN.exists():
            raise FileExistsError(PLAN)
        write(PLAN, make_plan())
        print('Frozen', sha(PLAN))
    elif args.run:
        if RESULT.exists():
            raise FileExistsError(RESULT)
        plan = json.loads(PLAN.read_text())
        for path, expected in plan['source_hashes'].items():
            if sha(ROOT/path) != expected:
                raise ValueError('Source changed after plan: ' + path)
        folder = ROOT / 'runs' / ('flybody-rolling-bridge-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        results = dict(plan_sha256=sha(PLAN), complete=False, cases=[])
        for case in plan['cases']:
            results['cases'].append(run_case(case, folder))
            write(RESULT, results)
            print(case['name'], results['cases'][-1]['passed'], flush=True)
        results['complete'] = True
        results['passed'] = all(x['passed'] for x in results['cases'])
        write(RESULT, results)
        if not results['passed']:
            raise SystemExit(1)
    else:
        parser.error('Choose --plan or --run')


if __name__ == '__main__':
    main()
