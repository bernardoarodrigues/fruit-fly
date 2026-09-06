"""Experimental APL conductance recruitment with a positive midpoint integrator.

This leaves the frozen first-order experiment unchanged. Shared recruitment and
removal times recover its slow-state ODE; unequal times are a nested candidate.
"""
import numpy as np
from numba import njit


@njit(cache=True)
def _activation(v, scale):
    return max(v,0.)/(scale+max(v,0.))


@njit(cache=True)
def _voltage(v, d, current, dt, circuit, g, reversal):
    cs,cd,gl,gc=circuit
    a=-1000*(gl+gc+g)/cs;b=1000*gc/cs;c=1000*gc/cd;dd=-1000*gc/cd
    gap=np.sqrt((a-dd)**2+4*b*c)
    fast=(a+dd-gap)/2
    slow=(1e6*gc*(gl+g)/(cs*cd))/fast
    ef=np.exp(fast*dt);factor=np.exp(slow*dt)*(-np.expm1(-gap*dt))/gap
    equilibrium=(current+g*reversal)/(gl+g)
    x=v-equilibrium;y=d-equilibrium
    return (equilibrium+(ef+factor*(a-fast))*x+factor*b*y,
            equilibrium+factor*c*x+(ef+factor*(dd-fast))*y)


@njit(cache=True)
def _gates(h,z,m,dt,th,ton,toff):
    rate=m/ton+(1-m)/toff;target=(m/ton)/rate
    return ((1-m)+(h-(1-m))*np.exp(-dt/th),target+(z-target)*np.exp(-dt*rate))


@njit(cache=True)
def step(state,current,dt,circuit,parameters,reversal):
    """Exponential midpoint with frozen positive conductance at the midpoint.

    parameters = gf, gs, tau_h, tau_on, tau_off, scale_mV.
    dz/dt = m*(1-z)/tau_on - (1-m)*z/tau_off.
    """
    v,d,h,z=state;gf,gs,th,ton,toff,scale=parameters
    m=_activation(v,scale);g=gf*m*h+gs*z
    vp,dp=_voltage(v,d,current,dt/2,circuit,g,reversal)
    hp,zp=_gates(h,z,m,dt/2,th,ton,toff)
    mid=_activation(vp,scale);gm=gf*mid*hp+gs*zp
    vn,dn=_voltage(v,d,current,dt,circuit,gm,reversal)
    hn,zn=_gates(h,z,mid,dt,th,ton,toff)
    return np.array([vn,dn,hn,zn])


@njit(cache=True)
def pulse(circuit,parameters,reversal,dt=.00005,amplitude=2000.,duration=.75,recovery=2.8):
    """Always observe at the original 10kHz times and average ten samples.

    dt must divide 0.1ms; refinement changes integration, not observation times.
    """
    substeps=int(round(.0001/dt));assert substeps>=1 and abs(substeps*dt-.0001)<1e-12
    n=int(round((duration+recovery)*10000));assert n%10==0
    out=np.zeros(n//10);state=np.array([0.,0.,1.,0.]);minimum=0.
    for i in range(n):
        out[i//10]+=state[0]/10
        current=amplitude if i<int(round(duration*10000)) else 0.
        for _ in range(substeps):
            state=step(state,current,dt,circuit,parameters,reversal)
            minimum=min(minimum,state[0],state[1])
    return out,state,minimum
