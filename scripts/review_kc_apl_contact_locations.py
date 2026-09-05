#!/usr/bin/env python3
"""Independent complete local partner-table rescan and selected spatial join audit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / 'validation/kc-apl-contact-location'
PLAN = Path(str(PREFIX) + '-plan.json')
RESULT = Path(str(PREFIX) + '-results.json')
OUTPUT = Path(str(PREFIX) + '-independent-review.json')
GRAPH = ROOT / 'data/processed/malecns_v1'
PLAN_SHA = '6bd090686794cb71fe727014f0fc34c4e864d4d226646e8832fb05bb41cdff33'
RESULT_SHA = 'd1bb03121cfa97efdf5641d2fd712094349000c3afc7bc6e40fd0648bd1f59e6'
SOURCE_SHA = '959d8ef4173b35382a3e6acfaf5167c795b6d10b877572d146af04e1b487bc07'
RAW = ['x_pre', 'y_pre', 'z_pre', 'body_pre', 'conf_pre', 'x_post', 'y_post', 'z_post', 'body_post', 'conf_post', 'primary_post']
COORDS = ['x_pre', 'y_pre', 'z_pre', 'x_post', 'y_post', 'z_post']


def load(p):
    return json.loads(Path(p).read_text())


def record(p):
    p = Path(p).resolve()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=h.hexdigest())


def logical(array):
    array = array.combine_chunks() if isinstance(array, pa.ChunkedArray) else array
    return pc.cast(array, array.type.value_type) if pa.types.is_dictionary(array.type) else array


def same_values(left, right):
    """Logical dictionaries, exact primitive bytes on valid rows, exact null masks."""
    left, right = logical(left), logical(right)
    if left.type != right.type or len(left) != len(right):
        return False
    lv, rv = left.is_valid().to_numpy(zero_copy_only=False), right.is_valid().to_numpy(zero_copy_only=False)
    if not np.array_equal(lv, rv):
        return False
    if pa.types.is_integer(left.type) or pa.types.is_floating(left.type):
        a, b = pc.filter(left, pa.array(lv)).to_numpy(), pc.filter(right, pa.array(rv)).to_numpy()
        return a.dtype == b.dtype and a.tobytes() == b.tobytes()
    return left.equals(right)


def label_key(value):
    return ('null', None) if value is None else ('string', value)


def fixture():
    a = pa.DictionaryArray.from_arrays(pa.array([0, 1, None]), pa.array(['CA(L)', '']))
    b = pa.DictionaryArray.from_arrays(pa.array([1, 0, None]), pa.array(['', 'CA(L)']))
    assert same_values(a, b)
    assert not same_values(a, pa.array(['CA(L)', '', 'null']))
    assert len({label_key(v) for v in [None, 'null', '', '<unspecified>']}) == 4
    values = pa.array([0, 3, None, 7, 10], pa.int64())
    hit = pc.index_in(values, value_set=pa.array([3, 7], pa.int64()))
    assert np.array_equal(np.flatnonzero(hit.is_valid().to_numpy(zero_copy_only=False)), [1, 3])
    return dict(passed=True, checks=4, scope='Logical dictionary remapping, null/string/blank separation, and independent exact target selection with an absent/out-of-range/null body.')


def run():
    if OUTPUT.exists():
        raise FileExistsError('Preserve the first independent review')
    start = time.perf_counter()
    categories, failures = {}, []
    context, error = 'preflight', None
    source_start, source_end, statistics = [], [], {}
    raw_rows = matched_rows = matched_batches = 0
    preflight = fixture()
    def ck(name, condition, detail=None):
        row = categories.setdefault(name, dict(checked=0, passed=0))
        row['checked'] += 1
        row['passed'] += int(bool(condition))
        if not condition:
            failures.append(dict(check=name, context=context, detail=detail))
            raise AssertionError(name + ': ' + str(detail or context))
    try:
        plan, result = load(PLAN), load(RESULT)
        summary = result['summary']
        ck('fixed_plan', record(PLAN)['sha256'] == PLAN_SHA)
        ck('completed_result', record(RESULT)['sha256'] == RESULT_SHA and result['passed'] and not result['errors']
           and all(result['checks'].values()) and result['partial_artifact'] is None)
        ck('result_plan_link', result['plan_sha256'] == PLAN_SHA)
        ck('no_compartment_or_model_claim', not any(result[k] for k in ['compartment_assignment', 'claw_assignment', 'model_changes', 'physiological_validation']))
        source = ROOT / 'data/raw/pn-kc-apl-compartment/syn-partners-male-cns-v1.0-minconf-0.5.feather'
        selected_path = ROOT / summary['selected_artifact']['path']
        paths = [Path(__file__), PLAN, RESULT, ROOT / result['arrays']['path'], selected_path]
        paths += [ROOT / r['path'] for r in plan['inputs']]
        source_start = [record(p) for p in dict.fromkeys(paths)]
        pins = {r['path']: r for r in source_start}
        for r in plan['inputs'] + [result['arrays'], summary['selected_artifact']]:
            ck('all_input_artifact_pins', pins[r['path']] == r, r['path'])
        ck('raw_source_pin', pins[str(source.relative_to(ROOT))]['sha256'] == SOURCE_SHA
           and pins[str(source.relative_to(ROOT))]['bytes'] == 6777179098)
        acquisition = load(ROOT / 'validation/malecns-synaptic-partners-acquisition.json')
        ck('acquisition_identity', acquisition['passed'] and acquisition['sha256'] == SOURCE_SHA
           and acquisition['expected_md5'] == acquisition['actual_md5'] and acquisition['bytes'] == 6777179098)
        inventory_plan = load(ROOT / 'validation/pn-kc-apl-inventory-plan.json')
        inventory_result = load(ROOT / 'validation/pn-kc-apl-inventory-results.json')
        inventory_review = load(ROOT / 'validation/pn-kc-apl-inventory-independent-review.json')
        ck('reviewed_inventory', inventory_result['passed'] and inventory_review['passed']
           and inventory_review['source_start'] == inventory_review['source_end'])
        reviewed = {r['path']: r for r in inventory_review['source_end']}
        for suffix in ['-plan.json', '-results.json', '-arrays.npz']:
            p = ROOT / ('validation/pn-kc-apl-inventory' + suffix)
            ck('reviewed_inventory_links', record(p) == reviewed[str(p.relative_to(ROOT))])
        ck('inventory_array_result_link', inventory_result['array_artifact'] == record(ROOT / 'validation/pn-kc-apl-inventory-arrays.npz'))
        ids = np.load(GRAPH / 'neuron_ids.npy')
        ptr = np.load(GRAPH / 'indptr.npy')
        dst = np.load(GRAPH / 'targets.npy', mmap_mode='r')
        contact = np.load(GRAPH / 'contact_counts.npy', mmap_mode='r')
        df = pd.read_feather(GRAPH / 'neurons.feather')
        ck('graph_metadata_identity', np.array_equal(ids, df.bodyId.to_numpy()) and np.all(np.diff(ids) > 0))
        manifest = load(GRAPH / 'manifest.json')
        for name in ['neuron_ids.npy', 'indptr.npy', 'targets.npy', 'contact_counts.npy']:
            ck('graph_manifest_array', record(GRAPH / name)['sha256'] == manifest['arrays'][name]['sha256'])
        ck('graph_manifest_metadata', record(GRAPH / 'neurons.feather')['sha256'] == manifest['metadata']['neurons.feather']['sha256'])
        kc = np.flatnonzero(df['class'].eq('Kenyon_Cell'))
        apl = np.flatnonzero(df.type.eq('APL'))
        target = np.sort(np.r_[kc, apl])
        ck('literal_target_population', len(kc) == 4064 and len(apl) == 2 and len(np.unique(target)) == 4066)
        target_ids = ids[target]
        target_mask = np.zeros(len(ids), bool)
        target_mask[target] = True
        edge = np.flatnonzero(target_mask[dst])
        edge_src = np.searchsorted(ptr[1:], edge, side='right')
        edge_target_col = np.searchsorted(target, dst[edge])
        expected = contact[edge].astype(np.int64)
        keys = edge_src * len(ids) + dst[edge]
        ck('CSR_unique_sorted_pairs', np.all(np.diff(keys) > 0) and len(edge) == 836650 and int(expected.sum()) == 2316256)
        ck('frozen_population_sizes', plan['targets'] == 4066 and plan['expected_modeled_pairs'] == 836650
           and plan['expected_modeled_contacts'] == 2316256)
        source_ids = np.unique(edge_src)
        group_labels = inventory_plan['labels']['group']
        classes = df.iloc[source_ids]['class'].fillna('<missing>').astype(str).to_numpy()
        classes[np.isin(source_ids, apl)] = 'APL (type override)'
        group_map = {label: i for i, label in enumerate(group_labels)}
        source_group = {int(i): group_map[label] for i, label in zip(source_ids, classes)}
        labels_expected = group_labels + ['known_graph_source_not_in_prior_input_inventory', 'outside_modeled_graph']
        ck('source_group_schema', plan['source_groups'] == summary['source_groups'] == labels_expected)
        type_labels = sorted(set(df.iloc[target].type))
        type_map = {label: i for i, label in enumerate(type_labels)}
        type_codes = np.array([type_map[v] for v in df.iloc[target].type], np.int64)
        ck('type_schema', type_labels == plan['target_types'] == summary['target_types'])
        with np.load(ROOT / 'validation/pn-kc-apl-inventory-arrays.npz', allow_pickle=False) as inv:
            for key, value in [('target_graph_indices', target), ('edge_indices', edge), ('edge_contacts', contact[edge]),
                               ('source_graph_indices', source_ids), ('target_type_codes', type_codes)]:
                ck('direct_graph_vs_inventory', np.array_equal(inv[key], value), key)
        selected = pq.read_table(selected_path)
        derived = ['source_row_ordinal', 'source_graph_index', 'target_graph_index', 'target_column', 'edge_local_index', 'source_group_code', 'roi_code']
        ck('selected_columns', selected.column_names == RAW + derived)
        ordinals = selected['source_row_ordinal'].to_numpy()
        ck('selected_order', ordinals.dtype == np.int64 and np.all(np.diff(ordinals) > 0) and len(ordinals) == summary['selected_rows'])
        full_reader = pa.ipc.open_file(pa.memory_map(str(source), 'r'))
        ck('actual_source_schema', str(full_reader.schema) == plan['source_schema'] and full_reader.schema.names == plan['source_columns']
           and full_reader.num_record_batches == plan['source_batches'] == 4759)
        include = [full_reader.schema.get_field_index(n) for n in ['body_pre', 'body_post', 'primary_post']]
        reader = pa.ipc.open_file(pa.memory_map(str(source), 'r'), options=pa.ipc.IpcReadOptions(included_fields=include))
        for batchno in range(reader.num_record_batches):
            context = dict(phase='raw_rescan', batch=batchno, raw_rows_completed=raw_rows, selected_rows_completed=matched_rows)
            batch = reader.get_batch(batchno)
            post = batch.column(batch.schema.get_field_index('body_post'))
            found = pc.index_in(post, value_set=pa.array(target_ids))
            rows = np.flatnonzero(found.is_valid().to_numpy(zero_copy_only=False))
            if len(rows):
                actual = selected.slice(matched_rows, len(rows))
                ck('complete_raw_selection_ordinals', np.array_equal(actual['source_row_ordinal'].to_numpy(), raw_rows + rows))
                # All eleven raw fields are compared at their original absolute
                # positions, without trusting the reducer's derived join fields.
                original = pa.Table.from_batches([full_reader.get_batch(batchno)]).take(pa.array(rows))
                for name in RAW:
                    ck('selected_original_raw_field', same_values(actual[name], original[name]), name)
                matched_rows += len(rows)
                matched_batches += 1
            raw_rows += batch.num_rows
        ck('full_raw_selection_coverage', raw_rows == plan['source_expected_rows'] == manifest['raw_segment_contacts'] == summary['raw_rows']
           and matched_rows == selected.num_rows == summary['selected_rows'])
        context = 'independent join and partitions'
        graph_lookup = {int(body): i for i, body in enumerate(ids)}
        target_lookup = {int(body): i for i, body in enumerate(target_ids)}
        pre = np.fromiter((graph_lookup.get(v, -1) for v in selected['body_pre'].to_pylist()), np.int64, count=selected.num_rows)
        tc = np.fromiter((target_lookup.get(v, -1) for v in selected['body_post'].to_pylist()), np.int64, count=selected.num_rows)
        ck('all_target_rows_join', np.all(tc >= 0))
        known = pre >= 0
        local = np.full(len(pre), -1, np.int64)
        joined_keys = pre[known] * len(ids) + target[tc[known]]
        candidate = np.searchsorted(keys, joined_keys)
        safe = np.minimum(candidate, len(keys) - 1)
        present = (candidate < len(keys)) & (keys[safe] == joined_keys)
        local[np.flatnonzero(known)[present]] = candidate[present]
        ng = len(labels_expected)
        groups = np.fromiter((source_group.get(int(i), ng - 2) if i >= 0 else ng - 1 for i in pre), np.int16, count=len(pre))
        roi_labels, roi_lookup, rc = [], {}, np.empty(len(pre), np.int16)
        for j, value in enumerate(selected['primary_post'].to_pylist()):
            key = label_key(value)
            if key not in roi_lookup:
                roi_lookup[key] = len(roi_labels)
                roi_labels.append(value)
            rc[j] = roi_lookup[key]
        ck('literal_ROI_labels_and_order', roi_labels == summary['roi_labels'] and len(roi_labels) < np.iinfo(np.int16).max)
        for name, value in [('source_graph_index', pre), ('target_graph_index', target[tc]), ('target_column', tc),
                            ('edge_local_index', local), ('source_group_code', groups), ('roi_code', rc)]:
            actual = selected[name].to_numpy()
            ck('derived_row_field', actual.dtype == value.dtype and actual.tobytes() == value.tobytes(), name)
        nr, nt = len(roi_labels), len(target)
        modeled = local >= 0
        counts = np.bincount(local[modeled], minlength=len(edge)).astype(np.int64)
        ck('every_CSR_contact_exact', np.array_equal(counts, expected))
        unique, multiplicity = np.unique(local[modeled] * nr + rc[modeled], return_counts=True)
        dense = np.bincount((tc * ng + groups) * nr + rc, minlength=nt * ng * nr).reshape(nt, ng, nr)
        bytype = np.bincount((type_codes[tc] * ng + groups) * nr + rc,
                             minlength=len(type_labels) * ng * nr).reshape(len(type_labels), ng, nr)
        arrays = dict(target_graph_indices=target, target_type_codes=type_codes, edge_graph_indices=edge,
                      edge_counts=counts, edge_roi_local_index=unique // nr, edge_roi_code=unique % nr,
                      edge_roi_contacts=multiplicity, target_group_roi_contacts=dense, type_group_roi_contacts=bytype)
        with np.load(ROOT / result['arrays']['path'], allow_pickle=False) as saved:
            ck('partition_payload_schema', set(saved.files) == set(arrays))
            for name, value in arrays.items():
                actual = saved[name]
                ck('all_partition_arrays_exact', actual.dtype == value.dtype and actual.shape == value.shape and actual.tobytes() == value.tobytes(), name)
        outside = int(np.count_nonzero(~known))
        missing_pair = int(np.count_nonzero(known & ~modeled))
        ck('summary_join_totals', summary['modeled_rows'] == int(counts.sum()) and summary['outside_graph_rows'] == outside
           and summary['known_source_missing_pair_rows'] == missing_pair == 0 and summary['edge_mismatches'] == 0)
        ck('complete_partitions', int(dense.sum()) == int(bytype.sum()) == selected.num_rows
           and np.array_equal(bytype.sum(0), dense.sum(0)) and int(multiplicity.sum()) == int(counts.sum()))
        ck('summary_group_ROI_counts', dense.sum(0).tolist() == summary['group_roi_contacts'])
        ck('modeled_and_outside_partitions', dense[:, -1].sum() == outside and dense[:, :-2].sum() == counts.sum()
           and dense[:, -2].sum() == 0)
        missing = {name: selected[name].null_count for name in RAW}
        ck('all_missing_field_counts', missing == summary['missing_fields'])
        bounds = [{} for _ in roi_labels]
        numerical = {}
        for name in ['conf_pre', 'conf_post'] + COORDS:
            value = selected[name].to_numpy()
            finite = np.isfinite(value)
            v = value[finite]
            stats = dict(min=float(v.min()) if len(v) else None, max=float(v.max()) if len(v) else None,
                         nonfinite=int(np.count_nonzero(~finite)))
            if name.startswith('conf'):
                stats.update(below_half=int(np.count_nonzero(v < .5)), above_one=int(np.count_nonzero(v > 1.)))
                ck('raw_confidence_anomalies', stats == summary['confidence'][name], name)
            else:
                stats.update(noninteger=int(np.count_nonzero(v != np.floor(v))), negative=int(np.count_nonzero(v < 0)))
                ck('raw_coordinate_anomalies', stats == summary['coordinates'][name], name)
                for roi in range(nr):
                    vv = value[finite & (rc == roi)]
                    if len(vv):
                        bounds[roi][name] = [float(vv.min()), float(vv.max())]
            numerical[name] = stats
        ck('all_ROI_bounds', bounds == summary['roi_coordinate_bounds_voxels'])
        identity = ['body_pre', 'body_post'] + COORDS
        # Pandas grouping is independent of the producer's Arrow group_by;
        # count logical null identities as well rather than dropping them.
        identity_frame = pd.DataFrame({name: selected[name].to_numpy() for name in identity})
        frequencies = identity_frame.value_counts(dropna=False, sort=False).to_numpy()
        duplicates = dict(unique_identities=len(frequencies), repeated_identities=int(np.count_nonzero(frequencies > 1)),
                          additional_rows=int((frequencies - 1).sum()), maximum_multiplicity=int(frequencies.max()), all_rows_retained=True)
        ck('full_partner_identity_duplicates', duplicates == summary['duplicate_identity'])
        ck('duplicate_identity_conservation', int(frequencies.sum()) == selected.num_rows)
        statistics = dict(raw_rows=raw_rows, selected_rows=matched_rows, selected_batches=matched_batches,
                          modeled_pairs=len(edge), modeled_contacts=int(counts.sum()), outside_graph_rows=outside,
                          known_source_missing_pair_rows=missing_pair, target_cells=len(target), ROI_labels=roi_labels,
                          unknown_label_counts=[dict(label=label, contacts=int(dense[:, :, i].sum())) for i, label in enumerate(roi_labels)
                                                if label is None or label == '' or 'unspecified' in label.lower()],
                          missing_fields=missing, duplicate_identity=duplicates, coordinate_scale_um_per_voxel=.008)
        context = 'final source rehash'
        source_end = [record(ROOT / r['path']) for r in source_start]
        ck('all_sources_and_outputs_unchanged', source_end == source_start)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), context=context, traceback=traceback.format_exc())
    review = dict(schema=1, passed=error is None and not failures, completed_utc=datetime.now(timezone.utc).isoformat(),
        source_start=source_start, source_end=source_end, preflight=preflight,
        check_count=sum(v['checked'] for v in categories.values()), categories=categories, failures=failures, error=error,
        statistics=statistics, last_complete_scan_counts=dict(raw_rows=raw_rows, selected_rows=matched_rows, selected_batches=matched_batches),
        wall_seconds=time.perf_counter() - start, scope='Full local source-body/ROI rescan over all record batches, complete target selection by exact body IDs, all eleven original selected raw fields at original row ordinals, direct CSR identities/contact totals, derived per-row fields, all partition arrays, metadata anomalies and partner-identity duplicates.',
        limits=['No download, simulation, parameter fitting, runtime mutation or producer import.',
                'Partner rows retain polyadic presynaptic repeats; identity duplicates are reported without removing rows.',
                'Dictionary encodings are compared as logical labels; valid numeric source fields are compared byte-for-byte, with exact null masks.',
                'Neuropils and 8nm native coordinates do not identify claws, axonal/dendritic electrical compartments or APL membrane parameters.',
                'Outside-graph source bodies, literal missing/unspecified labels and confidence/coordinate anomalies remain in their declared partitions; anatomical sums do not validate functional receptor signs.'])
    with OUTPUT.open('x') as f:
        json.dump(review, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(passed=review['passed'], checks=review['check_count'], result=record(OUTPUT), error=error, statistics=statistics)))
    return 0 if review['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['fixture', 'run'])
    if parser.parse_args().command == 'fixture':
        print(json.dumps(fixture()))
    else:
        raise SystemExit(run())
