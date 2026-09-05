"""Exact scalar low-pass reference for a declared piecewise-linear dye proxy.

This is a stimulus-to-reporter diagnostic, not an APL membrane/release law.
"""
import numpy as np


def linear_filter(input_times,values,query_times,tau):
    """Solve tau*y'=u-y, y(0)=0, exactly between linear input knots.

    tau=0 is the explicitly separate instantaneous limit. Input and query times
    are nonnegative; supplied knots must span queries. No inferred prehistory.
    """
    t=np.asarray(input_times,float);u=np.asarray(values,float);q=np.asarray(query_times,float)
    if t.ndim!=1 or u.shape!=t.shape or q.ndim!=1 or len(t)<2:
        raise ValueError('One-dimensional input and query arrays required')
    if not all(np.isfinite(x).all() for x in [t,u,q]) or not np.isfinite(tau) or tau<0:
        raise ValueError('Finite arrays and nonnegative finite tau required')
    if t[0]!=0 or np.any(np.diff(t)<=0) or np.any(q<0) or np.any(q>t[-1]):
        raise ValueError('Increasing input starts at zero and spans queries')
    if tau==0:return np.interp(q,t,u)
    grid=np.unique(np.r_[t[t<=q.max()],q]);drive=np.interp(grid,t,u)
    output=np.zeros(len(grid))
    for k,h in enumerate(np.diff(grid)):
        z=h/tau;alpha=-np.expm1(-z)
        # h - tau*(1-exp(-h/tau)), stable as h/tau approaches zero.
        ramp=h*(z/2-z*z/6+z**3/24-z**4/120) if z<1e-3 else h-tau*alpha
        output[k+1]=np.exp(-z)*output[k]+alpha*drive[k]+ramp*(drive[k+1]-drive[k])/h
    return output[np.searchsorted(grid,q)]


def profile_gain(prediction,target):
    x=np.asarray(prediction,float);y=np.asarray(target,float)
    denominator=float(np.sum(x*x))
    gain=max(0.,float(np.sum(x*y))/denominator) if denominator>0 else 0.
    return gain,float(np.mean((gain*x-y)**2))
