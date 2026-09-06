"""Independent continuous ODE and score review of the entire frozen batch."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from fruitfly.apl_conductance import pulse
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-full-pulse-review.json'


def main():
    if OUT.exists():raise FileExistsError('Preserve review')
    path=ROOT/'validation/apl-full-pulse-results.json';r=json.loads(path.read_text());p=json.loads((ROOT/'validation/apl-full-pulse-plan.json').read_text())
    archive=ROOT/r['arrays']['path'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==r['arrays']['sha256']
    a=np.load(archive);t=a['time_s'];masks={name:(t>=lo)&(t<hi) for name,(lo,hi) in p['windows_s'].items()}
    rows=[];max_score_error=0.;objectives=[]
    for s in r['scores']:
        f=r['fits'][s['fit_id']];i=s['index'];cs,cd,gl,gc=s['circuit'];gf,gs,th,tz,scale=s['parameters'];rev=s['reversal_relative_mV']
        def rhs(t,y,current):
            v,d,h,z=y;m=max(v,0)/(scale+max(v,0));g=gf*m*(h if f['inactivating'] else 1)+gs*z
            return [1000*(current-gl*v-gc*(v-d)-g*(v-rev))/cs,1000*gc*(v-d)/cd,(1-m-h)/th,(m-z)/tz]
        on=solve_ivp(lambda t,y:rhs(t,y,2000.),[0,.75],[0,0,1,0],method='DOP853',rtol=2e-9,atol=2e-10,dense_output=True)
        off=solve_ivp(lambda t,y:rhs(t,y,0.),[.75,3.55],on.y[:,-1],method='DOP853',rtol=2e-9,atol=2e-10,dense_output=True)
        assert on.success and off.success
        def reference(dt):
            samples=np.arange(round(3.55/dt))*dt;v=np.empty(len(samples));mask=samples<.75
            v[mask]=on.sol(samples[mask])[0];v[~mask]=off.sol(samples[~mask])[0]
            return v.reshape(-1,round(.001/dt)).mean(axis=1)
        pred=a[f'f{f["fit_id"]}_c{i}_candidate_mV'];control=a[f'f{f["fit_id"]}_c{i}_passive_mV'];obs=a[f'c{i}_observed_mean_mV']
        ref=reference(.0001);error=pred-ref
        half,_,_=pulse(np.array(s['circuit']),np.array(s['parameters']),rev,f['inactivating'],dt=.00005)
        halferror=half-reference(.00005)
        rmse=float(np.sqrt(np.mean(error**2)));half_rmse=float(np.sqrt(np.mean(halferror**2)))
        # Review gates fixed before result inspection: absolute voltage accuracy + refinement.
        gate=rmse<=.2 and float(np.max(np.abs(error)))<=1. and half_rmse<=.6*rmse+1e-7
        for name,mask in masks.items():
            for label,wave in [('candidate',pred),('passive',control)]:
                actual=float(np.sqrt(np.mean((wave[mask]-obs[mask])**2)))
                score_error=abs(actual-s['metrics'][name][label+'_rmse_mV']);assert score_error<1e-10;max_score_error=max(max_score_error,score_error)
        independent_min=float(min(on.y[:2].min(),off.y[:2].min()));assert independent_min>=rev-1e-7
        assert np.all(on.y[2:]>=-1e-7) and np.all(off.y[2:]>=-1e-7) and np.all(on.y[2:]<=1+1e-7) and np.all(off.y[2:]<=1+1e-7)
        rows.append(dict(fit_id=f['fit_id'],cell=s['cell'],ode_rmse_mV=rmse,ode_max_error_mV=float(np.max(np.abs(error))),
            half_step_ode_rmse_mV=half_rmse,numerical_gate_pass=gate,independent_minimum_mV=independent_min))
    for f in r['fits']:
        cells=[s for s in r['scores'] if s['fit_id']==f['fit_id'] and s['partition']=='calibration']
        mse=float(np.mean([s['metrics'][name]['candidate_rmse_mV']**2 for s in cells for name in masks]))
        assert abs(mse-f['selected']['mse_mV2'])<1e-8
        objectives.append(dict(fit_id=f['fit_id'],calibration_mse_mV2=mse))
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        review_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),case_count=len(rows),independent_rmse_score_checks=len(rows)*6,
        max_score_error=max_score_error,objective_checks=objectives,cases=rows,all_numerical_gates_pass=all(c['numerical_gate_pass'] for c in rows),
        max_ode_rmse_mV=max(c['ode_rmse_mV'] for c in rows),max_ode_absolute_error_mV=max(c['ode_max_error_mV'] for c in rows),
        max_repeat_memory_mV=max(s['next_pulse_max_difference_mV'] for s in r['scores']),
        scope='Independent continuous ODE integration and metric recomputation, plus half-step convergence for all candidate predictions. Not an independent optimizer, ABF decoder, or validation of the biological mechanism. Numerical gates: RMSE <=0.2mV, max error <=1mV, half-step RMSE <=0.6 times original plus 1e-7.')
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','objective_checks')},indent=2))


if __name__=='__main__':main()
