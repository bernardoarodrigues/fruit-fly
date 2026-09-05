#!/usr/bin/env python3
"""Pure streaming summaries for the fixed recurrent panel; no model imports.

Primary API: accumulate_chunk(counts[7,N], indices, ticks) then
summarize_counts(counts, completed_tick, cohorts). Counts describe the observed
completed prefix. A partial window never receives a complete-window rate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np

EDGES = np.array([0, 500, 5000, 10000, 15000, 20000, 25000, 30000], dtype=np.int64)
WINDOW_NAMES = ('startup', 'baseline', 'pulse', 'recovery', 'off_early', 'off_middle', 'off_late')
DT_SECONDS = .0001
SEEDS = (11, 12, 13)
ARMS = ('C0', 'C1', 'H0', 'H1')
CONDITIONS = ('no_input', 'constant_baseline', 'ethyl_acetate', 'isoamyl_acetate',
              'ethyl_acetate_source_outputs_blocked')
TARGET_IDS = (67052, 13314)


def _integers(values, name):
    a = np.asarray(values)
    if a.ndim != 1 or a.dtype.kind not in 'iu':
        raise ValueError(name+' must be a one-dimensional integer array')
    return a


def _count_array(counts):
    a = np.asarray(counts)
    if a.ndim != 2 or a.shape[0] != 7 or a.shape[1] < 1 or a.dtype != np.int64:
        raise ValueError('counts must be int64[7,N], N>0')
    return a


def build_cohorts(neuron_ids, old_plan):
    """Return ordered int32 graph-index arrays; caller pins source-file hashes.

    Source/first-hop/motor IDs come from the old plan. Two target identities
    come from the fixed recurrent design. This is an ID join, not a new
    connectivity traversal or a response-dependent cohort selection.
    """
    ids = _integers(neuron_ids, 'neuron_ids')
    if len(np.unique(ids)) != len(ids) or len(ids) != old_plan['neurons']:
        raise ValueError('Graph IDs/count differ from plan or contain duplicates')
    lookup = {int(v): i for i, v in enumerate(ids)}

    def join(values):
        values = list(values)
        if len(set(values)) != len(values):
            raise ValueError('Duplicate cohort ID')
        try:
            return np.array([lookup[int(v)] for v in values], dtype=np.int32)
        except KeyError as e:
            raise ValueError('Cohort ID absent from graph: '+str(e)) from e

    source = join(old_plan['source_body_ids'])
    first = join(old_plan['first_hop_body_ids'])
    if len(source) != 36 or len(first) != 365:
        raise ValueError('Expected exactly 36 sources and 365 first-hop nonsource cells')
    if not np.array_equal(source, old_plan['source_graph_indices']) or np.intersect1d(source, first).size:
        raise ValueError('Source order or first-hop nonsource membership differs from plan')
    if set(old_plan['motor_groups']) != {'forward', 'turn_left', 'turn_right', 'feeding', 'escape'}:
        raise ValueError('Motor group names differ from fixed old plan')
    cohorts = {'all': np.arange(len(ids), dtype=np.int32), 'source': source,
               'non_source': np.setdiff1d(np.arange(len(ids), dtype=np.int32), source),
               'first_hop_non_source': first, 'targets': join(TARGET_IDS)}
    for target in TARGET_IDS:
        cohorts['target_'+str(target)] = join([target])
    for name, values in old_plan['motor_groups'].items():
        if len(values) != 2:
            raise ValueError('Each fixed motor group must have two IDs')
        cohorts['motor:'+name] = join(values)
    return cohorts


def accumulate_chunk(counts, indices, ticks, *, start_tick=None, end_tick=None):
    """Add one ordered saved chunk in place and return counts.

    Optional [start_tick,end_tick) bounds validate the producer's chunk clock.
    Caller owns cross-chunk contiguity, uniqueness and durable publication.
    This function does not retain spikes, infer missing data or advance time.
    """
    counts = _count_array(counts)
    if not counts.flags.writeable:
        raise ValueError('counts must be writable')
    cells, times = _integers(indices, 'indices'), _integers(ticks, 'ticks')
    if cells.shape != times.shape:
        raise ValueError('Spike index/tick shape mismatch')
    if (start_tick is None) != (end_tick is None):
        raise ValueError('Supply both optional chunk bounds')
    lo, hi = 0, 30000
    if start_tick is not None:
        if not isinstance(start_tick, (int, np.integer)) or not isinstance(end_tick, (int, np.integer)):
            raise ValueError('Chunk bounds must be integer ticks')
        lo, hi = int(start_tick), int(end_tick)
        if not 0 <= lo <= hi <= 30000:
            raise ValueError('Invalid chunk tick range')
    if ((cells < 0) | (cells >= counts.shape[1])).any() or ((times < lo) | (times >= hi)).any():
        raise ValueError('Spike outside graph/chunk/panel range')
    if len(times) > 1 and not ((times[1:] > times[:-1]) |
                               ((times[1:] == times[:-1]) & (cells[1:] > cells[:-1]))).all():
        raise ValueError('Spike records must be tick-major/index-major with no duplicates')
    win = np.searchsorted(EDGES, times, side='right')-1
    # A chunk-sized accumulator avoids a full 7*N temporary and retains repeats
    # of a cell across different ticks. Checked indices fit intp on this host.
    np.add.at(counts, (win.astype(np.intp), cells.astype(np.intp)), 1)
    return counts


def summarize_counts(counts, completed_tick, cohorts):
    """Return JSON-safe metrics; partial/absent windows have null final metrics.

    observed_spikes is explicitly a completed-prefix count, including a
    partially observed window. No partial rate is passed off as a nominal-window
    rate. Save counts separately as observed_window_counts[7,N] in the NPZ.
    """
    counts = _count_array(counts)
    if not isinstance(completed_tick, (int, np.integer)) or not 0 <= int(completed_tick) <= 30000:
        raise ValueError('completed_tick must be in [0,30000]')
    completed_tick = int(completed_tick)
    observed_ticks = np.maximum(0, np.minimum(EDGES[1:], completed_tick)-EDGES[:-1])
    if (counts < 0).any() or counts[EDGES[:-1] >= completed_tick].any():
        raise ValueError('Negative counts or nonzero counts in an unobserved future window')
    if (counts > observed_ticks[:, None]).any():
        raise ValueError('Counts exceed the exact one-spike-per-cell-per-tick record contract')
    complete = EDGES[1:] <= completed_tick
    nominal = np.diff(EDGES)*DT_SECONDS
    observed = np.maximum(0, np.minimum(EDGES[1:], completed_tick)-EDGES[:-1])*DT_SECONDS
    metrics, off, membership = {}, {}, {}
    for name, values in cohorts.items():
        cells = _integers(values, 'cohort '+name)
        if len(np.unique(cells)) != len(cells) or ((cells < 0) | (cells >= counts.shape[1])).any():
            raise ValueError('Duplicate/out-of-range cohort indices: '+name)
        membership[name] = hashlib.sha256(cells.astype('<i8').tobytes()).hexdigest()
        rows = []
        for w in range(7):
            cell_counts = counts[w, cells.astype(np.intp)]
            total = int(cell_counts.sum())
            size = len(cells)
            valid = bool(complete[w])
            active = int(np.count_nonzero(cell_counts))
            rows.append(dict(window_index=w, window=WINDOW_NAMES[w], complete=valid,
                status='complete' if valid else ('partial' if observed[w] > 0 else 'unobserved'),
                population_size=size, nominal_duration_s=float(nominal[w]), observed_duration_s=float(observed[w]),
                observed_spikes=total, spike_count=total if valid else None,
                population_rate_hz=total/nominal[w] if valid and size else None,
                mean_cell_rate_hz=total/(nominal[w]*size) if valid and size else None,
                recruited_cells=active if valid else None,
                active_fraction=active/size if valid and size else None))
        metrics[name] = rows
        rates = [r['mean_cell_rate_hz'] for r in rows[4:]]
        difference = lambda x, y: None if x is None or y is None else float(x-y)
        off[name] = dict(rates_hz_per_cell=rates, middle_minus_early_hz_per_cell=difference(rates[1], rates[0]),
            late_minus_middle_hz_per_cell=difference(rates[2], rates[1]),
            late_minus_early_hz_per_cell=difference(rates[2], rates[0]),
            strictly_increasing=None if any(x is None for x in rates) else bool(rates[0] < rates[1] < rates[2]),
            interpretation='Descriptive direction only; no persistence or biological acceptance threshold')
    return dict(schema=1, completed_tick=completed_tick, n_neurons=counts.shape[1],
                cohort_index_sha256=membership, window_edges_ticks=EDGES.tolist(),
                window_names=list(WINDOW_NAMES), window_complete=complete.tolist(),
                complete_window_count=int(complete.sum()), dt_seconds=DT_SECONDS,
                observed_count_semantics='Counts cover only archived spikes before completed_tick; partial windows are not zero-filled complete observations',
                cohort_metrics=metrics, off_descriptive=off)


def summarize_trial(spike_indices, spike_ticks, n_neurons, completed_tick, cohorts):
    """Convenience for small saved streams; streaming is the primary interface."""
    counts = np.zeros((7, n_neurons), np.int64)
    accumulate_chunk(counts, spike_indices, spike_ticks, start_tick=0, end_tick=completed_tick)
    return dict(observed_window_counts=counts, **summarize_counts(counts, completed_tick, cohorts))


def paired_contrasts(trials):
    """JSON contrasts from {(seed,arm,condition): summarize_counts result}.

    Missing trials/windows yield null differences with explicit reasons. All
    contrasts use mean-cell rates, so the .45 s baseline and .5 s pulse use
    their own denominators. Counts remain available in the original summaries.
    """
    if not trials:
        raise ValueError('At least one summary is required to identify the pinned cohorts')
    group_sizes, membership = {}, {}
    neuron_counts = {trial['n_neurons'] for trial in trials.values()}
    if len(neuron_counts) != 1:
        raise ValueError('Graph population differs between trials')
    for key, trial in trials.items():
        if len(key) != 3 or key[0] not in SEEDS or key[1] not in ARMS or key[2] not in CONDITIONS:
            raise ValueError('Unexpected trial key')
        if trial['window_edges_ticks'] != EDGES.tolist() or trial['dt_seconds'] != DT_SECONDS:
            raise ValueError('Trial time/window definitions differ')
        if len(trial['window_complete']) != 7:
            raise ValueError('Incomplete window metadata')
        for name, rows in trial['cohort_metrics'].items():
            digest = trial['cohort_index_sha256'][name]
            if name in membership and membership[name] != digest:
                raise ValueError('Cohort ordered membership differs between trials')
            membership[name] = digest
            if len(rows) != 7:
                raise ValueError('Expected seven cohort rows')
            for w, row in enumerate(rows):
                if row['window_index'] != w or row['complete'] != trial['window_complete'][w]:
                    raise ValueError('Contradictory window metadata')
                size = row['population_size']
                if name in group_sizes and group_sizes[name] != size:
                    raise ValueError('Cohort population differs between trials')
                group_sizes[name] = size
                if not row['complete'] and any(row[k] is not None for k in ('spike_count', 'mean_cell_rate_hz', 'active_fraction')):
                    raise ValueError('Incomplete window has a purported complete metric')
    names = sorted(group_sizes)
    output = []

    def emit(label, seed, window, terms, arm=None, condition=None):
        for cohort in names:
            missing, rates, active, operands = [], [], [], []
            for coefficient, key, w in terms:
                operands.append(dict(coefficient=coefficient, seed=key[0], arm=key[1], condition=key[2], window=WINDOW_NAMES[w]))
                trial = trials.get(key)
                reason = None
                if trial is None:
                    reason = 'missing_trial'
                elif cohort not in trial['cohort_metrics']:
                    reason = 'missing_cohort'
                else:
                    row = trial['cohort_metrics'][cohort][w]
                    if not row['complete']:
                        reason = 'incomplete_window'
                    elif row['mean_cell_rate_hz'] is None or row['active_fraction'] is None:
                        reason = 'empty_cohort_or_unavailable_metric'
                    else:
                        rates.append(coefficient*row['mean_cell_rate_hz'])
                        active.append(coefficient*row['active_fraction'])
                if reason:
                    missing.append(dict(operand=operands[-1], reason=reason))
            output.append(dict(contrast=label, seed=seed, arm=arm, condition=condition, window=window,
                cohort=cohort, population_size=group_sizes[cohort], complete=not missing,
                difference_hz_per_cell=None if missing else float(sum(rates)),
                difference_active_fraction=None if missing else float(sum(active)),
                unavailable=missing, operands=operands))

    for seed in SEEDS:
        for arm in ARMS:
            for condition in CONDITIONS:
                key = (seed, arm, condition)
                emit('pulse_minus_own_baseline', seed, 'pulse_minus_baseline', [(1, key, 2), (-1, key, 1)], arm, condition)
                for late, early, name in [(5, 4, 'off_middle_minus_early'), (6, 5, 'off_late_minus_middle'), (6, 4, 'off_late_minus_early')]:
                    emit(name, seed, name, [(1, key, late), (-1, key, early)], arm, condition)
                if condition in ('ethyl_acetate', 'isoamyl_acetate', 'ethyl_acetate_source_outputs_blocked'):
                    emit('pulse_minus_matched_constant', seed, 'pulse', [(1, key, 2), (-1, (seed, arm, 'constant_baseline'), 2)], arm, condition)
                for control in ('constant_baseline', 'no_input'):
                    if condition != control:
                        for w in (4, 5, 6):
                            emit('off_excess_vs_'+control, seed, WINDOW_NAMES[w], [(1, key, w), (-1, (seed, arm, control), w)], arm, condition)
            for left, right, name in [('ethyl_acetate', 'isoamyl_acetate', 'ethyl_minus_isoamyl'),
                    ('ethyl_acetate', 'ethyl_acetate_source_outputs_blocked', 'unblocked_minus_blocked')]:
                for w in range(7):
                    emit(name, seed, WINDOW_NAMES[w], [(1, (seed, arm, left), w), (-1, (seed, arm, right), w)], arm)
        for condition in CONDITIONS:
            for w in range(7):
                hc0 = [(1, (seed, 'H0', condition), w), (-1, (seed, 'C0', condition), w)]
                hc1 = [(1, (seed, 'H1', condition), w), (-1, (seed, 'C1', condition), w)]
                emit('H0_minus_C0', seed, WINDOW_NAMES[w], hc0, condition=condition)
                emit('H1_minus_C1', seed, WINDOW_NAMES[w], hc1, condition=condition)
                emit('inhibition_by_handling_interaction', seed, WINDOW_NAMES[w], hc1+[(-c, k, q) for c, k, q in hc0], condition=condition)
    return dict(schema=1, rates='Mean spikes/s/cell; cohort/time denominators explicit in source summaries',
                seed_semantics='Paired simulation seeds, not independent biological specimens',
                missing_semantics='No complete paired contrast unless every required window/cohort is available',
                rows=output)


def self_check():
    """Manufactured arithmetic/missingness fixtures; no graph/model simulation."""
    checks = []

    def ck(name, value):
        checks.append(dict(name=name, passed=bool(value)))

    def rejects(name, fn):
        try:
            fn()
        except (ValueError, TypeError):
            ck(name, True)
        else:
            ck(name, False)

    times = np.ravel(np.column_stack((EDGES[:-1], EDGES[1:]-1)))
    cells = np.zeros(14, np.int32)
    whole = np.zeros((7, 3), np.int64)
    accumulate_chunk(whole, cells, times, start_tick=0, end_tick=30000)
    ck('all_half_open_window_boundaries', np.array_equal(whole[:, 0], np.full(7, 2)) and not whole[:, 1:].any())
    streamed = np.zeros_like(whole)
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        keep = (times >= lo) & (times < hi)
        accumulate_chunk(streamed, cells[keep], times[keep], start_tick=int(lo), end_tick=int(hi))
    ck('streaming_equals_whole', np.array_equal(whole, streamed))
    accumulate_chunk(streamed, np.array([], np.int32), np.array([], np.int64), start_tick=30000, end_tick=30000)
    ck('empty_terminal_chunk_no_change', np.array_equal(whole, streamed))
    cohorts = {'one': np.array([0], np.int32), 'all': np.arange(3, dtype=np.int32), 'empty': np.array([], np.int32)}
    summary = summarize_counts(whole, 30000, cohorts)
    ck('complete_windows_counts_and_rates', summary['complete_window_count'] == 7
       and summary['cohort_metrics']['one'][0]['mean_cell_rate_hz'] == 40
       and np.isclose(summary['cohort_metrics']['all'][0]['mean_cell_rate_hz'], 40/3))
    ck('empty_cohort_no_division_or_nan', summary['cohort_metrics']['empty'][0]['spike_count'] == 0
       and summary['cohort_metrics']['empty'][0]['mean_cell_rate_hz'] is None)
    partial_counts = np.zeros((7, 3), np.int64)
    partial_counts[0, 0], partial_counts[1, 0], partial_counts[2, 0] = 2, 9, 3
    partial = summarize_counts(partial_counts, 7500, cohorts)
    row = partial['cohort_metrics']['one'][2]
    ck('partial_count_preserved_rate_unavailable', row['observed_spikes'] == 3 and row['spike_count'] is None
       and row['mean_cell_rate_hz'] is None and row['status'] == 'partial' and row['observed_duration_s'] == .25)
    ck('unobserved_is_not_zero_response', partial['cohort_metrics']['one'][4]['spike_count'] is None
       and partial['off_descriptive']['one']['strictly_increasing'] is None)
    zeros = summarize_counts(np.zeros((7, 3), np.int64), 30000, cohorts)
    ck('complete_zero_is_observed_zero', zeros['cohort_metrics']['one'][6]['mean_cell_rate_hz'] == 0)
    ck('no_input_fixture_has_no_invented_growth', zeros['off_descriptive']['one']['strictly_increasing'] is False)
    rejects('reject_outside_panel_tick', lambda: accumulate_chunk(np.zeros_like(whole), np.array([0]), np.array([30000])))
    rejects('reject_negative_graph_index', lambda: accumulate_chunk(np.zeros_like(whole), np.array([-1]), np.array([0])))
    rejects('reject_duplicate_spike', lambda: accumulate_chunk(np.zeros_like(whole), np.array([0, 0]), np.array([1, 1])))
    rejects('reject_unsorted_spike', lambda: accumulate_chunk(np.zeros_like(whole), np.array([0, 1]), np.array([2, 1])))
    rejects('reject_outside_chunk_tick', lambda: accumulate_chunk(np.zeros_like(whole), np.array([0]), np.array([50]), start_tick=0, end_tick=50))
    rejects('reject_future_window_counts', lambda: summarize_counts(whole, 7500, cohorts))
    rejects('reject_bad_count_dtype', lambda: summarize_counts(whole.astype(np.int32), 30000, cohorts))
    rejects('reject_duplicate_cohort', lambda: summarize_counts(whole, 30000, {'bad': np.array([0, 0])}))
    rejects('reject_count_exceeding_tick_coverage', lambda: summarize_counts(np.full((7, 1), 5001, np.int64), 30000, {'one': np.array([0])}))
    rejects('reject_empty_trial_map_without_cohort_identity', lambda: paired_contrasts({}))

    # A synthetic ID table tests exact joins/order without acquiring a graph.
    fake_ids = np.array(list(range(1000, 1401))+list(TARGET_IDS)+list(range(2000, 2010)), np.int64)
    fake = dict(neurons=len(fake_ids), source_body_ids=fake_ids[:36].tolist(), source_graph_indices=list(range(36)),
                first_hop_body_ids=fake_ids[36:401].tolist(), motor_groups={
                    name: fake_ids[403+2*j:405+2*j].tolist()
                    for j, name in enumerate(('forward', 'turn_left', 'turn_right', 'feeding', 'escape'))})
    built = build_cohorts(fake_ids, fake)
    ck('cohort_exact_source_firsthop_target_join', len(built['source']) == 36 and len(built['first_hop_non_source']) == 365
       and np.array_equal(fake_ids[built['targets']], TARGET_IDS) and len(built['non_source']) == len(fake_ids)-36)
    changed = dict(fake, source_graph_indices=list(reversed(range(36))))
    rejects('reject_changed_source_order', lambda: build_cohorts(fake_ids, changed))

    trials = {}
    base = np.array([1, 9, 10, 10, 10, 10, 10], np.int64)[:, None]
    for seed in SEEDS:
        for arm, factor in zip(ARMS, (1, 2, 3, 5)):
            for condition, scale in zip(CONDITIONS, (0, 1, 3, 2, 1)):
                trials[(seed, arm, condition)] = summarize_counts(base*factor*scale, 30000, {'one': np.array([0])})
    out = paired_contrasts(trials)

    def find(label, seed=11, arm=None, condition=None, window='pulse'):
        return next(r for r in out['rows'] if r['contrast'] == label and r['seed'] == seed
                    and r['arm'] == arm and r['condition'] == condition and r['window'] == window)

    ck('baseline_and_pulse_durations_normalized', find('pulse_minus_own_baseline', arm='C0', condition='ethyl_acetate', window='pulse_minus_baseline')['difference_hz_per_cell'] == 0)
    ck('pulse_vs_matched_constant', find('pulse_minus_matched_constant', arm='C0', condition='ethyl_acetate')['difference_hz_per_cell'] == 40)
    ck('ethyl_vs_isoamyl', find('ethyl_minus_isoamyl', arm='C0')['difference_hz_per_cell'] == 20)
    ck('unblocked_vs_blocked', find('unblocked_minus_blocked', arm='C0')['difference_hz_per_cell'] == 40)
    ck('H0_minus_C0', find('H0_minus_C0', condition='ethyl_acetate')['difference_hz_per_cell'] == 120)
    ck('H1_minus_C1', find('H1_minus_C1', condition='ethyl_acetate')['difference_hz_per_cell'] == 180)
    ck('factorial_interaction', find('inhibition_by_handling_interaction', condition='ethyl_acetate')['difference_hz_per_cell'] == 60)
    ck('three_seeds_retained_separately', set(r['seed'] for r in out['rows']) == set(SEEDS))
    ck('all_manufactured_complete_contrasts', all(r['complete'] for r in out['rows']))
    truncated = (base*15).copy()
    truncated[3:] = 0
    trials[(13, 'H1', 'ethyl_acetate')] = summarize_counts(truncated, 12500, {'one': np.array([0])})
    del trials[(12, 'H0', 'isoamyl_acetate')]
    out = paired_contrasts(trials)
    missing = find('inhibition_by_handling_interaction', seed=13, condition='ethyl_acetate', window='off_late')
    ck('partial_off_cannot_enter_interaction', missing['difference_hz_per_cell'] is None
       and missing['unavailable'][0]['reason'] == 'incomplete_window')
    ck('complete_prefix_contrast_survives_partial_tail', find('inhibition_by_handling_interaction', seed=13, condition='ethyl_acetate')['complete'])
    missing = find('H0_minus_C0', seed=12, condition='isoamyl_acetate')
    ck('missing_trial_not_imputed_zero', missing['difference_hz_per_cell'] is None and missing['unavailable'][0]['reason'] == 'missing_trial')
    ck('unrelated_pair_remains_complete', find('H1_minus_C1', seed=12, condition='isoamyl_acetate')['complete'])
    corrupted = dict(trials)
    first = next(iter(corrupted))
    corrupted[first] = dict(corrupted[first], cohort_index_sha256={'one': 'different'})
    rejects('reject_same_size_different_membership', lambda: paired_contrasts(corrupted))
    json.dumps(out, allow_nan=False)
    ck('json_has_no_nan', True)
    return dict(schema=1, method='Manufactured arithmetic, ID-join, streaming and missingness fixtures only; no neural simulation',
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                generated_utc=datetime.now(timezone.utc).isoformat(), numpy=np.__version__,
                checks=checks, check_count=len(checks), passed=all(c['passed'] for c in checks))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', action='store_true', required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        raise SystemExit('Refusing to overwrite a metric-test receipt')
    try:
        result = self_check()
    except Exception as error:
        result = dict(schema=1, passed=False, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      generated_utc=datetime.now(timezone.utc).isoformat(),
                      exception=dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
    text = json.dumps(result, indent=2, allow_nan=False)+'\n'
    if args.receipt:
        args.receipt.write_text(text)
    print(text)
    raise SystemExit(0 if result['passed'] else 1)
