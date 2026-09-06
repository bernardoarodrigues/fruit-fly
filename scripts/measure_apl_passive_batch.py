"""Freeze and execute the complete passive-step measurement batch.

No parameter fitting. The source archive and workbook identities remain intact.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
from apl_ephys_measurements import passive_resistance

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-passive-measurement-plan.json'
RESULT=ROOT/'validation/apl-passive-measurements.json'
ARRAYS=ROOT/'validation/apl-passive-measurement-traces.npz'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve frozen plan')
    headers=json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text())
    join=json.loads((ROOT/'validation/apl-sk-workbook-join.json').read_text())
    files=[r for r in headers['records'] if r['metadata']['protocol'].startswith('IC_FP')]
    assert len(files)==82 and all(r['metadata']['sweepCount']==26 for r in files)
    pins=['scripts/measure_apl_passive_batch.py','scripts/apl_ephys_measurements.py',
          'validation/apl-sk-abf-headers.json','validation/apl-sk-workbook-join.json']
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_pins={p:sha(ROOT/p) for p in pins},
        pyabf_version=pyabf.__version__,expected_files=82,expected_sweeps=2132,
        baseline_duration_s=.1,plateau_duration_s=.1,minimum_recorded_step_pA=5.,
        delivery_absolute_tolerance_pA=5.,trace_stride_samples=10,
        methods='Every sweep in every APL firing-pattern file. ADC 0 must be mV. DAC0 epoch 1 is the -50 pA, 500 ms passive pulse; verify pyABF epoch boundaries against header duration sums and sweepPointCount//64. Mean voltage/current in the last 100 ms before onset and last 100 ms before offset. Retain commanded-current resistance separately from recorded-pA resistance. Missing recorded-pA channel never inferred from mV. The 5 pA floor and delivery tolerance are declared diagnostic conventions, not published biological exclusion rules. Preserve all sweeps and within-file variation; no smoothing, tau fit or source-matching selection. Plot traces are all-sweep means decimated to 1 ms without analysis use.',
        scope='Descriptive protocol/delivery/passive measurement only. No physiological parameter selection, calibration/evaluation fit or neural runtime change. Held voltage is not RMP. Junction correction is not applied; voltage differences cancel a constant offset.',
        files=files,author_rows=join['joins'])
    PLAN.write_text(json.dumps(plan,indent=2)+'\n')
    print('Frozen 82 files / 2132 sweeps:',sha(PLAN))


def run():
    if RESULT.exists() or ARRAYS.exists():raise FileExistsError('Preserve previous results')
    plan=json.loads(PLAN.read_text())
    for p,digest in plan['source_pins'].items():assert sha(ROOT/p)==digest,p
    assert pyabf.__version__==plan['pyabf_version']
    output=[];arrays={}
    for file_index,r in enumerate(plan['files']):
        path=ROOT/r['extracted_path'];assert sha(path)==r['sha256']
        a=pyabf.ABF(str(path));m=r['metadata'];assert a.adcUnits[0]=='mV'
        pA_channels=[i for i,u in enumerate(a.adcUnits) if u=='pA']
        if len(pA_channels)>1:raise ValueError('Ambiguous recorded current channel')
        e=r['raw_header_sections']['_epochPerDacSection']
        selected=[i for i,d in enumerate(e['nDACNum']) if d==0]
        epoch=[i for i in selected if e['nEpochNum'][i]==1]
        assert len(epoch)==1;ep=epoch[0]
        assert e['nEpochType'][ep]==1 and e['fEpochInitLevel'][ep]==-50
        assert e['fEpochLevelInc'][ep]==0 and e['lEpochDurationInc'][ep]==0
        onset=a.sweepPointCount//64+sum(e['lEpochInitDuration'][i] for i in selected if e['nEpochNum'][i]<1)
        offset=onset+e['lEpochInitDuration'][ep]
        assert offset-onset==int(.5*a.dataRate)
        width=int(plan['baseline_duration_s']*a.dataRate);pw=int(plan['plateau_duration_s']*a.dataRate)
        bs=slice(onset-width,onset);ps=slice(offset-pw,offset)
        trace_indices=np.arange(onset-width,offset+width,plan['trace_stride_samples'])
        vs=[];ics=[];sweeps=[]
        for sweep in a.sweepList:
            a.setSweep(sweep,channel=0)
            epochs=a.sweepEpochs
            assert any(p1==onset and p2==offset and level==-50 for p1,p2,level in zip(epochs.p1s,epochs.p2s,epochs.levels))
            v=a.sweepY.copy();t=a.sweepX.copy();command=a.sweepC.copy()
            assert np.isfinite(v).all() and np.isfinite(command).all()
            assert np.all(command[bs]==0) and np.all(command[ps]==-50)
            windows=dict(baseline_window_s=(float(t[bs.start]),float(t[bs.stop])),plateau_window_s=(float(t[ps.start]),float(t[ps.stop])))
            commanded=passive_resistance(t,v,command,minimum_current_step_pA=0,**windows)
            recorded=None
            if pA_channels:
                a.setSweep(sweep,channel=pA_channels[0]);current=a.sweepY.copy()
                recorded=passive_resistance(t,v,current,minimum_current_step_pA=plan['minimum_recorded_step_pA'],**windows)
                ics.append(current[trace_indices])
            vs.append(v[trace_indices])
            sweeps.append(dict(sweep=sweep,commanded=commanded,recorded=recorded,
                recorded_delivery_within_tolerance=abs(recorded['delta_current_pA']+50)<=plan['delivery_absolute_tolerance_pA'] if recorded else None,
                plateau_half_change_mV=float(v[offset-pw//2:offset].mean()-v[offset-pw:offset-pw//2].mean())))
        linked=[j for j in plan['author_rows'] if r['member'] in j['matched_abf_members']]
        filename_id=Path(r['member']).name.split('_')[0]
        rows=[dict(workbook=j['workbook'],sheet=j['sheet'],row=j['row'],cell=j['cell'],fly=j['fly'],state=j['state'],genotype=j['genotype'],
                   filename_prefix_agrees=filename_id==j['cell'],directory_exact_match=r['member'] in j['directory_id_matches']) for j in linked]
        arrays[f'f{file_index}_relative_time_s']=(trace_indices-onset)/a.dataRate
        arrays[f'f{file_index}_mean_voltage_mV']=np.mean(vs,axis=0)
        if ics:arrays[f'f{file_index}_mean_recorded_current_pA']=np.mean(ics,axis=0)
        output.append(dict(file_index=file_index,member=r['member'],sha256=r['sha256'],linked_author_rows=rows,
            adc_names=a.adcNames,adc_units=a.adcUnits,recorded_current_channel=pA_channels[0] if pA_channels else None,
            onset_sample=onset,offset_sample=offset,baseline_sample_range=[bs.start,bs.stop],plateau_sample_range=[ps.start,ps.stop],
            sample_rate_Hz=a.dataRate,sweeps=sweeps))
    assert len(output)==plan['expected_files'] and sum(len(r['sweeps']) for r in output)==plan['expected_sweeps']
    np.savez_compressed(ARRAYS,**arrays)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),
        arrays=dict(path=str(ARRAYS.relative_to(ROOT)),sha256=sha(ARRAYS),bytes=ARRAYS.stat().st_size),
        file_count=len(output),sweep_count=sum(len(r['sweeps']) for r in output),files=output,
        scope=plan['scope'])
    RESULT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('Complete:',len(output),'files;',result['sweep_count'],'sweeps')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    freeze() if args.freeze else run()
