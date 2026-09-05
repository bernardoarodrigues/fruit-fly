#!/usr/bin/env python3
"""Partition retained KC/APL contacts by source-declared postsynaptic neuropil.

Preserve all source rows onto the targets, including presynaptic bodies outside
the modeled graph. This is anatomy, not a claw/electrical compartment inference.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'validation/kc-apl-contact-location'
PLAN=BASE.with_name(BASE.name+'-plan.json')
RESULTS=BASE.with_name(BASE.name+'-results.json')
ARRAYS=BASE.with_name(BASE.name+'-arrays.npz')
SOURCE=ROOT/'data/raw/pn-kc-apl-compartment/syn-partners-male-cns-v1.0-minconf-0.5.feather'
SELECTED=ROOT/'data/raw/pn-kc-apl-compartment/kc-apl-partners-selected.parquet'
PARTIAL=SELECTED.with_suffix('.partial.parquet')
INVENTORY=ROOT/'validation/pn-kc-apl-inventory-arrays.npz'
INVENTORY_PLAN=ROOT/'validation/pn-kc-apl-inventory-plan.json'
GRAPH=ROOT/'data/processed/malecns_v1'
RAW_COLUMNS=['x_pre','y_pre','z_pre','body_pre','conf_pre','x_post','y_post','z_post','body_post','conf_post','primary_post']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8*1024**2):h.update(b)
    return h.hexdigest()


def record(path):
    p=Path(path)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p))


def write(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


def map_sorted(ids,values):
    """Return exact indices or -1, never a neighbouring body/index."""
    ii=np.searchsorted(ids,values)
    safe=np.minimum(ii,len(ids)-1)
    return np.where((ii<len(ids)) & (ids[safe]==values),ii,-1).astype(np.int64)


def fixture():
    assert np.array_equal(map_sorted(np.array([2,5,9]),np.array([-1,2,3,5,9,10])),[-1,0,-1,1,2,-1])
    a=pa.DictionaryArray.from_arrays(pa.array([0,1,0]),pa.array(['CA(R)','MB(R)']))
    b=pa.DictionaryArray.from_arrays(pa.array([1,0]),pa.array(['MB(R)','CA(R)']))
    labels=a.to_pylist()+b.to_pylist()
    assert Counter(labels)=={'CA(R)':3,'MB(R)':2}
    assert json.dumps(None)!=json.dumps('null') and json.dumps('')!=json.dumps(None)
    return dict(passed=True,checks=3,scope='Missing/out-of-range ID joins, reordered dictionary labels, null/string/blank separation')


def prepare():
    if any(p.exists() for p in (PLAN,RESULTS,ARRAYS,SELECTED,PARTIAL)):
        raise FileExistsError('Preserve prior attempt')
    acquisition=json.loads((ROOT/'validation/malecns-synaptic-partners-acquisition.json').read_text())
    assert acquisition['passed'] and acquisition['sha256']==sha(SOURCE)
    reader=pa.ipc.open_file(pa.memory_map(str(SOURCE),'r'))
    assert set(RAW_COLUMNS)<=set(reader.schema.names)
    old=json.loads(INVENTORY_PLAN.read_text())
    inventory_result=ROOT/'validation/pn-kc-apl-inventory-results.json'
    inventory_review=ROOT/'validation/pn-kc-apl-inventory-independent-review.json'
    reviewed=json.loads(inventory_review.read_text())
    assert json.loads(inventory_result.read_text())['passed'] and reviewed['passed']
    reviewed_pins={r['path']:r['sha256'] for r in reviewed['source_end']}
    for p in [INVENTORY,INVENTORY_PLAN,inventory_result]:
        assert reviewed_pins[str(p.relative_to(ROOT))]==sha(p)
    with np.load(INVENTORY,allow_pickle=False) as a:
        targets=a['target_graph_indices'];edges=a['edge_indices'];expected=int(a['edge_contacts'].sum())
    inputs=[Path(__file__),SOURCE,ROOT/'validation/malecns-synaptic-partners-acquisition.json',INVENTORY,INVENTORY_PLAN,inventory_result,inventory_review]
    inputs += [GRAPH/(name+'.npy') for name in ['neuron_ids','indptr','targets','contact_counts']]
    inputs += [GRAPH/'neurons.feather',GRAPH/'manifest.json']
    write(PLAN,dict(schema=1,frozen_utc=datetime.now(timezone.utc).isoformat(),inputs=[record(p) for p in inputs],
        source_schema=str(reader.schema),source_columns=reader.schema.names,source_batches=reader.num_record_batches,
        source_expected_rows=json.loads((GRAPH/'manifest.json').read_text())['raw_segment_contacts'],
        targets=int(len(targets)),expected_modeled_pairs=len(edges),expected_modeled_contacts=expected,
        target_selector='All4064 class Kenyon_Cell plus2 exact type APL, exact indices from independently reviewed inventory.',
        source_groups=old['labels']['group']+['known_graph_source_not_in_prior_input_inventory','outside_modeled_graph'],target_types=old['labels']['target_type'],
        raw_selection='Every raw partner row with body_post in the4066target IDs; no confidence re-filter or deduplication. Record original absolute row ordinal and all11raw columns.',
        join='Map body IDs exactly. Modeled-source rows must match an incoming CSR edge; preserve and count any known-source/missing-edge anomaly. Outside-graph bodies remain a distinct source group.',
        labels='Decode primary_post dictionary per batch; retain exact logical strings and null separately, including blank/unassigned labels. Encounter-order labels in arrays are explicitly listed.',
        coordinate_units='Native x/y/z integer voxel coordinates. 1voxel=.008micrometres. No axis reorientation or anatomical compartment assignment.',
        duplicate_policy='Count repeated full partner identities (both IDs and all6coordinates); retain all rows, never collapse a shared presynaptic point or deduplicate counts to force equality.',
        aggregates='Every modeled edge total, sparse edge/ROI contact counts, dense target/source-group/ROI counts including outsidegraph and known-source anomalies, target-type/source-group/ROI counts, ROI coordinate bounding boxes.',
        exact_gates=['all raw rows visited','all selected targets joined','every modeled edge reproduces oldcontactcount','no known-source pair absent from graph','all partition sums exact includingnull/outsidegraph'],
        preflight=fixture(),limits=['Neuropil label is not a claw, branch or electrical compartment. ROI segmentation is coarser than EM coordinates.',
            'No runtime parameter, graph, gain, receptor sign, APL law or neuron state changes.','Raw confidence and coordinate anomalies remain reported, not hidden by additional filtering.']))
    print(json.dumps(dict(plan=record(PLAN),source_schema=str(reader.schema),batches=reader.num_record_batches)),flush=True)


def run():
    if any(p.exists() for p in (RESULTS,ARRAYS,SELECTED,PARTIAL)):
        raise FileExistsError('Preserve prior outputs')
    plan=json.loads(PLAN.read_text());start=time.perf_counter()
    for row in plan['inputs']:
        if sha(ROOT/row['path'])!=row['sha256']:raise ValueError('Frozen source changed: '+row['path'])
    checks={};errors=[];writer=None;arrays={};summary={}
    def ck(name,v):checks[name]=bool(v)
    try:
        ids=np.load(GRAPH/'neuron_ids.npy',mmap_mode='r')
        with np.load(INVENTORY,allow_pickle=False) as a:
            target_index=a['target_graph_indices'];target_types=a['target_type_codes'];source_index=a['source_graph_indices']
            edges=a['edge_indices'];es=a['edge_source_indices'];et=target_index[a['edge_target_columns']]
            expected=a['edge_contacts'].astype(np.int64);source_groups=a['source_group_codes']
        target_ids=ids[target_index];nt=len(target_ids);ng=len(plan['source_groups'])
        ck('ordered_IDs',np.all(np.diff(ids)>0) and np.all(np.diff(target_ids)>0))
        keys=es*len(ids)+et;order=np.argsort(keys);sorted_keys=keys[order]
        ck('unique_expected_pairs',np.all(np.diff(sorted_keys)>0))
        edge_counts=np.zeros(len(edges),np.int64)
        group_by_source=np.full(len(ids),-1,np.int16);group_by_source[source_index]=source_groups
        roi_lookup={};roi_labels=[];roi_counts=[];roi_bounds=[]
        edge_parts=[];roi_parts=[];raw_offset=selected_rows=outside_rows=unknown_pairs=0
        missing_fields=Counter();confidence={k:dict(min=None,max=None,nonfinite=0,below_half=0,above_one=0) for k in ['conf_pre','conf_post']}
        coordinates={k:dict(min=None,max=None,nonfinite=0,noninteger=0,negative=0) for k in ['x_pre','y_pre','z_pre','x_post','y_post','z_post']}
        reader=pa.ipc.open_file(pa.memory_map(str(SOURCE),'r'))
        for batchno in range(reader.num_record_batches):
            batch=reader.get_batch(batchno)
            matches=pc.is_in(batch.column(batch.schema.get_field_index('body_post')),value_set=pa.array(target_ids))
            rows=np.flatnonzero(matches.to_numpy(zero_copy_only=False))
            if len(rows):
                selected=pa.Table.from_batches([batch]).take(pa.array(rows)).select(RAW_COLUMNS)
                for name in RAW_COLUMNS:missing_fields[name]+=selected[name].null_count
                pre=selected['body_pre'].to_numpy();post=selected['body_post'].to_numpy()
                # Validity is separate from the safe fill value, including unsigned IDs.
                valid=pc.is_valid(selected['body_pre']).to_numpy()
                values=pc.fill_null(selected['body_pre'],0).to_numpy()
                pre_index=map_sorted(ids,values);pre_index[~valid]=-1
                target_col=map_sorted(target_ids,post)
                ck('target_join_batch_'+str(batchno),bool((target_col>=0).all()))
                known=pre_index>=0;outside_rows+=int((~known).sum())
                edge_local=np.full(len(rows),-1,np.int64)
                search=map_sorted(sorted_keys,pre_index[known]*len(ids)+target_index[target_col[known]])
                present=search>=0;known_positions=np.flatnonzero(known)
                edge_local[known_positions[present]]=order[search[present]]
                unknown_pairs+=int((~present).sum())
                modeled=edge_local>=0
                group=np.full(len(rows),ng-1,np.int16)
                group[known]=group_by_source[pre_index[known]]
                group[known & (group<0)]=ng-2
                np.add.at(edge_counts,edge_local[modeled],1)
                logical=selected['primary_post'].to_pylist();rc=np.empty(len(rows),np.int16)
                for j,label in enumerate(logical):
                    key=json.dumps(label,ensure_ascii=False)
                    if key not in roi_lookup:
                        roi_lookup[key]=len(roi_labels);roi_labels.append(label)
                        roi_counts.append(np.zeros((nt,ng),np.int64))
                        roi_bounds.append({})
                    rc[j]=roi_lookup[key]
                for roi in np.unique(rc):
                    take=rc==roi
                    np.add.at(roi_counts[roi],(target_col[take],group[take]),1)
                    for name in coordinates:
                        xx=selected[name].to_numpy()[take];finite=xx[np.isfinite(xx)]
                        if len(finite):
                            old=roi_bounds[roi].get(name,[float('inf'),-float('inf')])
                            roi_bounds[roi][name]=[min(old[0],float(finite.min())),max(old[1],float(finite.max()))]
                for name,container in list(confidence.items())+list(coordinates.items()):
                    xx=selected[name].to_numpy();finite=xx[np.isfinite(xx)]
                    container['nonfinite']+=int((~np.isfinite(xx)).sum())
                    if len(finite):
                        container['min']=float(finite.min()) if container['min'] is None else min(container['min'],float(finite.min()))
                        container['max']=float(finite.max()) if container['max'] is None else max(container['max'],float(finite.max()))
                        if name.startswith('conf'):
                            container['below_half']+=int((finite<.5).sum());container['above_one']+=int((finite>1).sum())
                        else:
                            container['noninteger']+=int((finite!=np.floor(finite)).sum());container['negative']+=int((finite<0).sum())
                edge_parts.append(edge_local[modeled]);roi_parts.append(rc[modeled])
                for name,values in [('source_row_ordinal',rows.astype(np.int64)+raw_offset),('source_graph_index',pre_index),
                                    ('target_graph_index',target_index[target_col]),('target_column',target_col),
                                    ('edge_local_index',edge_local),('source_group_code',group),('roi_code',rc)]:
                    selected=selected.append_column(name,pa.array(values))
                if writer is None:writer=pq.ParquetWriter(PARTIAL,selected.schema,compression='zstd')
                writer.write_table(selected)
                selected_rows+=len(rows)
            raw_offset+=batch.num_rows
        if writer is not None:writer.close();writer=None
        PARTIAL.rename(SELECTED)
        nr=len(roi_labels);dense=np.stack(roi_counts,axis=2)
        all_edges=np.concatenate(edge_parts);all_roi=np.concatenate(roi_parts)
        packed,counts=np.unique(all_edges*nr+all_roi,return_counts=True)
        by_type=np.zeros((len(plan['target_types']),ng,nr),np.int64)
        for typ in range(len(by_type)):by_type[typ]=dense[target_types==typ].sum(axis=0)
        arrays.update(target_graph_indices=target_index,target_type_codes=target_types,edge_graph_indices=edges,
                      edge_counts=edge_counts,edge_roi_local_index=packed//nr,edge_roi_code=packed%nr,edge_roi_contacts=counts,
                      target_group_roi_contacts=dense,type_group_roi_contacts=by_type)
        identity=['body_pre','body_post','x_pre','y_pre','z_pre','x_post','y_post','z_post']
        dup=pq.read_table(SELECTED,columns=identity+['source_row_ordinal']).group_by(identity).aggregate([('source_row_ordinal','count')])
        frequencies=dup['source_row_ordinal_count'].to_numpy()
        ck('all_source_rows_visited',raw_offset==plan['source_expected_rows'])
        ck('all_targets_retained',len(target_index)==plan['targets'])
        ck('every_modeled_edge_exact',np.array_equal(edge_counts,expected))
        ck('expected_pair_count',len(edge_counts)==plan['expected_modeled_pairs'])
        ck('expected_contact_count',edge_counts.sum()==plan['expected_modeled_contacts'])
        ck('no_known_source_missing_edge',unknown_pairs==0)
        ck('selected_rows_partition',selected_rows==int(edge_counts.sum())+outside_rows+unknown_pairs)
        ck('dense_partition_total',dense.sum()==selected_rows)
        ck('dense_modeled_total',dense[:,:ng-1].sum()==edge_counts.sum())
        ck('dense_outside_total',dense[:,ng-1].sum()==outside_rows)
        ck('edge_ROI_total',counts.sum()==edge_counts.sum())
        ck('edge_ROI_per_edge_exact',np.array_equal(np.bincount(packed//nr,weights=counts,minlength=len(edges)).astype(np.int64),expected))
        ck('type_partition_exact',by_type.sum()==selected_rows)
        summary=dict(raw_rows=raw_offset,selected_rows=selected_rows,modeled_rows=int(edge_counts.sum()),outside_graph_rows=outside_rows,
            known_source_missing_pair_rows=unknown_pairs,roi_labels=roi_labels,source_groups=plan['source_groups'],target_types=plan['target_types'],
            group_roi_contacts=dense.sum(axis=0).tolist(),roi_coordinate_bounds_voxels=roi_bounds,missing_fields=dict(missing_fields),
            confidence=confidence,coordinates=coordinates,duplicate_identity=dict(unique_identities=len(frequencies),
                repeated_identities=int((frequencies>1).sum()),additional_rows=int((frequencies-1).sum()),maximum_multiplicity=int(frequencies.max()),all_rows_retained=True),
            edge_mismatches=int(np.count_nonzero(edge_counts!=expected)),selected_artifact=record(SELECTED))
        ck('all_sources_unchanged',all(sha(ROOT/r['path'])==r['sha256'] for r in plan['inputs']))
    except (Exception,KeyboardInterrupt) as exc:
        errors.append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    finally:
        if writer is not None:writer.close()
    np.savez_compressed(ARRAYS,**arrays)
    write(RESULTS,dict(schema=1,completed_utc=datetime.now(timezone.utc).isoformat(),passed=bool(checks) and all(checks.values()) and not errors,
        plan_sha256=sha(PLAN),arrays=record(ARRAYS),summary=summary,check_count=len(checks),checks=checks,errors=errors,
        partial_artifact=record(PARTIAL) if PARTIAL.exists() else None,wall_seconds=time.perf_counter()-start,
        compartment_assignment=False,claw_assignment=False,model_changes=False,physiological_validation=False))
    print(json.dumps(dict(passed=bool(checks) and all(checks.values()) and not errors,checks=len(checks),errors=errors,
        summary={k:summary.get(k) for k in ['raw_rows','selected_rows','modeled_rows','outside_graph_rows','edge_mismatches']},wall_seconds=time.perf_counter()-start)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['fixture','prepare','run']);a=p.parse_args()
    if a.command=='fixture':print(json.dumps(fixture()))
    elif a.command=='prepare':prepare()
    else:run()
