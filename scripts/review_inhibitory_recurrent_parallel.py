#!/usr/bin/env python3
"""Independent saved-data/source review. Does not import or run either kernel."""
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import json
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'validation/inhibitory-recurrent-parallel-independent-review.json'
BASE = 'validation/inhibitory-recurrent-parallel'
PINNED = {
    'scripts/inhibitory_recurrent_parallel.py': '1d787238144c74df46512bd266bbaefb7fbf50caebd67c87343f292406cd23c6',
    'scripts/inhibitory_recurrent_kernel.py': '52892eabb7124dfe6140f7c0cbc4d9047301978c6706053e3230d72280ec2b0f',
    'scripts/inhibitory_factorial_solver.py': 'ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711',
    'scripts/check_inhibitory_recurrent_parallel.py': '8fa0c9bc6ec5db9196c60ce3b4231e8d1a7d055a934d9b1dddf2554a4ca60951',
    'scripts/probe_inhibitory_recurrent_parallel.py': '0827e7d55168e0844450512d70885607953d67145c7306b00f6e60442c7f106e',
    BASE+'-plan.json': 'a0df93152521b691de5bb9e3f2f63e967ac520f3b64c9bdd2fda28ff81c82268',
    BASE+'-checks.json': '9c968800bf79edace82542566f525b407c801b1ab6077232a7b8e295cc0159a8',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise RuntimeError('Refusing to replace review receipt')
    checks = []
    errors = []
    details = {}
    inputs = {}

    def ck(name, ok):
        checks.append(dict(name=name, passed=bool(ok)))
        if not ok:
            raise AssertionError(name)

    def equal(a, b):
        if isinstance(a, np.ndarray):
            return isinstance(b, np.ndarray) and a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
        if type(a) is not type(b):
            return False
        if isinstance(a, dict):
            return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
        if isinstance(a, list):
            return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
        return a == b

    try:
        for name, expected in PINNED.items():
            inputs[name] = sha(ROOT/name)
            ck('frozen:'+name, inputs[name] == expected)
        plan = json.loads((ROOT/(BASE+'-plan.json')).read_text())
        receipt = json.loads((ROOT/(BASE+'-checks.json')).read_text())
        ck('plan_link', receipt['plan_sha256'] == inputs[BASE+'-plan.json'])
        ck('producer_passed_103', receipt['passed'] and not receipt['errors'] and len(receipt['checks']) == 103 and all(receipt['checks'].values()))
        ck('plan_sources_match_receipt', plan['source_sha256'] == receipt['source_sha256'])
        for name, expected in receipt['artifacts'].items():
            inputs[name] = sha(ROOT/name)
            ck('artifact:'+name, inputs[name] == expected['sha256'] and (ROOT/name).stat().st_size == expected['bytes'])
        for name in ['scripts/probe_inhibitory_recurrent_v2.py', 'fruitfly/neural.py',
                     'validation/inhibitory-recurrent-performance-v2/results.json']:
            inputs[name] = sha(ROOT/name)

        # Every class method, non-run preexisting function and constant remains
        # unchanged structurally. The narrow _run diff is separately read-reviewed.
        source = {}
        for kind in ['kernel', 'parallel']:
            tree = ast.parse((ROOT/f'scripts/inhibitory_recurrent_{kind}.py').read_text())
            source[kind] = {n.name: ast.dump(n, include_attributes=False) for n in tree.body
                            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        names = set(source['kernel']) - {'_run'}
        ck('original_API_and_other_functions_AST_unchanged', all(source['kernel'][k] == source['parallel'][k] for k in names))

        meta = json.loads((ROOT/(BASE+'-arrays.json')).read_text())
        with np.load(ROOT/(BASE+'-arrays.npz'), allow_pickle=False) as z:
            raw = {k: z[k] for k in z.files}
        references = []

        def decode(x):
            if isinstance(x, dict) and set(x) == {'array', 'shape', 'dtype'}:
                a = raw[x['array']]
                if list(a.shape) != x['shape'] or str(a.dtype) != x['dtype']:
                    raise AssertionError('Descriptor mismatch: '+x['array'])
                references.append(x['array'])
                return a
            if isinstance(x, dict):
                return {k: decode(v) for k, v in x.items()}
            if isinstance(x, list):
                return [decode(v) for v in x]
            return x

        data = decode(meta)
        ck('all_2737_arrays_described_once', len(raw) == 2737 and len(references) == len(raw) and set(references) == set(raw))
        pairs = [k for k, v in data.items() if isinstance(v, dict) and set(v) == {'serial', 'parallel'}]
        for key in pairs:
            ck('raw_pair:'+key, equal(data[key]['serial'], data[key]['parallel']))
        details['recursive_saved_pairs'] = len(pairs)
        details['saved_arrays'] = len(raw)
        details['paired_array_leaves'] = sum('__serial__' in k for k in raw)
        fixture = data['fixture']
        ck('fixture_ids_inputs', equal(fixture['neuron_ids'], np.arange(100, 228, dtype=np.int64)) and
           equal(fixture['inputs'], np.arange(0, 128, 16, dtype=np.int32)) and
           equal(fixture['selected'], np.arange(128, dtype=np.int32)))
        ck('fixture_CSR', equal(fixture['indptr'], np.arange(0, 129*5, 5, dtype=np.int64)) and
           equal(fixture['targets'], np.array([(i+d) % 128 for i in range(128) for d in [1, 2, 3, 7, 11]], np.int32)) and
           equal(fixture['weights'], np.tile(np.array([46, -23, 0, 70000, -69], np.float32), 128)))
        arms = {}
        for arm in ['C0', 'C1', 'H0', 'H1']:
            o = data[arm+':full_output']['parallel']
            cp = data[arm+':full_checkpoint']['parallel']
            ck(arm+':complete_clock', o['status'] == 'complete' and o['coherent_state'] and o['start_tick'] == 0 and o['end_tick'] == 300 and cp['tick'] == 300)
            ck(arm+':candidate', equal(o['candidate'], fixture['uniforms'] < fixture['probabilities']))
            last = np.full(128, -(2**60), dtype=np.int64)
            ref = np.full(128, 22, dtype=np.int64)
            ref[fixture['inputs']] = 0
            available = np.zeros((300, 128), bool)
            for t in range(300):
                available[t] = t-last >= ref
                last[o['selected_fired'][t]] = t
            fired = available & (o['selected_prethreshold_v'] > -45.)
            ck(arm+':refractory_and_threshold', equal(available, o['selected_available']) and equal(fired, o['selected_fired']) and equal(last, cp['last']))
            direct = available & ~fired
            ck(arm+':delivery_masks', equal(direct, o['selected_direct_available']) and equal(direct, o['selected_delivery_available']) and
               equal(np.ones_like(direct) if arm.endswith('1') else direct, o['selected_synaptic_available']))
            ck(arm+':applied', equal(o['applied'], o['candidate'] & direct[:, fixture['inputs']]))
            ticks, cells = np.where(fired)
            ck(arm+':ordered_spikes', equal(ticks.astype(np.int64), o['spike_ticks']) and equal(cells.astype(np.int32), o['spike_indices']))
            events = []
            pending = [[] for _ in range(19)]
            for t, cell in zip(ticks.tolist(), cells.tolist()):
                due = t+18
                if due >= 300:
                    pending[due % 19].append(cell)
                    continue
                for edge in range(int(fixture['indptr'][cell]), int(fixture['indptr'][cell+1])):
                    target = int(fixture['targets'][edge])
                    disposition = 0 if o['selected_synaptic_available'][due, target] else 1
                    events.append([due, cell, edge, target, disposition])
            ev = np.array(events, np.int64).reshape(-1, 5)
            ck(arm+':all_delayed_edge_records', equal(ev, o['selected_events']))
            counts = np.zeros((300, 4, 3), np.int64)
            for t, cell, edge, target, disposition in events:
                weight = fixture['weights'][edge]
                sign = 0 if weight < 0 else 2 if weight > 0 else 1
                counts[t, 0, sign] += 1
                counts[t, 1 if disposition == 0 else 2, sign] += 1
            ck(arm+':edge_count_accounting', equal(counts, o['per_tick']['edge_counts']))
            ck(arm+':pending', equal(np.array([len(x) for x in pending], np.int64), cp['pending_count']) and
               equal(np.array([cell for row in pending for cell in row], np.int32), cp['pending']))
            ck(arm+':reset_voltage', np.all(o['selected_v'][1:][fired] == -52.))
            if arm.endswith('0'):
                ck(arm+':reset_synapses', np.all(o['selected_s'][1:][fired] == 0.) and np.all(o['selected_h'][1:][fired] == 0.))
            ck(arm+':final_state', all(equal(cp[k], o['selected_'+k][-1]) for k in ['v', 's', 'h']))
            chunks = [data[arm+f':chunk{start}_output']['parallel'] for start in [0, 7, 71]]
            ck(arm+':whole_chunk_recorded_arrays', all(equal(o[k], np.concatenate([c[k] for c in chunks]))
                for k in ['spike_indices', 'spike_ticks', 'candidate', 'applied', 'selected_prethreshold_v', 'selected_events']) and
                all(equal(o['selected_'+k], np.concatenate([chunks[0]['selected_'+k]]+[c['selected_'+k][1:] for c in chunks[1:]])) for k in ['v', 's', 'h']))
            block = data[arm+':delivery_block_output']['parallel']
            be = block['selected_events']
            ck(arm+':delivery_time_block', np.any(be[:, 4] == 2) and np.all(be[be[:, 1] == 0, 4] == 2) and np.all(be[be[:, 4] == 2, 1] == 0))
            arms[arm] = dict(spikes=len(ticks), delayed_edges=len(events), pending_spikes=sum(map(len, pending)))
        details['whole_fixture'] = arms
        failures = []
        for arm in ['H0', 'H1']:
            for kind, code, phase in [('multiple_invalid', 1, 0), ('unavailable_invalid', 2, 1), ('postdelivery_infinite_edge', 4, 4), ('lower_bound', 5, 1)]:
                o = data[arm+':failure_'+kind+'_output']['parallel']
                cp = data[arm+':failure_'+kind+'_checkpoint']['parallel']
                f = o['failure']
                ck(arm+':failure_clock:'+kind, o['status'] == 'failed' and not o['coherent_state'] and not cp['coherent_state'] and
                   o['completed_ticks'] == 0 and o['end_tick'] == cp['tick'] == f['attempted_tick'] == f['completed_prefix_end_tick'] == 5 and f['last_completed_transition_tick'] == 4)
                ck(arm+':failure_phase:'+kind, f['code'] == code and f['phase_code'] == phase and o['partial'] is not None)
                if kind == 'multiple_invalid':
                    ck(arm+':first_error_and_earlier_spike', f['cell_index'] == 5 and equal(o['partial']['spike_indices'], np.array([1], np.int32)) and cp['last'][1] == 5 and np.isnan(cp['h'][90]) and cp['v'][1] > -45.)
                failures.append(dict(arm=arm, fixture=kind, code=code, phase=phase, cell=f['cell_index']))
        details['expected_invalid_cases'] = failures
        scratch = data['scratch']
        ck('scratch_native_bitwise', equal(scratch['before'], scratch['after']))
        ck('scratch_four_workers', equal(np.unique(scratch['workers']), np.arange(4, dtype=np.int32)))
        ck('scratch_status', scratch['status'][5] == 1 and scratch['status'][90] == 2 and np.count_nonzero(scratch['status'] == 0) == 126)
        ck('scratch_unavailable_unwritten', np.all(scratch['scratch'][90] == -999.))
        ck('runtime', data['parallel_runtime']['numba_threads'] == 4 and data['parallel_runtime']['threading_layer'] == 'workqueue' and not data['parallel_runtime']['fastmath'])
        compiler = (ROOT/(BASE+'-compiler.txt')).read_text()
        ck('compiler_optimized_parallel_listing', 'Parallel loop listing' in compiler and 'prange(len(v))' in compiler and 'Parallel structure is already optimal' in compiler)
        for name, expected in inputs.items():
            ck('unchanged:'+name, sha(ROOT/name) == expected)
    except Exception as exc:
        errors.append(dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
    result = dict(schema=1, completed_utc=datetime.now(timezone.utc).isoformat(), passed=not errors and all(c['passed'] for c in checks),
        scope='Independent source inspection plus saved synthetic arrays; no kernel import, producer execution, full graph, or timing run.',
        reviewer_role='Separate reviewer; authored earlier input/source/data reviews, not serial/parallel kernels or their synthetic/probe producers.',
        script_sha256=sha(__file__), inputs=inputs, checks=checks, check_count=len(checks), errors=errors, details=details,
        source_review=dict(blockers=[], corrected_before_freeze='Probe uncaught-return failure now separates confirmed pre-call prefix/RNG from possibly advanced mutable tick.',
            conclusion='Narrow independent H precomputation preserves serial commit, first failure, edge and reset order. API and original non-run functions are structurally unchanged.'),
        limits=['Saved metadata normalizes original tuples/lists and NumPy scalars; exact original Python container types were checked by producer, not recoverable here.',
            'Continuation denial is source/producer receipt evidence, not a saved operation that this reviewer re-executed.',
            'No new independent H numerical integration: this review checks concurrency parity against frozen serial results.',
            'Full-graph 50ms parity/speed remain a separately frozen upcoming test. Intermediate all-cell state hashes are producer digests, not retained full arrays.',
            'One/four-thread and failure coverage apply to saved synthetic fixtures; not exhaustive concurrency/fault testing.',
            'Resource limits checked between operations permit overshoot; process kill or allocation failure can prevent archival. Four-thread setting is process runtime state.',
            'No physiological claim, long-run stability result, scientific stimulus contrast, or H1 promotion.'])
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'], checks=len(checks), details=details, errors=errors), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
