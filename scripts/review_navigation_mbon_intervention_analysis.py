#!/usr/bin/env python3
"""Independent integer-count/paired-rate audit of completed saved outputs."""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np
from review_navigation_mbon_intervention_numerics import Reader, record, load, write

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'validation/navigation-mbon-intervention-analysis-results.json'
DEST=ROOT/'validation/navigation-mbon-intervention-analysis-independent-review.json'
EDGES=[0,500,5000,10000,15000,20000,25000,30000]
TOL=1e-12


def scalar_spikes(indices,ticks,targets):
    columns={int(i):j for j,i in enumerate(targets)};n=len(targets)
    counts=[[0]*n for _ in range(7)];bins=[[0]*n for _ in range(60)]
    intervals=[[0]*n for _ in range(7)];at22=[[0]*n for _ in range(7)]
    first=[[-1]*n for _ in range(7)];last=[[-1]*n for _ in range(7)];previous={}
    for index,tick in zip(indices,ticks):
        index,tick=int(index),int(tick);assert index in columns and 0<=tick<30000
        j=columns[index];w=bisect_right(EDGES,tick)-1
        counts[w][j]+=1;bins[tick//500][j]+=1
        if first[w][j]<0:first[w][j]=tick
        last[w][j]=tick
        if index in previous:
            gap=tick-previous[index];assert gap>0
            intervals[w][j]+=1;at22[w][j]+=int(gap==22)
        previous[index]=tick
    return dict(counts=counts,bin_counts=bins,isi_intervals=intervals,isi_at_22=at22,first_ticks=first,last_ticks=last)


def main(expected):
    if DEST.exists():raise FileExistsError('Preserve first independent analysis review')
    check_counts=Counter();verified={};reader=None;context=None;out=dict(schema=1,passed=False,absolute_rate_tolerance_hz=TOL,
        scope='Saved-count and spike-time re-reduction only. Twelve final full-population count checkpoints; reviewer-retained postbranch MBON spikes plus independently audited original-control prefixes. No producer metric helper, graph solver or new neural simulation.',
        limits=['Continuous voltage/p/h summaries and their plots are not re-reduced here; the separate state/integrity and numerical reviews have their own scopes.',
                'Cohorts overlap and are not summed as disjoint groups. The reused prefix is not a new observation.',
                'Three paired numerical seeds do not constitute biological replicates or establish general robustness.',
                'A conditional contribution of positive KC deliveries does not uniquely identify a physiological repair or justify model promotion.'],
        remaining_physiology_gates=['Exact-target absolute inhibitory amplitude, receptor-component and compatible temporal calibration remain unresolved.',
            'Female VM2 normalized excitatory fits are conditional on denominator/phase and do not calibrate male VM7d or KC-to-MBON mechanisms.',
            'The imposed VM7d event-rate pair is not a measured broad odor ensemble; this branch test includes no body or natural navigation assay.'])
    def check(name,passed):
        check_counts[name]+=1
        if not passed:raise AssertionError(f'{name}: {context}')
    def pin(rec):
        check('pinned_file',record(ROOT/rec['path'])==rec);verified[rec['path']]=rec
    def exact(name,a,b):check(name,np.array_equal(np.asarray(a),np.asarray(b)))
    def close(name,a,b):check(name,np.allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=0,atol=TOL,equal_nan=False))
    try:
        r=record(RESULT);check('expected_result',r['sha256']==expected);verified[r['path']]=r
        data=load(RESULT);check('completed_analysis',data['passed']);pin(data['plan']);pin(data['array_artifact'])
        plan=load(ROOT/data['plan']['path']);check('window_contract',plan['window_edges_ticks']==EDGES and plan['bin_ticks']==500 and plan['dt_s']==.0001)
        for r in plan['inputs']:pin(r)
        for p in [Path(__file__),ROOT/'scripts/review_navigation_mbon_intervention_numerics.py']:
            r=record(p);verified[r['path']]=r
        ex=load(ROOT/'validation/navigation-mbon-intervention-plan.json');anatomy=load(ROOT/'validation/navigation-ladder-anatomy.json')
        integrity=load(ROOT/'validation/navigation-mbon-intervention-independent-review.json');numerics=load(ROOT/'validation/navigation-mbon-intervention-numerics-results.json')
        check('both_batch_reviews_pass',integrity['passed'] and numerics['passed']);pin(integrity['array_artifact'])
        targets=plan['targets'];durations=[(b-a)*.0001 for a,b in zip(EDGES[:-1],EDGES[1:])]
        check('all_six_specs',[t['spec'] for t in data['trials']]==plan['trials']==ex['trials'] and len(data['trials'])==6)
        oldrun=ROOT/plan['prior_run_dir'];run=ROOT/plan['run_dir']
        oldmanifest=load(oldrun/'artifact-manifest.json')['artifacts']
        manifests=oldmanifest+sum([load(run/s['name']/'result.json')['artifacts'] for s in plan['trials']],[])
        reader=Reader(manifests);summary={};reconstructed={}
        with np.load(ROOT/'validation/navigation-ladder-mbon-input-arrays.npz',allow_pickle=False) as old, np.load(ROOT/integrity['array_artifact']['path'],allow_pickle=False) as reviewed, np.load(ROOT/data['array_artifact']['path'],allow_pickle=False) as produced:
            exact('target_order_old',old['graph_indices'],targets);exact('target_order_reviewed',reviewed['target_indices'],targets);exact('target_order_produced',produced['target_indices'],targets)
            for trial in data['trials']:
                spec=trial['spec'];prefix='trial_'+str(spec['ordinal']);context=spec['name'];summary[spec['ordinal']]=dict(spec=spec,arms={});reconstructed[spec['ordinal']]={}
                original=old[prefix+'_target_spikes'];prefix_mask=original['tick']<5000
                streams={'control':(original['index'],original['tick']),
                    'intervention':(np.r_[original['index'][prefix_mask],reviewed[prefix+'_MBON_spike_indices']],np.r_[original['tick'][prefix_mask],reviewed[prefix+'_MBON_spike_ticks']])}
                for arm,base in [('control',oldrun),('intervention',run)]:
                    reader.context=(spec['name'],arm);nodes,payload=reader.bundle(base/spec['name']/'checkpoint-30000')
                    with np.load(payload,allow_pickle=False) as z:
                        counts=reader.decode(nodes['window_counts_observed'],z)
                        check('checkpoint_identity',all(reader.decode(nodes[k],z)==v for k,v in [('tick',30000),('arm','H1'),('seed',spec['seed']),('coherent_state',True)]))
                    check('checkpoint_count_domain',counts.shape==(7,ex['neurons']) and counts.dtype.kind=='i' and np.all(counts>=0))
                    if arm=='intervention':exact('reviewed_full_checkpoint_counts',counts,reviewed[prefix+'_window_counts'])
                    m=scalar_spikes(*streams[arm],targets);expected_arm=trial['arms'][arm]
                    for key,value in m.items():
                        exact('independent_'+key,value,produced[prefix+'_'+arm+'_'+key])
                        if key!='bin_counts':exact('JSON_'+key,value,expected_arm[key])
                    exact('spike_counts_vs_checkpoint',m['counts'],counts[:,targets])
                    rates=[[int(c)/durations[w] for c in row] for w,row in enumerate(m['counts'])]
                    close('target_rates',rates,expected_arm['rates_hz'])
                    reconstructed[spec['ordinal']][arm]=dict(target_counts=np.array(m['counts']),target_rates=np.array(rates),groups={})
                    for name,ids in [('population',range(ex['neurons']))]+[(name,g['indices']) for name,g in anatomy['groups'].items()]:
                        n=len(ids);total=[sum(int(row[i]) for i in ids) for row in counts];active=[sum(int(row[i])>0 for i in ids) for row in counts]
                        mean=None if n==0 else [total[w]/(durations[w]*n) for w in range(7)]
                        target=expected_arm['population'] if name=='population' else expected_arm['cohorts'][name]
                        exact('cohort_or_population_counts',total,target['spikes']);exact('cohort_or_population_active',active,target['active_cells'])
                        if n:close('cohort_or_population_rate',mean,target['mean_rate_hz'])
                        else:check('empty_cohort_rate_missing',target['mean_rate_hz'] is None)
                        reconstructed[spec['ordinal']][arm]['groups'][name]=dict(counts=total,rate=mean,cells=n)
                    mbcount=[sum(v) for v in m['counts']]
                    summary[spec['ordinal']]['arms'][arm]=dict(MBON_spikes=mbcount,MBON_mean_rate_hz=[c/(durations[w]*10) for w,c in enumerate(mbcount)],
                        population_spikes=reconstructed[spec['ordinal']][arm]['groups']['population']['counts'],
                        population_mean_rate_hz=reconstructed[spec['ordinal']][arm]['groups']['population']['rate'],
                        ISI_at_22=[sum(v) for v in m['isi_at_22']],ISI_intervals=[sum(v) for v in m['isi_intervals']])
                a=reconstructed[spec['ordinal']];delta_counts=a['intervention']['target_counts']-a['control']['target_counts']
                delta_rates=delta_counts/np.array(durations)[:,None]
                close('trial_intervention_minus_control_rates',delta_rates,trial['intervention_minus_control_rates_hz'])
                summary[spec['ordinal']]['intervention_minus_control_MBON_spikes']=delta_counts.sum(axis=1).tolist()
                summary[spec['ordinal']]['intervention_minus_control_MBON_mean_rate_hz']=(delta_rates.sum(axis=1)/10).tolist()
        paired=[]
        for pair in data['paired']:
            seed=pair['seed'];context=('paired',seed)
            indexes={t['spec']['condition']:t['spec']['ordinal'] for t in data['trials'] if t['spec']['seed']==seed}
            ea=reconstructed[indexes['ethyl_acetate']];constant=reconstructed[indexes['constant_baseline']];cur={};entry=dict(seed=seed,EA_minus_constant={})
            for arm in ['control','intervention']:
                dc=ea[arm]['target_counts']-constant[arm]['target_counts'];rate=dc/np.array(durations)[:,None];cur[arm]=rate
                close('paired_target_rates',rate,pair['EA_minus_constant_rates_hz'][arm])
                entry['EA_minus_constant'][arm]=dict(MBON_spikes=dc.sum(axis=1).tolist(),MBON_mean_rate_hz=(rate.sum(axis=1)/10).tolist())
            close('paired_target_difference_of_contrasts',cur['intervention']-cur['control'],pair['contrast_change_hz'])
            entry['contrast_change_MBON_mean_rate_hz']=((cur['intervention']-cur['control']).sum(axis=1)/10).tolist()
            for name,values in pair['cohort_contrasts'].items():
                for arm in ['control','intervention']:
                    x=ea[arm]['groups'][name];y=constant[arm]['groups'][name]
                    if x['cells']:
                        rate=[(u-v)/(durations[w]*x['cells']) for w,(u,v) in enumerate(zip(x['counts'],y['counts']))]
                        close('paired_cohort_or_population_rates',rate,values[arm])
                    else:check('empty_paired_cohort_missing',values[arm] is None)
            paired.append(entry)
        check('paired_seed_coverage',[p['seed'] for p in data['paired']]==[11,12,13])
        for r in verified.values():check('inputs_unchanged_at_end',record(ROOT/r['path'])==r)
        out.update(passed=True,window_edges_ticks=EDGES,trial_summaries=list(summary.values()),paired_summaries=paired,
                   all_six_required_reference_and_integrity_reviews_passed=True)
    except (Exception,KeyboardInterrupt) as e:out['failure']=dict(type=type(e).__name__,message=str(e),context=context,traceback=traceback.format_exc())
    out.update(completed_utc=datetime.now(timezone.utc).isoformat(),input_artifacts=list(verified.values()),check_categories=dict(check_counts),checks=sum(check_counts.values()),
        checkpoint_archive_checks=None if reader is None else dict(reader.counts),checkpoint_files_checked=0 if reader is None else len(reader.checked))
    write(DEST,out);print(json.dumps(dict(passed=out['passed'],checks=out['checks'],receipt=record(DEST),failure=out.get('failure'))))
    return 0 if out['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-result-sha',required=True);args=p.parse_args();raise SystemExit(main(args.expected_result_sha))
