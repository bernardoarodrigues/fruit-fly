#!/usr/bin/env python3
"""Expose cell-type differences hidden by the ten-cell population mean."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_navigation_ladder_timing import load, record, write_new

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'validation/navigation-mbon-intervention-analysis-results.json'
ANATOMY=ROOT/'validation/navigation-ladder-anatomy.json'
IMAGE=ROOT/'validation/navigation-mbon-intervention-cell-types.png'
RECEIPT=ROOT/'validation/navigation-mbon-intervention-cell-types.json'


def main():
    assert not IMAGE.exists() and not RECEIPT.exists()
    result=load(RESULT);assert result['passed'];anatomy=load(ANATOMY)
    array_path=ROOT/result['array_artifact']['path']
    assert record(array_path)==result['array_artifact']
    pins=[record(Path(__file__)),record(RESULT),record(array_path),record(ANATOMY)]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,2,figsize=(12,9),sharex=True,sharey=True,layout='constrained')
    with np.load(array_path,allow_pickle=False) as a:
        time=(a['bin_edges_ticks'][:-1]+250)*.0001
        for col,condition in enumerate(['constant_baseline','ethyl_acetate']):
            ordinals=[t['spec']['ordinal'] for t in result['trials'] if t['spec']['condition']==condition]
            for row,name in enumerate(['MBON12','MBON13','MBON14']):
                ax=axes[row,col];members=anatomy['groups'][name]['indices']
                selected=np.flatnonzero(np.isin(a['target_indices'],members));assert len(selected)==len(members)
                for arm,color,label in [('control','#737373','Original control'),('intervention','#007F8B','KC delivery suppression')]:
                    data=np.stack([a[f'trial_{o}_{arm}_bin_counts'][:,selected].mean(axis=1)/.05 for o in ordinals])
                    ax.plot(time,data.mean(axis=0),color=color,lw=1.8,label=label)
                    ax.fill_between(time,data.min(axis=0),data.max(axis=0),color=color,alpha=.2)
                ax.axvspan(.5,1.5,color='#E7B46C',alpha=.2,zorder=-2)
                ax.axvline(1.5,color='#7c6651',ls=':',lw=1)
                if col:ax.axvspan(.5,1.,ymin=.96,ymax=1.,color='#6B4C9A',alpha=.8)
                ax.axhline(1000/2.2,color='#aa4444',ls='--',lw=.7,label='Refractory ceiling')
                ax.grid(axis='y',alpha=.15);ax.set_xlim(0,3);ax.set_ylim(-15,480)
                if row==0:ax.set_title('Constant VM7d baseline' if col==0 else 'VM7d ethyl-acetate rate pulse')
                if col==0:ax.set_ylabel(f'{name} ({len(selected)} cells)\nMean firing rate (Hz)')
                if row==2:ax.set_xlabel('Simulated time (s)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=3,frameon=False)
    fig.suptitle('The mean reduction conceals silence and persistent high firing\nAll six branches; line = three-seed mean, band = seed range; 50 ms bins',fontsize=14)
    fig.text(.5,.065,'Tan: KC deliveries suppressed (0.5–1.5 s). Purple: EA rate pulse (0.5–1.0 s).\nAt 1.5 s deliveries return and external input stops. The prefix before 0.5 s is reused.',ha='center',fontsize=9)
    fig.get_layout_engine().set(rect=(0,.1,1,.9));fig.savefig(IMAGE,dpi=160)
    for r in pins:assert record(ROOT/r['path'])==r
    write_new(RECEIPT,dict(passed=True,inputs=pins,image=record(IMAGE),scope='Descriptive cell-type view of all six reviewed simulations.'))
    print(json.dumps(record(IMAGE)))


if __name__=='__main__':main()
