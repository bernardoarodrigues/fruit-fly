#!/usr/bin/env python3
"""Plot the whole reviewed batch; no fitting or network execution."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_navigation_ladder_timing import load, record, write_new

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'validation/navigation-mbon-intervention-analysis-results.json'
IMAGE=ROOT/'validation/navigation-mbon-intervention-figure.png'
RECEIPT=ROOT/'validation/navigation-mbon-intervention-figure.json'


def main():
    assert not IMAGE.exists() and not RECEIPT.exists()
    result=load(RESULT);assert result['passed']
    array_path=ROOT/result['array_artifact']['path']
    assert record(array_path)==result['array_artifact']
    pins=[record(Path(__file__)),record(RESULT),record(array_path)]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,2,figsize=(12,10),sharex=True,layout='constrained')
    with np.load(array_path,allow_pickle=False) as a:
        time=(a['bin_edges_ticks'][:-1]+250)*.0001
        for col,condition in enumerate(['constant_baseline','ethyl_acetate']):
            ordinals=[t['spec']['ordinal'] for t in result['trials'] if t['spec']['condition']==condition]
            for row,metric in enumerate(['bin_counts','p_bin_mean','h_bin_mean']):
                ax=axes[row,col]
                for arm,color,label in [('control','#737373','Original control'),('intervention','#007F8B','KC delivery suppression')]:
                    data=np.stack([a[f'trial_{o}_{arm}_{metric}'].mean(axis=1) for o in ordinals])
                    if metric=='bin_counts':data=data/.05
                    ax.plot(time,data.mean(axis=0),color=color,lw=1.8,label=label)
                    ax.fill_between(time,data.min(axis=0),data.max(axis=0),color=color,alpha=.19)
                ax.axvspan(.5,1.5,color='#E7B46C',alpha=.2,zorder=-2)
                ax.axvline(1.5,color='#7c6651',ls=':',lw=1)
                if condition=='ethyl_acetate':ax.axvspan(.5,1.,ymin=.96,ymax=1.,color='#6B4C9A',alpha=.8)
                ax.grid(axis='y',alpha=.15);ax.set_xlim(0,3)
                if row==0:
                    ax.set_title('Constant VM7d baseline' if col==0 else 'VM7d ethyl-acetate rate pulse')
                    ax.axhline(1000/2.2,color='#aa4444',ls='--',lw=.7,label='Refractory ceiling')
                if col==0:ax.set_ylabel(['MBON mean firing rate (Hz)','Positive synaptic state p\n(model units; not voltage)','Relative inhibitory\nconductance h'][row])
                if row==2:ax.set_xlabel('Simulated time (s)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
    fig.suptitle('KC → MBON12–14 intervention: all six paired branches\n10 MBONs per run; line = three-seed mean, band = seed range; 50 ms bins',fontsize=14)
    fig.text(.5,.065,'Tan: selected deliveries suppressed (0.5–1.5 s). Purple strip: EA rate pulse (0.5–1.0 s).\nAt 1.5 s deliveries return and external input stops. Before 0.5 s, the original prefix is reused.',ha='center',fontsize=9)
    # Reserve footer space explicitly; keep the figure's scientific panels intact.
    fig.get_layout_engine().set(rect=(0,.1,1,.9))
    fig.savefig(IMAGE,dpi=160)
    for r in pins:assert record(ROOT/r['path'])==r
    write_new(RECEIPT,dict(passed=True,inputs=pins,image=record(IMAGE),scope='All six completed reviewed simulations; descriptive plotting only.'))
    print(json.dumps(record(IMAGE)))


if __name__=='__main__':main()
