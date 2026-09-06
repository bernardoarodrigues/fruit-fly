"""Complete constrained-mode comparison diagnostics."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from apl_passive_kernels import response
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-passive-modes-results.json').read_text())
s=json.loads((ROOT/'validation/apl-passive-transient-results.json').read_text());a=np.load(ROOT/s['arrays']['path'])
fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
colors=['#347cad','#648d37','#ca8636','#9858a7'];labels=['1–50','5–50','1–100','5–100']
for f,source in zip(r['files'],s['files'],strict=True):
    for i,v in enumerate(f['variants']):
        one=v['models']['single'];two=v['models']['two']
        axes[0,0].scatter(one['offset_rmse_fraction_of_passive_step']*100,two['offset_rmse_fraction_of_passive_step']*100,color=colors[i],s=14,alpha=.5,label=labels[i] if f['file_index']==0 else None)
        axes[0,1].scatter(two['tau_fast_s']*1000,two['tau_slow_s']*1000,color=colors[i],s=14,alpha=.5)
    axes[1,0].plot(range(4),[v['models']['two']['offset_rmse_fraction_of_passive_step']*100 for v in f['variants']],color='#518b9e',alpha=.25,lw=.8)
    # One declared display window, not a model-selection decision.
    fit=f['variants'][2]['models']['two'];t=a['offset_time_s']
    actual=(a[f"f{f['file_index']}_offset_voltage_mV"]-source['held_baseline_mV'])/source['passive_delta_mV']
    axes[1,1].plot(t*1000,actual-response(t,fit,offset=True),color='#518b9e',lw=.8,alpha=.3)
axes[0,0].plot([0,15],[0,15],c='.5',ls='--',lw=.8)
axes[0,0].set(title='All 328 comparisons: lower than diagonal improves',xlabel='Single-mode offset error (% passive step)',ylabel='Two-mode offset error (% passive step)')
axes[0,0].legend(title='Onset fit window (ms)',fontsize=8,frameon=False)
axes[0,1].set(title='All fitted components; colors denote fit window',xlabel='Fast component (ms)',ylabel='Slow component (ms)')
axes[1,0].set(xticks=range(4),xticklabels=labels,title='Every file: retained window sensitivity',xlabel='Onset fit window (ms)',ylabel='Two-mode offset error (% passive step)')
axes[1,1].set(title='All 82 residuals, displayed 1–100 ms onset fits',xlabel='Time after current switch-off (ms)',ylabel='Measured minus predicted / passive step')
axes[1,1].axhline(0,color='.4',lw=.7,ls=':')
for ax in axes.flat:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
fig.suptitle('APL positive passive modes: fixed endpoints and finite-pulse recovery prediction',fontsize=14)
fig.savefig(ROOT/'validation/apl-passive-modes.png',dpi=170);plt.close(fig)
