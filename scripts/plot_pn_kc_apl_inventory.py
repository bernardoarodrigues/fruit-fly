#!/usr/bin/env python3
"""Display all twelve reviewed histories with explicit model/input units."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_navigation_ladder_timing import record,load,write_new

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'validation/pn-kc-apl-inventory-results.json'
REVIEW=ROOT/'validation/pn-kc-apl-inventory-independent-review.json'
IMAGE=ROOT/'validation/pn-kc-apl-inventory-figure.png'
RECEIPT=ROOT/'validation/pn-kc-apl-inventory-figure.json'


def main():
    assert not IMAGE.exists() and not RECEIPT.exists()
    r=load(RESULT);review=load(REVIEW);assert r['passed'] and review['passed']
    plan=load(ROOT/r['plan']['path']);arraypath=ROOT/r['array_artifact']['path']
    assert record(arraypath)==r['array_artifact']
    pins=[record(Path(__file__)),record(RESULT),record(REVIEW),record(arraypath),record(ROOT/r['plan']['path'])]
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(13,10),layout='constrained',gridspec_kw={'height_ratios':[1,1.5]})
    time=np.array(plan['window_edges_ticks'])*.0001
    for col,group in enumerate(['KC_all','APL']):
        ax=axes[0,col]
        for condition,color,title in [('constant_baseline','#3274A1','Constant'),('ethyl_acetate','#B65F28','EA')]:
            for arm,ls in [('control','-'),('intervention','--')]:
                values=np.array([t['groups'][group]['mean_rates_hz'] for t in r['trials'] if t['arm']==arm and t['spec']['condition']==condition])
                assert values.shape==(3,7)
                mean=np.r_[values.mean(0),values.mean(0)[-1]]
                ax.step(time,mean,where='post',color=color,ls=ls,lw=1.8,label=f'{title}, {arm}')
                ax.fill_between(time,np.r_[values.min(0),values.min(0)[-1]],np.r_[values.max(0),values.max(0)[-1]],step='post',color=color,alpha=.12)
        ax.axvspan(.5,1.5,color='#E7B46C',alpha=.17,zorder=-2);ax.axvline(1.5,color='#7c6651',ls=':',lw=.8)
        ax.set(xlabel='Simulated time (s)',ylabel='Mean model spike-event rate (Hz)',xlim=(0,3),title='All 4,064 annotated KCs' if col==0 else 'Both APL cells (spiking H1 approximation)')
        ax.grid(axis='y',alpha=.15)
    with np.load(arraypath,allow_pickle=False) as a:
        target_types=plan['labels']['target_type'];keep=np.array([n!='APL' for n in target_types]);rows=[];names=[]
        for t in r['trials']:
            p=f"trial_{t['spec']['ordinal']}_{t['arm']}";names.append(f"{t['spec']['seed']} {'EA' if t['spec']['condition']=='ethyl_acetate' else 'constant'} / {'original' if t['arm']=='control' else 'KC block'}")
            rows.append([a[p+'_group_'+k][2:4,keep,:].sum(axis=(0,1)) for k in ['p_increment','h_increment']])
        rows=np.array(rows)
        for col in range(2):
            ax=axes[1,col];v=rows[:,col,:];totals=v.sum(axis=1);assert np.all(totals>0);shares=100*v/totals[:,None]
            im=ax.imshow(shares,aspect='auto',vmin=0,vmax=100,cmap='Blues')
            ax.set_xticks(range(len(plan['labels']['group'])),labels=plan['labels']['group'],rotation=45,ha='right')
            ax.set_yticks(range(len(names)),labels=names)
            ax.set_title(('Positive p' if col==0 else 'Inhibitory h')+' nominal increment shares onto KCs\n0.5–1.5 s; percent within this sign/channel')
            for j in range(len(names)):
                for k in range(shares.shape[1]):
                    value=shares[j,k];label='0' if value==0 else '<0.1' if value<.05 else f'{value:.1f}'
                    ax.text(k,j,label,ha='center',va='center',fontsize=7,color='white' if value>55 else '#222222')
            fig.colorbar(im,ax=ax,fraction=.025,pad=.02,label='%')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=4,frameon=False)
    fig.suptitle('KC/APL inventory of six original and six intervention histories\nLines: three-seed means; bands: seed ranges. Inputs: emitted events shifted by the fixed delay.',fontsize=13)
    fig.text(.5,.047,'Tan interval: KC→MBON deliveries suppressed only in intervention branches. Input stops at 1.5 s.\nNominal p/h increments omit decay and are not physical currents. APL event rates are not biological firing measurements.',ha='center',fontsize=8)
    fig.get_layout_engine().set(rect=(0,.09,1,.91));fig.savefig(IMAGE,dpi=160)
    for p in pins:assert record(ROOT/p['path'])==p
    write_new(RECEIPT,dict(passed=True,inputs=pins,image=record(IMAGE),scope='All12 complete reviewed saved histories; descriptive plots only.'))
    print(json.dumps(record(IMAGE)))


if __name__=='__main__':main()
