#!/usr/bin/env python3
"""Plot previously reduced author profiles, without refitting."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/'validation/apl-spatial-reference-data.json').read_text())
result = json.loads((ROOT/'validation/apl-spatial-reference-results.json').read_text())
out = ROOT/'validation/apl-spatial-reference-figure.png'
summary = ROOT/'validation/apl-spatial-reference-summary.json'
if out.exists() or summary.exists():
    raise FileExistsError('Preserve completed artifacts')
colors = {25:'#b4650b', 50:'#197d91', 75:'#9655a5'}
fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
for col, (site, title) in enumerate(zip(['Hstim','Vstim','Cstim'], ['Horizontal lobe stimulation','Vertical lobe stimulation','Calyx stimulation'])):
    for row, model in enumerate(['connectome','backbone']):
        ax = axes[row,col]
        for branch, ls, marker in [('CtoH','-','o'),('CtoV','--','x')]:
            pts = [p for p in data['fig8_profiles'][site] if p['branch']==branch]
            x = [p['distance_um'] for p in pts]
            for length, color in colors.items():
                ax.plot(x,[p['predictions'][f'{model}_{length}'] for p in pts],ls,color=color,lw=1.5)
            ax.plot(x,[p['observed'] for p in pts],ls,color='#202020',marker=marker,ms=3,lw=1)
        ax.axhline(0,color='#aaaaaa',lw=.6)
        ax.set_ylim(-.12,1.12)
        ax.grid(alpha=.15)
        if row==0: ax.set_title(title,fontsize=11)
        else: ax.set_xlabel('Normalized backbone distance from calyx (µm)')
        if col==0: ax.set_ylabel(('Connectome skeleton' if row==0 else 'Straight backbone')+'\nNormalized response')
handles=[Line2D([0],[0],color='#202020',marker='o',label='Source mean'),
         *[Line2D([0],[0],color=c,label=f'{l} µm model') for l,c in colors.items()],
         Line2D([0],[0],color='#777777',ls='-',label='Calyx → horizontal'),
         Line2D([0],[0],color='#777777',ls='--',label='Calyx → vertical')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.955),ncol=6,frameon=False,fontsize=9)
fig.suptitle('Published APL spatial profiles and fixed author predictions',fontsize=15,y=.997)
fig.text(.5,.015,'Amin et al. 2020, Figure 8 source data. No refitting. Shared path 0–180 µm appears in both branches; scores count it once.\nReporter-normalized profiles, not membrane voltage or a calibrated GABA release law.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.07,1,.9])
fig.savefig(out,dpi=160)
plt.close(fig)
groups=[]
for panel in ['A1','B1','C1','A4','B4','C4']:
    for region in ['C','H','V']:
        pts=[v for v in data['fig7_observations'] if v['sheet']=='Fig 7' and v['section']=='bottom' and v['panel']==panel and v['region']==region]
        a=np.array([v['value'] for v in pts])
        groups.append(dict(panel=panel,region=region,n_observation_slots=len(a),mean=float(a.mean()),
                           sem_across_slots=float(a.std(ddof=1)/math.sqrt(len(a))),source_cells=[v['cell'] for v in pts]))
pooled=[dict(model=model,length_um=l,equal_site_rmse=math.sqrt(sum(x['unique_segments']['rmse']**2 for x in result['comparisons'] if x['model']==model and x['length_um']==l)/3)) for model in ['connectome','backbone'] for l in colors]
summary.write_text(json.dumps(dict(descriptive_fig7_groups=groups,pooled_profile_scores=pooled,
    limitations=['Post-reduction descriptive summary, not hypothesis test.',
                 'Observation slots are not identified independent flies.',
                 'APL and KC values have different normalization and cohorts; no conversion ratio is inferred.']),indent=2)+'\n')
print(out)
