"""Experimental graded APL electrical state model, not enabled by the runtime.

Two or more passive voltage modes receive injected current minus a nonnegative
outward current. The latter relaxes to an explicitly supplied target. This
module does not infer that target from calcium, spikes, voltage or synapses.
Units: seconds, mV, pA and MOhm. Absolute resting voltage is an external offset.
"""
from dataclasses import dataclass
import numpy as np


def decay_convolution(time_s, passive_tau_s, outward_tau_s):
    """Exact convolution of outward-current decay with a passive mode.

    Stable for equal/near-equal time constants and long time intervals.
    """
    t=np.asarray(time_s,dtype=float);tau=np.asarray(passive_tau_s,dtype=float)
    if np.any(~np.isfinite(t)) or np.any(t<0) or np.any(~np.isfinite(tau)) or np.any(tau<=0) or not np.isfinite(outward_tau_s) or outward_tau_s<=0:
        raise ValueError('Finite nonnegative time and positive time constants required')
    difference=np.abs(1/tau-1/outward_tau_s)
    z=t*difference
    ratio=np.ones_like(z)
    np.divide(-np.expm1(-z),z,out=ratio,where=z!=0)
    return (t/tau)*np.exp(-t/np.maximum(tau,outward_tau_s))*ratio


@dataclass(frozen=True)
class GradedAPLState:
    voltage_components_mV: np.ndarray
    outward_current_pA: float


def advance_state(state, *, dt_s, input_current_pA, outward_target_pA,
                  resistance_MOhm, passive_tau_s, outward_tau_s):
    """Exact constant-input update; no Euler stability restriction.

    x_j' = (-x_j + R_j*(I-a)/1000)/tau_j
    a' = (a_target-a)/tau_a
    """
    x=np.asarray(state.voltage_components_mV,dtype=float)
    r=np.asarray(resistance_MOhm,dtype=float);tau=np.asarray(passive_tau_s,dtype=float)
    values=[dt_s,input_current_pA,outward_target_pA,state.outward_current_pA,outward_tau_s]
    if x.ndim!=1 or x.shape!=r.shape or x.shape!=tau.shape or not len(x):raise ValueError('Matching nonempty mode arrays required')
    if not np.isfinite(values).all() or dt_s<0 or outward_target_pA<0 or state.outward_current_pA<0 or outward_tau_s<=0:raise ValueError('Invalid current, time or outward state')
    if not np.isfinite(x).all() or not np.isfinite(r).all() or np.any(r<0) or not np.isfinite(tau).all() or np.any(tau<=0):raise ValueError('Finite modes with nonnegative resistance and positive tau required')
    e=np.exp(-dt_s/tau)
    driven=(input_current_pA-outward_target_pA)*(-np.expm1(-dt_s/tau))
    transient=(state.outward_current_pA-outward_target_pA)*decay_convolution(dt_s,tau,outward_tau_s)
    next_x=x*e+(r/1000)*(driven-transient)
    next_a=outward_target_pA+(state.outward_current_pA-outward_target_pA)*np.exp(-dt_s/outward_tau_s)
    return GradedAPLState(next_x,float(next_a))


def post_offset_voltage(time_s,initial_modes_mV,resistance_MOhm,passive_tau_s,
                        initial_outward_pA,outward_tau_s):
    """Zero-input recovery with outward target zero, relative to held baseline."""
    t=np.asarray(time_s,float)[:,None];tau=np.asarray(passive_tau_s,float)[None,:]
    return np.sum(np.asarray(initial_modes_mV)*np.exp(-t/tau)-
                  np.asarray(resistance_MOhm)/1000*initial_outward_pA*
                  decay_convolution(t,tau,outward_tau_s),axis=1)
