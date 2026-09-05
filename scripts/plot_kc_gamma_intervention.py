#!/usr/bin/env python3
"""Plot the completed combined analysis, with seed ranges and fixed time windows."""
from pathlib import Path
from datetime import datetime,timezone
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_navigation_ladder_timing import record,load,write_new
ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'validation/kc-gamma-intervention-analysis-results.json'
PLAN=ROOT/'validation/kc-gamma-intervention-analysis-plan.json'
OUT=ROOT/'validation/kc-gamma-intervention-figure.png'
RECEIPT=ROOT/'validation/kc-gamma-intervention-plot.json'
def main():
    if OUT.exists() or RECEIPT.exists():raise FileExistsError('Preserve first plot')
    result=load(RESULT);plan=load(PLAN);assert result['passed'] and result['plan']==record(PLAN)
    arrays=ROOT/result['array_artifact']['path'];assert record(arrays)==result['array_artifact']
    sources=[record(p) for p in [Path(__file__),RESULT,PLAN,arrays]]
    fig,axes=plt.subplots(3,2,figsize=(13.4,11.5),sharex=True);t=(np.arange(60)+.5)*.05;names=result['cohort_names'];curves={}
    colors={'control':'#42566b','intervention':'#c34d29'};styles={'constant_baseline':'--','ethyl_acetate':'-'}
    with np.load(arrays,allow_pickle=False) as z:
        for name in ['gamma_KC','other_KC','MBON12_14','APL','population']:
            j=names.index(name);n=len(plan['cohorts'][name]);curves[name]={}
            for arm in colors:
                for condition in styles:
                    specs=[s for s in plan['trials'] if s['condition']==condition]
                    curves[name][arm,condition]=np.array([z[f'trial_{s["ordinal"]}_{arm}_bin_counts'][:,j]/(.05*n) for s in specs])
    for ax,name,title in zip(axes.flat,['gamma_KC','other_KC','MBON12_14','APL','population'],['γ Kenyon cells (1,557)','Other Kenyon cells (2,507)','MBON12–14 (10)','APL (2)','Whole CNS (166,700)']):
        for arm,color in colors.items():
            for condition,style in styles.items():
                a=curves[name][arm,condition];ax.plot(t,a.mean(axis=0),color=color,ls=style,lw=1.65,label=f'{arm.title()} · '+('EA' if condition=='ethyl_acetate' else 'constant'))
                ax.fill_between(t,a.min(axis=0),a.max(axis=0),color=color,alpha=.10)
        ax.set_title(title,loc='left',fontsize=12);ax.set_ylabel('Mean spikes / cell / s');ax.set_ylim(bottom=0)
    ax=axes[-1,-1]
    for arm,color in colors.items():
        a=curves['gamma_KC'][arm,'ethyl_acetate']-curves['gamma_KC'][arm,'constant_baseline']
        for j,row in enumerate(a):ax.plot(t,row,color=color,lw=.7,alpha=.35)
        ax.plot(t,a.mean(axis=0),color=color,lw=1.7,label=arm.title())
    ax.axhline(0,color='#888',lw=.6);ax.set_title('γ KC odor contrast: EA − constant',loc='left',fontsize=12);ax.set_ylabel('Paired rate difference (Hz/cell)')
    for ax in axes.flat:
        ax.axvspan(.5,1.5,color='#dbaa56',alpha=.13);ax.axvline(.5,color='#9c7c42',lw=.7);ax.axvline(1,color='#9c7c42',ls=':',lw=.7);ax.axvline(1.5,color='#9c7c42',lw=.7)
        ax.set_xlim(0,3);ax.grid(alpha=.15);ax.spines[['top','right']].set_visible(False)
    for ax in axes[-1]:ax.set_xlabel('Simulation time (s)')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.94),ncol=4,frameon=False,fontsize=10)
    fig.suptitle('Contact-aware γ-KC intervention · all six recurrent trials',fontsize=17,y=.987)
    fig.text(.5,.957,'Model diagnostic; original H1 controls retained. No physiological or default-model promotion.',ha='center',fontsize=10,color='#555')
    fig.text(.065,.025,'50 ms bins. Lines: three-seed means; bands: seed min–max, not confidence intervals. Shaded: modified delivery (0.5–1.5 s).\nEA source pulse: 0.5–1.0 s. At 1.5 s, original weights return and external input ends together. Prefix before 0.5 s is reused.',fontsize=10,color='#444')
    fig.subplots_adjust(top=.89,bottom=.10,hspace=.30,wspace=.25);fig.savefig(OUT,dpi=170,facecolor='white');plt.close(fig)
    assert [record(ROOT/r['path']) for r in sources]==sources
    write_new(RECEIPT,dict(passed=True,created_utc=datetime.now(timezone.utc).isoformat(),inputs=sources,figure=record(OUT),bin_ms=50,uncertainty='Observed min/max across three historical simulation seeds, not confidence intervals.',review='Numeric source/array hashes checked; visual inspection separately required.'))
    print(json.dumps(record(OUT)))
if __name__=='__main__':main()
