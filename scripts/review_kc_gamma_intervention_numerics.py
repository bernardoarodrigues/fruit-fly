#!/usr/bin/env python3
"""Review saved event-free intervals only; never import or advance a network."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import traceback
import warnings

import numpy as np
from scipy.integrate import IntegrationWarning

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/'validation/kc-gamma-intervention-numerics'
EXPERIMENT = ROOT/'validation/kc-gamma-intervention-plan.json'
EXPECTED_PLAN = '1136fe06fc96ad63ea676be69b7caefd7f8ce419f102488bf809d1b85f1e347b'
EXPECTED_RESULTS = '03fa6035d5dcf171178da590fa296ebd224b2423525c58f159219f0e4b97d8e9'
EXPECTED_SOLVER = 'ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711'


def output(suffix): return Path(str(PREFIX)+suffix)
def load(path): return json.loads(Path(path).read_text())


def record(path):
    path=Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=h.hexdigest())


def safe(value):
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not math.isfinite(value):
        return dict(value=None,nonfinite='nan' if math.isnan(value) else 'positive_infinity' if value>0 else 'negative_infinity')
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,dict):return {k:safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value


def write(path,value):
    with path.open('x') as f:json.dump(safe(value),f,indent=2,allow_nan=False);f.write('\n')


def versions():return {k:importlib.metadata.version(k) for k in ['numpy','scipy','numba']}


def select_intervals(out,selected,targets):
    """Independent selection equivalent to the frozen experiment requirement."""
    records={};ref=out['reference_intervals'];counts=Counter();absent=[]
    def add(tick,index,values,label,global_values=None):
        key=(int(tick),int(index));values=tuple(float(v) for v in values)
        if key in records:
            assert tuple(v.hex() for v in values)==tuple(records[key][k].hex() for k in ['v','p','h','dt','production_v']), 'Conflicting duplicate interval'
            records[key]['selection'].append(label);counts['deduplicated']+=1
        else:
            records[key]=dict(tick=key[0],index=key[1],**dict(zip(['v','p','h','dt','production_v'],values)),selection=[label],global_sources=[])
        if global_values is not None:records[key]['global_sources'].append(dict(label=label,values=global_values))
    for j in range(3):
        if bool(ref['found'][j]):
            counts['global:'+str(j)]+=1
            add(ref['ticks'][j],ref['graph_indices'][j],ref['values'][j,:5],'global:'+str(j),ref['values'][j].tolist())
        else:counts['global_absent:'+str(j)]+=1
    columns={int(index):j for j,index in enumerate(selected)}
    for index in targets:
        j=columns[int(index)];positions=np.flatnonzero(out['selected_available'][:,j])
        if not len(positions):absent.append(int(index));continue
        k=int(positions[0]);counts['target_first_available']+=1
        add(out['start_tick']+k,index,[out['selected_v'][k,j],out['selected_s'][k,j],out['selected_h'][k,j],.1,out['selected_prethreshold_v'][k,j]],'target_first_available')
    return list(records.values()),dict(counts),absent


def selection_fixture():
    selected=[4,9];values=np.zeros((3,12));values[0,:5]=[-52,1,2,.1,-51]
    out=dict(start_tick=100,reference_intervals=dict(found=np.array([True,True,False]),ticks=np.array([101,101,-1]),graph_indices=np.array([4,4,-1]),values=values.copy()),
        selected_available=np.array([[False,False],[True,False],[True,False]]),selected_v=np.full((4,2),-52.),selected_s=np.ones((4,2)),selected_h=np.full((4,2),2.),selected_prethreshold_v=np.full((3,2),-51.))
    out['reference_intervals']['values'][1,:5]=values[0,:5]
    rows,counts,absent=select_intervals(out,selected,selected)
    assert len(rows)==1 and rows[0]['tick']==101 and rows[0]['selection']==['global:0','global:1','target_first_available']
    assert counts['deduplicated']==2 and absent==[9]
    out['reference_intervals']['values'][1,0]=-53.
    try:select_intervals(out,selected,selected)
    except AssertionError:pass
    else:raise AssertionError('Conflicting duplicate accepted')
    return dict(passed=True,checks=3,scope='Manufactured global/target deduplication, first available rather than first tick, absent target, and conflicting duplicate refusal. No numerical interval evaluation.')


def prepare():
    if any(output(s).exists() for s in ['-plan.json','-results.json','-rows.jsonl.gz']):raise FileExistsError('Preserve first numerical review')
    fixture=selection_fixture();exp=load(EXPERIMENT);run=ROOT/exp['run_dir'];parent=load(run/'results.json');terminal=load(run/'terminal.json')
    assert record(EXPERIMENT)['sha256']==EXPECTED_PLAN and record(run/'results.json')['sha256']==EXPECTED_RESULTS
    assert parent['passed'] and parent['complete'] and terminal['passed'] and terminal['complete']
    assert terminal['results']==record(run/'results.json') and terminal['plan']==record(EXPERIMENT) and parent['plan']==record(EXPERIMENT)
    assert [t['spec'] for t in parent['trials']]==exp['trials'] and len(parent['trials'])==6
    solver=ROOT/'scripts/inhibitory_factorial_solver.py';assert record(solver)['sha256']==EXPECTED_SOLVER
    assert exp['source_derivation']['solver_sha256']==EXPECTED_SOLVER
    paths=[Path(__file__),EXPERIMENT,run/'results.json',run/'terminal.json',solver,
        ROOT/'scripts/experiment_inhibitory_recurrent_panel.py',ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',
        ROOT/'scripts/inhibitory_recurrent_panel_archive.py',ROOT/'validation/inhibitory-factorial-solver-plan.json',ROOT/'validation/inhibitory-factorial-solver-results.json']
    pins=[record(p) for p in paths]
    for trial in parent['trials']:
        for name in ['terminal','result']:
            r=trial[name];assert record(ROOT/r['path'])==r;pins.append(r)
        t=load(ROOT/trial['terminal']['path']);r=load(ROOT/trial['result']['path'])
        assert t['passed'] and t['complete'] and t['result']==trial['result'] and r['passed'] and r['complete']
        assert r['plan']==record(EXPERIMENT) and r['completed_tick']==r['last_durable_chunk_end_tick']==30000
    plan=dict(schema=1,created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,versions=versions(),python=sys.version,
        run_dir=exp['run_dir'],trials=exp['trials'],neurons=exp['neurons'],selected_indices=exp['selected_indices'],reference_targets=exp['reference_targets'],
        start_tick=5000,end_tick=30000,chunk_ticks=50,expected_chunks=3000,threshold_mv=-45.,reversal_mv=-75.,tolerances_mv=exp['reference_tolerances_mv'],
        fixture=fixture,
        selection='Every found saved global reference (maxh,minthresholdmargin,maxlogp/h) plus each of27 reference targets first available interval in each of3000chunks. Deduplicate(tick,index) within each trial and require identical saved inputs/output for duplicates. Preserve absent targets and absent global categories explicitly.',
        scope='Only intervention branch ticks5000..29999. Reused prebranch prefix is not re-evaluated. Selected-column identity is checked against each branch-start checkpoint. No whole-network oracle or own-history event/state audit.',
        methods='Import only the pinned isolated scalar helper: adaptive attenuation quadrature with independent Brent inversion, time-domain DOP853/Radau ODE, and64-point quadrature. This evaluates saved event-free intervals, never advances a network or generates a spike train.',
        tolerances='Use the original experiment tolerances verbatim. Preserve production-vs-quad, production-vs64, ODE-vs-quad, quad-error estimate and lower-bound checks separately.',
        threshold='Retain abs(production_v+45), original observed-error ambiguity test, a conservative error bound additionally including reported quad error, and strict >-45 decision disagreement across production and all references. Ambiguities make the reference acceptance gate unresolved even if voltage tolerances pass.',
        failure='Hash/schema/selection inconsistency stops the review and preserves completed rows. Each numerical method exception is retained with its inputs and method; remaining fixed methods/rows still run, without a retry or amendment. Interrupts preserve durable rows and close the compressed stream.',
        durability='Exclusive plan/results/rows creation. Stream lossless JSONL through deterministic gzip, flush/fsync after each completed chunk. Record full input values, selection labels and reference method outcomes; JSON nonfinite values have explicit tags.',
        evidence='Trial result manifests pin each selected archive .npz/.json/completion marker. Validate loaded array descriptors and payload hashes. Other archive arrays are not decoded; independent spike/state/contact-weight audit is separate.',
        outputs=[str(output(s).relative_to(ROOT)) for s in ['-results.json','-rows.jsonl.gz']])
    write(output('-plan.json'),plan);print(json.dumps(record(output('-plan.json'))))


class Reader:
    def __init__(self,manifest):self.manifest={r['path']:r for r in manifest};self.checked={};self.counts=Counter();self.context=None
    def check(self,name,ok):
        self.counts[name]+=1
        if not ok:raise AssertionError(f'{name}: {self.context}')
    def verify(self,path):
        rec=record(path);self.check('manifest_file',self.manifest[rec['path']]==rec);self.checked[rec['path']]=rec
    def bundle(self,stem):
        paths={ext:Path(str(stem)+ext) for ext in ['.npz','.json','.complete.json']}
        for p in paths.values():self.verify(p)
        h=load(paths['.json']);m=load(paths['.complete.json'])
        self.check('complete_bundle',h['format']=='inhibitory-recurrent-panel' and h['version']==1 and m['format']=='inhibitory-recurrent-panel-completion' and m['version']==1 and m['complete'] and h['transaction']==m['transaction'])
        self.check('marker_payloads',m['artifacts']==[self.checked[str(paths[k].relative_to(ROOT))] for k in ['.npz','.json']])
        return dict(h['tree']['items']),paths['.npz']
    def decode(self,node,z):
        if node['kind']=='scalar':return node['value']
        if node['kind']=='array':
            d=node['array'];a=z[d['key']]
            self.check('array_descriptor',not a.dtype.hasobject and list(a.shape)==d['shape'] and a.nbytes==d['bytes'] and a.itemsize==d['itemsize'] and a.size==d['count'] and
                json.loads(json.dumps(np.lib.format.dtype_to_descr(a.dtype)))==d['dtype'] and hashlib.sha256(a.tobytes()).hexdigest()==d['sha256'])
            return a
        if node['kind']=='dict':return {k:self.decode(v,z) for k,v in node['items']}
        if node['kind'] in ['tuple','list']:return [self.decode(v,z) for v in node['items']]
        raise ValueError('Unsupported review node '+node['kind'])


def references(row,tol,helper):
    r=dict(row,methods={},numerical_tolerances_passed=False,threshold_ambiguity_observed=None,threshold_ambiguity_conservative=None,threshold_decision_disagreement=None)
    args=[r[k] for k in ['v','p','h','dt']]
    for method in ['adaptive_quadrature','independent_ode','order64']:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',IntegrationWarning)
                if method=='adaptive_quadrature':
                    v,error=helper.hybrid_reference(*args);value=dict(v_mv=v,error_estimate_mv=error)
                elif method=='independent_ode':
                    v,name,nfev=helper.ode_reference(*args);value=dict(v_mv=v,method=name,nfev=nfev)
                else:
                    a,b,c=helper.coefficients(r['dt']);v,p,h,tail,residual,iterations,cutoff=helper.hybrid_step(*args,a,b,c,helper.NODES64,helper.WEIGHTS64)
                    value=dict(v_mv=v,p_after=p,h_after=h,tail_bound_mv=tail,inversion_residual=residual,inversion_iterations=iterations,cutoff=cutoff)
            r['methods'][method]=value
        except (Exception,KeyboardInterrupt) as e:
            r['methods'][method]=dict(error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
            if isinstance(e,KeyboardInterrupt):r['interrupted']=True;return r
    if not any('error' in v for v in r['methods'].values()):
        q=r['methods']['adaptive_quadrature']['v_mv'];qe=r['methods']['adaptive_quadrature']['error_estimate_mv'];ode=r['methods']['independent_ode']['v_mv'];high=r['methods']['order64']['v_mv']
        errors=dict(production_vs_quad=abs(r['production_v']-q),order32_vs64=abs(r['production_v']-high),ode_vs_quad=abs(ode-q),quad_error_estimate=qe)
        finite=all(math.isfinite(x) for x in [q,qe,ode,high]);lower=all(v>=-75.-tol['hybrid_lower_bound'] for v in [r['production_v'],q,ode,high])
        r.update(errors_mv=errors,finite=finite,lower_bound_passed=lower,
            numerical_tolerances_passed=finite and lower and all(value<=tol[key] for key,value in errors.items()))
        observed=max(errors[k] for k in ['production_vs_quad','order32_vs64','ode_vs_quad'])
        margin=abs(r['production_v']+45.);decisions=[v>-45. for v in [r['production_v'],q,ode,high]]
        r.update(threshold_margin_mv=margin,observed_reference_error_mv=observed,conservative_reference_error_mv=observed+qe,
            threshold_ambiguity_observed=margin<=observed,threshold_ambiguity_conservative=margin<=observed+qe,threshold_decision_disagreement=len(set(decisions))>1,
            threshold_decisions=dict(zip(['production','quadrature','ode','order64'],decisions)))
    return r


def run():
    if output('-results.json').exists() or output('-rows.jsonl.gz').exists():raise FileExistsError('Preserve first execution')
    plan=load(output('-plan.json'));pin=record(output('-plan.json'));result=dict(schema=1,passed=False,plan=pin,trials=[],limitations=[plan['scope'],plan['methods'],plan['evidence']])
    total=Counter();maxima={};worst={};minimum_margin=None;reader=None;context='inputs';checked_digest=hashlib.sha256()
    raw=None;stream=None
    try:
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        assert versions()==plan['versions'] and record(ROOT/'scripts/inhibitory_factorial_solver.py')['sha256']==EXPECTED_SOLVER
        import inhibitory_factorial_solver as helper
        assert helper.REST==-52. and helper.REVERSAL==-75. and helper.TAU_M==20. and helper.TAU_S==5.
        raw=output('-rows.jsonl.gz').open('xb');stream=gzip.GzipFile(fileobj=raw,mode='wb',mtime=0)
        run_dir=ROOT/plan['run_dir'];selected=np.array(plan['selected_indices']);targets=plan['reference_targets'];selcol={int(index):j for j,index in enumerate(selected)}
        for spec in plan['trials']:
            context=dict(trial=spec['name'],stage='identity');directory=run_dir/spec['name'];publication=load(directory/'result.json');reader=Reader(publication['artifacts']);reader.context=context
            cp,npz=reader.bundle(directory/'checkpoint-05000')
            with np.load(npz,allow_pickle=False) as z:
                identity=reader.decode(cp['selected_indices'],z)
                reader.check('selected_column_identity',np.array_equal(identity,selected))
                reader.check('checkpoint_identity',all(reader.decode(cp[k],z)==v for k,v in [('arm','H1'),('seed',spec['seed']),('tick',5000),('coherent_state',True)]))
            stat=dict(spec=spec,completed_chunks=0,intervals=0,numerical_failures=0,method_errors=0,threshold_ambiguities_observed=0,threshold_ambiguities_conservative=0,threshold_decision_disagreements=0,selection_counts=Counter(),target_absence_counts=Counter(),max_errors_mv={})
            result['trials'].append(stat);seen=set()
            for start in range(5000,30000,50):
                context=dict(trial=spec['name'],chunk_start=start);reader.context=context;nodes,npz=reader.bundle(directory/f'chunk-{start//50:04d}')
                keys=['status','start_tick','end_tick','completed_ticks','requested_ticks','coherent_state','failure','partial','selected_v','selected_s','selected_h','selected_prethreshold_v','selected_available','selected_fired','reference_intervals','schema']
                with np.load(npz,allow_pickle=False) as z:out={k:reader.decode(nodes[k],z) for k in keys}
                reader.check('chunk_identity',out['status']=='complete' and out['start_tick']==start and out['end_tick']==start+50 and out['completed_ticks']==out['requested_ticks']==50 and out['coherent_state'] and out['failure'] is None and out['partial'] is None)
                for name,shape in [('selected_v',(51,len(selected))),('selected_s',(51,len(selected))),('selected_h',(51,len(selected))),('selected_prethreshold_v',(50,len(selected))),('selected_available',(50,len(selected))),('selected_fired',(50,len(selected)))]:
                    reader.check('selected_array_shape',out[name].shape==shape)
                ref=out['reference_intervals'];reader.check('global_reference_shapes',ref['found'].shape==ref['ticks'].shape==ref['graph_indices'].shape==(3,) and ref['values'].shape==(3,12) and ref['partial'] is None)
                reader.check('reference_schema',out['schema']['reference_columns'][:5]==['before_v_mv','before_p_mv','before_h','dt_ms','prethreshold_v_mv'] and out['schema']['reference_names']==['max_h','min_threshold_margin','max_log_p_over_h'])
                chosen,counts,absent=select_intervals(out,selected,targets);stat['selection_counts'].update(counts);stat['target_absence_counts'].update(map(str,absent))
                for r in chosen:
                    key=(r['tick'],r['index']);reader.check('unique_valid_interval',key not in seen and start<=r['tick']<start+50 and 0<=r['index']<plan['neurons'] and r['dt']==.1 and all(math.isfinite(r[k]) for k in ['v','p','h','dt','production_v']) and r['p']>=0 and r['h']>=0)
                    seen.add(key);r.update(trial=spec['name'],ordinal=spec['ordinal'],chunk_start_tick=start)
                    if r['index'] in selcol:
                        k=r['tick']-start;j=selcol[r['index']]
                        reader.check('selected_interval_identity',out['selected_available'][k,j] and all(float(out[name][k,j]).hex()==r[field].hex() for name,field in [('selected_v','v'),('selected_s','p'),('selected_h','h'),('selected_prethreshold_v','production_v')]))
                        reader.check('saved_threshold_flag',bool(out['selected_fired'][k,j])==(r['production_v']>-45.))
                    for global_source in r['global_sources']:reader.check('saved_global_margin',global_source['values'][5]==abs(r['production_v']+45.))
                    context=dict(trial=spec['name'],tick=r['tick'],index=r['index']);row=references(r,plan['tolerances_mv'],helper)
                    stream.write((json.dumps(safe(row),separators=(',',':'),allow_nan=False)+'\n').encode())
                    stat['intervals']+=1;total['intervals']+=1
                    method_errors=sum('error' in v for v in row['methods'].values());stat['method_errors']+=method_errors;total['method_errors']+=method_errors
                    for local,field in [('numerical_failures','numerical_tolerances_passed'),('threshold_ambiguities_observed','threshold_ambiguity_observed'),('threshold_ambiguities_conservative','threshold_ambiguity_conservative'),('threshold_decision_disagreements','threshold_decision_disagreement')]:
                        value=(not row[field]) if local=='numerical_failures' else bool(row[field]);stat[local]+=value;total[local]+=value
                    if row.get('threshold_margin_mv') is not None:
                        if minimum_margin is None or row['threshold_margin_mv']<minimum_margin['margin_mv']:minimum_margin=dict(trial=spec['name'],tick=r['tick'],index=r['index'],margin_mv=row['threshold_margin_mv'])
                    for name,error in row.get('errors_mv',{}).items():
                        if name not in maxima or error>maxima[name]:maxima[name]=error;worst[name]=dict(trial=spec['name'],tick=r['tick'],index=r['index'],error_mv=error)
                        stat['max_errors_mv'][name]=max(stat['max_errors_mv'].get(name,0),error)
                    if row.get('interrupted'):raise KeyboardInterrupt('Reference method interrupted; partial row retained')
                stream.flush();raw.flush();os.fsync(raw.fileno());stat['completed_chunks']+=1;total['chunks']+=1
            stat['selection_counts']=dict(stat['selection_counts']);stat['target_absence_counts']=dict(stat['target_absence_counts']);stat['archive_checks']=dict(reader.counts)
            total['archive_checks']+=sum(reader.counts.values());total['checked_files']+=len(reader.checked)
            for path in sorted(reader.checked):checked_digest.update((json.dumps(reader.checked[path],sort_keys=True,separators=(',',':'))+'\n').encode())
        for r in plan['inputs']:assert record(ROOT/r['path'])==r,r['path']
        assert record(output('-plan.json'))==pin
        result['coverage_complete']=total['chunks']==plan['expected_chunks'] and len(result['trials'])==6
        result['numerical_tolerances_passed']=total['numerical_failures']==0 and total['method_errors']==0
        result['threshold_gate_resolved']=total['threshold_ambiguities_conservative']==0 and total['threshold_decision_disagreements']==0
        result['passed']=result['coverage_complete'] and result['numerical_tolerances_passed'] and result['threshold_gate_resolved']
    except (Exception,KeyboardInterrupt) as e:
        result['failure']=dict(type=type(e).__name__,message=str(e),context=context,traceback=traceback.format_exc())
        if reader is not None:result['active_reader_checks']=dict(reader.counts)
    finally:
        if stream is not None:stream.close()
        if raw is not None:raw.flush();os.fsync(raw.fileno());raw.close()
    result.update(completed_utc=datetime.now(timezone.utc).isoformat(),totals=dict(total),max_errors_mv=maxima,worst_intervals=worst,minimum_threshold_margin=minimum_margin,
        checked_file_receipts_sha256=checked_digest.hexdigest(),rows_artifact=record(output('-rows.jsonl.gz')) if output('-rows.jsonl.gz').exists() else None)
    write(output('-results.json'),result);print(json.dumps(dict(passed=result['passed'],result=record(output('-results.json')),totals=dict(total),max_errors_mv=maxima,failure=result.get('failure'))))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:raise SystemExit(run())
