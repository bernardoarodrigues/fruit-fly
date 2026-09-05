"""Unit-explicit measurements for declared APL current-clamp windows.

Callers must establish file identity, correction state, commands, windows and
quality thresholds before applying these to biological data. No cohort parser,
automatic exclusion rule or physiological model default is supplied here.
"""
import numpy as np
from scipy.optimize import minimize_scalar


def _record(time_s,*channels):
    t=np.asarray(time_s,float)
    if t.ndim!=1 or len(t)<3 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('Finite strictly increasing time in seconds required')
    values=[np.asarray(x,float) for x in channels]
    if any(x.shape!=t.shape or not np.isfinite(x).all() for x in values):
        raise ValueError('Finite channels must match time')
    return (t,*values)


def _window(t,window):
    a,b=map(float,window)
    if not np.isfinite([a,b]).all() or not t[0]<=a<b<=t[-1]:
        raise ValueError('Declared half-open window must lie within recording')
    mask=(t>=a)&(t<b)
    if mask.sum()<2:raise ValueError('At least two samples required per window')
    return mask


def passive_resistance(time_s,voltage_mV,current_pA,*,baseline_window_s,
                       plateau_window_s,minimum_current_step_pA):
    """Empirical steady-state delta-V/delta-I; return MOhm, not GOhm.

    The holding command cancels in the difference. The measured held baseline
    is not relabeled as resting potential. Negative resistance is retained and
    flagged, not hidden by absolute values.
    """
    t,v,i=_record(time_s,voltage_mV,current_pA)
    if not np.isfinite(minimum_current_step_pA) or minimum_current_step_pA<0:
        raise ValueError('Nonnegative explicit current floor required')
    b=_window(t,baseline_window_s);p=_window(t,plateau_window_s)
    if baseline_window_s[1]>plateau_window_s[0]:raise ValueError('Baseline precedes plateau')
    dv=float(v[p].mean()-v[b].mean());di=float(i[p].mean()-i[b].mean())
    identifiable=abs(di)>minimum_current_step_pA
    resistance=1000*dv/di if identifiable else None
    return dict(status='measured' if identifiable else 'insufficient_current_step',
        held_baseline_mV=float(v[b].mean()),baseline_voltage_sd_mV=float(v[b].std(ddof=1)),
        baseline_current_pA=float(i[b].mean()),plateau_current_pA=float(i[p].mean()),
        plateau_current_sd_pA=float(i[p].std(ddof=1)),delta_voltage_mV=dv,delta_current_pA=di,
        resistance_MOhm=resistance,nonpositive_resistance=bool(resistance<=0) if identifiable else None,
        baseline_samples=int(b.sum()),plateau_samples=int(p.sum()))


def fit_step_exponential(time_s,voltage_mV,*,onset_s,fit_window_s,tau_bounds_s,
                         minimum_voltage_span_mV):
    """Fit V_inf + B exp(-(t-onset)/tau) in an explicit transient window.

    Profile the two linear coefficients over tau, including both boundaries.
    This is a descriptive single-exponential fit, not a cable-capacitance model.
    """
    t,v=_record(time_s,voltage_mV)
    if not np.isfinite(onset_s) or fit_window_s[0]<onset_s:raise ValueError('Fit begins after declared onset')
    lower,upper=map(float,tau_bounds_s)
    if not np.isfinite([lower,upper,minimum_voltage_span_mV]).all() or not 0<lower<upper or minimum_voltage_span_mV<0:
        raise ValueError('Positive finite tau bounds and nonnegative voltage floor required')
    mask=_window(t,fit_window_s);x=t[mask]-onset_s;y=v[mask]
    if len(x)<4:raise ValueError('At least four fit samples required')
    span=float(np.ptp(y))
    if span<=minimum_voltage_span_mV:
        return dict(status='insufficient_voltage_span',voltage_span_mV=span,tau_s=None,samples=len(x))
    def profile(tau):
        matrix=np.column_stack([np.ones(len(x)),np.exp(-x/tau)])
        co,_,rank,singular=np.linalg.lstsq(matrix,y,rcond=None)
        residual=matrix@co-y
        return float(np.mean(residual**2)),co,rank,singular
    grid=np.geomspace(lower,upper,81);scores=np.array([profile(z)[0] for z in grid]);candidates=list(zip(scores,grid))
    for j in range(1,len(grid)-1):
        if scores[j]<=scores[j-1] and scores[j]<=scores[j+1]:
            opt=minimize_scalar(lambda z:profile(np.exp(z))[0],bounds=np.log(grid[[j-1,j+1]]),method='bounded',options={'xatol':1e-10})
            if not opt.success:raise RuntimeError('Exponential fit did not converge')
            candidates.append((opt.fun,float(np.exp(opt.x))))
    _,tau=min(candidates);mse,co,rank,singular=profile(tau)
    condition=float(singular[0]/singular[-1]) if singular[-1]>0 else None
    return dict(status='fitted',tau_s=float(tau),asymptote_mV=float(co[0]),extrapolated_onset_mV=float(co.sum()),
        exponential_coefficient_mV=float(co[1]),rmse_mV=float(np.sqrt(mse)),samples=len(x),voltage_span_mV=span,
        at_tau_bound=bool(tau==lower or tau==upper),linear_design_rank=int(rank),linear_condition_number=condition,
        interpretation='Descriptive fit only; identifiability and physiological acceptance require separate checks')


def _crossings(t,relative,target):
    delta=relative-target
    down=np.flatnonzero((delta[:-1]>0)&(delta[1:]<=0))
    up=np.flatnonzero((delta[:-1]<=0)&(delta[1:]>0))
    def interpolate(indices):
        return [float(t[k]+(t[k+1]-t[k])*delta[k]/(delta[k]-delta[k+1])) for k in indices]
    return interpolate(down),interpolate(up)


def ahp_recovery(time_s,voltage_mV,*,baseline_window_s,post_offset_window_s,
                 minimum_amplitude_mV):
    """Measure AHP magnitude and first 70%-to-30% recovery crossings.

    Preserve all recrossings and missing crossings. No smoothing, forced
    exponential, or source-independent low-amplitude threshold is inserted.
    """
    t,v=_record(time_s,voltage_mV)
    if not np.isfinite(minimum_amplitude_mV) or minimum_amplitude_mV<0:raise ValueError('Nonnegative explicit amplitude floor required')
    baseline=_window(t,baseline_window_s);post=_window(t,post_offset_window_s)
    if baseline_window_s[1]>post_offset_window_s[0]:raise ValueError('Baseline precedes post-offset window')
    reference=float(v[baseline].mean());idx=np.flatnonzero(post);peak=idx[np.argmin(v[idx])]
    magnitude=reference-float(v[peak]);tail=idx[idx>=peak]
    result=dict(held_baseline_mV=reference,baseline_sd_mV=float(v[baseline].std(ddof=1)),
        minimum_voltage_mV=float(v[peak]),peak_time_s=float(t[peak]),signed_deflection_mV=-magnitude,
        amplitude_mV=magnitude,minimum_amplitude_mV=float(minimum_amplitude_mV),minimum_sample_count=int(np.sum(v[idx]==v[peak])),
        recovery_70_to_30_s=None)
    if magnitude<=minimum_amplitude_mV:
        return dict(result,status='insufficient_ahp_amplitude',crossings=None)
    relative=(reference-v[tail])/magnitude
    d70,u70=_crossings(t[tail],relative,.7);d30,u30=_crossings(t[tail],relative,.3)
    result['crossings']=dict(down_70_s=d70,up_70_s=u70,down_30_s=d30,up_30_s=u30)
    if not d70 or not d30:
        return dict(result,status='incomplete_recovery_window')
    t70=d70[0];after=[z for z in d30 if z>=t70]
    if not after:return dict(result,status='inconsistent_crossing_order')
    ambiguous=len(d70)>1 or len(d30)>1 or bool(u70) or bool(u30)
    result['recovery_70_to_30_s']=after[0]-t70
    return dict(result,status='ambiguous_recrossings' if ambiguous else 'measured',
                first_70_s=t70,first_30_s=after[0])
