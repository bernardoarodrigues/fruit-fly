#!/usr/bin/env python3
"""Data-only exact comparison of retained serial and parallel 50 ms probes."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PAR = ROOT/'validation/inhibitory-recurrent-parallel-performance'
SER = ROOT/'validation/inhibitory-recurrent-performance-v2'
PLAN = ROOT/'validation/inhibitory-recurrent-parallel-performance-plan.json'
OUT = ROOT/'validation/inhibitory-recurrent-parallel-performance-independent-review.json'
RESULT_SHA = '0bc69e23b06a1f0265f9609c31f4cc3c5aa98080d3cff95b8d21f33f2c8340f9'
STATE_KEYS = ('v', 's', 'h', 'last', 'refractory', 'blocked', 'pending_count', 'pending')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def main():
    if OUT.exists():
        raise RuntimeError('Refusing to replace saved review')
    checks, errors, inputs, details = [], [], {}, {}

    def ck(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
        if not passed:
            raise AssertionError(name)

    def pin(path, expected=None):
        path = Path(path)
        value = dict(sha256=sha(path), bytes=path.stat().st_size)
        inputs[str(path.relative_to(ROOT))] = value
        if expected is not None:
            ck('hash:'+str(path.relative_to(ROOT)), value == expected)
        return value

    def load(stem):
        meta = json.loads(stem.with_suffix('.json').read_text())
        with np.load(stem.with_suffix('.npz'), allow_pickle=False) as z:
            arrays = {key: z[key] for key in z.files}
        used = []

        def walk(x):
            if isinstance(x, dict) and set(x) == {'array', 'shape', 'dtype'}:
                a = arrays[x['array']]
                used.append(x['array'])
                if list(a.shape) != x['shape'] or str(a.dtype) != x['dtype']:
                    raise AssertionError('Array descriptor mismatch')
            elif isinstance(x, dict):
                for value in x.values(): walk(value)
            elif isinstance(x, list):
                for value in x: walk(value)
        walk(meta)
        ck('schema:'+str(stem.relative_to(ROOT)), len(used) == len(arrays) and set(used) == set(arrays))
        return meta, arrays

    try:
        ck('parallel_result_pin', pin(PAR/'results.json')['sha256'] == RESULT_SHA)
        plan = json.loads(PLAN.read_text())
        result = json.loads((PAR/'results.json').read_text())
        serial = json.loads((SER/'results.json').read_text())
        ck('parallel_plan_pin', pin(PLAN)['sha256'] == result['plan_sha256'])
        ck('parallel_complete_1242', result['complete'] and not result['errors'] and len(result['checks']) == 1242 and all(c['passed'] for c in result['checks']))
        ck('serial_complete', serial['complete'] and not serial['errors'] and all(c['passed'] for c in serial['checks']))
        for path, expected in plan['sources'].items(): pin(ROOT/path, expected)
        for path, expected in result['artifacts'].items(): pin(ROOT/path, expected)
        # Parallel plan pins every serial NPZ, but serial JSON schemas are also
        # read here, so verify those against the frozen serial result manifest.
        for arm in ['C0', 'C1', 'H0', 'H1']:
            for stem in ['initial', 'final']+[f'chunk-{k:02d}' for k in range(10)]:
                path = SER/arm/(stem+'.json')
                pin(path, serial['artifacts'][str(path.relative_to(ROOT))])
        serial_plan = json.loads((ROOT/'validation/inhibitory-recurrent-performance-plan-v2.json').read_text())
        ck('same_environment', plan['environment'] == serial_plan['environment'])
        ck('fixed_protocol', plan['threads'] == 4 and plan['seed'] == 11 and plan['duration_ms'] == 50 and plan['chunk_ms'] == 5 and plan['dt_ms'] == .1 and plan['arms'] == ['C0','C1','H0','H1'])
        ck('thread_metadata', result['threading_layer'] == 'workqueue' and any(c['name'] == 'four_threads' and c['passed'] for c in result['checks']))
        serial_arms = {x['arm']: x for x in serial['arms']}
        ck('all_four_arms', [x['arm'] for x in result['arms']] == plan['arms'])
        with np.load(SER/'input-stream.npz', allow_pickle=False) as z:
            states = z['root__logical_rng_boundaries']
        total_arrays, total_bytes = 0, 0
        timing = {}
        for arm_result in result['arms']:
            arm = arm_result['arm']
            old = serial_arms[arm]
            ck(arm+':ten_complete_chunks', arm_result['complete'] and len(arm_result['chunks']) == 10)
            for stem in ['initial']+[f'chunk-{k:02d}' for k in range(10)]+['final']:
                pm, pa = load(PAR/arm/stem)
                sm, sa = load(SER/arm/stem)
                ck(arm+':'+stem+':array_keys', pa.keys() == sa.keys())
                for key, a in pa.items():
                    b = sa[key]
                    ck(arm+':'+stem+':'+key, a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes())
                    total_arrays += 1
                    total_bytes += a.nbytes
                if stem.startswith('chunk-'):
                    k = int(stem[-2:]); start, end = k*50, (k+1)*50
                    # Only this explanatory note is absent in the new producer.
                    ck(arm+':'+stem+':metadata_keys', set(sm)-set(pm) == {'logical_rng_note'} and not set(pm)-set(sm))
                    ck(arm+':'+stem+':metadata', all(sm[key] == value for key, value in pm.items()))
                    ck(arm+':'+stem+':clocks_rng', pm['status'] == 'complete' and pm['coherent_state'] and pm['failure'] is None and pm['partial'] is None and
                       pm['start_tick'] == start and pm['end_tick'] == end and pm['completed_ticks'] == pm['requested_ticks'] == 50 and
                       pm['logical_rng_before'] == int(states[start]) and pm['logical_rng_completed_prefix'] == int(states[end]))
                    new_chunk, old_chunk = arm_result['chunks'][k], old['chunks'][k]
                    ck(arm+':'+stem+':summary', new_chunk['chunk'] == k and new_chunk['end_tick'] == end and new_chunk['spikes'] == len(pa['root__spike_indices']) and
                       pm['checkpoint_digest'] == new_chunk['state_sha256'] == old_chunk['state_sha256'])
                else:
                    tick = 0 if stem == 'initial' else 500
                    ck(arm+':'+stem+':metadata', pm == sm and pm['tick'] == tick and pm['time_ms'] == tick*.1 and pm['coherent_state'] and pm['failure'] is None and pm['logical_rng_state'] == int(states[tick]))
                    if stem == 'final':
                        digest = hashlib.sha256(str(tick).encode())
                        for key in STATE_KEYS:
                            a = pa['root__'+key]
                            digest.update(key.encode()); digest.update(str(a.dtype).encode())
                            digest.update(str(a.shape).encode()); digest.update(a.tobytes())
                        ck(arm+':final_digest_from_arrays', digest.hexdigest() == arm_result['chunks'][-1]['state_sha256'])
            new_sum = sum(x['kernel_seconds'] for x in arm_result['chunks'])
            old_sum = sum(x['kernel_seconds'] for x in old['chunks'])
            ck(arm+':timing_sums_and_ratio', all(x['kernel_seconds'] > 0 for x in arm_result['chunks']) and new_sum == arm_result['kernel_seconds'] and old_sum == old['kernel_seconds'] == arm_result['serial_kernel_seconds'] and old_sum/new_sum == arm_result['observed_serial_over_parallel_ratio'])
            timing[arm] = dict(serial_seconds=old_sum, new_module_seconds=new_sum, observed_ratio=old_sum/new_sum,
                spikes=sum(x['spikes'] for x in arm_result['chunks']))
        resources = result['resources']
        ck('reported_resources_within_plan', all(resources[k] <= plan['budget'][k] for k in plan['budget']))
        ck('timing_enclosure', sum(x['new_module_seconds'] for x in timing.values()) + result['warmup_seconds'] < result['execution_wall_seconds'] <= result['wall_seconds'])
        ck('C_also_faster_despite_serial_path', timing['C0']['observed_ratio'] > 1 and timing['C1']['observed_ratio'] > 1)
        details = dict(compared_archive_pairs=48, compared_array_pairs=total_arrays, compared_array_bytes_per_side=total_bytes,
            parallel_manifest_files=len(result['artifacts']), source_pins=len(plan['sources']), timing=timing, resources=resources,
            execution_wall_seconds=result['execution_wall_seconds'], overall_wall_seconds=result['wall_seconds'],
            warmup_seconds=result['warmup_seconds'])
        for path, expected in inputs.items():
            ck('unchanged:'+path, sha(ROOT/path) == expected['sha256'])
    except Exception as error:
        errors.append(dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
    review = dict(schema=1, completed_utc=datetime.now(timezone.utc).isoformat(), passed=not errors and all(c['passed'] for c in checks),
        scope='Saved file, array, metadata and timing arithmetic review only; no producer imports, model execution or new timing experiment.',
        reviewer_role='Independent of both kernels and probe producers; also authored the earlier parallel source/synthetic review.',
        script_sha256=sha(__file__), inputs=inputs, checks=checks, check_count=len(checks), errors=errors, details=details,
        limits=['Only one seed and 50 ms constant baseline; not the later stimulus/seed panel.',
            'Numeric equality is against retained serial-v2; this review does not rerun the original engine or H numerical integration.',
            'All initial/final arrays are retained. Intermediate global state digests are producer summaries, not independently reconstructible all-cell snapshots.',
            'Four-thread mask and workqueue are reported by the full-graph producer; actual worker IDs were saved only for the separately reviewed synthetic fixture.',
            'Both C arms also ran faster while their neural path remains serial. Noncontemporaneous single-run timings do not identify a robust thread speedup, uncertainty interval or later workload cost.',
            'Resource values are producer measurements between operations; reviewer verifies arithmetic and limits, not historical process RSS or per-operation maxima.',
            'No physiological validation, long-run stability conclusion, or H1 promotion.'])
    OUT.write_text(json.dumps(review, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(passed=review['passed'], checks=len(checks), details=details, errors=errors), indent=2))
    return 0 if review['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
