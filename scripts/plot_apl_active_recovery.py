"""Show all eleven cells and all four fixed passive variants."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/'validation/apl-active-recovery-plan.json').read_text());r=json.loads((ROOT/'validation/apl-active-recovery-results.json').read_text());a=np.load(ROOT/r['arrays']['path'])
t=a['time_s'];mask=t>=.05;colors=['#3d83ad','#69923d','#c48a38','#985caf']
fig,axes=plt.subplots(3,4,figsize=(15,10),layout='constrained')
for idx,(c,ax) in enumerate(zip(p['cells'],axes.flat)):
    data=a[f'c{idx}_observed_sweeps_mV']
    for trace in data:ax.plot(t[mask],trace[mask],c='.65',alpha=.22,lw=.5)
    ax.plot(t[mask],data.mean(axis=0)[mask],c='.15',lw=1.5,label='Measured mean' if idx==0 else None)
    for v in range(4):
        ax.plot(t[mask],a[f'v{v}_c{idx}_active_mV'][mask],color=colors[v],lw=1,label=f'Active variant {v}' if idx==0 else None)
    ax.plot(t[mask],a[f'v2_c{idx}_passive_mV'][mask],c='.4',ls='--',lw=1,label='Passive v2' if idx==0 else None)
    ax.set(title=f"{c['cell']} · {c['group']} · {c['partition']}",xlabel='Time after current offset (s)',ylabel='Voltage from baseline (mV)')
    ax.title.set_fontsize(9);ax.spines[['top','right']].set_visible(False)
    if idx==0:ax.legend(fontsize=7,frameon=False)
ax=axes.flat[-1]
for s in r['scores']:
    if s['partition']=='evaluation':ax.scatter(s['metrics']['full']['passive_rmse_mV'],s['metrics']['full']['active_rmse_mV'],color=colors[s['variant']],s=30,alpha=.75)
ax.plot([0,1.7],[0,1.7],c='.5',ls='--');ax.set(title='Five evaluation flies × four variants',xlabel='Passive full-window RMSE (mV)',ylabel='Active full-window RMSE (mV)')
ax.spines[['top','right']].set_visible(False)
fig.suptitle('Conditional APL recovery: six calibration flies, five evaluation flies, all sweeps retained',fontsize=15)
fig.supxlabel('Passive parameters fixed; initial voltage measured in each cell. Gray traces are repeats, not independent animals. This is retrospective conditional transfer.',fontsize=10)
fig.savefig(ROOT/'validation/apl-active-recovery.png',dpi=160);plt.close(fig)
