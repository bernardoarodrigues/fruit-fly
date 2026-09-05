#!/usr/bin/env python3
"""Plot frozen MBON inventory summaries; no raw-spike reduction or model imports."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import traceback

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import PercentFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'validation/navigation-ladder-mbon-input-results.json'
FIGURE = ROOT/'validation/navigation-ladder-mbon-input-figure-v2.png'
RECEIPT = ROOT/'validation/navigation-ladder-mbon-input-plot-receipt-v2.json'
EXPECTED = '94599739999cd8d8b04e5898de012ceaf63a721bdf437dea291b6b3ad4b174d6'
CLASSES = ['Kenyon_Cell','DAN','<missing>','MBON','ALPN','CX']
DISPLAY_CLASSES = ['Kenyon cell','DAN','Missing class','MBON','ALPN','CX']


def record(path):
    path = Path(path); digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=digest.hexdigest())


def main():
    if FIGURE.exists() or RECEIPT.exists(): raise FileExistsError('Preserve first rendering and receipt')
    receipt = dict(schema=1,passed=False,
        scope='Figure from frozen summary values only. No model, producer import, new spike reduction, fit or biological research.',
        independent_numerical_review_status='Not asserted or inspected by this plotting receipt.',
        aggregation=dict(positive_share='For each trial, divide each of the six saved class_positive_ranking p_increment values by their sum. These are positive accepted model increments in [5000,15000); no negative-state subtraction or current conversion.',
            isi='In each existing half-open window, sum saved isi_at_22_ticks_count over ten cells and divide by the sum of isi_interval_count over the same cells. A zero denominator gives null/undefined, never zero. Interval is assigned by its second spike with prior spike carried across windows.'),
        rendering=dict(format='PNG',render_attempt=2,log_color_scale=True,isi_stairs_baseline=None,
                       correction='Move the legend into unused right-panel space; preserve first PNG, receipt and source. No numerical change.',
                       visual_inspection='Separate from this automated data/render receipt; see the final reviewer message.'))
    inputs = []; checks = 0
    try:
        result_record = record(RESULTS); inputs.append(result_record)
        assert result_record['sha256']==EXPECTED; checks+=1
        data=json.loads(RESULTS.read_text()); assert data['passed']; checks+=1
        for rec in [data['plan']]+data['artifacts']:
            assert record(ROOT/rec['path'])==rec,rec['path'];inputs.append(rec);checks+=1
        script_record=record(__file__);inputs.append(script_record)
        for prior in ['scripts/plot_navigation_ladder_mbon_inputs.py',
                      'validation/navigation-ladder-mbon-input-figure.png',
                      'validation/navigation-ladder-mbon-input-plot-receipt.json']:
            inputs.append(record(ROOT/prior))
        plan=json.loads((ROOT/data['plan']['path']).read_text())
        assert len(plan['targets']['indices'])==10 and set(data['group_labels']['class'])==set(CLASSES); checks+=1
        assert data['intervention_gate']['delivery_window_ticks']==[5000,15000]; checks+=1
        byspec={(t['spec']['seed'],t['spec']['condition']):t for t in data['trials']}
        order=[(s,c) for s in [11,12,13] for c in ['constant_baseline','ethyl_acetate']]
        assert len(data['trials'])==6 and set(byspec)==set(order);checks+=1
        assert {t['spec']['name'] for t in data['trials']}=={t['name'] for t in plan['trials']};checks+=1
        edges=np.asarray(plan['window_edges_ticks'],dtype=np.int64)
        assert edges.tolist()==[0,500,5000,10000,15000,20000,25000,30000];checks+=1
        seconds=edges*plan['dt_ms']/1000
        plot_rows=[]
        for seed,condition in order:
            t=byspec[(seed,condition)]; values={r['label']:r['p_increment'] for r in t['class_positive_ranking']}
            assert set(values)==set(CLASSES) and all(math.isfinite(v) and v>=0 for v in values.values());checks+=1
            total=math.fsum(values.values()); assert total>0;checks+=1
            numer=t['isi_at_22_ticks_count'];denom=t['isi_interval_count']
            assert len(numer)==len(denom)==7 and all(len(v)==10 for v in numer+denom);checks+=1
            numerator=[sum(v) for v in numer];denominator=[sum(v) for v in denom]
            assert all(0<=a<=b for a,b in zip(numerator,denominator)) and denominator[0]==0;checks+=1
            fraction=[a/b if b else None for a,b in zip(numerator,denominator)]
            plot_rows.append(dict(spec=t['spec'],class_positive_increment={c:values[c] for c in CLASSES},
                total_positive_increment=total,class_share_percent={c:100*values[c]/total for c in CLASSES},
                isi_at_22_numerator=numerator,isi_interval_denominator=denominator,isi_fraction=fraction))
        pairs=[]
        for i,seed in enumerate([11,12,13]):
            constant,ea=plot_rows[2*i:2*i+2]
            pairs.append(dict(seed=seed,numerators_equal=constant['isi_at_22_numerator']==ea['isi_at_22_numerator'],
                denominators_equal=constant['isi_interval_denominator']==ea['isi_interval_denominator'],
                fractions_equal=constant['isi_fraction']==ea['isi_fraction']))
        receipt.update(input_artifacts=inputs,plotted_trials=plot_rows,paired_isi_overlap=pairs,
                       window_edges_ticks=edges.tolist(),window_edges_seconds=seconds.tolist(),class_order=CLASSES,
                       isi_ticks=22,isi_ms=22*plan['dt_ms'],checks=checks)
        shares=np.array([[r['class_share_percent'][c] for r in plot_rows] for c in CLASSES])
        positive=shares[shares>0];vmin=10**math.floor(math.log10(float(positive.min())))
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'savefig.facecolor':'white'})
        fig,(left,right)=plt.subplots(1,2,figsize=(13.0,5.8),gridspec_kw={'width_ratios':[1.12,1.]})
        fig.subplots_adjust(left=.09,right=.965,top=.77,bottom=.25,wspace=.48)
        fig.suptitle('MBON model input inventory',x=.09,y=.97,ha='left',fontsize=19,fontweight='bold')
        fig.text(.09,.91,'Conditional saved-history reconstruction · H1 · MBON12/13/14 (10 cells) · three numerical seeds',fontsize=10.5,color='#444444')
        norm=LogNorm(vmin=vmin,vmax=100)
        cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#f1f1f1')
        image=left.imshow(np.ma.masked_less_equal(shares,0),norm=norm,cmap=cmap,aspect='auto')
        left.set_title('Positive accepted increments by source class\nDelivery window [0.5, 1.5) s',loc='left',pad=12)
        left.set_xticks(range(6),[f'{seed}\n'+('Constant' if cond=='constant_baseline' else 'EA') for seed,cond in order])
        left.set_yticks(range(6),DISPLAY_CLASSES);left.tick_params(length=0)
        left.set_xlabel('Seed and stimulus condition',labelpad=8)
        left.set_xticks(np.arange(-.5,6,1),minor=True);left.set_yticks(np.arange(-.5,6,1),minor=True)
        left.grid(which='minor',color='white',linewidth=1);left.tick_params(which='minor',length=0)
        for i in range(6):
            for j in range(6):
                val=shares[i,j]
                label=f'{val:.2f}' if val>=10 else f'{val:.3f}' if val>=.1 else f'{val:.4f}'
                left.text(j,i,label,ha='center',va='center',fontsize=9,color='black' if val>0 and norm(val)>.66 else 'white' if val>0 else '#444444')
        bar=fig.colorbar(image,ax=left,fraction=.046,pad=.025,ticks=[10.**j for j in range(int(math.log10(vmin)),3)])
        bar.set_label('Share of positive increments (%) · log color',fontsize=9)
        bar.ax.tick_params(labelsize=8)
        colors=['#0072B2','#D55E00','#009E73'];markers=['o','s','^']
        midpoint=(seconds[:-1]+seconds[1:])/2
        for i,(seed,color,marker) in enumerate(zip([11,12,13],colors,markers)):
            constant,ea=plot_rows[2*i:2*i+2]
            if pairs[i]['fractions_equal']:
                y=np.array([np.nan if x is None else x for x in constant['isi_fraction']])
                right.stairs(y,seconds,baseline=None,color=color,linewidth=1.5,alpha=.8)
                right.plot(midpoint,y,linestyle='none',marker=marker,mfc='white',mec=color,ms=5,label=f'Seed {seed}: EA = constant')
            else:
                for row,linestyle,label in [(constant,'-',f'Seed {seed}: constant'),(ea,'--',f'Seed {seed}: EA')]:
                    y=np.array([np.nan if x is None else x for x in row['isi_fraction']])
                    right.stairs(y,seconds,baseline=None,color=color,linestyle=linestyle,linewidth=1.5,label=label)
        right.axvspan(0,.05,color='#cccccc',alpha=.3,hatch='////',linewidth=0)
        right.axvspan(.5,1.,color='#777777',alpha=.06)
        right.axvline(1.5,color='#555555',linestyle=':',linewidth=1)
        right.set_title('ISIs at 22 ticks (2.2 ms)\nFraction of intervals across the 10 cells',loc='left',pad=12)
        right.set(xlim=(0,3),ylim=(.90,1.015),xlabel='Simulation time (s)',ylabel='Fraction at the model ISI lower bound')
        right.set_xticks(np.arange(0,3.01,.5));right.set_yticks([.90,.925,.95,.975,1.]);right.yaxis.set_major_formatter(PercentFormatter(1,decimals=1))
        right.grid(axis='y',alpha=.18)
        right.text(.75,.903,'EA pulse',ha='center',va='bottom',fontsize=8.5,color='#666666')
        right.text(1.53,.911,'Input off',fontsize=8.5,color='#555555',rotation=90,ha='left',va='bottom')
        right.annotate('0–0.05 s: undefined\n(no observed intervals)',xy=(.025,.91),xytext=(.16,.919),fontsize=8.5,
                       arrowprops={'arrowstyle':'-','color':'#777777'},color='#555555')
        if all(all(x==1 for x in r['isi_fraction'][2:]) for r in plot_rows):
            right.text(1.95,.989,'All six = 100%\nfrom 0.5 s',fontsize=9,ha='center',va='top',color='#333333')
        right.legend(loc='center right',bbox_to_anchor=(.985,.44),frameon=False,fontsize=9,ncol=1,handletextpad=.4)
        fig.text(.09,.10,'Positive-increment shares are model quantities, not physiological currents. ISIs are assigned by the second spike; empty windows are undefined.',fontsize=9,color='#444444')
        fig.text(.09,.055,'EA: ethyl acetate. Paired overlap is exact where stated. This input inventory does not establish the cause of MBON firing.',fontsize=9,color='#444444')
        fig.savefig(FIGURE,dpi=180);plt.close(fig)
        for rec in inputs: assert record(ROOT/rec['path'])==rec,rec['path']
        receipt.update(passed=True,output_artifact=record(FIGURE),checks=checks+len(inputs))
    except (Exception,KeyboardInterrupt) as e:
        receipt['failure']=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        if FIGURE.exists():receipt['output_artifact']=record(FIGURE)
    receipt['completed_utc']=datetime.now(timezone.utc).isoformat()
    with RECEIPT.open('x') as f:json.dump(receipt,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(passed=receipt['passed'],receipt=record(RECEIPT),figure=receipt.get('output_artifact'),failure=receipt.get('failure'))))
    return 0 if receipt['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
