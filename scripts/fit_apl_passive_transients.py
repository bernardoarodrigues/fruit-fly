"""Frozen complete passive-transient fits and conditional offset predictions."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
from apl_ephys_measurements import fit_step_exponential
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-passive-transient-plan.json'
OUT=ROOT/'validation/apl-passive-transient-results.json'
ARRAYS=ROOT/'validation/apl-passive-transient-traces.npz'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve frozen plan')
    source=json.loads((ROOT/'validation/apl-passive-measurement-plan.json').read_text())
    pins=['scripts/fit_apl_passive_transients.py','scripts/apl_ephys_measurements.py',
        'validation/apl-passive-measurement-plan.json','validation/apl-passive-measurements.json']
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_pins={s:sha(ROOT/s) for s in pins},
        files=source['files'],pyabf_version=pyabf.__version__,mean_fit_windows_s=[[.001,.050],[.005,.050],[.001,.100],[.005,.100]],
        primary_fit_window_s=[.005,.100],tau_bounds_s=[.0005,.2],minimum_voltage_span_mV=.2,
        prediction_window_s=[.005,.100],late_plateau_window_s=[.100,.400],
        expected_files=82,expected_sweep_fits=2132,expected_mean_fits=328,
        methods='Fit V_inf+B exp(-t/tau) to onset-relative voltage at full 10 kHz. Fit all 26 sweeps per file using 5-100 ms and each all-sweep mean using all four predeclared windows. No smoothing or per-cell window selection. Include tau-bound/low-span flags and all fits. Offset evaluation uses the onset-fit tau with the separately measured held baseline and late passive plateau: V_base+deltaV exp(-t_after_offset/tau). No parameter is optimized against offset recovery. This is conditional within-record prediction using measured endpoints, not a blind held-out animal test. Late-plateau prediction uses the actual fitted onset curve at 100-400 ms. Retain source identity and drug labels through prior artifacts; do not pool sweeps as independent animals.',
        scope='Descriptive single-pole somatic transient comparison and window sensitivity. Not physical membrane capacitance, channel identification or neural parameter promotion.')
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen',sha(PLAN))


def run():
    if OUT.exists() or ARRAYS.exists():raise FileExistsError('Preserve results')
    p=json.loads(PLAN.read_text())
    for path,d in p['source_pins'].items():assert sha(ROOT/path)==d
    assert pyabf.__version__==p['pyabf_version']
    passive=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
    records=[];arrays={}
    def fit(y,t,window):
        return fit_step_exponential(t,y,onset_s=0.,fit_window_s=window,tau_bounds_s=p['tau_bounds_s'],minimum_voltage_span_mV=p['minimum_voltage_span_mV'])
    for f,old in zip(p['files'],passive['files'],strict=True):
        assert old['member']==f['member'];path=ROOT/f['extracted_path'];assert sha(path)==f['sha256']
        a=pyabf.ABF(str(path));on=old['onset_sample'];off=old['offset_sample'];rate=a.dataRate
        time=np.arange(4001)/rate;short_time=time[:1001]
        ys=[];recoveries=[];sweeps=[]
        for n in a.sweepList:
            a.setSweep(n,channel=0);v=a.sweepY;assert np.isfinite(v).all()
            onset=v[on:on+4001].astype(float);offset=v[off:off+1001].astype(float)
            ys.append(onset);recoveries.append(offset)
            result=fit(onset[:1001],short_time,p['primary_fit_window_s'])
            sweeps.append(dict(sweep=n,fit=result))
        avg=np.mean(ys,axis=0);recovery=np.mean(recoveries,axis=0)
        base=float(np.mean([s['commanded']['held_baseline_mV'] for s in old['sweeps']]))
        delta=float(np.mean([s['commanded']['delta_voltage_mV'] for s in old['sweeps']]))
        fits=[]
        for window in p['mean_fit_windows_s']:
            result=fit(avg[:1001],short_time,window)
            evaluations=None
            if result['status']=='fitted':
                tau=result['tau_s'];prediction=base+delta*np.exp(-short_time/tau)
                offmask=(short_time>=p['prediction_window_s'][0])&(short_time<p['prediction_window_s'][1])
                latemask=(time>=p['late_plateau_window_s'][0])&(time<p['late_plateau_window_s'][1])
                lateprediction=result['asymptote_mV']+result['exponential_coefficient_mV']*np.exp(-time/tau)
                rmse=float(np.sqrt(np.mean((recovery[offmask]-prediction[offmask])**2)))
                evaluations=dict(offset_rmse_mV=rmse,offset_rmse_fraction_of_passive_step=rmse/abs(delta) if delta else None,
                    late_plateau_rmse_mV=float(np.sqrt(np.mean((avg[latemask]-lateprediction[latemask])**2))),
                    fitted_onset_minus_held_baseline_mV=result['extrapolated_onset_mV']-base,
                    fitted_asymptote_minus_measured_plateau_mV=result['asymptote_mV']-(base+delta))
            fits.append(dict(window_s=window,fit=result,evaluation=evaluations))
        idx=old['file_index'];arrays[f'f{idx}_onset_voltage_mV']=avg;arrays[f'f{idx}_offset_voltage_mV']=recovery
        records.append(dict(file_index=idx,member=f['member'],source_sha256=f['sha256'],mean_fits=fits,sweep_fits=sweeps,
                            held_baseline_mV=base,passive_delta_mV=delta))
    arrays['onset_time_s']=time;arrays['offset_time_s']=short_time
    np.savez_compressed(ARRAYS,**arrays)
    assert len(records)==p['expected_files'] and sum(len(r['sweep_fits']) for r in records)==p['expected_sweep_fits']
    assert sum(len(r['mean_fits']) for r in records)==p['expected_mean_fits']
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),files=records,
        arrays=dict(path=str(ARRAYS.relative_to(ROOT)),sha256=sha(ARRAYS),bytes=ARRAYS.stat().st_size),scope=p['scope']),indent=2,allow_nan=False)+'\n')
    print('Complete: 2132 sweep fits and 328 mean fits with conditional offset evaluations')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
