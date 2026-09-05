"""Plot saved standalone rolling-reference dynamics; no simulation or fitting."""
from pathlib import Path
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT/'validation/flybody-persistent-experiment.json').read_text())
row = next(r for r in report['trials'] if r['case']=='rolling_switch12')
path = ROOT/row['trace']
assert hashlib.sha256(path.read_bytes()).hexdigest()==row['trace_sha256']
d = np.load(path)
t = d['native_time_s']
pose = d['pose_cm_quat'][:,:2]*10
speed = np.linalg.norm(np.diff(pose,axis=0),axis=1)/.002
fig,axes = plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
fig.suptitle('Rolling FlyBody: one predeclared 12 s stop/resume schedule',fontsize=15)
axes[0].plot(t,pose[:,0],label='Physical root x',color='#146e8a',lw=1.3)
axes[0].plot(t,d['target_pose_cm_quat'][:,0]*10,label='Integrated target x',color='#da8627',lw=1,ls='--')
axes[0].set_ylabel('Position (mm)');axes[0].legend(loc='upper left')
axes[1].plot(t[1:],speed,color='#146e8a',lw=.6,label='Raw 2 ms root chord speed')
axes[1].plot(t[1:],d['command_on'][1:]*20,color='#da8627',lw=1,ls='--',label='Current command')
axes[1].set_ylabel('Speed (mm/s)');axes[1].legend(loc='upper right')
axes[2].plot(t,d['reference_error_cm']*10,color='#146e8a',lw=.8,label='Root-reference error')
axes[2].axhline(3,color='#b23d47',ls='--',lw=1,label='Original physical guard (3 mm)')
axes[2].set_ylabel('Error (mm)');axes[2].set_xlabel('Native simulated time (s)');axes[2].legend(loc='upper left')
for ax in axes:
    for a,b in ((.6,1.2),(3,3.6),(6,6.6),(9,10.6)):
        ax.axvspan(a,b,color='#91a398',alpha=.17)
    ax.axvline(10,color='#777777',ls=':',lw=1)
    ax.grid(alpha=.18);ax.set_xlim(0,12)
fig.text(.5,-.012,'Shaded: active posture hold. Dotted line: former 10 s cutoff. Fixed learned policy; no neural graph in this assay.',ha='center',fontsize=9)
out = ROOT/'validation/flybody-persistent-motion.png'
fig.savefig(out,dpi=160,bbox_inches='tight')
print(out)
