#!/usr/bin/env python3
"""Independent saved-data audit. Does not import or execute neural producers.

Prospective oracle selection: ALL available intervals of ALL 48 selected cells
in H0 and H1, across all 500 ticks. Fixed tolerance 1e-8 mV. No sampling,
parameter fitting, trajectory continuation, or computation of new spikes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

import numpy as np
import scipy
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'validation/inhibitory-recurrent-performance-v2'
PLAN = ROOT / 'validation/inhibitory-recurrent-performance-plan-v2.json'
OUTPUT = ROOT / 'validation/inhibitory-recurrent-performance-independent-review.json'
ARMS = ('reference', 'C0', 'C1', 'H0', 'H1')
STATE_KEYS = ('v', 's', 'h', 'last', 'refractory', 'blocked', 'pending_count', 'pending')
TOL = 1e-8


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def array_sha(a):
    return hashlib.sha256(a.tobytes()).hexdigest()


def exact(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def state_digest(s):
    h = hashlib.sha256(str(s['tick']).encode())
    for key in STATE_KEYS:
        a = s[key]
        h.update(key.encode())
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def hybrid_voltage(v0, p0, h0):
    """Time-domain integrating factor in ms; no producer solver import.

    y=v+75; A(t)=t/20 + h0*5/20*(1-exp(-t/5)).
    y(dt)=y0 exp(-A(dt)) + integral exp(A(u)-A(dt))
          * (23+p0 exp(-u/5))/20 du.
    Stable differences keep every exponent nonpositive for h0>=0.
    """
    dt = .1
    terminal_attenuation = dt / 20 + h0 * .25 * (-math.expm1(-dt / 5))

    def forcing(u):
        remaining = (dt-u) / 20 + h0 * .25 * math.exp(-u/5) * (-math.expm1(-(dt-u)/5))
        return math.exp(-remaining) * (23 + p0 * math.exp(-u/5)) / 20

    value, error = quad(forcing, 0., dt, epsabs=1e-11, epsrel=1e-12, limit=200)
    return -75 + (v0 + 75) * math.exp(-terminal_attenuation) + value, error


def review():
    if OUTPUT.exists():
        raise RuntimeError('Refusing to overwrite the first saved review attempt')
    result = dict(schema=1, started_utc=datetime.now(timezone.utc).isoformat(),
                  reviewer_script=dict(path=str(Path(__file__).relative_to(ROOT)), sha256=sha(__file__)),
                  scope='Saved data and source inspection only; no producer imports or neural runs',
                  oracle_selection='All selected H0/H1 intervals with availability derived from own saved spikes',
                  oracle_tolerance_mv=TOL, scipy_quad=dict(epsabs=1e-11, epsrel=1e-12, limit=200),
                  environment=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__),
                  inputs={}, checks=[], arms={}, exceptions=[])

    def ck(name, value, detail=None):
        item = dict(name=name, passed=bool(value))
        if detail is not None:
            item['detail'] = detail
        result['checks'].append(item)
        return bool(value)

    def pin(path, expected=None):
        path = Path(path)
        rec = dict(bytes=path.stat().st_size, sha256=sha(path))
        name = str(path.relative_to(ROOT))
        result['inputs'][name] = rec
        if expected is not None:
            ck('hash:' + name, rec == expected)
        return rec

    def load(stem):
        stem = Path(stem)
        meta = json.loads(stem.with_suffix('.json').read_text())
        with np.load(stem.with_suffix('.npz'), allow_pickle=False) as z:
            used = []
            valid = True

            def decode(x):
                nonlocal valid
                if isinstance(x, dict) and set(x) == {'array', 'shape', 'dtype'}:
                    a = z[x['array']]
                    used.append(x['array'])
                    valid &= list(a.shape) == x['shape'] and str(a.dtype) == x['dtype']
                    return a
                if isinstance(x, dict):
                    return {k: decode(v) for k, v in x.items()}
                if isinstance(x, list):
                    return [decode(v) for v in x]
                return x

            out = decode(meta)
            ck('archive_schema:' + str(stem.relative_to(ROOT)), valid and set(used) == set(z.files))
        return out

    try:
        plan = json.loads(PLAN.read_text())
        producer = json.loads((DATA/'results.json').read_text())
        pin(PLAN)
        pin(DATA/'results.json')
        ck('producer_plan_hash', sha(PLAN) == producer['plan_sha256'])
        ck('producer_complete_and_280_checks', producer['complete'] and not producer['errors']
           and len(producer['checks']) == 280 and all(c['passed'] for c in producer['checks']))
        ck('declared_scope', plan['execution_order'] == list(ARMS) and plan['seed'] == 11
           and plan['duration_ms'] == 50 and plan['dt_ms'] == .1 and plan['chunk_ms'] == 5
           and plan['rate_hz'] == 11)
        for name, rec in plan['sources'].items():
            pin(ROOT/name, rec)
        for name, rec in producer['artifacts'].items():
            pin(ROOT/name, rec)
        actual = {str(p.relative_to(ROOT)) for p in DATA.rglob('*') if p.is_file()
                  and p.name not in ('results.json', 'progress.json')}
        ck('producer_artifact_inventory_complete', actual == set(producer['artifacts']))
        failed = json.loads((ROOT/'validation/inhibitory-recurrent-performance/results.json').read_text())
        ck('original_compilation_failure_preserved', not failed['complete'] and not failed['arms']
           and any('TypingError' in e.get('type', '') for e in failed['errors']))

        graph = ROOT/'data/processed/malecns_v1'
        ids, ptr, targets, weights = [np.load(graph/(n+'.npy'), mmap_mode='r')
                                      for n in ('neuron_ids', 'indptr', 'targets', 'weights')]
        n = len(ids)
        gh = hashlib.sha256()
        for a in (ids, ptr, targets, weights):
            gh.update(str(a.shape).encode())
            gh.update(memoryview(a).cast('B'))
        ck('graph_array_identity', gh.hexdigest() == plan['graph_sha256'] and n == 166700
           and len(weights) == 25582938 and weights.dtype == np.float32)

        stream = load(DATA/'input-stream')
        selection = load(DATA/'selection')
        inputs, selected = stream['input_indices'], selection['indices']
        op = json.loads((ROOT/'validation/or42a-summary-plan.json').read_text())
        index = {int(v): i for i, v in enumerate(ids)}
        motor_ids = [v for group in op['motor_groups'].values() for v in group]
        expected_selected = np.array(sorted(set(inputs.tolist()+[index[v] for v in [67052, 13314]+motor_ids])), np.int32)
        ck('exact_ordered_inputs_and_selection', len(inputs) == 36 and len(selected) == 48
           and exact(inputs, np.array(op['source_graph_indices'], np.int32))
           and exact(ids[inputs], np.array(op['source_body_ids'], np.int64))
           and exact(selected, expected_selected) and exact(ids[selected], selection['body_ids'])
           and exact(ids[inputs], selection['input_body_ids']))
        col = np.full(n, -1, np.int32)
        col[selected] = np.arange(len(selected))
        input_col = {int(cell): i for i, cell in enumerate(inputs)}

        # Independent public arithmetic specification, outside any neural module.
        state = int(np.random.SeedSequence(11).generate_state(1, dtype=np.uint64)[0]) or 1
        mask = (1 << 64)-1
        u = np.empty((500, 36), np.float64)
        rng = np.empty(501, np.uint64)
        rng[0] = state
        for tick in range(500):
            for j in range(36):
                state = (state ^ (state >> 12)) & mask
                state = (state ^ (state << 25)) & mask
                state = (state ^ (state >> 27)) & mask
                u[tick, j] = (((state*2685821657736338717) & mask) >> 11) / (2**53)
            rng[tick+1] = state
        probability = np.full(36, 11.) * .1 / 1000.
        candidates = u < probability
        ck('independent_uniforms_rng_and_probabilities', exact(u, stream['uniforms'])
           and exact(rng, stream['logical_rng_boundaries']) and exact(probability, stream['probabilities']))
        result['input_summary'] = dict(candidate_count=int(candidates.sum()), draws=int(u.size),
            candidate_sha256=array_sha(candidates), rng_start=int(rng[0]), rng_end=int(rng[-1]),
            selected_ids=ids[selected].tolist(), input_ids=ids[inputs].tolist())

        old_path = ROOT/plan['old_trial']
        with np.load(old_path/'trace.npz', allow_pickle=False) as old:
            old_ticks_all = old['all_spike_ticks']
            keep = old_ticks_all < 500
            old_ticks = old_ticks_all[keep]
            old_indices = old['all_spike_graph_indices'][keep]
            req = old['requested_arrival_ticks'] < 500
            old_candidates, old_applied = np.zeros((500, 36), bool), np.zeros((500, 36), bool)
            q, j = old['requested_arrival_ticks'][req], old['requested_arrival_source_column'][req]
            old_candidates[q, j] = True
            old_applied[q, j] = old['applied_direct_voltage_arrival'][req]
            ck('archived_input_rng_start', int(old['initial_rng_state'][0]) == int(rng[0]))
        old_samples = [json.loads(s) for s in (old_path/'samples.jsonl').read_text().splitlines()][:10]
        ck('archived_113_spikes_candidates', len(old_ticks) == 113 and exact(candidates, old_candidates))
        reference_final = reference_initial = reference_chunks = None

        for arm in ARMS:
            print('Reviewing saved arm '+arm, flush=True)
            initial, final = load(DATA/arm/'initial'), load(DATA/arm/'final')
            chunks = [load(DATA/arm/f'chunk-{j:02d}') for j in range(10)]
            ar = result['arms'][arm] = dict()
            meta = next(x for x in producer['arms'] if x['arm'] == arm)
            ck(arm+':endpoint_clock', initial['tick'] == 0 and final['tick'] == 500
               and initial['coherent_state'] and final['coherent_state'] and meta['complete'])
            rf = np.full(n, 22, np.int64)
            rf[inputs] = 0
            ck(arm+':initial_state_and_fixed_masks', (initial['v'] == -52).all()
               and not initial['s'].any() and not initial['h'].any()
               and (initial['last'] == -(2**60)).all() and not initial['blocked'].any()
               and not initial['pending_count'].any() and len(initial['pending']) == 0
               and exact(initial['refractory'], rf) and exact(final['refractory'], rf)
               and exact(initial['blocked'], final['blocked']))
            ck(arm+':endpoint_provenance', all(s['graph_sha256'] == plan['graph_sha256']
               and s['seed'] == 11 for s in (initial, final))
               and initial['logical_rng_state'] == int(rng[0]) and final['logical_rng_state'] == int(rng[-1]))
            ck(arm+':endpoint_finite', all(np.isfinite(s[k]).all() for s in (initial, final) for k in ('v', 's', 'h')))
            if arm.startswith('H'):
                ck(arm+':endpoint_hybrid_bounds', (final['v'] >= -75-1e-10).all()
                   and (final['s'] >= 0).all() and (final['h'] >= 0).all())
            else:
                ck(arm+':zero_conductance_current_arm', not final['h'].any())
            if arm == 'reference':
                reference_final, reference_initial, reference_chunks = final, initial, chunks
                original = final['original_complete_state']
                ck('reference:original_rng_and_current', int(original['rng_state'][0]) == int(rng[-1])
                   and not original['current_mv'].any() and exact(original['previous_drive'], inputs))
                for canonical, original_key in [('v', 'voltage_mv'), ('s', 'synaptic_mv'), ('last', 'last_spike_tick'),
                    ('refractory', 'refractory_ticks'), ('blocked', 'ablated'), ('pending_count', 'pending_count'), ('pending', 'pending')]:
                    ck('reference:canonical_'+canonical, exact(final[canonical], original[original_key]))
            elif arm == 'C0':
                for k in STATE_KEYS:
                    ck('C0:exact_final_'+k, exact(final[k], reference_final[k]))
                    ck('C0:exact_initial_'+k, exact(initial[k], reference_initial[k]))

            ii = np.concatenate([c['spike_indices'] for c in chunks])
            tt = np.concatenate([c['spike_ticks'] for c in chunks])
            cand = np.concatenate([c['candidate'] for c in chunks])
            app = np.concatenate([c['applied'] for c in chunks])
            ck(arm+':all_candidate_pairing', exact(cand, candidates))
            ck(arm+':spike_shape_order_range', ii.dtype == np.int32 and tt.dtype == np.int64
               and ii.shape == tt.shape and ((ii >= 0) & (ii < n)).all() and ((tt >= 0) & (tt < 500)).all()
               and ((tt[1:] > tt[:-1]) | ((tt[1:] == tt[:-1]) & (ii[1:] > ii[:-1]))).all())
            if arm in ('reference', 'C0'):
                ck(arm+':exact_archived_spikes_and_applied', exact(ii, old_indices) and exact(tt, old_ticks)
                   and exact(app, old_applied))
            for j, c in enumerate(chunks):
                ck(arm+f':chunk{j}_clock_rng', c['end_tick'] == (j+1)*50 and c['completed_ticks'] == 50
                   and c['status'] == 'complete' and c['coherent_state']
                   and c['logical_rng_before'] == int(rng[j*50]) and c['logical_rng_completed_prefix'] == int(rng[(j+1)*50])
                   and ((c['spike_ticks'] >= j*50) & (c['spike_ticks'] < (j+1)*50)).all())
                ck(arm+f':chunk{j}_reported_summary', len(c['spike_indices']) == meta['chunks'][j]['spikes']
                   and c['checkpoint_digest'] == meta['chunks'][j]['state_sha256'])
                if arm == 'reference':
                    ck(arm+f':chunk{j}_archived_summary', c['traversed_edges'] == old_samples[j]['actual_edge_visits']
                       and meta['chunks'][j]['vmin'] == old_samples[j]['global_voltage_min_mv']
                       and meta['chunks'][j]['vmax'] == old_samples[j]['global_voltage_max_mv']
                       and c['logical_rng_completed_prefix'] == old_samples[j]['rng_after'])
                elif arm == 'C0':
                    ck(arm+f':chunk{j}_producer_digest_agreement_only', c['checkpoint_digest'] == reference_chunks[j]['checkpoint_digest'])
            ck(arm+':independent_final_digest', state_digest(final) == chunks[-1]['checkpoint_digest'])

            # Only saved spikes determine refractory state, queues and eligibility.
            by_tick = [ii[tt == tick] for tick in range(500)]
            last = initial['last'].copy()
            edge_counts = np.zeros((500, 4, 3), np.int64)
            available = np.empty((500, len(selected)), bool)
            fired = np.zeros_like(available)
            active = np.empty_like(available)
            work_available = np.zeros(500, np.int64)
            expected_app = candidates.copy()
            selected_events = []
            refractory_ok = True
            for tick in range(500):
                is_available = tick-last >= rf
                available[tick] = is_available[selected]
                work_available[tick] = np.count_nonzero(is_available)
                firing = by_tick[tick]
                refractory_ok &= bool(is_available[firing].all())
                last[firing] = tick
                is_available[firing] = False
                active[tick] = is_available[selected]
                sf = col[firing]
                fired[tick, sf[sf >= 0]] = True
                expected_app[tick] &= is_available[inputs]
                if tick < 18:
                    continue
                for source in by_tick[tick-18]:
                    lo, hi = int(ptr[source]), int(ptr[source+1])
                    edges = np.arange(lo, hi, dtype=np.int64)
                    target = targets[lo:hi]
                    w = weights[lo:hi]
                    sign = np.where(w < 0, 0, np.where(w > 0, 2, 1))
                    if initial['blocked'][source]:
                        disposition = np.full(hi-lo, 2, np.int8)
                        edge_counts[tick, 3] += np.bincount(sign, minlength=3)
                    else:
                        disposition = np.zeros(hi-lo, np.int8) if arm.endswith('1') else (~is_available[target]).astype(np.int8)
                        edge_counts[tick, 0] += np.bincount(sign, minlength=3)
                        edge_counts[tick, 1] += np.bincount(sign[disposition == 0], minlength=3)
                        edge_counts[tick, 2] += np.bincount(sign[disposition == 1], minlength=3)
                    keep = col[target] >= 0
                    selected_events.extend((tick, int(source), int(e), int(t), int(d))
                                           for e, t, d in zip(edges[keep], target[keep], disposition[keep]))
            events = np.array(selected_events, np.int64).reshape(-1, 5)
            ck(arm+':spikes_obey_refractory', refractory_ok)
            ck(arm+':final_last_from_all_own_spikes', exact(last, final['last']))
            pending = [[] for _ in range(19)]
            for cell, tick in zip(ii, tt):
                if tick+18 >= 500:
                    pending[(int(tick)+18) % 19].append(int(cell))
            pc = np.array([len(x) for x in pending], np.int64)
            pq = np.array([cell for slot in pending for cell in slot], np.int32)
            ck(arm+':final_pending_from_all_own_spikes', exact(pc, final['pending_count']) and exact(pq, final['pending']))
            ck(arm+':direct_candidates_vs_own_same_tick_fire', exact(app, expected_app))
            ar.update(spikes=len(ii), candidate_count=int(cand.sum()), applied_count=int(app.sum()),
                rejected_same_tick_source_fire=int(cand.sum()-app.sum()), pending_sources=int(pc.sum()),
                final_voltage_range_mv=[float(final['v'].min()), float(final['v'].max())],
                final_voltage_sha256=array_sha(final['v']), spike_indices_sha256=array_sha(ii),
                spike_ticks_sha256=array_sha(tt), expected_selected_events=len(events),
                reconstructed_edge_counts=edge_counts.sum(axis=0).tolist(),
                edge_count_axes=['visited_unblocked', 'accepted', 'target_unavailable', 'source_blocked'],
                edge_sign_axis=['negative', 'zero', 'positive'], kernel_seconds=meta['kernel_seconds'])
            if arm == 'reference':
                ck('reference:all_chunk_edge_visits_from_history', all(int(edge_counts[j*50:(j+1)*50, 0].sum())
                   == chunks[j]['traversed_edges'] for j in range(10)))
                continue

            def joined(key):
                return np.concatenate([c[key] for c in chunks])

            def states(key):
                return np.concatenate([chunks[0][key]]+[c[key][1:] for c in chunks[1:]])

            ck(arm+':selected_trace_continuity', all(exact(chunks[j][key][-1], chunks[j+1][key][0])
               for j in range(9) for key in ('selected_v', 'selected_s', 'selected_h')))
            sv, ss, sh = [states(k) for k in ('selected_v', 'selected_s', 'selected_h')]
            spre = joined('selected_prethreshold_v')
            ck(arm+':selected_shapes', sv.shape == ss.shape == sh.shape == (501, 48) and spre.shape == (500, 48))
            ck(arm+':selected_endpoint_states', all(exact(arr[0], initial[key][selected])
               and exact(arr[-1], final[key][selected]) for arr, key in ((sv, 'v'), (ss, 's'), (sh, 'h'))))
            ck(arm+':selected_available_and_fired_from_history', exact(available, joined('selected_available'))
               and exact(fired, joined('selected_fired')) and exact(active, joined('selected_direct_available'))
               and exact(active, joined('selected_delivery_available'))
               and exact(np.ones_like(active) if arm.endswith('1') else active, joined('selected_synaptic_available')))
            ck(arm+':selected_firing_threshold', exact(fired, available & (spre > -45)))
            ck(arm+':selected_events_exact_graph_identity_order_disposition', exact(events, joined('selected_events')))
            per = {k: np.concatenate([c['per_tick'][k] for c in chunks]) for k in chunks[0]['per_tick']}
            ck(arm+':all_global_signed_edge_dispositions', exact(edge_counts, per['edge_counts']))
            ck(arm+':available_work_from_history', exact(work_available, per['work'][:, 0]))
            ck(arm+':completed_finite_telemetry', (per['phase_reached'] == 5).all()
               and not per['phase_nonfinite_count'].any() and not per['state_invalid_count'].any()
               and np.isfinite(per['phase_min_mv']).all() and np.isfinite(per['phase_max_mv']).all()
               and np.isfinite(per['solver']).all() and (per['solver'] >= 0).all()
               and all(c['failure'] is None and c['partial'] is None for c in chunks))
            ck(arm+':extrema_indices_and_order', (per['phase_min_mv'] <= per['phase_max_mv']).all()
               and ((per['phase_min_index'] >= 0) & (per['phase_min_index'] < n)).all()
               and ((per['phase_max_index'] >= 0) & (per['phase_max_index'] < n)).all())
            if arm.startswith('H'):
                ck(arm+':hybrid_phase_lower_bound', not per['phase_below_reversal_count'].any()
                   and (per['phase_min_mv'] >= -75-1e-10).all() and (ss >= 0).all() and (sh >= 0).all())
            ck(arm+':endpoint_global_extrema_recomputable', per['phase_min_mv'][-1, 2] == final['v'].min()
               and per['phase_max_mv'][-1, 2] == final['v'].max()
               and per['phase_min_index'][-1, 2] == int(np.argmin(final['v']))
               and per['phase_max_index'][-1, 2] == int(np.argmax(final['v'])))
            ck(arm+':chunk_postreset_extrema_match_summaries', all(per['phase_min_mv'][(j+1)*50-1, 2] == meta['chunks'][j]['vmin']
               and per['phase_max_mv'][(j+1)*50-1, 2] == meta['chunks'][j]['vmax'] for j in range(10)))

            # Each transition is checked from its archived starting point. This
            # is not an iterated neural state trajectory or a new spike run.
            decay = float(np.exp(-.1/5))
            vm_decay = float(np.exp(-.1/20))
            coeff = 5./15.*(vm_decay-decay)
            decay_mask = available | arm.endswith('1')
            expected_s = np.where(decay_mask, ss[:-1]*decay, ss[:-1]).copy()
            expected_h = np.where(decay_mask, sh[:-1]*decay, sh[:-1]).copy()
            for tick, source, edge, target, disposition in events:
                if disposition != 0:
                    continue
                j = int(col[target])
                weight = float(weights[edge])
                if arm.startswith('H') and weight < 0:
                    expected_h[tick, j] += -weight*(1./23.)
                else:
                    expected_s[tick, j] += weight
            if arm.endswith('0'):
                expected_s[fired] = 0.
                expected_h[fired] = 0.
            ck(arm+':selected_synaptic_transition_exact', exact(expected_s, ss[1:]) and exact(expected_h, sh[1:]))
            expected_post = spre.copy()
            for cell, input_j in input_col.items():
                expected_post[:, col[cell]] += app[:, input_j] * 68.75
            postexternal = expected_post.copy()
            expected_post[fired] = -52.
            ck(arm+':selected_external_and_reset_exact', exact(expected_post, sv[1:]))
            ck(arm+':unavailable_voltage_contract', np.array_equal(spre[~available],
               np.full(np.count_nonzero(~available), -52.) if arm.endswith('1') else sv[:-1][~available]))
            selected_phase = np.stack((spre, postexternal, sv[1:]), axis=1)
            ck(arm+':selected_values_enclosed_by_global_telemetry',
               (selected_phase >= per['phase_min_mv'][:, :, None]).all()
               and (selected_phase <= per['phase_max_mv'][:, :, None]).all())
            extremum_match = True
            extremum_checks = 0
            for key, values in (('phase_min_index', 'phase_min_mv'), ('phase_max_index', 'phase_max_mv')):
                positions = col[per[key]]
                for tick, phase in zip(*np.nonzero(positions >= 0)):
                    extremum_checks += 1
                    extremum_match &= bool(selected_phase[tick, phase, positions[tick, phase]] == per[values][tick, phase])
            ck(arm+':named_selected_extrema_match', extremum_match, dict(comparisons=extremum_checks))
            ar.update(selected_available_intervals=int(available.sum()), selected_spikes=int(fired.sum()),
                selected_accepted_negative_events=int(sum(d == 0 and weights[e] < 0 for _, _, e, _, d in events)),
                phase_voltage_range_mv=[float(per['phase_min_mv'].min()), float(per['phase_max_mv'].max())],
                reported_hybrid_quadrature_calls=int(per['work'][:, 1].sum()),
                reported_peak_h_before=float(per['solver'][:, 2].max()),
                selected_synaptic_max_abs_error=float(np.max(np.abs(expected_s-ss[1:]))),
                selected_conductance_max_abs_error=float(np.max(np.abs(expected_h-sh[1:]))))
            if arm.startswith('H'):
                max_error = max_quad_error = 0.
                worst = None
                positive_h = zero_h = 0
                h_range, p_range = [math.inf, -math.inf], [math.inf, -math.inf]
                for tick, j in zip(*np.nonzero(available)):
                    v0, p0, h0 = float(sv[tick, j]), float(ss[tick, j]), float(sh[tick, j])
                    predicted, qe = hybrid_voltage(v0, p0, h0)
                    error = abs(predicted - spre[tick, j])
                    positive_h += h0 > 0
                    zero_h += h0 == 0
                    h_range = [min(h_range[0], h0), max(h_range[1], h0)]
                    p_range = [min(p_range[0], p0), max(p_range[1], p0)]
                    max_quad_error = max(max_quad_error, qe)
                    if error > max_error or worst is None:
                        max_error = error
                        worst = dict(tick=int(tick), selected_column=int(j), graph_index=int(selected[j]),
                            body_id=int(ids[selected[j]]), initial_v_mv=v0, initial_p_mv=p0, initial_h=h0,
                            recorded_prethreshold_mv=float(spre[tick, j]), oracle_mv=predicted, abs_error_mv=error,
                            quad_error_estimate_mv=qe)
                ck(arm+':all_selected_available_time_domain_quadrature', max_error <= TOL and max_quad_error <= TOL)
                ar['independent_voltage_oracle'] = dict(intervals=positive_h+zero_h, positive_h_intervals=positive_h,
                    zero_h_intervals=zero_h, initial_h_range=h_range, initial_p_mv_range=p_range,
                    max_abs_error_mv=max_error, max_quad_error_estimate_mv=max_quad_error, worst=worst)
            else:
                predicted = -52. + (sv[:-1]+52.)*vm_decay + ss[:-1]*coeff
                error = float(np.max(np.abs(predicted[available]-spre[available])))
                ck(arm+':selected_current_interval_closed_form', error <= TOL)
                ar['selected_current_interval_max_abs_error_mv'] = error

        ck('producer_recorded_resource_budget', producer['resources']['wall_seconds'] <= plan['budget']['wall_seconds']
           and producer['resources']['output_bytes'] <= plan['budget']['output_bytes']
           and producer['resources']['peak_rss_bytes'] <= plan['budget']['peak_rss_bytes'])
        result['producer_timing_scope'] = dict(recorded=producer['resources'],
            scalar_grid=producer['scalar_grid'], independently_remeasured=False,
            limits='Recorded timings and sampled process limits only; this review does not benchmark execution')
        result['limits'] = [
            'Initial/final canonical arrays are available and independently compared. Intermediate C0/reference digest equality is a producer assertion; full intermediate global states were not retained.',
            'Global event dispositions and refractory availability are independently reconstructed from every saved spike. Global intermediate voltage extrema/finite counts remain telemetry except endpoint and selected-value checks.',
            'Selected interval oracle and transitions check retained states without generating new spikes, fitting parameters, or advancing a model.',
            '50 ms, seed 11, one baseline stimulus. C1 activity is already greater than C0; no withdrawal, longer persistence, stimulus contrasts, seed robustness, physiological amplitude or model promotion follows.',
            'The -75 mV lower bound is an engineering property of declared hybrid states, not a measured receptor reversal.'
        ]
    except Exception as error:
        result['exceptions'].append(dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
    finally:
        result['check_count'] = len(result['checks'])
        result['passed'] = not result['exceptions'] and all(c['passed'] for c in result['checks'])
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(json.dumps(dict(path=str(OUTPUT.relative_to(ROOT)), sha256=sha(OUTPUT),
            checks=result['check_count'], passed=result['passed'], exceptions=result['exceptions']), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(review())
