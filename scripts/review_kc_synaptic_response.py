#!/usr/bin/env python3
"""Independent saved-trace KC assay review, without producer or neural imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np
import scipy
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation/kc-synaptic-response'
PLAN = Path(str(BASE) + '-plan.json')
RESULT = Path(str(BASE) + '-results.json')
ARRAY = Path(str(BASE) + '-arrays.npz')
OUTPUT = Path(str(BASE) + '-independent-review.json')
PLAN_SHA = '1c0da89f8c897710306c9657bc0103a90ce406b053341d8e76cf24b6ac48f51a'
RESULT_SHA = '809216ec1d3b5e7072d3d24a6a7e367f13ff5a6dd1e4b9a4241fb07866cf0a82'
ARMS = ['current_contact', 'current_amplitude_only', 'epsc_decay_anchored',
        'epsc_rise_anchored', 'intrinsic_boundary']


def load(p):
    return json.loads(Path(p).read_text())


def record(p):
    p = Path(p).resolve()
    digest = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            digest.update(block)
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=digest.hexdigest())


def ode(tm, td, tr, gain, end):
    """Three independent ODE states: EPSP and two signed-current components."""
    def rhs(t, y):
        return [(y[1] - y[2] - y[0]) / tm, -y[1] / td,
                -y[2] / tr if tr else 0.]
    value = solve_ivp(rhs, [0., end], [0., gain, gain if tr else 0.],
                      method='DOP853', rtol=3e-13, atol=3e-14, dense_output=True)
    if not value.success or value.t[-1] != end:
        raise RuntimeError('Independent ODE failed: ' + value.message)
    return value


def continuous_metrics(solution, tm, td, tr, gain, end):
    def p(t):
        y = solution.sol(t)
        return float(y[1] - y[2]) / gain
    def pprime(t):
        y = solution.sol(t)
        return float(-y[1] / td + (y[2] / tr if tr else 0.)) / gain
    def u(t):
        return float(solution.sol(t)[0])
    def uprime(t):
        y = solution.sol(t)
        return float(y[1] - y[2] - y[0]) / tm
    pk = 0. if tr == 0. else brentq(pprime, 0., min(end, 20. * max(td, tr)), xtol=1e-12)
    vk = brentq(uprime, 1e-6, min(end, 20. * max(tm, td)), xtol=1e-12)
    def summary(fun, peak_time, late):
        peak = fun(peak_time)
        rise = [0., 0.] if peak_time == 0. else [brentq(lambda t: fun(t) - f * peak, 0., peak_time, xtol=1e-12) for f in [.1, .9]]
        fall = {str(f): brentq(lambda t: fun(t) - f * peak, peak_time, min(end, peak_time + 30. * late), xtol=1e-12)
                for f in [.9, .8, .5, .2, .1]}
        return dict(peak=peak, peak_time_ms=peak_time, rise_10_90_ms=rise[1] - rise[0], rise_crossings_ms=rise,
                    asymptotic_decay_ms=late, fall_crossings_ms=fall,
                    fall_80_20_equivalent_tau_ms=(fall['0.2'] - fall['0.8']) / np.log(4.),
                    fall_50_10_equivalent_tau_ms=(fall['0.1'] - fall['0.5']) / np.log(5.))
    return dict(epsc=summary(p, pk, td), epsp=summary(u, vk, max(tm, td)))


def sampled(t, values):
    peak_index = int(np.argmax(values))
    peak = float(values[peak_index])
    crossings = []
    if peak_index:
        for fraction in [.1, .9]:
            level = fraction * peak
            right = int(np.flatnonzero(values[:peak_index + 1] >= level)[0])
            left = right - 1
            crossings.append(float(t[left] + (level - values[left]) * (t[right] - t[left]) / (values[right] - values[left])))
    return dict(peak=peak, peak_time_ms=float(t[peak_index]),
                rise_10_90_ms=crossings[1] - crossings[0] if crossings else 0.)


def analytic_lowpass(t, tm, ts):
    """Stable integrating-factor divided difference, including equal poles."""
    t = np.asarray(t)
    rate = 1. / ts - 1. / tm
    if rate == 0.:
        return (t / tm) * np.exp(-t / tm)
    # Avoid overflow if the synaptic pole is slower than the membrane pole.
    if rate > 0.:
        return np.exp(-t / tm) * (-np.expm1(-t * rate)) / (tm * rate)
    return np.exp(-t / ts) * np.expm1(t * rate) / (tm * rate)


def fixture():
    t = np.linspace(0., 100., 1001)
    equal = ode(5., 5., 0., 1., 100.)
    y = equal.sol(t)
    assert np.max(np.abs(y[0] - t / 5. * np.exp(-t / 5.))) < 2e-10
    assert np.max(np.abs(y[1] - np.exp(-t / 5.))) < 2e-10
    assert np.array_equal(analytic_lowpass(t, 5., 5.), t / 5. * np.exp(-t / 5.))
    ramp = sampled(np.array([0., 1., 2., 3.]), np.array([0., .5, 1., .25]))
    assert abs(ramp['rise_10_90_ms'] - 1.6) < 1e-14
    return dict(passed=True, checks=4, scope='Independent ODE equal-pole limit, current exponential, stable divided difference, and manufactured sampled crossing interpolation.')


def run():
    if OUTPUT.exists():
        raise FileExistsError('Preserve first independent review receipt')
    start = time.perf_counter()
    categories, maxima, failures, completed, refs = {}, {}, [], [], []
    source_start, source_end = [], []
    context, error, exact_h1 = 'preflight', None, None
    pure = fixture()
    def ck(name, ok, detail=None):
        row = categories.setdefault(name, dict(checked=0, passed=0))
        row['checked'] += 1
        row['passed'] += int(bool(ok))
        if not ok:
            failures.append(dict(check=name, context=context, detail=detail))
            raise AssertionError(name + ': ' + str(detail or context))
    def close(name, actual, expected, atol=2e-8, rtol=1e-10):
        actual, expected = np.asarray(actual), np.asarray(expected)
        ck(name + '_shape', actual.shape == expected.shape)
        delta = float(np.max(np.abs(actual - expected), initial=0.))
        maxima[name] = max(maxima.get(name, 0.), delta)
        ck(name, np.isfinite(actual).all() and np.isfinite(expected).all() and np.allclose(actual, expected, atol=atol, rtol=rtol))
        return delta
    def tree(name, actual, expected, atol=2e-8):
        if isinstance(expected, dict):
            ck(name + '_keys', isinstance(actual, dict) and actual.keys() == expected.keys())
            for k in expected:
                tree(name, actual[k], expected[k], atol)
        elif isinstance(expected, list):
            ck(name + '_length', len(actual) == len(expected))
            for a, b in zip(actual, expected):
                tree(name, a, b, atol)
        else:
            close(name, actual, expected, atol=atol)
    try:
        plan, result = load(PLAN), load(RESULT)
        ck('frozen_plan', record(PLAN)['sha256'] == PLAN_SHA)
        ck('completed_result', record(RESULT)['sha256'] == RESULT_SHA and result['passed'] and result['numerical_passed']
           and result['complete_batch_analyzed'] and not result['errors'] and all(result['checks'].values()))
        ck('result_links', result['plan_sha256'] == PLAN_SHA and result['arrays_sha256'] == record(ARRAY)['sha256'])
        ck('no_biological_promotion', not result['biological_validation'] and not result['defaults_changed'] and not result['h1_promoted'])
        paths = [Path(__file__), PLAN, RESULT, ARRAY] + [ROOT / p for p in plan['source_sha256']]
        source_start = [record(p) for p in dict.fromkeys(paths)]
        pinned = {r['path']: r for r in source_start}
        for p, digest in plan['source_sha256'].items():
            ck('all_source_pins', pinned[p]['sha256'] == digest, p)
        ck('five_arm_schema', [a['id'] for a in result['arms']] == plan['arm_ids'] == ARMS)
        ck('fixed_recording_grid', plan['recording']['duration_ms'] == 2000. and plan['recording']['timesteps_ms'] == [.1, .05, .025])
        end = 2000.
        arms = result['arms']
        ck('control_parameters', all(a['tau_m_ms'] == 20. and a['tau_decay_ms'] == 5. and a['tau_rise_ms'] == 0. for a in arms[:2])
           and arms[0]['gain_effective_mv'] == float(np.float32(.275)))
        ck('declared_identification', all(a['tau_decay_ms'] == 2.8 and .001 < a['tau_rise_ms'] < 2.799 for a in arms[2:])
           and len({a['tau_rise_ms'] for a in arms[2:]}) == 1 and arms[2]['tau_m_ms'] == 11.5
           and .05 < arms[3]['tau_m_ms'] < 11.5 and arms[4]['tau_m_ms'] == 200.)
        all_times = {}
        with np.load(ARRAY, allow_pickle=False) as saved:
            seen = set()
            def array(key, shape):
                a = saved[key]
                seen.add(key)
                ck('array_shape_dtype_finite', a.shape == shape and a.dtype == np.float64 and np.isfinite(a).all(), key)
                return a
            for dt in [.1, .05, .025]:
                tag = str(dt).replace('.', 'p')
                t = array('time_ms_' + tag, (round(end / dt) + 1,))
                ck('exact_time_grid', np.array_equal(t, np.arange(len(t)) * dt))
                all_times[tag] = t
                v = array('native_v_' + tag, (len(t), 6))
                p = array('native_p_' + tag, (len(t), 6))
                weights = np.array([0., arms[0]['gain_effective_mv'], arms[1]['gain_effective_mv']])
                u = analytic_lowpass(t, 20., 5.)[:, None] * weights
                expected_p = np.exp(-t[:, None] / 5.) * weights
                close('native_closed_form', v, np.column_stack((-52. + u, -58. + u)), atol=1e-8)
                close('native_p_closed_form', p, np.tile(expected_p, (1, 2)), atol=1e-8)
                ck('post_event_initial_state', np.array_equal(v[0], [-52., -52., -52., -58., -58., -58.])
                   and np.array_equal(p[0], np.tile(weights, 2)))
                ck('first_interval_response', v[1, 1] > v[0, 1] and v[1, 2] > v[0, 2] and v[1, 4] > v[0, 4] and v[1, 5] > v[0, 5])
                close('zero_native_hold', v[:, 0], np.full(len(t), -52.), atol=1e-8)
                close('zero_source_hold', v[:, 3], np.full(len(t), -58.), atol=1e-8)
                close('holding_affine', v[:, :3] - v[:, 3:], np.full((len(t), 3), 6.), atol=1e-8)
                ck('zero_event_p', not p[:, [0, 3]].any())
                ck('native_subthreshold', np.max(v) < -45.)
                metadata = result['native_records'][tag]
                ck('native_reported_counters', metadata['spikes'] == 0 and metadata['rng_unchanged'] and metadata['pending_events'] == 0
                   and metadata['refractory_ticks'] == [round(2.2 / dt)] * 6)
            for i, arm in enumerate(arms):
                context = arm['id']
                tm, td, tr, gain = (arm[k] for k in ['tau_m_ms', 'tau_decay_ms', 'tau_rise_ms', 'gain_effective_mv'])
                ck('positive_parameters', tm > 0. and td > tr >= 0. and gain > 0.)
                solution = ode(tm, td, tr, gain, end)
                ref = continuous_metrics(solution, tm, td, tr, gain, end)
                tree('continuous_ODE_metric', arm['continuous'], ref)
                residual = dict(epsp_peak_mv=ref['epsp']['peak'] - 1.4, epsp_rise_ms=ref['epsp']['rise_10_90_ms'] - 2.1,
                                epsp_asymptotic_decay_ms=max(tm, td) - 11.5, epsc_rise_ms=ref['epsc']['rise_10_90_ms'] - .9,
                                epsc_asymptotic_decay_ms=td - 2.8)
                tree('signed_mean_residuals', arm['mean_residuals'], residual)
                if i:
                    close('amplitude_identification', ref['epsp']['peak'], 1.4, atol=1e-8)
                if i >= 2:
                    close('current_rise_identification', ref['epsc']['rise_10_90_ms'], .9, atol=1e-8)
                if i == 3:
                    close('voltage_rise_identification', ref['epsp']['rise_10_90_ms'], 2.1, atol=1e-8)
                intrinsic = arm['intrinsic']
                ck('intrinsic_no_fit_claim', intrinsic['tau_ms'] == tm and intrinsic['strict_gt200_satisfied'] == (tm > 200.)
                   and not intrinsic['threshold_fitted'] and intrinsic['resistance_gohm'] is None and intrinsic['capacitance_pf'] is None
                   and intrinsic['native_rest_to_threshold_mv'] == (7. if i < 2 else None)
                   and intrinsic['held_to_native_threshold_mv'] == (13. if i < 2 else None))
                ck('intrinsic_strict_bound_not_met', not intrinsic['strict_gt200_satisfied'])
                area_infinite = gain * (td - tr)
                area_input_finite = gain * (td * (-np.expm1(-end / td)) - tr * (-np.expm1(-end / tr)) if tr else td * (-np.expm1(-end / td)))
                area_voltage_finite = area_input_finite - tm * float(solution.sol(end)[0])
                row = dict(id=arm['id'], ode_method='DOP853', ode_rtol=3e-13, ode_atol=3e-14, nfev=solution.nfev,
                           continuous=ref, signed_mean_residuals=residual, finite_EPSP_area_mv_ms=area_voltage_finite,
                           infinite_EPSP_area_mv_ms=area_infinite, unobserved_tail_area_mv_ms=area_infinite - area_voltage_finite, grids=[])
                for dt in [.1, .05, .025]:
                    tag = str(dt).replace('.', 'p')
                    t = all_times[tag]
                    key = arm['id'] + '_' + tag
                    u = array(key + '_epsp_mv', t.shape)
                    current = array(key + '_epsc_normalized', t.shape)
                    step = array(key + '_intrinsic_step_mv', t.shape)
                    relax = array(key + '_intrinsic_relaxation_mv', t.shape)
                    reference = solution.sol(t)
                    normalized = (reference[1] - reference[2]) / gain / ref['epsc']['peak']
                    e_u = close('all_saved_EPSP_vs_ODE', u, reference[0])
                    e_c = close('all_saved_clamp_vs_ODE', current, normalized)
                    analytic = gain * (analytic_lowpass(t, tm, td) - (analytic_lowpass(t, tm, tr) if tr else 0.))
                    close('independent_closed_form_vs_ODE', analytic, reference[0])
                    closed_error = close('saved_vs_independent_closed_form', u, analytic, atol=1e-8)
                    close('intrinsic_step_trace', step, np.exp(-t / tm) - 1., atol=1e-10)
                    close('intrinsic_relaxation_trace', relax, -np.exp(-t / tm), atol=1e-10)
                    tree('sampled_EPSP_metrics', arm['sampled'][tag]['epsp'], sampled(t, u), atol=1e-10)
                    tree('sampled_EPSC_metrics', arm['sampled'][tag]['epsc'], sampled(t, current), atol=1e-10)
                    close('reported_closed_form_max', arm['sampled'][tag]['max_closed_form_error_mv'], closed_error, atol=1e-10)
                    measured_area = float(np.trapezoid(u, t))
                    close('reported_sampled_area', arm['sampled'][tag]['epsp_area_mv_ms'], measured_area, atol=1e-10)
                    close('reported_infinite_area', arm['sampled'][tag]['infinite_expected_area_mv_ms'], area_infinite, atol=1e-10)
                    ck('finite_voltage_area', abs(measured_area / area_voltage_finite - 1.) < plan['numerical_tolerances']['area_rtol'])
                    ck('declared_infinite_area_gate', abs(measured_area / area_infinite - 1.) < plan['numerical_tolerances']['area_rtol'])
                    # Exact trapezoidal sum for finite sampled exponentials, so
                    # fast onset quadrature error is not confused with dynamics.
                    def trap_exponential(tau):
                        return .5 * dt / np.tanh(dt / (2. * tau)) * (-np.expm1(-end / tau))
                    current_trap = (trap_exponential(td) - (trap_exponential(tr) if tr else 0.)) / ref['epsc']['peak']
                    close('normalized_current_discrete_area', np.trapezoid(current, t), current_trap, atol=2e-8)
                    ck('current_initial_condition', current[0] == (1. if tr == 0. else 0.))
                    ck('voltage_initial_condition', u[0] == 0.)
                    if dt != .1:
                        stride = round(.1 / dt)
                        close('common_time_voltage', u[::stride], saved[arm['id'] + '_0p1_epsp_mv'], atol=1e-8)
                        close('common_time_current', current[::stride], saved[arm['id'] + '_0p1_epsc_normalized'], atol=1e-8)
                    if i < 2:
                        ck('native_trace_extract', np.array_equal(u, saved['native_v_' + tag][:, i + 4] + 58.)
                           and np.array_equal(current, saved['native_p_' + tag][:, i + 4] / gain))
                    row['grids'].append(dict(dt_ms=dt, samples=len(t), max_ODE_EPSP_error_mv=e_u,
                        max_ODE_normalized_current_error=e_c, sampled_peak_gap_mv=ref['epsp']['peak'] - float(np.max(u))))
                refs.append(row)
                completed.append(arm['id'])
            context = 'H1 and equal-pole controls'
            hv = array('h1_v_0p1', (len(all_times['0p1']), 3))
            hp = array('h1_p_0p1', hv.shape)
            close('H1_native_voltage', hv, saved['native_v_0p1'][:, :3], atol=1e-8)
            close('H1_native_current', hp, saved['native_p_0p1'][:, :3], atol=1e-8)
            exact_h1 = dict(voltage=hv.tobytes() == saved['native_v_0p1'][:, :3].tobytes(),
                            current=hp.tobytes() == saved['native_p_0p1'][:, :3].tobytes())
            for tau in [2.8, 20., 200.]:
                eq = array('equal_pole_' + str(tau), (1001, 2))
                t = np.arange(1001) * .1
                close('equal_pole_analytic', eq, np.column_stack((t / tau * np.exp(-t / tau), np.exp(-t / tau))), atol=1e-8)
                sol = ode(tau, tau, 0., 1., 100.)
                close('equal_pole_independent_ODE', eq, sol.sol(t)[:2].T)
            ck('all_saved_arrays_reviewed', seen == set(saved.files), sorted(set(saved.files) - seen))
        source_end = [record(ROOT / r['path']) for r in source_start]
        ck('all_inputs_unchanged', source_end == source_start)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), context=context, traceback=traceback.format_exc())
    review = dict(schema=1, passed=error is None and not failures and completed == ARMS,
        completed_utc=datetime.now(timezone.utc).isoformat(), source_start=source_start, source_end=source_end,
        preflight=pure, completed_arms=completed, check_count=sum(x['checked'] for x in categories.values()),
        categories=categories, failures=failures, error=error, numerical_max_abs_differences=maxima,
        references=refs, H1_native_bitwise_observation=exact_h1,
        environment=dict(numpy=np.__version__, scipy=scipy.__version__), wall_seconds=time.perf_counter() - start,
        biological_validation=False, scope='All five completed arms, all three saved timesteps, six native cells, actual H1 h=0 traces and equal-pole fixtures. Independent time-domain ODE and dense-output/root metrics; closed-form, exact area, holding and sampled-grid checks. No producer/kernel import, parameter fitting or neural simulation.',
        limits=['The event is an effective postsynaptic initial state; the assay contains no presynaptic emission, delayed queue, release probability or graph-contact-to-event calibration.',
                'Native no-spike evidence includes all voltage samples and analytic subthreshold solutions. RNG/pending counts are producer counters corroborated by source inspection; raw RNG endpoint/state snapshots are not retained.',
                'EPSC normalization discards absolute current amplitude. No pA/nS, input resistance or capacitance is identified.',
                'Asymptotic poles and descriptive falling-window constants are distinct; the primary fitted decay window is unavailable.',
                'Reported source dispersions are not confidence intervals. Numerical pass does not imply physiological acceptance, same-cell compatibility or male-VM7d calibration.',
                'None of these five arms satisfies the strict >200ms intrinsic condition. Threshold/APL/spike sparseness were excluded from identification and remain uncalibrated.'])
    with OUTPUT.open('x') as f:
        json.dump(review, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(passed=review['passed'], checks=review['check_count'], completed=completed,
                         receipt=record(OUTPUT), error=error, maxima=maxima)))
    return 0 if review['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['fixture', 'run'])
    if parser.parse_args().command == 'fixture':
        print(json.dumps(fixture()))
    else:
        raise SystemExit(run())
