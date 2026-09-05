#!/usr/bin/env python3
"""Frozen graph/count/input inventory; no network integration or fitting."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd
from analyze_navigation_ladder_timing import Reader, load, record, write_new

ROOT=Path(__file__).resolve().parents[1]
PREFIX=ROOT/'validation/pn-kc-apl-inventory'
GRAPH=ROOT/'data/processed/malecns_v1'
EXECUTION=ROOT/'validation/navigation-mbon-intervention-plan.json'
IDENTITY=ROOT/'validation/pn-kc-apl-identity-review.json'
WINDOWS=np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)
DT=.0001


def path(suffix):return Path(str(PREFIX)+suffix)


def delayed_counts(emitted,tails):
    return emitted+tails[:-1]-tails[1:]


def fixture():
    bounds=np.array([0,20,50,80]);tt=np.array([0,1,19,20,31,32,49,50,62,63,79]);ii=np.array([0,1,0,0,1,0,1,0,1,0,1])
    counts=np.array([np.bincount(ii[(tt>=a)&(tt<b)],minlength=3) for a,b in zip(bounds[:-1],bounds[1:])])
    tails=np.array([np.bincount(ii[(tt>=b-18)&(tt<b)],minlength=3) for b in bounds])
    actual=delayed_counts(counts,tails)
    expected=np.array([np.bincount(ii[(tt+18>=a)&(tt+18<b)],minlength=3) for a,b in zip(bounds[:-1],bounds[1:])])
    assert np.array_equal(actual,expected)
    assert actual.sum()+tails[-1].sum()==len(tt)
    assert not actual[:,2].any() and np.all(actual>=0)
    return dict(passed=True,checks=3,scope='Exact delayed-window identity including lower/upper endpoints and pending tail.')


def anatomy():
    df=pd.read_feather(GRAPH/'neurons.feather');ids=np.load(GRAPH/'neuron_ids.npy')
    assert np.array_equal(ids,df.bodyId.to_numpy())
    kc=np.flatnonzero(df['class'].eq('Kenyon_Cell'));apl=np.flatnonzero(df.type.eq('APL'));alpn=np.flatnonzero(df['class'].eq('ALPN'))
    target=np.union1d(kc,apl);ptr=np.load(GRAPH/'indptr.npy');targets=np.load(GRAPH/'targets.npy',mmap_mode='r')
    e=np.flatnonzero(np.isin(targets,target));src=np.searchsorted(ptr,e,side='right')-1;tc=np.searchsorted(target,targets[e]);sources,sc=np.unique(src,return_inverse=True)
    weights=np.load(GRAPH/'weights.npy',mmap_mode='r')[e];contacts=np.load(GRAPH/'contact_counts.npy',mmap_mode='r')[e]
    assert len(np.unique(src*len(ids)+targets[e]))==len(e) and np.isfinite(weights).all() and np.all(contacts>0)
    with np.load(ROOT/'validation/navigation-ladder-mbon-input-arrays.npz',allow_pickle=False) as z:
        subset=np.intersect1d(z['source_indices'],kc)
    groups={'KC_all':kc,'KC_MBON12_14_presynaptic':subset,'KC_not_in_MBON_subset':np.setdiff1d(kc,subset),'APL':apl,'ALPN_all':alpn,
            'ALPN_to_KC':np.intersect1d(src[np.isin(targets[e],kc)],alpn),'ALPN_to_APL':np.intersect1d(src[np.isin(targets[e],apl)],alpn)}
    groups['SEZPN_all']=np.flatnonzero(df['class'].eq('SEZPN'))
    groups['SEZPN_to_KC']=np.intersect1d(src[np.isin(targets[e],kc)],groups['SEZPN_all'])
    groups['visual_projection_to_KC']=np.intersect1d(src[np.isin(targets[e],kc)],np.flatnonzero(df.superclass.eq('visual_projection')))
    for name in sorted(df.iloc[kc].type.unique()):groups['KC_type:'+name]=kc[df.iloc[kc].type.to_numpy()==name]
    for side in ['L','R']:groups['KC_soma:'+side]=kc[df.iloc[kc].somaSide.to_numpy()==side]
    source_class=df.iloc[sources]['class'].fillna('<missing>').astype(str).to_numpy()
    source_group=source_class.copy();source_group[np.isin(sources,apl)]='APL (type override)'
    source_nt=df.iloc[sources].consensus_nt.fillna('<missing>').astype(str).to_numpy()
    labels={};codes={}
    for k,v in [('class',source_class),('group',source_group),('nt',source_nt)]:labels[k],codes[k]=np.unique(v,return_inverse=True)
    target_type=df.iloc[target].type.to_numpy();type_labels,type_codes=np.unique(target_type,return_inverse=True)
    common=dict(target_graph_indices=target,source_graph_indices=sources,edge_indices=e,edge_source_indices=src,edge_source_columns=sc,
                edge_target_columns=tc,edge_weights=weights,edge_contacts=contacts,target_type_codes=type_codes,window_edges_ticks=WINDOWS)
    common.update({'source_'+k+'_codes':v for k,v in codes.items()})
    return df,ids,groups,common,{**{k:v.tolist() for k,v in labels.items()},'target_type':type_labels.tolist()}


def prepare():
    assert not any(path(s).exists() for s in ['-plan.json','-results.json','-arrays.npz','-cells.csv'])
    preflight=fixture();ex=load(EXECUTION);identity=load(IDENTITY);assert identity['passed']
    complete=load(ROOT/'validation/navigation-mbon-intervention-completion.json');assert complete['passed'] and complete['execution_plan']==record(EXECUTION)
    for r in complete['reviews_and_figures']:assert record(ROOT/r['path'])==r
    for r in identity['inputs']:assert record(ROOT/r['path'])==r,r['path']
    input_result=load(ROOT/'validation/navigation-ladder-mbon-input-results.json')
    assert record(ROOT/'validation/navigation-ladder-mbon-input-arrays.npz') in input_result['artifacts']
    df,ids,groups,common,labels=anatomy()
    assert len(groups['KC_all'])==4064 and len(groups['APL'])==2 and len(groups['KC_MBON12_14_presynaptic'])==3957
    assert not np.intersect1d(common['edge_indices'],ex['suppressed_edge_indices']).size
    inputs=[Path(__file__),ROOT/'scripts/analyze_navigation_ladder_timing.py',EXECUTION,IDENTITY,
            ROOT/'validation/navigation-mbon-intervention-completion.json',ROOT/'validation/navigation-mbon-intervention-independent-review.json',
            ROOT/'validation/navigation-ladder-mbon-input-results.json',ROOT/'validation/navigation-ladder-mbon-input-arrays.npz',
            ROOT/'validation/navigation-ladder-mbon-input-independent-review.json',ROOT/'docs/pn-kc-apl-calibration-plan.md']
    inputs += [GRAPH/n for n in ['manifest.json','neurons.feather','neuron_ids.npy','indptr.npy','targets.npy','weights.npy','contact_counts.npy','signs.npy']]
    for run in [ex['prior_run_dir'],ex['run_dir']]:
        inputs += [ROOT/run/'results.json',ROOT/run/'terminal.json']
        for spec in ex['trials']:inputs += [ROOT/run/spec['name']/n for n in ['result.json','terminal.json']]
    inputs += [ROOT/ex['prior_run_dir']/'artifact-manifest.json',ROOT/'validation/inhibitory-recurrent-panel-H1-batch-review.json']
    for r in identity['inputs']:
        if ROOT/r['path'] not in inputs:inputs.append(ROOT/r['path'])
    for p in inputs:
        if p.name=='terminal.json':
            t=load(p);assert t['complete']
            for key in ['result','results','artifact_manifest']:
                if key in t:assert record(ROOT/t[key]['path'])==t[key]
    pins=[record(p) for p in inputs];graphpins={p.name:record(p) for p in inputs if p.parent==GRAPH}
    for name,r in (load(GRAPH/'manifest.json')['arrays']|load(GRAPH/'manifest.json')['metadata']).items():assert graphpins[name]['sha256']==r['sha256']
    plan=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,
        original_run_dir=ex['prior_run_dir'],branch_run_dir=ex['run_dir'],trials=ex['trials'],neurons=len(ids),
        window_edges_ticks=WINDOWS.tolist(),dt_s=DT,delay_ticks=18,labels=labels,
        groups={k:dict(indices=v.tolist(),body_ids=ids[v].tolist(),cells=len(v)) for k,v in groups.items()},
        graph_scope=dict(target_cells=len(common['target_graph_indices']),incoming_edges=len(common['edge_indices']),source_cells=len(common['source_graph_indices'])),
        selections={'KC':'class exactly Kenyon_Cell; exact type strings for subdivisions; no subclass labels inferred.',
                    'APL':'type exactly APL; class is missing, and its explicit source-group override is not an anatomical class annotation.',
                    'ALPN':'class exactly ALPN, including missing/non-PN primary type names; actual outgoing selected edges define upstream subsets.',
                    'incoming':'All retained CSR edges onto all KCs or APL, including sources outside PN/KC/APL and every model sign.'},
        method='Twelve complete saved histories reduced together. Full-final-checkpoint emission counts are already raw-spike audited. Decode exact final18ticks before each windowboundary from rawspikes, and shift emissions to nominalarrival windows by count conservation. Reviewer independently checks tails against full checkpoint queues. Retain available boundary v/p/h, not unsaved continuous KC voltage.',
        metrics=['Exact per-cell/group seven-window counts, rates, any-spike fraction, active-cell rate quantiles, pairwise EA−constant and intervention−control.',
                 'Per-cell pulse-minus-baseline rate changes and fraction positive; descriptive, not statistically reliable calcium recruitment.',
                 'Directed pair/contact/weight inventories; incoming ALPN/KC/APL source counts are not claw counts.',
                 'Nominal signed input counts and H1 positive/h increments without decay, grouped by target exacttype and sourcegroup/NT; all source histories retained for reconstruction.'],
        numerical_tolerance=dict(atol=1e-7,rtol=1e-12),preflight=preflight,
        limits=['No simulation, fitting, new inhibition or default change. All12 histories have already been inspected; no held-out biological validation.',
                'Branch prefix before5000 is reused; source spike histories after5000 are the altered recurrent histories, not replayed controls.',
                'Nominal arrivals derive from emission+18. They are not release probabilities, receptor currents, claws, physiological PN ensembles or measured synaptic efficacies.',
                'No KC/APL incoming edge is in the MBON suppression set; all stored source-block masks must be false. This does not validate the synapse sign rule.',
                'Boundary voltage samples do not reveal continuous subthreshold dynamics or evoked latency.',
                'Any-spike and baseline-rate differences do not implement a reliable calcium-response criterion. No universal5% objective.',
                'Exacttype/somaSide are recorded annotations. Missing subclass/rootSide/compartment information is not imputed. Groups overlap.'])
    write_new(path('-plan.json'),plan);print(json.dumps(record(path('-plan.json'))))


def read_fields(reader,stem,fields):
    h,p=reader.header(stem);m=dict(h['tree']['items'])
    with np.load(p,allow_pickle=False) as z:out={k:reader.array(m[k]['array'],z) for k in fields}
    return out,m


def grouped(counts,indices):
    c=counts[:,indices];duration=np.diff(WINDOWS)*DT;rates=c/duration[:,None];active=c>0
    return dict(cells=len(indices),spikes=c.sum(axis=1).tolist(),active_cells=active.sum(axis=1).tolist(),
                any_spike_fraction=active.mean(axis=1).tolist() if len(indices) else None,
                mean_rates_hz=rates.mean(axis=1).tolist() if len(indices) else None,
                active_rate_quantiles_hz=[np.quantile(r[a],[0,.25,.5,.75,1.]).tolist() if a.any() else None for r,a in zip(rates,active)],
                pulse_minus_prebaseline_rate_hz=(rates[2]-rates[1]).tolist(),
                pulse_rate_above_baseline_cells=int((rates[2]>rates[1]).sum()))


def analyze():
    assert not any(path(s).exists() for s in ['-results.json','-arrays.npz','-cells.csv'])
    plan=load(path('-plan.json'));start=time.perf_counter();reader=None;context=None
    result=dict(schema=1,passed=False,plan=record(path('-plan.json')),trials=[],paired=[],labels=plan['labels'],limits=plan['limits'])
    try:
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        df,ids,groups,a,labels=anatomy();assert labels==plan['labels']
        for k,v in groups.items():assert v.tolist()==plan['groups'][k]['indices']
        oldrun=ROOT/plan['original_run_dir'];newrun=ROOT/plan['branch_run_dir']
        artifacts=load(oldrun/'artifact-manifest.json')['artifacts']+sum([load(newrun/s['name']/'result.json')['artifacts'] for s in plan['trials']],[])
        reader=Reader(dict(artifacts=artifacts));target=a['target_graph_indices'];sources=a['source_graph_indices'];src=a['edge_source_columns'];tc=a['edge_target_columns'];w=a['edge_weights'].astype(np.float64);contact=a['edge_contacts'];neg=w<0;pos=w>0;sign=np.sign(w).astype(int)+1
        selected=np.unique(np.concatenate([sources,target,*groups.values()]));a['activity_graph_indices']=selected
        metadata=df.iloc[selected][['bodyId','type','class','subclass','somaSide','rootSide','consensus_nt','model_sign']].copy();metadata.insert(0,'graph_index',selected)
        metadata['is_KC']=np.isin(selected,groups['KC_all']);metadata['is_APL']=np.isin(selected,groups['APL']);metadata['is_ALPN']=np.isin(selected,groups['ALPN_all'])
        with path('-cells.csv').open('x',newline='') as f:metadata.to_csv(f,index=False,lineterminator='\n')
        nt=len(target);kt=len(labels['target_type']);typecode=a['target_type_codes'][tc]
        static={}; groupcode=a['source_group_codes'][src]
        for name,mask in [('all',np.ones(len(w),bool)),('ALPN',np.isin(a['edge_source_indices'],groups['ALPN_all'])),('KC',np.isin(a['edge_source_indices'],groups['KC_all'])),('APL',np.isin(a['edge_source_indices'],groups['APL']))]:
            pair=np.bincount(tc[mask],minlength=nt);ct=np.zeros(nt,np.int64);np.add.at(ct,tc[mask],contact[mask])
            a['anatomy_'+name+'_source_pairs']=pair;a['anatomy_'+name+'_contacts']=ct
            static[name]=dict(directed_pairs=int(mask.sum()),contacts=int(ct.sum()),distinct_sources=int(len(np.unique(a['edge_source_indices'][mask]))),target_cells=int(np.count_nonzero(pair)))
        result['anatomy']=static;result['source_group_static']={}
        for g,label in enumerate(labels['group']):
            mask=groupcode==g;result['source_group_static'][label]=dict(directed_pairs=int(mask.sum()),contacts=int(contact[mask].sum()),source_cells=int((a['source_group_codes']==g).sum()),positive_edges=int(pos[mask].sum()),negative_edges=int(neg[mask].sum()),zero_edges=int((w[mask]==0).sum()))
        lookup={};control_boundary={}
        for spec in plan['trials']:
            for arm,run in [('control',oldrun),('intervention',newrun)]:
                context=(spec['ordinal'],arm);reader.current=context;pfx=f"trial_{spec['ordinal']}_{arm}"
                final,m=read_fields(reader,run/spec['name']/'checkpoint-30000',['window_counts_observed','input_indices'])
                full=final['window_counts_observed'];reader.check('full-count-shape',full.shape==(7,len(ids)) and full.dtype==np.int64 and np.all(full>=0))
                reader.check('target-not-directly-stimulated',not np.intersect1d(target,final['input_indices']).size)
                tails=np.zeros((8,len(sources)),np.int64);states={k:np.empty((8,nt)) for k in ['v','s','h']}
                source_lookup=np.full(len(ids),-1,np.int32);source_lookup[sources]=np.arange(len(sources))
                for j,b in enumerate(WINDOWS):
                    cp_run=oldrun if arm=='intervention' and b<5000 else run
                    cp,head=read_fields(reader,cp_run/spec['name']/f'checkpoint-{b:05d}',['v','s','h','blocked','window_counts_observed'])
                    reader.check('checkpoint-clock',head['tick']['value']==int(b) and head['arm']['value']=='H1' and head['coherent_state']['value'])
                    parameters={k:v['value'] for k,v in head['parameters']['items']}
                    reader.check('H1-impulse-units',parameters['dt_ms']==.1 and parameters['delay_ticks']==18 and parameters['inhibitory_reversal_mv']==-75. and parameters['resting_mv']==-52.)
                    reader.check('unblocked-sources',not cp['blocked'].any())
                    expected=full.copy();expected[j:]=0
                    reader.check('checkpoint-prefix-counts',np.array_equal(cp['window_counts_observed'],expected))
                    for k in states:states[k][j]=cp[k][target]
                    if b:
                        rawrun=oldrun if arm=='intervention' and b<=5000 else run
                        sp,items=reader.spikes(rawrun/spec['name']/f'chunk-{b//50-1:04d}')
                        reader.check('tail-chunk-clock',items['start_tick']['value']==int(b-50) and items['end_tick']['value']==int(b))
                        z=sp[(sp['tick']>=b-18)&(sp['tick']<b)];keep=source_lookup[z['index']]>=0
                        tails[j]=np.bincount(source_lookup[z['index'][keep]],minlength=len(sources))
                if arm=='control':control_boundary[spec['ordinal']]=states
                else:
                    for k in states:reader.check('reused-prefix-state',np.array_equal(states[k][:3].view(np.uint64),control_boundary[spec['ordinal']][k][:3].view(np.uint64)))
                emitted=full[:,sources];arrivals=delayed_counts(emitted,tails)
                reader.check('delayed-count-conservation',np.all(arrivals>=0) and np.array_equal(arrivals.sum(axis=0)+tails[-1],emitted.sum(axis=0)))
                a[pfx+'_counts']=full[:,selected];a[pfx+'_source_emissions']=emitted;a[pfx+'_boundary_tail_counts']=tails;a[pfx+'_nominal_source_arrivals']=arrivals
                for k,v in states.items():a[pfx+'_boundary_'+('p' if k=='s' else k)]=v
                total_arrivals=np.zeros((7,nt,3),np.int64);positive=np.zeros((7,nt));inhibitory=np.zeros((7,nt))
                roll={}
                for kind in ['group','nt']:
                    ng=len(labels[kind]);roll[kind]={'arrivals':np.zeros((7,kt,ng,3),np.int64),'contacts':np.zeros((7,kt,ng,3),np.int64),'p_increment':np.zeros((7,kt,ng)),'h_increment':np.zeros((7,kt,ng))}
                for j in range(7):
                    n=arrivals[j,src];np.add.at(total_arrivals[j],(tc,sign),n)
                    positive[j]=np.bincount(tc[pos],weights=n[pos]*w[pos],minlength=nt)
                    inhibitory[j]=np.bincount(tc[neg],weights=n[neg]*(-w[neg])*(1./23.),minlength=nt)
                    for kind in roll:
                        code=a['source_'+kind+'_codes'][src];ng=len(labels[kind]);rr=roll[kind]
                        np.add.at(rr['arrivals'][j],(typecode,code,sign),n);np.add.at(rr['contacts'][j],(typecode,code,sign),n*contact)
                        ix=typecode*ng+code
                        rr['p_increment'][j]=np.bincount(ix[pos],weights=n[pos]*w[pos],minlength=kt*ng).reshape(kt,ng)
                        rr['h_increment'][j]=np.bincount(ix[neg],weights=n[neg]*(-w[neg])*(1./23.),minlength=kt*ng).reshape(kt,ng)
                        reader.check('rollup-arrival-conservation',np.array_equal(rr['arrivals'][j].sum(axis=(0,1)),total_arrivals[j].sum(axis=0)))
                        reader.check('rollup-positive-conservation',np.isclose(rr['p_increment'][j].sum(),positive[j].sum(),rtol=1e-12,atol=1e-7))
                        reader.check('rollup-negative-conservation',np.isclose(rr['h_increment'][j].sum(),inhibitory[j].sum(),rtol=1e-12,atol=1e-7))
                a[pfx+'_target_nominal_signed_arrivals']=total_arrivals;a[pfx+'_target_nominal_p_increment']=positive;a[pfx+'_target_nominal_h_increment']=inhibitory
                for kind,rr in roll.items():
                    for k,v in rr.items():a[pfx+'_'+kind+'_'+k]=v
                summary=dict(spec=spec,arm=arm,groups={k:grouped(full,v) for k,v in groups.items()},nominal_input_group_totals={kind:{k:v.sum(axis=1).tolist() for k,v in rr.items()} for kind,rr in roll.items()},boundary_state_scope='Eight boundary samples only; p/h not integrated here.')
                result['trials'].append(summary);lookup[(spec['ordinal'],arm)]=summary
        for seed in [11,12,13]:
            base=next(s['ordinal'] for s in plan['trials'] if s['seed']==seed and s['condition']=='constant_baseline');odor=next(s['ordinal'] for s in plan['trials'] if s['seed']==seed and s['condition']=='ethyl_acetate')
            pair=dict(seed=seed,EA_minus_constant={},intervention_minus_control={})
            for arm in ['control','intervention']:
                pair['EA_minus_constant'][arm]={k:(np.array(lookup[(odor,arm)]['groups'][k]['mean_rates_hz'])-np.array(lookup[(base,arm)]['groups'][k]['mean_rates_hz'])).tolist() if len(v) else None for k,v in groups.items()}
            for o in [base,odor]:pair['intervention_minus_control'][str(o)]={k:(np.array(lookup[(o,'intervention')]['groups'][k]['mean_rates_hz'])-np.array(lookup[(o,'control')]['groups'][k]['mean_rates_hz'])).tolist() if len(v) else None for k,v in groups.items()}
            result['paired'].append(pair)
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        with path('-arrays.npz').open('xb') as f:np.savez_compressed(f,**a)
        result.update(passed=True,array_artifact=record(path('-arrays.npz')),cell_artifact=record(path('-cells.csv')),checks=reader.counts,manifest_files_checked=len(reader.checked))
    except BaseException as e:result.update(error_type=type(e).__name__,error=str(e),context=context,traceback=traceback.format_exc())
    result['wall_seconds']=time.perf_counter()-start;result['completed_utc']=datetime.now(timezone.utc).isoformat();write_new(path('-results.json'),result)
    print(json.dumps(dict(passed=result['passed'],result=record(path('-results.json')),wall_seconds=result['wall_seconds'])))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['fixture','prepare','analyze']);cmd=parser.parse_args().command
    if cmd=='fixture':print(json.dumps(fixture()))
    elif cmd=='prepare':prepare()
    else:analyze()
