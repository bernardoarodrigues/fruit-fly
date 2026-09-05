#!/usr/bin/env python3
"""Local KC waveform compatibility; no graph import or runtime parameter change.

The recorded event is effective, not one identified PN spike/contact. Decay
targets are conditionally interpreted as asymptotic constants; alternative
finite-window summaries are retained because the source fit window is absent.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from scipy.linalg import expm
from scipy.optimize import brentq
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive
from inhibitory_factorial_solver import hybrid_step, coefficients, NODES32, WEIGHTS32

BASE = ROOT / 'validation/kc-synaptic-response'
PLAN = BASE.with_name(BASE.name + '-plan.json')
RESULTS = BASE.with_name(BASE.name + '-results.json')
ARRAYS = BASE.with_name(BASE.name + '-arrays.npz')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def kernel(t, td, tr):
    t = np.asarray(t)
    return np.exp(-t / td) if tr == 0 else np.exp(-t / td) * (-np.expm1(-t * (1 / tr - 1 / td)))


def lowpass(t, tm, ts):
    t = np.asarray(t)
    if tm == ts:
        return t / tm * np.exp(-t / tm)
    return ts / (tm - ts) * (np.exp(-t / tm) - np.exp(-t / ts))


def voltage(t, tm, td, tr):
    return lowpass(t, tm, td) - (lowpass(t, tm, tr) if tr else 0.)


def waveform_metrics(fun, peak_time, late_tau):
    peak = float(fun(peak_time))
    rising = [0., 0.] if peak_time == 0 else [brentq(lambda t: float(fun(t)) / peak - f, 0., peak_time, xtol=1e-12) for f in (.1, .9)]
    falls = {str(f): brentq(lambda t: float(fun(t)) / peak - f, peak_time, peak_time + 30 * late_tau, xtol=1e-12) for f in (.9, .8, .5, .2, .1)}
    return dict(peak=peak, peak_time_ms=float(peak_time), rise_10_90_ms=float(rising[1] - rising[0]),
                rise_crossings_ms=rising, asymptotic_decay_ms=late_tau,
                fall_crossings_ms=falls, fall_80_20_equivalent_tau_ms=(falls['0.2'] - falls['0.8']) / np.log(4.),
                fall_50_10_equivalent_tau_ms=(falls['0.1'] - falls['0.5']) / np.log(5.))


def metrics(tm, td, tr):
    kt = 0. if tr == 0 else td * tr / (td - tr) * np.log(td / tr)
    vt = brentq(lambda t: float(kernel(t, td, tr) - voltage(t, tm, td, tr)), 1e-6, 20 * max(tm, td), xtol=1e-12)
    return dict(epsc=waveform_metrics(lambda t: kernel(t, td, tr), kt, td),
                epsp=waveform_metrics(lambda t: voltage(t, tm, td, tr), vt, max(tm, td)))


def prepare():
    if any(p.exists() for p in (PLAN, RESULTS, ARRAYS)):
        raise FileExistsError('Preserve prior attempt')
    sources = ['scripts/assay_kc_synaptic_response.py', 'fruitfly/neural.py',
               'scripts/inhibitory_factorial_solver.py', 'research/21-pn-kc-physiology-calibration.md',
               'docs/pn-kc-apl-inventory.md', 'data/raw/pn-kc-physiology/turner2008-author.pdf',
               'data/raw/pn-kc-physiology/turner2008-author.txt']
    write(PLAN, dict(schema=1, frozen_utc=datetime.now(timezone.utc).isoformat(),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_sha256={p: sha(ROOT / p) for p in sources},
        scope='Five deterministic isolated effective-event arms, all completed before analysis. No full network, graph event/claw mapping, APL, recurrent assay, motor tuning or default promotion.',
        already_seen='Source summary means and analytic preview 3.57559ms candidate rise have already been inspected. This is a prospective computational check, not blind validation.',
        targets=dict(epsc_rise_ms=.9, epsc_decay_ms=2.8, epsp_rise_ms=2.1, epsp_decay_ms=11.5, epsp_peak_mv=1.4,
                     source_holding_mv=-58., source_clamp_mv=-60., intrinsic_tau_strict_lower_bound_ms=200., input_resistance_strict_lower_bound_gohm=10., threshold_distance_mv=21.5),
        source='Turner et al. 2008 Fig3, female cohorts, not paired EPSP/EPSC cells; reported dispersion is not a confidence interval or hard cell bound.',
        equation='q=exp(-t/td)-exp(-t/tr); du/dt=(A*q-u)/tm. tr=0 denotes q=exp(-t/td). u is baseline-subtracted mV, A is effective equilibrium-voltage gain, not pA/nS/contact.',
        identification=dict(epsc='td=2.8 under asymptotic interpretation; Brent tr in [0.001,2.799] to match 10-90 rise0.9.',
            epsc_decay_anchored='tm=11.5 under asymptotic interpretation; predict EPSP rise.',
            epsc_rise_anchored='Same EPSC; Brent tm in [0.05,11.5] to match EPSP rise2.1; predict late decay.',
            intrinsic_boundary='Same EPSC; tm=200 is the lower boundary diagnostic, not an estimate or strict-bound pass.',
            amplitude='Each non-contact arm has continuous peak1.4mV by one linear gain. Control amplitude-only changes p0 but leaves tm20/td5/tr0.',
            current_contact='Native float32(0.275) nominal single-contact weight, not the measured spontaneous event.'),
        arm_ids=['current_contact', 'current_amplitude_only', 'epsc_decay_anchored', 'epsc_rise_anchored', 'intrinsic_boundary'],
        recording=dict(duration_ms=2000., timesteps_ms=[.1, .05, .025], primary_dt_ms=.1,
            event='State initialized just after one accepted postsynaptic event at t=0. No presynaptic train, delay queue or release model is inferred.',
            current_control='Unchanged LIFNetwork zero-edge 6-cell fixture: zero/contact/scaled event at native -52mV and held -58mV using constant current_mv=-6. Native thresholds/refractory retained; require no spikes/RNG changes.',
            h1_control='Actual hybrid_step with h=0, native rest, same three initial p values at dt0.1; compare native LIF samples. H1 inhibition is not exercised.',
            candidates='Exact matrix-exponential transitions, separate subthreshold testbed, no threshold/reset selection.',
            clamp='Normalized input-current proxy only. At fixed -60mV baseline, q/peak(q) represents inward current magnitude without pA calibration; no current feedback into clamped voltage.',
            intrinsic='Normalized -1mV asymptotic DC response and relaxation. No pA scale, no inferred Rin or capacitance.'),
        metrics=dict(primary='Continuous baseline-to-peak and 10-90 rising crossings; asymptotic late poles are conditional decay summaries.',
            secondary='Falling80-20 and50-10 equivalent exponential constants; descriptive, not a reproduction of unspecified source fitting windows.',
            sampling='Save all traces at each dt, compute sampled peak and interpolated rise, compare common times; exact integrators need not have monotonic roundoff.'),
        numerical_tolerances=dict(trace_atol_mv=1e-8, trace_rtol=1e-10, root_target_ms=1e-8,
            independent_ode_atol_mv=2e-8, common_time_atol_mv=1e-8, area_rtol=2e-4),
        conclusion_rule='Numerical validity is separate from conditional central-summary compatibility. No pass/fail biological tolerance from unspecified dispersion; retain signed mean residuals and strict intrinsic failure. Threshold, Rin, capacitance and contact gain unidentified.',
        held_out='Gruntman 2013 amplitudes and multi-claw responses excluded from parameter identification; already inspected, not blind. No new stochastic seed claim.',
        failure_policy='Do not overwrite frozen artifacts. Retain failures and any subsequent correction separately. No automatic parameter installation.',
        environment=dict(python=sys.version, numpy=np.__version__, scipy=version('scipy'), numba=version('numba'))))
    print(json.dumps(dict(plan=str(PLAN.relative_to(ROOT)), sha256=sha(PLAN))))


@njit(cache=True)
def propagate(transition, state, n):
    out = np.empty((n + 1, len(state)))
    out[0] = state
    for i in range(n):
        state = transition @ state
        out[i + 1] = state
    return out


@njit(cache=True)
def h1_trace(weights, n, a, b, c):
    vs = np.empty((n + 1, len(weights)))
    ps = np.empty_like(vs)
    vs[0] = -52.
    ps[0] = weights
    for i in range(n):
        for j in range(len(weights)):
            res = hybrid_step(vs[i,j], ps[i,j], 0., .1, a, b, c, NODES32, WEIGHTS32)
            vs[i+1,j], ps[i+1,j] = res[0], res[1]
    return vs, ps


def native_trace(dt, duration, weights):
    p = LIFParameters(dt_ms=dt)
    n = 6
    net = LIFNetwork(np.arange(n), np.zeros(n + 1, dtype=np.int64), np.empty(0, np.int32), np.empty(0, np.float32), parameters=p)
    initial_v = np.array([-52.] * 3 + [-58.] * 3)
    net.voltage_mv[:] = initial_v
    net.synaptic_mv[:] = np.tile(weights, 2)
    rng = net._rng_state.copy()
    drive = SparseDrive(np.arange(n), current_mv=[0.] * 3 + [-6.] * 3, disable_refractory=False)
    ticks = round(duration / dt)
    v = np.empty((ticks + 1, n)); s = np.empty_like(v)
    v[0], s[0] = net.voltage_mv, net.synaptic_mv
    spikes = 0
    for k in range(ticks):
        spikes += net.step(drive=drive, outputs=[]).total_spikes
        v[k+1], s[k+1] = net.voltage_mv, net.synaptic_mv
    return v, s, dict(spikes=spikes, rng_unchanged=bool(np.array_equal(rng, net._rng_state)),
                     pending_events=int(net._pending_count.sum()), refractory_ticks=net.refractory_ticks.tolist())


def sampled_metrics(t, y):
    i = int(np.argmax(y)); peak = float(y[i])
    if i == 0:
        rise = 0.
    else:
        crossings = np.interp(np.array([.1, .9]) * peak, y[:i+1], t[:i+1])
        rise = float(crossings[1] - crossings[0])
    return dict(peak=peak, peak_time_ms=float(t[i]), rise_10_90_ms=rise)


def run():
    if RESULTS.exists() or ARRAYS.exists():
        raise FileExistsError('Preserve prior results')
    plan = json.loads(PLAN.read_text())
    for p, digest in plan['source_sha256'].items():
        if sha(ROOT / p) != digest:
            raise ValueError('Source changed since freeze: ' + p)
    started = time.perf_counter()
    checks = {}; arrays = {}; arms = []; errors = []
    def ck(name, condition):
        checks[name] = bool(condition)
    def close(name, a, b, atol=1e-8):
        delta = float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
        ck(name, np.allclose(a, b, atol=atol, rtol=1e-10))
        return delta
    try:
        targets = plan['targets']
        td = targets['epsc_decay_ms']
        tr = brentq(lambda r: metrics(11.5, td, r)['epsc']['rise_10_90_ms'] - .9, .001, 2.799, xtol=1e-12)
        rise_tm = brentq(lambda m: metrics(m, td, tr)['epsp']['rise_10_90_ms'] - 2.1, .05, 11.5, xtol=1e-12)
        specs = [('current_contact', 20., 5., 0.), ('current_amplitude_only', 20., 5., 0.),
                 ('epsc_decay_anchored', 11.5, td, tr), ('epsc_rise_anchored', rise_tm, td, tr), ('intrinsic_boundary', 200., td, tr)]
        for name, tm, decay, rise in specs:
            mm = metrics(tm, decay, rise)
            gain = float(np.float32(.275)) if name == 'current_contact' else 1.4 / mm['epsp']['peak']
            mm['epsp']['peak'] *= gain
            arm = dict(id=name, tau_m_ms=tm, tau_decay_ms=decay, tau_rise_ms=rise, gain_effective_mv=gain, continuous=mm,
                mean_residuals=dict(epsp_peak_mv=mm['epsp']['peak']-1.4, epsp_rise_ms=mm['epsp']['rise_10_90_ms']-2.1,
                    epsp_asymptotic_decay_ms=mm['epsp']['asymptotic_decay_ms']-11.5,
                    epsc_rise_ms=mm['epsc']['rise_10_90_ms']-.9, epsc_asymptotic_decay_ms=decay-2.8),
                intrinsic=dict(tau_ms=tm, strict_gt200_satisfied=tm>200., resistance_gohm=None, capacitance_pf=None,
                    native_rest_to_threshold_mv=7. if name.startswith('current') else None,
                    held_to_native_threshold_mv=13. if name.startswith('current') else None,
                    threshold_fitted=False, note='No calibrated physical current unit; 200ms arm equals the boundary and does not satisfy strict >200.'))
            arms.append(arm)
        weights = np.array([0., arms[0]['gain_effective_mv'], arms[1]['gain_effective_mv']])
        records = {}
        for dt in plan['recording']['timesteps_ms']:
            tag = str(dt).replace('.', 'p')
            n = round(plan['recording']['duration_ms'] / dt)
            t = np.arange(n + 1) * dt
            arrays['time_ms_' + tag] = t
            v, p, native = native_trace(dt, t[-1], weights)
            arrays['native_v_' + tag] = v; arrays['native_p_' + tag] = p
            records[tag] = native
            ck('native_no_spikes_' + tag, native['spikes'] == 0)
            ck('native_rng_unchanged_' + tag, native['rng_unchanged'])
            ck('native_empty_pending_' + tag, native['pending_events'] == 0)
            close('held_zero_event_' + tag, v[:,3], -58.)
            close('native_zero_event_' + tag, v[:,0], -52.)
            close('holding_affine_' + tag, v[:,:3] - v[:,3:], 6.)
            for i, arm in enumerate(arms):
                name = arm['id']; tm = arm['tau_m_ms']; decay = arm['tau_decay_ms']; rise = arm['tau_rise_ms']; gain = arm['gain_effective_mv']
                if i < 2:
                    u = v[:,i+4] + 58.
                    q = p[:,i+4] / gain
                else:
                    matrix = np.array([[-1/tm,gain/tm,-gain/tm], [0.,-1/decay,0.], [0.,0.,-1/rise]])
                    state = propagate(expm(matrix * dt), np.array([0.,1.,1.]), n)
                    u = state[:,0]; q = state[:,1] - state[:,2]
                key = name + '_' + tag
                arrays[key + '_epsp_mv'] = u
                arrays[key + '_epsc_normalized'] = q / arm['continuous']['epsc']['peak']
                arrays[key + '_intrinsic_step_mv'] = -np.expm1(-t / tm) * -1.
                arrays[key + '_intrinsic_relaxation_mv'] = -np.exp(-t / tm)
                delta = close('closed_form_voltage_' + key, u, gain * voltage(t, tm, decay, rise))
                close('closed_form_current_' + key, q, kernel(t, decay, rise))
                ck('finite_nonnegative_response_' + key, np.isfinite(u).all() and u.min() >= -1e-10 and np.isfinite(q).all() and q.min() >= -1e-10)
                expected_area = gain * (decay - rise)
                area = float(np.trapezoid(u, t))
                ck('response_area_' + key, abs(area/expected_area - 1.) < plan['numerical_tolerances']['area_rtol'])
                arm.setdefault('sampled', {})[tag] = dict(epsp=sampled_metrics(t,u), epsc=sampled_metrics(t, arrays[key+'_epsc_normalized']),
                    max_closed_form_error_mv=delta, epsp_area_mv_ms=area, infinite_expected_area_mv_ms=expected_area)
                if dt != .1:
                    step = round(.1 / dt)
                    close('common_times_' + key, u[::step], arrays[name + '_0p1_epsp_mv'])
        hv, hp = h1_trace(weights, round(plan['recording']['duration_ms']/.1), *coefficients(.1))
        arrays['h1_v_0p1'], arrays['h1_p_0p1'] = hv, hp
        close('h1_excitation_voltage_vs_native', hv, arrays['native_v_0p1'][:,:3])
        close('h1_excitation_current_vs_native', hp, arrays['native_p_0p1'][:,:3])
        # Equal-pole limit and zero-event input are manufactured numerical cases.
        fixture_t = np.linspace(0,100,1001)
        for tau in (2.8,20.,200.):
            mat = np.array([[-1/tau,1/tau],[0.,-1/tau]])
            ss = propagate(expm(mat*.1), np.array([0.,1.]),1000)
            close('equal_pole_' + str(tau), ss[:,0], lowpass(fixture_t,tau,tau))
            arrays['equal_pole_'+str(tau)] = ss
        ck('epsc_root', abs(arms[2]['mean_residuals']['epsc_rise_ms']) < 1e-8)
        ck('epsp_rise_root', abs(arms[3]['mean_residuals']['epsp_rise_ms']) < 1e-8)
        ck('all_planned_arms', [a['id'] for a in arms] == plan['arm_ids'])
        ck('all_sources_unchanged', all(sha(ROOT/p) == digest for p,digest in plan['source_sha256'].items()))
    except (Exception, KeyboardInterrupt) as exc:
        import traceback
        errors.append(dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
    np.savez_compressed(ARRAYS, **arrays)
    passed = bool(checks) and all(checks.values()) and not errors
    write(RESULTS, dict(schema=1, completed_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter()-started,
        plan_sha256=sha(PLAN), arrays_sha256=sha(ARRAYS), passed=passed, numerical_passed=passed,
        biological_validation=False, defaults_changed=False, h1_promoted=False, complete_batch_analyzed=passed,
        checks=checks, check_count=len(checks), errors=errors, arms=arms,
        native_records=locals().get('records', {}),
        limits=plan['conclusion_rule']))
    print(json.dumps(dict(passed=passed, checks=len(checks), errors=errors, results=str(RESULTS.relative_to(ROOT)), wall_seconds=time.perf_counter()-started)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare','run'])
    args = parser.parse_args()
    prepare() if args.command == 'prepare' else run()
