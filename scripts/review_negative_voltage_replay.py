#!/usr/bin/env python3
"""Independent saved-data audit; does not run any free-running neural recurrence.

Checks each saved transition from its preceding saved state, independently
classifies original recorded events, and evaluates discrete impulse algebra.
Never imports the producer, fruitfly, numba, learned policy, or physics.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / 'validation/negative-voltage-replay'
OUT = ROOT / 'validation/negative-voltage-replay-independent-review.json'
EXPECTED_PLAN = '5e474e043a4c302a4694ac7b0e87db0bfce6f9de1d4a4213ae484e27399914a1'
N = 120000
CHECKS = []
INPUTS = {}


def path(suffix):
    return Path(str(PREFIX) + suffix)


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def check(name, value, **details):
    CHECKS.append(dict(name=name, passed=bool(value), **details))
    if not value:
        raise AssertionError(name)


def exact(name, a, b):
    a, b = np.asarray(a), np.asarray(b)
    check(name, a.shape == b.shape and np.array_equal(a, b))


def bits(name, a, b):
    a, b = np.asarray(a), np.asarray(b)
    check(name, a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes())


def close(name, a, b, atol=1e-9):
    a, b = np.asarray(a), np.asarray(b)
    error = float(np.max(np.abs(a - b))) if a.size else 0.
    check(name, a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
          and error <= atol, maximum_absolute_error=error, tolerance=atol)
    return error


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(name, expected, revision=None):
    p = ROOT / name
    actual = sha(p)
    record = {'current_sha256': actual, 'expected_sha256': expected['sha256'],
              'bytes': p.stat().st_size, 'location': 'working-tree'}
    if actual != expected['sha256'] and revision is not None:
        old = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT)
        record.update(location=f'git:{revision}', frozen_sha256=hashlib.sha256(old).hexdigest(),
                      frozen_bytes=len(old))
    INPUTS[name] = record
    digest = record.get('frozen_sha256', actual)
    size = record.get('frozen_bytes', record['bytes'])
    check('hash:' + name, digest == expected['sha256'] and size == expected['bytes'])


class Stream:
    def __init__(self, p):
        self.f = gzip.open(p, 'rb')
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, n):
        out = self.f.read(n)
        self.digest.update(out)
        self.size += len(out)
        return out

    def lines(self):
        while raw := self.f.readline():
            self.digest.update(raw)
            self.size += len(raw)
            assert raw.endswith(b'\n')
            yield raw

    def finish(self, name, receipt):
        assert self.read(1) == b''
        self.f.close()
        check(name, self.size == receipt['uncompressed_bytes'] and
              self.digest.hexdigest() == receipt['uncompressed_sha256'])


def original_records(condition, plan, ids, needed, target_indices):
    folder = ROOT / 'runs/flybody-rolling-loop-3e5ca3ca6c91' / condition
    summary = read(folder / 'condition-summary.json')
    assert summary['complete'] and not summary['failures']
    assert summary['completed_physical_ticks'] == 6000
    mask = np.zeros(len(ids), dtype=bool)
    for group in summary['design']['outgoing_blocks']:
        g = summary['groups'][group]
        exact(condition + ':block-group-ids:' + group, ids[g['indices']], g['neuron_ids'])
        mask[g['indices']] = True
    all_sensory = np.unique(np.concatenate([summary['groups'][x]['indices'] for x in ('odor', 'sweet', 'club')]))
    packets, start, complete, initial, union = [], [], [], [], set()
    reader = Stream(folder / 'events.jsonl.gz')
    lines = 0
    for raw in reader.lines():
        lines += 1
        if not any(tag in raw[:160] for tag in (b'"event":"initial"', b'"event":"neural_start"',
                                               b'"event":"ordered_spikes"', b'"event":"neural_complete"')):
            continue
        row = json.loads(raw)
        if row['event'] == 'initial':
            initial.append(row)
            assert row['state']['neural']['voltage_mv'] == dict(minimum=-52., maximum=-52., mean=-52.)
            assert row['state']['neural']['total_spikes'] == 0
        elif row['event'] == 'neural_start':
            k = row['tick']
            assert row['brain_t_ms'] == 2. * k and row['duration_ms'] == 2.
            drive = row['actual_drive']
            assert drive['ordered_drive_sha256'] == hashlib.sha256(canonical(
                {k: v for k, v in drive.items() if k != 'ordered_drive_sha256'})).hexdigest()
            index = np.asarray(drive['indices'], dtype=int)
            assert len(index) == len(np.unique(index))
            assert np.array_equal(ids[index], drive['neuron_ids'])
            assert not np.isin(target_indices, index).any()
            assert drive['current_mv'] is drive['poisson_weight_mv'] is None
            assert drive['disable_refractory'] is True
            rates = np.asarray(drive['rates_hz'])
            assert rates.shape == index.shape and np.isfinite(rates).all() and (rates >= 0).all()
            union.update(index.tolist())
            start.append(k)
        elif row['event'] == 'ordered_spikes':
            packets.append(row)
        elif row['event'] == 'neural_complete':
            assert row['blocked_neuron_count'] == int(mask.sum())
            assert row['sensory_outgoing_mask'] == bool(mask[all_sensory].all())
            assert row['total_spikes'] == packets[-1]['events']
            assert row['full_event_sha256'] == packets[-1]['event_sha256']
            complete.append(row['tick'])
    reader.finish(condition + ':journal-uncompressed-hash-and-eof', summary['journal'])
    check(condition + ':all-ordered-drives-and-block-metadata', start == complete == list(range(6000))
          and [x['tick'] for x in packets] == start and len(initial) == 1 and lines == summary['journal']['records'])
    stream = Stream(folder / 'spikes.bin.gz')
    assert stream.read(8) == b'FFSPK001'
    length, = struct.unpack('<I', stream.read(4))
    assert 0 < length < 65536
    header = json.loads(stream.read(length))
    assert header['format'] == 'FFSPK001' and header['endian'] == 'little'
    assert header['plan_sha256'] == plan['original_plan_sha256'] and header['graph_sha256'] == plan['graph_sha256']
    assert header['block_header_bytes'] == 32 and header['bytes_per_event'] == 16
    selected_indices, selected_ticks = [], []
    observed_targets = [[], []]
    total = 0
    for k, packet in enumerate(packets):
        offset = stream.size
        tick, count, begin, end = struct.unpack('<QQdd', stream.read(32))
        assert (tick, begin, end) == (k, k * 2., (k + 1) * 2.)
        raw_ids, raw_times = stream.read(count * 8), stream.read(count * 8)
        assert len(raw_ids) == len(raw_times) == count * 8
        digest = hashlib.sha256(struct.pack('<Q', count) + raw_ids + raw_times).hexdigest()
        record = dict(tick=k, uncompressed_offset=offset, uncompressed_block_bytes=32 + count * 16,
                      events=count, start_ms=begin, end_ms=end, event_sha256=digest)
        assert all(packet[key] == value for key, value in record.items())
        body_ids, times = np.frombuffer(raw_ids, dtype='<i8'), np.frombuffer(raw_times, dtype='<f8')
        stamps = np.rint(times / .1).astype(np.int64)
        assert np.array_equal(stamps * .1, times)
        assert ((stamps >= 20 * k) & (stamps < 20 * (k + 1))).all()
        index = np.searchsorted(ids, body_ids)
        assert (index < len(ids)).all() and np.array_equal(ids[index], body_ids)
        assert (np.diff(stamps) >= 0).all()
        assert (np.diff(index)[stamps[1:] == stamps[:-1]] > 0).all()
        keep = needed[index]
        selected_indices.append(index[keep].astype(np.int32))
        selected_ticks.append(stamps[keep].astype(np.int32))
        for j, target in enumerate(target_indices):
            observed_targets[j].extend(stamps[index == target].tolist())
        total += count
    assert record == summary['lossless_spikes']['last_complete_block']
    stream.finish(condition + ':spikes-uncompressed-hash-and-eof', summary['lossless_spikes'])
    check(condition + ':all-6000-spike-blocks-order-hashes-clocks', total == summary['lossless_spikes']['events'])
    with np.load(folder / 'brain-final-or-failure.npz') as f:
        checkpoint = {key: f[key] for key in f.files}
    metadata = json.loads(str(checkpoint.pop('metadata')))
    check(condition + ':checkpoint-clock-parameters-graph', metadata['tick'] == N and
          metadata['parameters'] == plan['parameters'] and metadata['graph_sha256'] == plan['graph_sha256'])
    exact(condition + ':checkpoint-whole-output-block-mask', mask, checkpoint['ablated'])
    return np.concatenate(selected_indices), np.concatenate(selected_ticks), observed_targets, mask, checkpoint, total, len(union)


def edge_inventory(plan):
    graph = ROOT / 'data/processed/malecns_v1'
    ids, indptr, target, weight, contacts, sign = [np.load(graph / (key + '.npy'), mmap_mode='r')
        for key in ('neuron_ids', 'indptr', 'targets', 'weights', 'contact_counts', 'signs')]
    annotations = pd.read_feather(graph / 'neurons.feather')
    edges = pd.read_csv(path('-incoming-edges.csv'), float_precision='round_trip')
    exact('annotation-body-id-order', ids, annotations.bodyId)
    assert (np.diff(ids) > 0).all()
    selected = np.searchsorted(ids, plan['target_ids'])
    exact('target-id-order', ids[selected], [67052, 13314])
    exact('target-type-order', annotations.iloc[selected]['type'], plan['target_types'])
    edge_ids, sources, slots = [], [], []
    for j, index in enumerate(selected):
        where = np.flatnonzero(target == index)
        src = np.searchsorted(indptr, where, side='right') - 1
        # Required because the producer's dense lookup holds one edge per pair.
        check(f'{ids[index]}:unique-source-target-pairs', len(src) == len(np.unique(src)))
        assert ((where >= indptr[src]) & (where < indptr[src + 1])).all()
        edge_ids.extend(where.tolist()); sources.extend(src.tolist()); slots.extend([j] * len(src))
    ei, src, slot = np.array(edge_ids), np.array(sources), np.array(slots)
    expected = dict(row=np.arange(len(ei)), graph_edge_index=ei, source_index=src, source_id=ids[src],
        target_slot=slot, target_index=selected[slot], target_id=ids[selected[slot]],
        target_type=np.asarray(plan['target_types'])[slot], source_model_sign=sign[src],
        contacts=contacts[ei], weight_mv=weight[ei].astype(np.float64),
        weight_float32_hex=np.array([x.tobytes().hex() for x in weight[ei]]))
    for column, annotation, missing in [('source_type', 'type', '[untyped]'),
            ('source_class', 'class', '[unassigned]'), ('source_superclass', 'superclass', ''),
            ('source_consensus_nt', 'consensus_nt', 'unknown')]:
        expected[column] = annotations.iloc[src][annotation].fillna(missing).astype(str).to_numpy()
    for column, values in expected.items():
        exact('incoming-edge-column:' + column, edges[column], values)
    exact('annotation-and-graph-signs', annotations.iloc[src].model_sign, sign[src])
    bits('float32-contact-sign-weight-rule', weight[ei], contacts[ei].astype(np.float32) * np.float32(.275) * sign[src])
    check('incoming-counts-and-contacts', np.bincount(slot).tolist() == [2260, 435] and
          np.bincount(slot, weights=contacts[ei]).tolist() == [27830., 7247.])
    digest = hashlib.sha256()
    for array in (ids, indptr, target, weight):
        digest.update(str(array.shape).encode()); digest.update(memoryview(array).cast('B'))
    check('whole-csr-graph-fingerprint', digest.hexdigest() == plan['graph_sha256'])
    lookup = np.full((len(ids), 2), -1, dtype=np.int32)
    lookup[src, slot] = np.arange(len(edges))
    return ids, selected, edges, lookup


def condition_review(name, plan, result, ids, target_indices, edges, lookup):
    print('Reviewing saved original streams and transitions:', name, flush=True)
    source, stamps, observed, mask, final, total, union = original_records(
        name, plan, ids, (lookup >= 0).any(axis=1), target_indices)
    with np.load(path(f'-{name}-arrays.npz')) as f:
        z = {key: f[key] for key in f.files}
    expected_keys = {'sample_time_ms', 'target_ids', 'voltage_mv', 'synaptic_mv', 'emitted_spikes_by_tick',
        'accepted_positive_negative_jump_mv_by_tick', 'recorded_source_indices', 'recorded_source_spike_ticks',
        'accepted_delivery_ticks', 'accepted_edge_rows', 'recorded_target0_spike_ticks', 'recorded_target1_spike_ticks',
        'checkpoint_selected_voltage_mv', 'checkpoint_selected_synaptic_mv'}
    check(name + ':complete-archive-schema', set(z) == expected_keys)
    bits(name + ':source-indices-from-original', z['recorded_source_indices'], source)
    bits(name + ':source-ticks-from-original', z['recorded_source_spike_ticks'], stamps)
    bits(name + ':sample-clock', z['sample_time_ms'], np.arange(N + 1) * .1)
    exact(name + ':array-target-ids', z['target_ids'], plan['target_ids'])
    v, g, fired = z['voltage_mv'], z['synaptic_mv'], z['emitted_spikes_by_tick']
    check(name + ':state-array-shape-finite-and-dtype', v.shape == g.shape == (N + 1, 2)
          and v.dtype == g.dtype == np.float64 and np.isfinite(v).all() and np.isfinite(g).all()
          and fired.shape == (N, 2) and fired.dtype == np.bool_)
    bits(name + ':initial-voltage', v[0], np.full(2, -52.))
    bits(name + ':initial-synaptic', g[0], np.zeros(2))
    exact(name + ':targets-not-directly-driven-final', final['current_mv'][target_indices], [0., 0.])
    exact(name + ':target-refractory-ticks', final['refractory_ticks'][target_indices], [22, 22])
    recorded_fired = np.zeros((N, 2), dtype=bool)
    for j in range(2):
        ticks = np.array(observed[j], dtype=np.int32)
        bits(name + f':target{j}-recorded-spike-array', z[f'recorded_target{j}_spike_ticks'], ticks)
        recorded_fired[ticks, j] = True
    bits(name + ':all-target-spike-stamps-from-original', fired, recorded_fired)
    ticks = np.arange(N)[:, None]
    last_at = np.maximum.accumulate(np.where(recorded_fired, ticks, -(2**60)), axis=0)
    last_before = np.vstack((np.full((1, 2), -(2**60), dtype=np.int64), last_at[:-1]))
    available = ticks - last_before >= 22
    a, b = np.exp(-.1 / 20.), np.exp(-.1 / 5.)
    coefficient = 5. / 15. * (a - b)
    integrated_v = np.where(available, -52. + (v[:-1] + 52.) * a + g[:-1] * coefficient + 0. * (1. - a), v[:-1])
    expected_fired = available & (integrated_v > -45.)
    bits(name + ':threshold-and-refractory-from-saved-previous-state', fired, expected_fired)
    expected_v = np.where(expected_fired, -52., integrated_v)
    bits(name + ':every-voltage-transition-bitwise', v[1:], expected_v)
    eligible = available & ~expected_fired
    slot = edges.target_slot.to_numpy(int)
    weights = edges.weight_mv.to_numpy(float)
    # Expand original event order into possible target deliveries; no state model.
    possible = lookup[source].ravel()
    retain = possible >= 0
    edge = possible[retain]
    delivery = np.repeat(stamps + 18, 2)[retain]
    src = np.repeat(source, 2)[retain]
    in_horizon = delivery < N
    blocked = in_horizon & mask[src]
    accepted = np.zeros(len(edge), dtype=bool)
    candidate = in_horizon & ~blocked
    accepted[candidate] = eligible[delivery[candidate], slot[edge[candidate]]]
    rejected = candidate & ~accepted
    pending = ~in_horizon
    bits(name + ':accepted-delivery-order-and-delay', z['accepted_delivery_ticks'], delivery[accepted])
    bits(name + ':accepted-edge-order', z['accepted_edge_rows'], edge[accepted])
    classified = dict(accepted_events=accepted, source_blocked_events=blocked,
                      target_unavailable_events=rejected, beyond_horizon_events=pending)
    balance = pd.read_csv(path(f'-{name}-edge-balance.csv'), float_precision='round_trip')
    for col in edges:
        exact(name + ':balance-inventory:' + col, balance[col], edges[col])
    for col, selection in classified.items():
        exact(name + ':per-edge-classification:' + col, balance[col], np.bincount(edge[selection], minlength=len(edges)))
    exact(name + ':every-original-input-accounted-once', sum(balance[col].to_numpy() for col in classified),
          np.bincount(source, minlength=len(ids))[edges.source_index])
    expected_g = np.where(available, g[:-1] * b, g[:-1])
    # Unbuffered addition follows recorded source order, including repeated indices.
    ae, ad = edge[accepted], delivery[accepted]
    np.add.at(expected_g, (ad, slot[ae]), weights[ae])
    expected_g[expected_fired] = 0.
    bits(name + ':every-synaptic-transition-bitwise', g[1:], expected_g)
    increments = np.zeros((N, 2, 2), dtype=np.float64)
    np.add.at(increments, (ad, slot[ae], (weights[ae] < 0).astype(int)), weights[ae])
    bits(name + ':per-tick-positive-negative-jumps', z['accepted_positive_negative_jump_mv_by_tick'], increments)
    for col, archive in [('voltage_mv', v), ('synaptic_mv', g)]:
        bits(name + ':original-checkpoint:' + col, archive[-1], final[col][target_indices])
        bits(name + ':duplicated-checkpoint-array:' + col, z['checkpoint_selected_' + col], final[col][target_indices])
    exact(name + ':last-spike-ticks', last_at[-1], final['last_spike_tick'][target_indices])
    boundaries = np.r_[0, np.cumsum(final['pending_count'])]
    assert len(boundaries) == 20 and boundaries[-1] == len(final['pending'])
    needed = (lookup >= 0).any(axis=1)
    for k in range(19):
        actual = final['pending'][boundaries[k]:boundaries[k + 1]]
        expected = source[(stamps + 18 >= N) & ((stamps + 18) % 19 == k)]
        exact(name + f':pending-ring-slot-{k}-source-order', actual[needed[actual]], expected)
    exact(name + ':cumulative-signed-jump', balance.accepted_signed_jump_mv_sum,
          balance.accepted_events.to_numpy() * weights)
    for width, label in [(1000, 'last_100ms'), (10000, 'last_1s')]:
        count = np.bincount(ae[ad >= N - width], minlength=len(edges))
        exact(name + ':' + label + '-counts', balance[label + '_accepted_events'], count)
        exact(name + ':' + label + '-jumps', balance[label + '_signed_jump_mv_sum'], count * weights)
    # Independent discrete impulse response, in powers rather than producer exp(n).
    after_reset = ad > last_at[-1, slot[ae]]
    age = N - 1 - ad[after_reset]
    w = weights[ae[after_reset]]
    cg = np.bincount(ae[after_reset], weights=w * np.power(b, age), minlength=len(edges))
    cv = np.bincount(ae[after_reset], weights=w * coefficient * (np.power(a, age) - np.power(b, age)) / (a - b), minlength=len(edges))
    errors = [close(name + ':per-edge-discrete-endpoint-g', cg, balance.endpoint_g_contribution_mv),
              close(name + ':per-edge-discrete-endpoint-v', cv, balance.endpoint_v_minus_rest_contribution_mv)]
    errors += [close(name + ':summed-discrete-endpoint-g', np.bincount(slot, weights=cg), g[-1]),
               close(name + ':summed-discrete-endpoint-v', np.bincount(slot, weights=cv), v[-1] + 52.)]
    group_cols = ['target_id', 'target_type', 'source_type', 'source_consensus_nt', 'source_model_sign']
    numeric = ['contacts', *classified, 'accepted_signed_jump_mv_sum', 'endpoint_g_contribution_mv',
               'endpoint_v_minus_rest_contribution_mv', 'last_100ms_accepted_events', 'last_100ms_signed_jump_mv_sum',
               'last_1s_accepted_events', 'last_1s_signed_jump_mv_sum']
    # Independent explicit grouping, retaining all untyped/zero-sign rows.
    grouped = defaultdict(lambda: {col: [] for col in numeric})
    for row in balance.to_dict('records'):
        key = tuple(row[col] for col in group_cols)
        for col in numeric:
            grouped[key][col].append(row[col])
    type_csv = pd.read_csv(path(f'-{name}-type-balance.csv'), float_precision='round_trip')
    type_keys = [tuple(row[col] for col in group_cols) for row in type_csv.to_dict('records')]
    check(name + ':all-type-groups-preserved', len(type_keys) == len(grouped) and set(type_keys) == set(grouped))
    for col in numeric:
        # Pandas uses compensated sums; independent Python sum can differ at low bits.
        expected = np.array([sum(grouped[key][col]) for key in type_keys])
        close(name + ':type-sum:' + col, type_csv[col], expected)
    exact(name + ':type-magnitude-column', type_csv.abs_cumulative_accepted_jump, type_csv.accepted_signed_jump_mv_sum.abs())
    ordered = sorted(type_keys, key=lambda key: (key[0], -abs(sum(grouped[key]['accepted_signed_jump_mv_sum']))))
    check(name + ':type-cumulative-magnitude-ranking', ordered == type_keys)
    check(name + ':result-condition-counts', result['recorded_all_graph_events'] == total and
          result['recorded_relevant_source_events'] == len(source) and result['input_list_union_count'] == union
          and result['source_blocked_count'] == int(mask.sum()) and not result['selected_targets_in_any_input_list'])
    cells = []
    for j, target in enumerate(plan['target_ids']):
        r = result['cells'][j]
        e = balance[balance.target_id == target]
        positive, negative = e.weight_mv > 0, e.weight_mv < 0
        values = dict(id=target, type=plan['target_types'][j], incoming_edges=len(e), contacts=int(e.contacts.sum()),
            recorded_spike_ticks=observed[j], predicted_spike_ticks=np.flatnonzero(expected_fired[:, j]).tolist(),
            checkpoint_voltage_mv=float(final['voltage_mv'][target_indices[j]]), checkpoint_synaptic_mv=float(final['synaptic_mv'][target_indices[j]]),
            replayed_voltage_mv=float(v[-1, j]), replayed_synaptic_mv=float(g[-1, j]), minimum_replayed_voltage_mv=float(v[:, j].min()),
            accepted_positive_events=int(e.loc[positive, 'accepted_events'].sum()), accepted_negative_events=int(e.loc[negative, 'accepted_events'].sum()),
            accepted_zero_weight_events=int(e.loc[e.weight_mv == 0, 'accepted_events'].sum()),
            accepted_positive_jump_mv_sum=float(e.loc[positive, 'accepted_signed_jump_mv_sum'].sum()),
            accepted_negative_jump_mv_sum=float(e.loc[negative, 'accepted_signed_jump_mv_sum'].sum()),
            source_blocked_events=int(e.source_blocked_events.sum()), target_unavailable_events=int(e.target_unavailable_events.sum()),
            beyond_horizon_events=int(e.beyond_horizon_events.sum()),
            endpoint_positive_v_contribution_mv=float(e.loc[positive, 'endpoint_v_minus_rest_contribution_mv'].sum()),
            endpoint_negative_v_contribution_mv=float(e.loc[negative, 'endpoint_v_minus_rest_contribution_mv'].sum()))
        check(name + f':{target}-every-cell-summary-field', all(r[key] == value for key, value in values.items()))
        top = type_csv[type_csv.target_id == target].head(10).to_dict('records')
        check(name + f':{target}-top-ten-types', top == r['top_10_source_types_by_cumulative_magnitude'])
        values['minimum_reconstructed_sample_ms'] = float(z['sample_time_ms'][np.argmin(v[:, j])])
        cells.append(values)
    # Detailed report claims for the sensory-only history.
    if name == 'sensory_only':
        for target, types, percentage in [(67052, ['lLN2F_b', 'il3LN6'], 83.17), (13314, ['lLN2P_a', 'lLN2P_b'], 92.93)]:
            e = balance[(balance.target_id == target) & (balance.weight_mv < 0)]
            share = 100. * e[e.source_type.isin(types)].accepted_signed_jump_mv_sum.sum() / e.accepted_signed_jump_mv_sum.sum()
            check(f'{target}:documented-inhibitory-share', round(share, 2) == percentage, percentage=float(share))
        four = balance[(balance.target_id == 67052) & balance.source_id.isin([10169, 10515, 10473, 523591])]
        check('documented-four-strong-source-cells', {int(row.source_id): (int(row.contacts), int(row.accepted_events)) for row in four.itertuples()}
              == {10169: (606, 3779), 10515: (633, 3662), 10473: (397, 3613), 523591: (767, 3673)})
    return dict(condition=name, all_graph_spikes=total, relevant_source_spikes=len(source),
                potential_target_deliveries=len(edge), accepted_deliveries=int(accepted.sum()),
                source_blocked_deliveries=int(blocked.sum()), unavailable_deliveries=int(rejected.sum()),
                beyond_horizon_deliveries=int(pending.sum()), checked_state_transitions=N * 2,
                maximum_discrete_endpoint_difference_mv=max(errors), cells=cells)


def main():
    if OUT.exists():
        raise FileExistsError('Preserve the completed independent review receipt')
    report = dict(schema=1, started_utc=datetime.now(timezone.utc).isoformat(),
                  reviewer_sha256=sha(Path(__file__)), plan_sha256=sha(path('-plan.json')),
                  method='Saved-state one-step residual checks plus independent original-event classification and discrete impulse algebra; no free-running neural recurrence.',
                  full_graph_or_body_rerun=False, producer_imported_or_executed=False, conditions=[])
    try:
        plan, result = read(path('-plan.json')), read(path('-results.json'))
        check('fixed-plan-digest', report['plan_sha256'] == EXPECTED_PLAN)
        for name, record in plan['inputs'].items():
            pin(name, record, plan['git_head'] if name.startswith(('fruitfly/', 'scripts/')) else None)
        for name, record in result['artifacts'].items():
            pin(name, record)
        for name in ['validation/negative-voltage-replay-results.json', 'docs/negative-voltage-replay.md',
                     'validation/negative-voltage-replay-plot-receipt.json']:
            p = ROOT / name
            pin(name, dict(sha256=sha(p), bytes=p.stat().st_size))
        plot = read(path('-plot-receipt.json'))
        for name, expected in (plot['inputs'] | plot['outputs']).items():
            check('plot-hash:' + name, sha(ROOT / name) == expected)
        check('plan-parameters-and-targets', plan['parameters'] == dict(dt_ms=.1, resting_mv=-52., reset_mv=-52., threshold_mv=-45.,
            membrane_tau_ms=20., synapse_tau_ms=5., refractory_ms=2.2, delay_ms=1.8, poisson_weight_mv=68.75)
            and plan['target_ids'] == [67052, 13314] and plan['neural_ticks'] == N and plan['coupling_intervals'] == 6000)
        check('producer-claims-and-finished-status', result['plan_sha256'] == EXPECTED_PLAN and result['passed']
              and len(result['checks']) == 58 and all(x['pass'] for x in result['checks'])
              and not result['full_graph_rerun'] and not result['parameters_changed'] and not path('-failure.json').exists())
        ids, selected, edges, lookup = edge_inventory(plan)
        for name, condition in zip(plan['conditions'], result['conditions'], strict=True):
            assert name == condition['condition']
            report['conditions'].append(condition_review(name, plan, condition, ids, selected, edges, lookup))
        report['limits'] = [
            'Initial full synaptic state was not independently serialized; zero g and reset bookkeeping are grounded in pinned reset source.',
            'Only the final original full-network per-cell voltage/synaptic arrays were retained; interior 0.1ms target states are reconstructed and checked against equations, not directly compared to original interior arrays.',
            'Source output-mask membership between checkpoints is inferred from pinned runtime/design plus recorded counts/all-sensory flag, not a per-step full boolean mask serialization.',
            'Self/cross target source spikes remain recorded external inputs. Matching target emissions corroborates this realized history, not recurrent intervention outcomes.',
            'Conditional endpoint sums and cumulative signed jumps are numerical effective-state accounting, not biological causation, conductance, electric charge, or calibrated fly membrane potentials.',
            'No parameter changes, fitting, free-running two-cell replay, full-brain, learned-policy or physics execution occurred in this review.'
        ]
        report['passed'] = True
    except Exception as exc:
        report.update(passed=False, error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    report.update(completed_utc=datetime.now(timezone.utc).isoformat(), checks=CHECKS, inputs=INPUTS,
                  check_count=len(CHECKS), runtime=dict(numpy=np.__version__, pandas=pd.__version__))
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({key: report[key] for key in ('passed', 'check_count')}, indent=2), flush=True)
    if not report['passed']:
        print(report['traceback'], flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
