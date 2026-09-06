"""Show every cell and every sweep in the complete 2 nA AHP batch."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-ahp-measurements.json').read_text())
a=np.load(ROOT/r['arrays']['path'])
fig,axes=plt.subplots(3,4,figsize=(15,10),layout='constrained')
for ax,f in zip(axes.flat,r['files']):
    idx=f['file_index'];row=f['author_row'];rnai='dSK' in row['genotype'];c='#8052aa' if rnai else '#ba5847'
    t=a[f'f{idx}_time_from_offset_s'];v=a[f'f{idx}_voltage_mV'].astype(float)
    baseline=np.array([s['measurements'][0]['held_baseline_mV'] for s in f['sweeps']]);v-=baseline[:,None]
    mask=t>=.05
    for trace in v:ax.plot(t[mask],trace[mask],color=c,alpha=.22,lw=.5)
    ax.plot(t[mask],v.mean(axis=0)[mask],color=c,lw=1.5)
    ax.axhline(0,color='.4',lw=.7,ls=':')
    ax.set(title=f"{row['cell']} · {'SK RNAi' if rnai else 'control'} · n={len(v)}",xlabel='Time after pulse offset (s)',ylabel='Voltage from baseline (mV)')
    ax.title.set_fontsize(10)
    ax.spines[['top','right']].set_visible(False)
ax=axes.flat[-1]
for f in r['files']:
    row=f['author_row'];rnai='dSK' in row['genotype'];c='#8052aa' if rnai else '#ba5847'
    ax.scatter(-row['row_values']['G1'],f['mean_trace_measurements'][0]['amplitude_mV'],c=c,s=35)
ax.plot([0,6],[0,6],c='.5',ls='--',lw=.8)
ax.set(title='All eleven amplitude comparisons',xlabel='Author AHP magnitude (mV)',ylabel='All-sweep mean AHP magnitude (mV)')
ax.spines[['top','right']].set_visible(False)
fig.suptitle('APL 2 nA AHP: every sweep retained; repeated threshold crossings remain flagged',fontsize=15)
fig.supxlabel('Thin lines: individual sweeps; thick lines: within-cell means. Recovery view starts at +50 ms; measurements start at +5/+20 ms. No smoothing.',fontsize=10)
fig.savefig(ROOT/'validation/apl-ahp-measurements.png',dpi=160);plt.close(fig)
