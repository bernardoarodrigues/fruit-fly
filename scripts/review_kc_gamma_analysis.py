#!/usr/bin/env python3
"""Independent all-population ISI/count reduction by whole-trial sorting."""
from pathlib import Path
from datetime import datetime,timezone
import json,time,traceback
import numpy as np
from analyze_navigation_ladder_timing import Reader,load,record,write_new
ROOT=Path(__file__).resolve().parents[1]
PREFIX=ROOT/'validation/kc-gamma-intervention-analysis-review'
def main():
    planpath=Path(str(PREFIX)+'-plan.json');outpath=Path(str(PREFIX)+'.json')
    if planpath.exists() or outpath.exists():raise FileExistsError('Preserve first analysis review')
    ap=ROOT/'validation/kc-gamma-intervention-analysis-plan.json';ar=ROOT/'validation/kc-gamma-intervention-analysis-results.json';p=load(ap);r=load(ar);assert r['passed'] and r['plan']==record(ap)
    a=ROOT/r['array_artifact']['path'];assert record(a)==r['array_artifact'];ep=ROOT/'validation/kc-gamma-intervention-plan.json';e=load(ep);old=ROOT/e['prior_run_dir'];new=ROOT/e['run_dir']
    paths=[Path(__file__),ROOT/'scripts/analyze_navigation_ladder_timing.py',ap,ar,a,ep,old/'artifact-manifest.json',old/'terminal.json']
    paths += [new/s['name']/name for s in e['trials'] for name in ['result.json','terminal.json']]
    pins=[record(x) for x in paths]
    write_new(planpath,dict(inputs=pins,trials=e['trials'],method='Read all original spike chunks and reuse only the first100 chunks as branch prefix. Concatenate each full trial then lexsort by cell and time; direct bincount for all166700 cell/window counts and same-cell ISIs, with no streaming state or analyzer import. Independently sum integer50ms cell bins for every cohort and check rates, activity, ISI denominators, observed-cell rates and paired contrasts.',created_utc=datetime.now(timezone.utc).isoformat()))
    out=dict(passed=False,plan=record(planpath),checks=0,trials=[],error=None);start=time.monotonic();reader=None;context=None
    def ck(value,label):
        out['checks']+=1
        if not value:raise AssertionError(str((label,context)))
    try:
        manifest=load(old/'artifact-manifest.json');ck(record(old/'artifact-manifest.json')==load(old/'terminal.json')['artifact_manifest'],'old manifest')
        manifest={'artifacts':manifest['artifacts']+sum([load(new/s['name']/'result.json')['artifacts'] for s in e['trials']],[])};reader=Reader(manifest)
        windows=np.array([0,500,5000,10000,15000,20000,25000,30000]);duration=np.diff(windows)/10000.;n=e['neurons'];cohorts=p['cohorts'];summaries={}
        with np.load(a,allow_pickle=False) as z:
            for spec,trial in zip(e['trials'],r['trials']):
                ck(spec==trial['spec'],'spec');prefix=[];control=[]
                for chunk in range(600):
                    reader.current=(spec['ordinal'],'control',chunk);sp,_=reader.spikes(old/spec['name']/f'chunk-{chunk:04d}');control.append(sp)
                    if chunk<100:prefix.append(sp)
                branch=prefix.copy()
                for chunk in range(100,600):
                    reader.current=(spec['ordinal'],'intervention',chunk);sp,_=reader.spikes(new/spec['name']/f'chunk-{chunk:04d}');branch.append(sp)
                for arm,pieces in [('control',control),('intervention',branch)]:
                    context=(spec['ordinal'],arm);sp=np.concatenate(pieces);ii=sp['index'];tt=sp['tick'];order=np.lexsort((tt,ii));si=ii[order];st=tt[order];same=si[1:]==si[:-1];endcell=si[1:][same];endtime=st[1:][same];delta=(st[1:]-st[:-1])[same]
                    ck(np.all(delta>0),'unique increasing per-cell times');ww=np.searchsorted(windows,tt,side='right')-1;dw=np.searchsorted(windows,endtime,side='right')-1
                    counts=np.bincount(ww*n+ii,minlength=7*n).reshape(7,n);intervals=np.bincount(dw*n+endcell,minlength=7*n).reshape(7,n);at22=np.bincount(dw[delta==22]*n+endcell[delta==22],minlength=7*n).reshape(7,n)
                    for key,value in [('counts',counts),('intervals',intervals),('at22',at22)]:ck(np.array_equal(value,z[f'trial_{spec["ordinal"]}_{arm}_{key}']),'all-cell '+key)
                    bins=np.bincount(tt//500*n+ii,minlength=60*n).reshape(60,n);groupbins=[];summaries[spec['ordinal'],arm]={}
                    for name,indices in cohorts.items():
                        c=counts[:,indices];den=intervals[:,indices].sum(axis=1);num=at22[:,indices].sum(axis=1);summary=trial['arms'][arm]['cohorts'][name];groupbins.append(bins[:,indices].sum(axis=1))
                        ck(summary['cells']==len(indices),'cohort size');ck(np.array_equal(c.sum(axis=1),summary['spikes']),'cohort counts');ck(np.array_equal((c>0).sum(axis=1),summary['active_cells']),'cohort active')
                        ck(np.array_equal(den,summary['isi_intervals']) and np.array_equal(num,summary['isi_at_22']),'cohort ISIs')
                        fraction=[float(a/b) if b else None for a,b in zip(num,den)];ck(fraction==summary['isi_at_22_fraction'],'fractions')
                        rates=c.sum(axis=1)/duration/len(indices) if indices else None;ck(summary['mean_rate_hz'] is None if rates is None else np.allclose(rates,summary['mean_rate_hz'],atol=1e-12,rtol=0),'cohort rate');summaries[spec['ordinal'],arm][name]=rates
                    ck(np.array_equal(np.array(groupbins).T,z[f'trial_{spec["ordinal"]}_{arm}_bin_counts']),'all cohort bins')
                    ck(np.allclose(counts[:,p['selected_indices']]/duration[:,None],trial['arms'][arm]['observed_rates_hz'],atol=1e-12,rtol=0),'observed rates')
                    out['trials'].append(dict(spec=spec,arm=arm,spikes=len(sp),passed=True))
                for name,difference in trial['intervention_minus_control_rates_hz'].items():ck(np.allclose(summaries[spec['ordinal'],'intervention'][name]-summaries[spec['ordinal'],'control'][name],difference,atol=1e-12,rtol=0),'intervention difference')
            for paired in r['paired']:
                seed=paired['seed'];lookup={s['condition']:s['ordinal'] for s in e['trials'] if s['seed']==seed}
                for name,values in paired['cohorts'].items():
                    contrast={arm:summaries[lookup['ethyl_acetate'],arm][name]-summaries[lookup['constant_baseline'],arm][name] for arm in ['control','intervention']}
                    for arm in contrast:ck(np.allclose(contrast[arm],values[arm],atol=1e-12,rtol=0),'EA contrast')
                    ck(np.allclose(contrast['intervention']-contrast['control'],values['contrast_change_hz'],atol=1e-12,rtol=0),'contrast change')
        ck([record(ROOT/x['path']) for x in pins]==pins,'source stability');out['passed']=True
    except BaseException:out['error']=traceback.format_exc();out['context']=context
    out.update(completed_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.monotonic()-start,archive_checks=reader.counts if reader else None,interpretation='Independent reduction by root agent, not a separate reviewer. No biological acceptance or network simulation.');write_new(outpath,out);print(json.dumps({k:out[k] for k in ['passed','checks','wall_seconds','error']}))
    return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
