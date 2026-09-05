#!/usr/bin/env python3
"""Display recovered curves without fitting or assigning intrinsic kinetics."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'validation/apl-timecourse-traces.json').read_text())
fig,axes=plt.subplots(2,3,figsize=(12,6),sharex=True,sharey='row')
for col,(panel,title) in enumerate(zip(['C','D','E'],['Horizontal-lobe stimulation','Vertical-lobe stimulation','Calyx stimulation'])):
 for row,signal in enumerate(['calcium','dye']):
  ax=axes[row,col]
  for trace in r['traces']:
   if trace['panel']!=panel or trace['signal']!=signal:continue
   t=trace['time_s_common_calcium_bar'];color=trace['color_rgb']
   ax.fill_between(t,trace['stroke_dff_lower'],trace['stroke_dff_upper'],color=color,alpha=.12,lw=0)
   ax.plot(t,trace['baseline_adjusted_dff'],color=color,lw=1)
  ax.axvline(0,color='black',lw=.7);ax.axhline(0,color='black',lw=.5,alpha=.4)
  ax.set_xlim(-4.5,14.5);ax.grid(alpha=.15)
  if row==0:ax.set_title(f'Fig. 5{panel}: {title}',fontsize=10)
  else:ax.set_xlabel('Time from ATP marker (s), common bar')
axes[0,0].set_ylabel('APL GCaMP6f ΔF/F\n(display baseline adjusted)')
axes[1,0].set_ylabel('Red dye ΔF/F\n(display baseline adjusted)')
fig.suptitle('Published APL calcium and stimulus-dye time courses',fontsize=15)
fig.text(.5,.025,'All 80 displayed curves retained. Shading shows extracted stroke bounds, not SEM.\nThe dye row’s own 5 s bar would stretch its times by 10.77%; both axes are saved. Approximate source imaging rate: 5 Hz.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.1,1,.94))
p=ROOT/'validation/apl-timecourse-extraction-figure.png'
if p.exists():raise FileExistsError(p)
fig.savefig(p,dpi=180)
print(p)
for panel,ranks in [('C',[11,12]),('D',[12,13]),('E',[0,1])]:
 for signal in ['calcium','dye']:
  rows=[t for t in r['traces'] if t['panel']==panel and t['signal']==signal and t['color_rank'] in ranks]
  print(panel,signal,[(t['color_rank'],round(t['displayed_peak_dff'],4),t['displayed_peak_s_common_bar'],round(t['area_over_peak_common_s'],4)) for t in rows])
