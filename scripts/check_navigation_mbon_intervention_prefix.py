#!/usr/bin/env python3
"""Frozen six-case inactive-window checkpoint branch check; no run on import.

prepare only reads files. run performs exactly one 50-tick original branch and
one 50-tick derived branch per archived condition, after explicit plan freezing.
No source spikes or uniforms are regenerated; no active suppression is allowed.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import platform
import resource
import sys
import time
import traceback

import numpy as np
import numba

from inhibitory_recurrent_panel_archive import atomic_json, save_archive
from review_inhibitory_recurrent_panel_trial import Audit

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'validation/navigation-mbon-intervention-prefix-plan.json'
RESULT = ROOT / 'validation/navigation-mbon-intervention-prefix-results.json'
PANEL = ROOT / 'validation/inhibitory-recurrent-panel-plan.json'
GRAPH = ROOT / 'data/processed/malecns_v1'
MBON = ROOT / 'validation/navigation-ladder-mbon-input-results.json'
REVIEW = ROOT / 'validation/navigation-ladder-mbon-input-independent-review.json'
KERNEL = ROOT / 'scripts/navigation_mbon_intervention_kernel.py'
KERNEL_SHA = '5cfb8c0e51e7bc968a23c2be41133634e284a39ca6f63e5d010f0656b17241a4'
BASE_SHA = 'fecae2793af7d5b491a9090d0a8d0b712bba727d918c39be14e0e73048dd4eff'
ORDINALS = [26, 29, 32, 35, 38, 41]
START, END = 5000, 5050
WINDOW = [10000, 15000]
TRACE_FIELDS = ['selected_v', 'selected_s', 'selected_h', 'selected_prethreshold_v',
                'selected_available', 'selected_fired', 'selected_delivery_available',
                'selected_direct_available', 'selected_synaptic_available']


def load(path):
    return json.loads(Path(path).read_text())


def record(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=h.hexdigest())


def prepare(synthetic):
    if PLAN.exists() or RESULT.exists():
        raise FileExistsError('Preserve first prefix plan/results')
    panel, mbon, review, manufactured = load(PANEL), load(MBON), load(REVIEW), load(synthetic)
    assert mbon['passed'] and mbon['intervention_gate']['passed'] and not mbon['intervention_gate']['launched']
    assert mbon['intervention_gate']['selected_class'] == 'Kenyon_Cell' and mbon['intervention_gate']['positive_edge_count'] == 8236
    assert review['passed'] and not review['failures'] and review['error'] is None
    assert review['source_start'][str(MBON.relative_to(ROOT))] == record(MBON)
    assert manufactured['passed'] and manufactured['checks_passed'] == manufactured['checks_total'] == 157
    assert manufactured['source_sha256'][KERNEL.name] == record(KERNEL)['sha256'] == KERNEL_SHA
    assert manufactured['source_sha256']['check_navigation_mbon_intervention_kernel.py'] == record(ROOT / 'scripts/check_navigation_mbon_intervention_kernel.py')['sha256']
    assert record(ROOT / 'scripts/inhibitory_recurrent_panel_kernel.py')['sha256'] == BASE_SHA
    run = ROOT / panel['run_dir']
    specs = [panel['order'][i] for i in ORDINALS]
    assert all(s['arm'] == 'H1' and s['condition'] in ('constant_baseline', 'ethyl_acetate') for s in specs)
    assert panel['threads'] == 4 and panel['dt_ms'] == .1 and panel['chunk_ticks'] == 50
    assert START < END <= WINDOW[0]
    paths = [Path(__file__), KERNEL, ROOT / 'scripts/check_navigation_mbon_intervention_kernel.py',
             ROOT / 'scripts/inhibitory_recurrent_panel_kernel.py', ROOT / 'scripts/inhibitory_factorial_solver.py',
             ROOT / 'scripts/inhibitory_recurrent_panel_archive.py', ROOT / 'scripts/review_inhibitory_recurrent_panel_trial.py',
             Path(synthetic), PANEL, MBON, REVIEW, ROOT / 'validation/navigation-ladder-mbon-input-plan.json',
             ROOT / 'validation/navigation-ladder-mbon-input-arrays.npz', ROOT / 'validation/navigation-ladder-anatomy.json',
             GRAPH / 'manifest.json', run / 'terminal.json', run / 'artifact-manifest.json']
    paths += [GRAPH / (k + '.npy') for k in ('neuron_ids', 'indptr', 'targets', 'weights')]
    stems = [run / 'selection'] + [run / f'input-seed{s}' for s in (11, 12, 13)]
    for spec in specs:
        directory = run / spec['name']
        terminal = load(directory / 'terminal.json')
        assert terminal['complete'] and terminal['status'] == 'complete'
        assert record(directory / 'result.json') == terminal['result']
        paths += [directory / 'terminal.json', directory / 'result.json']
        stems += [directory / 'checkpoint-05000', directory / 'chunk-0099', directory / 'chunk-0100']
    paths += [Path(str(s) + suffix) for s in stems for suffix in ('.npz', '.json', '.complete.json')]
    pins = [record(p) for p in paths]
    plan = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), inputs=pins,
        trials=specs, run_dir=panel['run_dir'], start_tick=START, end_tick=END, chunk_index=100,
        threads=4, dt_ms=.1, graph_sha256=panel['graph_sha256'], inactive_delivery_window_ticks=WINDOW,
        suppressed_edge_count=8236, selected_class='Kenyon_Cell',
        condition_rates_hz=panel['condition_rates_hz'],
        selection='Restore exact original48 checkpoint; derived observation selection is sorted unique original48 plus the ten verified MBON12_14 targets. Original branch remains48. Event logging explicitly stays original48.',
        input='Use archived seed uniforms[5000:5050] and exact source expression np.full(36, rate)*.1/1000; pulse-phase rate from the frozen panel plan. Record logical RNG boundaries; no generator or RNG restoration inside kernel.',
        comparison=dict(trace_fields_projected_to_original48=TRACE_FIELDS,
            output_fields='Every original kernel output field is compared recursively by dtype/shape/bytes to saved chunk100; the derived58 output is projected only for the declared trace fields. Global diagnostics, events, references, schema and scalar fields must be identical.',
            checkpoint='Every original kernel checkpoint field equals archived5000 before branch. After observation expansion and at5050, only selected_indices intentionally differs; all full dynamical arrays, clock, parameters, masks and valid packed queue match original. Expanded selection must equal declared sorted58.',
            new_MBON_traces='Ten added v/s/h initial and final trace rows equal corresponding full checkpoint states; intermediate MBON values are newly recorded observations, not independently retained historical traces.',
            own_history='Verify initial pending queue from saved chunk99 tail; reconstruct final last-spike array and pending queue from checkpoint5000 plus current spikes. Compare current input masks against exact uniforms and firing stamps.'),
        total_network_advances=12, ticks_per_advance=50,
        output_directory='runs/navigation-mbon-intervention-prefix-<first12_plan_sha256>',
        resource_budget=dict(wall_seconds=600, output_bytes=256 * 1024**2, peak_rss_bytes=4 * 1024**3),
        budget_scope='Start after preflight hashing; checked before/after each branch and publication. One operation can overshoot. Final source rehash and result publication are outside the execution limit.',
        failure='Stop at first disagreement/exception/interruption, retain all completed outputs and attempted-state phase; no retry, tuning, active suppression or extension.',
        limits=['This inactive5ms branch verifies exact implementation and observation invariance, not the active intervention outcome or physiological validity.',
                'The actual suppressed mask is nonempty but all tested delivery ticks precede its window.',
                'Historical full state at5050 was not retained; full endpoint parity uses the separately restored frozen original branch, while all historical retained kernel fields are compared exactly.'],
        environment=dict(python=platform.python_version(), numpy=np.__version__, numba=numba.__version__))
    print(json.dumps(atomic_json(PLAN, plan)))


def manual_original_restore(base, graph, cp):
    """Independent literal restoration into the unmodified original class."""
    net = base.FactorialNetwork(*graph, 'H1', cp['input_indices'], cp['selected_indices'], seed=cp['seed'])
    for key in ('v', 's', 'h', 'last', 'refractory', 'blocked', 'pending_count'):
        getattr(net, key)[:] = cp[key]
    offset = 0
    for slot, count in enumerate(cp['pending_count']):
        net._pending[slot, :count] = cp['pending'][offset:offset + count]
        offset += int(count)
    net.tick = int(cp['tick'])
    return net


def run():
    if RESULT.exists():
        raise FileExistsError('Preserve first prefix result')
    plan = load(PLAN)
    plan_record = record(PLAN)
    outdir = ROOT / ('runs/navigation-mbon-intervention-prefix-' + plan_record['sha256'][:12])
    if outdir.exists():
        raise FileExistsError('Preserve first prefix execution directory')
    outdir.mkdir(parents=True)
    reader = Audit()
    result = dict(schema=1, plan=plan_record, passed=False, trials=[], artifacts=[], errors=[],
                  context={'phase': 'preflight'}, source_start=plan['inputs'])
    began = None
    net, executing, current_output = None, False, None

    def ck(name, condition, context=None):
        if not reader.ck(name, condition, context):
            raise AssertionError(name + ': ' + str(context))

    def same(a, b, path):
        if isinstance(a, np.ndarray):
            ck('exact_array', isinstance(b, np.ndarray) and a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), path)
        elif isinstance(a, dict):
            ck('dictionary_schema', isinstance(b, dict) and list(a) == list(b), path)
            for k in a:
                same(a[k], b[k], path + '.' + k)
        elif isinstance(a, (list, tuple)):
            ck('sequence_schema', type(a) is type(b) and len(a) == len(b), path)
            for j, (x, y) in enumerate(zip(a, b)):
                same(x, y, path + '.' + str(j))
        else:
            ck('exact_scalar', type(a) is type(b) and (a == b or isinstance(a, float) and np.isnan(a) and np.isnan(b)), path)

    def save(name, value):
        result['artifacts'].extend(save_archive(outdir / name, value))

    def budget():
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        values = dict(wall_seconds=time.perf_counter() - began,
                      output_bytes=sum(p.stat().st_size for p in outdir.rglob('*') if p.is_file()), peak_rss_bytes=rss)
        result['resources'] = values
        ck('bounded_execution', all(values[k] <= v for k, v in plan['resource_budget'].items()), values)

    try:
        for pin in plan['inputs']:
            ck('frozen_input', record(ROOT / pin['path']) == pin, pin['path'])
        ck('environment', plan['environment'] == dict(python=platform.python_version(), numpy=np.__version__, numba=numba.__version__))
        import navigation_mbon_intervention_kernel as module
        base = module.original
        began = time.perf_counter()
        base.configure_threads(plan['threads'])
        ck('four_threads', numba.get_num_threads() == 4)
        result['source_derivation'] = module.source_derivation()
        graph = tuple(np.load(GRAPH / (k + '.npy')) for k in ('neuron_ids', 'indptr', 'targets', 'weights'))
        saved_run = ROOT / plan['run_dir']
        selection = reader.archive(saved_run / 'selection')
        with np.load(ROOT / 'validation/navigation-ladder-mbon-input-arrays.npz', allow_pickle=False) as arrays:
            edges = arrays['proposed_intervention_edge_indices']
            mbon = arrays['graph_indices']
        selected = selection['selected']
        expanded = np.unique(np.r_[selected, mbon]).astype(np.int32)
        original_columns, mbon_columns = np.searchsorted(expanded, selected), np.searchsorted(expanded, mbon)
        ck('exact_observation_populations', len(selected) == 48 and len(mbon) == 10 and len(expanded) == 58
           and not np.intersect1d(selected, mbon).size)
        ck('nonempty_inactive_mask', len(edges) == plan['suppressed_edge_count'] == 8236 and END <= WINDOW[0])
        save('selection-and-intervention', dict(original_selected=selected, expanded_selected=expanded,
             added_MBON=mbon, original_columns=original_columns, MBON_columns=mbon_columns,
             suppressed_edge_indices=edges, delivery_window_ticks=WINDOW))
        for spec in plan['trials']:
            net, current_output = None, None
            result['context'] = dict(ordinal=spec['ordinal'], phase='load_saved')
            directory = saved_run / spec['name']
            cp = reader.archive(directory / 'checkpoint-05000')
            previous = reader.archive(directory / 'chunk-0099')
            historical = reader.archive(directory / 'chunk-0100')
            stream = reader.archive(saved_run / f'input-seed{spec["seed"]}')
            u = stream['uniforms'][START:END].copy()
            rate = plan['condition_rates_hz'][spec['condition']][1]
            probabilities = np.full(36, rate) * .1 / 1000.
            ck('checkpoint_source_identity', cp['tick'] == START and cp['arm'] == 'H1' and cp['seed'] == spec['seed']
               and cp['coherent_state'] and cp['failure'] is None and cp['graph_sha256'] == plan['graph_sha256'])
            same(selected, cp['selected_indices'], 'original selected')
            same(selection['inputs'], cp['input_indices'], 'original inputs')
            ck('saved_input_clock', int(stream['logical_rng_boundaries'][START]) == cp['logical_rng_state']
               == historical['panel_telemetry']['logical_rng_before']
               and int(stream['logical_rng_boundaries'][END]) == historical['panel_telemetry']['logical_rng_completed_prefix']
               and historical['panel_telemetry']['rate_hz'] == rate)
            same(selected, historical['panel_telemetry']['event_indices'], 'saved event population')
            tail = previous['spike_ticks'] + 18 >= START
            slots = (previous['spike_ticks'][tail] + 18) % 19
            pi = previous['spike_indices'][tail]
            same(np.bincount(slots, minlength=19).astype(np.int64), cp['pending_count'], 'initial queue counts')
            same(np.concatenate([pi[slots == s] for s in range(19)]), cp['pending'], 'initial queue entries')
            original = manual_original_restore(base, graph, cp)
            derived = module.EdgeDeliveryInterventionNetwork.from_checkpoint(*graph, cp,
                suppressed_edge_indices=edges, delivery_window=WINDOW)
            canonical = original.checkpoint()
            same(canonical, {k: cp[k] for k in canonical}, 'manual original restore')
            same(canonical, derived.checkpoint(), 'validated derived restore')
            derived.replace_selected_indices(expanded)
            expanded_initial = derived.checkpoint()
            same(expanded, expanded_initial['selected_indices'], 'expanded selection')
            same(canonical, dict(expanded_initial, selected_indices=selected), 'observation-only initial state')
            stem = str(spec['ordinal'])
            save(stem + '-input', dict(uniforms=u, probabilities=probabilities, rate_hz=rate,
                 event_indices=selected, logical_rng_before=int(stream['logical_rng_boundaries'][START]),
                 logical_rng_after=int(stream['logical_rng_boundaries'][END]),
                 intervention=derived.intervention_specification()))
            save(stem + '-original-initial', canonical)
            save(stem + '-derived-initial', expanded_initial)
            branch_outputs = {}
            branch_endpoints = {}
            timing = {}
            for kind, net in (('original', original), ('derived', derived)):
                budget()
                result['context'] = dict(ordinal=spec['ordinal'], phase=kind + '_advance', completed_prefix_end_tick=START)
                current_output = None
                started = time.perf_counter()
                executing = True
                current_output = net.advance(u, probabilities, log_selected_events=True, event_indices=selected)
                executing = False
                timing[kind] = time.perf_counter() - started
                save(stem + '-' + kind + '-output', current_output)
                endpoint = net.checkpoint()
                save(stem + '-' + kind + '-endpoint', endpoint)
                ck('complete_50_tick_branch', current_output['status'] == 'complete' and current_output['coherent_state']
                   and current_output['start_tick'] == START and current_output['end_tick'] == END
                   and current_output['completed_ticks'] == 50 and current_output['partial'] is None
                   and endpoint['tick'] == END, [spec['ordinal'], kind])
                branch_outputs[kind], branch_endpoints[kind] = current_output, endpoint
                budget()
            new_original, new_derived = branch_outputs['original'], branch_outputs['derived']
            same(new_original, {k: historical[k] for k in new_original}, 'all historical kernel fields')
            projected = {k: (v[:, original_columns] if k in TRACE_FIELDS else v) for k, v in new_derived.items()}
            same(new_original, projected, 'projected derived kernel fields')
            same(expanded, branch_endpoints['derived']['selected_indices'], 'derived endpoint selection')
            same(branch_endpoints['original'], dict(branch_endpoints['derived'], selected_indices=selected), 'full dynamical endpoint')
            for state in ('v', 's', 'h'):
                same(new_derived['selected_' + state][0, mbon_columns], cp[state][mbon], 'MBON initial ' + state)
                same(new_derived['selected_' + state][-1, mbon_columns], branch_endpoints['original'][state][mbon], 'MBON endpoint ' + state)
            ii, tt = new_derived['spike_indices'], new_derived['spike_ticks']
            last = cp['last'].copy()
            np.maximum.at(last, ii, tt)
            same(last, branch_endpoints['derived']['last'], 'new own last-spike history')
            pending = tt + 18 >= END
            slots, pi = (tt[pending] + 18) % 19, ii[pending]
            same(np.bincount(slots, minlength=19).astype(np.int64), branch_endpoints['derived']['pending_count'], 'new own queue counts')
            same(np.concatenate([pi[slots == s] for s in range(19)]), branch_endpoints['derived']['pending'], 'new own queue entries')
            same(u < probabilities, new_derived['candidate'], 'common candidate realization')
            applied = new_derived['candidate'].copy()
            source_lookup = np.full(len(graph[0]), -1, np.int32)
            source_lookup[selection['inputs']] = np.arange(36)
            source = source_lookup[ii] >= 0
            applied[tt[source] - START, source_lookup[ii[source]]] = False
            same(applied, new_derived['applied'], 'direct firing-tick exclusion')
            sidecar = derived.last_edge_intervention
            save(stem + '-zero-suppression-sidecar', sidecar)
            ck('no_suppression_at_any_tested_tick', sidecar['start_tick'] == START and sidecar['end_tick'] == END
               and sidecar['counts'].shape == (50, 3) and not sidecar['counts'].any()
               and sidecar['events'].shape == (0, 5) and sidecar['partial'] is None)
            result['trials'].append(dict(spec=spec, passed=True, start_tick=START, end_tick=END,
                original_selected_count=48, derived_selected_count=58, logged_selected_count=48,
                full_endpoint_equal=True, historical_kernel_fields_equal=True, expanded_trace_projection_equal=True,
                suppressed_deliveries=0, spike_count=len(ii), branch_seconds=timing))
            budget()
        ck('complete_six_case_scope', len(result['trials']) == 6)
        result['passed'] = True
    except (Exception, KeyboardInterrupt) as exc:
        result['errors'].append(dict(type=type(exc).__name__, message=str(exc), context=result['context'].copy(), traceback=traceback.format_exc()))
        if net is not None:
            try:
                failure_cp = net.checkpoint()
                if executing:
                    failure_cp['coherent_state'] = False
                    failure_cp['failure'] = dict(reason='Exception interrupted a branch before an output was returned',
                        completed_prefix_end_tick=START, mutable_state_phase='unknown partial attempted branch; no coherent endpoint claim')
                save('first-failure-state', failure_cp)
                if current_output is not None:
                    save('first-failure-returned-output', current_output)
            except (Exception, KeyboardInterrupt) as retention_error:
                result['errors'].append(dict(type=type(retention_error).__name__, message=str(retention_error), phase='failure_retention'))
    result['source_end'] = []
    for pin in plan['inputs']:
        try:
            after = record(ROOT / pin['path'])
            result['source_end'].append(after)
            reader.ck('source_stability', after == pin, pin['path'])
        except Exception as exc:
            reader.ck('source_stability', False, str(exc))
    reader.ck('plan_stability', record(PLAN) == plan_record)
    result.update(passed=result['passed'] and not reader.failures and not result['errors'], categories=reader.categories,
        check_count=sum(r['checked'] for r in reader.categories.values()), failures=reader.failures,
        decoded_archives=reader.decoded_archives, decoded_arrays=reader.decoded_arrays,
        completed_utc=datetime.now(timezone.utc).isoformat(), limits=plan['limits'])
    print(json.dumps(dict(result=atomic_json(RESULT, result), passed=result['passed'], checks=result['check_count'], errors=result['errors']), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--synthetic-results', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        if args.synthetic_results is None:
            parser.error('prepare requires --synthetic-results')
        prepare(args.synthetic_results)
    else:
        raise SystemExit(run())
