"""Experimental APL current-clamp candidate; disconnected from neural defaults.

The two-pole impedance is realized by soma leak/capacitance and a passive,
nonleaking distal capacitance. This realization is not anatomical identification.
Voltages are relative to held baseline; pA, mV, nS, pF and seconds are used.
"""
import numpy as np
from numba import njit


def passive_circuit(resistance_MOhm, tau_s):
    """Return Cs, Cd, gL, gC with exactly the supplied two-pole impedance."""
    r=np.asarray(resistance_MOhm,float)/1000  # GOhm = 1/nS
    tau=np.asarray(tau_s,float)
    if r.shape!=(2,) or tau.shape!=(2,) or not np.isfinite([r,tau]).all() or np.any(r<=0) or np.any(tau<=0) or tau[0]==tau[1]:
        raise ValueError('Two distinct positive poles and positive residues required')
    total=r.sum();b=r[0]*tau[1]+r[1]*tau[0];product=tau.prod()
    cs=product/b;gl=1/total;gc=tau.sum()/b-product*total/b**2-gl
    cd=gc*b/total
    if min(cs,cd,gl,gc)<=0:raise ValueError('Degenerate passive realization')
    return np.array([cs*1000,cd*1000,gl,gc])


@njit(cache=True)
def activation(v, scale):
    return max(v,0.)/(scale+max(v,0.))


@njit(cache=True)
def step(state, current, dt, circuit, parameters, reversal, inactivating):
    """First-order IMEX step: M-matrix voltage solve, exponential gate updates.

    parameters = [g_fast, g_slow, tau_h, tau_z, activation_scale_mV].
    Fast voltage activation is instantaneous. h tends to 1-m; z tends to m.
    No measured post-pulse voltage or outward state enters the update.
    """
    vs,vd,h,z=state;cs,cd,gl,gc=circuit;gf,gs,th,tz,scale=parameters
    m=activation(vs,scale)
    g=gf*m*(h if inactivating else 1.)+gs*z
    # pF * mV / second = 1000 pA
    a=cs/(1000*dt)+gl+gc+g;d=cd/(1000*dt)+gc
    rhs=cs/(1000*dt)*vs+current+g*reversal
    rhsd=cd/(1000*dt)*vd
    vnext=(rhs*d+gc*rhsd)/(a*d-gc*gc)
    dnext=(a*rhsd+gc*rhs)/(a*d-gc*gc)
    mnext=activation(vnext,scale)
    hnext=(1-mnext)+(h-(1-mnext))*np.exp(-dt/th)
    znext=mnext+(z-mnext)*np.exp(-dt/tz)
    return np.array([vnext,dnext,hnext,znext])


@njit(cache=True)
def pulse(circuit, parameters, reversal, inactivating, amplitude=2000., duration=.75,
          recovery=2.8, dt=.0001, bin_s=.001):
    """Sample at t=0,dt,..., then bin identically to acquired traces."""
    n=int(round((duration+recovery)/dt));width=int(round(bin_s/dt))
    out=np.zeros(n//width);state=np.array([0.,0.,1.,0.]);minimum=0.
    for i in range(n):
        out[i//width]+=state[0]/width
        state=step(state,amplitude if i<int(round(duration/dt)) else 0.,dt,circuit,parameters,reversal,inactivating)
        minimum=min(minimum,state[0],state[1])
    return out,state,minimum
