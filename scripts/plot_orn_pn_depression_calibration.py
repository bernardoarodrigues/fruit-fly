#!/usr/bin/env python3
"""Plot frozen local-calibration outputs only; no calibration/model imports or calls."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import math

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
PREFIX=ROOT/'validation/orn-pn-depression-calibration'
POINTS=ROOT/'validation/orn-pn-depression-fig8f-points.csv'
FIXED=ROOT/'validation/synaptic-depression-reference-arrays.npz'


def path(suffix):return Path(str(PREFIX)+suffix)
def record(p):
    p=Path(p);b=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def table(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))


def main(expected_results_sha):
    output=path('-figure.png');receipt=path('-plot-receipt.json')
    if output.exists() or receipt.exists():raise FileExistsError('Preserve first calibration plot and receipt')
    result_path=path('-results.json');assert record(result_path)['sha256']==expected_results_sha
    r=json.loads(result_path.read_text());assert r['passed'] and 'error' not in r
    plan_path=ROOT/r['plan']['path'];assert record(plan_path)==r['plan'];plan=json.loads(plan_path.read_text())
    inputs={x['path']:x for x in plan['inputs']};artifacts={x['path']:x for x in r['artifacts']}
    for p in [POINTS,FIXED]:assert record(p)==inputs[str(p.relative_to(ROOT))]
    for suffix in ['-arrays.npz','-profile.csv','-predictions.csv']:
        p=path(suffix);assert record(p)==artifacts[str(p.relative_to(ROOT))]
    pins=[record(Path(__file__)),record(result_path),record(plan_path),record(POINTS),record(FIXED)]
    pins += [record(path(s)) for s in ['-arrays.npz','-profile.csv','-predictions.csv']]
    rows=table(POINTS);profile=table(path('-profile.csv'));prediction_rows=table(path('-predictions.csv'))
    assert plan['development']['frequency_hz']==20 and plan['development']['ordinals']==list(range(1,10))
    assert plan['evaluation']['rates_hz']==[15,50]
    values={};plotted_resolved_bars=0;missing_mean=0;missing_sem=0
    with np.load(path('-arrays.npz'),allow_pickle=False) as z, np.load(FIXED,allow_pickle=False) as fixed:
        for rate,count in [(15,8),(20,10),(50,25)]:
            rr=[x for x in rows if int(x['frequency_hz'])==rate]
            pr=[x for x in prediction_rows if int(x['frequency_hz'])==rate]
            assert [int(x['point_ordinal']) for x in rr]==list(range(count))
            assert [int(x['point_ordinal']) for x in pr]==list(range(count))
            x=np.array([float(a['time_ms']) for a in rr]);obs=np.array([float(a['mean_percent_initial']) if a['mean_percent_initial'] else np.nan for a in rr])
            fitted=z[f'rate_{rate}_nominal_percent'];original=100*fixed[f'train_{rate}_normalized_test_amplitude']
            assert fitted.shape==original.shape==x.shape==(count,) and np.isfinite(fitted).all() and np.isfinite(original).all()
            assert np.array_equal(fitted,np.array([float(a['fitted_percent']) for a in pr]))
            assert np.array_equal(x,np.array([float(a['source_time_ms']) for a in pr]))
            assert np.array_equal(obs,np.array([float(a['observed_percent']) if a['observed_percent'] else np.nan for a in pr]),equal_nan=True)
            assert not np.isfinite(obs[0]) and np.isfinite(obs[1:]).all()
            missing_mean+=int((~np.isfinite(obs)).sum())
            values[rate]=dict(rows=rr,x=x,observed=obs,original=original.copy(),fitted=fitted.copy())
        tau=np.array([float(x['tau_s']) for x in profile]);rmse=np.array([float(x['RMSE_percentage_points']) for x in profile]);sse=np.array([float(x['SSE']) for x in profile])
        assert np.array_equal(tau,z['profile_tau_s']) and np.array_equal(sse,z['profile_SSE'])
        assert len(tau)==121 and np.all(np.diff(tau)>0) and np.isfinite(rmse).all()
        assert np.allclose(rmse,np.sqrt(sse/9),rtol=1e-14,atol=0)
    best=r['best'];best_tau=float(best['tau_s']);best_rmse=math.sqrt(best['SSE']/9)
    assert best['success'] and plan['model'].find('Normalize test efficacy by firsttestevent')>=0
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':11,'axes.labelsize':9,
                         'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white'})
    fig=plt.figure(figsize=(12,8.2))
    grid=fig.add_gridspec(2,3,height_ratios=[2.65,1],left=.065,right=.975,bottom=.195,top=.81,wspace=.24,hspace=.62)
    obs_color='#24292E';fixed_color='#617AA0';fit_color='#008879';missing_color='#C45A32'
    fig.text(.065,.965,'Local scalar depression calibration',fontsize=17,weight='bold',va='top')
    fig.text(.065,.922,'Kazama-Wilson Fig. 8F (VM2) • fit only 20 Hz means • 15/50 Hz evaluation was already inspected',fontsize=11,va='top',color='#454B50')
    legend=[Line2D([],[],marker='o',color=obs_color,linestyle='none',markersize=4,label='Extracted mean / resolved drawn bars'),
            Line2D([],[],color=fixed_color,linestyle='--',linewidth=1.6,label='Original Abbott: f=0.75, τ=0.3 s'),
            Line2D([],[],color=fit_color,linewidth=1.8,label='20 Hz fitted nominal model'),
            Line2D([],[],marker='o',color=missing_color,markerfacecolor='none',linestyle='none',markersize=6,label='Unresolved SEM')]
    fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.056,.886),ncol=2,frameon=False,columnspacing=2.2,handlelength=2.2,fontsize=9)
    for col,rate in enumerate([15,20,50]):
        ax=fig.add_subplot(grid[0,col]);v=values[rate]
        if rate==20:ax.set_facecolor('#F0F8F6')
        ax.plot(v['x'],v['original'],'--',color=fixed_color,lw=1.6)
        ax.plot(v['x'],v['fitted'],color=fit_color,lw=1.8)
        for row,x,y in zip(v['rows'],v['x'],v['observed']):
            if not np.isfinite(y):continue
            if row['sem_percent_initial']:
                low=float(row['error_low_percent_initial']);high=float(row['error_high_percent_initial'])
                assert low<=y<=high
                ax.errorbar(x,y,yerr=np.array([[y-low],[high-y]]),fmt='o',ms=3.5,color=obs_color,
                            elinewidth=.8,capsize=1.8,capthick=.7,zorder=4)
                plotted_resolved_bars+=1
            else:
                ax.plot(x,y,'o',ms=3.5,color=obs_color,zorder=4)
                ax.plot(x,y,'o',ms=7.5,mfc='none',mec=missing_color,mew=1,zorder=5);missing_sem+=1
        ax.axhline(0,color='#999999',lw=.6);ax.set_xlim(-8,505);ax.set_ylim(-20,112)
        ax.set_xticks([0,100,200,300,400,500]);ax.set_yticks([0,25,50,75,100]);ax.grid(alpha=.18)
        ax.set_title(f'{rate} Hz | '+('development (9 means)' if rate==20 else f'evaluation ({len(v["x"])-1} means)'),loc='left',fontweight='bold',pad=8)
        ax.set_xlabel('Digitized event coordinate (ms)')
        if col==0:ax.set_ylabel('uEPSC amplitude (% initial)')
        else:ax.tick_params(labelleft=False)
    ax=fig.add_subplot(grid[1,0]);ax.plot(tau,rmse,color='#4C5C6B',lw=1.4);ax.scatter([best_tau],[best_rmse],color=fit_color,marker='*',s=75,zorder=4)
    ax.set_xscale('log');ax.set_xlim(tau[0]*.8,tau[-1]*1.25);ax.set_xlabel('Fixed τ in profile (s, log scale)');ax.set_ylabel('20 Hz RMSE\n(percentage points)');ax.set_title('Descriptive profile; not a confidence interval',loc='left',fontsize=9.5,pad=7);ax.grid(alpha=.2)
    for tick in ax.get_xticklabels():tick.set_fontsize(8)
    if r['bound_proximity']['tau_upper']:
        ax.axvline(tau[-1],color='#AF5D22',lw=.8,linestyle=':')
        ax.text(tau[-1],.96,'τ ceiling',transform=ax.get_xaxis_transform(),ha='right',va='top',fontsize=8,color='#934911')
    notes=fig.add_subplot(grid[1,1:]);notes.axis('off')
    boundary_names=[k for k,v in r['bound_proximity'].items() if v]
    boundary='Bound proximity: '+(', '.join(boundary_names) if boundary_names else 'none at declared tolerance')
    if r['bound_proximity']['tau_upper']:
        notes.text(0,1.,f'Best τ={best_tau:.5g} s reaches the declared upper bound',
                   fontsize=11,weight='bold',color='#934911',va='top')
    else:
        notes.text(0,1.,'A descriptive fit within declared engineering bounds',fontsize=11,weight='bold',va='top')
    notes.text(0,.73,f'Selected f={best["f"]:.5g}, τ={best_tau:.5g} s; development RMSE={best_rmse:.3g} percentage points.\n'
        'Profile optimizes f at each τ using development means only.\n'
        'No SEM weighting; normalization and experimental timing remain conditional.\n'
        'The search ceiling is not a measured recovery timescale; no fit is promoted.',
        fontsize=9.2,va='top',linespacing=1.45,color='#363D43')
    fig.text(.065,.035,'Models matched by event ordinal; x retains raster coordinates. Shared initial measurements are missing, not zeros.\n'
        'Asymmetric drawn-bar endpoints are shown where resolved; raster-placement sensitivity is separate from SEM.\n'
        'Previously inspected evaluation curves are not unseen validation. No physiological parameter or runtime promotion.',
        fontsize=9.4,va='bottom',linespacing=1.55,color='#4B5258')
    assert plotted_resolved_bars==37 and missing_mean==3 and missing_sem==3
    fig.savefig(output,dpi=180,metadata={'InputResultsSHA256':expected_results_sha,'Scope':'Local scalar fit visualization only; development20Hz; previously inspected evaluation15/50Hz'})
    plt.close(fig)
    assert all(record(ROOT / x['path'])==x for x in pins),'Input changed while plotting; preserve first artifact'
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),passed=True,inputs=pins,output=record(output),
        plot_only=True,no_fit_or_model_execution=True,development_frequency_hz=20,evaluation_frequencies_hz=[15,50],
        plotted_individual_means=40,plotted_resolved_bars=37,missing_initial_means=3,additional_missing_SEM=3,
        predicted_points_per_model=43,profile_points=len(tau),best_parameter_marker=dict(tau_s=best_tau,RMSE_percentage_points=best_rmse),
        limits=['Ordinal-matched nominal predictions shown at source raster coordinates; experimental phase remains unresolved.',
                'Profile is descriptive development RMSE, not likelihood or a confidence interval; no unseen-data or physiology claim.',
                'Missing initial means omitted; unresolved SEM ringed and never replaced by zero.'])
    with receipt.open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(output=record(output),receipt=record(receipt)),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--expected-results-sha',required=True)
    args=parser.parse_args();main(args.expected_results_sha)
