#!/usr/bin/env python3
"""Complete fixed dye-to-calcium shape comparison; no electrical interpretation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np
from scipy.optimize import minimize_scalar
from apl_reporter_filter import linear_filter,profile_gain
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-reporter-filter-plan.json'
OUT=ROOT/'validation/apl-reporter-filter-results.json'
ARRAYS=ROOT/'validation/apl-reporter-filter-arrays.npz'


def pin(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    if OUT.exists() or ARRAYS.exists():raise FileExistsError('Preserve completed comparison')
    plan=json.loads(PLAN.read_text())
    for s in plan['source_pins']:assert pin(ROOT/s['path'])['sha256']==s['sha256']
    traces=json.loads((ROOT/plan['data']).read_text())['traces']
    pairs={}
    for row in traces:pairs.setdefault((row['panel'],row['color_rank']),{})[row['signal']]=row
    assert len(pairs)==40
    for pair in pairs.values():assert pair['calcium']['color_rgb']==pair['dye']['color_rgb']
    arrays={};arms=[]
    query=np.round(np.arange(0,12.001,.1),10)
    for ai,(clock,proxy) in enumerate((c,p) for c in plan['clocks'] for p in plan['input_proxies']):
        prepared=[];unscorable=[]
        for (panel,rank),pair in sorted(pairs.items()):
            ca=pair['calcium'];dye=pair['dye']
            ct=np.array(ca['time_s_common_calcium_bar']);dt=np.array(dye['time_s_'+clock])
            positive=dt>=0;dt=dt[positive]
            raw=np.array(dye['baseline_adjusted_dff'])[positive]
            factor=float(raw[dt<=12].max())
            if factor<=0:
                assert [panel,rank] not in plan['calibration_pairs']+plan['evaluation_pairs']
                unscorable.append(dict(panel=panel,color_rank=rank,role='secondary',reason='No positive dye peak for declared normalization',input_peak_dff=factor))
                continue
            driver=raw/factor
            lower=np.array(dye['stroke_dff_lower'])[positive]/factor
            upper=np.array(dye['stroke_dff_upper'])[positive]/factor
            if proxy=='nonnegative':driver,lower,upper=[np.maximum(v,0) for v in [driver,lower,upper]]
            response=np.interp(query,ct,ca['baseline_adjusted_dff']);peak=float(response.max());assert peak>0
            response/=peak
            low=np.interp(query,ct,ca['stroke_dff_lower'])/peak;high=np.interp(query,ct,ca['stroke_dff_upper'])/peak
            role='calibration' if [panel,rank] in plan['calibration_pairs'] else ('evaluation' if [panel,rank] in plan['evaluation_pairs'] else 'secondary')
            prepared.append(dict(panel=panel,rank=rank,role=role,t=dt,u=driver,ulo=lower,uhi=upper,y=response,ylo=low,yhi=high,input_peak_dff=factor,calcium_peak_dff=peak))
        training=[x for x in prepared if x['role']=='calibration'];assert len(training)==2
        target=np.stack([x['y'] for x in training])
        def objective(tau):
            prediction=np.stack([linear_filter(x['t'],x['u'],query,tau) for x in training])
            return profile_gain(prediction,target)
        grid=np.r_[0.,np.geomspace(*plan['tau_bounds_s'],plan['tau_grid_points'])]
        profile=[dict(tau_s=float(t),gain=objective(t)[0],mse=objective(t)[1]) for t in grid]
        candidates=[(p['mse'],p['tau_s'],p['gain']) for p in profile]
        for j in range(1,len(grid)-1):
            if profile[j]['mse']<=profile[j-1]['mse'] and profile[j]['mse']<=profile[j+1]['mse']:
                lo=max(grid[j-1],plan['tau_bounds_s'][0]);hi=grid[j+1]
                opt=minimize_scalar(lambda log_tau:objective(np.exp(log_tau))[1],bounds=(np.log(lo),np.log(hi)),method='bounded',options={'xatol':1e-9})
                assert opt.success
                tau=float(np.exp(opt.x));gain,error=objective(tau);candidates.append((error,tau,gain))
        error,tau,gain=min(candidates)
        g0,e0=objective(0.)
        models=[dict(name='instantaneous',tau_s=0.,gain=g0,calibration_mse=e0),dict(name='fitted_lowpass',tau_s=tau,gain=gain,calibration_mse=error)]
        cases=[]
        for model in models:
            for pi,x in enumerate(prepared):
                pred=model['gain']*linear_filter(x['t'],x['u'],query,model['tau_s'])
                plow=model['gain']*linear_filter(x['t'],x['ulo'],query,model['tau_s'])
                phigh=model['gain']*linear_filter(x['t'],x['uhi'],query,model['tau_s'])
                assert np.isfinite(pred).all()
                assert (plow<=pred+1e-12).all() and (pred<=phigh+1e-12).all()
                interval_gap=np.maximum(np.maximum(plow-x['yhi'],x['ylo']-phigh),0)
                key=f"a{ai}_{model['name']}_{x['panel']}_{x['rank']}"
                arrays[key]=np.stack([x['y'],x['ylo'],x['yhi'],pred,plow,phigh,np.interp(query,x['t'],x['u'])])
                residual=pred-x['y'];mse=float(np.mean(residual**2))
                cases.append(dict(panel=x['panel'],color_rank=x['rank'],role=x['role'],model=model['name'],array_key=key,
                    normalized_rmse=float(np.sqrt(mse)),normalized_mae=float(np.abs(residual).mean()),
                    target_peak_s=float(query[np.argmax(x['y'])]),prediction_peak_s=float(query[np.argmax(pred)]),
                    graphical_interval_overlap_fraction=float(np.mean(interval_gap<=1e-12)),maximum_graphical_interval_gap=float(interval_gap.max()),
                    input_peak_dff=x['input_peak_dff'],calcium_peak_dff=x['calcium_peak_dff']))
        summaries=[]
        for model in models:
            for role in ['calibration','evaluation','secondary']:
                rows=[c for c in cases if c['model']==model['name'] and c['role']==role]
                summaries.append(dict(model=model['name'],role=role,pairs=len(rows),pooled_normalized_rmse=float(np.sqrt(np.mean([c['normalized_rmse']**2 for c in rows]))),
                                      mean_graphical_overlap=float(np.mean([c['graphical_interval_overlap_fraction'] for c in rows]))))
        arms.append(dict(clock=clock,input_proxy=proxy,models=models,profile=profile,summaries=summaries,cases=cases,unscorable_pairs=unscorable))
    arrays['time_s']=query
    np.savez_compressed(ARRAYS,**arrays)
    result=dict(status='complete_declared_reporter_filter_comparison',completed_utc=datetime.now(timezone.utc).isoformat(),plan=pin(PLAN),arrays=pin(ARRAYS),
                arms=arms,declared_prediction_slots=320,scored_predictions=sum(len(a['cases']) for a in arms),unscorable_prediction_slots=2*sum(len(a['unscorable_pairs']) for a in arms),physiological_parameter_selected=False,neural_run=False,runtime_changed=False)
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=result['status'],arrays=result['arrays'],arms=[{k:v for k,v in a.items() if k in ['clock','input_proxy','models','summaries']} for a in arms]),indent=2))


if __name__=='__main__':main()
