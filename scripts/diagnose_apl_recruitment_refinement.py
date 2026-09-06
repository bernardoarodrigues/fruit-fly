"""Bounded diagnosis of failed refinement ratios; no fitting or gate changes."""
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from fruitfly.apl_recruitment import pulse
ROOT=Path(__file__).resolve().parents[1];PLAN=ROOT/'validation/apl-recruitment-refinement-plan.json';OUT=ROOT/'validation/apl-recruitment-refinement.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve plan')
    review=json.loads((ROOT/'validation/apl-recruitment-review.json').read_text())
    chosen=[c for c in review['cases'] if not c['numerical_gate_pass']]
    chosen+=[max(review['cases'],key=lambda c:c['ode_max_error_mV']),next(c for c in review['cases'] if c['numerical_gate_pass'])]
    keys=sorted(set((c['fit_id'],c['cell']) for c in chosen))
    pins=['scripts/diagnose_apl_recruitment_refinement.py','fruitfly/apl_recruitment.py','validation/apl-recruitment-results.json','validation/apl-recruitment-review.json']
    PLAN.write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),pins={s:sha(ROOT/s) for s in pins},cases=keys,dt_s=[.00005,.000025,.0000125,.00000625],
        selection='All 19 failed refinement-ratio cases plus maximum-absolute-error and first passing reference cases, deduplicated. No biological fitting, parameter change, gate revision or promotion.',
        methods='Recompute original DOP853 reference at rtol2e-9 atol2e-10 and a tighter reference at rtol2e-12 atol2e-13. Split at the current discontinuity. Keep original 10kHz observation clock and 1ms bins for all four integration steps. Save RMSE/max error and its bin time, reference shift, successive error ratios and whether the original 50-to25us ratio gate changes under the tighter reference.'),indent=2)+'\n')
    print('Frozen',len(keys),'diagnostic cases')


def run():
    if OUT.exists():raise FileExistsError('Preserve result')
    p=json.loads(PLAN.read_text())
    for f,h in p['pins'].items():assert sha(ROOT/f)==h
    r=json.loads((ROOT/'validation/apl-recruitment-results.json').read_text());rows=[]
    times=np.arange(35500)/10000;bint=times.reshape(-1,10).mean(axis=1)
    for fid,cell in p['cases']:
        s=next(s for s in r['scores'] if s['fit_id']==fid and s['cell']==cell);circuit=np.array(s['circuit']);pars=np.array(s['parameters']);rev=s['reversal_relative_mV'];cs,cd,gl,gc=circuit;gf,gs,th,ton,toff,scale=pars
        def rhs(y,current):
            v,d,h,z=y;m=max(v,0)/(scale+max(v,0));g=gf*m*h+gs*z
            return [1000*(current-gl*v-gc*(v-d)-g*(v-rev))/cs,1000*gc*(v-d)/cd,(1-m-h)/th,m*(1-z)/ton-(1-m)*z/toff]
        refs=[]
        for tolerance in [2e-9,2e-12]:
            on=solve_ivp(lambda t,y:rhs(y,2000.),[0,.75],[0,0,1,0],method='DOP853',rtol=tolerance,atol=tolerance/10,dense_output=True)
            off=solve_ivp(lambda t,y:rhs(y,0.),[.75,3.55],on.y[:,-1],method='DOP853',rtol=tolerance,atol=tolerance/10,dense_output=True)
            assert on.success and off.success
            refs.append(np.concatenate([on.sol(times[:7500])[0],off.sol(times[7500:])[0]]).reshape(-1,10).mean(axis=1))
        errors=[]
        for dt in p['dt_s']:
            pred,_,_=pulse(circuit,pars,rev,dt=dt);err=pred-refs[1];idx=int(np.argmax(np.abs(err)))
            errors.append(dict(dt_s=dt,rmse_mV=float(np.sqrt(np.mean(err**2))),max_error_mV=float(abs(err[idx])),max_error_bin_time_s=float(bint[idx])))
        shift=refs[0]-refs[1]
        rows.append(dict(fit_id=fid,cell=cell,reference_shift_rmse_mV=float(np.sqrt(np.mean(shift**2))),reference_shift_max_mV=float(np.max(np.abs(shift))),errors=errors,
            successive_rmse_ratios=[errors[i+1]['rmse_mV']/errors[i]['rmse_mV'] for i in range(3)],original_ratio_gate_with_tight_reference=errors[1]['rmse_mV']<=.4*errors[0]['rmse_mV']+1e-7))
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),cases=rows,scope=p['selection']),indent=2)+'\n')
    print('Completed all',len(rows),'diagnostic cases')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
