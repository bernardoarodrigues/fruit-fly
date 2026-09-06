"""Complete APL staircase and dedicated-pulse current/voltage measurements."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-input-response-plan.json'
OUT=ROOT/'validation/apl-input-response-results.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve frozen plan')
    h=json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text())
    files=[r for r in h['records'] if r['metadata']['protocol'].startswith('IC_FP') or ('AHP' in r['metadata']['protocol'] and '/APL_SD_APL_SKRNAi_' in r['member'])]
    pins=['scripts/measure_apl_input_response.py','validation/apl-sk-abf-headers.json','validation/apl-sk-workbook-join.json','validation/apl-passive-measurements.json']
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),pins={x:sha(ROOT/x) for x in pins},members=[f['member'] for f in files],
        expected_files=93,expected_sweeps=2197,baseline_duration_s=.1,plateau_duration_s=.1,early_window_s=[.05,.1],
        common_ahp_window_s=[.005,.6],recorded_current_tolerance_pA=5.,recorded_current_relative_tolerance=.05,
        methods='Every sweep of every APL firing-pattern file plus all eleven dedicated 2 nA files. Read the variable epoch (DAC0 epoch3 for staircase, epoch1 for dedicated pulse), including its per-sweep amplitude increment and actual onset/duration. Fixed mean voltage/current baseline in 100 ms before onset and plateau in final 100 ms before offset. Preserve 50-100 ms early mean, maximum in first100ms, signed post-offset minimum relative to baseline over +5 to +600ms and its time. These minima are descriptive extrema, not accepted AHP kinetics. Do not smooth, reject sweeps or infer current from mV channels. Record all identities, source timestamps, sweep order and inter-sweep interval. Compare positive-current plateaus with the fixed independently measured -50pA response; do not assume that small-signal resistance predicts large depolarization. No fitting occurs in this batch.',
        scope='Complete drive/response measurements, not an autonomous outward-current law, corrected absolute voltage or physiological parameter selection.')
    assert len(files)==p['expected_files'] and sum(f['metadata']['sweepCount'] for f in files)==p['expected_sweeps']
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen 93 files / 2197 sweeps',sha(PLAN))


def run():
    if OUT.exists():raise FileExistsError('Preserve completed batch')
    p=json.loads(PLAN.read_text())
    for path,d in p['pins'].items():assert sha(ROOT/path)==d
    headers=json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text());lookup={r['member']:r for r in headers['records']}
    joins=json.loads((ROOT/'validation/apl-sk-workbook-join.json').read_text())['joins']
    results=[]
    for idx,member in enumerate(p['members']):
        f=lookup[member];path=ROOT/f['extracted_path'];assert sha(path)==f['sha256'];a=pyabf.ABF(str(path));assert a.adcUnits[0]=='mV'
        staircase=f['metadata']['protocol'].startswith('IC_FP');epnum=3 if staircase else 1
        e=f['raw_header_sections']['_epochPerDacSection'];ids=[i for i,d in enumerate(e['nDACNum']) if d==0]
        selected=[i for i in ids if e['nEpochNum'][i]==epnum];assert len(selected)==1;j=selected[0]
        current_channels=[i for i,u in enumerate(a.adcUnits) if u=='pA'];assert len(current_channels)<=1
        sweeps=[];rate=a.dataRate
        for n in a.sweepList:
            on=a.sweepPointCount//64+sum(e['lEpochInitDuration'][i]+n*e['lEpochDurationInc'][i] for i in ids if e['nEpochNum'][i]<epnum)
            off=on+e['lEpochInitDuration'][j]+n*e['lEpochDurationInc'][j];amplitude=e['fEpochInitLevel'][j]+n*e['fEpochLevelInc'][j]
            b0=on-round(.1*rate);p0=off-round(.1*rate);early0=on+round(.05*rate);early1=on+round(.1*rate)
            ah0=off+round(.005*rate);ah1=off+round(.6*rate);assert ah1<=a.sweepPointCount
            a.setSweep(n,channel=0);v=a.sweepY.astype(float);command=a.sweepC
            assert np.isfinite(v).all() and np.all(command[b0:on]==0) and np.all(command[on:off]==amplitude)
            baseline=float(v[b0:on].mean());plateau=float(v[p0:off].mean());early=float(v[early0:early1].mean())
            peak=on+int(np.argmax(v[on:early1]));trough=ah0+int(np.argmin(v[ah0:ah1]));recorded=None
            if current_channels:
                a.setSweep(n,channel=current_channels[0]);c=a.sweepY.astype(float);assert np.isfinite(c).all()
                delta=float(c[p0:off].mean()-c[b0:on].mean());tol=max(5.,.05*abs(amplitude))
                recorded=dict(baseline_pA=float(c[b0:on].mean()),plateau_pA=float(c[p0:off].mean()),delta_pA=delta,tolerance_pA=tol,within_tolerance=abs(delta-amplitude)<=tol)
            sweeps.append(dict(sweep=n,nominal_start_s=n*a.sweepIntervalSec,onset_sample=on,offset_sample=off,
                baseline_samples=[b0,on],plateau_samples=[p0,off],early_samples=[early0,early1],post_samples=[ah0,ah1],
                command_delta_pA=float(amplitude),recorded_current=recorded,baseline_voltage_mV=baseline,
                plateau_voltage_mV=plateau,plateau_delta_mV=plateau-baseline,early_delta_mV=early-baseline,
                plateau_minus_early_mV=plateau-early,first_100ms_peak_delta_mV=float(v[peak]-baseline),peak_time_from_onset_s=(peak-on)/rate,
                post_minimum_delta_mV=float(v[trough]-baseline),post_minimum_time_from_offset_s=(trough-off)/rate))
        linked=[dict(workbook=j['workbook'],sheet=j['sheet'],row=j['row'],cell=j['cell'],fly=j['fly'],state=j['state'],genotype=j['genotype']) for j in joins if member in j['matched_abf_members']]
        results.append(dict(file_index=idx,member=member,source_sha256=f['sha256'],protocol=f['metadata']['protocol'],
            source_timestamp=f['metadata']['abfDateTimeString'],sweep_interval_s=a.sweepIntervalSec,
            pulse_duration_s=(sweeps[0]['offset_sample']-sweeps[0]['onset_sample'])/rate,
            sample_rate_Hz=rate,current_channel=current_channels[0] if current_channels else None,adc_units=a.adcUnits,
            author_rows=linked,staircase=staircase,sweeps=sweeps))
    assert len(results)==p['expected_files'] and sum(len(f['sweeps']) for f in results)==p['expected_sweeps']
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),files=results,scope=p['scope']),indent=2,allow_nan=False)+'\n')
    print('Complete: all 93 files and 2197 sweeps')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
