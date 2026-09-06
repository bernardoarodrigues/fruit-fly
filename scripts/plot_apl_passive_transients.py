"""Complete transient sensitivity and prediction diagnostics."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-passive-transient-results.json').read_text());a=np.load(ROOT/r['arrays']['path'])
fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
labels=['1–50','5–50','1–100','5–100'];colors=['#3b80ad','#659849','#cf8c2f','#9854a6']
for f in r['files']:
    taus=[x['fit']['tau_s']*1000 for x in f['mean_fits']]
    axes[0,0].plot(range(4),taus,color='#54859b',alpha=.2,lw=.8)
    for i,x in enumerate(f['mean_fits']):
        axes[0,1].scatter(x['fit']['rmse_mV'],x['evaluation']['offset_rmse_mV'],c=colors[i],s=12,alpha=.55,label=labels[i] if f['file_index']==0 else None)
    t=a['offset_time_s'];actual=(a[f"f{f['file_index']}_offset_voltage_mV"]-f['held_baseline_mV'])/f['passive_delta_mV']
    pred=np.exp(-t/f['mean_fits'][3]['fit']['tau_s'])
    axes[1,1].plot(t*1000,actual,color='#397fac',alpha=.15,lw=.7,label='Measured' if f['file_index']==0 else None)
    axes[1,1].plot(t*1000,pred,color='#c57b36',alpha=.12,lw=.7,label='Onset-fit prediction' if f['file_index']==0 else None)
axes[0,0].plot(range(4),[np.median([f['mean_fits'][i]['fit']['tau_s']*1000 for f in r['files']]) for i in range(4)],c='black',lw=2,label='File median')
axes[0,0].set(xticks=range(4),xticklabels=labels,xlabel='Fit window after onset (ms)',ylabel='Fitted tau (ms)',title='All 82 mean traces: fitting-window sensitivity')
axes[0,0].legend(frameon=False)
axes[0,1].set(xlabel='Onset fit RMSE (mV)',ylabel='Conditional offset RMSE (mV)',title='All 328 fits: onset fit versus offset prediction')
axes[0,1].legend(title='Fit window (ms)',fontsize=8,frameon=False)
vals=[s['fit']['tau_s']*1000 for f in r['files'] for s in f['sweep_fits']]
axes[1,0].hist(vals,bins=np.geomspace(.5,200,45),color='#54859b');axes[1,0].set_xscale('log')
axes[1,0].set(xlabel='Single-sweep tau (ms), primary 5–100 ms window',ylabel='Sweep count',title='All 2,132 fits; 221 reach a supplied bound')
axes[1,1].set(xlabel='Time from switch-off (ms)',ylabel='Residual deflection / measured passive step',title='Every file: primary-fit conditional recovery')
axes[1,1].legend(frameon=False)
for ax in axes.flat:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
fig.suptitle('APL single-exponential transients: descriptive fits, not identified membrane constants',fontsize=14)
fig.savefig(ROOT/'validation/apl-passive-transients.png',dpi=170);plt.close(fig)
