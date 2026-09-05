"""Scalar reference derived from the audited author recurrence, not physiology.

No dependency on or installation into fruitfly.neural. C and lateral drive must
remain fixed within each declared hold interval. Time is in seconds.
"""
import math


def source_step(state, drive, modulation, tau_s, dt_s):
    """The inspected discrete memory-gating equation at the requested step."""
    if not all(math.isfinite(x) for x in (state, drive, modulation, tau_s, dt_s)):
        raise ValueError('Finite scalar inputs required')
    if not (state >= 0 and drive >= 0 and 0 <= modulation <= 1 and 0 < dt_s < tau_s):
        raise ValueError('Requires nonnegative state/drive, m in [0,1], 0 < dt < tau')
    return modulation * ((1 - dt_s / tau_s) * state + dt_s / tau_s * drive)


def embedding(modulation, tau_s, reference_dt_s):
    """Return decay rate and equilibrium per unit drive for fixed 30-Hz law.

    q=m*(1-reference_dt/tau). Exact zero modulation has no finite-rate
    continuous embedding: the discrete map deletes arbitrary state at once.
    """
    if not all(math.isfinite(x) for x in (modulation, tau_s, reference_dt_s)):
        raise ValueError('Finite parameters required')
    if not (0 < modulation <= 1 and 0 < reference_dt_s < tau_s):
        raise ValueError('Finite embedding requires 0 < m <= 1 and 0 < reference_dt < tau')
    a = reference_dt_s / tau_s
    log_q = math.log(modulation) + math.log1p(-a)
    loss = -math.expm1(log_q)
    return -log_q / reference_dt_s, modulation * a / loss


def embedded_step(state, drive, modulation, tau_s, reference_dt_s, interval_s):
    """Exact held-input step of a declared embedding at any interval length.

    This preserves the *reference* recurrence, not a newly measured receptor
    ODE. Varying C/drive within the hold requires a separate convergence study.
    """
    if not all(math.isfinite(x) for x in (state, drive, interval_s)):
        raise ValueError('Finite state, drive and interval required')
    if state < 0 or drive < 0 or interval_s < 0:
        raise ValueError('Nonnegative state, drive and interval required')
    rate, gain = embedding(modulation, tau_s, reference_dt_s)
    loss = -math.expm1(-rate * interval_s)
    return state * (1 - loss) + drive * gain * loss
