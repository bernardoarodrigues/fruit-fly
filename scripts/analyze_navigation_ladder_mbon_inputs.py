#!/usr/bin/env python3
"""Conditional MBON synaptic-state reconstruction from saved spikes only."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time
import traceback

import numpy as np
import pandas as pd
from numba import njit
from analyze_navigation_ladder_timing import Reader

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/'validation/navigation-ladder-mbon-input'
GRAPH = ROOT/'data/processed/malecns_v1'
PANEL = ROOT/'validation/inhibitory-recurrent-panel-plan.json'
ANATOMY = ROOT/'validation/navigation-ladder-anatomy.json'
END = 30000
WINDOWS = np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)
DECAY = float(np.exp(-.1/5.))
SPIKES = np.dtype([('tick','<i8'),('index','<i4')])


def path(suffix): return Path(str(PREFIX)+suffix)
def load(p): return json.loads(Path(p).read_text())
def record(p):
    p=Path(p); h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''): h.update(b)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.hexdigest())
def write_new(p,d):
    with Path(p).open('x') as f: json.dump(d,f,indent=2,allow_nan=False); f.write('\n')


@njit(cache=True)
def reduce_chunk(lo,hi,spikes,ptr,target_cols,weights,blocked,window_by_tick,p,h,arrivals,accepted,rejected,decay):
    """Independent input-only recurrence; no voltage, threshold or new spikes."""
    j=0
    while j<len(spikes) and spikes[j]['tick']+18<lo: j+=1
    for tick in range(lo,hi):
        for target in range(p.shape[1]):
            p[tick+1,target]=p[tick,target]*decay
            h[tick+1,target]=h[tick,target]*decay
        while j<len(spikes) and spikes[j]['tick']+18==tick:
            source=spikes[j]['index']; window=window_by_tick[tick]
            for e in range(ptr[source],ptr[source+1]):
                col=target_cols[e]; w=np.float64(weights[e]); arrivals[window,e]+=1
                if blocked[source]: rejected[window,e]+=1
                else:
                    accepted[window,e]+=1
                    if w<0.: h[tick+1,col]+=-w*(1./23.)
                    else: p[tick+1,col]+=w
            j+=1


def fixture():
    # Delay, half-open window/chunk boundaries, duplicate-source multiple edges,
    # positive/negative/zero weights, blocked sources, zero-input decay and tail.
    ptr=np.array([0,3,4,5,5],np.int64); tc=np.array([0,1,1,0,1],np.int32)
    ww=np.array([.1,-.2,0.,2.,-.7],np.float32); blocked=np.array([False,True,False,False])
    sp=np.array([(0,0),(1,1),(2,2),(31,0),(32,1),(49,0),(50,2),(59,0)],dtype=SPIKES)
    win=np.repeat(np.arange(3,dtype=np.int64),20); p=np.zeros((61,2)); h=p.copy(); p[0]=[.25,.5];h[0]=[.01,.2]
    a=np.zeros((3,5),np.int64);ac=a.copy();bc=a.copy()
    for lo,hi in [(0,20),(20,50),(50,60)]: reduce_chunk(lo,hi,sp,ptr,tc,ww,blocked,win,p,h,a,ac,bc,DECAY)
    pp=np.zeros_like(p);hh=np.zeros_like(h);pp[0]=p[0];hh[0]=h[0];aa=np.zeros_like(a);bb=aa.copy()
    for tick in range(60):
        pp[tick+1]=pp[tick]*DECAY;hh[tick+1]=hh[tick]*DECAY
        for t,s in sp.tolist():
            if t+18!=tick: continue
            for e in range(ptr[s],ptr[s+1]):
                aa[tick//20,e]+=1
                if blocked[s]:bb[tick//20,e]+=1;continue
                w=float(ww[e]);col=tc[e]
                if w<0:hh[tick+1,col]+=-w*(1./23.)
                else:pp[tick+1,col]+=w
    assert np.array_equal(p,pp) and np.array_equal(h,hh)
    assert np.array_equal(a,aa) and np.array_equal(bc,bb) and np.array_equal(ac,aa-bb)
    assert a[0,0]==1 and a[1,4]==1 and a[2,0]==1 and a.sum()==9
    return dict(passed=True,checks=6,scope='Scalar independent fixture including blocked/zero edges, delay, boundaries and pending events')


def prepare():
    for suffix in ['-plan.json','-results.json','-arrays.npz','-edges.csv']:
        if path(suffix).exists(): raise FileExistsError('Preserve first audit '+suffix)
    f=fixture(); panel=load(PANEL); anatomy=load(ANATOMY)
    assert record(PANEL)['sha256']=='c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5'
    assert anatomy['passed'];run=ROOT/panel['run_dir']; terminal=load(run/'terminal.json')
    assert terminal['complete'] and terminal['status']=='complete'
    assert record(ROOT/terminal['artifact_manifest']['path'])==terminal['artifact_manifest']
    specs=[s for s in panel['order'] if s['arm']=='H1' and s['condition'] in ['constant_baseline','ethyl_acetate']]
    assert [s['ordinal'] for s in specs]==[26,29,32,35,38,41]
    paths=[Path(__file__),ROOT/'scripts/analyze_navigation_ladder_timing.py',ROOT/'scripts/review_navigation_ladder_mbon_inputs.py',
           ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'fruitfly/neural.py',
           ROOT/'docs/navigation-ladder-mbon-input-plan.md',PANEL,ANATOMY,GRAPH/'manifest.json',
           run/'terminal.json',run/'results.json',run/'artifact-manifest.json']
    paths += [GRAPH/n for n in ['neurons.feather','neuron_ids.npy','indptr.npy','targets.npy','weights.npy','contact_counts.npy','signs.npy']]
    for n in ['inhibitory-recurrent-panel-H1-batch-review.json','inhibitory-recurrent-panel-final-integrity.json','navigation-ladder-timing-independent-review.json']:
        p=ROOT/'validation'/n; d=load(p);assert d.get('passed') is True;paths.append(p)
    paths += [Path(str(run/'selection')+s) for s in ['.json','.npz','.complete.json']]
    for spec in specs:
        d=run/spec['name'];t=load(d/'terminal.json');assert t['complete'] and t['status']=='complete' and record(d/'result.json')==t['result']
        paths += [d/'terminal.json',d/'result.json']
    pins=[record(p) for p in paths];gm=load(GRAPH/'manifest.json')
    bypath={r['path']:r for r in pins}
    for n,r in (gm['arrays']|gm['metadata']).items(): assert bypath[str((GRAPH/n).relative_to(ROOT))]['sha256']==r['sha256']
    plan=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,run_dir=panel['run_dir'],trials=specs,
        targets=anatomy['groups']['MBON12_14'],neurons=panel['neurons'],graph_sha256=panel['graph_sha256'],
        window_edges_ticks=WINDOWS.tolist(),checkpoint_ticks=WINDOWS.tolist(),delay_ticks=18,dt_ms=.1,decay=DECAY,
        trace_clock='Row T is state after ticks 0 through T-1; arrival at emission+18, added after decay for that delivery tick.',
        ordering='Promote original float32 weights to float64; retain ordered source spikes and ascending original CSR edges. H1 receives during refractory/firing ticks and retains p/h through reset.',
        grouping_fields={'class':'class','nt':'consensus_nt'},missing_label='<missing>',
        isi_convention='Assign each interval to the window of its second spike, carrying previous spike across windows. First observed spike has no interval.',
        gate='Same nonmissing annotated class uniquely largest summed positive accepted increment over [5000,15000) in all six trials, after all eight checkpoint p/h bitwise gates. This is a proposed edge intervention, not proof of cause.',
        independent_regrouped_tolerances=dict(atol=1e-9,rtol=1e-12),manufactured_preflight=f,
        environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
        limits=['Saved-history synaptic-state reconstruction only; no voltage solver, threshold, new network spikes or body simulation.',
                'Transmitter-derived model signs are not calibrated receptor effects; p and h have different units and are not subtracted.',
                'Post-hoc selection reuses six previous trials; no new biological evidence or model promotion.',
                'No continuous MBON voltage was saved; input rankings alone do not establish causes of individual spikes.'])
    write_new(path('-plan.json'),plan);print(json.dumps(record(path('-plan.json'))))


def incoming(selected):
    ids=np.load(GRAPH/'neuron_ids.npy'); ptr=np.load(GRAPH/'indptr.npy'); targets=np.load(GRAPH/'targets.npy',mmap_mode='r')
    e=np.flatnonzero(np.isin(targets,selected));src=np.searchsorted(ptr,e,side='right')-1;cols=np.searchsorted(selected,targets[e])
    weights=np.load(GRAPH/'weights.npy',mmap_mode='r')[e];contacts=np.load(GRAPH/'contact_counts.npy',mmap_mode='r')[e]
    df=pd.read_feather(GRAPH/'neurons.feather');assert np.array_equal(df.bodyId.to_numpy(),ids)
    restricted_ptr=np.r_[0,np.bincount(src,minlength=len(ids)).cumsum()].astype(np.int64)
    assert np.all(e[1:]>e[:-1]) and np.all(src[1:]>=src[:-1]) and weights.dtype==np.float32 and np.isfinite(weights).all()
    assert np.array_equal(selected[cols],targets[e]) and np.all(contacts>0)
    table=pd.DataFrame(dict(edge_index=e,source_index=src,target_index=selected[cols],source_body_id=ids[src],target_body_id=ids[selected[cols]],
                           weight_float32=weights,contact_count=contacts))
    for c in ['type','class','consensus_nt','model_sign']:
        table[c]=df.iloc[src][c].fillna('<missing>').astype(str).to_numpy()
    return ids,e,src,cols.astype(np.int32),weights,contacts,restricted_ptr,table


def rollup(values,cols,codes,nlabels):
    out=np.zeros((7,10,nlabels),dtype=values.dtype)
    for w in range(7): np.add.at(out[w],(cols,codes),values[w])
    return out


def analyze():
    if any(path(s).exists() for s in ['-results.json','-arrays.npz','-edges.csv']): raise FileExistsError('Preserve first audit outputs')
    plan=load(path('-plan.json'));pr=record(path('-plan.json'));started=time.perf_counter();reader=None;arrays={};context=None
    result=dict(schema=1,passed=False,plan=pr,trials=[],limits=plan['limits'],group_labels={})
    try:
        for r in plan['inputs']: assert record(ROOT/r['path'])==r, r['path']
        run=ROOT/plan['run_dir'];reader=Reader(load(run/'artifact-manifest.json'));selected=np.array(plan['targets']['indices'],np.int32)
        ids,e,src,cols,weights,contacts,ptr,table=incoming(selected); n=plan['neurons'];sources=np.unique(src)
        reader.check('target-identity',len(selected)==10 and ids[selected].tolist()==plan['targets']['body_ids'])
        source_lookup=np.full(n,-1,np.int32);source_lookup[sources]=np.arange(len(sources),dtype=np.int32)
        target_lookup=np.full(n,-1,np.int32);target_lookup[selected]=np.arange(10,dtype=np.int32)
        window_by_tick=np.searchsorted(WINDOWS,np.arange(END),side='right')-1
        labels={};codes={}
        for kind,field in plan['grouping_fields'].items():
            labels[kind]=sorted(table[field].unique().tolist());codes[kind]=np.searchsorted(labels[kind],table[field].to_numpy())
        result['group_labels']=labels
        result['anatomy']=dict(incoming_edges=len(e),distinct_sources=len(sources),contacts=int(contacts.sum()),target_order=selected.tolist())
        arrays.update(graph_indices=selected,source_indices=sources,edge_indices=e,edge_source_indices=src,edge_target_columns=cols,
                      edge_weights=weights,edge_contact_counts=contacts,window_edges_ticks=WINDOWS,body_ids=ids[selected])
        with path('-edges.csv').open('x',newline='') as f: table.to_csv(f,index=False,float_format='%.17g',lineterminator='\n')
        def checkpoint(directory,tick,p,h,counts,tail,blocked_reference):
            head,pfile=reader.header(directory/f'checkpoint-{tick:05d}');m=dict(head['tree']['items'])
            reader.check('checkpoint-clock',m['tick']['value']==tick and m['arm']['value']=='H1' and m['coherent_state']['value'] and m['graph_sha256']['value']==plan['graph_sha256'])
            params={k:v['value'] for k,v in m['parameters']['items']}
            reader.check('checkpoint-parameters',params['dt_ms']==.1 and params['synapse_tau_ms']==5. and params['delay_ticks']==18 and params['inhibitory_reversal_mv']==-75.)
            with np.load(pfile,allow_pickle=False) as z:
                cp={k:reader.array(m[k]['array'],z) for k in ['s','h','blocked','window_counts_observed','pending_count','pending','input_indices','selected_indices','refractory']}
            reader.check('checkpoint-fixed-mask',np.array_equal(cp['blocked'],blocked_reference) and not cp['blocked'].any())
            reader.check('target-recording-boundary',not np.isin(selected,cp['input_indices']).any() and not np.isin(selected,cp['selected_indices']).any() and np.all(cp['refractory'][selected]==22))
            reader.check('checkpoint-p-bitwise',np.array_equal(p[tick].view(np.uint64),cp['s'][selected].view(np.uint64)))
            reader.check('checkpoint-h-bitwise',np.array_equal(h[tick].view(np.uint64),cp['h'][selected].view(np.uint64)))
            reader.check('checkpoint-target-counts',np.array_equal(counts,cp['window_counts_observed'][:,selected]))
            slots=(tail['tick']+18)%19; pending_counts=np.bincount(slots,minlength=19).astype(np.int64)
            pending=np.concatenate([tail['index'][slots==s] for s in range(19)])
            reader.check('checkpoint-packed-queue',np.array_equal(pending_counts,cp['pending_count']) and np.array_equal(pending,cp['pending']))
            return dict(tick=tick,p_bitwise=True,h_bitwise=True,target_counts_exact=True,all_pending_spikes_exact=True)

        for spec in plan['trials']:
            context=dict(trial=spec['name'],chunk=None);reader.current=context;directory=run/spec['name'];prefix='trial_'+str(spec['ordinal'])
            p=np.zeros((END+1,10));h=np.zeros_like(p);arrivals=np.zeros((7,len(e)),np.int64);accepted=arrivals.copy();blocked_counts=arrivals.copy()
            emissions=np.zeros((7,len(sources)),np.int64);tc=np.zeros((7,10),np.int64);blocked=np.zeros(n,np.bool_)
            arrays.update({prefix+'_p':p,prefix+'_h':h,prefix+'_edge_arrivals':arrivals,prefix+'_edge_accepted':accepted,prefix+'_edge_blocked':blocked_counts,prefix+'_source_emissions':emissions})
            carry=np.empty(0,SPIKES);tail=carry.copy();target_pieces=[];total=0;checks=[checkpoint(directory,0,p,h,tc,tail,blocked)]
            # Per-source delivery windows independently count shifted emissions.
            source_deliveries=np.zeros((7,len(sources)),np.int64);pending_sources=np.zeros(len(sources),np.int64)
            for chunk in range(600):
                lo=chunk*50;hi=lo+50;context['chunk']=chunk;reader.current=context
                packed,items=reader.spikes(directory/f'chunk-{chunk:04d}');tt=packed['tick'];ii=packed['index']
                reader.check('chunk-clock-status',items['status']['value']=='complete' and items['coherent_state']['value'] and items['failure']['value'] is None and items['partial']['value'] is None and items['start_tick']['value']==lo and items['end_tick']['value']==hi and items['completed_ticks']['value']==50 and items['requested_ticks']['value']==50)
                reader.check('ordered-spikes',np.all((tt>=lo)&(tt<hi)) and np.all((ii>=0)&(ii<n)) and (len(tt)<2 or np.all((tt[1:]>tt[:-1])|((tt[1:]==tt[:-1])&(ii[1:]>ii[:-1])))))
                pre=packed[source_lookup[ii]>=0]; post=packed[target_lookup[ii]>=0];target_pieces.append(post.copy())
                np.add.at(emissions,(window_by_tick[pre['tick']],source_lookup[pre['index']]),1)
                deliveries=pre['tick']+18;valid=deliveries<END
                np.add.at(source_deliveries,(window_by_tick[deliveries[valid]],source_lookup[pre['index'][valid]]),1)
                np.add.at(pending_sources,source_lookup[pre['index'][~valid]],1)
                joined=np.concatenate([carry,pre]);reduce_chunk(lo,hi,joined,ptr,cols,weights,blocked,window_by_tick,p,h,arrivals,accepted,blocked_counts,plan['decay'])
                carry=joined[joined['tick']+18>=hi].copy();tail=packed[tt>=hi-18].copy()
                np.add.at(tc,(window_by_tick[post['tick']],target_lookup[post['index']]),1);total+=len(packed)
                if hi in WINDOWS: checks.append(checkpoint(directory,hi,p,h,tc,tail,blocked))
            ts=np.concatenate(target_pieces);arrays[prefix+'_target_spikes']=ts
            reader.check('all-raw-spike-total',total==load(directory/'result.json')['spike_count'])
            reader.check('edge-integer-roundtrip',np.array_equal(arrivals,source_deliveries[:,source_lookup[src]]) and np.array_equal(arrivals,accepted+blocked_counts) and not blocked_counts.any())
            reader.check('pending-delivery-conservation',np.array_equal(emissions.sum(axis=0),source_deliveries.sum(axis=0)+pending_sources))
            reader.check('finite-nonnegative-states',np.isfinite(p).all() and np.isfinite(h).all() and (p>=0).all() and (h>=0).all())
            interval=np.zeros((7,10),np.int64);at22=interval.copy()
            for col,idx in enumerate(selected):
                t=ts['tick'][ts['index']==idx];isi=np.diff(t);win=window_by_tick[t[1:]]
                np.add.at(interval,(win,np.full(len(win),col)),1);np.add.at(at22,(win[isi==22],np.full(int((isi==22).sum()),col)),1)
                reader.check('refractory-lower-bound',np.all(isi>=22))
            tr=dict(spec=spec,total_raw_spikes=total,checkpoints=checks,target_counts=tc.tolist(),isi_interval_count=interval.tolist(),isi_at_22_ticks_count=at22.tolist(),
                    pending_presynaptic_spikes=int(pending_sources.sum()),synaptic_state_summary=dict(p_peak=p.max(axis=0).tolist(),h_peak=h.max(axis=0).tolist(),p_final=p[-1].tolist(),h_final=h[-1].tolist()))
            incp=np.maximum(weights.astype(np.float64),0);inch=np.maximum(-weights.astype(np.float64),0)*(1./23.)
            values=dict(arrivals=arrivals,accepted=accepted,blocked=blocked_counts,contacts=accepted*contacts,p_increment=accepted*incp,h_increment=accepted*inch)
            for kind in labels:
                for name,v in values.items(): arrays[prefix+'_'+kind+'_'+name]=rollup(v,cols,codes[kind],len(labels[kind]))
            totals=arrays[prefix+'_class_p_increment'][2:4].sum(axis=(0,1));ranking=np.argsort(-totals,kind='stable')
            tr['class_positive_ranking']=[dict(label=labels['class'][j],p_increment=float(totals[j])) for j in ranking]
            tr['unique_positive_class_winner']=labels['class'][ranking[0]] if totals[ranking[0]]>0 and (len(totals)==1 or totals[ranking[0]]>totals[ranking[1]]) else None
            result['trials'].append(tr)
        winners=[t['unique_positive_class_winner'] for t in result['trials']]
        eligible=len(set(winners))==1 and winners[0] not in [None,'<missing>']
        chosen=e[(table['class'].to_numpy()==winners[0])&(weights>0)] if eligible else np.array([],np.int64)
        arrays['proposed_intervention_edge_indices']=chosen
        result['intervention_gate']=dict(passed=eligible,winners=winners,selected_class=winners[0] if eligible else None,positive_edge_count=len(chosen),delivery_window_ticks=[5000,15000],
            status='eligible_for_separately_frozen_intervention' if eligible else 'ambiguous_no_intervention_selected',launched=False)
        for r in plan['inputs']:reader.check('frozen-input-at-end',record(ROOT/r['path'])==r)
        reader.check('plan-unchanged',record(path('-plan.json'))==pr);result['passed']=True
    except (Exception,KeyboardInterrupt) as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc),context=context,traceback=traceback.format_exc())
    with path('-arrays.npz').open('xb') as f:np.savez_compressed(f,**arrays)
    result.update(artifacts=[record(path(s)) for s in ['-arrays.npz','-edges.csv'] if path(s).exists()],completed_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started,
                  check_categories={} if reader is None else reader.counts,checked_manifest_files=0 if reader is None else len(reader.checked))
    result['check_count']=sum(result['check_categories'].values());write_new(path('-results.json'),result)
    print(json.dumps(dict(passed=result['passed'],result=record(path('-results.json')),checks=result['check_count'],error=result.get('error'))))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['fixture','prepare','analyze']);args=parser.parse_args()
    if args.action=='fixture': print(json.dumps(fixture()))
    elif args.action=='prepare': prepare()
    else: raise SystemExit(analyze())
