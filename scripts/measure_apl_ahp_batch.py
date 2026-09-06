"""Freeze and measure all dedicated 2 nA APL AHP recordings, without fitting."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
from apl_ephys_measurements import ahp_recovery
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-ahp-measurement-plan.json'
OUT=ROOT/'validation/apl-ahp-measurements.json'
ARRAYS=ROOT/'validation/apl-ahp-measurement-traces.npz'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve frozen plan')
    h=json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text())
    j=json.loads((ROOT/'validation/apl-sk-workbook-join.json').read_text())
    files=[r for r in h['records'] if 'AHP' in r['metadata']['protocol'] and '/APL_SD_APL_SKRNAi_' in r['member']]
    rows=[r for r in j['joins'] if r['sheet']=='AHP(2nA)']
    assert len(files)==len(rows)==11
    pins=['scripts/measure_apl_ahp_batch.py','scripts/apl_ephys_measurements.py','validation/apl-sk-abf-headers.json','validation/apl-sk-workbook-join.json']
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_pins={x:sha(ROOT/x) for x in pins},
        pyabf_version=pyabf.__version__,files=files,author_rows=rows,expected_sweeps=sum(r['metadata']['sweepCount'] for r in files),
        baseline_relative_to_onset_s=[-.4,-.05],post_offset_start_s=[.005,.020],post_offset_end_s=2.8,
        minimum_amplitude_mV=.2,delivery_tolerance_pA=100.,plot_stride_samples=10,
        methods='Measure all sweeps in all eleven dedicated 2 nA files. Fixed baseline 400 to 50 ms before pulse onset. Two post-offset windows start at 5 and 20 ms and end at 2.8 s. Retain the minimum voltage, signed AHP magnitude, all 70/30 percent crossings and their ambiguity/incomplete/weak flags; no smoothing or exponential fit. The 0.2 mV amplitude floor and 100 pA delivery tolerance are declared diagnostic conventions, not author exclusions. Apply identical measurements to each raw sweep and the within-cell all-sweep mean. Do not choose a best sweep or treat sweeps as independent animals. Voltage differences receive no liquid-junction subtraction. Plot data are decimated to 1 ms; full 10 kHz data are measured.',
        scope='Complete descriptive active-response measurement batch; not SK conductance fitting, physiological promotion or a source-blind evaluation.')
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen',len(files),'files',p['expected_sweeps'],'sweeps',sha(PLAN))


def run():
    if OUT.exists() or ARRAYS.exists():raise FileExistsError('Preserve completed batch')
    p=json.loads(PLAN.read_text())
    for x,digest in p['source_pins'].items():assert sha(ROOT/x)==digest
    assert pyabf.__version__==p['pyabf_version']
    results=[];arrays={}
    for file_index,f in enumerate(p['files']):
        path=ROOT/f['extracted_path'];assert sha(path)==f['sha256']
        a=pyabf.ABF(str(path));assert a.adcUnits[0]=='mV'
        epoch=f['raw_header_sections']['_epochPerDacSection'];ids=[i for i,d in enumerate(epoch['nDACNum']) if d==0]
        active=[i for i in ids if epoch['fEpochInitLevel'][i]==2000];assert len(active)==1;i=active[0]
        assert epoch['nEpochType'][i]==1 and epoch['fEpochLevelInc'][i]==0 and epoch['lEpochDurationInc'][i]==0
        onset=a.sweepPointCount//64+sum(epoch['lEpochInitDuration'][j] for j in ids if epoch['nEpochNum'][j]<epoch['nEpochNum'][i])
        offset=onset+epoch['lEpochInitDuration'][i];assert offset-onset==7500 and a.dataRate==10000
        b0,b1=[onset+round(x*a.dataRate) for x in p['baseline_relative_to_onset_s']]
        windows=[[offset+round(x*a.dataRate),offset+round(p['post_offset_end_s']*a.dataRate)] for x in p['post_offset_start_s']]
        indices=np.arange(b0,windows[0][1],p['plot_stride_samples']);current_channels=[c for c,u in enumerate(a.adcUnits) if u=='pA'];assert len(current_channels)<=1
        linked=[r for r in p['author_rows'] if f['member'] in r['matched_abf_members']];assert len(linked)==1
        total=np.zeros(a.sweepPointCount);sweeps=[];traces=[]
        for sweep in a.sweepList:
            a.setSweep(sweep,channel=0);t=a.sweepX.copy();v=a.sweepY.copy();assert np.isfinite(v).all()
            assert any(x==onset and y==offset and level==2000 for x,y,level in zip(a.sweepEpochs.p1s,a.sweepEpochs.p2s,a.sweepEpochs.levels))
            assert np.all(a.sweepC[b0:b1]==0) and np.all(a.sweepC[onset:offset]==2000)
            measurements=[ahp_recovery(t,v,baseline_window_s=(float(t[b0]),float(t[b1])),post_offset_window_s=(float(t[x]),float(t[y])),minimum_amplitude_mV=p['minimum_amplitude_mV']) for x,y in windows]
            delivery=None
            if current_channels:
                a.setSweep(sweep,channel=current_channels[0]);c=a.sweepY;assert np.isfinite(c).all()
                di=float(c[offset-1000:offset].mean()-c[b0:b1].mean())
                delivery=dict(delta_current_pA=di,within_tolerance=abs(di-2000)<=p['delivery_tolerance_pA'])
            sweeps.append(dict(sweep=sweep,measurements=measurements,delivery=delivery));traces.append(v[indices]);total+=v
        avg=total/a.sweepCount
        averages=[ahp_recovery(t,avg,baseline_window_s=(float(t[b0]),float(t[b1])),post_offset_window_s=(float(t[x]),float(t[y])),minimum_amplitude_mV=p['minimum_amplitude_mV']) for x,y in windows]
        arrays[f'f{file_index}_time_from_offset_s']=(indices-offset)/a.dataRate;arrays[f'f{file_index}_voltage_mV']=np.array(traces)
        results.append(dict(file_index=file_index,member=f['member'],source_sha256=f['sha256'],author_row=linked[0],
            baseline_sample_range=[b0,b1],post_sample_ranges=windows,onset_sample=onset,offset_sample=offset,
            adc_units=a.adcUnits,current_channel=current_channels[0] if current_channels else None,sample_rate_Hz=a.dataRate,
            sweep_interval_s=a.sweepIntervalSec,sweeps=sweeps,mean_trace_measurements=averages))
    assert sum(len(f['sweeps']) for f in results)==p['expected_sweeps']
    np.savez_compressed(ARRAYS,**arrays)
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),
        arrays=dict(path=str(ARRAYS.relative_to(ROOT)),sha256=sha(ARRAYS),bytes=ARRAYS.stat().st_size),files=results,
        scope=p['scope']),indent=2,allow_nan=False)+'\n');print('Completed',len(results),'files',p['expected_sweeps'],'sweeps')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
