#!/usr/bin/env python3
"""Compare extracted Fig8F means with already saved, unfitted scalar predictions.

This reads observations/predictions only; it runs no neural or synapse model.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/'validation/orn-pn-depression-comparison'
POINTS = ROOT/'validation/orn-pn-depression-fig8f-points.csv'
PREDICTIONS = ROOT/'validation/synaptic-depression-reference-arrays.npz'


def out(suffix):
    return Path(str(PREFIX)+suffix)


def record(path):
    b = Path(path).read_bytes()
    return {'path': str(Path(path).relative_to(ROOT)), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}


def write(path, obj):
    with Path(path).open('x') as f:
        json.dump(obj, f, indent=2, allow_nan=False); f.write('\n')


def prepare():
    paths = [Path(__file__), POINTS, PREDICTIONS,
             ROOT/'validation/orn-pn-depression-fig8f-plan.json',
             ROOT/'validation/orn-pn-depression-fig8f-results.json',
             ROOT/'validation/orn-pn-depression-fig8f-independent-review.json',
             ROOT/'validation/synaptic-depression-reference-plan.json',
             ROOT/'validation/synaptic-depression-reference-results.json']
    for name in ['orn-pn-depression-fig8f-results.json', 'orn-pn-depression-fig8f-independent-review.json']:
        assert json.loads((ROOT/'validation'/name).read_text())['passed']
    write(out('-plan.json'), {
        'created_utc': datetime.now(timezone.utc).isoformat(), 'inputs': [record(p) for p in paths],
        'method': 'Match by frequency and ordinal test event. Retain all43 source rows; exclude three unresolved shared initial means from residuals. Compare40 noninitial estimates against100*saved normalized efficacy and a static100-percent null. No parameter search or gain fit.',
        'metrics': 'Per-frequency unweighted RMSE, MAE and signed residual in percentage points. Raster sensitivity bounds form a conservative Cartesian envelope over individual marker intervals, not confidence intervals or necessarily attainable joint calibrations: axis anchors couple the points. Do not use SEM as independent point weights.',
        'reference': 'Previously frozen Abbott rat-cortex reference f=.75, recovery=.3s, normalized to first test event after declared7Hz/4s baseline; predictions predate this extraction.',
        'limits': ['A conditional normalized-shape comparison, not absolute EPSC/EPSP calibration, a fit or a biological pass/fail.',
                   'Comparison assumes the source initial-amplitude denominator corresponds to the reference first-test-event denominator; exact experimental baseline/test phase and preprocessing are not recovered.',
                   'Shared6-cell cohort and normalization make plotted points dependent; graphical envelopes and SEM are distinct uncertainties.',
                   'Initial means and unresolved SEM stay missing. Negative graphical means remain as drawn; no clipping or sign interpretation.',
                   'FemaleVM2 does not calibrate maleVM7d or other cell classes. No runtime, neural simulation, causal intervention or promotion.']})
    print(json.dumps(record(out('-plan.json'))))


def compare():
    if any(out(s).exists() for s in ['-results.json','-rows.csv','-figure.png']):
        raise FileExistsError('Preserve first comparison outputs')
    plan = json.loads(out('-plan.json').read_text()); plan_record = record(out('-plan.json'))
    for r in plan['inputs']:
        assert record(ROOT/r['path']) == r, r['path']
    rows = list(csv.DictReader(POINTS.open()))
    with np.load(PREDICTIONS, allow_pickle=False) as z:
        pred = {r: 100*z[f'train_{r}_normalized_test_amplitude'] for r in [15,20,50]}
    records = []; summaries = []
    for rate in [15,20,50]:
        chosen = [r for r in rows if int(r['frequency_hz']) == rate]
        assert [int(r['point_ordinal']) for r in chosen] == list(range(len(pred[rate])))
        for r in chosen:
            n = int(r['point_ordinal']); observed = float(r['mean_percent_initial']) if r['mean_percent_initial'] else None
            assert (observed is None) == (n == 0)
            records.append(dict(frequency_hz=rate, point_ordinal=n, source_time_ms=float(r['time_ms']),
                observed_percent=observed, mean_status=r['mean_status'],
                sem_percent=float(r['sem_percent_initial']) if r['sem_percent_initial'] else None,
                error_low_percent=float(r['error_low_percent_initial']) if r['error_low_percent_initial'] else None,
                error_high_percent=float(r['error_high_percent_initial']) if r['error_high_percent_initial'] else None,
                graphical_mean_bounds=json.loads(r['marker_sensitivity_percent_initial']),
                reference_percent=float(pred[rate][n]), static_percent=100.,
                reference_minus_observed=None if observed is None else float(pred[rate][n]-observed),
                static_minus_observed=None if observed is None else 100.-observed))
        usable = [r for r in records if r['frequency_hz']==rate and r['observed_percent'] is not None]
        observed = np.array([r['observed_percent'] for r in usable])
        lower,upper = np.array([r['graphical_mean_bounds'] for r in usable]).T
        summary = dict(frequency_hz=rate, compared_means=len(usable), missing_initial_means=1, metrics={})
        for model in ['reference','static']:
            p = np.array([r[model+'_percent'] for r in usable]); residual = p-observed
            nearest = np.maximum(np.maximum(lower-p,p-upper),0)
            furthest = np.maximum(np.abs(p-lower),np.abs(p-upper))
            summary['metrics'][model] = dict(rmse_percentage_points=float(np.sqrt(np.mean(residual**2))),
                mae_percentage_points=float(np.mean(np.abs(residual))), mean_signed_error_percentage_points=float(residual.mean()),
                conservative_cartesian_graphical_rmse_envelope=[float(np.sqrt(np.mean(nearest**2))),float(np.sqrt(np.mean(furthest**2)))])
        summaries.append(summary)
    assert len(records)==43 and sum(r['observed_percent'] is not None for r in records)==40
    with out('-rows.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4.8),sharey=True)
    for ax,rate in zip(axes,[15,20,50]):
        rr=[r for r in records if r['frequency_hz']==rate]; n=np.arange(len(rr))
        ax.plot(n,[r['reference_percent'] for r in rr],color='#326aab',label='Fixed Abbott reference')
        ax.axhline(100,color='#888888',ls='--',label='Static null')
        for r in rr[1:]:
            error = None if r['sem_percent'] is None else np.array([[r['observed_percent']-r['error_low_percent']],
                                                                   [r['error_high_percent']-r['observed_percent']]])
            if error is not None:
                assert np.all(error >= 0)
            ax.errorbar(r['point_ordinal'],r['observed_percent'],yerr=error,fmt='o',ms=4,color='#202020',capsize=2)
        ax.set(title=f'{rate} Hz · {len(rr)-1} resolved means',xlabel='Test-event ordinal (first = 0)',ylim=(-15,110))
        ax.grid(alpha=.15)
    axes[0].set_ylabel('uEPSC amplitude (% initial)')
    axes[0].scatter([],[],color='#202020',s=16,label='Female VM2 raster means')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.88),ncol=3,frameon=False)
    fig.suptitle('Local depression comparison: saved predictions, no fitted parameters',y=.98)
    fig.subplots_adjust(top=.73,bottom=.24,wspace=.15)
    fig.text(.06,.10,'Bars: resolved drawn SEM only; missing bars remain absent. Three shared initial means are excluded.',fontsize=9)
    fig.text(.06,.055,'Ordinal alignment and initial normalization are conditional; unknown exact phase. Female VM2 is not male VM7d calibration.',fontsize=9)
    fig.savefig(out('-figure.png'),dpi=160);plt.close(fig)
    for r in plan['inputs']:
        assert record(ROOT/r['path'])==r
    assert record(out('-plan.json'))==plan_record
    result={'passed':True,'completed_utc':datetime.now(timezone.utc).isoformat(),'plan':plan_record,
            'summaries':summaries,'limits':plan['limits'],
            'artifacts':[record(out(s)) for s in ['-rows.csv','-figure.png']]}
    write(out('-results.json'),result);print(json.dumps(result['summaries']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','compare']);args=p.parse_args()
    if args.action=='prepare': prepare()
    else: compare()
