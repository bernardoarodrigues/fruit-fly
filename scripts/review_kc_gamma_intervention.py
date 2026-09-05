#!/usr/bin/env python3
"""Independent six-branch saved-data audit; no neural or producer imports."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import platform
import time
import traceback

import numpy as np

from review_inhibitory_recurrent_panel_trial import Audit, exact, ROOT
from review_navigation_ladder_mbon_inputs import incoming_edges, expanded_edges, WINDOWS, DECAY

EXPERIMENT = ROOT / 'validation/kc-gamma-intervention-plan.json'
PREFIX = ROOT / 'validation/kc-gamma-intervention-independent-review'
PLAN = Path(str(PREFIX) + '-plan.json')
RESULT = Path(str(PREFIX) + '.json')
ARRAYS = Path(str(PREFIX) + '-arrays.npz')
GRAPH = ROOT / 'data/processed/malecns_v1'
EXPERIMENT_SHA = '1136fe06fc96ad63ea676be69b7caefd7f8ce419f102488bf809d1b85f1e347b'
RESULT_SHA = '03fa6035d5dcf171178da590fa296ebd224b2423525c58f159219f0e4b97d8e9'
ORDINALS = [26, 29, 32, 35, 38, 41]
TARGETS = np.array(json.loads(EXPERIMENT.read_text())["selected_indices"], np.int32)
MASK = ROOT/"validation/kc-gamma-contact-mask-arrays.npz"


def load(path):
    return json.loads(Path(path).read_text())


def record(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            digest.update(block)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest.hexdigest())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


class ConditionalInputs:
    """Ordered p/h arithmetic from supplied emissions, never a voltage solver."""
    def __init__(self, graph, target_indices, n, p, h, tick, tail_t, tail_i, masked_rows, retained, window):
        self.g, self.targets, self.tick = graph, target_indices, tick
        self.p, self.h = p.copy(), h.copy()
        self.tail_t, self.tail_i = tail_t.copy(), tail_i.copy()
        self.source_position = np.full(n, -1, np.int64)
        self.source_position[graph['unique_sources']] = np.arange(len(graph['unique_sources']))
        self.mask = np.isin(graph['rows'], masked_rows)
        self.retained = np.zeros(len(graph['rows']),np.float64)
        self.retained[self.mask] = retained[np.searchsorted(masked_rows,graph['rows'][self.mask])]
        self.window = window
        self.arrivals = np.zeros((7, len(graph['rows'])), np.int64)
        self.modified = np.zeros_like(self.arrivals)

    def consume(self, ticks, indices, end):
        start = self.tick
        joined_t, joined_i = np.r_[self.tail_t, ticks], np.r_[self.tail_i, indices]
        delivery = joined_t + 18
        in_chunk = (delivery >= start) & (delivery < end)
        positions = self.source_position[joined_i]
        relevant = in_chunk & (positions >= 0)
        edges, lengths = expanded_edges(positions[relevant], self.g['source_ptr'])
        event_t = np.repeat(delivery[relevant], lengths)
        event_source = np.repeat(joined_i[relevant], lengths)
        columns = self.g['columns'][edges]
        weight = self.g['weights'][edges].astype(np.float64)
        modified = self.mask[edges] & (event_t >= self.window[0]) & (event_t < self.window[1])
        events = np.column_stack((event_t, event_source, self.g['rows'][edges], self.targets[columns],
                                  np.where(modified, 3, 0))).astype(np.int64)
        bins = np.searchsorted(WINDOWS, event_t, side='right') - 1
        np.add.at(self.arrivals, (bins, edges), 1)
        np.add.at(self.modified, (bins[modified], edges[modified]), 1)
        p, h = np.empty((end - start + 1, len(self.targets))), np.empty((end - start + 1, len(self.targets)))
        p[0], h[0] = self.p, self.h
        cuts = np.searchsorted(event_t, np.arange(start, end + 1), side='left')
        for j in range(end - start):
            self.p *= DECAY
            self.h *= DECAY
            sl = slice(cuts[j], cuts[j + 1])
            w, col = weight[sl].copy(), columns[sl]
            changed=modified[sl]
            w[changed]=self.retained[edges[sl]][changed]
            positive, negative = w >= 0, w < 0
            np.add.at(self.p, col[positive], w[positive])
            np.add.at(self.h, col[negative], -w[negative] * (1. / 23.))
            p[j + 1], h[j + 1] = self.p, self.h
        pending = delivery >= end
        self.tail_t, self.tail_i = joined_t[pending], joined_i[pending]
        self.tick = end
        return dict(p=p, h=h, events=events, modified_events=events[modified],
                    all_delivery_ticks=delivery[in_chunk], all_delivery_sources=joined_i[in_chunk])


def fixture():
    g = dict(rows=np.arange(4, dtype=np.int64), columns=np.array([0, 1, 1, 0]),
             weights=np.array([.275, -.825, 0., .1375], np.float32),
             unique_sources=np.array([0, 1]), source_ptr=np.array([0, 3, 4]))
    targets = np.array([2, 3])
    ticks = np.array([0, 1, 31, 32, 49, 50, 69], np.int64)
    indices = np.array([0, 0, 0, 1, 0, 0, 1], np.int32)
    initial_p, initial_h = np.array([.2, .3]), np.array([.1, .0])
    reduction = ConditionalInputs(g, targets, 4, initial_p, initial_h, 0,
                                  np.empty(0, np.int64), np.empty(0, np.int32), np.array([0, 3]), np.array([0.,.0234567890123]), [19, 68])
    pieces, events = [], []
    for end in (20, 50, 80, 100):
        mask = (ticks >= reduction.tick) & (ticks < end)
        value = reduction.consume(ticks[mask], indices[mask], end)
        pieces.append(value)
        events.extend(value['events'].tolist())
    p, h = np.empty((101, 2)), np.empty((101, 2))
    p[0], h[0] = initial_p, initial_h
    expected_events = []
    for tick in range(100):
        p[tick + 1], h[tick + 1] = p[tick] * DECAY, h[tick] * DECAY
        for emitted, source in zip(ticks, indices):
            if emitted + 18 != tick:
                continue
            for edge in range(g['source_ptr'][source], g['source_ptr'][source + 1]):
                modified = edge in (0, 3) and 19 <= tick < 68
                expected_events.append([tick, int(source), edge, int(targets[g['columns'][edge]]), 3 if modified else 0])
                w, column = float(g['weights'][edge]), g['columns'][edge]
                if modified:w={0:0.,3:.0234567890123}[edge]
                if w < 0:
                    h[tick + 1, column] += -w * (1. / 23.)
                else:
                    p[tick + 1, column] += w
    assert exact(p, np.concatenate([pieces[0]['p']] + [v['p'][1:] for v in pieces[1:]]))
    assert exact(h, np.concatenate([pieces[0]['h']] + [v['h'][1:] for v in pieces[1:]]))
    assert events == expected_events
    assert any(t == 19 and d == 3 for t, s, e, target, d in events)
    assert all(d == 0 for t, s, e, target, d in events if t == 68)
    assert reduction.arrivals.sum() == len(expected_events)
    assert reduction.modified.sum() == sum(e[-1] == 3 for e in expected_events)
    return dict(passed=True, checks=7, scope='Manufactured supplied events only: float32 promotion, ordered positive/negative/zero additions, chunk/18tick delay, half-open modification boundaries, exact float64 partial retained weight')


def prepare():
    if any(p.exists() for p in (PLAN, RESULT, ARRAYS)):
        raise FileExistsError('Preserve first independent audit artifacts')
    pure = fixture()
    experiment = load(EXPERIMENT)
    run = ROOT / experiment['run_dir']
    parent = load(run / 'results.json')
    assert record(EXPERIMENT)['sha256'] == EXPERIMENT_SHA and record(run / 'results.json')['sha256'] == RESULT_SHA
    assert parent['passed'] and parent['complete'] and not parent['errors']
    assert [s['ordinal'] for s in experiment['trials']] == ORDINALS
    paths = [Path(__file__), MASK, ROOT / 'scripts/review_inhibitory_recurrent_panel_trial.py',
             ROOT / 'scripts/review_navigation_ladder_mbon_inputs.py', EXPERIMENT,
             run / 'results.json', run / 'terminal.json', GRAPH / 'manifest.json',
             GRAPH / 'neurons.feather', GRAPH / 'contact_counts.npy',
             ROOT / 'validation/navigation-ladder-mbon-input-independent-review.json']
    paths += [ROOT / p['path'] for p in experiment['inputs']]
    for trial in parent['trials']:
        paths += [ROOT / trial['terminal']['path'], ROOT / trial['result']['path']]
    pins = [record(p) for p in dict.fromkeys(paths)]
    plan = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), inputs=pins,
        experiment_plan=record(EXPERIMENT), parent_result=record(run / 'results.json'), trials=experiment['trials'],
        start_tick=5000, end_tick=30000, chunks_per_trial=500, targets=TARGETS.tolist(),
        methods=['Independent immutable archive decoder verifies descriptors, hashes, dtype/shape and packed spike restoration.',
                 'All actual uniforms/candidate/applied masks, ordered spikes and refractory state are checked; input rates reuse the frozen schedule without regenerating RNG.',
                 'Restore original5000 full state exactly except declared observation selection, then reconstruct all-neuron seven-window counts, last-spike state and full pending queues at every checkpoint.',
                 'Join every source emission to original CSR incoming edges for73 observed cells at emission+18; replace only declared positive contact-weight terms at ticks[5000,15000). Compare every logged arrival for25 event targets; reconstruct all270710 affected edges globally from source emissions and verify zero/partial counts and removed p-weight sums.',
                 'Reconstruct73 target p/h in original float64 operation order with float32 stored weights, decay before arrival, H1 receives throughout refractory/reset; compare all25001 trace rows bitwise and all6 checkpoints.',
                 'Reconstruct global edge counts by source out-degree and sign, without propagating state; verify no blocked/unavailable counts and the accepted deliveries regardless of retained weight.',
                 'Verify73 selected-state continuity, availability, threshold/firing/reset/direct-input phase identities; numerical interval solutions are independently reviewed elsewhere.'],
        outputs=dict(result=str(RESULT.relative_to(ROOT)), arrays=str(ARRAYS.relative_to(ROOT))),
        array_schema='Per trial: full7xN window_counts, observed p/h25001x73, incoming edge arrival/modified7xE, and exact postbranch observed-cell tick/index records. Common target/edge identities.',
        manufactured_preflight=pure, environment=dict(python=platform.python_version(), numpy=np.__version__),
        failure='Preserve first failure/context and completed arrays/results, stop the batch, do not change the frozen checker or rerun a neural model.',
        limits=['Conditional synaptic-state reconstruction uses the newly emitted recurrent spike history; no full neural/voltage re-integration occurs.',
                'The initial5000 prefix is reused and pinned, not resimulated. Full-population voltage between checkpoints is not independently reconstructed.',
                'Quadrature/ODE/order64 accuracy and threshold ambiguity are a separate required review; this receipt alone is not scientific or physiological acceptance.',
                'The pathway was selected using the same prior six controls; the intervention does not establish unique causation, biological KC ablation, a calibrated receptor mechanism or navigation.'])
    write(PLAN, plan)
    print(json.dumps(record(PLAN)))


def run():
    if RESULT.exists() or ARRAYS.exists():
        raise FileExistsError('Preserve first review execution')
    plan, experiment = load(PLAN), load(EXPERIMENT)
    plan_record = record(PLAN)
    run, old = ROOT / experiment['run_dir'], ROOT / experiment['prior_run_dir']
    audit = Audit()
    result = dict(schema=1, plan=plan_record, passed=False, completed_trials=[], errors=[], context={'stage': 'preflight'},
                  source_start=plan['inputs'], limits=plan['limits'])
    arrays = {}
    started = time.perf_counter()

    def ck(name, value, context=None):
        if not audit.ck(name, value, context):
            raise AssertionError(name + ': ' + str(context))

    def same(name, a, b, context=None):
        ck(name, exact(a, b), context)

    def pending(t, i):
        slot = (t + 18) % 19
        return np.bincount(slot, minlength=19).astype(np.int64), np.concatenate([i[slot == j] for j in range(19)])

    try:
        for pin in plan['inputs']:
            ck('frozen_input', record(ROOT / pin['path']) == pin, pin['path'])
        ck('fixed_contract', experiment['start_tick'] == 5000 and experiment['end_tick'] == 30000
           and experiment['chunk_ticks'] == 50 and experiment['threads'] == 4
           and experiment['selected_indices'] == TARGETS.tolist() and experiment['window_edges_ticks'] == WINDOWS.tolist()
           and experiment['delivery_window_ticks'] == [5000, 15000])
        parent, terminal = load(run / 'results.json'), load(run / 'terminal.json')
        ck('parent_publication', parent['passed'] and parent['complete'] and not parent['errors']
           and terminal['passed'] and terminal['complete'] and terminal['status'] == 'complete'
           and terminal['results'] == record(run / 'results.json') and parent['plan'] == record(EXPERIMENT))
        ck('exact_six_cases', [x['spec'] for x in parent['trials']] == experiment['trials'])
        for item in parent['trials']:
            ck('parent_child_pins', audit.record(item['terminal']) and audit.record(item['result']))
        manifest = load(GRAPH / 'manifest.json')
        for name, pin in (manifest['arrays'] | manifest['metadata']).items():
            ck('original_graph_hash', record(GRAPH / name)['sha256'] == pin['sha256'], name)
        graph = incoming_edges(TARGETS)
        with np.load(MASK, allow_pickle=False) as z:
            mask_rows=z['edge_indices'].copy();retained=z['retained_weight'].copy();mask_sources=z['source_indices'].copy();mask_baseline=z['baseline_weight'].copy()
        ck('positive_mask',len(mask_rows)==270710 and np.all(mask_baseline>0) and np.all(retained>=0) and np.all(retained<mask_baseline))
        n = experiment['neurons']
        ptr = np.load(GRAPH / 'indptr.npy', mmap_mode='r')
        weights = np.load(GRAPH / 'weights.npy', mmap_mode='r')
        degrees = np.empty((n, 3), np.int64)
        for sign, include in enumerate((weights < 0, weights == 0, weights > 0)):
            cumulative = np.r_[0, np.cumsum(include, dtype=np.int64)]
            degrees[:, sign] = cumulative[ptr[1:]] - cumulative[ptr[:-1]]
        same('mask_baseline_graph_weights',weights[mask_rows].astype(np.float64),mask_baseline)
        same('mask_source_csr',np.searchsorted(ptr,mask_rows,side='right')-1,mask_sources)
        modified_degrees=np.column_stack([np.bincount(mask_sources[retained==0],minlength=n),np.bincount(mask_sources[retained>0],minlength=n)]).astype(np.int64)
        removed_by_source=np.bincount(mask_sources,weights=mask_baseline-retained,minlength=n)
        ck('degree_partition', np.array_equal(degrees.sum(axis=1), np.diff(ptr)))
        del cumulative, include
        selection = audit.archive(old / 'selection')
        selected = np.array(experiment['selected_indices'], np.int32)
        inputs = selection['inputs']
        target_cols = np.searchsorted(selected, TARGETS)
        same('expanded_selection', selected, np.unique(np.r_[selection['selected'], experiment['event_indices']]).astype(np.int32))
        source_lookup = np.full(n, -1, np.int32)
        source_lookup[inputs] = np.arange(len(inputs))
        selected_lookup = np.full(n, -1, np.int32)
        selected_lookup[selected] = np.arange(len(selected))
        expected_refractory = np.full(n, 22, np.int64)
        expected_refractory[inputs] = 0
        arrays.update(target_indices=TARGETS, selected_indices=selected, edge_indices=graph['rows'],
                      edge_source_indices=graph['sources'], edge_target_columns=graph['columns'],
                      modified_edge_indices=mask_rows, window_edges_ticks=WINDOWS)
        for spec in experiment['trials']:
            ordinal = spec['ordinal']
            result['context'] = dict(stage='trial_preflight', ordinal=ordinal)
            directory = run / spec['name']
            report, terminal = load(directory / 'result.json'), load(directory / 'terminal.json')
            ck('trial_complete', report['passed'] and report['complete'] and not report['errors']
               and report['spec'] == spec and report['completed_tick'] == report['last_durable_chunk_end_tick'] == 30000
               and terminal['passed'] and terminal['complete'] and terminal['result'] == record(directory / 'result.json')
               and report['plan'] == record(EXPERIMENT), ordinal)
            ck('no_failure_or_partial_files', not list(directory.glob('*failure*')) and not list(directory.glob('*failed*'))
               and not list(directory.glob('*.publish.lock')) and not list(directory.glob('*.tmp-*')), ordinal)
            for pin in report['artifacts']:
                ck('raw_artifact_pin', audit.record(pin), pin['path'])
            ck('exact_chunk_population', sorted(p.name for p in directory.glob('chunk-*.complete.json'))
               == [f'chunk-{j:04d}.complete.json' for j in range(100, 600)], ordinal)
            original = audit.archive(old / spec['name'] / 'checkpoint-05000')
            initial = audit.archive(directory / 'checkpoint-05000')
            for key in ('v', 's', 'h', 'last', 'refractory', 'blocked', 'pending', 'pending_count', 'input_indices', 'window_counts_observed'):
                same('initial_full_state', initial[key], original[key], [ordinal, key])
            same('initial_declared_selection', initial['selected_indices'], selected, ordinal)
            stream = audit.archive(old / f'input-seed{spec["seed"]}')
            u, states = stream['uniforms'], stream['logical_rng_boundaries']
            counts, last = initial['window_counts_observed'].copy(), initial['last'].copy()
            tail = audit.archive(old / spec['name'] / 'chunk-0099')
            keep = tail['spike_ticks'] + 18 >= 5000
            tail_t, tail_i = tail['spike_ticks'][keep], tail['spike_indices'][keep]
            reduction = ConditionalInputs(graph, TARGETS, n, initial['s'][TARGETS], initial['h'][TARGETS],
                                          5000, tail_t, tail_i, mask_rows, retained, [5000, 15000])
            p_trace, h_trace = np.full((25001, len(TARGETS)), np.nan), np.full((25001, len(TARGETS)), np.nan)
            p_trace[0], h_trace[0] = reduction.p, reduction.h
            name = f'trial_{ordinal}_'
            arrays[name + 'p'], arrays[name + 'h'], arrays[name + 'window_counts'] = p_trace, h_trace, counts
            own_t, own_i = [], []
            totals = dict(spikes_after_branch=0, modified_deliveries=0, candidate_events=0, applied_events=0,
                          source_spikes=0, incoming_target_arrivals=0, accepted_target_arrivals=0)
            prior = {k: initial[k][selected].copy() for k in ('v', 's', 'h')}
            minimum_voltage = np.inf

            def checkpoint(tick, cp=None):
                cp = audit.archive(directory / f'checkpoint-{tick:05d}') if cp is None else cp
                ck('checkpoint_clock_identity', cp['tick'] == tick and cp['time_ms'] == tick * .1
                   and cp['coherent_state'] and cp['failure'] is None and cp['arm'] == 'H1' and cp['seed'] == spec['seed']
                   and cp['graph_sha256'] == experiment['graph_sha256'] and cp['logical_rng_state'] == int(states[tick]), [ordinal, tick])
                ck('checkpoint_parameters', cp['parameters'] == original['parameters'] and cp['version'] == original['version'] == 1, [ordinal, tick])
                same('checkpoint_refractory', cp['refractory'], expected_refractory, [ordinal, tick])
                same('checkpoint_selection', cp['selected_indices'], selected, [ordinal, tick])
                same('checkpoint_input_population', cp['input_indices'], inputs, [ordinal, tick])
                ck('checkpoint_source_unblocked', not cp['blocked'].any(), [ordinal, tick])
                same('full_checkpoint_counts', cp['window_counts_observed'], counts, [ordinal, tick])
                same('full_checkpoint_last', cp['last'], last, [ordinal, tick])
                pc, pi = pending(reduction.tail_t, reduction.tail_i)
                same('full_checkpoint_pending_count', cp['pending_count'], pc, [ordinal, tick])
                same('full_checkpoint_pending', cp['pending'], pi, [ordinal, tick])
                same('conditional_checkpoint_p', cp['s'][TARGETS], reduction.p, [ordinal, tick])
                same('conditional_checkpoint_h', cp['h'][TARGETS], reduction.h, [ordinal, tick])
                for k in ('v', 's', 'h'):
                    same('selected_checkpoint_state', cp[k][selected], prior[k], [ordinal, tick, k])
                    ck('full_checkpoint_finite_state', cp[k].dtype == np.float64 and cp[k].shape == (n,) and np.isfinite(cp[k]).all(), [ordinal, tick, k])
                ck('full_checkpoint_H1_bounds', np.all(cp['v'] >= -75. - 1e-10) and np.all(cp['s'] >= 0) and np.all(cp['h'] >= 0), [ordinal, tick])
                ins = cp['intervention_specification']
                same('checkpoint_edge_mask', ins['modified_edge_indices'], mask_rows, [ordinal, tick])
                same('checkpoint_retained_weights',ins['retained_weights'],retained,[ordinal,tick])
                ck('checkpoint_intervention_spec', ins['delivery_window_ticks'] == [5000,15000] and ins['graph_sha256']==experiment['graph_sha256'],[ordinal,tick])

            checkpoint(5000, initial)
            for chunk in range(100, 600):
                start, end = chunk * 50, chunk * 50 + 50
                result['context'] = dict(stage='chunk', ordinal=ordinal, chunk=chunk, last_checked_tick=start)
                out = audit.archive(directory / f'chunk-{chunk:04d}')
                ck('complete_chunk_clock', out['status'] == 'complete' and out['coherent_state'] and out['failure'] is None
                   and out['partial'] is None and out['start_tick'] == start and out['end_tick'] == end
                   and out['completed_ticks'] == out['requested_ticks'] == 50, [ordinal, chunk])
                ii, tt = out['spike_indices'], out['spike_ticks']
                ck('ordered_spike_domain', ii.dtype == np.int32 and tt.dtype == np.int64 and ii.shape == tt.shape
                   and np.all((tt >= start) & (tt < end)) and np.all((ii >= 0) & (ii < n))
                   and (len(tt) < 2 or np.all((tt[1:] > tt[:-1]) | ((tt[1:] == tt[:-1]) & (ii[1:] > ii[:-1])))), [ordinal, chunk])
                phase = int(np.searchsorted([5000, 10000, 15000], start, side='right'))
                probability = np.full(len(inputs), experiment['condition_rates_hz'][spec['condition']][phase]) * .1 / 1000.
                same('exact_input_candidates', out['candidate'], u[start:end] < probability, [ordinal, chunk])
                source = source_lookup[ii] >= 0
                applied = out['candidate'].copy()
                applied[tt[source] - start, source_lookup[ii[source]]] = False
                same('actual_direct_application', out['applied'], applied, [ordinal, chunk])
                if start >= 15000:
                    ck('input_off_masks', not out['candidate'].any() and not out['applied'].any(), [ordinal, chunk])
                fired = np.zeros((50, len(selected)), np.bool_)
                selected_spikes = selected_lookup[ii] >= 0
                fired[tt[selected_spikes] - start, selected_lookup[ii[selected_spikes]]] = True
                current_last = last[selected].copy()
                available = np.empty_like(fired)
                for j, tick in enumerate(range(start, end)):
                    available[j] = tick - current_last >= expected_refractory[selected]
                    current_last[fired[j]] = tick
                for key, value in (('selected_available', available), ('selected_fired', fired),
                                   ('selected_direct_available', available & ~fired),
                                   ('selected_delivery_available', available & ~fired),
                                   ('selected_synaptic_available', np.ones_like(fired))):
                    same('selected_masks', out[key], value, [ordinal, chunk, key])
                pre = out['selected_prethreshold_v']
                ck('selected_state_domain', pre.shape == (50, len(selected)) and np.isfinite(pre).all()
                   and all(out['selected_' + k].shape == (51, len(selected)) and out['selected_' + k].dtype == np.float64
                           and np.isfinite(out['selected_' + k]).all() for k in ('v', 's', 'h'))
                   and np.all(out['selected_s'] >= 0) and np.all(out['selected_h'] >= 0)
                   and np.all(out['selected_v'] >= -75. - 1e-10), [ordinal, chunk])
                same('threshold_stamps', fired, available & (pre > -45.), [ordinal, chunk])
                ck('unavailable_reset', np.all(pre[~available] == -52.), [ordinal, chunk])
                after = pre.copy()
                for column, index in enumerate(selected):
                    src = source_lookup[index]
                    if src >= 0:
                        after[:, column] += out['applied'][:, src] * 68.75
                after[fired] = -52.
                same('selected_postexternal_reset', out['selected_v'][1:], after, [ordinal, chunk])
                for key in prior:
                    same('selected_trace_continuity', out['selected_' + key][0], prior[key], [ordinal, chunk, key])
                reduced = reduction.consume(tt, ii, end)
                for state, trace, saved_state in (('p', p_trace, 's'), ('h', h_trace, 'h')):
                    same('complete_observed_conditional_' + state, out['selected_' + saved_state][:, target_cols], reduced[state], [ordinal, chunk])
                    trace[start - 5000:end - 5000 + 1] = reduced[state]
                result['context']['conditional_trace_end_tick'] = end
                logged=reduced['events'][np.isin(reduced['events'][:,3],experiment['event_indices'])]
                same('every_ordered_logged_target_arrival',out['selected_events'],logged,[ordinal,chunk])
                ck('event_target_schema',out['schema']['event_graph_indices']==experiment['event_indices'],[ordinal,chunk])
                side=out['contact_intervention'];dticks=reduced['all_delivery_ticks'];dsource=reduced['all_delivery_sources']
                active=(dticks>=5000)&(dticks<15000)
                modified_counts=np.column_stack([np.bincount(dticks[active]-start,weights=modified_degrees[dsource[active],j],minlength=50) for j in range(2)]).astype(np.int64)
                removed_sum=np.bincount(dticks[active]-start,weights=removed_by_source[dsource[active]],minlength=50)
                same('all_modified_delivery_counts',side['counts'],modified_counts,[ordinal,chunk])
                ck('all_removed_weight_sums',np.allclose(side['removed_weight_sum'],removed_sum,rtol=1e-11,atol=1e-9),[ordinal,chunk])
                ck('modification_sidecar_clock',side['start_tick']==start and side['end_tick']==end and side['partial'] is None,[ordinal,chunk])
                visited = np.zeros((50, 3), np.int64)
                for sign in range(3):
                    np.add.at(visited[:, sign], reduced['all_delivery_ticks'] - start, degrees[reduced['all_delivery_sources'], sign])
                edge_counts = out['per_tick']['edge_counts']
                same('all_graph_signed_edge_visits', edge_counts[:, 0], visited, [ordinal, chunk])
                same('all_graph_signed_edge_acceptance', edge_counts[:, 1], visited, [ordinal, chunk])
                ck('no_reclassified_block_or_unavailability', not edge_counts[:, 2:].any(), [ordinal, chunk])
                if len(ii):
                    order = np.argsort(ii, kind='stable')
                    si, st = ii[order], tt[order]
                    continuing = si[1:] == si[:-1]
                    first = np.r_[True, ~continuing]
                    ck('full_spike_refractory_history', np.all(st[1:][continuing] - st[:-1][continuing] >= expected_refractory[si[1:][continuing]])
                       and np.all(st[first] - last[si[first]] >= expected_refractory[si[first]]), [ordinal, chunk])
                np.add.at(counts, (np.searchsorted(WINDOWS, tt, side='right') - 1, ii), 1)
                np.maximum.at(last, ii, tt)
                result['context']['counts_end_tick'] = end
                for key in prior:
                    prior[key] = out['selected_' + key][-1].copy()
                target_spike = np.isin(ii, TARGETS)
                own_t.append(tt[target_spike].copy())
                own_i.append(ii[target_spike].copy())
                totals['spikes_after_branch'] += len(ii)
                totals['modified_deliveries'] += int(side['counts'].sum())
                totals['candidate_events'] += int(out['candidate'].sum())
                totals['applied_events'] += int(out['applied'].sum())
                totals['source_spikes'] += int(source.sum())
                totals['incoming_target_arrivals'] += len(reduced['events'])
                totals['accepted_target_arrivals'] += len(reduced['events'])
                diagnostics = out['per_tick']
                ck('finite_complete_phase_diagnostics', not diagnostics['phase_nonfinite_count'].any()
                   and not diagnostics['state_invalid_count'].any() and not diagnostics['phase_below_reversal_count'].any()
                   and np.all(diagnostics['phase_reached'] == 5), [ordinal, chunk])
                minimum_voltage = min(minimum_voltage, float(diagnostics['phase_min_mv'].min()))
                if end in experiment['checkpoint_ticks']:
                    checkpoint(end)
            ck('reported_trial_totals', totals['spikes_after_branch'] == report['spikes_after_branch']
               and totals['modified_deliveries'] == report['modified_deliveries'], ordinal)
            arrays[name + 'edge_arrivals'] = reduction.arrivals
            arrays[name + 'edge_modified'] = reduction.modified
            arrays[name + 'edge_accepted'] = reduction.arrivals
            arrays[name + 'observed_spike_ticks'] = np.concatenate(own_t)
            arrays[name + 'observed_spike_indices'] = np.concatenate(own_i)
            result['completed_trials'].append(dict(spec=spec, passed=True, checkpoint_ticks=experiment['checkpoint_ticks'],
                totals=totals, minimum_recorded_global_voltage_mv=minimum_voltage,
                complete_observed_p_h_bitwise=True, observed_window_counts=counts[:, TARGETS].tolist(),
                source_window_counts=counts[:, inputs].sum(axis=1).tolist(),
                whole_graph_window_counts=counts.sum(axis=1).tolist()))
        ck('complete_six_trial_review', len(result['completed_trials']) == 6)
        result['passed'] = True
    except (Exception, KeyboardInterrupt) as exc:
        result['errors'].append(dict(type=type(exc).__name__, message=str(exc), context=result['context'].copy(), traceback=traceback.format_exc()))
    with ARRAYS.open('xb') as stream:
        np.savez_compressed(stream, **arrays)
    result['array_artifact'] = record(ARRAYS)
    result['source_end'] = []
    for pin in plan['inputs']:
        try:
            current = record(ROOT / pin['path'])
            result['source_end'].append(current)
            audit.ck('source_stability', current == pin, pin['path'])
        except Exception as exc:
            audit.ck('source_stability', False, str(exc))
    audit.ck('review_plan_stability', record(PLAN) == plan_record)
    result.update(passed=result['passed'] and not audit.failures and not result['errors'],
        check_count=sum(c['checked'] for c in audit.categories.values()), categories=audit.categories, failures=audit.failures,
        decoded_archives=audit.decoded_archives, decoded_arrays=audit.decoded_arrays,
        wall_seconds=time.perf_counter() - started, completed_utc=datetime.now(timezone.utc).isoformat(),
        numerical_reference_review='Separate scalar reference calculation; this receipt checks saved state/event/count semantics only. Independent implementation by root agent, not a separate reviewer.')
    write(RESULT, result)
    print(json.dumps(dict(result=record(RESULT), passed=result['passed'], checks=result['check_count'], errors=result['errors']), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['fixture', 'prepare', 'run'])
    args = parser.parse_args()
    if args.action == 'fixture':
        print(json.dumps(fixture()))
    elif args.action == 'prepare':
        prepare()
    else:
        raise SystemExit(run())
