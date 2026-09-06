"""Verify every prediction using matrix-exponential state propagation."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from scipy.signal import dlsim
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-active-recovery-review.json'


def main():
    if OUT.exists():raise FileExistsError('Preserve review')
    source=ROOT/'validation/apl-active-recovery-results.json';r=json.loads(source.read_text())
    p=json.loads((ROOT/'validation/apl-active-recovery-plan.json').read_text());a=np.load(ROOT/r['arrays']['path']);t=a['time_s']
    assert len(p['cells'])==11 and len({c['fly'] for c in p['cells']})==11
    train={c['fly'] for c in p['cells'] if c['partition']=='calibration'};evaluation={c['fly'] for c in p['cells'] if c['partition']=='evaluation'}
    assert len(train)==6 and len(evaluation)==5 and not train&evaluation
    max_error=0.;trace_count=0;metric_count=0;fit_checks=[]
    for score in r['scores']:
        variant=score['variant'];idx=next(i for i,c in enumerate(p['cells']) if c['cell']==score['cell']);fit=r['fits'][variant]
        tf,ts=score['passive_tau_s'];rf,rs=score['resistance_modes_MOhm'];ta=fit['outward_tau_s']
        generator=np.array([[-1/tf,0,-rf/(1000*tf)],[0,-1/ts,-rs/(1000*ts)],[0,0,-1/ta]])
        transition=expm(generator*.0001)
        observation=a[f'c{idx}_observed_mean_mV']
        for name,outward in [('passive',0.),('active',fit['initial_outward_pA'][score['group']])]:
            initial=np.r_[score['initial_modes_mV'],outward]
            _,output,_=dlsim((transition,np.zeros((3,1)),np.array([[1.,1.,0.]]),np.zeros((1,1)),.0001),np.zeros(28000),x0=initial)
            predicted=output[:,0].reshape(-1,10).mean(axis=1)
            error=float(np.max(np.abs(predicted-a[f'v{variant}_c{idx}_{name}_mV'])))
            assert error<1e-8,(variant,idx,name,error)
            max_error=max(max_error,error);trace_count+=1
            for window,limits in [('early',[.05,.8]),('full',[.05,2.8]),('late',[.8,2.8])]:
                mask=(t>=limits[0])&(t<limits[1]);rmse=float(np.sqrt(np.mean((predicted[mask]-observation[mask])**2)))
                assert abs(rmse-score['metrics'][window][name+'_rmse_mV'])<1e-9;metric_count+=1
    summaries=[]
    for variant in range(4):
        cal=[s for s in r['scores'] if s['variant']==variant and s['partition']=='calibration']
        objective=float(np.mean([s['metrics']['early']['active_rmse_mV']**2 for s in cal]))
        assert abs(objective-r['fits'][variant]['calibration_mse_mV2'])<1e-12
        fit_checks.append(dict(variant=variant,recomputed_calibration_mse_mV2=objective))
        for partition in ['calibration','evaluation']:
            rows=[s for s in r['scores'] if s['variant']==variant and s['partition']==partition]
            summaries.append(dict(variant=variant,partition=partition,cells=len(rows),
                full_window_mean_cell_passive_rmse_mV=float(np.mean([s['metrics']['full']['passive_rmse_mV'] for s in rows])),
                full_window_mean_cell_active_rmse_mV=float(np.mean([s['metrics']['full']['active_rmse_mV'] for s in rows])),
                full_window_improved_cells=sum(s['metrics']['full']['active_rmse_mV']<s['metrics']['full']['passive_rmse_mV'] for s in rows),
                not_improved_cells=[s['cell'] for s in rows if s['metrics']['full']['active_rmse_mV']>=s['metrics']['full']['passive_rmse_mV']]))
    review=dict(completed_utc=datetime.now(timezone.utc).isoformat(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        result_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),independent_matrix_propagation_traces=trace_count,
        max_trace_absolute_error_mV=max_error,metric_checks=metric_count,calibration_objective_checks=fit_checks,
        summaries=summaries,scope='Independent matrix-exponential discrete state simulation of all 88 passive/active traces, plus all 264 metric checks. Disjoint fly identities verified. Optimization objective recomputed, optimizer not independently repeated; tests are retrospective conditional transfer, not blind validation or depolarization-phase prediction.')
    OUT.write_text(json.dumps(review,indent=2)+'\n');print(json.dumps({k:v for k,v in review.items() if k not in ('summaries','calibration_objective_checks')},indent=2))


if __name__=='__main__':main()
