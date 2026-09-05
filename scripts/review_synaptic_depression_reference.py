#!/usr/bin/env python3
"""Independent saved-array and source review of the scalar depression reference.

No producer/model import, parameter fit, graph loading, brain or body execution.
Expected efficacy and recovery values use 80-digit Decimal closed expressions.
"""
from __future__ import annotations

import ast
import csv
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'validation/synaptic-depression-reference'
getcontext().prec = 80
D = Decimal
FACTOR, TAU, KERNEL = D('0.75'), D('0.3'), D('0.002')


def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def read(suffix):
    return json.loads((ROOT/(PREFIX+suffix)).read_text())


def decimal_fraction(value):
    return D(value.numerator)/D(value.denominator)


def regular_amplitudes(rate,count,initial=D(1)):
    decay = (-D(1)/(D(rate)*TAU)).exp()
    q = FACTOR*decay
    steady = (1-decay)/(1-q)
    return [steady+(initial-steady)*q**n for n in range(count)],steady


def protocol(rate,baseline):
    times = ([Fraction(-4)+Fraction(j,7) for j in range(28)] if baseline else [])
    base,_ = regular_amplitudes(7,29)
    n = (rate+1)//2
    test,_ = regular_amplitudes(rate,n,base[28] if baseline else D(1))
    return times+[Fraction(j,rate) for j in range(n)],(base[:28] if baseline else [])+test


def integral(times,amps,lo,hi):
    lo,hi = decimal_fraction(lo),decimal_fraction(hi)
    total = D(0)
    for t,a in zip(times,amps,strict=True):
        t = decimal_fraction(t)
        if t < hi:
            start = max(t,lo)
            total += a*KERNEL*((-(start-t)/KERNEL).exp()-(-(hi-t)/KERNEL).exp())
    return total


def main():
    plan,result,plot = read('-plan.json'),read('-results.json'),read('-plot-receipt.json')
    checks,errors,source_receipts = [],[],{}
    def check(name,value,detail=None):
        checks.append(dict(name=name,passed=bool(value),detail=detail))
        assert value,name
    def close(name,actual,expected,tolerance=1e-12):
        actual,expected = np.asarray(actual,dtype=float),np.asarray(expected,dtype=float)
        assert actual.shape == expected.shape,(name,actual.shape,expected.shape)
        error = float(np.max(abs(actual-expected))) if actual.size else 0.
        check(name,np.isfinite(actual).all() and error <= tolerance,error)
        errors.append((name,error));return error
    check('frozen_plan_chain',result['plan_sha256'] == sha(PREFIX+'-plan.json')
          == '86ade63439b8b20fb169ae7d9ea6395102f43f054319cc2e7a83f2f80c52f174')
    check('producer_79_checks',result['passed'] and len(result['checks']) == 79 and all(c['pass'] for c in result['checks']))
    check('parameters_source_units',result['fixed_parameters'] == plan['fixed_parameters'] == dict(
        per_event_retention_factor=.75,recovery_tau_seconds=.3,normalized_response_kernel_tau_seconds=.002))
    check('no_fit_no_runtime_no_brain',not result['model_fitted'] and not result['runtime_integrated'] and not result['brain_simulated'])
    for path,record in plan['source_paths'].items():
        data = (ROOT/path).read_bytes();origin = 'matching local bytes'
        if hashlib.sha256(data).hexdigest() != record['sha256']:
            proc = subprocess.run(['git','show',plan['git_head']+':'+path],cwd=ROOT,capture_output=True,check=True)
            data=proc.stdout;origin=plan['git_head']
        actual = hashlib.sha256(data).hexdigest()
        check('source:'+path,actual == record['sha256'] and len(data) == record['bytes'])
        source_receipts[path] = dict(sha256=actual,bytes=len(data),read_from=origin)
    for path,record in result['artifacts'].items():
        check('artifact:'+path,sha(path) == record['sha256'] and (ROOT/path).stat().st_size == record['bytes'])
    for category in ('inputs','outputs'):
        for path,expected in plot[category].items():check('plot_'+category+':'+path,sha(path) == expected)
    with np.load(ROOT/(PREFIX+'-arrays.npz'),allow_pickle=False) as archive:
        arrays = {k:archive[k] for k in archive.files}
    check('all_arrays_finite_float64',len(arrays) == 56 and all(v.dtype == np.float64 and np.isfinite(v).all() for v in arrays.values()))
    checked_arrays = set()
    def array(name,expected,tolerance=1e-12):
        checked_arrays.add(name)
        return close('array:'+name,arrays[name],expected,tolerance)
    expected_controls = {}
    for row in result['periodic_reference']:
        rate = row['rate_hz'];check('periodic_rate:'+str(rate),rate in [7,15,20,50,100,200])
        values,steady = regular_amplitudes(rate,256)
        array(f'periodic_{rate}_times_s',[float(Fraction(j,rate)) for j in range(256)],0)
        array(f'periodic_{rate}_pre_post',[[a,FACTOR*a] for a in values])
        actual = arrays[f'periodic_{rate}_pre_post']
        check(f'periodic_{rate}:bounds_monotonic',((0 <= actual)&(actual <= 1)).all() and (np.diff(actual[:,0]) <= 1e-12).all())
        close(f'periodic_{rate}:steady_formula',row['analytic_steady_state'],steady)
        close(f'periodic_{rate}:summary_last',row['last_amplitude'],actual[-1,0],0)
        close(f'periodic_{rate}:source_event_order',actual[:,1],.75*actual[:,0],0)
        check(f'periodic_{rate}:summary_count',row['pulses'] == 256 and row['initial_amplitude'] == 1)
    samples = [Fraction(j,10000) for j in range(-2000,7001)]
    sample_float = np.asarray([float(t) for t in samples])
    array('train_response_sample_times_s',sample_float,0)
    with (ROOT/(PREFIX+'-events.csv')).open(newline='') as stream:
        events = list(csv.DictReader(stream))
    with (ROOT/(PREFIX+'-charge-predictions.csv')).open(newline='') as stream:
        charge_csv = list(csv.DictReader(stream))
    event_cursor=0;protocol_values={};train_errors=[]
    check('train_frequencies',[r['test_rate_hz'] for r in result['train_predictions']] == [15,20,50,100,200])
    for row in result['train_predictions']:
        rate = row['test_rate_hz'];times,amps = protocol(rate,True)
        floats = np.asarray([float(t) for t in times]);afloat=np.asarray([float(a) for a in amps])
        array(f'train_{rate}_times_s',floats,0)
        train_errors.append(array(f'train_{rate}_pre_post',[[a,FACTOR*a] for a in amps]))
        array(f'train_{rate}_normalized_test_amplitude',[a/amps[28] for a in amps[28:]])
        # Independent explicit kernel matrix, not the producer's streaming state.
        age = sample_float[:,None]-floats[None,:]
        kernel = np.exp(-np.maximum(age,0)/float(KERNEL))*(age >= 0)
        response = kernel @ afloat
        array(f'train_{rate}_normalized_response',response)
        # Source events are exact rational fractions, not rounded display ticks.
        rows=events[event_cursor:event_cursor+len(times)];event_cursor += len(times)
        check(f'train_{rate}:CSV_row_count',len(rows) == len(times))
        for index,(event,t,a) in enumerate(zip(rows,times,amps,strict=True)):
            assert event['protocol'] == f'baseline7_then_{rate}' and int(event['event_index']) == index
            assert event['phase'] == ('baseline' if index < 28 else 'test')
            assert int(event['time_numerator']) == t.numerator and int(event['time_denominator']) == t.denominator
            assert float(event['time_seconds']) == float(t)
            assert abs(float(event['a_pre'])-float(a)) < 1e-12
            assert abs(float(event['a_post'])-float(FACTOR*a)) < 1e-12
            if index < 28: assert event['relative_to_first_test'] == ''
            else: assert abs(float(event['relative_to_first_test'])-float(a/amps[28])) < 1e-12
        check(f'train_{rate}:all_CSV_fractions_amplitudes',True)
        close(f'train_{rate}:summary',[row['first_test_amplitude'],row['last_test_time_s'],row['last_test_amplitude'],row['last_over_first_test_amplitude']],
            [float(amps[28]),float(times[-1]),float(amps[-1]),float(amps[-1]/amps[28])])
        check(f'train_{rate}:right_open_count',row['test_events'] == len(times)-28 == (rate+1)//2 and times[28] == 0 and times[-1] < Fraction(1,2))
        check(f'train_{rate}:prediction_label',row['status'] == 'fixed_rat_source_model_prediction_not_a_fit_or_measured_fly_value')
        protocol_values[rate] = (times,amps)
    check('all_CSV_rows_consumed',event_cursor == len(events) == 333)
    area_values={};baseline_values={}
    for rate in [20,50,100,200]:
        times,amps=protocol_values[rate]
        for window in [Fraction(1,10),Fraction(1,2)]:
            area_values[(rate,window)] = integral(times[28:],amps[28:],Fraction(0),window)
            baseline_values[(rate,window)] = integral(times[:28],amps[:28],Fraction(0),window)
    check('charge_rows_count',len(result['charge_predictions']) == len(charge_csv) == 8)
    baseline_tail_receipts=[]
    for row,csv_row in zip(result['charge_predictions'],charge_csv,strict=True):
        rate=row['rate_hz'];window=Fraction(str(row['window_s']));only=area_values[(rate,window)]
        baseline=baseline_values[(rate,window)];full=only+baseline
        normalized=only/area_values[(100,window)]
        close(f'charge_{rate}_{window}:analytic_test_integral',row['test_only_unit_amplitude_seconds'],only)
        close(f'charge_{rate}_{window}:analytic_full_integral',row['with_baseline_tail_unit_amplitude_seconds'],full)
        close(f'charge_{rate}_{window}:normalization',row['normalized_to_same_window_100hz'],normalized)
        close(f'charge_{rate}_{window}:CSV',[float(csv_row[k]) for k in row],list(row.values()),0)
        check(f'charge_{rate}_{window}:float_rounding_not_exact_zero',baseline > 0 and row['baseline_tail_difference'] == 0
            and float(only+baseline) == float(only))
        baseline_tail_receipts.append(dict(rate_hz=rate,window_s=float(window),
            positive_baseline_tail_amplitude_seconds_decimal=str(baseline)))
    recovery_errors=[]
    for row in result['recovery_predictions']:
        key=row['name']
        if key == 'pause7':
            base,_ = regular_amplitudes(7,28)
            start=FACTOR*base[-1];grid=[Fraction(j,100) for j in range(3001)]
            prefix='pause7'
            array('pause7_time_since_last_baseline_event_s',[float(t) for t in grid],0)
            check('pause_anchor_last_event',row['anchor_last_event_s'] == float(Fraction(-1,7)) and row['baseline_events'] == 28)
            close('pause_start_post_event',row['amplitude_immediately_after_last_event'],start)
        else:
            rate=row['test_hz'];baseline=row['baseline'] == '7Hz4s'
            times,amps=protocol(rate,baseline)
            array(key+'_event_times_s',[float(t) for t in times],0)
            array(key+'_event_pre_post',[[a,FACTOR*a] for a in amps])
            grid=[Fraction(j,1000) for j in range(2001)]
            array(key+'_time_after_nominal_train_end_s',[float(t) for t in grid],0)
            gap=Fraction(1,2)-times[-1]
            start=1-(1-FACTOR*amps[-1])*(-decimal_fraction(gap)/TAU).exp()
            check(key+':nominal_end_not_last_spike',row['anchor_nominal_train_end_s'] == .5 and row['last_event_time_s'] == float(times[-1]) and gap > 0)
            close(key+':anchor_amplitude',row['amplitude_at_anchor'],start)
            prefix=key
        recovered=[1-(-decimal_fraction(t)/TAU).exp() for t in grid]
        probe=[start+(1-start)*f for f in recovered]
        recovery_errors.append(array(prefix+'_probe_amplitude',probe))
        array(prefix+'_fraction_of_deficit_recovered',recovered)
        check(key+':probe_bounds_monotonic',np.all((arrays[prefix+'_probe_amplitude'] >= 0)&(arrays[prefix+'_probe_amplitude'] <= 1))
            and np.all(np.diff(arrays[prefix+'_probe_amplitude']) >= 0))
        for field,t in [('probe_amplitude_after_300ms',D('.3')),('probe_amplitude_after_1s',D(1)),
                        ('probe_amplitude_after_2s',D(2)),('probe_amplitude_after_7p5s',D('7.5'))]:
            if field in row:close(key+':'+field,row[field],1-(1-start)*(-t/TAU).exp())
    check('all_56_arrays_independently_checked',checked_arrays == set(arrays))
    close('single_tau_63percent',result['uniform_recovery_property']['time_to_recover_fraction_1_minus_exp_minus1_s'],TAU,0)
    close('single_tau_99percent',result['uniform_recovery_property']['time_to_recover_99percent_of_current_deficit_s'],-TAU*D('.01').ln())
    # The edge-case state snapshots were not saved. Inspect their operations;
    # do not relabel the producer's zero-error summaries as independent traces.
    tree=ast.parse((ROOT/'scripts/synaptic-depression-reference.py').read_text())
    imports=[node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    imports += [alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names]
    check('standalone_import_scope',not any((name or '').startswith(('fruitfly','mujoco','scipy.optimize')) for name in imports))
    efficacy=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'Efficacy')
    methods={n.name:n for n in efficacy.body if isinstance(n,ast.FunctionDef)}
    assignments=[n for n in ast.walk(methods['peek']) if isinstance(n,(ast.Assign,ast.AugAssign,ast.AnnAssign))]
    targets=[t for n in assignments for t in (n.targets if isinstance(n,ast.Assign) else [n.target])]
    check('peek_source_no_state_assignment',not any(isinstance(t,ast.Attribute) for t in targets))
    event_body=methods['event'].body
    check('source_read_before_decrement',isinstance(event_body[0],ast.Assign)
          and ast.unparse(event_body[0].value) == 'self.peek(time_s)'
          and ast.unparse(event_body[-1]) == 'return (before, self.a)'
          and any(ast.unparse(n) == 'self.a = self.factor * before' for n in event_body))
    check('frozen_artifacts_unchanged_after_review',all(sha(p) == r['sha256'] for p,r in result['artifacts'].items()))
    receipt=dict(created_utc=datetime.now(timezone.utc).isoformat(),passed=True,checks=checks,check_count=len(checks),
        reviewer_sha256=sha('scripts/review_synaptic_depression_reference.py'),
        plan_sha256=sha(PREFIX+'-plan.json'),results_sha256=sha(PREFIX+'-results.json'),plot_receipt_sha256=sha(PREFIX+'-plot-receipt.json'),
        source_receipts=source_receipts,arrays_checked=len(checked_arrays),array_values_checked=sum(v.size for v in arrays.values()),
        exact_fraction_CSV_rows_checked=len(events),precision_decimal_digits=getcontext().prec,
        maximum_absolute_numeric_error=max(v for _,v in errors),maximum_error_check=max(errors,key=lambda x:x[1])[0],
        finite_train_max_error=max(train_errors),recovery_max_error=max(recovery_errors),
        positive_baseline_tail_values=baseline_tail_receipts,
        source_review=dict(Abbott_1997='Printed p223 notes 4/6/7/10 visually and textually checked: rat primary visual cortex; f=.75; tau=300ms; efficacy multiplication/recovery; separate 2ms conductance decay.',
            Kazama_Wilson_2008='Main Fig8D-F and Fig9B-D visually/textually checked; female methods checked. Figure8F rates15/20/50Hz; Fig9B rates20/50/100/200Hz; 7Hz4s baseline, .5s train, .1/.5s integrals normalized at100Hz.',
            supplement='FigS8 visually/textually checked: post-train and baseline-pause protocols differ; S8D explicitly reports7.5s recovery. Fixed0.3s model is not an empirical reproduction.',
            plot='PNG visually inspected: model-only label, fixed parameters, event ratios, normalized area and common recovery law are legible; no fly data overlay.'),
        limitations=[
            'Primary scalar equations and parameter provenance are verified; linear summed response is a separate declared observation proxy, not a reproduction of the Abbott conductance-driven network or a measured fly current.',
            'The array suffix normalized_response means unit peak per fully recovered event. It is not divided by the first test amplitude; normalized_test_amplitude and same-window area ratios are separate arrays/quantities.',
            'Same-time/null/backward-event/read-only-query checks retain producer pass/error summaries, not their before/after scalar state traces. Source ordering and independent analytic expectations support them without re-executing the producer.',
            'Exact pulse phase, recovery probe timing/history and empirical recovery-ratio conventions were not extracted from fly measurements. Rational timing and isolated-probe grids are declared scenarios.',
            'Positive baseline-tail area is around1e-34 amplitude-seconds; saved full-minus-test zero is floating-point cancellation, not exact absence of a tail.',
            'No points/uncertainties were digitized, no parameters fitted, no residual or biological pass/fail computed. The fixed rat-derived0.3s recovery cannot be presented as validation of the published fly recovery curve or7.5s timescale.',
            'No inferred release probability/site count, male ORN-PN gain, graph-wide depression, or runtime integration is justified by this scalar reference.'
        ])
    destination=ROOT/'validation/synaptic-depression-reference-independent-review.json'
    destination.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:receipt[k] for k in ('passed','check_count','arrays_checked','array_values_checked','exact_fraction_CSV_rows_checked','maximum_absolute_numeric_error','maximum_error_check')},indent=2))


if __name__ == '__main__':
    main()
