#!/usr/bin/env python3
"""Fixed Turner (2008) local subthreshold reference; no neural package imports.

--prepare freezes literal source parameters and numerical/readout definitions.
--run executes every frozen arm once; failures and partial arrays are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np
import scipy
from scipy.integrate import quad, solve_ivp
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation' / 'turner-kc-conductance'
SOURCE_PATHS = [
    'data/raw/pn-kc-physiology/turner2008-author.pdf',
    'data/raw/pn-kc-physiology/turner2008-author.txt',
    'research/21-pn-kc-physiology-calibration.md',
    'validation/pn-kc-physiology-source-review.json',
    'docs/pn-kc-waveform-candidate-review.md',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def path(suffix):
    return Path(str(BASE) + '-' + suffix)


def record(f):
    f = Path(f)
    b = f.read_bytes()
    return {'path': str(f.relative_to(ROOT)), 'bytes': len(b),
            'sha256': hashlib.sha256(b).hexdigest()}


def write_json(f, value):
    with Path(f).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def parameters():
    return {'C_uF_per_cm2': 1.0, 'gL_mS_per_cm2': .089, 'EL_mV': -57.8,
            'Esyn_mV': 0., 'clamp_mV': -60., 'T_on_source_units': .5,
            'width_ms': .3, 'alpha_per_ms_source_units': 2.5,
            'beta_per_ms': .4}


def prepare():
    for suffix in ['plan.json', 'started.json', 'results.json', 'arrays.npz', 'completion.json']:
        if path(suffix).exists():
            raise FileExistsError(path(suffix))
    anchors = sorted(set([0., .001, .005, .01, .025, .05, .1, .2,
                          .299999, .3, .300001, .4, .5, .75, 1., 1.5, 2.,
                          3., 5., 7., 10., 15., 20., 30., 40., 60., 80.,
                          100., 150., 200.] + list(np.linspace(0., 2., 81))
                         + list(np.linspace(2., 200., 100))))
    plan = {
        'schema': 'turner-kc-conductance-plan-v1', 'created_utc': now(),
        'scope': 'Fixed published density-parameter conductance equations; all three local arms together. No parameter fit, threshold/reset, APL, network, state clamp, or source-default change.',
        'source': record(Path(__file__)), 'inputs': [record(ROOT / f) for f in SOURCE_PATHS],
        'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                        'scipy': scipy.__version__, 'platform': platform.platform()},
        'parameters': parameters(),
        'units': {'time': 'ms', 'voltage': 'mV', 'capacitance_density': 'uF/cm^2',
                  'conductance_density': 'mS/cm^2', 'synaptic_current_density': 'uA/cm^2',
                  'conversion': 'Numeric (mS/cm^2)/(uF/cm^2) is ms^-1; no factor 1000. Numeric mS*mV is uA.',
                  'transmitter': 'A=.5 in unspecified source concentration units; not assigned mM',
                  'absolute_scaling_limit': 'No membrane area or total capacitance: no total pA/nS or per-connectome-contact calibration'},
        'arms': [{'id': 'g005', 'gbar_mS_per_cm2': .05, 'event': True,
                  'author_intended_EPSP_peak_mV': 1.4},
                 {'id': 'g004', 'gbar_mS_per_cm2': .04, 'event': True,
                  'author_intended_EPSP_peak_mV': 1.2},
                 {'id': 'zero_event', 'gbar_mS_per_cm2': .05, 'event': False,
                  'author_intended_EPSP_peak_mV': None}],
        'clock_and_initial_state': {'t_start_ms': 0., 't_end_ms': 200., 'gate_O0': 0.,
                                    'u0_mV_relative_to_EL': 0., 'V0_mV': -57.8,
                                    'event': 'Exactly one transmitter rectangle [0,0.3) ms for event arms, zero otherwise; time zero is synapse activation, not sensory onset or measured PN arrival latency'},
        'equations': ['dO/dt=alpha*(1-O)*T-beta*O',
                      'du/dt=-(gL+gbar*O)*u/C+gbar*O*(Esyn-EL)/C',
                      'V=EL+u; outward synaptic current density=gbar*O*(V-Esyn)',
                      'separate ideal clamp synaptic current=gbar*O*(Vclamp-Esyn); leak excluded'],
        'numerics': {'primary': 'DOP853 coupled O,u ODE, explicitly split at transmitter offset; primary max_step is smallest below',
                     'max_step_ms': [.2, .1, .05], 'rtol': 1e-11,
                     'atol_gate_and_u': 1e-12, 'output_dt_ms': .01,
                     'independent_reference': 'Analytic piecewise gate and primitive; integrating-factor voltage quadrature split at transmitter offset',
                     'quad_epsabs': 1e-12, 'quad_epsrel': 1e-12, 'quad_limit': 200,
                     'reference_anchors_ms': anchors,
                     'additional_reference_times': 'Every nonzero arm voltage peak, rising10/rising90 and falling1/e; deterministic readout-defined anchors, not chosen by observed numerical error',
                     'root_xtol_ms': 1e-11,
                     'tolerances': {'voltage_quad_mV': 1e-8, 'gate_exact': 1e-10,
                                    'temporal_convergence_mV': 1e-8, 'temporal_convergence_gate': 1e-10,
                                    'quad_reported_error_mV': 1e-9, 'boundary_continuity': 1e-12,
                                    'positivity_and_bound': 1e-10, 'endpoint_u_mV': 1e-6,
                                    'density_current_gate_crosscheck_uA_per_cm2': 1e-8}},
        'readouts': {'rise': 'First 10% and 90% rising crossings of each own baseline-subtracted waveform peak, via dense ODE root solve for voltage and exact gate for clamp',
                     'peak': 'Continuous voltage peak from derivative root; exact gate peak at0.3ms; zero-event normalized/peak-time metrics null',
                     'decay_primary': 'Theoretical asymptotic tau=C/gL for event voltage and1/beta for clamp; explicitly not the paper unspecified finite-window exponential fit',
                     'decay_additional': 'Peak-to-first-falling-1/e duration and instantaneous -u/uprime at peak+[1,5,10,20,40]ms; no exponential fitting or posthoc window selection',
                     'zero_event': 'Retain complete zero trajectories; undefined normalized kinetics null, never missing-as-zero'},
        'source_summary': {'EPSP_peak_mV': {'mean': 1.4, 'reported_dispersion': .8, 'median': 1.2},
                           'EPSP_rise_ms': {'mean': 2.1, 'reported_dispersion': .5},
                           'EPSP_fitted_decay_ms': {'mean': 11.5, 'reported_dispersion': 5.3},
                           'EPSC_rise_ms': {'mean': .9, 'reported_dispersion': .4},
                           'EPSC_fitted_decay_ms': {'mean': 2.8, 'reported_dispersion': 1.2},
                           'dispersion_caveat': 'Do not label each as SEM/SD without specific source definition; do not make acceptance intervals from them',
                           'holding': 'KC current clamp near-58±2mV; model native EL-57.8; separate measured EPSC clamp-60mV',
                           'intrinsic_somatic_tau_ms': {'relation': '>', 'value': 200},
                           'cohort': 'Female Canton-S: KCs1–2days; PN4–12days; EPSP7cells49eventsMethods/50Results, EPSC5cells50events; no matched cells/PN identities or MaleCNS mapping'},
        'outputs': [str(path(s).relative_to(ROOT)) for s in ['started.json', 'arrays.npz', 'results.json', 'completion.json']],
        'failure_policy': 'Exclusive files; all arms attempted after source checks; retain first exceptions/check failures and partial named arrays, no overwrite/restart. Completion status distinguishes numeric failure from descriptive physiological mismatch.',
    }
    write_json(path('plan.json'), plan)
    print(json.dumps({'plan': record(path('plan.json')), 'source': plan['source']}, indent=2))


def exact_gate(t, p, event):
    if not event or t <= 0:
        return 0.
    l = p['alpha_per_ms_source_units'] * p['T_on_source_units'] + p['beta_per_ms']
    h = p['alpha_per_ms_source_units'] * p['T_on_source_units'] / l
    w = p['width_ms']
    if t <= w:
        return h * -math.expm1(-l * t)
    ow = h * -math.expm1(-l * w)
    return ow * math.exp(-p['beta_per_ms'] * (t - w))


def gate_integral(t, p, event):
    if not event or t <= 0:
        return 0.
    l = p['alpha_per_ms_source_units'] * p['T_on_source_units'] + p['beta_per_ms']
    h = p['alpha_per_ms_source_units'] * p['T_on_source_units'] / l
    w = p['width_ms']
    a = min(t, w)
    first = h * (a + math.expm1(-l * a) / l)
    if t <= w:
        return first
    ow = h * -math.expm1(-l * w)
    return first + ow * -math.expm1(-p['beta_per_ms'] * (t - w)) / p['beta_per_ms']


def voltage_quad(t, gb, p, event, numerical):
    if t <= 0 or not event:
        return 0., 0.
    C, gl, D = p['C_uF_per_cm2'], p['gL_mS_per_cm2'], p['Esyn_mV'] - p['EL_mV']
    Gt = gate_integral(t, p, event)
    def integrand(s):
        attenuation = gl * (t-s) / C + gb * (Gt-gate_integral(s, p, event)) / C
        return D*gb/C*exact_gate(s, p, event)*math.exp(-attenuation)
    cuts = [0.] + ([p['width_ms']] if t > p['width_ms'] else []) + [t]
    values, errors = [], []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        v, e = quad(integrand, lo, hi, epsabs=numerical['quad_epsabs'],
                    epsrel=numerical['quad_epsrel'], limit=numerical['quad_limit'])
        values.append(v); errors.append(e)
    return math.fsum(values), math.fsum(errors)


def solve_arm(arm, p, n, end, max_step):
    gb, event = arm['gbar_mS_per_cm2'], arm['event']
    C, gl, D = p['C_uF_per_cm2'], p['gL_mS_per_cm2'], p['Esyn_mV'] - p['EL_mV']
    def rhs(T):
        def f(t, y):
            O, u = y
            return [p['alpha_per_ms_source_units']*(1-O)*T-p['beta_per_ms']*O,
                    -(gl+gb*O)*u/C+gb*O*D/C]
        return f
    kw = dict(method='DOP853', rtol=n['rtol'], atol=n['atol_gate_and_u'],
              max_step=max_step, dense_output=True)
    first = solve_ivp(rhs(p['T_on_source_units'] if event else 0.),
                      (0., p['width_ms']), [0., 0.], **kw)
    if not first.success:
        raise RuntimeError('first interval solver failed: ' + first.message)
    second = solve_ivp(rhs(0.), (p['width_ms'], end), first.y[:, -1], **kw)
    if not second.success:
        raise RuntimeError('second interval solver failed: ' + second.message)
    def evaluate(t):
        t = np.asarray(t)
        if t.ndim == 0:
            return first.sol(float(t)) if float(t) <= p['width_ms'] else second.sol(float(t))
        result = np.empty((2, len(t)))
        early = t <= p['width_ms']
        if early.any(): result[:, early] = first.sol(t[early])
        if (~early).any(): result[:, ~early] = second.sol(t[~early])
        return result
    return evaluate, first, second


def summarize(arm, p, n, end, evaluate):
    if not arm['event']:
        return {'event': False, 'voltage_peak_delta_mV': 0., 'voltage_peak_time_ms': None,
                'voltage_t10_ms': None, 'voltage_t90_ms': None, 'voltage_rise_ms': None,
                'voltage_falling_1e_time_ms': None, 'voltage_peak_to_1e_ms': None,
                'clamp_peak_inward_uA_per_cm2': 0., 'clamp_peak_time_ms': None,
                'clamp_t10_ms': None, 'clamp_t90_ms': None, 'clamp_rise_ms': None,
                'clamp_peak_to_1e_ms': None, 'voltage_asymptotic_tau_ms': None,
                'clamp_asymptotic_tau_ms': None, 'instantaneous_voltage_decay_ms': None,
                'source_differences': None}
    gb = arm['gbar_mS_per_cm2']; C = p['C_uF_per_cm2']
    root_kw = {'xtol': n['root_xtol_ms']}
    def u(t): return float(evaluate(t)[1])
    def deriv(t):
        O, val = evaluate(t)
        return -(p['gL_mS_per_cm2']+gb*O)*val/C+gb*O*(p['Esyn_mV']-p['EL_mV'])/C
    peak_t = brentq(deriv, p['width_ms'], end, **root_kw)
    peak = u(peak_t)
    t10 = brentq(lambda t:u(t)-.1*peak, 0., peak_t, **root_kw)
    t90 = brentq(lambda t:u(t)-.9*peak, 0., peak_t, **root_kw)
    falling = brentq(lambda t:u(t)-peak/math.e, peak_t, end, **root_kw)
    peak_gate = exact_gate(p['width_ms'], p, True)
    c10 = brentq(lambda t:exact_gate(t,p,True)-.1*peak_gate,0.,p['width_ms'],**root_kw)
    c90 = brentq(lambda t:exact_gate(t,p,True)-.9*peak_gate,0.,p['width_ms'],**root_kw)
    tau_m = C/p['gL_mS_per_cm2']; tau_c = 1/p['beta_per_ms']
    return {'event': True, 'voltage_peak_delta_mV': peak, 'voltage_peak_time_ms': peak_t,
            'voltage_t10_ms': t10, 'voltage_t90_ms': t90, 'voltage_rise_ms': t90-t10,
            'voltage_falling_1e_time_ms': falling, 'voltage_peak_to_1e_ms': falling-peak_t,
            'clamp_peak_inward_uA_per_cm2': gb*peak_gate*(p['Esyn_mV']-p['clamp_mV']),
            'clamp_peak_time_ms': p['width_ms'], 'clamp_t10_ms': c10,
            'clamp_t90_ms': c90, 'clamp_rise_ms': c90-c10,
            'clamp_peak_to_1e_ms': tau_c, 'voltage_asymptotic_tau_ms': tau_m,
            'clamp_asymptotic_tau_ms': tau_c,
            'instantaneous_voltage_decay_ms': {str(offset): -u(peak_t+offset)/deriv(peak_t+offset) for offset in [1,5,10,20,40]},
            'source_differences': {'EPSP_amplitude_minus_author_intended_mV': peak-arm['author_intended_EPSP_peak_mV'],
                                   'EPSP_amplitude_minus_reported_mean_mV': peak-1.4,
                                   'EPSP_rise_minus_reported_mean_ms': t90-t10-2.1,
                                   'EPSC_rise_minus_reported_mean_ms': c90-c10-.9,
                                   'conditional_EPSP_tail_minus_paper_fitted_decay_ms': tau_m-11.5,
                                   'conditional_EPSC_tail_minus_paper_fitted_decay_ms': tau_c-2.8,
                                   'decay_comparison_caveat': 'Different metrics: source exponential fit window unavailable; no exact fitted-decay reproduction claimed'}}


def run():
    for suffix in ['started.json', 'results.json', 'arrays.npz', 'completion.json']:
        if path(suffix).exists(): raise FileExistsError(path(suffix))
    plan = json.loads(path('plan.json').read_text())
    started = {'schema': 'turner-kc-conductance-start-v1', 'started_utc': now(),
               'plan': record(path('plan.json')), 'source': record(Path(__file__)),
               'pid': __import__('os').getpid()}
    write_json(path('started.json'), started)
    start = time.monotonic()
    result = {'schema': 'turner-kc-conductance-results-v1', 'status': 'running',
              'plan': record(path('plan.json')), 'source': record(Path(__file__)),
              'started': record(path('started.json')), 'arms': [], 'checks': [],
              'exceptions': [], 'scope': plan['scope'],
              'physiological_acceptance': 'Not established; source dispersions are not acceptance bounds; model is historical effective synaptic approximation'}
    arrays = {}
    def check(name, value, limit=None, equal=False):
        ok = bool(value) if limit is None else bool(value == limit if equal else value <= limit)
        row = {'name': name, 'passed': ok, 'value': value}
        if limit is not None: row.update(limit=limit, relation='==' if equal else '<=')
        result['checks'].append(row)
        return ok
    def pins():
        return all(record(ROOT/q['path']) == q for q in [plan['source'], *plan['inputs']])
    try:
        if not check('Frozen source and primary inputs match before', pins()):
            raise RuntimeError('Frozen source/input mismatch')
        if not check('Frozen Python/NumPy/SciPy versions match',
                     [platform.python_version(),np.__version__,scipy.__version__] ==
                     [plan['environment'][k] for k in ['python','numpy','scipy']]):
            raise RuntimeError('Frozen package-version mismatch')
        p, n = plan['parameters'], plan['numerics']; lim = n['tolerances']
        end = plan['clock_and_initial_state']['t_end_ms']
        dt = n['output_dt_ms']; grid = np.arange(round(end/dt)+1,dtype=np.float64)*dt
        arrays['time_ms'] = grid
        Oexact = np.array([exact_gate(float(t),p,True) for t in grid])
        arrays['event_exact_gate'] = Oexact
        result['fixed_intrinsic_properties'] = {'tau_m_ms': p['C_uF_per_cm2']/p['gL_mS_per_cm2'],
                                                'reported_somatic_tau_lower_ms': 200.,
                                                'somatic_tau_constraint_met': False,
                                                'total_input_resistance_Gohm': None,
                                                'reason': 'Area missing; source densities identify specific resistance and effective time constant, not total resistance'}
        for arm in plan['arms']:
            name = arm['id']; state = {'id': name, 'status': 'running', 'definition': arm}
            result['arms'].append(state)
            try:
                solutions = []
                for step in n['max_step_ms']:
                    evaluate, first, second = solve_arm(arm,p,n,end,step)
                    ys = evaluate(grid)
                    arrays[f'{name}_step_{str(step).replace(".","p")}_O_u'] = ys
                    solutions.append((evaluate, first, second, ys))
                ev, first, second, ys = solutions[-1]
                state['metrics'] = summarize(arm,p,n,end,ev)
                state['solver_steps'] = [{'max_step_ms':step, 'nfev':a.nfev+b.nfev,
                                          'saved_internal_time_count':len(a.t)+len(b.t),
                                          'success':a.success and b.success}
                                         for step,(_,a,b,_) in zip(n['max_step_ms'],solutions)]
                arrays[f'{name}_gate_O'] = ys[0]
                arrays[f'{name}_u_mV'] = ys[1]
                arrays[f'{name}_V_mV'] = ys[1]+p['EL_mV']
                arrays[f'{name}_outward_synaptic_current_uA_per_cm2'] = arm['gbar_mS_per_cm2']*ys[0]*(ys[1]+p['EL_mV']-p['Esyn_mV'])
                cexact = -arm['gbar_mS_per_cm2']*(Oexact if arm['event'] else np.zeros_like(Oexact))*(p['Esyn_mV']-p['clamp_mV'])
                arrays[f'{name}_clamp_outward_synaptic_current_uA_per_cm2'] = cexact
                check(name+' finite output states', bool(np.isfinite(ys).all()))
                check(name+' exact gate error', float(np.max(np.abs(ys[0]-(Oexact if arm['event'] else 0.)))),lim['gate_exact'])
                check(name+' gate below zero', float(max(0.,-ys[0].min())),lim['positivity_and_bound'])
                check(name+' gate above one', float(max(0.,ys[0].max()-1.)),lim['positivity_and_bound'])
                check(name+' voltage below baseline',float(max(0.,-ys[1].min())),lim['positivity_and_bound'])
                check(name+' voltage above excitatory reversal',float(max(0.,(ys[1]+p['EL_mV']-p['Esyn_mV']).max())),lim['positivity_and_bound'])
                check(name+' endpoint baseline approach',float(abs(ys[1,-1])),lim['endpoint_u_mV'])
                boundary = np.max(np.abs(first.sol(p['width_ms'])-second.sol(p['width_ms'])))
                check(name+' transmitter-offset state continuity',float(boundary),lim['boundary_continuity'])
                for step,(_,_,_,s) in zip(n['max_step_ms'][:-1],solutions[:-1]):
                    check(name+f' step{step} versus primary voltage',float(np.max(np.abs(s[1]-ys[1]))),lim['temporal_convergence_mV'])
                    check(name+f' step{step} versus primary gate',float(np.max(np.abs(s[0]-ys[0]))),lim['temporal_convergence_gate'])
                ct_ode = arm['gbar_mS_per_cm2']*ys[0]*(p['clamp_mV']-p['Esyn_mV'])
                check(name+' density-current gate crosscheck',float(np.max(np.abs(ct_ode-cexact))),lim['density_current_gate_crosscheck_uA_per_cm2'])
                references = list(n['reference_anchors_ms'])
                if arm['event']:
                    references += [state['metrics'][k] for k in ['voltage_peak_time_ms','voltage_t10_ms','voltage_t90_ms','voltage_falling_1e_time_ms']]
                rt = np.array(sorted(set(references)))
                rv = np.array([voltage_quad(float(t),arm['gbar_mS_per_cm2'],p,arm['event'],n) for t in rt])
                predicted = ev(rt)
                arrays[f'{name}_reference_time_ms'] = rt
                arrays[f'{name}_reference_u_mV'] = rv[:,0]
                arrays[f'{name}_reference_quad_error_mV'] = rv[:,1]
                arrays[f'{name}_reference_ode_u_mV'] = predicted[1]
                arrays[f'{name}_reference_exact_gate'] = np.array([exact_gate(float(t),p,arm['event']) for t in rt])
                check(name+' independent voltage quadrature',float(np.max(np.abs(rv[:,0]-predicted[1]))),lim['voltage_quad_mV'])
                check(name+' reference estimated quadrature error',float(rv[:,1].max()),lim['quad_reported_error_mV'])
                state['reference_count'] = len(rt)
                if arm['event']:
                    check(name+' positive event EPSP',state['metrics']['voltage_peak_delta_mV']>0)
                    check(name+' peak and crossing order',0<state['metrics']['voltage_t10_ms']<state['metrics']['voltage_t90_ms']<state['metrics']['voltage_peak_time_ms']<state['metrics']['voltage_falling_1e_time_ms']<end)
                    check(name+' independent gate boundary value',abs(float(first.sol(p['width_ms'])[0])-exact_gate(p['width_ms'],p,True)),lim['gate_exact'])
                else:
                    check(name+' zero-event arrays exactly zero', bool(np.array_equal(ys,np.zeros_like(ys))))
                    check(name+' zero-event normalized metrics unavailable',state['metrics']['voltage_rise_ms'] is None and state['metrics']['clamp_rise_ms'] is None)
                state['status'] = 'numeric_pass' if all(c['passed'] for c in result['checks'] if c['name'].startswith(name+' ')) else 'numeric_failure'
            except Exception as error:
                state['status']='exception'; state['exception']=repr(error)
                result['exceptions'].append({'stage':name, 'exception':repr(error), 'traceback':traceback.format_exc()})
        check('All frozen arms present and numerically passed',len(result['arms'])==len(plan['arms']) and all(a['status']=='numeric_pass' for a in result['arms']))
        check('Frozen source and primary inputs match after',pins())
        check('Frozen plan unchanged',record(path('plan.json'))==started['plan'])
        result['status']='numeric_pass' if all(c['passed'] for c in result['checks']) and not result['exceptions'] else 'numeric_failure'
    except Exception as error:
        result['status']='exception'
        result['exceptions'].append({'stage':'outer', 'exception':repr(error), 'traceback':traceback.format_exc()})
    finally:
        with path('arrays.npz').open('xb') as stream:
            np.savez_compressed(stream,**arrays)
        result['arrays']=record(path('arrays.npz'))
        result['array_schema']={k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in arrays.items()}
        result['finished_utc']=now();result['wall_s']=time.monotonic()-start
        result['checks_passed']=sum(c['passed'] for c in result['checks'])
        result['checks_failed']=sum(not c['passed'] for c in result['checks'])
        write_json(path('results.json'),result)
        write_json(path('completion.json'),{'schema':'turner-kc-conductance-completion-v1',
                   'status':result['status'],'plan':record(path('plan.json')),
                   'results':record(path('results.json')),'arrays':record(path('arrays.npz')),
                   'source':record(Path(__file__)),'completed_utc':now()})
        print(json.dumps({'status':result['status'],'checks_passed':result['checks_passed'],
                          'checks_failed':result['checks_failed'],'wall_s':result['wall_s'],
                          'results':record(path('results.json'))},indent=2))
    return 0 if result['status']=='numeric_pass' else 1


if __name__ == '__main__':
    a=argparse.ArgumentParser(description=__doc__)
    g=a.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true');g.add_argument('--run',action='store_true')
    args=a.parse_args()
    if args.prepare:prepare()
    else:sys.exit(run())
