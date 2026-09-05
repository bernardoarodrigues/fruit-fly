#!/usr/bin/env python3
"""Combined six-case saved-data comparison; no network or solver imports."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,json,time,traceback
import numpy as np
import pyarrow.feather as feather
from analyze_navigation_ladder_timing import Reader,record,load,write_new

ROOT=Path(__file__).resolve().parents[1]
PREFIX=ROOT/'validation/kc-gamma-intervention-analysis'
EXPERIMENT=ROOT/'validation/kc-gamma-intervention-plan.json'
REVIEW=ROOT/'validation/kc-gamma-intervention-independent-review.json'
NUMERICS=ROOT/'validation/kc-gamma-intervention-numerics-results.json'
WINDOWS=np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)
DURATION=np.diff(WINDOWS)*.0001

def path(s):return Path(str(PREFIX)+s)
def read_arrays(reader,stem,keys):
    h,p=reader.header(stem);items=dict(h['tree']['items'])
    with np.load(p,allow_pickle=False) as z:return {k:reader.array(items[k]['array'],z) for k in keys}

class Metrics:
    def __init__(self,n,cohorts):
        self.n=n;self.cohorts=cohorts;self.counts=np.zeros((7,n),np.int64);self.intervals=np.zeros_like(self.counts);self.at22=np.zeros_like(self.counts);self.last=np.full(n,-1,np.int64)
        self.bin_counts=np.zeros((60,len(cohorts)),np.int64)
        self.membership=np.zeros((n,len(cohorts)),np.int64)
        for j,ii in enumerate(cohorts.values()):self.membership[ii,j]=1
    def consume(self,spikes):
        ii=spikes['index'];tt=spikes['tick'];ww=np.searchsorted(WINDOWS,tt,side='right')-1
        np.add.at(self.counts,(ww,ii),1)
        if len(ii):
            order=np.argsort(ii,kind='stable');si=ii[order];st=tt[order];previous=np.r_[-1,st[:-1]];first=np.r_[True,si[1:]!=si[:-1]];previous[first]=self.last[si[first]]
            valid=previous>=0;sw=np.searchsorted(WINDOWS,st,side='right')-1
            np.add.at(self.intervals,(sw[valid],si[valid]),1);at=valid&(st-previous==22);np.add.at(self.at22,(sw[at],si[at]),1);np.maximum.at(self.last,ii,tt)
            # Per-source counts followed by an integer membership reduction.
            for b in np.unique(tt//500):
                histogram=np.bincount(ii[tt//500==b],minlength=self.n)
                present=np.flatnonzero(histogram)
                self.bin_counts[b]+=histogram[present]@self.membership[present]
    def summary(self):
        result={}
        for name,ii in self.cohorts.items():
            c=self.counts[:,ii];den=self.intervals[:,ii].sum(axis=1);num=self.at22[:,ii].sum(axis=1)
            result[name]=dict(cells=len(ii),spikes=c.sum(axis=1).tolist(),active_cells=(c>0).sum(axis=1).tolist(),mean_rate_hz=(c.sum(axis=1)/DURATION/len(ii)).tolist() if len(ii) else None,isi_intervals=den.tolist(),isi_at_22=num.tolist(),isi_at_22_fraction=[float(a/b) if b else None for a,b in zip(num,den)])
        return result

def fixture():
    dtype=[('tick','<i8'),('index','<i4')];sp=np.array([(4980,0),(5002,0),(10000,0),(15000,0),(15022,0),(29999,1)],dtype=dtype)
    a=Metrics(3,{'all':np.arange(3)});a.consume(sp[:2]);a.consume(sp[2:])
    assert a.counts[:,0].tolist()==[0,1,1,1,2,0,0] and a.at22[:,0].tolist()==[0,0,1,0,1,0,0]
    assert a.intervals[:,0].tolist()==[0,0,1,1,2,0,0] and a.intervals[:,1:].sum()==0 and a.bin_counts.sum()==6
    assert a.summary()['all']['isi_at_22_fraction'][0] is None
    b=Metrics(3,{'all':np.arange(3)});b.consume(sp);assert np.array_equal(a.at22,b.at22) and np.array_equal(a.counts,b.counts)
    return dict(passed=True,checks=7,scope='Half-open windows, cross-chunk ISI carry, first/silent cell denominators and integer cohort binning.')

def prepare():
    if any(path(s).exists() for s in ['-plan.json','-results.json','-arrays.npz']):raise FileExistsError('Preserve first analysis')
    preflight=fixture();exp=load(EXPERIMENT);rev=load(REVIEW);num=load(NUMERICS);parent=load(ROOT/exp['run_dir']/'results.json')
    assert rev['passed'] and num['passed'] and parent['passed'] and parent['complete']
    assert len(parent['trials'])==6 and [t['spec'] for t in parent['trials']]==exp['trials']
    paths=[Path(__file__),ROOT/'scripts/analyze_navigation_ladder_timing.py',EXPERIMENT,REVIEW,NUMERICS,ROOT/rev['array_artifact']['path'],ROOT/'validation/kc-gamma-contact-mask-arrays.npz',ROOT/'data/processed/malecns_v1/neurons.feather',ROOT/'data/processed/malecns_v1/neuron_ids.npy',ROOT/'validation/navigation-ladder-anatomy.json',ROOT/exp['prior_run_dir']/'artifact-manifest.json',ROOT/exp['prior_run_dir']/'terminal.json',ROOT/exp['run_dir']/'results.json',ROOT/exp['run_dir']/'terminal.json']
    for receipt in [rev,num]:
        assert record(ROOT/receipt['plan']['path'])==receipt['plan'];rp=load(ROOT/receipt['plan']['path']);assert rp['trials']==exp['trials'] and record(EXPERIMENT) in rp['inputs'];paths.append(ROOT/receipt['plan']['path'])
        for r in rp['inputs']:assert record(ROOT/r['path'])==r;paths.append(ROOT/r['path'])
    assert rev['source_start']==rev['source_end'] and record(ROOT/rev['array_artifact']['path'])==rev['array_artifact'] and record(ROOT/num['rows_artifact']['path'])==num['rows_artifact']
    for spec in exp['trials']:
        for run in [exp['prior_run_dir'],exp['run_dir']]:
            paths += [ROOT/run/spec['name']/n for n in ['result.json','terminal.json']]
    neurons=feather.read_table(ROOT/'data/processed/malecns_v1/neurons.feather').to_pandas();assert np.array_equal(neurons.bodyId.to_numpy(),np.load(ROOT/'data/processed/malecns_v1/neuron_ids.npy'))
    cohorts={k:np.array(v['indices'],np.int32) for k,v in load(ROOT/'validation/navigation-ladder-anatomy.json')['groups'].items()}
    with np.load(ROOT/'validation/kc-gamma-contact-mask-arrays.npz',allow_pickle=False) as m:gamma=m['gamma_indices'];kc=m['kc_indices']
    cohorts.update(population=np.arange(len(neurons),dtype=np.int32),all_KC=kc,gamma_KC=gamma,other_KC=np.setdiff1d(kc,gamma).astype(np.int32),APL=np.flatnonzero(neurons['type'].eq('APL')).astype(np.int32))
    for typ in sorted(neurons.iloc[kc]['type'].unique()):cohorts['type:'+typ]=np.flatnonzero(neurons['class'].eq('Kenyon_Cell') & neurons['type'].eq(typ)).astype(np.int32)
    write_new(path('-plan.json'),dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=[record(p) for p in dict.fromkeys(paths)],trials=exp['trials'],cohorts={k:v.tolist() for k,v in cohorts.items()},selected_indices=exp['selected_indices'],fixture=preflight,
        method='Independently reduce full population spikes in all600 original chunks and500 branch chunks per trial. Copy original prefix metrics at5000, then append branch histories. Verify all per-cell counts against full checkpoints and reviewer arrays; compare branch observed-cell spike streams and continuous p/h against reviewer reconstruction. Compute all per-cell ISIs with second-spike window assignment, including intervals crossing5000. Cohorts may overlap. Record branch-only continuous voltage/p/h50ms min/mean/max and matched control/branch full checkpoint states for73 observed cells.',
        metrics=['seven-window rates/active fractions/22tick ISI fractions for whole population, all34 navigation groups, allKC/gamma/otherKC/APL and15 exactKC types','EA-minus-constant contrasts for each seed and both arms, and intervention-minus-control rates','50ms cohort rates and branch observed-cell state envelopes','Per-cell73 observed counts/ISIs and six matched checkpoint v/p/h samples'],
        limitations=['Historical paired simulations, not independent animals or held-out seeds; no fitting or promotion.','Original controls lack continuous recordings for added25 cells; only matched full checkpoints compare their voltage/p/h.','Full-population p/h and voltage between checkpoints are not independently reconstructed.','Restoration and input withdrawal coincide; their contributions cannot be separated.','This is a narrow imposed VM7d rate assay without a body, natural odor ensemble or calibrated receptor law.','p and h have different meanings/units and must not be subtracted.']))
    print(json.dumps(record(path('-plan.json'))))

def analyze():
    if path('-results.json').exists() or path('-arrays.npz').exists():raise FileExistsError('Preserve first analysis')
    plan=load(path('-plan.json'));exp=load(EXPERIMENT);started=time.perf_counter();out=dict(passed=False,plan=record(path('-plan.json')),trials=[],paired=[],limitations=plan['limitations']);arrays={};context=None;reader=None
    try:
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        old=ROOT/exp['prior_run_dir'];new=ROOT/exp['run_dir'];manifest=load(old/'artifact-manifest.json');assert record(old/'artifact-manifest.json')==load(old/'terminal.json')['artifact_manifest']
        manifest={'artifacts':manifest['artifacts']+sum([load(new/s['name']/'result.json')['artifacts'] for s in exp['trials']],[])};reader=Reader(manifest)
        cohorts={k:np.array(v,np.int32) for k,v in plan['cohorts'].items()};selected=np.array(plan['selected_indices'],np.int32);review=load(REVIEW)
        arrays.update(selected_indices=selected,window_edges_ticks=WINDOWS,bin_edges_ticks=np.arange(0,30001,500))
        saved={}
        with np.load(ROOT/review['array_artifact']['path'],allow_pickle=False) as checked:
            reader.check('review-selection',np.array_equal(selected,checked['target_indices']))
            for spec in exp['trials']:
                ordinal=spec['ordinal'];prefix=f'trial_{ordinal}_';trial=dict(spec=spec,arms={});original=Metrics(exp['neurons'],cohorts);branch=None;pieces=[]
                for chunk in range(600):
                    context=(ordinal,'control',chunk);reader.current=context;stem=old/spec['name']/f'chunk-{chunk:04d}';sp,items=reader.spikes(stem)
                    reader.check('original-chunk-clock',items['start_tick']['value']==chunk*50 and items['end_tick']['value']==chunk*50+50)
                    original.consume(sp)
                    if chunk==99:branch=copy.deepcopy(original)
                trace={k:np.empty((25001,len(selected)),float) for k in ['v','s','h']}
                for chunk in range(100,600):
                    context=(ordinal,'intervention',chunk);reader.current=context;stem=new/spec['name']/f'chunk-{chunk:04d}';sp,items=reader.spikes(stem)
                    reader.check('branch-chunk-clock',items['start_tick']['value']==chunk*50 and items['end_tick']['value']==chunk*50+50);branch.consume(sp);pieces.append(sp[np.isin(sp['index'],selected)])
                    a=read_arrays(reader,stem,['selected_v','selected_s','selected_h']);lo=chunk*50-5000
                    for k in trace:
                        v=a['selected_'+k]
                        if lo:reader.check('trace-continuity',np.array_equal(trace[k][lo].view(np.uint64),v[0].view(np.uint64)))
                        trace[k][lo:lo+51]=v
                observed=np.concatenate(pieces);reader.check('reviewed-spikes',np.array_equal(observed['tick'],checked[prefix+'observed_spike_ticks']) and np.array_equal(observed['index'],checked[prefix+'observed_spike_indices']))
                for k,other in [('s','p'),('h','h')]:reader.check('independent-state',np.array_equal(trace[k].view(np.uint64),checked[prefix+other].view(np.uint64)))
                reader.check('reviewed-counts',np.array_equal(branch.counts,checked[prefix+'window_counts']))
                for arm,m,run in [('control',original,old),('intervention',branch,new)]:
                    final=read_arrays(reader,run/spec['name']/'checkpoint-30000',['window_counts_observed']);reader.check('all-population-counts',np.array_equal(m.counts,final['window_counts_observed']))
                    trial['arms'][arm]=dict(cohorts=m.summary(),observed_rates_hz=(m.counts[:,selected]/DURATION[:,None]).tolist())
                    for k in ['counts','intervals','at22','bin_counts']:arrays[prefix+arm+'_'+k]=getattr(m,k)
                    for k in ['v','s','h']:
                        samples=[]
                        for tick in exp['checkpoint_ticks']:
                            cp=read_arrays(reader,run/spec['name']/f'checkpoint-{tick:05d}',[k]);samples.append(cp[k][selected])
                        arrays[prefix+arm+'_'+k+'_checkpoints']=np.array(samples)
                        if arm=='intervention':reader.check('branch-state-checkpoints',np.array_equal(np.array(samples).view(np.uint64),trace[k][np.array(exp['checkpoint_ticks'])-5000].view(np.uint64)))
                for k,v in trace.items():
                    bins=v[:-1].reshape(50,500,len(selected))
                    for operation in ['min','mean','max']:arrays[prefix+'intervention_'+k+'_bin_'+operation]=getattr(bins,operation)(axis=1)
                trial['intervention_minus_control_rates_hz']={name:(np.array(trial['arms']['intervention']['cohorts'][name]['mean_rate_hz'])-np.array(trial['arms']['control']['cohorts'][name]['mean_rate_hz'])).tolist() for name,ii in cohorts.items() if len(ii)}
                out['trials'].append(trial);saved[ordinal]=trial
        for seed in [11,12,13]:
            ordinal={s['condition']:s['ordinal'] for s in exp['trials'] if s['seed']==seed};a=saved[ordinal['ethyl_acetate']];b=saved[ordinal['constant_baseline']];pair=dict(seed=seed,cohorts={})
            for name,ii in cohorts.items():
                if not len(ii):continue
                contrasts={arm:np.array(a['arms'][arm]['cohorts'][name]['mean_rate_hz'])-np.array(b['arms'][arm]['cohorts'][name]['mean_rate_hz']) for arm in ['control','intervention']}
                pair['cohorts'][name]={k:v.tolist() for k,v in contrasts.items()};pair['cohorts'][name]['contrast_change_hz']=(contrasts['intervention']-contrasts['control']).tolist()
            out['paired'].append(pair)
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        with path('-arrays.npz').open('xb') as f:np.savez_compressed(f,**arrays)
        out.update(passed=True,cohort_names=list(cohorts),array_artifact=record(path('-arrays.npz')),checks=reader.counts,manifest_files_checked=len(reader.checked))
    except BaseException as e:out.update(error=str(e),context=context,traceback=traceback.format_exc())
    out.update(completed_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started);write_new(path('-results.json'),out);print(json.dumps({k:out[k] for k in ['passed','wall_seconds']}|{'error':out.get('error')}))
    return 0 if out['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['fixture','prepare','analyze']);args=p.parse_args()
    if args.action=='fixture':print(json.dumps(fixture()))
    elif args.action=='prepare':prepare()
    else:raise SystemExit(analyze())
