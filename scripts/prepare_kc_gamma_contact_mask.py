#!/usr/bin/env python3
"""Freeze a contact-aware fast-positive-term diagnostic; never advance a network."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
from collections import Counter
import numpy as np
import pyarrow.feather as feather
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'validation/kc-gamma-contact-mask'
GRAPH=ROOT/'data/processed/malecns_v1'
GAMMA_TYPES=('KCg','KCg-d','KCg-m','KCg-s1','KCg-s2','KCg-s3','KCg-s4')
ROIS=('gL(L)','gL(R)')

def record(p):
    p=Path(p);h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.hexdigest())
def write(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def main():
    paths=[Path(__file__),ROOT/'validation/kc-apl-contact-location-arrays.npz',ROOT/'validation/kc-apl-contact-location-results.json',ROOT/'validation/kc-apl-contact-location-independent-review.json',ROOT/'validation/kc-apl-contact-location-plan.json',ROOT/'research/24-kc-spatial-mechanism-constraints.md',ROOT/'validation/kc-spatial-mechanism-source-review.json',ROOT/'data/raw/pn-kc-apl-compartment/kc-apl-partners-selected.parquet']
    paths += [GRAPH/n for n in ['neurons.feather','neuron_ids.npy','indptr.npy','targets.npy','weights.npy','contact_counts.npy']]
    outputs={s:Path(str(BASE)+s) for s in ['-plan.json','-arrays.npz','-results.json']}
    if any(p.exists() for p in outputs.values()):raise FileExistsError('Preserve first mask attempt')
    spatial=json.loads(paths[2].read_text());review=json.loads(paths[3].read_text())
    assert spatial['passed'] and review['passed'] and not review['failures'] and review['error'] is None
    reviewed={r['path']:r for r in review['source_end']}
    for p in [paths[1],paths[2],paths[4],paths[7]]:assert record(p)==reviewed[str(p.relative_to(ROOT))]
    pins=[record(p) for p in paths]
    write(outputs['-plan.json'],dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,
        source_selector='Exact class Kenyon_Cell, any annotated KC subtype; direct adult lateral experiment stimulated a mixed alpha/beta and gamma subset. This is a declared model diagnostic, not a receptor map.',
        target_selector=dict(exact_class='Kenyon_Cell',exact_types=list(GAMMA_TYPES)),postsynaptic_primary_rois=list(ROIS),
        retained_contacts='Preserve graph contacts. Remove only the implemented fast positive contribution allocated to these contacts; leave every other contact on a mixed-ROI pair intact. Do not include PED, calyx, unspecified ROI or non-gamma targets.',
        arithmetic='Let W be the original stored float32 pair weight cast to float64, c the integer selected contacts and N all contacts on that pair. removed=float64(W)*float64(c/N); retained=float64(W)-removed. Fully selected pairs use exactly zero. Unaffected pair weights bypass this calculation and remain bitwise original. This allocates the original rounded pair weight, without installing a new per-contact gain or float32 rounding.',
        independent_check='Re-read audited raw selected partner rows, select by body IDs and literal strings, count body pairs with Counter, and join directly to full CSR. Do not use sparse edge-ROI aggregates for this check.',
        limitations=['Gamma subtype/ROI label transfer is a hypothesis, not measured receptor identity at each synapse.','Source sex and local-to-soma voltage transfer remain unresolved.','No simulation, sign reversal, GPCR kinetics, body integration, or promotion.']))
    neurons=feather.read_table(GRAPH/'neurons.feather').to_pandas();ids=np.load(GRAPH/'neuron_ids.npy');ptr=np.load(GRAPH/'indptr.npy');targets=np.load(GRAPH/'targets.npy');weights=np.load(GRAPH/'weights.npy');counts=np.load(GRAPH/'contact_counts.npy')
    assert np.array_equal(neurons.bodyId.to_numpy(),ids)
    kc=neurons['class'].eq('Kenyon_Cell').to_numpy();gamma=kc & neurons['type'].isin(GAMMA_TYPES).to_numpy()
    with np.load(paths[1],allow_pickle=False) as z:
        edges=z['edge_graph_indices'];local=z['edge_roi_local_index'];code=z['edge_roi_code'];contacts=z['edge_roi_contacts']
        roi_codes=[spatial['summary']['roi_labels'].index(s) for s in ROIS]
        chosen=np.isin(code,roi_codes);part=np.zeros(len(edges),np.int64);np.add.at(part,local[chosen],contacts[chosen])
    sources=np.searchsorted(ptr,edges,side='right')-1
    keep=kc[sources]&gamma[targets[edges]]&(part>0)
    edge=edges[keep];source=sources[keep];target=targets[edge];c=part[keep];n=counts[edge].astype(np.int64);w=weights[edge].astype(np.float64)
    assert np.all(w>0) and np.all((c>0)&(c<=n))
    removed=w*(c.astype(np.float64)/n);retained=w-removed
    assert np.all(retained>=0) and np.all(retained[c==n]==0) and np.all(retained[c<n]>0)
    # Independent body-pair/label route uses raw fields only from the separately audited table.
    kc_ids=set(map(int,ids[kc]));gamma_ids=set(map(int,ids[gamma]));counter=Counter();all_gamma_roi=Counter()
    for b in pq.ParquetFile(paths[7]).iter_batches(columns=['body_pre','body_post','primary_post']):
        pre,post,roi=(b.column(k).to_pylist() for k in range(3))
        for a,d,r in zip(pre,post,roi):
            if a in kc_ids and r in ROIS:
                all_gamma_roi['all_KC_targets']+=int(d in kc_ids)
                if d in gamma_ids:counter[(a,d)]+=1
    observed={(int(ids[s]),int(ids[t])):int(v) for s,t,v in zip(source,target,c)}
    assert counter==observed and len(counter)==len(edge)
    # Direct CSR identity and integer complement, independent of sparse local-edge indices.
    for s,t,e in zip(source,target,edge):assert ptr[s]<=e<ptr[s+1] and targets[e]==t
    assert np.array_equal(n-c,counts[edge].astype(np.int64)-np.array([counter[(int(ids[s]),int(ids[t]))] for s,t in zip(source,target)]))
    representatives=[]
    for typ in GAMMA_TYPES:
        for side in ['L','R']:
            ii=np.flatnonzero(gamma & neurons['type'].eq(typ).to_numpy() & neurons.somaSide.eq(side).to_numpy())
            if len(ii):representatives.append(int(ii[0]))
    with outputs['-arrays.npz'].open('xb') as f:np.savez_compressed(f,edge_indices=edge,source_indices=source,target_indices=target,total_contacts=n,selected_contacts=c,baseline_weight=w,removed_weight=removed,retained_weight=retained,gamma_indices=np.flatnonzero(gamma).astype(np.int32),kc_indices=np.flatnonzero(kc).astype(np.int32),representative_indices=np.array(representatives,np.int32))
    end=[record(p) for p in paths];assert pins==end
    write(outputs['-results.json'],dict(schema=1,passed=True,completed_utc=datetime.now(timezone.utc).isoformat(),plan=record(outputs['-plan.json']),arrays=record(outputs['-arrays.npz']),source_start=pins,source_end=end,
        edges=len(edge),selected_contacts=int(c.sum()),pair_total_contacts=int(n.sum()),retained_contacts_on_selected_pairs=int((n-c).sum()),fully_selected_edges=int((c==n).sum()),mixed_edges=int((c<n).sum()),gamma_cells=int(gamma.sum()),gamma_cells_receiving_selected_contacts=len(np.unique(target)),source_cells=len(np.unique(source)),all_KC_to_KC_gamma_roi_contacts=int(all_gamma_roi['all_KC_targets']),
        target_types={s:int(np.sum(c[neurons['type'].to_numpy()[target]==s])) for s in GAMMA_TYPES},source_types={str(s):int(np.sum(c[neurons['type'].to_numpy()[source]==s])) for s in np.unique(neurons['type'].to_numpy()[source])},representative_indices=representatives,
        independent_raw_pair_check=dict(passed=True,pairs=len(counter),contacts=sum(counter.values()),method='Raw body IDs and literal primary_post labels, Python Counter; exact equality with aggregate route'),
        arithmetic_checks=dict(positive_original=True,selected_bounded_by_total=True,full_pairs_exact_zero=True,mixed_pairs_strict_positive=True),network_run=False,physiological_acceptance=False))
    print(json.dumps({k:record(v) for k,v in outputs.items()}))
if __name__=='__main__':main()
