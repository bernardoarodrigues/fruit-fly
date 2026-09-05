#!/usr/bin/env python3
"""Independent saved-checkpoint/CSR inventory audit; no producer or model imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd
from review_inhibitory_recurrent_panel_trial import Audit, exact, ROOT

PREFIX = ROOT / 'validation/pn-kc-apl-inventory'
OUTPUT = ROOT / 'validation/pn-kc-apl-inventory-independent-review.json'
GRAPH = ROOT / 'data/processed/malecns_v1'
BOUNDS = np.array([0, 500, 5000, 10000, 15000, 20000, 25000, 30000], np.int64)
ORDINALS = [26, 29, 32, 35, 38, 41]
PLAN_SHA = 'e6d6738e5f18fd45dfd1184b454797c1c80ee67c2c57c8588c336b3e98813ad9'
RESULT_SHA = '7bf856c127a2e7eca93d683e184e3e3f3be77c93839bf03442cf3e6a69c64a69'
DECODER_SHA = '1e2d91757813372de3fa3d5df100690ab7ac6d3805fe7f7035e3ebc5f6424da8'


def load(p):
    return json.loads(Path(p).read_text())


def record(p):
    p = Path(p).resolve()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=h.hexdigest())


def integer_bins(index, values, size):
    """Integer sums through binary64 only under an explicit exactness bound."""
    assert values.dtype.kind in 'iu' and np.all(values >= 0)
    bound = int(values.max(initial=0)) * len(values)
    assert bound < 2**53
    return np.bincount(index, weights=values, minlength=size).astype(np.int64)


def fixture():
    bounds = np.array([0, 18, 55, 100])
    times = np.array([0, 17, 18, 36, 37, 54, 55, 82, 99])
    sources = np.array([0, 1, 0, 1, 0, 0, 1, 0, 1], np.int32)
    emitted = np.array([np.bincount(sources[(times >= a) & (times < b)], minlength=3)
                        for a, b in zip(bounds[:-1], bounds[1:])])
    tails = []
    for b in bounds:
        pending = (times < b) & (times + 18 >= b)
        slots = (times[pending] + 18) % 19
        packed = np.concatenate([sources[pending][slots == slot] for slot in range(19)])
        tails.append(np.bincount(packed, minlength=3))
    actual = emitted + np.array(tails[:-1]) - np.array(tails[1:])
    direct = np.array([np.bincount(sources[(times + 18 >= a) & (times + 18 < b)], minlength=3)
                       for a, b in zip(bounds[:-1], bounds[1:])])
    assert exact(actual, direct)
    assert np.array_equal(actual.sum(0) + tails[-1], emitted.sum(0))
    assert not actual[:, 2].any()
    assert exact(integer_bins(np.array([0, 2, 0]), np.array([7, 0, 11], np.int64), 4),
                 np.array([18, 0, 0, 0], np.int64))
    return dict(passed=True, checks=4, scope='Synthetic packed pending queues versus explicitly shifted emissions; delay/window endpoints, empty source, exact integer aggregation.')


def metrics(full, indices):
    c = full[:, indices]
    d = np.diff(BOUNDS) / 10000.
    rates = c / d[:, None]
    active = np.count_nonzero(c, axis=1)
    return dict(cells=len(indices), spikes=c.sum(1).tolist(), active_cells=active.tolist(),
                any_spike_fraction=(active / len(indices)).tolist() if len(indices) else None,
                mean_rates_hz=(c.sum(1) / len(indices) / d).tolist() if len(indices) else None,
                active_rate_quantiles_hz=[np.quantile(row[row > 0], [0, .25, .5, .75, 1]).tolist()
                                         if np.any(row > 0) else None for row in rates],
                pulse_minus_prebaseline_rate_hz=(rates[2] - rates[1]).tolist(),
                pulse_rate_above_baseline_cells=int(np.count_nonzero(rates[2] > rates[1])))


def run():
    if OUTPUT.exists():
        raise FileExistsError('Preserve the first independent review receipt')
    audit = Audit()
    started = time.perf_counter()
    context = 'preflight'
    source_start, source_end, completed, maxima = [], [], [], {}
    error = None
    pure = fixture()

    def ck(name, value, detail=None):
        if not audit.ck(name, value, context if detail is None else detail):
            raise AssertionError(name + ': ' + str(context if detail is None else detail))

    def close(name, actual, expected, atol=1e-7, rtol=1e-12):
        actual, expected = np.asarray(actual), np.asarray(expected)
        ck(name + '_shape', actual.shape == expected.shape)
        delta = float(np.max(np.abs(actual - expected), initial=0.))
        maxima[name] = max(maxima.get(name, 0.), delta)
        ck(name, np.isfinite(actual).all() and np.isfinite(expected).all()
           and np.allclose(actual, expected, atol=atol, rtol=rtol))

    def tree(name, actual, expected):
        if isinstance(expected, dict):
            ck(name + '_keys', isinstance(actual, dict) and actual.keys() == expected.keys())
            for k in expected:
                tree(name, actual[k], expected[k])
        elif isinstance(expected, list):
            ck(name + '_length', isinstance(actual, list) and len(actual) == len(expected))
            for x, y in zip(actual, expected):
                tree(name, x, y)
        elif isinstance(expected, float):
            close(name, actual, expected, atol=1e-10)
        else:
            ck(name, actual == expected)

    try:
        plan_path, result_path = Path(str(PREFIX) + '-plan.json'), Path(str(PREFIX) + '-results.json')
        plan, result = load(plan_path), load(result_path)
        ck('fixed_plan', record(plan_path)['sha256'] == PLAN_SHA)
        ck('fixed_result', record(result_path)['sha256'] == RESULT_SHA and result['passed'])
        ck('result_plan_link', result['plan'] == record(plan_path))
        decoder = ROOT / 'scripts/review_inhibitory_recurrent_panel_trial.py'
        ck('independent_decoder_pin', record(decoder)['sha256'] == DECODER_SHA)
        paths = [Path(__file__), decoder, plan_path, result_path,
                 ROOT / result['array_artifact']['path'], ROOT / result['cell_artifact']['path']]
        paths += [ROOT / r['path'] for r in plan['inputs']]
        source_start = [record(p) for p in dict.fromkeys(paths)]
        start_map = {r['path']: r for r in source_start}
        for r in plan['inputs'] + [result['array_artifact'], result['cell_artifact']]:
            ck('producer_input_and_artifact_pin', start_map[r['path']] == r, r['path'])
        ck('contract', plan['window_edges_ticks'] == BOUNDS.tolist() and plan['dt_s'] == .0001
           and plan['delay_ticks'] == 18 and [s['ordinal'] for s in plan['trials']] == ORDINALS
           and plan['numerical_tolerance'] == dict(atol=1e-7, rtol=1e-12))
        ck('twelve_complete_results', [(t['spec'], t['arm']) for t in result['trials']]
           == [(s, a) for s in plan['trials'] for a in ['control', 'intervention']])
        manifest = load(GRAPH / 'manifest.json')
        for name, r in (manifest['arrays'] | manifest['metadata']).items():
            ck('graph_manifest', record(GRAPH / name)['sha256'] == r['sha256'], name)
        ex = load(ROOT / 'validation/navigation-mbon-intervention-plan.json')
        ck('execution_identity', ex['trials'] == plan['trials'] and ex['prior_run_dir'] == plan['original_run_dir']
           and ex['run_dir'] == plan['branch_run_dir'])
        df = pd.read_feather(GRAPH / 'neurons.feather')
        ids = np.load(GRAPH / 'neuron_ids.npy')
        ptr = np.load(GRAPH / 'indptr.npy')
        dst = np.load(GRAPH / 'targets.npy', mmap_mode='r')
        n = len(ids)
        ck('metadata_graph_order', np.array_equal(ids, df.bodyId.to_numpy()) and n == plan['neurons'])
        kc = np.flatnonzero(df['class'].eq('Kenyon_Cell'))
        apl = np.flatnonzero(df['type'].eq('APL'))
        alpn = np.flatnonzero(df['class'].eq('ALPN'))
        target = np.sort(np.r_[kc, apl])
        ck('disjoint_targets', len(np.unique(target)) == len(target) == 4066 and len(kc) == 4064 and len(apl) == 2)
        target_mask = np.zeros(n, bool)
        target_mask[target] = True
        edges = np.flatnonzero(target_mask[dst])
        source = np.searchsorted(ptr[1:], edges, side='right')
        tc = np.searchsorted(target, dst[edges])
        sources = np.unique(source)
        sc = np.searchsorted(sources, source)
        w32 = np.load(GRAPH / 'weights.npy', mmap_mode='r')[edges]
        w = w32.astype(np.float64)
        contact = np.load(GRAPH / 'contact_counts.npy', mmap_mode='r')[edges]
        ck('direct_CSR_rows', np.all((ptr[source] <= edges) & (edges < ptr[source + 1]))
           and np.array_equal(target[tc], dst[edges]) and len(np.unique(source * n + dst[edges])) == len(edges))
        ck('edge_domain', w32.dtype == np.float32 and np.isfinite(w).all() and np.all(contact > 0)
           and not np.intersect1d(edges, ex['suppressed_edge_indices']).size)
        ck('graph_scope', plan['graph_scope'] == dict(target_cells=len(target), incoming_edges=len(edges), source_cells=len(sources)))
        with np.load(ROOT / 'validation/navigation-ladder-mbon-input-arrays.npz', allow_pickle=False) as old:
            subset = kc[np.isin(kc, old['source_indices'])]
        to_kc = source[np.isin(dst[edges], kc)]
        to_apl = source[np.isin(dst[edges], apl)]
        groups = dict(KC_all=kc, KC_MBON12_14_presynaptic=subset, KC_not_in_MBON_subset=kc[~np.isin(kc, subset)],
                      APL=apl, ALPN_all=alpn, ALPN_to_KC=alpn[np.isin(alpn, to_kc)], ALPN_to_APL=alpn[np.isin(alpn, to_apl)])
        groups['SEZPN_all'] = np.flatnonzero(df['class'].eq('SEZPN'))
        groups['SEZPN_to_KC'] = groups['SEZPN_all'][np.isin(groups['SEZPN_all'], to_kc)]
        groups['visual_projection_to_KC'] = np.flatnonzero(df.superclass.eq('visual_projection') & np.isin(np.arange(n), to_kc))
        for label in sorted(set(df.iloc[kc].type)):
            groups['KC_type:' + label] = kc[df.iloc[kc].type.to_numpy() == label]
        for side in ['L', 'R']:
            groups['KC_soma:' + side] = kc[df.iloc[kc].somaSide.to_numpy() == side]
        ck('all_group_definitions', {k: dict(indices=v.tolist(), body_ids=ids[v].tolist(), cells=len(v)) for k, v in groups.items()} == plan['groups'])
        ck('KC_denominators', len(subset) == 3957 and len(groups['KC_not_in_MBON_subset']) == 107
           and len(alpn) == 686 and len(groups['ALPN_to_KC']) == 314)
        labels, codes = {}, {}
        values = {'class': df.iloc[sources]['class'].fillna('<missing>').astype(str).to_numpy(),
                  'nt': df.iloc[sources].consensus_nt.fillna('<missing>').astype(str).to_numpy(),
                  'target_type': df.iloc[target].type.to_numpy()}
        values['group'] = values['class'].copy()
        values['group'][np.isin(sources, apl)] = 'APL (type override)'
        for k, value in values.items():
            labels[k] = sorted(set(value))
            codes[k] = np.array([{label: j for j, label in enumerate(labels[k])}[v] for v in value], np.int64)
        ck('exact_labels', labels == plan['labels'] == result['labels'])
        activity = np.unique(np.r_[sources, target, *groups.values()])
        expected_common = dict(target_graph_indices=target, source_graph_indices=sources, edge_indices=edges,
            edge_source_indices=source, edge_source_columns=sc, edge_target_columns=tc, edge_weights=w32,
            edge_contacts=contact, target_type_codes=codes['target_type'], window_edges_ticks=BOUNDS,
            source_class_codes=codes['class'], source_group_codes=codes['group'], source_nt_codes=codes['nt'],
            activity_graph_indices=activity)
        with np.load(ROOT / result['array_artifact']['path'], allow_pickle=False) as stored:
            seen = set()
            def arr(key, expected, floating=False):
                actual = stored[key]
                seen.add(key)
                if floating:
                    ck('nominal_float_dtype', actual.dtype == expected.dtype and actual.shape == expected.shape, key)
                    close('nominal_float', actual, expected)
                else:
                    ck('array_exact', exact(actual, expected), key)
            for k, value in expected_common.items():
                arr(k, value)
            csv = pd.read_csv(ROOT / result['cell_artifact']['path'], dtype=str, keep_default_na=False)
            expected_csv = df.iloc[activity][['bodyId', 'type', 'class', 'subclass', 'somaSide', 'rootSide', 'consensus_nt', 'model_sign']].fillna('').astype(str).reset_index(drop=True)
            expected_csv.insert(0, 'graph_index', activity.astype(str))
            for key, group in [('is_KC', kc), ('is_APL', apl), ('is_ALPN', alpn)]:
                expected_csv[key] = np.isin(activity, group).astype(str)
            ck('cell_metadata_CSV', csv.equals(expected_csv))
            sign = (np.sign(w) + 1).astype(np.int64)
            pos, neg = w > 0, w < 0
            nt, kt = len(target), len(labels['target_type'])
            for name, group in [('all', sources), ('ALPN', alpn), ('KC', kc), ('APL', apl)]:
                mask = np.isin(source, group)
                pairs = np.bincount(tc[mask], minlength=nt)
                contacts = integer_bins(tc[mask], contact[mask], nt)
                arr('anatomy_' + name + '_source_pairs', pairs)
                arr('anatomy_' + name + '_contacts', contacts)
                ck('static_population', result['anatomy'][name] == dict(directed_pairs=int(mask.sum()), contacts=int(contacts.sum()),
                   distinct_sources=len(np.unique(source[mask])), target_cells=int(np.count_nonzero(pairs))), name)
            for g, label in enumerate(labels['group']):
                mask = codes['group'][sc] == g
                ck('static_source_group', result['source_group_static'][label] == dict(directed_pairs=int(mask.sum()),
                   contacts=int(contact[mask].sum()), source_cells=int(np.count_nonzero(codes['group'] == g)),
                   positive_edges=int(np.count_nonzero(pos & mask)), negative_edges=int(np.count_nonzero(neg & mask)),
                   zero_edges=int(np.count_nonzero((w == 0) & mask))), label)
            oldrun, newrun = ROOT / plan['original_run_dir'], ROOT / plan['branch_run_dir']
            artifacts = load(oldrun / 'artifact-manifest.json')['artifacts']
            for spec in plan['trials']:
                artifacts += load(newrun / spec['name'] / 'result.json')['artifacts']
            authority = {r['path']: r for r in artifacts}
            def read(stem):
                for suffix in ['.npz', '.json', '.complete.json']:
                    p = Path(str(stem) + suffix)
                    r = authority[str(p.relative_to(ROOT))]
                    ck('authoritative_archive_pin', audit.record(r), r['path'])
                out = audit.archive(stem)
                ck('archive_all_checks_passed', not audit.failures)
                return out
            cache, fulls, summaries = {}, {}, {}
            def checkpoint(run, spec, tick):
                stem = run / spec['name'] / f'checkpoint-{tick:05d}'
                key = str(stem)
                if key not in cache:
                    cache[key] = read(stem)
                return cache[key]
            for spec in plan['trials']:
                for arm, run_dir in [('control', oldrun), ('intervention', newrun)]:
                    context = dict(ordinal=spec['ordinal'], arm=arm)
                    pfx = f"trial_{spec['ordinal']}_{arm}"
                    terminal = load(run_dir / spec['name'] / 'terminal.json')
                    ck('authoritative_trial_complete', terminal['complete'] and audit.record(terminal['result']))
                    final = checkpoint(run_dir, spec, 30000)
                    full = final['window_counts_observed']
                    ck('full_counts', full.dtype == np.int64 and full.shape == (7, n) and np.all(full >= 0))
                    ck('target_not_exogenous', not np.intersect1d(final['input_indices'], target).size)
                    tails = np.empty((8, len(sources)), np.int64)
                    states = {k: np.empty((8, nt), np.float64) for k in ['v', 's', 'h']}
                    for j, b in enumerate(BOUNDS):
                        cprun = oldrun if arm == 'intervention' and b < 5000 else run_dir
                        cp = checkpoint(cprun, spec, int(b))
                        ck('checkpoint_identity', cp['tick'] == b and cp['time_ms'] == b * .1 and cp['seed'] == spec['seed']
                           and cp['arm'] == 'H1' and cp['coherent_state'] and cp['failure'] is None and cp['graph_sha256'] == ex['graph_sha256'])
                        pp = cp['parameters']
                        ck('checkpoint_parameters', pp['dt_ms'] == .1 and pp['delay_ticks'] == 18
                           and pp['resting_mv'] == -52. and pp['inhibitory_reversal_mv'] == -75.)
                        ck('checkpoint_unblocked', cp['blocked'].dtype == np.bool_ and cp['blocked'].shape == (n,) and not cp['blocked'].any())
                        ck('checkpoint_prefix_counts', exact(cp['window_counts_observed'][:j], full[:j]) and not cp['window_counts_observed'][j:].any())
                        for k in states:
                            ck('checkpoint_state_domain', cp[k].dtype == np.float64 and cp[k].shape == (n,) and np.isfinite(cp[k]).all())
                            states[k][j] = cp[k][target]
                        pc, pending = cp['pending_count'], cp['pending']
                        ck('pending_domain', pc.dtype == np.int64 and pc.shape == (19,) and np.all(pc >= 0)
                           and pending.dtype == np.int32 and pending.shape == (int(pc.sum()),)
                           and np.all((pending >= 0) & (pending < n)))
                        cuts = np.r_[0, np.cumsum(pc)]
                        for slot in range(19):
                            cells = pending[cuts[slot]:cuts[slot + 1]]
                            emission = int(b) + (slot - int(b)) % 19 - 18
                            ck('pending_slot_order_horizon', (not len(cells) or (emission >= 0 and int(b) - 18 <= emission < b))
                               and np.all(np.diff(cells) > 0) and np.all(cp['last'][cells] >= emission))
                        tails[j] = np.bincount(pending, minlength=n)[sources]
                    emissions = full[:, sources]
                    arrivals = emissions + tails[:-1] - tails[1:]
                    ck('delayed_arrival_conservation', not tails[0].any() and np.all(arrivals >= 0)
                       and np.array_equal(arrivals.sum(0) + tails[-1], emissions.sum(0)))
                    arr(pfx + '_counts', full[:, activity])
                    arr(pfx + '_source_emissions', emissions)
                    arr(pfx + '_boundary_tail_counts', tails)
                    arr(pfx + '_nominal_source_arrivals', arrivals)
                    for k, value in states.items():
                        arr(pfx + '_boundary_' + ('p' if k == 's' else k), value)
                    if arm == 'intervention':
                        ck('reused_prefix_counts', exact(full[:2], fulls[(spec['ordinal'], 'control')][:2]))
                        for k in states:
                            previous = stored[f"trial_{spec['ordinal']}_control_boundary_" + ('p' if k == 's' else k)]
                            ck('reused_prefix_states', exact(states[k][:3], previous[:3]))
                    total = np.zeros((7, nt, 3), np.int64)
                    pv, hv = np.zeros((7, nt)), np.zeros((7, nt))
                    rolls = {}
                    for kind in ['group', 'nt']:
                        ng = len(labels[kind])
                        rolls[kind] = dict(arrivals=np.zeros((7, kt, ng, 3), np.int64), contacts=np.zeros((7, kt, ng, 3), np.int64),
                                           p_increment=np.zeros((7, kt, ng)), h_increment=np.zeros((7, kt, ng)))
                    for j in range(7):
                        counts = arrivals[j, sc]
                        total[j] = integer_bins(tc * 3 + sign, counts, nt * 3).reshape(nt, 3)
                        positive = counts[pos] * w[pos]
                        inhibitory = counts[neg] * (-w[neg] / 23.)
                        pv[j] = np.bincount(tc[pos], weights=positive, minlength=nt)
                        hv[j] = np.bincount(tc[neg], weights=inhibitory, minlength=nt)
                        for kind, rr in rolls.items():
                            ng = len(labels[kind])
                            group_index = codes['target_type'][tc] * ng + codes[kind][sc]
                            flat = group_index * 3 + sign
                            rr['arrivals'][j] = integer_bins(flat, counts, kt * ng * 3).reshape(kt, ng, 3)
                            ck('contact_product_no_overflow', int(counts.max(initial=0)) * int(contact.max(initial=0)) < 2**63)
                            rr['contacts'][j] = integer_bins(flat, counts * contact, kt * ng * 3).reshape(kt, ng, 3)
                            rr['p_increment'][j] = np.bincount(group_index[pos], weights=positive, minlength=kt * ng).reshape(kt, ng)
                            rr['h_increment'][j] = np.bincount(group_index[neg], weights=inhibitory, minlength=kt * ng).reshape(kt, ng)
                            ck('independent_integer_rollup_conservation', np.array_equal(rr['arrivals'][j].sum((0, 1)), total[j].sum(0)))
                            close('independent_positive_rollup_conservation', rr['p_increment'][j].sum(), pv[j].sum())
                            close('independent_negative_rollup_conservation', rr['h_increment'][j].sum(), hv[j].sum())
                    arr(pfx + '_target_nominal_signed_arrivals', total)
                    arr(pfx + '_target_nominal_p_increment', pv, True)
                    arr(pfx + '_target_nominal_h_increment', hv, True)
                    for kind, rr in rolls.items():
                        for k, value in rr.items():
                            arr(pfx + '_' + kind + '_' + k, value, 'increment' in k)
                    saved = next(t for t in result['trials'] if t['spec']['ordinal'] == spec['ordinal'] and t['arm'] == arm)
                    summary = {k: metrics(full, v) for k, v in groups.items()}
                    tree('population_metric', saved['groups'], summary)
                    tree('nominal_group_totals', saved['nominal_input_group_totals'],
                         {kind: {k: value.sum(1).tolist() for k, value in rr.items()} for kind, rr in rolls.items()})
                    fulls[(spec['ordinal'], arm)] = full.copy()
                    summaries[(spec['ordinal'], arm)] = summary
                    completed.append(context.copy())
                    cache.clear()
            ck('all_payload_fields_reviewed', seen == set(stored.files), sorted(set(stored.files) - seen))
            for pair in result['paired']:
                seed = pair['seed']
                base = next(s['ordinal'] for s in plan['trials'] if s['seed'] == seed and s['condition'] == 'constant_baseline')
                ea = next(s['ordinal'] for s in plan['trials'] if s['seed'] == seed and s['condition'] == 'ethyl_acetate')
                def diff(left, right):
                    return {k: (np.array(summaries[left][k]['mean_rates_hz']) - np.array(summaries[right][k]['mean_rates_hz'])).tolist()
                            if len(v) else None for k, v in groups.items()}
                expected = dict(seed=seed, EA_minus_constant={a: diff((ea, a), (base, a)) for a in ['control', 'intervention']},
                                intervention_minus_control={str(o): diff((o, 'intervention'), (o, 'control')) for o in [base, ea]})
                tree('paired_contrast', pair, expected)
            ck('paired_seed_coverage', [p['seed'] for p in result['paired']] == [11, 12, 13])
        source_end = [record(ROOT / r['path']) for r in source_start]
        ck('source_and_artifacts_unchanged', source_end == source_start)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc(), context=context)
    review = dict(schema=1, passed=error is None and not audit.failures and len(completed) == 12,
                  completed_utc=datetime.now(timezone.utc).isoformat(), source_start=source_start, source_end=source_end,
                  preflight=pure, completed=completed, check_count=sum(v['checked'] for v in audit.categories.values()),
                  categories=audit.categories, failures=audit.failures, error=error, numerical_max_abs_differences=maxima,
                  decoded_archives=audit.decoded_archives, decoded_arrays=audit.decoded_arrays,
                  wall_seconds=time.perf_counter() - started,
                  scope='All twelve histories: direct retained CSR identity/contact/weight inventory; all full final counts and target boundary v/p/h; every valid pending source at eight boundaries; independently shifted nominal input totals, all populations/rollups and paired contrasts.',
                  limits=['No network integration, parameter fitting, producer import, or new source research.',
                          'Full final checkpoint counts rely on earlier certified raw-stream audits; this bounded review does not rescan every original spike.',
                          'Pending queues independently check the producer raw-timestamp boundary tails; all unsaved per-tick KC/APL states and receptor currents remain unknown.',
                          'Nominal p/h increments are un-decayed algebraic inventories. Regrouped floating sums use the predeclared atol1e-7/rtol1e-12; integer contact/event counts and saved boundary states are exact.',
                          'Class/type/soma metadata are literal annotations, not inferred compartments, claws, physiological ensemble identity, or calibrated response criteria.',
                          'Reused branch prefix is not independent evidence; all twelve histories were previously inspected and are not held-out biology.'])
    with OUTPUT.open('x') as f:
        json.dump(review, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(passed=review['passed'], checks=review['check_count'], completed=len(completed),
                         result=record(OUTPUT), error=error, maxima=maxima)))
    return 0 if review['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['fixture', 'run'])
    if parser.parse_args().command == 'fixture':
        print(json.dumps(fixture()))
    else:
        raise SystemExit(run())
