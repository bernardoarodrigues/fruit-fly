"""Freeze and compare complete single/two-mode passive response models."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from apl_passive_kernels import fit_modes,response
ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-passive-modes-plan.json'
OUT=ROOT/'validation/apl-passive-modes-results.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze():
    if PLAN.exists():raise FileExistsError('Preserve fixed plan')
    source=json.loads((ROOT/'validation/apl-passive-transient-results.json').read_text())
    files=['scripts/compare_apl_passive_modes.py','scripts/apl_passive_kernels.py','tests/test_apl_passive_kernels.py',
           'validation/apl-passive-transient-results.json',source['arrays']['path']]
    p=dict(created_utc=datetime.now(timezone.utc).isoformat(),pins={x:sha(ROOT/x) for x in files},
        windows_s=[[.001,.05],[.005,.05],[.001,.1],[.005,.1]],tau_bounds_s=[.0005,.2],grid_points=25,
        expected_files=82,expected_fits=656,evaluation_window_s=[.005,.1],pulse_s=.5,
        synthetic_tests=dict(command='.venv/bin/python -m pytest -q tests/test_apl_passive_kernels.py',passed=2),
        methods='Use the exact complete mean-voltage traces and measured held baseline/passive step from the prior batch. Fit single and positive two-mode onset responses on each of four windows. Each basis is divided by its exact discrete mean step response at samples 4000:5000 (0.4-0.5 s); the mixture therefore matches the independently measured late plateau. Alpha is the fraction of plateau response; steady-state weights/gain are reported separately. Profile alpha on [0,1], search 25x25 ordered log-tau grid and refine four separated low-cost seeds. Keep the single-mode boundary candidate. Predict finite-pulse switch-off using the same parameters and exact 500 ms pulse. No offset data enter fitting, model selection or parameter bounds. All windows retained; prior offset plots have been seen, so this is not a blind test. No individual-sweep or cross-animal fit in this comparison.',
        scope='Constrained passive observational model comparison. Component time constants are not identified channels, anatomical compartments or membrane capacitance. No neural runtime changes.')
    PLAN.write_text(json.dumps(p,indent=2)+'\n');print('Frozen',sha(PLAN))


def run():
    if OUT.exists():raise FileExistsError('Preserve completed batch')
    p=json.loads(PLAN.read_text())
    for path,d in p['pins'].items():assert sha(ROOT/path)==d
    source=json.loads((ROOT/'validation/apl-passive-transient-results.json').read_text());a=np.load(ROOT/source['arrays']['path'])
    t=a['onset_time_s'];off=a['offset_time_s'];maskoff=(off>=p['evaluation_window_s'][0])&(off<p['evaluation_window_s'][1])
    files=[]
    for f in source['files']:
        on=(a[f"f{f['file_index']}_onset_voltage_mV"]-f['held_baseline_mV'])/f['passive_delta_mV']
        actualoff=(a[f"f{f['file_index']}_offset_voltage_mV"]-f['held_baseline_mV'])/f['passive_delta_mV']
        variants=[]
        for window in p['windows_s']:
            mask=(t>=window[0])&(t<window[1]);models=fit_modes(t[mask],on[mask],p['tau_bounds_s'],p['grid_points'])
            for name,fit in models.items():
                error=response(off,fit,offset=True)-actualoff
                fit['offset_rmse_fraction_of_passive_step']=float(np.sqrt(np.mean(error[maskoff]**2)))
                fit['offset_rmse_mV']=fit['offset_rmse_fraction_of_passive_step']*abs(f['passive_delta_mV'])
                fit['onset_rmse_mV']=float(np.sqrt(fit['fit_mse'])*abs(f['passive_delta_mV']))
            variants.append(dict(window_s=window,models=models))
        files.append(dict(file_index=f['file_index'],member=f['member'],variants=variants))
    assert len(files)==p['expected_files'] and sum(len(v['models']) for f in files for v in f['variants'])==p['expected_fits']
    OUT.write_text(json.dumps(dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),files=files,scope=p['scope']),indent=2,allow_nan=False)+'\n')
    print('Completed 656 fits across 82 files and all four windows')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args();freeze() if args.freeze else run()
