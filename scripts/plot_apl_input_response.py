"""All-file drive-response diagnostics, with no selection of fitting targets."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-input-response-results.json').read_text());v=json.loads((ROOT/'validation/apl-input-response-review.json').read_text())
refs={x['member']:x['small_signal_resistance_MOhm'] for x in v['one_nA_comparisons']}
fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
for f in r['files']:
    if not f['staircase']:continue
    current=np.array([s['command_delta_pA'] for s in f['sweeps']]);voltage=np.array([s['plateau_delta_mV'] for s in f['sweeps']])
    axes[0,0].plot(current,voltage,color='#3b83a3',lw=.8,alpha=.35)
    keep=current>=200;ratio=voltage[keep]/(refs[f['member']]*current[keep]/1000)
    axes[0,1].plot(current[keep],ratio,color='#3b83a3',lw=.8,alpha=.35)
    axes[1,0].plot(current,[s['plateau_minus_early_mV'] for s in f['sweeps']],color='#3b83a3',lw=.8,alpha=.3)
for idx,c in enumerate(v['two_nA_comparisons']):
    f=next(f for f in r['files'] if f['file_index']==c['file_index']);rnai='dSK' in f['author_rows'][0]['genotype']
    axes[1,1].scatter(c['small_signal_resistance_MOhm']*2,c['two_nA_mean_plateau_delta_mV'],color='#9654a4' if rnai else '#bd6745',s=40)
axes[0,0].set(title='All 82 staircase files',xlabel='Commanded current step (pA)',ylabel='Late plateau voltage change (mV)')
axes[0,1].axhline(1,color='.4',ls='--',lw=.8)
axes[0,1].set(title='Compression relative to small-signal resistance',xlabel='Commanded positive current (≥200 pA shown)',ylabel='Observed / linear predicted voltage change')
axes[1,0].axhline(0,color='.4',ls='--',lw=.8)
axes[1,0].set(title='Late response minus 50–100 ms response',xlabel='Commanded current step (pA)',ylabel='Late minus early voltage (mV)')
axes[1,1].plot([0,250],[0,250],color='.4',ls='--',lw=.8)
axes[1,1].set(title='All eleven dedicated 2 nA cells',xlabel='Small-signal linear prediction (mV)',ylabel='Measured mean late voltage change (mV)')
for ax in axes.flat:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
fig.suptitle('APL complete drive-response batch: large depolarization is not a passive extrapolation',fontsize=14)
fig.savefig(ROOT/'validation/apl-input-response.png',dpi=170);plt.close(fig)
