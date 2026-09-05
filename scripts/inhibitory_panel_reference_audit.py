#!/usr/bin/env python3
"""Independent scalar references; no producer, helper, graph or runtime imports.

Units: v,p are mV; h is dimensionless; time is ms. The specified equations are
  v' = (-52-v+p-h*(v+75))/20, p'=-p/5, h'=-h/5.
Writing y=v+75 gives y'+(1+h(t))*y/20=(23+p(t))/20.
For T=dt, p(T)=p0*exp(-T/5), h(T)=h0*exp(-T/5). With backward lag
q=(T-t)/T, the accumulated attenuation from t to T is
  x(q)=T*q/20 + h(T)*expm1(T*q/5)/4.
Its derivative is positive. Changing variables in the integrating factor gives
  y(T)=exp(-x(1))*y(0) + integral_0^x(1) exp(-x)
       * (23+p(T)*exp(T*q(x)/5))/(1+h(T)*exp(T*q(x)/5)) dx.
SciPy Brent solves q(x) on [0,1]. Adaptive and separately generated 64-node
Legendre integration use this coordinate, without a special h=0 source branch.
Since p,h>=0, the omitted tail after c is <=(23+p0)*exp(-c) mV.

The ODE reference separately advances all three original states in time,
using an analytic 3x3 Jacobian for Radau. It does not call the integral path.
Both time constants, method-selection boundary and tolerances are fixed before
validation against the retained 125-case scalar grid. No parameter search,
threshold/reset logic, fitting or physiological conclusion is implemented.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import traceback
import warnings

import numpy as np
import scipy
from scipy.integrate import IntegrationWarning, quad, solve_ivp
from scipy.optimize import brentq

TAIL_MV = 1e-15
QUAD_ATOL, QUAD_RTOL = 1e-11, 1e-13
ODE_ATOL, ODE_RTOL = 2e-12, 2e-12
BRENT_RTOL = 8*np.finfo(np.float64).eps
BRENT_XTOL = np.nextafter(0., 1.)
LEGENDRE_NODES, LEGENDRE_WEIGHTS = np.polynomial.legendre.leggauss(64)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return dict(value=None, nonfinite='nan' if math.isnan(value) else '+inf' if value>0 else '-inf')
    if isinstance(value, dict):return {k:_json_safe(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)):return [_json_safe(v) for v in value]
    return value


class ReferenceAuditError(RuntimeError):
    """A failed method, with inputs and completed method values for retention."""
    def __init__(self, record):
        self.record = _json_safe(record)
        self.inputs = self.record['inputs']
        self.method = record['method']
        super().__init__(f"Independent reference {self.method} failed: {record['error_type']}: {record['message']}")


def evaluate(v, p, h, dt=.1):
    """Return six reference fields, or raise ReferenceAuditError with evidence.

    quad_error_estimate includes QUADPACK's estimate and the analytic truncated
    tail bound. It is not a rigorous enclosure of floating-point/inversion error.
    Caller owns archival and any comparison gate; no files are written here.
    """
    inputs=dict(v=v,p=p,h=h,dt=dt);partial={};method='input_validation'
    try:
        v,p,h,T=map(float,(v,p,h,dt));inputs=dict(v=v,p=p,h=h,dt=T)
        if not all(map(math.isfinite,(v,p,h,T))) or p<0 or h<0 or T<=0:
            raise ValueError('Require finite v,p,h,dt, nonnegative p/h and positive dt')
        method='attenuation_setup'
        decay=math.exp(-T/5.);p_end=p*decay;h_end=h*decay
        def attenuation(q):
            return T*q/20. + (h_end/4.)*math.expm1(T*q/5.)
        A=attenuation(1.)
        cutoff=min(A,math.log(23.+p)-math.log(TAIL_MV))
        tail=0. if cutoff==A else (23.+p)*math.exp(-cutoff)
        initial=math.exp(-A)*(v+75.)
        if not all(map(math.isfinite,(A,cutoff,tail,initial))):
            raise ArithmeticError('Nonfinite attenuation setup')

        def kernel(x):
            if x==0.:q=0.
            else:q=brentq(lambda q:attenuation(q)-x,0.,1.,xtol=BRENT_XTOL,rtol=BRENT_RTOL,maxiter=200)
            e=math.exp(T*q/5.)
            return math.exp(-x)*(23.+p_end*e)/(1.+h_end*e)

        method='adaptive_quad'
        with warnings.catch_warnings():
            warnings.simplefilter('error',IntegrationWarning)
            integral,estimate=quad(kernel,0.,cutoff,epsabs=QUAD_ATOL,epsrel=QUAD_RTOL,limit=200)
        partial.update(quad_v=float(-75.+initial+integral),quad_error_estimate=float(estimate+tail))
        method='order64_quad'
        half=cutoff/2.
        integral64=half*math.fsum(float(weight)*kernel(half*(float(node)+1.))
            for node,weight in zip(LEGENDRE_NODES,LEGENDRE_WEIGHTS))
        partial['order64_v']=float(-75.+initial+integral64)

        method='time_domain_ode'
        ode_method='Radau' if (1.+h)*T/20.>10. else 'DOP853'
        def derivative(t,state):
            voltage,excitation,inhibition=state
            return [(-52.-voltage+excitation-inhibition*(voltage+75.))/20.,-excitation/5.,-inhibition/5.]
        def jacobian(t,state):
            voltage,_,inhibition=state
            return [[-(1.+inhibition)/20.,1./20.,-(voltage+75.)/20.],
                    [0.,-1./5.,0.],[0.,0.,-1./5.]]
        partial['ode_method']=ode_method
        with warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            solution=solve_ivp(derivative,(0.,T),[v,p,h],method=ode_method,
                rtol=ODE_RTOL,atol=ODE_ATOL,**({'jac':jacobian} if ode_method=='Radau' else {}))
        partial['ode_nfev']=int(solution.nfev)
        if not solution.success or solution.t[-1]!=T or not np.isfinite(solution.y[:,-1]).all():
            raise RuntimeError('ODE incomplete/nonfinite: '+solution.message)
        partial['ode_v']=float(solution.y[0,-1])
        method='finite_result'
        if not all(math.isfinite(partial[k]) for k in ['quad_v','quad_error_estimate','order64_v','ode_v']):
            raise ArithmeticError('Nonfinite reference output')
        return partial
    except Exception as error:
        raise ReferenceAuditError(dict(inputs=inputs,method=method,partial=partial,
            error_type=type(error).__name__,message=str(error),traceback=traceback.format_exc())) from error


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate():
    root=Path(__file__).resolve().parents[1]
    plan_path=root/'validation/inhibitory-panel-reference-audit-plan.json'
    result_path=root/'validation/inhibitory-panel-reference-audit-results.json'
    if plan_path.exists() or result_path.exists():raise FileExistsError('Preserve frozen reference audit attempt')
    original_plan=root/'validation/inhibitory-factorial-solver-plan.json'
    original_result=root/'validation/inhibitory-factorial-solver-results.json'
    pins={str(Path(__file__).relative_to(root)):_sha(__file__),
        str(original_plan.relative_to(root)):'14df7dad75cec57c86f3608c6ffec842b0cf7e83d707758f2d6220198fe6d687',
        str(original_result.relative_to(root)):'7f0a65072d1a0cd7121c7405e7671a3c44013a85af951e0d864bb4617c284e38',
        'scripts/inhibitory_factorial_solver.py':'ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711'}
    for name,digest in pins.items():
        if _sha(root/name)!=digest:raise RuntimeError('Frozen source/input changed: '+name)
    old_plan=json.loads(original_plan.read_text());old_result=json.loads(original_result.read_text())
    if not old_result['complete'] or not old_result['passed'] or len(old_plan['cases'])!=125 or len(old_result['cases'])!=125:
        raise RuntimeError('Incomplete or unexpected frozen scalar fixture')
    tolerances=old_plan['tolerances_mv']
    plan=dict(version=1,frozen_utc=datetime.now(timezone.utc).isoformat(),source_sha256=pins,
        scope='Evaluate only the exact 125 saved scalar cases, once each; no original helper import, new grid or network.',
        methods=dict(derivation=__doc__,quad_epsabs=QUAD_ATOL,quad_epsrel=QUAD_RTOL,tail_bound_mv=TAIL_MV,
            brent_coordinate='dimensionless backward lag q in [0,1]',brent_rtol=float(BRENT_RTOL),brent_xtol=float(BRENT_XTOL),
            legendre_order=64,ode_states=['v','p','h'],ode_rtol=ODE_RTOL,ode_atol=ODE_ATOL,ode_selection='Radau iff (1+h)*dt/20>10, otherwise DOP853',ode_jacobian='analytic 3x3 for Radau'),
        tolerances_mv=tolerances,case_count=125,case_source=str(original_plan.relative_to(root)),
        environment=dict(numpy=np.__version__,scipy=scipy.__version__),
        failure_policy='Record each failed case with exact inputs, failed method and completed partial values. No retries, parameter changes or substitutions; retain first receipt.',
        claim_limit='Synthetic scalar numerical audit; neither physiological validation nor recurrent-network equivalence.')
    plan_path.write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
    rows=[];errors=[];checks=[]
    try:
        for i,(case,old) in enumerate(zip(old_plan['cases'],old_result['cases'])):
            row=dict(index=i,inputs=case,saved_production_v=old['production'][0],saved_quad_v=old['quad_mv'],saved_order64_v=old['order64_mv'],saved_ode_v=old['ode_mv'])
            try:
                if case!=old['case']:raise ValueError('Saved case order/identity mismatch')
                value=evaluate(*(case[k] for k in ['v','p','h','dt']))
                row['independent']=value
                diffs=dict(quad_saved_production=abs(value['quad_v']-old['production'][0]),
                    order64_saved_production=abs(value['order64_v']-old['production'][0]),quad_saved_quad=abs(value['quad_v']-old['quad_mv']),
                    order64_saved_order64=abs(value['order64_v']-old['order64_mv']),ode_saved_ode=abs(value['ode_v']-old['ode_mv']),
                    quad_order64=abs(value['quad_v']-value['order64_v']),ode_quad=abs(value['ode_v']-value['quad_v']))
                row['absolute_differences_mv']=diffs
                row['checks']={k:d<=tolerances['ode_vs_quad' if k.startswith('ode_') else 'production_vs_quad'] for k,d in diffs.items()}
                row['checks']['quad_error_estimate']=value['quad_error_estimate']<=tolerances['quad_error_estimate']
                row['checks']['interval_bounds']=all(-75.-tolerances['bounds']<=value[k]<=max(case['v'],-52.+case['p'])+tolerances['bounds'] for k in ['quad_v','order64_v','ode_v'])
                row['passed']=all(row['checks'].values())
            except Exception as error:
                row.update(passed=False,error=error.record if isinstance(error,ReferenceAuditError) else dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
            rows.append(row)
            if (i+1)%25==0:print(json.dumps(dict(completed_cases=i+1,passed_so_far=all(r['passed'] for r in rows))),flush=True)
    except (Exception,KeyboardInterrupt) as error:
        errors.append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc(),next_case_index=len(rows),inputs=old_plan['cases'][len(rows)] if len(rows)<125 else None))
    for name,digest in pins.items():checks.append(dict(name='unchanged:'+name,passed=_sha(root/name)==digest))
    complete=len(rows)==125
    numeric=[r for r in rows if 'independent' in r]
    summary=dict(computed_cases=len(numeric),failed_cases=[r['index'] for r in rows if not r['passed']],
        max_differences_mv={key:max(r['absolute_differences_mv'][key] for r in numeric) for key in numeric[0]['absolute_differences_mv']} if numeric else {},
        max_quad_error_estimate=max((r['independent']['quad_error_estimate'] for r in numeric),default=None),
        ode_methods={method:sum(r['independent']['ode_method']==method for r in numeric) for method in ['DOP853','Radau']})
    result=dict(version=1,completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=_sha(plan_path),source_sha256=pins,
        complete=complete,passed=complete and not errors and all(r['passed'] for r in rows) and all(c['passed'] for c in checks),
        cases=rows,checks=checks,errors=errors,summary=summary,
        limits=['All three numerical methods solve the stated scalar equation; adaptive and order64 share a coordinate and Brent inversion, while the ODE path is separate.',
            'The estimate adds QUADPACK error and a tail bound; it is not a certified bound on all floating-point/inversion errors.',
            'Original source was inspected for fixed conventions and hashed, but never imported or executed. No graph, spike, reset, fit or new parameter sweep.'])
    result_path.write_text(json.dumps(_json_safe(result),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],complete=complete,summary=summary,errors=errors),indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['validate']);parser.parse_args()
    raise SystemExit(validate())
