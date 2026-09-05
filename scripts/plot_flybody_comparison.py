"""Static scientific figure from the frozen motor-comparison summaries."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    report = json.loads(Path('validation/flybody-motor-comparison.json').read_text())
    plan = json.loads(Path('validation/flybody-motor-comparison-plan.json').read_text())
    cpg = [r for r in json.loads(Path('validation/cpg-calibration-experiment.json').read_text())['trials'] if r['variant']=='baseline']
    rows = {r['case']:r for r in report['trials'] if r['seed']==11}
    plt.rcParams.update({'font.size':11, 'axes.spines.top':False, 'axes.spines.right':False,
                         'axes.titleweight':'bold', 'figure.facecolor':'white'})
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.8))
    blue, orange, gray = '#176eab', '#d66a25', '#616977'
    x = np.arange(2)
    ax=axes[0,0]
    baseline=[d['cpg_abs_yaw_deg_s'] for d in report['decisions']['straight']]
    current=[d['flybody_abs_yaw_deg_s'] for d in report['decisions']['straight']]
    ax.bar(x-.18,baseline,.34,label='Frozen CPG',color=orange)
    ax.bar(x+.18,current,.34,label='FlyBody',color=blue)
    ax.set(xticks=x,xticklabels=['10 mm/s','20 mm/s'],ylabel='Median absolute yaw rate (°/s)',title='A  Less reversing yaw in straight walking')
    ax.legend(frameon=False)
    ax.text(.03,.94,'74.6% / 82.9% reduction',transform=ax.transAxes,va='top')
    ax=axes[0,1]
    for i,speed in enumerate([10,20]):
        ref=plan['source_reference'][str(speed)]['metrics']['LF_frequency_hz']
        ax.errorbar(i,ref['median'],yerr=[[ref['median']-ref['p25']],[ref['p75']-ref['median']]],fmt='o',color=gray,capsize=5,label='Source animal IQR' if i==0 else None)
        ax.scatter(i+.12,rows[f'straight{speed}']['legs']['LF']['frequency_hz']['median'],marker='s',s=65,color=blue,label='FlyBody' if i==0 else None)
        values=[r['legs']['LF']['frequency_hz']['median'] for r in cpg if r['drive']==speed/20]
        ax.scatter(i-.12,np.mean(values),marker='^',s=65,color=orange,label='Frozen CPG' if i==0 else None)
    ax.set(xticks=x,xticklabels=['10 mm/s','20 mm/s'],ylim=(5,19),ylabel='Left foreleg cycle frequency (Hz)',title='B  High-command cadence overshoots')
    ax.legend(frameon=False,fontsize=9)
    ax=axes[0,2]
    legs=['LF','LM','LH','RF','RM','RH'];x=np.arange(6)
    ref=plan['source_reference']['20']['metrics']
    med=np.array([ref[l+'_tibia_rom_deg']['median'] for l in legs])
    low=np.array([ref[l+'_tibia_rom_deg']['p25'] for l in legs]);high=np.array([ref[l+'_tibia_rom_deg']['p75'] for l in legs])
    ax.errorbar(x,med,yerr=[med-low,high-med],fmt='o',capsize=4,color=gray,label='Source animal IQR')
    ax.scatter(x+.16,[rows['straight20']['legs'][l]['tibia_rom_deg']['median'] for l in legs],marker='s',color=blue,label='FlyBody')
    ax.scatter(x-.16,[np.mean([r['legs'][l]['tibia_rom_deg']['median'] for r in cpg if r['drive']==1]) for l in legs],marker='^',color=orange,label='Frozen CPG')
    ax.set(xticks=x,xticklabels=legs,ylim=(0,100),ylabel='Tibia range of motion (°)',title='C  20 mm/s excursions remain too small')
    ax.legend(frameon=False,fontsize=9)
    ax=axes[1,0]
    for name,color in [('straight10',gray),('straight20',blue),('left20','#16855f'),('right20',orange)]:
        raw=np.load(rows[name]['trace']);xy=(raw['pose'][:,:2]-raw['pose'][0,:2])*10
        target=(raw['target_pose'][:,:2]-raw['target_pose'][0,:2])*10
        ax.plot(xy[:,0],xy[:,1],label=name,color=color)
        ax.plot(target[:,0],target[:,1],ls=':',lw=1,color=color)
    ax.set(xlabel='Forward X (mm)',ylabel='World Y (mm)',title='D  Both signed turns follow their targets')
    ax.set_aspect('equal',adjustable='datalim');ax.legend(frameon=False,fontsize=9,ncol=2)
    ax.text(.02,.02,'Dotted: command reference; full 1.5 s',transform=ax.transAxes,fontsize=9)
    ax=axes[1,1]
    values=[rows['zero']['speed_mm_s']['median'],rows['withdraw20']['after_withdrawal']['speed_mm_s']['median']]
    ax.bar([0,1],values,width=.5,color=[gray,blue]);ax.axhline(1,color='#b82236',ls='--',label='Declared ≤1 mm/s gate')
    for i,v in enumerate(values):ax.text(i,v+.07,f'{v:.2f}',ha='center')
    ax.set(xticks=[0,1],xticklabels=['Zero\n0.3–1.5 s','Withdrawal\n1.0–1.5 s'],ylim=(0,2.4),ylabel='Median unsmoothed root speed (mm/s)',title='E  Both quiescence checks fail')
    ax.legend(frameon=False,fontsize=9,loc='upper right')
    ax.text(.03,.03,'Net displacement: 0.018 / 0.173 mm\nLittle drift does not remove local motion.',transform=ax.transAxes,fontsize=9)
    ax=axes[1,2];ax.axis('off')
    ax.text(0,1,'F  Interpretation and limits',weight='bold',fontsize=12,va='top')
    ax.text(0,.88,'• Frozen female-derived body and released policy\n• No neural decoder, controller fit, or default change\n• 12 trials; seed pairs are physically identical\n• All physical stability gates passed\n• Four / seven source animals at 10 / 20 mm/s\n• Mixed-sex, curated running; sex per fly unknown\n• Source poses are body-size normalized\n• CPG/FlyBody differ in geometry and contacts\n• High cadence and small ROM remain mismatched\n• Declared overall promotion criterion failed',va='top',linespacing=1.8,fontsize=10)
    fig.suptitle('Frozen FlyBody motor comparison: better steering, incomplete gait and stopping',fontsize=17,weight='bold')
    fig.text(.5,.015,'Source = existing 800 Hz freewalking benchmark; FlyBody 500 Hz; frozen CPG 200 Hz. Same 7.5 ms heading/cycle smoothing. No raw experimental arrays redistributed.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,.96),h_pad=2.5,w_pad=2)
    for suffix in ['png','svg']:
        fig.savefig(Path('validation')/f'flybody-motor-comparison.{suffix}',dpi=180)
    print('Saved validation/flybody-motor-comparison.png and .svg')


if __name__=='__main__':
    main()
