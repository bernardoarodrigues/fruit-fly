#!/usr/bin/env python3
"""Display individual-KC tails from the closed attachment stress test."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
a=np.load(ROOT/'validation/apl-attachment-sensitivity-arrays.npz')
g=np.load(ROOT/'validation/male-apl-geometry-arrays.npz')
b=np.load(ROOT/'validation/apl-spatial-operator-arrays.npz')
fig,axes=plt.subplots(1,2,figsize=(11,4.8),sharex=True,sharey=True)
for ax,body,title in zip(axes,[10540,10977],['Right APL','Left APL']):
 p=f'b{body}_';ids=b[p+'output_contact_indices'];inv=b[p+'output_contact_inverse']
 kc,ki=np.unique(g[p+'counterpart_body_id'][ids],return_inverse=True);counts=np.bincount(ki)
 for j,(region,color) in enumerate(zip(['CA','gL','aL'],['#8c4a9e','#157ca3','#d06b27'])):
  control=a[p+'coupling'][1,0,j][inv];alternate=a[p+'coupling'][1,3,j][inv]
  d=np.abs(np.bincount(ki,weights=alternate-control)/counts)
  x=np.sort(d);y=(len(x)-np.arange(len(x)))/len(x)
  ax.step(x,y,where='pre',label=region,color=color,lw=1.8)
 ax.set(xscale='log',yscale='log',xlim=(1e-7,.1),ylim=(3e-4,1.1),title=f'{title} · {len(kc):,} postsynaptic KCs',xlabel='Absolute change in mean coupling per KC contact')
 ax.grid(True,which='major',alpha=.2)
axes[0].set_ylabel('Fraction of KCs with at least this change')
axes[1].legend(title='Unit-total input region',loc='lower left')
fig.suptitle('Regional averages hide larger changes for individual KCs',fontsize=14,y=.99)
fig.text(.5,.015,'Declared attachment stress test: +0.512 µm residual, ≥10 µm path separation; both ends moved.\nCoarse-radius reference, λ = 50 µm. Coupling is dimensionless; these are not physiological error bars.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.1,1,.94))
p=ROOT/'validation/apl-attachment-sensitivity-figure.png'
if p.exists():raise FileExistsError(p)
fig.savefig(p,dpi=180)
print(p)
