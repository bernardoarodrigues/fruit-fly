"""Display all cells and all fitted variants without selecting a best-looking case."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-full-pulse-results.json').read_text());p=json.loads((ROOT/'validation/apl-full-pulse-plan.json').read_text());a=np.load(ROOT/r['arrays']['path']);t=a['time_s']
fig,axes=plt.subplots(6,4,figsize=(18,19))
for i,c in enumerate(p['cells']):
    row=i//2;col=(i%2)*2
    for side in [0,1]:
        ax=axes[row,col+side];mask=(t>=0)&(t<.75) if side==0 else (t>=.8)&(t<3.55);x=t[mask] if side==0 else t[mask]-.75
        for sweep in a[f'c{i}_observed_sweeps_mV']:ax.plot(x,sweep[mask],color='.75',lw=.45,alpha=.45)
        for f in r['fits']:
            color='#087f8c' if f['inactivating'] else '#d97706'
            ax.plot(x,a[f'f{f["fit_id"]}_c{i}_candidate_mV'][mask],color=color,lw=.7,alpha=.4)
        for variant in range(4):ax.plot(x,a[f'f{variant*4}_c{i}_passive_mV'][mask],color='#667085',ls=':',lw=.7,alpha=.5)
        ax.plot(x,a[f'c{i}_observed_mean_mV'][mask],color='black',lw=1.)
        ax.axhline(0,color='.65',lw=.5)
        ax.set_title(f'{c["cell"]} · {c["group"]} · {c["partition"]}\n'+('2 nA pulse' if side==0 else 'recovery'),fontsize=9)
        ax.set_xlabel('Time from '+('onset' if side==0 else 'offset')+' (s)',fontsize=8);ax.set_ylabel('Δ voltage (mV)',fontsize=8);ax.tick_params(labelsize=8)
        if side==1:ax.set_ylim(-8,5)
for ax in axes[5,2:]:ax.axis('off')
fig.suptitle('APL full-pulse candidates: improved compression, inadequate recovery\nAll 11 cells, 65 repeats, four passive variants and two voltage-correction scenarios',fontsize=16,y=.994)
fig.legend(handles=[Line2D([],[],color='black',label='Observed mean (gray: repeats)'),Line2D([],[],color='#667085',ls=':',label='Fixed passive controls'),Line2D([],[],color='#d97706',label='No slow inactivation'),Line2D([],[],color='#087f8c',label='With slow inactivation')],loc='lower center',ncol=4,fontsize=10)
fig.tight_layout(rect=[0,.025,1,.963]);fig.savefig(ROOT/'validation/apl-full-pulse.png',dpi=130);plt.close(fig)
