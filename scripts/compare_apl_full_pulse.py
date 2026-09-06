"""Frozen complete pulse/recovery comparison with autonomously recruited state."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
from scipy.optimize import least_squares
from fruitfly.apl_conductance import passive_circuit, pulse, step
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-full-pulse-plan.json'
OUT=ROOT/'validation/apl-full-pulse-results.json'
ARRAYS=ROOT/'validation/apl-full-pulse-arrays.npz'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve frozen plan')
    old=json.loads((ROOT/'validation/apl-active-recovery-plan.json').read_text())
    pins=['scripts/compare_apl_full_pulse.py','fruitfly/apl_conductance.py','tests/test_apl_conductance.py',
          'validation/apl-active-recovery-plan.json','validation/apl-passive-modes-results.json','validation/apl-passive-measurements.json']
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),pins={x:sha(ROOT/x) for x in pins},cells=old['cells'],
           variants=[0,1,2,3],junction_correction_scenarios_mV=[0.,15.7],candidate_inactivation=[False,True],
           potassium_reversal_mV=1000*8.31446261815324*298.15/96485.33212*np.log(3/141),
           reversal_assumptions='Ideal monovalent potassium Nernst calculation at assumed 25 C using nominal external 3 and internal 141 mM potassium. Temperature and activities are not measured here. Two alternatives apply zero or 15.7 mV subtraction to raw baseline; neither correction convention is selected as correct for the ABF traces. These are sensitivity scenarios, not measured reversal potentials.',
           parameter_names=['g_fast_nS','g_slow_control_nS','g_slow_RNAi_nS','tau_h_s','tau_z_s','activation_scale_mV'],
           lower=[.1,.01,.01,.01,.05,5.],upper=[100.,20.,20.,1.,3.,80.],
           starts=[[20.,1.,.5,.2,.6,20.],[5.,3.,1.5,.05,1.5,50.]],max_nfev=80,
           dt_s=.0001,bin_s=.001,duration_s=.75,recovery_s=2.8,amplitude_pA=2000.,
           windows_s={'pulse':[.005,.75],'early_recovery':[.755,1.55],'late_recovery':[1.55,3.55]},
           methods='Six calibration and five evaluation flies retain the previous hash partition and all four fixed passive variants. Convert each two-pole impedance to a positive soma-leak/distal-capacitance realization. Activation m=max(V,0)/(scale+max(V,0)); V is relative to held baseline. Fast conductance is gf*m with optional h, where dh/dt=(1-m-h)/tau_h. Slow conductance is gs*z with dz/dt=(m-z)/tau_z. Both use the same declared potassium reversal. Start V_s=V_d=0,h=1,z=0 before the 750ms 2nA pulse; never initialize from post-pulse measurements. Fit group-shared gs, common gf/tau_h/tau_z/scale in log coordinates with two fixed starts and bounds. Noninactivating model removes tau_h from optimization. Objective equally weights each calibration cell and each of three declared time windows in absolute mV; observations and predictions are nonoverlapping 1ms averages. Preserve all 65 repeats and their order. Predict the same repeated pulse from equilibrium, then verify the approximation by evolving every fitted case through the remaining 60s onset interval and a second pulse. Recorded baseline is subtracted per sweep; its cell mean conditions the reversal conversion. This is retrospective, conditional transfer, not blind validation or a prediction of absolute resting voltage. Report optimizer termination, bound proximity, window errors, all voltage/gate bounds and repeat-memory differences; do not choose a winner from a nicer plot.',
           history_check='First simulate 3.55s at 0.1ms. Then use stable 1ms zero-input steps for the remaining 56.45s. Check all state residuals and next-pulse difference against an equilibrium start. Finite gaps are not assumed to erase state without this check.',
           scope='Local descriptive electrical candidates only. Not channel identification, measured calcium, natural KC input, GABA release, male parameter validation, recurrent promotion or navigation/motor tuning.')
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen 16 fits / 176 candidate cell predictions',sha(PLAN))


def run():
    if OUT.exists() or ARRAYS.exists():raise FileExistsError('Preserve results')
    p=json.loads(PLAN.read_text())
    for path,d in p['pins'].items():assert sha(ROOT/path)==d
    modes=json.loads((ROOT/'validation/apl-passive-modes-results.json').read_text())
    passive=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
    t=(np.arange(3550)*10+4.5)/10000;arrays={'time_s':t};prepared=[]
    masks={name:(t>=lo)&(t<hi) for name,(lo,hi) in p['windows_s'].items()}
    for i,c in enumerate(p['cells']):
        path=ROOT/c['path'];assert sha(path)==c['sha256'];a=pyabf.ABF(str(path));on=c['offset_sample']-7500;b0,b1=c['baseline_sample_range']
        obs=[];baselines=[]
        for n in a.sweepList:
            a.setSweep(n,channel=0);v=a.sweepY.astype(float);baseline=v[b0:b1].mean();baselines.append(baseline)
            obs.append((v[on:on+35500]-baseline).reshape(-1,10).mean(axis=1))
        source=passive['files'][c['passive_file_index']];rin=np.mean([s['commanded']['resistance_MOhm'] for s in source['sweeps']])
        arrays[f'c{i}_observed_sweeps_mV']=np.array(obs);arrays[f'c{i}_observed_mean_mV']=np.mean(obs,axis=0)
        prepared.append(dict(**c,index=i,observed=np.mean(obs,axis=0),baseline=float(np.mean(baselines)),rin=rin,sweeps=len(obs)))
    fit_indices=[i for i,c in enumerate(prepared) if c['partition']=='calibration']
    fits=[];scores=[]
    for variant in p['variants']:
        circuits=[]
        for c in prepared:
            m=modes['files'][c['passive_file_index']]['variants'][variant]['models']['two'];tau=np.array([m['tau_fast_s'],m['tau_slow_s']]);alpha=m['alpha']
            factor=np.array([np.mean(1-np.exp(-np.arange(4000,5000)/10000/z)) for z in tau])
            circuits.append(passive_circuit(c['rin']*np.array([alpha,1-alpha])/factor,tau))
        for correction in p['junction_correction_scenarios_mV']:
            reversals=[p['potassium_reversal_mV']-(c['baseline']-correction) for c in prepared]
            for inactivating in p['candidate_inactivation']:
                fit_id=len(fits);free=np.array([0,1,2,3,4,5] if inactivating else [0,1,2,4,5]);fixed=np.array(p['starts'][0])
                def unpack(q):
                    x=fixed.copy();x[free]=np.exp(q);return x
                def parameters(x,i):return np.array([x[0],x[1] if prepared[i]['group']=='control' else x[2],x[3],x[4],x[5]])
                def residual(q):
                    x=unpack(q);parts=[]
                    for i in fit_indices:
                        pred,_,_=pulse(circuits[i],parameters(x,i),reversals[i],inactivating)
                        for mask in masks.values():parts.append((pred[mask]-prepared[i]['observed'][mask])/np.sqrt(mask.sum()*len(masks)*len(fit_indices)))
                    return np.concatenate(parts)
                attempts=[]
                for start in p['starts']:
                    fit=least_squares(residual,np.log(np.array(start)[free]),bounds=(np.log(np.array(p['lower'])[free]),np.log(np.array(p['upper'])[free])),max_nfev=p['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7)
                    attempts.append(dict(parameters=unpack(fit.x).tolist(),mse_mV2=float(2*fit.cost),success=bool(fit.success),status=int(fit.status),message=fit.message,nfev=fit.nfev,optimality=float(fit.optimality)))
                best=min(attempts,key=lambda a:a['mse_mV2']);x=np.array(best['parameters'])
                bound_fraction=(np.log(x)-np.log(p['lower']))/(np.log(p['upper'])-np.log(p['lower']))
                near=[p['parameter_names'][i] for i in free if min(bound_fraction[i],1-bound_fraction[i])<.001]
                fits.append(dict(fit_id=fit_id,variant=variant,correction_mV=correction,inactivating=inactivating,attempts=attempts,selected=best,near_bounds=near))
                for i,c in enumerate(prepared):
                    pars=parameters(x,i);pred,state,minimum=pulse(circuits[i],pars,reversals[i],inactivating)
                    control,_,_=pulse(circuits[i],np.array([0.,0.,.2,.6,20.]),reversals[i],False)
                    arrays[f'f{fit_id}_c{i}_candidate_mV']=pred;arrays[f'f{fit_id}_c{i}_passive_mV']=control
                    # Actual source inter-pulse interval is 60s; explicitly propagate it.
                    for _ in range(56450):state=step(state,0.,.001,circuits[i],pars,reversals[i],inactivating)
                    reset_error=float(np.max(np.abs(state-np.array([0,0,1,0]))))
                    second=[]
                    for k in range(35500):
                        second.append(state[0]);state=step(state,2000. if k<7500 else 0.,.0001,circuits[i],pars,reversals[i],inactivating)
                    next_diff=float(np.max(np.abs(np.array(second).reshape(-1,10).mean(axis=1)-pred)))
                    metrics={name:{'candidate_rmse_mV':float(np.sqrt(np.mean((pred[mask]-c['observed'][mask])**2))),
                                       'passive_rmse_mV':float(np.sqrt(np.mean((control[mask]-c['observed'][mask])**2)))} for name,mask in masks.items()}
                    scores.append(dict(fit_id=fit_id,cell=c['cell'],index=i,fly=c['fly'],group=c['group'],partition=c['partition'],sweeps=c['sweeps'],
                        baseline_raw_mV=c['baseline'],circuit=circuits[i].tolist(),parameters=pars.tolist(),reversal_relative_mV=reversals[i],
                        minimum_compartment_mV=minimum,reversal_bound_pass=bool(minimum>=reversals[i]-1e-9),repeat_state_max_difference=reset_error,
                        next_pulse_max_difference_mV=next_diff,metrics=metrics))
    np.savez_compressed(ARRAYS,**arrays)
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),fits=fits,scores=scores,
        arrays=dict(path=str(ARRAYS.relative_to(ROOT)),sha256=sha(ARRAYS)),scope=p['scope']),indent=2,allow_nan=False)+'\n')
    print('Complete: 16 fits, 176 candidate predictions, passive controls and repeat-memory checks. No partial interpretation.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
