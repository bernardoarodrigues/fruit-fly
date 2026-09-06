"""Positive passive modes conditioned on a measured finite-pulse plateau.

Alpha is the fraction of late-plateau response, not a channel conductance.
"""
import numpy as np
from scipy.optimize import minimize, minimize_scalar


def plateau_factor(tau,dt=.0001,start=.4,count=1000):
    """Mean unit-step response on the exact sampled plateau window."""
    if tau<=0 or dt<=0 or start<0 or count<1:raise ValueError('Positive time scales and sample count required')
    mean_exponential=np.exp(-start/tau)*np.expm1(-count*dt/tau)/(count*np.expm1(-dt/tau))
    return 1-mean_exponential


def mode_on(t,tau):return -np.expm1(-np.asarray(t)/tau)/plateau_factor(tau)


def mode_off(t,tau,pulse_s=.5):return -np.expm1(-pulse_s/tau)*np.exp(-np.asarray(t)/tau)/plateau_factor(tau)


def response(t,fit,offset=False):
    fn=mode_off if offset else mode_on
    return fit['alpha']*fn(t,fit['tau_fast_s'])+(1-fit['alpha'])*fn(t,fit['tau_slow_s'])


def fit_modes(t,y,bounds,grid_points=25):
    """Single-mode control plus two modes with profiled, bounded mixture weight."""
    t=np.asarray(t,float);y=np.asarray(y,float)
    if t.shape!=y.shape or t.ndim!=1 or len(t)<4 or not np.isfinite(t).all() or not np.isfinite(y).all():raise ValueError('Finite matching arrays required')
    lo,hi=bounds
    if not 0<lo<hi:raise ValueError('Positive ordered bounds required')
    logbounds=np.log(bounds)
    def single_cost(z):return float(np.mean((mode_on(t,np.exp(z))-y)**2))
    one=minimize_scalar(single_cost,bounds=logbounds,method='bounded',options={'xatol':1e-11})
    if not one.success:raise RuntimeError('Single-mode optimization failed')
    score,z=min([(one.fun,one.x)]+[(single_cost(x),x) for x in logbounds]);tau=float(np.exp(z))
    single=dict(tau_fast_s=tau,tau_slow_s=tau,alpha=1.,fit_mse=score)
    def profile(logs):
        tf,ts=np.sort(np.exp(logs));fast=mode_on(t,tf);slow=mode_on(t,ts);d=fast-slow
        denom=float(d@d);alpha=float(np.clip(d@(y-slow)/denom,0,1)) if denom>1e-24 else 1.
        return float(np.mean((slow+alpha*d-y)**2)),alpha,float(tf),float(ts)
    grid=np.linspace(*logbounds,grid_points);candidates=[]
    for i,x in enumerate(grid):
        for z in grid[i:]:
            mse,alpha,tf,ts=profile([x,z]);candidates.append((mse,alpha,tf,ts))
    candidates.append((score,1.,tau,tau))
    # Refine the four best separated grid seeds. Include all original candidates.
    seeds=[]
    for c in sorted(candidates):
        point=np.log(c[2:])
        if all(np.linalg.norm(point-prev)>.35 for prev in seeds):seeds.append(point)
        if len(seeds)==4:break
    optimizations=[]
    for seed in seeds:
        result=minimize(lambda x:profile(x)[0],seed,method='Nelder-Mead',bounds=[logbounds,logbounds],
                        options={'xatol':1e-9,'fatol':1e-13,'maxiter':1500})
        optimizations.append(dict(success=bool(result.success),message=str(result.message),evaluations=int(result.nfev)))
        if not result.success:raise RuntimeError('Two-mode optimization failed')
        candidates.append(profile(result.x))
    mse,alpha,tf,ts=min(candidates)
    two=dict(tau_fast_s=tf,tau_slow_s=ts,alpha=alpha,fit_mse=mse,optimization_records=optimizations)
    for model in (single,two):
        model['at_tau_bound']=any(abs(np.log(model[k]/b))<1e-7 for k in ('tau_fast_s','tau_slow_s') for b in bounds)
        model['degenerate_mixture']=bool(model['alpha']<1e-6 or model['alpha']>1-1e-6 or model['tau_slow_s']/model['tau_fast_s']<1.0001)
        cf=model['alpha']/plateau_factor(model['tau_fast_s']);cs=(1-model['alpha'])/plateau_factor(model['tau_slow_s'])
        model['steady_fast_weight']=cf/(cf+cs);model['steady_gain_relative_to_measured_plateau']=cf+cs
    return dict(single=single,two=two)
