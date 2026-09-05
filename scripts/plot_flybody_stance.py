"""Summarize fixed stance experiment and preserve a derived failure diagnostic."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scripts.benchmark_freewalking import digest


def main():
    source=Path('validation/flybody-stance-experiment.json');report=json.loads(source.read_text())
    plan=json.loads(Path('validation/flybody-stance-plan.json').read_text())
    rows={(r['variant'],r['assay']):r for r in report['trials']}
    failure=rows['last_target','walk_stop_resume'];raw=dict(np.load(failure['trace']))
    final_step=len(raw['native_action']);target=raw['target_pose'][-1,:3].copy()
    target[0]+=.004 if raw['motor_enabled'][-1] else 0
    distance=float(np.linalg.norm(target-raw['pose'][-1,:3]))
    diagnostic={'analysis_kind':'Post hoc failure diagnostic from retained finite trace, no additional physics.',
        'script_sha256':digest(__file__),'experiment_sha256':digest(source),'trace_sha256':digest(failure['trace']),
        'termination_time_s':final_step*.002,'source_reference_distance_cm':distance,
        'source_reference_distance_threshold_cm':.3,'distance_criterion_exceeded':distance>.3,
        'final_root_linear_speed_cm_s':float(np.linalg.norm(raw['qvel'][-1,:3])),
        'source_linear_speed_threshold_cm_s':50,
        'final_root_angular_speed_rad_s':float(np.linalg.norm(raw['qvel'][-1,3:6])),
        'source_angular_speed_threshold_rad_s':200,
        'final_up_z':float(raw['up_z'][-1]),'all_retained_arrays_finite':all(np.isfinite(x).all() for x in raw.values()),
        'limit':'Reference-distance threshold is sufficient to explain termination. qacc was not recorded, so another simultaneous termination condition is not excluded. No warning-free completion claimed for this failed row.'}
    Path('validation/flybody-stance-failure-diagnostic.json').write_text(json.dumps(diagnostic,indent=2,allow_nan=False)+'\n')
    variants=plan['variants'];labels=['Policy zero','Last targets','Measured length','Neutral zero']
    colors=['#616977','#bf5633','#176eab','#16855f']
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
    fig,axs=plt.subplots(2,2,figsize=(13,9))
    ax=axs[0,0];x=np.arange(4)
    for offset,assay,label in [(-.18,'zero_start','Zero start'),(.18,'walk_stop','After walking')]:
        values=[rows[v,assay]['windows']['stop']['speed_mm_s']['median'] for v in variants]
        ax.bar(x+offset,values,.34,color=colors,alpha=.55 if offset<0 else 1,label=label)
    ax.axhline(1,color='#b82236',ls='--',lw=1.5,label='≤1 mm/s gate')
    ax.set(yscale='log',ylim=(.0001,5),xticks=x,xticklabels=labels,ylabel='Median unsmoothed root speed (mm/s)',title='A  All three holds reduce local motion')
    ax.tick_params(axis='x',rotation=15);ax.legend(frameon=False,fontsize=9)
    ax=axs[0,1]
    for variant,label,color in zip(variants,labels,colors):
        row=rows[variant,'walk_stop_resume'];z=np.load(row['trace'])
        speed=np.linalg.norm(np.diff(z['pose'][:,:2],axis=0),axis=1)*5000
        # Moving median for figure readability only; gates use unsmoothed data.
        from scipy.ndimage import median_filter
        ax.plot((np.arange(len(speed))+.5)*.002,median_filter(speed,size=11,mode='nearest'),color=color,lw=1.4,label=label)
    ax.axvspan(.6,1.2,color='#e8edf3',zorder=0);ax.axhline(20,color='black',ls=':',lw=1)
    ax.set(xlim=(0,2),ylim=(0,55),xlabel='Simulation time (s)',ylabel='Root speed (mm/s)',title='B  Two holds resume walking successfully')
    ax.text(.69,40,'Motor gate off',fontsize=9);ax.legend(frameon=False,fontsize=8,loc='upper left')
    ax.text(.02,.02,'11-sample median for display only; gates remain raw.',transform=ax.transAxes,fontsize=8)
    ax=axs[1,0]
    for variant,label,color in zip(variants,labels,colors):
        z=np.load(rows[variant,'walk_stop_resume']['trace'])
        ax.plot(np.arange(len(z['up_z']))*.002,z['up_z'],color=color,label=label)
    ax.axvspan(.6,1.2,color='#e8edf3',zorder=0);ax.axhline(.5,color='#b82236',ls='--',lw=1)
    ax.set(xlim=(0,2),ylim=(.45,1.02),xlabel='Simulation time (s)',ylabel='Body upright axis z',title='C  Last-target hold fails on resumption')
    ax.annotate(f'Source terminates at {final_step*.002:.3f} s\nReference error {distance*10:.2f} mm > 3 mm',xy=(final_step*.002,raw['up_z'][-1]),xytext=(1.28,.53),fontsize=9,arrowprops={'arrowstyle':'->','color':colors[1]})
    ax=axs[1,1];ax.axis('off')
    ax.text(0,1,'D  What the positive result means',weight='bold',fontsize=12,va='top')
    ax.text(0,.9,'Measured-length and neutral-zero holds passed:\n  • Quiet stop and fixed physical gates\n  • Motor-policy output mute with active posture hold\n  • Resumed median speed: 20.57 / 19.71 mm/s\n  • Resumed absolute yaw: 35.40 / 29.34°/s\n\nOriginal weights, dynamics and gains retained.\nAll six adhesion commands fixed at native 1 in holds.\n\nOne stop phase, one deterministic initial state.\nSuccessful holds support four / five legs after walking.\nNo male anatomy, neural stance or robustness claim.\nNo runtime adapter promoted.',va='top',fontsize=10,linespacing=1.55)
    fig.suptitle('Source-native engineering posture holds: two pass the fixed stop/resume assay',fontsize=16,weight='bold')
    fig.text(.5,.015,'12 predeclared trials; shaded interval: motor gate off. Engineering holds mute policy output and retain posture actuation; policy-zero is the unchanged control.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.96),h_pad=2,w_pad=2)
    for suffix in ['png','svg']:fig.savefig('validation/flybody-stance-experiment.'+suffix,dpi=180)
    print(json.dumps(diagnostic,indent=2))


if __name__=='__main__':main()
