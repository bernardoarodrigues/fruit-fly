"""Independent direct three-parameter fits and finite-pulse predictions."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-passive-modes-review.json'


def main():
    if OUT.exists():raise FileExistsError('Preserve completed review')
    path=ROOT/'validation/apl-passive-modes-results.json';r=json.loads(path.read_text())
    src=json.loads((ROOT/'validation/apl-passive-transient-results.json').read_text());a=np.load(ROOT/src['arrays']['path'])
    t=a['onset_time_s'];ot=a['offset_time_s'];plateau_times=np.arange(4000,5000)/10000
    def one(t,tau,offset=False):
        scale=np.mean(1-np.exp(-plateau_times/tau))
        return ((1-np.exp(-.5/tau))*np.exp(-t/tau) if offset else 1-np.exp(-t/tau))/scale
    def formula(t,logs,alpha,offset=False):return alpha*one(t,np.exp(logs[0]),offset)+(1-alpha)*one(t,np.exp(logs[1]),offset)
    comparisons=[];scalar_checks=0;max_error=0.
    for f,s in zip(r['files'],src['files'],strict=True):
        assert f['member']==s['member']
        norm=(a[f"f{f['file_index']}_onset_voltage_mV"]-s['held_baseline_mV'])/s['passive_delta_mV']
        off=(a[f"f{f['file_index']}_offset_voltage_mV"]-s['held_baseline_mV'])/s['passive_delta_mV']
        for v in f['variants']:
            mask=(t>=v['window_s'][0])&(t<v['window_s'][1]);x=t[mask];y=norm[mask]
            candidates=[]
            for tf,ts,alpha in ((.001,.03,.5),(.003,.06,.8),(.008,.1,.7)):
                opt=least_squares(lambda z:formula(x,z[:2],z[2])-y,[np.log(tf),np.log(ts),alpha],
                    bounds=([np.log(.0005),np.log(.0005),0],[np.log(.2),np.log(.2),1]),
                    ftol=1e-11,xtol=1e-11,gtol=1e-11,max_nfev=1000)
                assert opt.success
                candidates.append((float(np.mean(opt.fun**2)),opt.x.tolist()))
            best,z=min(candidates);difference=abs(best-v['models']['two']['fit_mse'])
            assert difference<1e-8,(f['file_index'],v['window_s'],difference)
            max_error=max(max_error,difference)
            comparisons.append(dict(file_index=f['file_index'],window_s=v['window_s'],independent_mse=best,
                producer_mse=v['models']['two']['fit_mse'],independent_parameters=z,absolute_mse_difference=difference))
            for name,m in v['models'].items():
                logs=np.log([m['tau_fast_s'],m['tau_slow_s']]);pred=formula(x,logs,m['alpha'])
                assert abs(np.mean((pred-y)**2)-m['fit_mse'])<1e-10;scalar_checks+=1
                maskoff=(ot>=.005)&(ot<.1);predoff=formula(ot,logs,m['alpha'],True)
                error=float(np.sqrt(np.mean((predoff[maskoff]-off[maskoff])**2)))
                assert abs(error-m['offset_rmse_fraction_of_passive_step'])<1e-10;scalar_checks+=1
    summaries=[]
    for i in range(4):
        m=[f['variants'][i]['models'] for f in r['files']]
        summaries.append(dict(window_s=r['files'][0]['variants'][i]['window_s'],
            offset_improved_files=sum(x['two']['offset_rmse_mV']<x['single']['offset_rmse_mV'] for x in m),
            single_offset_fraction_median=float(np.median([x['single']['offset_rmse_fraction_of_passive_step'] for x in m])),
            two_offset_fraction_median=float(np.median([x['two']['offset_rmse_fraction_of_passive_step'] for x in m])),
            two_tau_bound_count=sum(x['two']['at_tau_bound'] for x in m),
            two_degenerate_count=sum(x['two']['degenerate_mixture'] for x in m),
            two_median_fast_ms=float(np.median([x['two']['tau_fast_s']*1000 for x in m])),
            two_median_slow_ms=float(np.median([x['two']['tau_slow_s']*1000 for x in m])),
            two_median_plateau_fast_weight=float(np.median([x['two']['alpha'] for x in m]))))
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),independent_two_mode_fits=len(comparisons),
        scalar_checks=scalar_checks,max_absolute_mse_difference=max_error,summaries=summaries,comparisons=comparisons,
        scope='Independent direct three-parameter nonlinear least squares from three fixed starts, with explicit sampled plateau factors. Agreement checks fit objective, not unique mode identifiability. All conditional recovery predictions recomputed without source fitting calls.')
    OUT.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('comparisons','summaries')},indent=2))


if __name__=='__main__':main()
