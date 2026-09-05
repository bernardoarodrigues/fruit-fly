#!/usr/bin/env python3
"""Independent saved-data review; no producer, runtime, or helper imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation/turner-kc-conductance'
OUTPUT = ROOT / 'validation/turner-kc-conductance-independent-review.json'

# Printed model settings, Turner 2008 p.736, not imported from the producer.
CM_UF_CM2 = 1.
GL_MS_CM2 = .089
EL_MV = -57.8
ESYN_MV = 0.
ALPHA_PER_MS = 2.5
BETA_PER_MS = .4
WIDTH_MS = .3
CLAMP_MV = -60.


def record(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def gate(t, transmitter):
    """Independent piecewise closed form of dO/dt=alpha*T*(1-O)-beta*O."""
    t = np.asarray(t, dtype=np.float64)
    rate = ALPHA_PER_MS * transmitter + BETA_PER_MS
    equilibrium = ALPHA_PER_MS * transmitter / rate
    during = equilibrium * -np.expm1(-rate * np.minimum(np.maximum(t, 0), WIDTH_MS))
    return during * np.exp(-BETA_PER_MS * np.maximum(t - WIDTH_MS, 0))


def voltage_reference(gbar, transmitter, end_ms):
    """Integrate only u=V-EL; the gate is analytic, not a second ODE state.

    Radau with exact scalar Jacobian, explicitly split at the transmitter edge.
    mS/cm² divided by µF/cm² gives ms⁻¹ when time is in milliseconds.
    """
    def rhs(t, y):
        gs = gbar * float(gate(t, transmitter))
        return np.array([(-(GL_MS_CM2 + gs) * y[0] + gs * (ESYN_MV - EL_MV)) / CM_UF_CM2])

    def jac(t, y):
        return np.array([[-(GL_MS_CM2 + gbar * float(gate(t, transmitter))) / CM_UF_CM2]])

    kwargs = dict(method='Radau', rtol=2e-12, atol=2e-13, dense_output=True, jac=jac)
    first = solve_ivp(rhs, (0., WIDTH_MS), [0.], max_step=.01, **kwargs)
    second = solve_ivp(rhs, (WIDTH_MS, end_ms), first.y[:, -1], max_step=.5, **kwargs)
    if not first.success or not second.success:
        raise RuntimeError('Independent Radau failure: ' + first.message + '; ' + second.message)

    def u(t):
        a = np.asarray(t, dtype=np.float64)
        values = np.empty(a.shape)
        before = a <= WIDTH_MS
        if np.any(before):
            values[before] = first.sol(a[before])[0]
        if np.any(~before):
            values[~before] = second.sol(a[~before])[0]
        return values

    return u, rhs, dict(method='scalar Radau with closed-form gate',
                       nfev=first.nfev + second.nfev, njev=first.njev + second.njev,
                       rtol=kwargs['rtol'], atol=kwargs['atol'], split_ms=WIDTH_MS)


def epsp_metrics(u, rhs, end_ms):
    peak_t = brentq(lambda t: float(rhs(t, [float(u(t))])[0]), WIDTH_MS, 50., xtol=2e-12)
    peak = float(u(peak_t))
    rising = [brentq(lambda t: float(u(t)) - fraction * peak, 0., peak_t, xtol=2e-12)
              for fraction in (.1, .9)]
    fall_t = brentq(lambda t: float(u(t)) - peak / np.e, peak_t, end_ms, xtol=2e-12)
    return dict(peak_mv=peak, peak_time_ms=peak_t, rise_10_90_ms=rising[1] - rising[0],
                rise_crossings_ms=rising, peak_to_1e_ms=fall_t - peak_t,
                asymptotic_decay_ms=CM_UF_CM2 / GL_MS_CM2)


def path(suffix):
    return BASE.with_name(BASE.name + '-' + suffix)


def main(expected_results_sha):
    if OUTPUT.exists():
        raise FileExistsError('Preserve the initial independent review')
    checks, reviews, exceptions, inputs = [], [], [], []

    def check(name, passed, **extra):
        checks.append(dict(name=name, passed=bool(passed), **extra))

    def close(name, actual, reference, tolerance):
        actual, reference = np.asarray(actual), np.asarray(reference)
        delta = float(np.max(np.abs(actual - reference)))
        check(name, np.isfinite(delta) and delta <= tolerance,
              max_absolute_difference=delta, tolerance=tolerance)
        return delta

    def pin(reference):
        current = record(ROOT / reference['path'])
        check('hash/size: ' + reference['path'], current == reference)
        inputs.append(current)

    try:
        rp, pp, cp, ap = (path(s) for s in ['results.json', 'plan.json', 'completion.json', 'arrays.npz'])
        check('externally supplied results SHA', record(rp)['sha256'] == expected_results_sha)
        r, p, completion = (json.loads(q.read_text()) for q in [rp, pp, cp])
        inputs.extend(record(q) for q in [rp, pp, cp, Path(__file__)])
        check('complete three-arm numeric batch before interpretation',
              r['status'] == completion['status'] == 'numeric_pass' and not r['exceptions']
              and [a['id'] for a in r['arms']] == ['g005', 'g004', 'zero_event']
              and all(a['status'] == 'numeric_pass' for a in r['arms']))
        check('reported check counts', r['checks_passed'] == sum(c['passed'] for c in r['checks'])
              and r['checks_failed'] == sum(not c['passed'] for c in r['checks']) == 0)
        for q in [p['source'], *p['inputs'], r['plan'], r['source'], r['started'],
                  r['arrays'], completion['plan'], completion['source'], completion['results'], completion['arrays']]:
            pin(q)
        started = json.loads((ROOT / r['started']['path']).read_text())
        check('started plan/source links', started['plan'] == r['plan'] and started['source'] == r['source'])
        expected_parameters = {'C_uF_per_cm2': CM_UF_CM2, 'gL_mS_per_cm2': GL_MS_CM2,
            'EL_mV': EL_MV, 'Esyn_mV': ESYN_MV, 'clamp_mV': CLAMP_MV,
            'T_on_source_units': .5, 'width_ms': WIDTH_MS,
            'alpha_per_ms_source_units': ALPHA_PER_MS, 'beta_per_ms': BETA_PER_MS}
        check('literal primary-source model parameters', p['parameters'] == expected_parameters)
        definitions = [dict(id='g005', gbar_mS_per_cm2=.05, event=True, author_intended_EPSP_peak_mV=1.4),
                       dict(id='g004', gbar_mS_per_cm2=.04, event=True, author_intended_EPSP_peak_mV=1.2),
                       dict(id='zero_event', gbar_mS_per_cm2=.05, event=False, author_intended_EPSP_peak_mV=None)]
        check('fixed arm definitions; no gain fitting', p['arms'] == definitions
              and [a['definition'] for a in r['arms']] == definitions)
        check('clock and baseline', p['clock_and_initial_state']['t_start_ms'] == 0.
              and p['clock_and_initial_state']['t_end_ms'] == 200.
              and p['clock_and_initial_state']['gate_O0'] == 0.
              and p['clock_and_initial_state']['u0_mV_relative_to_EL'] == 0.
              and p['clock_and_initial_state']['V0_mV'] == EL_MV)
        check('unit labels preserve density and unknown transmitter units',
              p['units']['synaptic_current_density'] == 'uA/cm^2'
              and 'not assigned mM' in p['units']['transmitter']
              and 'no total pA/nS' in p['units']['absolute_scaling_limit'])
        check('primary numerical/readout definitions', p['numerics']['max_step_ms'] == [.2, .1, .05]
              and p['numerics']['output_dt_ms'] == .01
              and 'asymptotic' in p['readouts']['decay_primary']
              and 'not the paper' in p['readouts']['decay_primary'])
        if not all(c['passed'] for c in checks):
            raise RuntimeError('Integrity/source prerequisite failed; no independent trajectory calculation')

        with np.load(ap, allow_pickle=False) as z:
            t = z['time_ms']
            check('exact retained output clock', np.array_equal(t, np.arange(20001, dtype=np.float64) * .01))
            check('array schema key set', set(z.files) == set(r['array_schema']))
            for key in z.files:
                a = z[key]
                check('array dtype/shape/finite: ' + key,
                      r['array_schema'][key] == dict(shape=list(a.shape), dtype=str(a.dtype))
                      and a.dtype == np.float64 and np.isfinite(a).all())
            close('shared exact gate array', z['event_exact_gate'], gate(t, .5), 1e-14)
            for definition, arm in zip(definitions, r['arms']):
                name, gb = definition['id'], definition['gbar_mS_per_cm2']
                transmitter = .5 if definition['event'] else 0.
                O = gate(t, transmitter)
                u, rhs, ode = voltage_reference(gb, transmitter, float(t[-1]))
                independent_u = u(t)
                worst_u, worst_gate = 0., 0.
                for tag in ['0p2', '0p1', '0p05']:
                    pair = z[f'{name}_step_{tag}_O_u']
                    check(name + ' sampled state dimensions ' + tag, pair.shape == (2, len(t)))
                    worst_gate = max(worst_gate, close(name + ' exact gate all samples ' + tag, pair[0], O, 1e-10))
                    worst_u = max(worst_u, close(name + ' independent scalar Radau all samples ' + tag,
                                                  pair[1], independent_u, 1e-8))
                primary = z[f'{name}_step_0p05_O_u']
                check(name + ' primary gate/voltage copies',
                      np.array_equal(z[name + '_gate_O'], primary[0])
                      and np.array_equal(z[name + '_u_mV'], primary[1]))
                close(name + ' baseline-relative voltage algebra', z[name + '_V_mV'], primary[1] + EL_MV, 0.)
                close(name + ' outward current density algebra', z[name + '_outward_synaptic_current_uA_per_cm2'],
                      gb * primary[0] * (primary[1] + EL_MV - ESYN_MV), 0.)
                close(name + ' separate ideal clamp current', z[name + '_clamp_outward_synaptic_current_uA_per_cm2'],
                      gb * O * (CLAMP_MV - ESYN_MV), 1e-12)
                check(name + ' current direction and physical bounds',
                      np.min(primary) >= -1e-10 and np.max(primary[0]) <= 1. + 1e-10
                      and np.max(primary[1] + EL_MV) <= ESYN_MV
                      and np.max(z[name + '_outward_synaptic_current_uA_per_cm2']) <= 1e-12)
                check(name + ' no initial state jump', np.array_equal(primary[:, 0], [0., 0.]))
                check(name + ' unforced endpoint approaches baseline', abs(primary[1, -1]) <= 1e-6)
                rt = z[name + '_reference_time_ms']
                anchors = list(p['numerics']['reference_anchors_ms'])
                if definition['event']:
                    anchors += [arm['metrics'][k] for k in ['voltage_peak_time_ms', 'voltage_t10_ms',
                                                          'voltage_t90_ms', 'voltage_falling_1e_time_ms']]
                check(name + ' exact predeclared/reference-defined anchors',
                      np.array_equal(rt, np.array(sorted(set(anchors)))) and len(rt) == arm['reference_count'])
                close(name + ' saved quadrature versus independent Radau', z[name + '_reference_u_mV'], u(rt), 1e-8)
                close(name + ' saved dense ODE versus independent Radau', z[name + '_reference_ode_u_mV'], u(rt), 1e-8)
                close(name + ' saved reference gate', z[name + '_reference_exact_gate'], gate(rt, transmitter), 1e-14)
                err = z[name + '_reference_quad_error_mV']
                check(name + ' retained quadrature error estimates', err.min() >= 0. and err.max() <= 1e-9)
                reviewed = dict(id=name, independent_reference=ode, samples_per_resolution=len(t),
                                resolutions=3, worst_voltage_difference_mV=worst_u,
                                worst_gate_difference=worst_gate, reference_anchors=len(rt))
                m = arm['metrics']
                if not definition['event']:
                    check('zero-event exact retained state', np.array_equal(primary, np.zeros_like(primary)))
                    check('zero-event undefined kinetics remain null',
                          all(v is None for k, v in m.items() if k not in [
                              'event', 'voltage_peak_delta_mV', 'clamp_peak_inward_uA_per_cm2'])
                          and not m['event'] and m['voltage_peak_delta_mV'] == m['clamp_peak_inward_uA_per_cm2'] == 0.)
                    reviewed['metrics'] = None
                else:
                    em = epsp_metrics(u, rhs, float(t[-1]))
                    rate = ALPHA_PER_MS * transmitter + BETA_PER_MS
                    crossings = [-np.log1p(-fraction * -np.expm1(-rate * WIDTH_MS)) / rate for fraction in [.1, .9]]
                    expected = dict(voltage_peak_delta_mV=em['peak_mv'], voltage_peak_time_ms=em['peak_time_ms'],
                        voltage_t10_ms=em['rise_crossings_ms'][0], voltage_t90_ms=em['rise_crossings_ms'][1],
                        voltage_rise_ms=em['rise_10_90_ms'], voltage_falling_1e_time_ms=em['peak_time_ms'] + em['peak_to_1e_ms'],
                        voltage_peak_to_1e_ms=em['peak_to_1e_ms'], voltage_asymptotic_tau_ms=CM_UF_CM2 / GL_MS_CM2,
                        clamp_peak_inward_uA_per_cm2=gb * float(gate(WIDTH_MS, transmitter)) * (ESYN_MV - CLAMP_MV),
                        clamp_peak_time_ms=WIDTH_MS, clamp_t10_ms=crossings[0], clamp_t90_ms=crossings[1],
                        clamp_rise_ms=crossings[1] - crossings[0], clamp_peak_to_1e_ms=1 / BETA_PER_MS,
                        clamp_asymptotic_tau_ms=1 / BETA_PER_MS)
                    for key, value in expected.items():
                        close(name + ' independent metric ' + key, m[key], value, 2e-8)
                    slopes = {}
                    for offset in [1, 5, 10, 20, 40]:
                        at = em['peak_time_ms'] + offset
                        value = -float(u(at)) / float(rhs(at, [float(u(at))])[0])
                        slopes[str(offset)] = value
                        close(name + ' instantaneous decay at peak+' + str(offset),
                              m['instantaneous_voltage_decay_ms'][str(offset)], value, 2e-7)
                    residuals = dict(EPSP_amplitude_minus_author_intended_mV=expected['voltage_peak_delta_mV'] - definition['author_intended_EPSP_peak_mV'],
                        EPSP_amplitude_minus_reported_mean_mV=expected['voltage_peak_delta_mV'] - 1.4,
                        EPSP_rise_minus_reported_mean_ms=expected['voltage_rise_ms'] - 2.1,
                        EPSC_rise_minus_reported_mean_ms=expected['clamp_rise_ms'] - .9,
                        conditional_EPSP_tail_minus_paper_fitted_decay_ms=CM_UF_CM2 / GL_MS_CM2 - 11.5,
                        conditional_EPSC_tail_minus_paper_fitted_decay_ms=1 / BETA_PER_MS - 2.8)
                    for key, value in residuals.items():
                        close(name + ' reported signed residual ' + key, m['source_differences'][key], value, 2e-8)
                    reviewed.update(metrics=expected, instantaneous_voltage_decay_ms=slopes,
                                    source_residuals=residuals)
                reviews.append(reviewed)
        ip = r['fixed_intrinsic_properties']
        close('intrinsic membrane ratio from source densities', ip['tau_m_ms'], CM_UF_CM2 / GL_MS_CM2, 0.)
        check('intrinsic boundary/missing area not promoted', ip['reported_somatic_tau_lower_ms'] == 200.
              and not ip['somatic_tau_constraint_met'] and ip['total_input_resistance_Gohm'] is None)
        for pin_record in inputs:
            check('end hash: ' + pin_record['path'], record(ROOT / pin_record['path']) == pin_record)
    except Exception as exc:
        import traceback
        exceptions.append(dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))

    report = dict(schema='turner-kc-conductance-independent-review/v1', created_utc=datetime.now(timezone.utc).isoformat(),
        passed=bool(checks) and all(c['passed'] for c in checks) and not exceptions,
        checks_passed=sum(c['passed'] for c in checks), checks_total=len(checks), checks=checks,
        exceptions=exceptions, inputs=inputs, arms=reviews,
        source_review=dict(visual_source='Turner author PDF physical page4, printed p736; preparation on physical page3/p735',
            rendered_page=record(ROOT / 'tmp/turner-kc-conductance-review/source-equations-page.png'),
            model_parameters='Printed fixed density values independently transcribed; no producer import.',
            unit_identity='(1e-3 S)/(1e-6 F)=1e3 per second=1 per ms; mS*mV=uA. No extra1000 in ms ODE.',
            gate='The activation rate is alpha times transmitter .5; transmitter concentration unit is not specified.',
            historical_model='Only passive intrinsic membrane properties plus synaptic activation gate; not a new active-channel or whole-network reproduction.',
            source_cohort='Female Canton-S, KC1–2 days. EPSP49 events Methods/50 Results in7cells, EPSC50events in5cells; not matched physiological cohorts.',
            source_decay='Published exponential fit windows absent; theoretical tails and 1/e durations are separately defined model summaries.'),
        scope='Independent scalar reference calculations on completed fixed-arm saved data. No producer/helper imports, fitting, network simulation or runtime edits.',
        limits=['Numerical consistency of a historical effective-event model is not biological validation.',
            'Reported dispersions are not assumed SEM/SD, confidence intervals or hard biological bounds.',
            'No membrane area, absolute whole-cell conductance/capacitance, PN identity, graph-contact or claw mapping inferred.',
            'Fixed published gains remain unchanged despite any mismatch from rounded author-intended amplitudes.',
            'Somatic greater-than200ms constraint remains unmet; no APL or threshold tuning.'])
    with OUTPUT.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(passed=report['passed'], checks_passed=report['checks_passed'],
                          checks_total=report['checks_total'], receipt=record(OUTPUT)), indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-results-sha', required=True)
    args = parser.parse_args()
    raise SystemExit(main(args.expected_results_sha))
