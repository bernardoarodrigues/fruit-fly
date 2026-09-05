#!/usr/bin/env python3
"""Bounded review of saved aggregate, without importing/running its reducer or model."""
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import traceback
import math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
AGG='validation/inhibitory-recurrent-panel-combined-analysis.json'
AGG_SHA='bb42919231572491e2adbd4adfa67f53c1ce0b87bdd5a8f229628b0797488d29'
SOURCE='scripts/summarize_inhibitory_recurrent_panel.py'
SOURCE_SHA='f9d4f63b8a3aca75e5e2c5b832af4fcc50fd3a9b41ce36729ba43075a1548a35'
BASE=ROOT/'validation/inhibitory-recurrent-panel-combined-independent-review'
ORDINALS=[2,33,34,35]
TOL=1e-10

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),''):
            if not b:break
            h.update(b)
    return h.hexdigest()
def record(path):
    path=Path(path);return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=sha(path))
def load(path):return json.loads(Path(path).read_text())
def publish(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def items(node):return dict(node['items'])

def main():
    dest=BASE.with_suffix('.json');planpath=BASE.with_name(BASE.name+'-plan.json')
    if dest.exists() or planpath.exists():raise FileExistsError('Preserve first review attempt')
    source_pins={AGG:AGG_SHA,SOURCE:SOURCE_SHA,str(Path(__file__).resolve().relative_to(ROOT)):sha(__file__)}
    for name,h in source_pins.items():
        if sha(ROOT/name)!=h:raise ValueError('Unexpected review source: '+name)
    publish(planpath,dict(frozen_utc=datetime.now(timezone.utc).isoformat(),source_sha256=source_pins,
        checkpoint_ordinals=ORDINALS,scope='Rehash 306 aggregate inputs and linked trial/audit receipts; independently check four seed11 ethyl-acetate final count distributions and all five factorial contrasts for their 12 cohorts/seven windows. No reducer or model execution.',
        quantile_method='Sort integer counts; exact Fraction rank (n-1)*q and linear interpolation, divide by exact window duration. No numpy.quantile or numpy.median.',
        numeric_tolerance_hz=TOL,failure_policy='Retain first result including failures; no retry or frozen source modification.'))
    categories={};failures=[];error=None;maxima={};examples=[];summary={}
    def ck(name,ok,context=None):
        c=categories.setdefault(name,dict(checked=0,passed=0));c['checked']+=1;c['passed']+=int(bool(ok))
        if not ok:failures.append(dict(check=name,context=context))
    def compare(name,a,b,context=None):
        err=abs(float(a)-float(b));maxima[name]=max(maxima.get(name,0.),err);ck(name,math.isfinite(err) and err<=TOL,context)
    def typed(node,z):
        d=node['array'];a=z[d['key']]
        ck('typed_count_or_cohort_array',not a.dtype.hasobject and list(a.shape)==d['shape'] and a.dtype.str==d['dtype'] and a.nbytes==d['bytes'] and a.itemsize==d['itemsize'] and a.size==d['count'] and hashlib.sha256(a.tobytes()).hexdigest()==d['sha256'])
        return a
    try:
        r=load(ROOT/AGG);p=load(ROOT/'validation/inhibitory-recurrent-panel-plan.json');run=ROOT/p['run_dir'];parent=load(run/'results.json');terminal=load(run/'terminal.json')
        ck('aggregate_complete',r['passed'] and 'error' not in r and r['check_count']==554896 and len(r['trials'])==60 and r['independently_reviewed_trials']==60)
        for name,rec in r['input_receipts'].items():ck('aggregate_input_hash',record(ROOT/name)==rec,name)
        ck('reducer_source_pin',r['input_receipts'][SOURCE]['sha256']==SOURCE_SHA)
        source=(ROOT/SOURCE).read_text()
        ck('reviewed_integrity_fixes_present','record(run_dir / "selection.json") == plan["sources"]' in source and 'record(path) == artifact_map[str(path.relative_to(ROOT))]' in source and 'counts.shape == (7, plan["neurons"]) and counts.dtype.str == "<i8"' in source)
        ck('parent_terminal_link',terminal['complete'] and terminal['status']=='complete' and record(run/'results.json')==terminal['results'])
        ck('terminal_resources_copied',r['terminal_resources']==terminal['resources'] and r['started_utc']==parent['started_utc'] and r['finished_utc']==terminal['finished_utc'])
        review_checks=0;digest=hashlib.sha256();chunkfiles=0
        reports={}
        for spec,aggregate,pr in zip(p['order'],r['trials'],parent['trials']):
            d=run/spec['name'];report=load(d/'result.json');tt=load(d/'terminal.json');review=load(ROOT/aggregate['review']['path']);reports[spec['ordinal']]=report
            ck('ordered_trial_identity',aggregate['spec']==spec and all(pr[k]==v for k,v in spec.items()),spec['ordinal'])
            ck('trial_terminal_links',record(d/'result.json')==pr['result']==tt['result'] and record(d/'terminal.json')==pr['terminal'],spec['ordinal'])
            ck('audit_receipt_link',record(ROOT/aggregate['review']['path'])==aggregate['review'] and review['passed'] and not review['failures'] and review['error'] is None and review['trial']==spec and review['result_sha256']==pr['result']['sha256'] and review['terminal_sha256']==pr['terminal']['sha256'],spec['ordinal'])
            ck('audit_checks',aggregate['review_checks']==review['check_count']==sum(c['checked'] for c in review['categories'].values()) and all(c['checked']==c['passed'] for c in review['categories'].values()),spec['ordinal'])
            ck('trial_resources_and_timing',aggregate['resources']==tt['resources'] and aggregate['timing']==report['timing'] and aggregate['wall_seconds']==report['wall_seconds'],spec['ordinal'])
            review_checks+=review['check_count'];art={x['path']:x for x in report['artifacts']}
            for chunk in range(600):
                for ext in ['.json','.npz']:
                    name=str((d/f'chunk-{chunk:04d}{ext}').relative_to(ROOT));h=art[name]['sha256'];digest.update((name+'\0'+h+'\n').encode());chunkfiles+=1
        ck('component_totals',review_checks==r['component_checks'])
        ck('chunk_record_digest',chunkfiles==r['saved_chunk_files_reduced']==72000 and digest.hexdigest()==r['saved_chunk_path_hash_digest'])
        selection=load(run/'selection.json')
        ck('selection_metadata_frozen',record(run/'selection.json')==p['sources'][str((run/'selection.json').relative_to(ROOT))])
        ck('selection_payload_frozen',record(run/'selection.npz')==p['sources'][str((run/'selection.npz').relative_to(ROOT))])
        with np.load(run/'selection.npz',allow_pickle=False) as z:cohorts={k:typed(node,z) for k,node in items(items(selection['tree'])['cohorts']).items()}
        edges=r['window_edges_ticks'];durations=[Fraction(edges[i+1]-edges[i],10000) for i in range(7)];rates={}
        for ordinal in ORDINALS:
            t=r['trials'][ordinal];spec=t['spec'];d=run/spec['name'];cp=load(d/'checkpoint-30000.json');art={x['path']:x for x in reports[ordinal]['artifacts']}
            for ext in ['.json','.npz']:
                path=d/('checkpoint-30000'+ext);ck('selected_checkpoint_frozen',record(path)==art[str(path.relative_to(ROOT))],ordinal)
            with np.load(d/'checkpoint-30000.npz',allow_pickle=False) as z:counts=typed(items(cp['tree'])['window_counts_observed'],z)
            ck('selected_checkpoint_dimensions',counts.shape==(7,p['neurons']) and counts.dtype.str=='<i8' and np.all(counts>=0),ordinal)
            for cohort,idx in cohorts.items():
                saved=t['cohorts'][cohort];sample=counts[:,idx];n=len(idx);rates[spec['arm'],cohort]=[]
                ck('cohort_n_identity',saved['n']==n and hashlib.sha256(idx.astype('<i8').tobytes()).hexdigest()==reports[ordinal]['summary']['cohort_index_sha256'][cohort],(ordinal,cohort))
                for w,values in enumerate(sample):
                    ordered=np.sort(values);total=sum(map(int,values));rate=Fraction(total,n)/durations[w];rates[spec['arm'],cohort].append(rate)
                    ck('checkpoint_cohort_counts',saved['counts'][w]==total and saved['active_cells'][w]==int(np.count_nonzero(values)),(ordinal,cohort,w))
                    compare('checkpoint_mean_rate',rate,saved['mean_rates_hz'][w],(ordinal,cohort,w))
                    for qi,q in enumerate([Fraction(0),Fraction(1,2),Fraction(9,10),Fraction(99,100),Fraction(1)]):
                        rank=(n-1)*q;lo=rank.numerator//rank.denominator;hi=min(lo+1,n-1);v=Fraction(int(ordered[lo]))+(rank-lo)*int(ordered[hi]-ordered[lo]);value=v/durations[w]
                        compare('checkpoint_rate_quantile',value,saved['all_cell_rate_quantiles_hz'][w][qi],(ordinal,cohort,w,qi))
                    active=ordered[ordered>0];na=len(active)
                    if na:
                        median=Fraction(int(active[(na-1)//2])+int(active[na//2]),2)/durations[w]
                        compare('checkpoint_active_median',median,saved['active_cell_median_rate_hz'][w],(ordinal,cohort,w))
                    else:ck('empty_active_median',saved['active_cell_median_rate_hz'][w] is None,(ordinal,cohort,w))
                if cohort in ['all','motor:forward']:examples.append(dict(ordinal=ordinal,arm=spec['arm'],cohort=cohort,mean_rates_hz=[float(x) for x in rates[spec['arm'],cohort]],saved_quantiles_hz=saved['all_cell_rate_quantiles_hz']))
        coefficients={'H0_minus_C0':{'H0':1,'C0':-1},'H1_minus_C1':{'H1':1,'C1':-1},'C1_minus_C0':{'C1':1,'C0':-1},'H1_minus_H0':{'H1':1,'H0':-1},'interaction':{'H1':1,'C1':-1,'H0':-1,'C0':1}}
        ck('factorial_coefficient_conventions',r['factorial_coefficients']==coefficients)
        selected=[x for x in r['factorial_effects'] if x['seed']==11 and x['condition']=='ethyl_acetate'];ck('selected_factorial_coverage',len(selected)==12 and {x['cohort'] for x in selected}==set(cohorts))
        for row in selected:
            for name,coef in coefficients.items():
                for w in range(7):
                    v=sum(k*rates[a,row['cohort']][w] for a,k in coef.items());compare('checkpoint_factorial_effect',v,row['effects_hz'][name][w],(row['cohort'],name,w))
        summary=dict(input_hashes=len(r['input_receipts']),trial_links=60,component_checks=review_checks,selected_checkpoint_ordinals=ORDINALS,selected_cohorts=len(cohorts),selected_cell_windows=4*12*7,quantile_values=4*12*7*5,factorial_values=12*5*7,max_absolute_errors_hz=maxima)
    except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    for name,h in source_pins.items():ck('review_source_unchanged',sha(ROOT/name)==h,name)
    out=dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan=record(planpath),source_sha256=source_pins,passed=not failures and error is None,check_count=sum(c['checked'] for c in categories.values()),categories=categories,failures=failures,error=error,summary=summary,selected_examples=examples,
        limits=['No reducer/model execution and no new spike recount. Existing passed raw-data audits supply the raw-spike provenance.',
            'All aggregate input hashes and 60 audit/result/terminal links are checked; 72,000 chunk-record digest entries are reconstructed from frozen artifact records, not rehashed raw chunk payloads in this review.',
            'Fresh count-array distributions and exact-rational factorial arithmetic are checked only for four seed11 ethyl-acetate checkpoints, all 12 cohorts and seven windows.',
            'Producer extrema remain telemetry reductions, not independently reconstructed global trajectories. Terminal resources are copied recorded snapshots, not a new final filesystem/RSS census.',
            'This reviewer authored the scalar reference helper and ran the separate H1 audit batch; the present work is independent of the aggregate reducer implementation, not independent of all prior project work.',
            'Three technical seeds, a three-second duration and fixed neural motor readouts do not validate measured physiology or body behavior, and do not promote H1.'])
    publish(dest,out);print(json.dumps(dict(passed=out['passed'],checks=out['check_count'],summary=summary,error=error,failures=failures),indent=2));return 0 if out['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
