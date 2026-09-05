#!/usr/bin/env python3
"""Read-only navigation identity/contact audit; no neural or runtime imports."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,traceback
import numpy as np
import pandas as pd
import pyarrow as pa

ROOT=Path(__file__).resolve().parents[1]
GRAPH=ROOT/'data/processed/malecns_v1'
ANNOTATIONS=ROOT/'data/raw/body-annotations-male-cns-v1.0-minconf-0.5.feather'
CONTACTS=ROOT/'data/raw/connectome-weights-male-cns-v1.0-minconf-0.5.feather'
ATTACHMENT=Path('/Users/bernardo/.codex/attachments/2fd24431-6eee-4074-835b-1a0f1203b25b/pasted-text.txt')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def clean(value):
    if isinstance(value,np.ndarray):return [clean(x) for x in value]
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if value is None or value is pd.NA or (isinstance(value,float) and np.isnan(value)):return None
    return value

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'validation/navigation-ladder-anatomy.json');args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Preserve first anatomy receipt; use a distinct --output for a later reproduction')
    result=dict(started_utc=datetime.now(timezone.utc).isoformat(),checks=[],errors=[],groups={},queries={},scope='Read-only exact MaleCNS v1.0 identities and raw contacts. No graph/model/default/gain changes; no functional calibration.')
    def ck(name,value,context=None):
        result['checks'].append(dict(name=name,passed=bool(value),context=context))
        if not value:raise ValueError(name+': '+str(context))
    paths=[Path(__file__),GRAPH/'manifest.json',ANNOTATIONS,CONTACTS]
    paths += [GRAPH/name for name in ['neurons.feather','neuron_ids.npy','indptr.npy','targets.npy','contact_counts.npy','weights.npy','signs.npy']]
    pins={str(p.relative_to(ROOT)):sha(p) for p in paths}
    result['source_sha256']=pins;result['user_claim_source']=dict(path=str(ATTACHMENT),sha256=sha(ATTACHMENT))
    try:
        manifest=json.loads((GRAPH/'manifest.json').read_text());result['graph_manifest']=manifest
        for name,record in (manifest['arrays']|manifest['metadata']).items():ck('processed_manifest_hash',pins[str((GRAPH/name).relative_to(ROOT))]==record['sha256'],name)
        for path in [ANNOTATIONS,CONTACTS]:
            original=next(r for r in manifest['sources'] if Path(r['path']).name==path.name)
            ck('raw_manifest_hash',pins[str(path.relative_to(ROOT))]==original['sha256'],path.name)
        d=pd.read_feather(GRAPH/'neurons.feather');ids=np.load(GRAPH/'neuron_ids.npy',mmap_mode='r');ptr=np.load(GRAPH/'indptr.npy',mmap_mode='r');target=np.load(GRAPH/'targets.npy',mmap_mode='r');counts=np.load(GRAPH/'contact_counts.npy',mmap_mode='r')
        ck('matrix_annotation_order',np.array_equal(ids,d.bodyId.to_numpy()) and np.all(np.diff(ids)>0))
        raw_annotation=pd.read_feather(ANNOTATIONS);retained=raw_annotation.loc[raw_annotation.superclass.notna()].sort_values('bodyId').reset_index(drop=True)
        fields=['bodyId','type','instance','superclass','class','rootSide','somaSide','entryNerve','exitNerve','group','flywireType','hemibrainType','matchingNotes','assignedOlHex1','assignedOlHex2','mcnsSerial','serialMotif']
        for field in fields:ck('raw_annotation_exact_column',clean(retained[field].tolist())==clean(d[field].tolist()),field)
        result['annotation_columns']=dict(processed=d.columns.tolist(),raw=raw_annotation.columns.tolist(),explicit_hemisphere_column='hemisphere' in d,explicit_column_or_angle_fields=[c for c in d if re.search('column|angle|azimuth',c,re.I)])
        group_defs={name:[name] for name in ['ORN_VM7d','ORN_DM1','ORN_DM4','VM7d_adPN','DM1_lPN','DM4_adPN','DM4_vPN','LHAD1b2','LHAD1b2_b','LHAD1b2_d','LHCENT3','LHPV5e1','MBON12','MBON13','MBON14','FB5AB','hDeltaC','hDeltaK','PFNa','PFL2','PFL3','DNa01','DNa02','DNg97','DNp09','DNb05','DNg34']}
        group_defs.update(ORN_DM1_DM4=['ORN_DM1','ORN_DM4'],PN_DM1_DM4_cholinergic=['DM1_lPN','DM4_adPN'],PN_DM1_DM4_all=['DM1_lPN','DM4_adPN','DM4_vPN'],LHAD1b2_family=['LHAD1b2','LHAD1b2_b','LHAD1b2_d'],MBON12_14=['MBON12','MBON13','MBON14'])
        group_indices={name:np.flatnonzero(d.type.isin(types)).astype(np.int32) for name,types in group_defs.items()}
        group_indices['ORN_DM1_DM4_known_root_side']=np.flatnonzero(d.type.isin(['ORN_DM1','ORN_DM4']) & d.rootSide.isin(['L','R'])).astype(np.int32)
        group_indices['DN_all']=np.flatnonzero(d.superclass.eq('descending_neuron')).astype(np.int32)
        effective_side=d.rootSide.fillna(d.somaSide)
        def histogram(series):
            return {('<missing>' if pd.isna(k) else str(k)):int(v) for k,v in series.value_counts(dropna=False).items()}
        def partition(indices,series):
            return {key:indices[(series.iloc[indices].isna() if key=='missing' else series.iloc[indices].eq(key)).to_numpy()].tolist() for key in ['L','R','unknown','missing']}
        for name,indices in group_indices.items():
            ck('nonempty_exact_group',len(indices)>0,name);sub=d.iloc[indices]
            selector=dict(field='type',operator='isin',values=group_defs[name]) if name in group_defs else (dict(field='superclass',operator='==',value='descending_neuron') if name=='DN_all' else dict(type_in=['ORN_DM1','ORN_DM4'],rootSide_in=['L','R']))
            result['groups'][name]=dict(indices=indices.tolist(),body_ids=ids[indices].tolist(),count=len(indices),availability='mapped',selector=selector,
                index_sha256=hashlib.sha256(indices.astype('<i4').tobytes()).hexdigest(),metadata_counts={c:histogram(sub[c]) for c in ['type','superclass','rootSide','somaSide','consensus_nt','model_sign']},
                root_side_indices=partition(indices,d.rootSide),soma_side_indices=partition(indices,d.somaSide),current_select_side_indices=partition(indices,effective_side),
                mirror_mapping=None,column_angle_mapping=None,identity_limit='Annotated population; no automatic functional equivalence or mirror pairing.')
        selected=np.unique(np.concatenate(list(group_indices.values())));metadata_fields=fields+['somaLocation','tosomaLocation','receptorType','synonyms','consensus_nt','model_sign','ground_truth','predicted_nt','predicted_nt_confidence']
        result['neurons_by_index']={}
        for i in selected:
            row={c:clean(d.iloc[i][c]) for c in metadata_fields};instance=row['instance'] or ''
            col=re.search(r'(?:^|_)C(\d+[a-z]?)(?:_|$)',instance);pb=re.search(r'_([LR]\d+)(?:_|$)',instance)
            row.update(index=int(i),instance_column_token=col.group(1) if col else None,instance_pb_glomerulus_token=pb.group(1) if pb else None,instance_irregular='irreg' in instance,token_semantics='Literal instance tokens only; no inferred angle, tuning, hemisphere or mirror transform.')
            result['neurons_by_index'][str(int(i))]=row
        dn=d.superclass.eq('descending_neuron').to_numpy();prefix=d.type.fillna('').str.startswith('DN').to_numpy()
        result['dn_selector_comparison']=dict(superclass_count=int(dn.sum()),prefix_count=int(prefix.sum()),superclass_not_prefix_indices=np.flatnonzero(dn&~prefix).tolist(),prefix_not_superclass_indices=np.flatnonzero(prefix&~dn).tolist(),prefix_only_types=histogram(d.loc[prefix&~dn,'type']))
        alias=d.flywireType.fillna('').str.contains('LHAD1b2',regex=False)&~d.type.isin(group_defs['LHAD1b2_family'])
        result['cross_namespace_alias_candidates']=dict(note='Historical/cross-dataset labels are not merged into exact primary-type groups.',rows=clean(d.loc[alias,['bodyId','type','flywireType','hemibrainType']].to_dict('records')))

        # Each query sums unsigned raw contact multiplicity, never assumed mV weights.
        definitions=[
            ('VM7d_ORN_to_adPN','ORN_VM7d','VM7d_adPN',10251,'exact primary types'),
            ('DM1_DM4_ORN_to_cholinergic_PN_pooled','ORN_DM1_DM4','PN_DM1_DM4_cholinergic',18390,'pooled four-PN target; includes cross-glomerular contacts'),
            ('DM1_DM4_PN_to_LHAD1b2_family','PN_DM1_DM4_cholinergic','LHAD1b2_family',96,'explicit19-cell family, not exact8-cell LHAD1b2'),
            ('LHAD1b2_family_to_LHCENT3','LHAD1b2_family','LHCENT3',257,'explicit19-cell family, not exact8-cell LHAD1b2'),
            ('MBON12_14_to_FB5AB','MBON12_14','FB5AB',316,'three exact primary types'),
            ('LHPV5e1_to_FB5AB','LHPV5e1','FB5AB',224,'exact primary types'),
            ('FB5AB_to_hDeltaC','FB5AB','hDeltaC',1751,'exact primary types; no driver-line functional identity inference'),
            ('PFNa_to_hDeltaC','PFNa','hDeltaC',1303,'exact primary types'),
            ('PFL3_to_DNa02','PFL3','DNa02',736,'exact primary types'),
            ('PFL3_to_DNg97','PFL3','DNg97',301,'exact primary types'),
            ('DM1_ORN_to_cognate_PN','ORN_DM1','DM1_lPN',None,'strict cognate component'),
            ('DM4_ORN_to_cognate_adPN','ORN_DM4','DM4_adPN',None,'strict cognate excitatory-PN component'),
            ('DM1_ORN_to_DM4_adPN_cross','ORN_DM1','DM4_adPN',None,'cross-glomerular component'),
            ('DM4_ORN_to_DM1_lPN_cross','ORN_DM4','DM1_lPN',None,'cross-glomerular component'),
            ('DM1_DM4_ORN_to_all_PN_pooled','ORN_DM1_DM4','PN_DM1_DM4_all',None,'includes the two GABA-annotated DM4_vPNs'),
            ('DM1_DM4_PN_to_exact_LHAD1b2','PN_DM1_DM4_cholinergic','LHAD1b2',None,'literal exact primary type'),
            ('exact_LHAD1b2_to_LHCENT3','LHAD1b2','LHCENT3',None,'literal exact primary type'),
            ('FB5AB_to_hDeltaK','FB5AB','hDeltaK',None,'malev1.0 structural comparison only'),
            ('PFNa_to_hDeltaK','PFNa','hDeltaK',None,'malev1.0 structural comparison only')]
        edge_rows={};allowed={}
        for name,pre_group,post_group,quoted,note in definitions:
            pres=group_indices[pre_group];posts=group_indices[post_group];post_mask=np.zeros(len(d),bool);post_mask[posts]=True;edge_ids=[]
            for pre in pres:
                for edge in np.arange(ptr[pre],ptr[pre+1])[post_mask[target[ptr[pre]:ptr[pre+1]]]]:
                    edge=int(edge);post=int(target[edge]);edge_ids.append(edge)
                    edge_rows[edge]=dict(edge_index=edge,pre_index=int(pre),post_index=post,pre_body_id=int(ids[pre]),post_body_id=int(ids[post]),contacts=int(counts[edge]),raw_rows=[])
                allowed.setdefault(int(ids[pre]),set()).update(int(i) for i in ids[posts])
            total=sum(edge_rows[e]['contacts'] for e in edge_ids)
            result['queries'][name]=dict(pre_group=pre_group,post_group=post_group,edge_indices=edge_ids,neuron_pairs=len(edge_ids),contacts=total,quoted_contacts=quoted,matches_quote=total==quoted if quoted is not None else None,interpretation=note)
            if quoted is not None:ck('quoted_total_under_explicit_selection',total==quoted,name)
        result['strict_cognate_cholinergic_contacts']=sum(result['queries'][name]['contacts'] for name in ['DM1_ORN_to_cognate_PN','DM4_ORN_to_cognate_adPN'])
        result['pooled_cross_glomerular_contacts']=sum(result['queries'][name]['contacts'] for name in ['DM1_ORN_to_DM4_adPN_cross','DM4_ORN_to_DM1_lPN_cross'])
        ck('pooled_cognate_cross_partition',result['strict_cognate_cholinergic_contacts']+result['pooled_cross_glomerular_contacts']==result['queries']['DM1_DM4_ORN_to_cholinergic_PN_pooled']['contacts'])
        # Independently join the original Feather rows, retaining their absolute row
        # offsets and multiplicities, including any duplicate neuron-pair rows.
        expected_pairs={(r['pre_body_id'],r['post_body_id']):r for r in edge_rows.values()};raw_totals={};raw_row_count=0;raw_contacts=0
        wanted_pres=np.array(sorted(allowed),np.int64);reader=pa.ipc.open_file(pa.memory_map(str(CONTACTS)))
        for batch_index in range(reader.num_record_batches):
            batch=reader.get_batch(batch_index);pre=batch.column('body_pre').to_numpy();post=batch.column('body_post').to_numpy();mult=batch.column('weight').to_numpy();raw_contacts+=int(mult.sum(dtype=np.uint64))
            slots=np.searchsorted(wanted_pres,pre);valid=slots<len(wanted_pres);valid[valid]&=wanted_pres[slots[valid]]==pre[valid]
            for row in np.flatnonzero(valid):
                a,b=int(pre[row]),int(post[row])
                if b not in allowed[a]:continue
                key=(a,b);raw_totals[key]=raw_totals.get(key,0)+int(mult[row]);ck('raw_selected_pair_present_in_CSR',key in expected_pairs,[a,b])
                expected_pairs[key]['raw_rows'].append(dict(batch=batch_index,row_in_batch=int(row),absolute_row=raw_row_count+int(row),contacts=int(mult[row])))
            raw_row_count+=len(pre)
        ck('raw_full_table_inventory',raw_row_count==manifest['raw_segment_edges'] and raw_contacts==manifest['raw_segment_contacts'])
        ck('raw_selected_pair_population',set(raw_totals)==set(expected_pairs))
        for key,row in expected_pairs.items():ck('raw_CSR_pair_contact_equality',raw_totals[key]==row['contacts'],list(key))
        result['contact_edges']=sorted(edge_rows.values(),key=lambda r:r['edge_index']);result['raw_contact_scan']=dict(rows=raw_row_count,contacts=raw_contacts,selected_neuron_pairs=len(edge_rows),selected_original_rows=sum(len(r['raw_rows']) for r in edge_rows.values()),columns=['body_pre','body_post','weight'])
        result['identity_limits']=[
            'somaSide and rootSide are retained separately. Current runtime fallback rootSide.fillna(somaSide) is recorded, not declared a tuning/axon hemisphere.',
            'One ORN_DM4 has rootSide unknown and no somaSide; it belongs to the106-cell anatomical union, but not its105-cell known-root-side subset.',
            'Column/glomerulus tokens parsed from instance are labels only; no validated radians, column equivalence or mirror pairs are assigned. group is an annotation grouping, not a one-to-one mirror map.',
            'The2024 VT062617 addendum makes hDeltaC versus hDeltaK functional attribution ambiguous. Keep both exact male types and their counts separately.',
            'Malev1.0 hDeltaK sparse direct contacts do not establish the same preparation, functional strength or equivalence to the earlier reference connectome.',
            'DNg34 consensus_nt is unclear and its current model_sign is zero; this audit does not assign its biological sign.',
            'Unsigned contacts do not establish synaptic efficacy, receptor sign, delays, plasticity, functional navigation membership or appropriate stimulation rates.']
    except (Exception,KeyboardInterrupt) as exc:result['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    result['final_source_sha256']={p:sha(ROOT/p) for p in pins};result['source_unchanged']=pins==result['final_source_sha256'];result['passed']=not result['errors'] and result['source_unchanged'] and all(c['passed'] for c in result['checks']);result['completed_utc']=datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(clean(result),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(result['checks']),groups={k:v['count'] for k,v in result['groups'].items()},contacts={k:v['contacts'] for k,v in result['queries'].items()},errors=result['errors']),indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
