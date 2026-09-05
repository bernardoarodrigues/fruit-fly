#!/usr/bin/env python3
"""Development-only shape fit and bounded inversion; no neural/runtime imports."""
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
from scipy.optimize import brentq, least_squares, minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / 'validation/orn-pn-depression-shape-boundary'
POINTS = ROOT / 'validation/orn-pn-depression-fig8f-points.csv'
TAU_RANGE = (1e-6, 1e12)


def output(suffix):
    return Path(str(PREFIX) + suffix)


def record(path):
    path = Path(path); b = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def write(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def shape(b, q, n):
    return b + (1-b)*np.power(q, np.asarray(n))


def best_b(q, n, observed_fraction):
    power = np.power(q, n); basis = 1-power
    if q == 1: return 0.  # Constant-one null, all b are equivalent.
    return float(np.clip(np.dot(basis, observed_fraction-power)/np.dot(basis, basis), 0., 1.))


def steady(rate, f, tau):
    loss = -math.expm1(-1/(rate*tau))
    return loss/((1-f)+f*loss), f*math.exp(-1/(rate*tau))


def finite_baseline(f, tau, rate, n):
    a7, q7 = steady(7, f, tau); ar, qr = steady(rate, f, tau)
    a0 = a7 + (1-a7)*q7**28
    absolute = ar + (a0-ar)*np.power(qr, np.asarray(n))
    return absolute/a0, absolute, a0, ar/a0, qr


def event_recurrence(f, tau, rate, count):
    """Independent explicit recovery/read/decrement over all 28 baseline events."""
    times = [-4+j/7 for j in range(28)] + [j/rate for j in range(count)]
    a = 1.; last = times[0]; emitted = []
    for t in times:
        a += (1-a)*(-math.expm1(-(t-last)/tau))
        emitted.append(a); a *= f; last = t
    test = np.array(emitted[28:])
    return test/test[0], test


def compatible_b(q, tau):
    # f <= 1 is a mathematical compatibility constraint. Allow only endpoint
    # floating-point overshoot in log(f), never an unconstrained fitted f.
    log_f = math.log(q) + 1/(20*tau)
    if log_f > 5e-14: raise ValueError('tau violates f <= 1')
    f = math.exp(min(log_f, 0.))
    _, _, a0, b, qr = finite_baseline(f, tau, 20, [0])
    return b, f, a0, qr


def preflight():
    count = 0; worst = 0.; inverse_worst = 0.
    for f in [0., .2, .75, .95, 1.]:
        for tau in [.001, .3, 100., 1e5, 1e12]:
            for rate in [15, 20, 50]:
                n = np.arange(math.ceil(rate/2))
                y, a, a0, b, q = finite_baseline(f, tau, rate, n)
                yr, ar = event_recurrence(f, tau, rate, len(n))
                err = max(float(np.max(abs(y-yr))), float(np.max(abs(a-ar))))
                worst = max(worst, err)
                assert err < 2e-10 and a0 > 0 and np.isfinite(y).all()
                assert np.max(abs(y-shape(b, q, n))) < 2e-10
                assert abs(y[0]-1) < 2e-12
                if f == 1: assert np.max(abs(y-1)) < 2e-12
                count += 1
            if 0 < f < 1:
                _, _, _, b, q = finite_baseline(f, tau, 20, [0])
                if q > 0:
                    reconstructed, ff, _, qq = compatible_b(q, tau)
                    err = max(abs(b-reconstructed), abs(ff-f), abs(qq-q))
                    inverse_worst = max(inverse_worst, err)
                    assert err < 2e-10
                    count += 1
    n = np.arange(1, 10)
    for b, q in [(0., .7), (.2, .8), (.7, .4), (1., .3)]:
        assert abs(best_b(q, n, shape(b, q, n))-b) < 2e-12
        count += 1
    assert best_b(1., n, np.zeros(9)) == 0
    return dict(passed=True, cases=count+1, maximum_recurrence_error=worst,
                maximum_inverse_identity_error=inverse_worst,
                scope='Manufactured finite-baseline/shape/event-loop equivalence, f=0/1, tau up to1e12s, inverse identity, analytic b(q), and flat-null handling. No experimental means or fitted parameters used.')


def prepare():
    if any(output(s).exists() for s in ['-plan.json', '-results.json', '-arrays.npz', '-predictions.csv']):
        raise FileExistsError('Preserve frozen boundary outputs')
    checks = preflight()
    paths = [Path(__file__), POINTS,
             ROOT/'validation/orn-pn-depression-fig8f-results.json',
             ROOT/'validation/orn-pn-depression-fig8f-independent-review.json',
             ROOT/'validation/orn-pn-depression-calibration-plan.json',
             ROOT/'validation/orn-pn-depression-calibration-results.json',
             ROOT/'validation/orn-pn-depression-calibration-arrays.npz',
             ROOT/'validation/orn-pn-depression-calibration-predictions.csv',
             ROOT/'validation/orn-pn-depression-calibration-profile.csv']
    old = json.loads(paths[5].read_text())
    assert old['passed'] and old['bound_proximity']['tau_upper']
    plan = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), inputs=[record(p) for p in paths],
        versions=dict(numpy=np.__version__, scipy=scipy.__version__), preflight=checks,
        trigger='The original finite-baseline calibration reached its imposed100s recovery ceiling; no selection based on the previously inspected evaluation errors.',
        development=dict(frequency_hz=20, ordinals=list(range(1,10)), means=9,
            objective='Unweighted SSE in percentage points against100*(b+(1-b)*q**n), b and q each in[0,1]. No SEM weights, gain, phase, initial state or normalization fit.'),
        least_squares=dict(method='trf, analytic Jacobian', starts=[[b,q] for b in [0.,.25,.5,.75,1.] for q in [0.,.25,.5,.75,1.]],
            ftol=1e-12, xtol=1e-12, gtol=1e-10, max_nfev=4000),
        profile=dict(q_grid=np.linspace(0,1,4001).tolist(),
            b='At fixedq<1 use clip(sum((1-q**n)*(obs/100-q**n))/sum((1-q**n)**2),0,1); q=1 is the constant-one null with arbitraryb, recorded asb=0.',
            refinement='Refine every strict local grid basin with bounded minimize_scalar; include q=0/1 and grid minimum. xatol1e-14, maxiter2000.',
            selection='Smallest development SSE among converged multistarts and profile candidates. Retain every outcome; no evaluation-curve input. This finite numerical coverage is not a global-optimality proof.'),
        inversion=dict(formula='q=f*exp(-1/(20*tau)); f=q*exp(1/(20*tau)); tau_min=-1/(20*ln(q)). b=A20/[A7+(1-A7)*q7**28], Ar=(1-exp(-1/(r*tau)))/(1-f*exp(-1/(r*tau))), q7=f*exp(-1/(7*tau)).',
            tau_engineering_bounds_s=list(TAU_RANGE), log_grid_points=4097,
            actual_lower='max(tau_min,1e-6s); retain the whole grid, endpoint signs and monotonicity. A lower above1e12s yields unresolved mapping.',
            roots='Find every sign-changing adjacent log-grid bracket plus exactly zero grid samples. Brent xtol1e-12 and rtol1e-14 in log seconds, maxiter300; deduplicate roots within1e-9 log seconds. A finite grid can miss tangent/closely spaced roots.',
            boundaries='Shape b/q at or within1e-10 of0/1 is reported as a boundary/unidentified case, without pretending a unique finite inverse. A null q=1 or b=1 does not identify both original parameters. No roots and multiple detected roots are explicit outcomes.',
            evaluation_gate='Exactly one detected finite interior root, strictly decreasing sampled b(tau), absolute recovered b/q error <=1e-10, and independent event-recurrence error <=2e-10. Uniqueness is within the declared sampled search, not a proof over all positive tau.'),
        schedule='Fully recovered before28baseline events at-4+j/7 seconds,j=0..27. Test events n/r, n/r<.5; firsttest0, lastbaseline-to-firsttestgap1/7s. Normalize all test amplitudes to firsttest.',
        evaluation=dict(rates_hz=[15,50], rule='Only after the gate, evaluate each saved curve once using the fixed mapped f/tau and unchanged finite schedule; no fit or selection on these curves. They were previously inspected and share source animals.'),
        checks=dict(recurrence_tolerance_absolute=2e-10, shape_mapping_tolerance_absolute=1e-10,
                    profile_vs_multistart_SSE_tolerance=1e-6, comparison_SSE_recount_tolerance=1e-8),
        limits=['Conditional on the unrecovered primary initial-denominator and exact phase/preprocessing correspondence.',
                'Shape parameters are effective normalized descriptors. An invertible engineering schedule does not identify physiological release probability, recovery kinetics or absolute efficacy.',
                'No SEM weighting, confidence intervals, independent-animal inference or goodness-of-fit acceptance threshold.',
                'Female VM2 does not calibrate male VM7d; no graph, neural/runtime/body change or promotion.',
                'Original calibration and all prior files remain unchanged; retain first failures.'])
    write(output('-plan.json'), plan)
    print(json.dumps(dict(plan=record(output('-plan.json')), preflight=checks)))


def run():
    if any(output(s).exists() for s in ['-results.json','-arrays.npz','-predictions.csv']):
        raise FileExistsError('Preserve first boundary execution')
    plan = json.loads(output('-plan.json').read_text()); pin = record(output('-plan.json'))
    result = dict(schema=1, passed=False, plan=pin, attempts=[], roots=[], limits=plan['limits'])
    arrays = {}; context = 'input checks'; predictions = []
    try:
        for r in plan['inputs']: assert record(ROOT/r['path']) == r, r['path']
        assert plan['versions'] == dict(numpy=np.__version__, scipy=scipy.__version__)
        rows = list(csv.DictReader(POINTS.open()))
        development = [r for r in rows if int(r['frequency_hz'])==20 and r['mean_percent_initial']]
        n = np.array([int(r['point_ordinal']) for r in development]); obs = np.array([float(r['mean_percent_initial']) for r in development])
        assert n.tolist() == plan['development']['ordinals']
        arrays.update(development_ordinals=n, development_mean_percent=obs)
        def residual(x): return 100*shape(x[0],x[1],n)-obs
        def jacobian(x): return 100*np.column_stack((1-x[1]**n, (1-x[0])*n*x[1]**(n-1)))
        def objective(q):
            b = best_b(q,n,obs/100); r=100*shape(b,q,n)-obs
            return float(np.dot(r,r)),b
        candidates=[]; opt=plan['least_squares']
        for i,start in enumerate(opt['starts']):
            context=dict(stage='multistart', ordinal=i)
            fit=least_squares(residual,start,jac=jacobian,bounds=([0.,0.],[1.,1.]),method='trf',
                ftol=opt['ftol'],xtol=opt['xtol'],gtol=opt['gtol'],max_nfev=opt['max_nfev'])
            item=dict(method='least_squares',start=start,success=bool(fit.success),status=int(fit.status),message=fit.message,
                nfev=fit.nfev,b=float(fit.x[0]),q=float(fit.x[1]),SSE=float(np.dot(fit.fun,fit.fun)),optimality=float(fit.optimality),active_mask=fit.active_mask.tolist())
            result['attempts'].append(item)
            if fit.success: candidates.append(item)
        assert candidates, 'No converged shape multistart'
        context='analytic b(q) profile'; qgrid=np.array(plan['profile']['q_grid'])
        profile=np.array([objective(float(q)) for q in qgrid])
        arrays.update(profile_q=qgrid,profile_SSE=profile[:,0],profile_b=profile[:,1])
        choices=[]; basins=[]
        for j in sorted({0,len(qgrid)-1,int(profile[:,0].argmin())}):
            choices.append(dict(method='profile_grid',q=float(qgrid[j]),b=float(profile[j,1]),SSE=float(profile[j,0]),success=True))
        for j in range(1,len(qgrid)-1):
            if profile[j,0]<=profile[j-1,0] and profile[j,0]<=profile[j+1,0] and (profile[j,0]<profile[j-1,0] or profile[j,0]<profile[j+1,0]):
                basins.append([float(qgrid[j-1]),float(qgrid[j+1])])
        if profile[0,0]<=profile[1,0]: basins.append(qgrid[:2].tolist())
        if profile[-1,0]<=profile[-2,0]: basins.append(qgrid[-2:].tolist())
        for bracket in basins:
            fit=minimize_scalar(lambda q:objective(q)[0],bounds=bracket,method='bounded',options={'xatol':1e-14,'maxiter':2000})
            item=dict(method='profile_refinement',bracket=bracket,success=bool(fit.success),message=fit.message,nfev=fit.nfev,
                q=float(fit.x),b=objective(float(fit.x))[1],SSE=float(fit.fun))
            choices.append(item)
        result['profile_candidates']=choices
        profile_best=min((c for c in choices if c['success']),key=lambda c:c['SSE'])
        ls_best=min(candidates,key=lambda c:c['SSE'])
        result['profile_vs_multistart_SSE_difference']=profile_best['SSE']-ls_best['SSE']
        assert abs(profile_best['SSE']-ls_best['SSE'])<=plan['checks']['profile_vs_multistart_SSE_tolerance']
        candidates.extend(c for c in choices if c['success']); best=min(candidates,key=lambda c:c['SSE'])
        b,q=best['b'],best['q']; result.update(best_shape=best,RMSE_development_percentage_points=math.sqrt(best['SSE']/9),
            converged_multistarts=sum(a['success'] for a in result['attempts']),
            multistart_SSE_range=[min(a['SSE'] for a in result['attempts'] if a['success']),max(a['SSE'] for a in result['attempts'] if a['success'])])
        arrays['shape_development_prediction_percent']=100*shape(b,q,n)
        old=json.loads((ROOT/'validation/orn-pn-depression-calibration-results.json').read_text())
        result['original_calibration_comparison']=dict(original_f=old['best']['f'],original_tau_s=old['best']['tau_s'],
            original_SSE=old['best']['SSE'],shape_SSE_improvement=old['best']['SSE']-best['SSE'])
        if not (1e-10<b<1-1e-10 and 1e-10<q<1-1e-10):
            result['mapping_status']='boundary_shape_unidentified'; result['evaluation_performed']=False
        else:
            context='inverse scan'; tau_min=-1/(20*math.log(q));lo=max(tau_min,TAU_RANGE[0]);hi=TAU_RANGE[1]
            result['physical_tau_lower_s']=tau_min; result['searched_tau_bounds_s']=[lo,hi]
            if lo>=hi:
                result['mapping_status']='physical_lower_outside_engineering_range'; result['evaluation_performed']=False
            else:
                loggrid=np.linspace(math.log(lo),math.log(hi),plan['inversion']['log_grid_points'])
                values=np.array([compatible_b(q,math.exp(t)) for t in loggrid]); delta=values[:,0]-b
                arrays.update(inverse_logtau=loggrid,inverse_b=values[:,0],inverse_f=values[:,1],inverse_first_test_efficacy=values[:,2],inverse_q_reconstructed=values[:,3],inverse_b_residual=delta)
                brackets=[]; roots=[float(loggrid[j]) for j in np.flatnonzero(delta==0)]
                for j in range(len(loggrid)-1):
                    if (delta[j]<0<delta[j+1]) or (delta[j+1]<0<delta[j]): brackets.append([float(loggrid[j]),float(loggrid[j+1])])
                result.update(inversion_log_brackets=brackets,inversion_endpoint_residuals=[float(delta[0]),float(delta[-1])],
                    sampled_b_strictly_decreasing=bool(np.all(np.diff(values[:,0])<0)),
                    minimum_sampled_absolute_b_residual=float(np.min(abs(delta))))
                for bracket in brackets:
                    root,info=brentq(lambda logtau:compatible_b(q,math.exp(logtau))[0]-b,*bracket,xtol=1e-12,rtol=1e-14,maxiter=300,full_output=True)
                    assert info.converged
                    roots.append(float(root))
                unique=[]
                for logtau in sorted(roots):
                    if not unique or abs(logtau-unique[-1])>1e-9: unique.append(logtau)
                for logtau in unique:
                    tau=math.exp(logtau); recovered,f,a0,qr=compatible_b(q,tau)
                    result['roots'].append(dict(log_tau=logtau,tau_s=tau,f=f,first_test_efficacy=a0,b_recovered=recovered,q_recovered=qr,
                        b_error=recovered-b,q_error=qr-q))
                result['mapping_status']='no_detected_root' if not unique else 'multiple_detected_roots' if len(unique)>1 else 'one_detected_finite_root'
                gate=len(unique)==1 and result['sampled_b_strictly_decreasing']
                if gate:
                    mapped=result['roots'][0];f,tau=mapped['f'],mapped['tau_s']
                    assert max(abs(mapped['b_error']),abs(mapped['q_error']))<=plan['checks']['shape_mapping_tolerance_absolute']
                    nominal,absolute,a0,_,_=finite_baseline(f,tau,20,np.arange(10))
                    independent,independent_absolute=event_recurrence(f,tau,20,10)
                    error=max(float(np.max(abs(nominal-independent))),float(np.max(abs(absolute-independent_absolute))),float(np.max(abs(nominal-shape(b,q,np.arange(10))))))
                    result['mapped_development_recurrence_max_error']=error
                    assert error<=plan['checks']['recurrence_tolerance_absolute']
                    devSSE=math.fsum((float(100*independent[j])-float(obs[j-1]))**2 for j in range(1,10))
                    assert abs(devSSE-best['SSE'])<=plan['checks']['comparison_SSE_recount_tolerance']
                    result['mapped_development_SSE']=devSSE
                    arrays['mapped_development_percent']=100*nominal
                    arrays['mapped_development_absolute']=absolute.copy()
                    result['evaluation_performed']=True; result['evaluation']=[]
                    for rate in [15,50]:
                        context=dict(stage='fixed_parameter_evaluation',rate=rate)
                        rr=[r for r in rows if int(r['frequency_hz'])==rate];nn=np.array([int(r['point_ordinal']) for r in rr])
                        assert nn.tolist()==list(range(math.ceil(rate/2)))
                        pred,absolute,a0,bb,qq=finite_baseline(f,tau,rate,nn)
                        ev,ea=event_recurrence(f,tau,rate,len(nn));err=max(float(np.max(abs(pred-ev))),float(np.max(abs(absolute-ea))))
                        assert err<=plan['checks']['recurrence_tolerance_absolute']
                        observed=[float(r['mean_percent_initial']) if r['mean_percent_initial'] else None for r in rr]
                        assert observed[0] is None and all(v is not None for v in observed[1:])
                        residuals=[float(100*pred[j])-observed[j] for j in range(1,len(nn))]
                        result['evaluation'].append(dict(frequency_hz=rate,means=len(residuals),RMSE_percentage_points=math.sqrt(math.fsum(x*x for x in residuals)/len(residuals)),
                            MAE_percentage_points=math.fsum(abs(x) for x in residuals)/len(residuals),mean_signed_error_percentage_points=math.fsum(residuals)/len(residuals),
                            recurrence_max_error=err,normalized_floor=bb,per_event_decay=qq,first_test_efficacy=a0))
                        arrays[f'evaluation_{rate}_percent']=100*pred;arrays[f'evaluation_{rate}_absolute']=absolute
                        for j,r in enumerate(rr): predictions.append(dict(frequency_hz=rate,ordinal=j,role='evaluation',observed_percent=observed[j],predicted_percent=float(100*pred[j]),absolute_model_efficacy=float(absolute[j])))
                    for j in range(10): predictions.append(dict(frequency_hz=20,ordinal=j,role='development',observed_percent=None if j==0 else float(obs[j-1]),predicted_percent=float(100*nominal[j]),absolute_model_efficacy=float(arrays['mapped_development_absolute'][j])))
                else:
                    result['evaluation_performed']=False
                    if len(unique)==1: result['mapping_status']='single_root_with_nonmonotone_sampled_inverse_unresolved'
        for r in plan['inputs']: assert record(ROOT/r['path'])==r,r['path']
        assert record(output('-plan.json'))==pin
        result['passed']=True
    except (Exception,KeyboardInterrupt) as e:
        result['failure']=dict(type=type(e).__name__,message=str(e),context=context,traceback=traceback.format_exc())
    with output('-arrays.npz').open('xb') as f: np.savez_compressed(f,**arrays)
    if predictions:
        with output('-predictions.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(predictions[0]),lineterminator='\n');writer.writeheader();writer.writerows(predictions)
    result.update(completed_utc=datetime.now(timezone.utc).isoformat(),artifacts=[record(output(s)) for s in ['-arrays.npz','-predictions.csv'] if output(s).exists()])
    write(output('-results.json'),result)
    print(json.dumps(dict(passed=result['passed'],result=record(output('-results.json')),best=result.get('best_shape'),mapping_status=result.get('mapping_status'),roots=result['roots'],evaluation=result.get('evaluation'),failure=result.get('failure'))))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    if args.action=='prepare': prepare()
    else: raise SystemExit(run())
