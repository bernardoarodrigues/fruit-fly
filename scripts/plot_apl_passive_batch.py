"""Plot complete passive measurements without tuning or filtering observations."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
v=json.loads((ROOT/'validation/apl-passive-measurement-review.json').read_text())
a=np.load(ROOT/r['arrays']['path'])
fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
colors={'NS':'#2675ad','SD':'#d87521','RS':'#39a17c','RNAi':'#9c69b4','control':'#6b6b6b','unresolved':'#bf465f'}
seen=set()
for f,s in zip(r['files'],v['files'],strict=True):
    idx=f['file_index']; linked=f['linked_author_rows'];group='unresolved'
    if linked:
        row=linked[0]
        group=('RNAi' if 'dSK' in row['genotype'] else 'control') if row['genotype'] else row['state']
    t=a[f'f{idx}_relative_time_s'];y=a[f'f{idx}_mean_voltage_mV']-s['mean_held_baseline_mV']
    axes[0,0].plot(t,y,color=colors[group],lw=.7,alpha=.65,label=group if group not in seen else None)
    seen.add(group)
    if f['recorded_current_channel'] is not None:
        y=a[f'f{idx}_mean_recorded_current_pA']-np.mean([q['recorded']['baseline_current_pA'] for q in f['sweeps']])
        axes[0,1].plot(t,y,color=colors[group],lw=.7,alpha=.5)
    for c in s['comparisons']:
        if c['author_resistance_numeric_MOhm'] is not None:
            axes[1,0].scatter(c['author_resistance_numeric_MOhm'],s['mean_commanded_resistance_MOhm'],c=colors[group],s=20,alpha=.8)
    axes[1,1].plot([idx,idx],[s['min_commanded_resistance_MOhm'],s['max_commanded_resistance_MOhm']],color=colors[group],lw=1,alpha=.6)
    axes[1,1].scatter(idx,s['mean_commanded_resistance_MOhm'],color=colors[group],s=10)
for ax in axes[0]:
    ax.axvline(0,color='.3',ls=':',lw=.8);ax.axvline(.5,color='.3',ls=':',lw=.8)
    ax.set_xlabel('Time from passive-step onset (s)')
axes[0,0].set(title='All 82 files: mean of 26 sweeps each',ylabel='Voltage relative to held baseline (mV)')
axes[0,0].legend(ncol=3,fontsize=8,frameon=False)
axes[0,1].set(title='77 files with a recorded pA channel; 5 unavailable',ylabel='Recorded current change (pA)',ylim=(-65,15))
axes[1,0].plot([50,250],[50,250],c='.5',ls='--',lw=1)
axes[1,0].set(title='79 source comparisons; cursor selections differ',xlabel='Author resistance, interpreted as MΩ',ylabel='Fixed-window file mean (MΩ)')
axes[1,1].set(title='All sweeps retained: range and file mean',xlabel='Source inventory file index',ylabel='Command-based resistance (MΩ)')
for ax in axes.flat:
    ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
fig.suptitle('APL passive-step measurements — complete descriptive batch',fontsize=15)
fig.savefig(ROOT/'validation/apl-passive-measurements.png',dpi=170)
plt.close(fig)
