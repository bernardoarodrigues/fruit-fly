#!/usr/bin/env python3
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-reporter-filter-results.json').read_text());a=np.load(ROOT/r['arrays']['path']);t=a['time_s']
fig,axes=plt.subplots(2,3,figsize=(12,6),sharex=True,sharey=True)
for ax,(panel,rank) in zip(axes.T.flat,[('C',11),('C',12),('D',12),('D',13),('E',0),('E',1)]):
 for clock,color,label in [('common_calcium_bar','#c05b23','Fit: common clock'),('literal_row_bar','#1766a0','Fit: row-specific clock')]:
  arm=next(x for x in r['arms'] if x['clock']==clock and x['input_proxy']=='nonnegative')
  c=next(x for x in arm['cases'] if x['panel']==panel and x['color_rank']==rank and x['model']=='fitted_lowpass')
  y,lo,hi,p,pl,ph,u=a[c['array_key']]
  if clock=='common_calcium_bar':
   ax.fill_between(t,lo,hi,color='black',alpha=.12,lw=0)
   ax.plot(t,y,color='black',lw=1.5,label='Calcium shape')
   ax.plot(t,u,color='#999999',lw=1,ls=':',label='Dye proxy (common clock)')
  ax.plot(t,p,color=color,lw=1.3,ls='--' if clock=='literal_row_bar' else '-',label=label)
 ax.set_title(f'{panel}, color rank {rank} · '+('calibration' if panel=='C' else 'evaluation'),fontsize=10)
 ax.grid(alpha=.18);ax.set_xlim(0,12);ax.set_ylim(-.15,1.12)
for ax in axes[-1]:ax.set_xlabel('Seconds after ATP marker')
for ax in axes[:,0]:ax.set_ylabel('Peak-normalized response')
axes[0,2].legend(loc='upper right',fontsize=7)
fig.suptitle('A first-order delay does not resolve the dye-to-calcium shape mismatch',fontsize=14)
fig.text(.5,.025,'Nonnegative input shown; signed controls are retained. Every fitted τ is zero, so fitted and instantaneous controls coincide.\nEach observed trace is peak-normalized; amplitudes and intrinsic neuronal kinetics are not validated. Shading is graphical, not SEM.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.1,1,.94))
p=ROOT/'validation/apl-reporter-filter-figure.png'
if p.exists():raise FileExistsError(p)
fig.savefig(p,dpi=180);print(p)
