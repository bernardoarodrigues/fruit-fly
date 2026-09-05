#!/usr/bin/env python3
"""Layout-only overlay amendment; original source/plan/extraction/overlay retained."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np
from PIL import Image
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'validation/orn-pn-depression-fig8f'
def path(s):return Path(str(P)+s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
result=path('-results.json');expected='5a664d8f890e995b5bd79402bff7ea53977d14205098ee2922e6cbd4bacaabce'
assert sha(result)==expected
output=path('-overlay-v2.png');receipt=path('-plot-receipt-v2.json')
if output.exists() or receipt.exists():raise FileExistsError('Preserve layout amendment')
data=json.loads(result.read_text());assert data['passed']
colors={15:'#2767A3',20:'#D67C0F',50:'#19855C'};markers={15:'o',20:'s',50:'^'}
fig,(a,b)=plt.subplots(1,2,figsize=(12,8));fig.subplots_adjust(left=.065,right=.985,bottom=.25,top=.85,wspace=.22)
a.imshow(np.array(Image.open(path('-embedded.jpg'))),cmap='gray',vmin=0,vmax=255,interpolation='nearest');a.set_xlim(82,370);a.set_ylim(1035,740)
for r in data['rows']:
 if r['component_id']==0:continue
 color=colors[r['frequency_hz']];a.plot(r['marker_x_native_px'],r['marker_y_native_px'],'+',color=color,ms=4,mew=.8)
 if r['sem_percent_initial'] is not None:a.plot([r['error_x_native_px']]*2,[r['error_top_native_px'],r['error_bottom_native_px']],linestyle='none',marker='_',color=color,ms=5,mew=.9)
a.set_title('Native raster + marker centers / bar endpoints',fontsize=10.5);a.set_xlabel('Embedded-image x (native pixels)');a.set_ylabel('Embedded-image y (native pixels, downward)')
for freq in [15,20,50]:
 rows=[r for r in data['rows'] if r['frequency_hz']==freq and r['mean_percent_initial'] is not None]
 b.plot([r['time_ms'] for r in rows],[r['mean_percent_initial'] for r in rows],color=colors[freq],marker=markers[freq],ms=4,lw=.8,label=f'{freq} Hz')
 for r in rows:
  if r['sem_percent_initial'] is not None:b.vlines(r['time_ms'],r['error_low_percent_initial'],r['error_high_percent_initial'],color=colors[freq],lw=.8)
  else:b.scatter(r['time_ms'],r['mean_percent_initial'],s=70,facecolors='none',edgecolors='#B53B2E',linewidths=1.1)
b.axhline(0,color='.6',lw=.7);b.set_xlim(-8,505);b.set_ylim(-18,108);b.set_xlabel('Plotted event coordinate (ms; phase not assigned)');b.set_ylabel('uEPSC amplitude (% initial)');b.set_title('Individual means; visible stem extents only',fontsize=10.5);b.legend(frameon=False);b.grid(alpha=.2)
fig.suptitle('Kazama & Wilson 2008, Fig. 8F: VM2 synaptic depression',fontsize=16,y=.955)
fig.text(.065,.035,'Native JPEG extraction; n=6 cells in panel caption. General methods specify mean +/- SEM.\n'
 '40 individual means / 37 resolved bars; shared initial means omitted. Red rings: unresolved SEM, not zero.\n'
 'Raster sensitivity is separate from SEM. No fit, event-phase inference, or transfer to the neural runtime.',fontsize=10,linespacing=1.7)
fig.savefig(output,dpi=180);plt.close(fig);assert sha(result)==expected
with receipt.open('x') as f:json.dump(dict(created_utc=datetime.now(timezone.utc).isoformat(),source_results_sha256=expected,
 source_plot_script_sha256=sha(__file__),output=dict(path=str(output.relative_to(ROOT)),bytes=output.stat().st_size,sha256=sha(output)),
 amendment='Original overlay footer overlapped xlabel; preserve original and change layout only. No numeric extraction rerun.',original_plot_receipt_sha256=sha(path('-plot-receipt.json'))),f,indent=2);f.write('\n')
print(json.dumps(dict(output=str(output),sha256=sha(output))))
