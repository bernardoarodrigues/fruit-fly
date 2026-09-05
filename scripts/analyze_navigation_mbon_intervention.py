#!/usr/bin/env python3
"""One combined, saved-data-only comparison of the six KC delivery branches."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import traceback

import numpy as np
from analyze_navigation_ladder_timing import Reader, load, record, write_new

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/'validation/navigation-mbon-intervention-analysis'
EXECUTION = ROOT/'validation/navigation-mbon-intervention-plan.json'
ANATOMY = ROOT/'validation/navigation-ladder-anatomy.json'
OLD_INPUTS = ROOT/'validation/navigation-ladder-mbon-input-arrays.npz'
REVIEW = ROOT/'validation/navigation-mbon-intervention-independent-review.json'
REVIEW_ARRAYS = ROOT/'validation/navigation-mbon-intervention-independent-review-arrays.npz'
NUMERICS = ROOT/'validation/navigation-mbon-intervention-numerics-results.json'
WINDOWS = np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)
BIN = 500
DT = .0001
SPIKES = np.dtype([('tick','<i8'),('index','<i4')])


def path(suffix): return Path(str(PREFIX)+suffix)


def spike_metrics(spikes, targets):
    counts = np.zeros((7,len(targets)),np.int64)
    intervals = counts.copy(); ceiling = counts.copy()
    binned = np.zeros((60,len(targets)),np.int64)
    first = np.full_like(counts,-1); last = first.copy()
    for col, target in enumerate(targets):
        tt = spikes['tick'][spikes['index']==target]
        assert not len(tt) or (tt.min()>=0 and tt.max()<30000 and np.all(np.diff(tt)>0))
        ww = np.searchsorted(WINDOWS,tt,side='right')-1
        counts[:,col] = np.bincount(ww,minlength=7)
        binned[:,col] = np.bincount(tt//BIN,minlength=60)
        intervals[:,col] = np.bincount(ww[1:],minlength=7)
        ceiling[:,col] = np.bincount(ww[1:][np.diff(tt)==22],minlength=7)
        for w in range(7):
            tw = tt[ww==w]
            if len(tw): first[w,col],last[w,col] = tw[0],tw[-1]
    return dict(counts=counts,isi_intervals=intervals,isi_at_22=ceiling,
                bin_counts=binned,first_ticks=first,last_ticks=last)


def fixture():
    sp = np.array([(4980,3),(5002,3),(10000,3),(15000,3),(15022,3),(29999,7)],dtype=SPIKES)
    m = spike_metrics(sp,np.array([3,7,9]))
    assert m['counts'][:,0].tolist()==[0,1,1,1,2,0,0]
    assert m['isi_at_22'][:,0].tolist()==[0,0,1,0,1,0,0]
    assert m['isi_intervals'][:,0].tolist()==[0,0,1,1,2,0,0]
    assert m['isi_intervals'][:,1:].sum()==0 and m['first_ticks'][6,1]==29999
    assert m['bin_counts'].sum()==6 and m['first_ticks'][:,2].tolist()==[-1]*7
    assert not spike_metrics(np.empty(0,SPIKES),np.array([3]))['counts'].any()
    return dict(passed=True,checks=6,scope='Half-open windows, carried ISIs, silent/first spikes and bins.')


def prepare():
    assert not any(path(s).exists() for s in ['-plan.json','-results.json','-arrays.npz'])
    preflight=fixture(); ex=load(EXECUTION); parent=load(ROOT/ex['run_dir']/'results.json')
    assert parent['complete'] and parent['passed'] and not parent['errors']
    assert parent['plan']==record(EXECUTION)
    assert [s['ordinal'] for s in ex['trials']]==[26,29,32,35,38,41]
    # Numerical/integrity failures are retained by their reviewers; no outcome
    # reduction is executed until both entire-batch reviews have passed.
    review=load(REVIEW); numerics=load(NUMERICS)
    assert review['passed'] and numerics['passed']
    assert [r['spec'] for r in parent['trials']]==ex['trials']
    publications=[review['plan'],review['array_artifact'],numerics['plan'],numerics['rows_artifact']]
    old_result=load(ROOT/'validation/navigation-ladder-mbon-input-results.json')
    publications += [old_result['plan']]+old_result['artifacts']
    assert review['array_artifact']==record(REVIEW_ARRAYS)
    assert record(OLD_INPUTS) in old_result['artifacts']
    for r in publications: assert record(ROOT/r['path'])==r,r['path']
    reviewed_inputs=[]
    for receipt in [review,numerics]:
        reviewed_plan=load(ROOT/receipt['plan']['path'])
        assert reviewed_plan['trials']==ex['trials']
        assert record(EXECUTION) in reviewed_plan['inputs']
        assert record(ROOT/ex['run_dir']/'results.json') in reviewed_plan['inputs']
        for r in reviewed_plan['inputs']:
            assert record(ROOT/r['path'])==r,r['path']
            reviewed_inputs.append(r)
    assert review['source_start']==review['source_end']==load(ROOT/review['plan']['path'])['inputs']
    old_review=load(ROOT/'validation/navigation-ladder-mbon-input-independent-review.json')
    old_result_path='validation/navigation-ladder-mbon-input-results.json'
    assert old_review['passed'] and old_review['source_start']==old_review['source_end']
    assert old_review['source_end'][old_result_path]==record(ROOT/old_result_path)
    inputs=[Path(__file__),ROOT/'scripts/analyze_navigation_ladder_timing.py',EXECUTION,ANATOMY,
            OLD_INPUTS,REVIEW,REVIEW_ARRAYS,NUMERICS,
            ROOT/'validation/navigation-ladder-mbon-input-results.json',
            ROOT/'validation/navigation-ladder-mbon-input-independent-review.json',
            ROOT/ex['prior_run_dir']/'artifact-manifest.json',
            ROOT/ex['run_dir']/'results.json',ROOT/ex['run_dir']/'terminal.json']
    inputs.extend(ROOT/r['path'] for r in publications if ROOT/r['path'] not in inputs)
    for r in reviewed_inputs:
        if ROOT/r['path'] not in inputs: inputs.append(ROOT/r['path'])
    for s in ex['trials']:
        inputs.extend(ROOT/ex['run_dir']/s['name']/n for n in ['terminal.json','result.json'])
    plan=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=[record(p) for p in inputs],
        trials=ex['trials'],prior_run_dir=ex['prior_run_dir'],run_dir=ex['run_dir'],
        targets=ex['mbon_indices'],selected_indices=ex['selected_indices'],window_edges_ticks=WINDOWS.tolist(),
        bin_ticks=BIN,dt_s=DT,pulse_ticks=[5000,10000],washout_ticks=[10000,15000],restored_input_off_ticks=[15000,30000],
        preflight=preflight,
        measures=['Per-cell seven-window spike counts/rates and ISIs exactly22ticks (second-spike assignment).',
                  'Per-seed intervention-minus-control, EA-minus-constant and their difference for every window.',
                  '50ms per-cell rate and p/h means; intervention-only MBON voltage envelope.',
                  'Full-population and all34 anatomical cohort window counts, active fractions, paired rates.',
                  'First and last target spike in each window, including restoration with external input off.'],
        method='Read all3000 branch chunks once after full-batch reviews. Independently reduce target spikes and compare with reviewer streams/counts. Compare full checkpoint counts with reviewer counts. Use independently audited original-control MBON input/spike arrays. Verify retained selected p/h against independently reconstructed reviewer histories.',
        state_clock='Row T follows ticks<T. State averages use rows[lo,hi), so exact initial/terminal states are separately checked. Branch voltage exists only from5000 onward.',
        limits=['Post-hoc six paired simulations, not six biological observations; no fitting or model promotion.',
                'Prefix before5000 is reused, not resimulated. Original controls lack continuous MBON voltage.',
                'Ethyl-acetate here is a narrow imposed VM7d rate assay, not a measured broad odor ensemble.',
                'Model p is a current-like state, not membrane voltage; h has different units and is not subtracted.',
                'A change under complete positive KC-delivery suppression does not uniquely identify a physiological repair.',
                'Restoration coincides with external input withdrawal; matched controls expose the same schedule.',
                'Cohorts overlap; do not sum them as disjoint populations. No body ran.'])
    write_new(path('-plan.json'),plan); print(json.dumps(record(path('-plan.json'))))


def read_arrays(reader,stem,names):
    header,payload=reader.header(stem); items=dict(header['tree']['items'])
    with np.load(payload,allow_pickle=False) as z:
        result={k:reader.array(items[k]['array'],z) for k in names}
    return result,items


def analyze():
    assert not path('-results.json').exists() and not path('-arrays.npz').exists()
    plan=load(path('-plan.json')); start=time.perf_counter(); reader=None; context=None
    out=dict(schema=1,passed=False,plan=record(path('-plan.json')),limits=plan['limits'],trials=[],paired=[])
    arrays={}; outputs={}
    try:
        for r in plan['inputs']: assert record(ROOT/r['path'])==r,r['path']
        ex=load(EXECUTION); anatomy=load(ANATOMY); targets=np.array(plan['targets'],np.int32)
        selected=np.array(plan['selected_indices'],np.int32); cols=np.searchsorted(selected,targets)
        assert np.array_equal(selected[cols],targets)
        oldrun=ROOT/plan['prior_run_dir']; newrun=ROOT/plan['run_dir']
        manifest=load(oldrun/'artifact-manifest.json')
        manifest={'artifacts':manifest['artifacts']+sum([load(newrun/s['name']/'result.json')['artifacts'] for s in plan['trials']],[])}
        reader=Reader(manifest)
        source_counts={}; durations=np.diff(WINDOWS)*DT
        arrays.update(target_indices=targets,window_edges_ticks=WINDOWS,bin_edges_ticks=np.arange(0,30001,BIN))
        with np.load(OLD_INPUTS,allow_pickle=False) as old,np.load(REVIEW_ARRAYS,allow_pickle=False) as review:
            reader.check('target-identity',np.array_equal(old['graph_indices'],targets) and np.array_equal(review['target_indices'],targets))
            for spec in plan['trials']:
                context=spec['name'];reader.current=context;pfx='trial_'+str(spec['ordinal'])
                cp,_=read_arrays(reader,newrun/spec['name']/'checkpoint-30000',['window_counts_observed','selected_indices','v','s','h'])
                oldcp,_=read_arrays(reader,oldrun/spec['name']/'checkpoint-30000',['window_counts_observed'])
                reader.check('all-counts-independent',np.array_equal(cp['window_counts_observed'],review[pfx+'_window_counts']))
                reader.check('selection',np.array_equal(cp['selected_indices'],selected))
                source_counts[spec['ordinal']]={'control':oldcp['window_counts_observed'],'intervention':cp['window_counts_observed']}
                trace={k:np.empty((25001,10),np.float64) for k in ['v','s','h']};pieces=[]
                lookup=np.full(ex['neurons'],-1,np.int32);lookup[targets]=np.arange(10)
                for chunk in range(100,600):
                    stem=newrun/spec['name']/f'chunk-{chunk:04d}';reader.current=(context,chunk)
                    sp,items=reader.spikes(stem)
                    pieces.append(sp[lookup[sp['index']]>=0].copy())
                    a,_=read_arrays(reader,stem,['selected_v','selected_s','selected_h'])
                    lo=(chunk-100)*50
                    reader.check('chunk-time',items['start_tick']['value']==chunk*50 and items['end_tick']['value']==chunk*50+50)
                    for key in trace:
                        v=a['selected_'+key][:,cols]
                        if lo: reader.check('state-continuity',np.array_equal(trace[key][lo].view(np.uint64),v[0].view(np.uint64)))
                        trace[key][lo:lo+51]=v
                after=np.concatenate(pieces)
                reader.check('review-spike-stream',np.array_equal(after['tick'],review[pfx+'_MBON_spike_ticks']) and np.array_equal(after['index'],review[pfx+'_MBON_spike_indices']))
                original=old[pfx+'_target_spikes'];prefix=original[original['tick']<5000]
                branch=np.concatenate([prefix,after])
                for key,rkey in [('s','p'),('h','h')]:
                    reader.check('review-state-bitwise',np.array_equal(trace[key].view(np.uint64),review[pfx+'_'+rkey].view(np.uint64)))
                    reader.check('restored-state-bitwise',np.array_equal(trace[key][0].view(np.uint64),old[pfx+'_'+rkey][5000].view(np.uint64)))
                for key in trace: reader.check('final-state',np.array_equal(trace[key][-1].view(np.uint64),cp[key][targets].view(np.uint64)))
                trial=dict(spec=spec,arms={})
                for arm,spikes in [('control',original),('intervention',branch)]:
                    m=spike_metrics(spikes,targets);full=source_counts[spec['ordinal']][arm]
                    reader.check('target-window-counts',np.array_equal(m['counts'],full[:,targets]))
                    rate=m['counts']/durations[:,None]
                    summary={k:v.tolist() for k,v in m.items() if k!='bin_counts'};summary['rates_hz']=rate.tolist()
                    summary['cohorts']={}
                    for name,group in anatomy['groups'].items():
                        ind=group['indices']; c=full[:,ind];n=len(ind)
                        summary['cohorts'][name]=dict(cells=n,spikes=c.sum(axis=1).tolist(),active_cells=(c>0).sum(axis=1).tolist(),mean_rate_hz=(c.sum(axis=1)/durations/n).tolist() if n else None)
                    summary['population']=dict(spikes=full.sum(axis=1).tolist(),active_cells=(full>0).sum(axis=1).tolist(),mean_rate_hz=(full.sum(axis=1)/durations/ex['neurons']).tolist())
                    for key,value in m.items(): arrays[pfx+'_'+arm+'_'+key]=value
                    for key in ['p','h']:
                        state=old[pfx+'_'+key] if arm=='control' else np.concatenate([old[pfx+'_'+key][:5000],trace['s' if key=='p' else 'h']])
                        arrays[pfx+'_'+arm+'_'+key+'_bin_mean']=state[:30000].reshape(60,BIN,10).mean(axis=1)
                        summary[key+'_window_mean']=[state[lo:hi].mean(axis=0).tolist() for lo,hi in zip(WINDOWS[:-1],WINDOWS[1:])]
                        summary[key+'_window_max']=[state[lo:hi].max(axis=0).tolist() for lo,hi in zip(WINDOWS[:-1],WINDOWS[1:])]
                    trial['arms'][arm]=summary
                voltage=trace['v'][:-1].reshape(50,BIN,10)
                arrays[pfx+'_intervention_v_bin_min']=voltage.min(axis=1)
                arrays[pfx+'_intervention_v_bin_max']=voltage.max(axis=1)
                trial['voltage_clock_start_tick']=5000
                trial['intervention_v_min_mv']=trace['v'].min(axis=0).tolist();trial['intervention_v_max_mv']=trace['v'].max(axis=0).tolist()
                trial['intervention_minus_control_rates_hz']=(np.array(trial['arms']['intervention']['rates_hz'])-np.array(trial['arms']['control']['rates_hz'])).tolist()
                out['trials'].append(trial);outputs[spec['ordinal']]=trial
        for seed in [11,12,13]:
            base=next(s['ordinal'] for s in plan['trials'] if s['seed']==seed and s['condition']=='constant_baseline')
            odor=next(s['ordinal'] for s in plan['trials'] if s['seed']==seed and s['condition']=='ethyl_acetate')
            contrasts={arm:np.array(outputs[odor]['arms'][arm]['rates_hz'])-np.array(outputs[base]['arms'][arm]['rates_hz']) for arm in ['control','intervention']}
            pair=dict(seed=seed,EA_minus_constant_rates_hz={k:v.tolist() for k,v in contrasts.items()},contrast_change_hz=(contrasts['intervention']-contrasts['control']).tolist(),cohort_contrasts={})
            for name in ['population']+list(anatomy['groups']):
                vals={}
                for arm in ['control','intervention']:
                    sections=[outputs[o]['arms'][arm]['population'] if name=='population' else outputs[o]['arms'][arm]['cohorts'][name] for o in [odor,base]]
                    vals[arm]=None if sections[0]['mean_rate_hz'] is None else (np.array(sections[0]['mean_rate_hz'])-np.array(sections[1]['mean_rate_hz'])).tolist()
                pair['cohort_contrasts'][name]=vals
            out['paired'].append(pair)
        for r in plan['inputs']: assert record(ROOT/r['path'])==r,r['path']
        with path('-arrays.npz').open('xb') as f: np.savez_compressed(f,**arrays)
        out.update(passed=True,array_artifact=record(path('-arrays.npz')),checks=reader.counts,manifest_files_checked=len(reader.checked))
    except BaseException as e:
        out.update(error_type=type(e).__name__,error=str(e),context=context,traceback=traceback.format_exc())
    out['wall_seconds']=time.perf_counter()-start;out['completed_utc']=datetime.now(timezone.utc).isoformat()
    write_new(path('-results.json'),out)
    print(json.dumps(dict(passed=out['passed'],result=record(path('-results.json')),wall_seconds=out['wall_seconds'])))
    if not out['passed']: raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['fixture','prepare','analyze'])
    command=parser.parse_args().command
    if command=='fixture': print(json.dumps(fixture()))
    elif command=='prepare': prepare()
    else: analyze()
