#!/usr/bin/env python3
"""Bounded local scalar calibration; no graph, neural runtime or body imports.

Fit only the nine resolved 20Hz means. Other rates and phase scenarios are
evaluated after the nominal fit, with the fitted parameters held fixed.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import traceback

import numpy as np
import scipy
from scipy.optimize import least_squares, minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/'validation/orn-pn-depression-calibration'
POINTS = ROOT/'validation/orn-pn-depression-fig8f-points.csv'
TAU_BOUNDS = (.001, 100.)
RATES = (15,20,50)
GAP = 1/7


def out(suffix):
    return Path(str(PREFIX)+suffix)


def record(path):
    b=Path(path).read_bytes()
    return dict(path=str(Path(path).relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def steady(rate,f,tau):
    loss=-np.expm1(-1/(rate*tau))
    return loss/((1-f)+f*loss), f*(1-loss)


def prediction(f,tau,rate,n,gap=GAP):
    """Absolute pre-event efficacy plus first-test normalized amplitude."""
    A7,q7=steady(7,f,tau);Ar,qr=steady(rate,f,tau)
    before_last=A7+(1-A7)*q7**27
    after_last=f*before_last
    a0=after_last+(1-after_last)*(-np.expm1(-gap/tau))
    n=np.asarray(n)
    absolute=Ar+(a0-Ar)*qr**n
    return absolute/a0,absolute,float(a0),float(Ar/a0),float(qr)


def event_reference(f,tau,rate,count,gap):
    """Separate read/recover/decrement loop, including all baseline events."""
    schedule=[-gap+(j-27)/7 for j in range(28)]+[j/rate for j in range(count)]
    state=1.;last=schedule[0];amps=[]
    for t in schedule:
        state=1-(1-state)*math.exp(-(t-last)/tau)
        amps.append(state);state*=f;last=t
    test=np.array(amps[28:])
    return test/test[0],test


def preflight():
    count=0;maximum=0.
    for f in [0.,.15,.5,.75,.95,1.]:
        for tau in [.001,.01,.3,3.,100.]:
            for rate in RATES:
                n=np.arange(math.ceil(rate*.5))
                for fraction in [.05,.5,1.]:
                    gap=GAP*fraction
                    y,a,a0,b,q=prediction(f,tau,rate,n,gap)
                    ref,absref=event_reference(f,tau,rate,len(n),gap)
                    error=max(float(np.max(abs(ref-y))),float(np.max(abs(absref-a))))
                    maximum=max(maximum,error)
                    assert error<2e-10 and a0>0 and np.all((a>=-1e-12)&(a<=1+1e-12))
                    assert abs(y[0]-1)<1e-12 and np.isfinite(y).all()
                    if fraction==1.:
                        A7,q7=steady(7,f,tau)
                        assert abs(a0-(A7+(1-A7)*q7**28))<2e-12
                        assert np.all(np.diff(y)<=2e-12) and np.all(np.diff(y,2)>=-2e-12)
                    if f==1.: assert np.allclose(y,1,rtol=0,atol=2e-12)
                    count+=1
    return dict(passed=True,cases=count,max_absolute_difference=maximum,
                scope='Independent event recurrence versus closed form at boundaries/interior, all3rates and3positive phases; nominal positivity/monotonicity/discrete convexity and f=1 null.')


def prepare():
    if out('-plan.json').exists():raise FileExistsError('Preserve first calibration plan')
    checks=preflight()
    paths=[Path(__file__),POINTS,ROOT/'validation/orn-pn-depression-fig8f-results.json',
           ROOT/'validation/orn-pn-depression-fig8f-independent-review.json',
           ROOT/'validation/orn-pn-depression-comparison-results.json',
           ROOT/'validation/synaptic-depression-reference-arrays.npz',
           ROOT/'fruitfly/neural.py',ROOT/'fruitfly/sensors.py']
    starts=[[f,float(math.log(t))] for f in [.05,.25,.5,.75,.95] for t in [.001,.01,.1,1,10,100]]
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),inputs=[record(p) for p in paths],
        versions=dict(numpy=np.__version__,scipy=scipy.__version__),preflight=checks,
        parameterization='f dimensionless in[0,1]; optimization coordinates(f,ln(tau_seconds)); tau in[.001,100]s are engineering search bounds, not physiological priors.',
        model='Between events da/dt=(1-a)/tau; event amplitude=a_before, thena_after=f*a_before. Fully recovered before28baseline events at-4+j/7; firsttest0; no event at.5s. Normalize test efficacy by firsttestevent. No gain/initialstate/phase fit.',
        development=dict(frequency_hz=20,ordinals=list(range(1,10)),objective='Unweighted SSE of nine resolved mean percentages; first shared initial point missing/excluded.'),
        evaluation=dict(rates_hz=[15,50],scope='Previously inspected figure curves; evaluation-only for this fit, not unseen data or independent animals.'),
        optimizer=dict(method='scipy.optimize.least_squares trf',starts=starts,ftol=1e-12,xtol=1e-12,gtol=1e-10,max_nfev=2000,
                       selection='Smallest development SSE among converged starts; retain every outcome. Profile is a diagnostic, never selection on evaluation errors.'),
        profile=dict(tau_seconds=np.geomspace(*TAU_BOUNDS,121).tolist(),f_grid=np.linspace(0,1,201).tolist(),
                     method='At each fixed tau evaluate full201point f grid and minimize within every local grid basin; include f endpoints. SSE/RMSE profile is descriptive, not likelihood/CI.',
                     near_best_rule='Report sampled tau extent within1percentagepoint RMSE of best. This engineering resolution diagnostic is not a confidence interval.'),
        boundary='Also fit the analytic tau-to-infinity curve f**n over f in[1e-8,1] to DEVELOPMENT ONLY; the lower bound approximates interior f>0. Finite28baseline thena0 tendsf**28. Exact f=0 and tau-infinity joint corner has noncommuting limits and is excluded from that limiting parameterization.',
        phase_sensitivity=dict(gap_fractions_of_one_seventh=[.05,.25,.5,.75,1.],
                               rule='Hold fitted f,tau fixed;28baselineevents ending-gap and spaced1/7s, followed bytestat0. Allpositive gaps keep28baselineevents inside[-4,0); no simultaneous events, no fitted phase. Hypothetical schedule sensitivity, not measured timing.'),
        limits=['Normalization/experimental phase/pooling are not fully recovered; this fit is conditional on the stated operation.',
                'Raster uncertainty, biological SEM and common-cell/normalization dependence are distinct; no SEM weights, p-values, covariance confidence intervals or resampling pseudo-animals.',
                'A normalized curve constrains effective shape floor and decay; it does not measure absolute efficacy, release probability or anatomical synaptic gain.',
                'No transfer to maleVM7d, fullgraph, decoder/body, wind/hunger, or runtime promotion. Numerical parameter bounds or better residuals are not physiological validation.'])
    write(out('-plan.json'),plan);print(json.dumps(dict(plan=record(out('-plan.json')),preflight=checks)))


def run():
    outputs=['-results.json','-arrays.npz','-predictions.csv','-profile.csv']
    if any(out(s).exists() for s in outputs):raise FileExistsError('Preserve first calibration execution')
    plan=json.loads(out('-plan.json').read_text());pin=record(out('-plan.json'))
    result=dict(passed=False,plan=pin,attempts=[],limits=plan['limits']);arrays={}
    try:
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        assert plan['versions']==dict(numpy=np.__version__,scipy=scipy.__version__)
        rows=list(csv.DictReader(POINTS.open()))
        train=[r for r in rows if int(r['frequency_hz'])==20 and r['mean_percent_initial']]
        n=np.array([int(r['point_ordinal']) for r in train]);y=np.array([float(r['mean_percent_initial']) for r in train])
        assert n.tolist()==plan['development']['ordinals']

        def residual(x):return 100*prediction(x[0],math.exp(x[1]),20,n)[0]-y
        def sse_f(f,tau):return float(np.sum((100*prediction(f,tau,20,n)[0]-y)**2))
        candidates=[]
        opt=plan['optimizer']
        for start in opt['starts']:
            fit=least_squares(residual,start,bounds=([0,math.log(TAU_BOUNDS[0])],[1,math.log(TAU_BOUNDS[1])]),
                              ftol=opt['ftol'],xtol=opt['xtol'],gtol=opt['gtol'],max_nfev=opt['max_nfev'])
            item=dict(start=start,success=bool(fit.success),status=int(fit.status),message=fit.message,
                      nfev=fit.nfev,f=float(fit.x[0]),tau_s=math.exp(fit.x[1]),SSE=float(np.sum(fit.fun**2)),
                      optimality=float(fit.optimality),active_mask=fit.active_mask.tolist())
            result['attempts'].append(item)
            if fit.success:candidates.append((item,fit))
        assert candidates,'No converged development fit'
        best,fit=min(candidates,key=lambda v:v[0]['SSE']);f,tau=best['f'],best['tau_s']
        profile=[];fg=np.array(plan['profile']['f_grid'])
        for t in plan['profile']['tau_seconds']:
            errors=np.array([sse_f(v,t) for v in fg]); choices=[(float(errors[j]),float(fg[j])) for j in [0,len(fg)-1]]
            brackets=[]
            if errors[0]<=errors[1]:brackets.append((fg[0],fg[1]))
            if errors[-1]<=errors[-2]:brackets.append((fg[-2],fg[-1]))
            for j in range(1,len(fg)-1):
                if (errors[j]<=errors[j-1] and errors[j]<=errors[j+1] and
                        (errors[j]<errors[j-1] or errors[j]<errors[j+1])):
                    brackets.append((fg[j-1],fg[j+1]))
            for bracket in brackets:
                q=minimize_scalar(lambda v:sse_f(v,t),bounds=bracket,method='bounded',options={'xatol':1e-13,'maxiter':1000})
                assert q.success
                choices.append((float(q.fun),float(q.x)))
            # Retain the grid minimum even if it is a boundary of numerical resolution.
            j=int(errors.argmin());choices.append((float(errors[j]),float(fg[j])))
            e,ff=min(choices);profile.append(dict(tau_s=t,f=ff,SSE=e,RMSE_percentage_points=math.sqrt(e/len(y))))
        assert min(p['SSE'] for p in profile)>=best['SSE']-1e-6,'Profile exposes lower missed development minimum'
        boundary=minimize_scalar(lambda v:float(np.sum((100*v**n-y)**2)),bounds=(1e-8,1),method='bounded',options={'xatol':1e-13})
        assert boundary.success
        sv=np.linalg.svd(fit.jac,compute_uv=False)
        near=[p for p in profile if p['RMSE_percentage_points']<=math.sqrt(best['SSE']/len(y))+1.]
        result.update(best=best,effective_20Hz_shape=dict(zip(['first_test_efficacy','normalized_floor','per_event_decay'],prediction(f,tau,20,[0])[2:])),
                      converged_starts=len(candidates),converged_SSE_range=[min(c[0]['SSE'] for c in candidates),max(c[0]['SSE'] for c in candidates)],
                      scaled_coordinate_jacobian_singular_values=sv.tolist(),jacobian_coordinate_units=['f','ln(tau_seconds)'],
                      sampled_tau_extent_within_one_pp_rmse=None if not near else [near[0]['tau_s'],near[-1]['tau_s']],
                      tau_infinite_interior_f_limit=dict(f=float(boundary.x),SSE=float(boundary.fun),RMSE_percentage_points=math.sqrt(boundary.fun/len(y))),
                      bound_proximity=dict(f_lower=f<1e-6,f_upper=1-f<1e-6,tau_lower=tau/TAU_BOUNDS[0]-1<1e-5,tau_upper=1-tau/TAU_BOUNDS[1]<1e-5))
        prediction_rows=[];summary=[];phases=[]
        for rate in RATES:
            rr=[r for r in rows if int(r['frequency_hz'])==rate];ordinal=np.array([int(r['point_ordinal']) for r in rr])
            assert ordinal.tolist()==list(range(math.ceil(rate*.5)))
            pred,absolute,a0,b,q=prediction(f,tau,rate,ordinal)
            nominal_ref,nominal_abs=event_reference(f,tau,rate,len(ordinal),GAP)
            assert np.max(abs(pred-nominal_ref))<2e-10 and np.max(abs(absolute-nominal_abs))<2e-10
            obs=np.array([float(r['mean_percent_initial']) if r['mean_percent_initial'] else np.nan for r in rr]);keep=np.isfinite(obs)
            error=100*pred[keep]-obs[keep]
            summary.append(dict(frequency_hz=rate,role='development' if rate==20 else 'evaluation',means=int(keep.sum()),
                                RMSE_percentage_points=float(np.sqrt(np.mean(error**2))),MAE_percentage_points=float(np.mean(abs(error))),
                                mean_signed_error_percentage_points=float(error.mean()),last_predicted_percent=float(100*pred[-1]),last_observed_percent=float(obs[-1])))
            arrays[f'rate_{rate}_nominal_amplitude']=absolute;arrays[f'rate_{rate}_nominal_percent']=100*pred
            for r,p,a in zip(rr,pred,absolute):
                prediction_rows.append(dict(frequency_hz=rate,point_ordinal=int(r['point_ordinal']),source_time_ms=float(r['time_ms']),
                    observed_percent=None if not r['mean_percent_initial'] else float(r['mean_percent_initial']),fitted_percent=float(100*p),absolute_model_efficacy=float(a)))
            for fraction in plan['phase_sensitivity']['gap_fractions_of_one_seventh']:
                values,amps,a0p,bp,qp=prediction(f,tau,rate,ordinal,GAP*fraction)
                event,ea=event_reference(f,tau,rate,len(ordinal),GAP*fraction)
                assert np.max(abs(values-event))<2e-10 and np.max(abs(amps-ea))<2e-10
                phases.append(dict(frequency_hz=rate,gap_s=GAP*fraction,fraction=fraction,first_test_efficacy=a0p,
                                   RMSE_percentage_points=float(np.sqrt(np.mean((100*values[keep]-obs[keep])**2))),
                                   last_percent=float(100*values[-1])))
                arrays[f'rate_{rate}_gap_fraction_{fraction}_percent']=100*values
        arrays['profile_tau_s']=np.array([p['tau_s'] for p in profile]);arrays['profile_SSE']=np.array([p['SSE'] for p in profile])
        result.update(summary=summary,phase_sensitivity=phases,passed=True)
        for suffix,table in [('-predictions.csv',prediction_rows),('-profile.csv',profile)]:
            with out(suffix).open('x',newline='') as fh:
                writer=csv.DictWriter(fh,fieldnames=list(table[0]),lineterminator='\n');writer.writeheader();writer.writerows(table)
        for r in plan['inputs']:assert record(ROOT/r['path'])==r
        assert record(out('-plan.json'))==pin
    except (Exception,KeyboardInterrupt) as e:
        result.update(passed=False,error=repr(e),traceback=traceback.format_exc())
        raise
    finally:
        np.savez_compressed(out('-arrays.npz'),**arrays)
        result['completed_utc']=datetime.now(timezone.utc).isoformat()
        result['artifacts']=[record(out(s)) for s in outputs[1:] if out(s).exists()]
        write(out('-results.json'),result)
    print(json.dumps({k:result[k] for k in ['passed','best','converged_SSE_range','effective_20Hz_shape','bound_proximity','sampled_tau_extent_within_one_pp_rmse','tau_infinite_interior_f_limit','summary']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:run()
