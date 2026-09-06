"""Independent centered-regression profile fits for every mean transient."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-passive-transient-review.json'


def main():
    if OUT.exists():raise FileExistsError('Preserve complete review')
    path=ROOT/'validation/apl-passive-transient-results.json';r=json.loads(path.read_text())
    p=json.loads((ROOT/'validation/apl-passive-transient-plan.json').read_text())
    arrays_path=ROOT/r['arrays']['path'];assert hashlib.sha256(arrays_path.read_bytes()).hexdigest()==r['arrays']['sha256']
    a=np.load(arrays_path);t=a['onset_time_s'];off_t=a['offset_time_s']
    comparisons=[];checks=0;maximum=0.
    for f in r['files']:
        y=a[f"f{f['file_index']}_onset_voltage_mV"];offset=a[f"f{f['file_index']}_offset_voltage_mV"]
        for item in f['mean_fits']:
            window=item['window_s'];mask=(t>=window[0])&(t<window[1]);x=t[mask];v=y[mask]
            def profile(logtau):
                z=np.exp(-x/np.exp(logtau));zc=z-z.mean();vc=v-v.mean()
                b=np.dot(zc,vc)/np.dot(zc,zc);c=v.mean()-b*z.mean()
                return float(np.mean((c+b*z-v)**2)),float(c),float(b)
            opt=minimize_scalar(lambda z:profile(z)[0],bounds=np.log(p['tau_bounds_s']),method='bounded',options={'xatol':1e-12})
            assert opt.success
            candidates=[(opt.fun,opt.x)]+[(profile(np.log(bound))[0],np.log(bound)) for bound in p['tau_bounds_s']]
            score,logtau=min(candidates);tau=float(np.exp(logtau));fit=item['fit']
            score_difference=abs(score-fit['rmse_mV']**2)
            assert score_difference<1e-8,(f['file_index'],window,score_difference)
            maximum=max(maximum,score_difference);checks+=1
            z=fit['asymptote_mV']+fit['exponential_coefficient_mV']*np.exp(-x/fit['tau_s'])
            assert abs(np.sqrt(np.mean((z-v)**2))-fit['rmse_mV'])<1e-10;checks+=1
            maskoff=(off_t>=p['prediction_window_s'][0])&(off_t<p['prediction_window_s'][1])
            pred=f['held_baseline_mV']+f['passive_delta_mV']*np.exp(-off_t/fit['tau_s'])
            rmse=float(np.sqrt(np.mean((pred[maskoff]-offset[maskoff])**2)))
            assert abs(rmse-item['evaluation']['offset_rmse_mV'])<1e-10;checks+=1
            comparisons.append(dict(file_index=f['file_index'],window_s=window,independent_tau_s=tau,
                saved_tau_s=fit['tau_s'],absolute_mse_difference=score_difference))
    stats=[]
    for i,w in enumerate(p['mean_fit_windows_s']):
        cases=[f['mean_fits'][i] for f in r['files']]
        stats.append(dict(window_s=w,tau_ms_min_median_max=np.quantile([x['fit']['tau_s']*1000 for x in cases],[0,.5,1]).tolist(),
            onset_rmse_mV_min_median_max=np.quantile([x['fit']['rmse_mV'] for x in cases],[0,.5,1]).tolist(),
            offset_rmse_mV_min_median_max=np.quantile([x['evaluation']['offset_rmse_mV'] for x in cases],[0,.5,1]).tolist(),
            offset_error_fraction_min_median_max=np.quantile([x['evaluation']['offset_rmse_fraction_of_passive_step'] for x in cases],[0,.5,1]).tolist()))
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),independent_optimizations=len(comparisons),scalar_checks=checks,
        max_absolute_mse_difference=maximum,window_summaries=stats,
        sweep_status_counts=dict(Counter(s['fit']['status'] for f in r['files'] for s in f['sweep_fits'])),
        sweep_tau_bound_count=sum(s['fit']['at_tau_bound'] for f in r['files'] for s in f['sweep_fits']),
        mean_tau_bound_count=sum(x['fit']['at_tau_bound'] for f in r['files'] for x in f['mean_fits']),
        max_mean_window_tau_ratio=max(max(x['fit']['tau_s'] for x in f['mean_fits'])/min(x['fit']['tau_s'] for x in f['mean_fits']) for f in r['files']),
        comparisons=comparisons,
        scope='Independent centered-regression coefficient solve and full-interval scalar optimization for all 328 mean fits. The 2132 single-sweep fits retain their original diagnostics; not all independently reoptimized. Conditional offset checks do not establish cross-cell prediction or physical capacitance.')
    OUT.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('comparisons','window_summaries')},indent=2))


if __name__=='__main__':main()
