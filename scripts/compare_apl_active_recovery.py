"""Frozen fly-level conditional transfer of a slow outward-current candidate."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pyabf
from scipy.optimize import minimize_scalar
from fruitfly.graded_apl import post_offset_voltage
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-active-recovery-plan.json'
OUT=ROOT/'validation/apl-active-recovery-results.json'
ARRAYS=ROOT/'validation/apl-active-recovery-arrays.npz'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve plan')
    ahp=json.loads((ROOT/'validation/apl-ahp-measurements.json').read_text())
    headers=json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text())
    passive=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
    rows=[]
    for f in ahp['files']:
        identity=f['author_row'];candidates=[p for p in passive['files'] if any(j['cell']==identity['cell'] for j in p['linked_author_rows'])]
        assert len(candidates)==1
        source=next(h for h in headers['records'] if h['member']==f['member'])
        rows.append(dict(cell=identity['cell'],fly=identity['fly'],group='RNAi' if 'dSK' in identity['genotype'] else 'control',
            member=f['member'],path=source['extracted_path'],sha256=source['sha256'],passive_file_index=candidates[0]['file_index'],
            baseline_sample_range=f['baseline_sample_range'],offset_sample=f['offset_sample']))
    assert len({r['fly'] for r in rows})==11
    for group in ('RNAi','control'):
        ranked=sorted([r for r in rows if r['group']==group],key=lambda r:hashlib.sha256(('apl-active-v1:'+r['fly']).encode()).hexdigest())
        for rank,row in enumerate(ranked):row['partition']='calibration' if rank<3 else 'evaluation'
    pins=['scripts/compare_apl_active_recovery.py','fruitfly/graded_apl.py','tests/test_graded_apl.py',
          'validation/apl-ahp-measurements.json','validation/apl-sk-abf-headers.json',
          'validation/apl-passive-measurements.json','validation/apl-passive-modes-results.json']
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),pins={s:sha(ROOT/s) for s in pins},cells=rows,
        outward_tau_bounds_s=[.05,3.],fit_window_s=[.05,.8],evaluation_window_s=[.05,2.8],late_window_s=[.8,2.8],
        sample_rate_Hz=10000,bin_samples=10,initial_voltage_window_s=[-.001,0.],passive_variants=[0,1,2,3],
        numerical_tests=dict(command='.venv/bin/python -m pytest -q tests/test_graded_apl.py',passed=4),
        methods='Keep each matched cell passive resistance and both time constants fixed for all four prior window variants. Initial voltage deflection is measured from the final 1 ms before offset, relative to the source baseline; distribute it among modes according to their finite 750 ms passive pulse contributions. This modal allocation is an explicit assumption. Current after offset is zero; the outward current starts at a nonnegative group-shared amplitude and decays with one shared tau. Fit three parameters (control amplitude, RNAi amplitude, common tau) to equal-cell-weight mean waveforms from three hash-selected flies per group on 50-800 ms. At fixed tau, each amplitude is a nonnegative scalar least-squares solve; search 61 log-tau values and refine every local minimum, retaining bounds. Average ten consecutive 10 kHz samples into nonoverlapping 1 ms bins and apply exactly the same bin average to predictions. This is a declared waveform observation rule, not threshold-crossing smoothing. Score all eleven cells and the 800-2800 ms tail, retaining five excluded-from-fit evaluation flies. All waveforms were seen earlier; this is a retrospective conditional transfer test, not blind validation. Initial conditions and passive fits use measurements from each evaluation cell; it is not a prediction of the 2 nA depolarizing phase.',
        scope='Experimental graded state realization and conditional active-recovery comparison only. No inferred calcium-to-outward-current drive, synaptic release rule, absolute rest or recurrent promotion.')
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen six calibration / five evaluation flies',sha(PLAN))


def run():
    if OUT.exists() or ARRAYS.exists():raise FileExistsError('Preserve results')
    p=json.loads(PLAN.read_text())
    for path,d in p['pins'].items():assert sha(ROOT/path)==d
    modes=json.loads((ROOT/'validation/apl-passive-modes-results.json').read_text())
    passive=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
    t=np.arange(28000)/10000;bin_t=t.reshape(-1,10).mean(axis=1)
    prepared=[];arrays={'time_s':bin_t};allfits=[];scores=[]
    for idx,c in enumerate(p['cells']):
        path=ROOT/c['path'];assert sha(path)==c['sha256'];a=pyabf.ABF(str(path));b0,b1=c['baseline_sample_range'];off=c['offset_sample']
        observations=[];initial=[]
        for sweep in a.sweepList:
            a.setSweep(sweep,channel=0);v=a.sweepY.astype(float);baseline=float(v[b0:b1].mean())
            observations.append((v[off:off+28000]-baseline).reshape(-1,10).mean(axis=1));initial.append(v[off-10:off].mean()-baseline)
        obs=np.mean(observations,axis=0);v0=float(np.mean(initial));arrays[f'c{idx}_observed_sweeps_mV']=np.array(observations);arrays[f'c{idx}_observed_mean_mV']=obs
        source=passive['files'][c['passive_file_index']]
        rin=float(np.mean([s['commanded']['resistance_MOhm'] for s in source['sweeps']]))
        prepared.append(dict(**c,index=idx,observation=obs,initial_mV=v0,resistance_MOhm=rin))
    fitmask=(bin_t>=.05)&(bin_t<.8);fullmask=(bin_t>=.05)&(bin_t<2.8);late=(bin_t>=.8)&(bin_t<2.8)
    for variant in p['passive_variants']:
        bases=[]
        for c in prepared:
            m=modes['files'][c['passive_file_index']]['variants'][variant]['models']['two']
            tau=np.array([m['tau_fast_s'],m['tau_slow_s']]);alpha=m['alpha']
            factor=np.array([np.mean(1-np.exp(-np.arange(4000,5000)/10000/z)) for z in tau])
            r=c['resistance_MOhm']*np.array([alpha,1-alpha])/factor
            weights=r*(1-np.exp(-.75/tau));x0=c['initial_mV']*weights/weights.sum()
            passive_prediction=post_offset_voltage(t,x0,r,tau,0.,1.).reshape(-1,10).mean(axis=1)
            bases.append(dict(tau=tau,r=r,x0=x0,passive=passive_prediction))
        def profile(outward_tau,save=False):
            kernels=[-post_offset_voltage(t,[0.,0.],b['r'],b['tau'],1.,outward_tau).reshape(-1,10).mean(axis=1) for b in bases]
            amps={};loss=0.
            for group in ('control','RNAi'):
                indices=[i for i,c in enumerate(prepared) if c['group']==group and c['partition']=='calibration']
                numerator=sum(np.dot(kernels[i][fitmask],(bases[i]['passive']-prepared[i]['observation'])[fitmask]) for i in indices)
                denominator=sum(np.dot(kernels[i][fitmask],kernels[i][fitmask]) for i in indices)
                amps[group]=max(0.,float(numerator/denominator))
            predictions=[b['passive']-amps[c['group']]*k for b,c,k in zip(bases,prepared,kernels)]
            loss=float(np.mean([np.mean((predictions[i][fitmask]-c['observation'][fitmask])**2) for i,c in enumerate(prepared) if c['partition']=='calibration']))
            return (loss,amps,predictions) if save else loss
        grid=np.geomspace(*p['outward_tau_bounds_s'],61);values=[profile(z) for z in grid];candidates=list(zip(values,grid))
        for i in range(1,len(grid)-1):
            if values[i]<=values[i-1] and values[i]<=values[i+1]:
                result=minimize_scalar(lambda z:profile(np.exp(z)),bounds=np.log(grid[[i-1,i+1]]),method='bounded',options={'xatol':1e-9})
                assert result.success;candidates.append((result.fun,float(np.exp(result.x))))
        _,outward_tau=min(candidates);loss,amps,preds=profile(outward_tau,True)
        allfits.append(dict(variant=variant,outward_tau_s=float(outward_tau),initial_outward_pA=amps,calibration_mse_mV2=loss,
                           tau_at_bound=bool(outward_tau in p['outward_tau_bounds_s'])))
        for idx,(c,b,pred) in enumerate(zip(prepared,bases,preds)):
            arrays[f'v{variant}_c{idx}_passive_mV']=b['passive'];arrays[f'v{variant}_c{idx}_active_mV']=pred
            metrics={}
            for name,mask in [('early',fitmask),('full',fullmask),('late',late)]:
                metrics[name]=dict(passive_rmse_mV=float(np.sqrt(np.mean((b['passive'][mask]-c['observation'][mask])**2))),
                                   active_rmse_mV=float(np.sqrt(np.mean((pred[mask]-c['observation'][mask])**2))))
            scores.append(dict(variant=variant,cell=c['cell'],fly=c['fly'],partition=c['partition'],group=c['group'],
                initial_voltage_mV=c['initial_mV'],resistance_modes_MOhm=b['r'].tolist(),passive_tau_s=b['tau'].tolist(),initial_modes_mV=b['x0'].tolist(),metrics=metrics))
    np.savez_compressed(ARRAYS,**arrays)
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),fits=allfits,scores=scores,
        arrays=dict(path=str(ARRAYS.relative_to(ROOT)),sha256=sha(ARRAYS),bytes=ARRAYS.stat().st_size),scope=p['scope']),indent=2,allow_nan=False)+'\n')
    print('Completed four calibrated variants and all 44 cell/variant predictions')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
