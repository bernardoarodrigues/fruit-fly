#!/usr/bin/env python3
"""One frozen six-trial gamma-KC contact-weight intervention, branched at 500 ms.

No default/runtime model changes. Prefixes and controls are the prior completed
panel; each new branch uses its exact state, pending queue and external stream.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback

import numpy as np
from inhibitory_recurrent_panel_archive import load_archive,save_archive,atomic_json
from kc_gamma_intervention_kernel import GammaContactNetwork,source_derivation
from inhibitory_recurrent_panel_kernel import configure_threads

ROOT=Path(__file__).resolve().parents[1]
GRAPH=ROOT/'data/processed/malecns_v1'
PLAN=ROOT/'validation/kc-gamma-intervention-plan.json'
MASK=ROOT/'validation/kc-gamma-contact-mask-arrays.npz'
PANEL=ROOT/'validation/inhibitory-recurrent-panel-plan.json'
WINDOWS=np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)


def utc():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(Path(p).read_text())
def record(p):
    p=Path(p);h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.hexdigest())
def exact(a,b):return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()
def pins(plan):
    for r in plan['inputs']:
        if record(ROOT/r['path'])!=r:raise RuntimeError('Changed frozen input: '+r['path'])


def prepare():
    if PLAN.exists():raise FileExistsError('Preserve first experiment plan')
    panel=load(PANEL);old=ROOT/panel['run_dir'];selection=load_archive(old/'selection')
    gates=[ROOT/'validation/kc-gamma-contact-mask-results.json',ROOT/'validation/kc-gamma-intervention-kernel-checks.json',ROOT/'validation/kc-gamma-checkpoint-parity-results.json']
    for path in gates:
        gate=load(path)
        if not gate['passed']:raise RuntimeError('Failed prerequisite: '+str(path))
        for r in gate.get('inputs',gate.get('source_end',[])):
            if record(ROOT/r['path'])!=r:raise RuntimeError('Stale prerequisite input: '+r['path'])
        if 'plan' in gate:
            if record(ROOT/gate['plan']['path'])!=gate['plan']:raise RuntimeError('Stale gate plan')
            for r in load(ROOT/gate['plan']['path'])['inputs']:
                if record(ROOT/r['path'])!=r:raise RuntimeError('Stale gate plan input: '+r['path'])
    mask_result=load(gates[0]);assert record(MASK)==mask_result['arrays']
    with np.load(MASK,allow_pickle=False) as z:representatives=z['representative_indices']
    prior_intervention=load(ROOT/'validation/navigation-mbon-intervention-plan.json')
    observations=np.unique(np.r_[representatives,[502,904],prior_intervention['mbon_indices']]).astype(np.int32)
    expanded=np.unique(np.r_[selection['selected'],observations]).astype(np.int32)
    specs=[panel['order'][i] for i in [26,29,32,35,38,41]]
    paths=[Path(__file__),ROOT/'scripts/kc_gamma_intervention_kernel.py',ROOT/'scripts/navigation_mbon_intervention_kernel.py',ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'scripts/inhibitory_recurrent_panel_archive.py',ROOT/'fruitfly/neural.py',MASK,PANEL,ROOT/'validation/navigation-mbon-intervention-plan.json',ROOT/'validation/kc-gamma-contact-mask-plan.json',ROOT/'validation/kc-gamma-checkpoint-parity-plan.json',ROOT/'docs/kc-gamma-intervention-plan.md',GRAPH/'manifest.json',old/'artifact-manifest.json',old/'terminal.json']+gates
    paths += [GRAPH/(n+'.npy') for n in ['neuron_ids','indptr','targets','weights']]
    for stem in [old/'selection']+[old/f'input-seed{s}' for s in [11,12,13]]:
        paths += [Path(str(stem)+suffix) for suffix in ['.json','.npz','.complete.json']]
    for spec in specs:
        d=old/spec['name'];paths += [d/'terminal.json',d/'result.json']
        for stem in [d/'checkpoint-05000',d/'chunk-0099']:
            paths += [Path(str(stem)+suffix) for suffix in ['.json','.npz','.complete.json']]
    terminal=load(old/'terminal.json')
    if record(ROOT/terminal['artifact_manifest']['path'])!=terminal['artifact_manifest']:raise RuntimeError('Prior archive manifest changed')
    original_records={r['path']:r for r in load(old/'artifact-manifest.json')['artifacts']}
    for p in paths:
        rel=str(p.relative_to(ROOT))
        if rel in original_records and record(p)!=original_records[rel]:raise RuntimeError('Historical artifact changed: '+rel)
    plan=dict(schema=1,created_utc=utc(),inputs=[record(p) for p in dict.fromkeys(paths)],
        prior_run_dir=panel['run_dir'],run_dir='runs/'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-kc-gamma-intervention',
        trials=specs,graph_sha256=panel['graph_sha256'],neurons=panel['neurons'],threads=4,chunk_ticks=50,start_tick=5000,end_tick=30000,
        window_edges_ticks=WINDOWS.tolist(),checkpoint_ticks=[5000,10000,15000,20000,25000,30000],
        selected_indices=expanded.tolist(),event_indices=observations.tolist(),mask=record(MASK),delivery_window_ticks=[5000,15000],
        condition_rates_hz={k:panel['condition_rates_hz'][k] for k in ['constant_baseline','ethyl_acetate']},
        reference_targets=np.unique(np.r_[selection['targets'],observations]).astype(int).tolist(),reference_tolerances_mv=panel['tolerances_mv'],source_derivation=source_derivation(),
        reference_review='After all six complete, evaluate all saved global reference intervals plus each declared reference target first available interval per chunk using adaptive quadrature, independent ODE and order64 under original panel tolerances. Check threshold margins. Independent spike, state and contact-delivery reconstruction is also required.',
        prefix='Reuse exact checkpoint at5000 and its archived prefix and pending source queue. All six inactive 50-tick probes match historical original outputs. No claim of a resimulated full prefix.',
        observation='Original48 plus13 exact-type/side first-ID gamma representatives, two APLs and ten MBON12-14 cells (deduplicated). Representatives selected by anatomy only, never outcome. Full population spikes and six checkpoints retained.',
        intervention='Apply archived float64 retained weights only on270710 positive KC-to-gamma-KC pairs at deliveries in[5000,15000), removing the allocated fast term for414095 literal gL contacts. Preserve46992 other contacts on the affected pairs, original graph and all other deliveries. Existing p/h and queues persist. Restore original delivery after15000.',
        measures=['All gamma and other KC subtype mean rates, fraction active, ISIs and22tick occupancy by window','Matched EA-minus-constant pulse contrasts across all3 seeds and saved controls','Representative gamma, APL, MBON and original navigation-cell continuous v/p/h; full population post-input persistence','Actual source arrival reconstruction and per-tick zero/partial modification counts and removed p-weight sums','Recovery/restoration after15000 compared to independently diverged control history'],
        analysis='Wait for complete fixed six-trial batch, then analyze together. No per-trial outcome-based changes, gain sweeps, extra runs or model promotion. These are reused historical seeds/conditions, not held-out animals.',
        budgets=dict(trial_wall_seconds=3600,global_wall_seconds=21600,trial_output_bytes=4*1024**3,worker_peak_rss_bytes=8*1024**3,min_free_bytes=10*1024**3),
        failure='Stop and retain partial output and traceback; never restart/resume automatically. Parent enforces bounded waits; forced stops guarantee only durable archives.',
        terminal_passed_semantics='All six completed and online invariants passed; not independent numerical or physiological acceptance.',
        limits=['An intervention on a model assumption, not a biological synaptic ablation or identified mAChR-B mechanism.','Other loops, APL nonspiking physiology and local-to-soma transfer remain unresolved.','No body integration, decoder or runtime changes; H1 unpromoted.'])
    atomic_json(PLAN,plan);print(json.dumps(record(PLAN)))


def worker(ordinal,expected_plan_sha):
    entered=time.monotonic();plan_record=record(PLAN)
    if plan_record['sha256']!=expected_plan_sha:raise RuntimeError('Worker expected a different frozen plan')
    plan=load(PLAN);pins(plan)
    if record(PLAN)!=plan_record:raise RuntimeError('Plan changed at worker entry')
    spec=next(s for s in plan['trials'] if s['ordinal']==ordinal)
    run=ROOT/plan['run_dir'];directory=run/spec['name'];directory.mkdir(exist_ok=False);old=ROOT/plan['prior_run_dir']
    report=dict(spec=spec,started_utc=utc(),pid=os.getpid(),passed=False,complete=False,completed_tick=5000,last_durable_chunk_end_tick=5000,checks=0,artifacts=[],errors=[],modified_deliveries=0,spikes_after_branch=0)
    net=None;out=None;counts=None;archive_bytes=0;executing=False;out_durable=True;confirmed_before_call=5000
    def ck(name,condition):
        report['checks']+=1
        if not condition:raise AssertionError(name)
    def save(stem,data):
        nonlocal archive_bytes
        rec=save_archive(directory/stem,data);report['artifacts'].extend(rec);archive_bytes+=sum(r['bytes'] for r in rec)
    def budget():
        limits=plan['budgets'];rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        log=run/(spec['name']+'.log')
        actual_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())+(log.stat().st_size if log.exists() else 0)
        usage=dict(trial_wall_seconds=time.monotonic()-entered,worker_peak_rss_bytes=rss,trial_output_bytes=actual_bytes,free_bytes=shutil.disk_usage(run).free)
        report['resources']=usage
        if any(usage[k]>limits[k] for k in ['trial_wall_seconds','worker_peak_rss_bytes','trial_output_bytes']) or usage['free_bytes']<limits['min_free_bytes']:raise RuntimeError('Declared resource budget exceeded')
    def snapshot(tick):
        cp=net.checkpoint();cp.update(window_counts_observed=counts.copy(),logical_rng_state=int(states[tick]),intervention_specification=net.intervention_specification())
        ck('own last-spike history',exact(cp['last'],prior_last))
        slots=(tail_t+18)%19;pc=np.bincount(slots,minlength=19).astype(np.int64);pending=np.concatenate([tail_i[slots==j] for j in range(19)])
        ck('own pending history',exact(pc,cp['pending_count']) and exact(pending,cp['pending']))
        save(f'checkpoint-{tick:05d}',cp)
    try:
        budget();configure_threads(plan['threads']);graph=tuple(np.load(GRAPH/(n+'.npy')) for n in ['neuron_ids','indptr','targets','weights'])
        cp=load_archive(old/spec['name']/'checkpoint-05000');stream=load_archive(old/f'input-seed{spec["seed"]}');u=stream['uniforms'];states=stream['logical_rng_boundaries']
        with np.load(MASK,allow_pickle=False) as z:
            modified_edges=z['edge_indices'];retained_weights=z['retained_weight'];affected_sources=z['source_indices'];removed_weights=z['baseline_weight']-retained_weights
        net=GammaContactNetwork.from_checkpoint(*graph,cp,modified_edge_indices=modified_edges,retained_weights=retained_weights,delivery_window=plan['delivery_window_ticks'])
        initial=net.checkpoint();ck('original checkpoint exact',all(exact(initial[k],v) if isinstance(v,np.ndarray) else initial[k]==v for k,v in cp.items() if k in initial))
        ck('graph',net.graph_sha256==plan['graph_sha256']);ck('source masks',not net.blocked.any())
        net.replace_selected_indices(plan['selected_indices']);counts=cp['window_counts_observed'].copy();prior_last=cp['last'].copy()
        tail=load_archive(old/spec['name']/'chunk-0099');keep=tail['spike_ticks']>=4982;tail_i=tail['spike_indices'][keep].copy();tail_t=tail['spike_ticks'][keep].copy()
        snapshot(5000);previous={k:getattr(net,k)[net.selected_indices].copy() for k in ['v','s','h']}
        source_col=np.full(net.n_neurons,-1,np.int32);source_col[net.input_indices]=np.arange(len(net.input_indices))
        modified_mask=np.zeros(net.n_edges,np.bool_);modified_mask[modified_edges]=True
        source_counts=np.zeros((net.n_neurons,2),np.int64);np.add.at(source_counts,(affected_sources,(retained_weights!=0).astype(int)),1)
        source_removed=np.zeros(net.n_neurons);np.add.at(source_removed,affected_sources,removed_weights)
        for start in range(5000,30000,50):
            budget();end=start+50;phase=int(np.searchsorted([5000,10000,15000],start,side='right'))
            probability=np.full(len(net.input_indices),plan['condition_rates_hz'][spec['condition']][phase])*.1/1000.
            out=None;out_durable=False;confirmed_before_call=net.tick;executing=True
            out=net.advance(u[start:end],probability,log_selected_events=True,event_indices=plan['event_indices'])
            executing=False
            side=net.last_contact_intervention;out['contact_intervention']=side
            if out['status']!='complete':
                save(f'failed-chunk-{start//50:04d}',out);out_durable=True
                raise RuntimeError('Kernel transition did not complete')
            ck('clock',net.tick==end and out['end_tick']==end and out['completed_ticks']==50)
            ck('candidate stream',exact(out['candidate'],u[start:end]<probability))
            ii=out['spike_indices'];tt=out['spike_ticks'];source=source_col[ii]>=0;applied=out['candidate'].copy();applied[tt[source]-start,source_col[ii[source]]]=False
            ck('applied input',exact(applied,out['applied']))
            stats=out['per_tick'];edge=stats['edge_counts'];ck('edge accounting',np.array_equal(edge[:,0],edge[:,1]+edge[:,2]))
            ck('finite and reversal bound',not stats['state_invalid_count'].any() and not stats['phase_nonfinite_count'].any() and not stats['phase_below_reversal_count'].any())
            ck('trace continuity',all(exact(out['selected_'+k][0],previous[k]) for k in previous))
            # Independent arrival-count route, including emissions before branch/chunk.
            arrival_t=np.r_[tail_t,tt]+18;arrival_i=np.r_[tail_i,ii]
            eligible=(arrival_t>=start)&(arrival_t<end)&(arrival_t>=5000)&(arrival_t<15000)
            expected_count=np.zeros((50,2),np.int64);expected_removed=np.zeros(50)
            np.add.at(expected_count,arrival_t[eligible]-start,source_counts[arrival_i[eligible]])
            np.add.at(expected_removed,arrival_t[eligible]-start,source_removed[arrival_i[eligible]])
            ck('modified arrival count',exact(expected_count,side['counts']))
            ck('removed weight aggregate',np.allclose(expected_removed,side['removed_weight_sum'],rtol=1e-11,atol=1e-9))
            events=out['selected_events'];changed=events[events[:,4]==3]
            ck('changed selected event identity',not len(changed) or (modified_mask[changed[:,2]].all() and np.all((changed[:,0]>=5000)&(changed[:,0]<15000))))
            if len(ii):
                order=np.argsort(ii,kind='stable');si=ii[order];st=tt[order];same=si[1:]==si[:-1];first=np.r_[True,~same]
                ck('refractory',np.all(st[1:][same]-st[:-1][same]>=net.refractory[si[1:][same]]) and np.all(st[first]-prior_last[si[first]]>=net.refractory[si[first]]))
            np.add.at(counts,(np.searchsorted(WINDOWS,tt,side='right')-1,ii),1);np.maximum.at(prior_last,ii,tt)
            tail_i=np.r_[tail_i,ii];tail_t=np.r_[tail_t,tt];keep=tail_t>=end-18;tail_i=tail_i[keep];tail_t=tail_t[keep]
            previous={k:out['selected_'+k][-1].copy() for k in previous};report['completed_tick']=end
            report['modified_deliveries']+=int(side['counts'].sum());report['spikes_after_branch']+=len(ii)
            save(f'chunk-{start//50:04d}',out);out_durable=True;report['last_durable_chunk_end_tick']=end
            if end in plan['checkpoint_ticks']:snapshot(end)
            atomic_json(directory/'progress.json',{k:report[k] for k in ['spec','pid','completed_tick','last_durable_chunk_end_tick','resources']},overwrite=True)
        budget();pins(plan);ck('plan unchanged',record(PLAN)==plan_record);report['passed']=True;report['complete']=True
    except (Exception,KeyboardInterrupt) as exc:
        report['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
        if out is not None and not out_durable:
            try:save('failure-returned-output',out)
            except Exception as nested:report['errors'].append(dict(type=type(nested).__name__,message=str(nested)))
        if net is not None:
            try:
                failure=net.checkpoint()
                if executing:
                    failure['coherent_state']=False
                    failure['failure']=dict(kind='exception_during_advance',last_confirmed_prefix_tick=confirmed_before_call,partial_phase='unknown')
                failure['last_durable_chunk_end_tick']=report['last_durable_chunk_end_tick']
                save('failure-state',failure)
            except Exception as nested:report['errors'].append(dict(type=type(nested).__name__,message=str(nested)))
    report.update(completed_utc=utc(),wall_seconds=time.monotonic()-entered,independent_reference_review='pending',plan=plan_record,
                  resource_sampling='Per chunk and after final checkpoint, before final input rehash/result/terminal publication; output usage includes actual files, temporary evidence and worker log at each sample.')
    atomic_json(directory/'result.json',report)
    atomic_json(directory/'terminal.json',dict(complete=report['complete'],passed=report['passed'],status='complete' if report['passed'] else 'failed',result=record(directory/'result.json')))
    return 0 if report['passed'] else 1


def stop_child(child):
    outcome=dict(pid=child.pid,signal='SIGINT',forced=False)
    if child.poll() is None:
        child.send_signal(signal.SIGINT)
        try:child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            outcome['forced']=True;child.kill();child.wait(timeout=10)
    outcome['returncode']=child.returncode
    outcome['retention']='On forced stop only already durable archives are guaranteed'
    return outcome


def run():
    plan_record=record(PLAN);plan=load(PLAN);pins(plan)
    if record(PLAN)!=plan_record:raise RuntimeError('Plan changed at parent entry')
    run_dir=ROOT/plan['run_dir'];run_dir.mkdir(exist_ok=False)
    started=time.monotonic();atomic_json(run_dir/'started.json',dict(started_utc=utc(),pid=os.getpid(),plan=plan_record,argv=sys.argv))
    result=dict(passed=False,complete=False,started_utc=utc(),plan=plan_record,trials=[],errors=[]);child=None
    try:
        for spec in plan['trials']:
            pins(plan)
            if record(PLAN)!=plan_record:raise RuntimeError('Plan changed before worker dispatch')
            if time.monotonic()-started>plan['budgets']['global_wall_seconds']:raise RuntimeError('Global wall-time budget exceeded')
            command=[sys.executable,str(Path(__file__)), 'worker','--ordinal',str(spec['ordinal']),'--expected-plan-sha',plan_record['sha256']]
            with (run_dir/(spec['name']+'.log')).open('x') as log:
                child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                atomic_json(run_dir/'active-worker.json',dict(parent_pid=os.getpid(),pid=child.pid,spec=spec,started_utc=utc(),command=command),overwrite=True)
                remaining_global=plan['budgets']['global_wall_seconds']-(time.monotonic()-started)
                code=child.wait(timeout=max(.001,min(plan['budgets']['trial_wall_seconds'],remaining_global)));child=None
            terminal=load(run_dir/spec['name']/'terminal.json')
            if code!=0 or not terminal['passed'] or not terminal['complete']:raise RuntimeError('Worker failed: '+spec['name'])
            if record(run_dir/spec['name']/'result.json')!=terminal['result']:raise RuntimeError('Worker publication changed')
            result['trials'].append(dict(spec=spec,terminal=record(run_dir/spec['name']/'terminal.json'),result=terminal['result']))
            atomic_json(run_dir/'progress.json',dict(completed_trials=len(result['trials']),expected_trials=6),overwrite=True)
        pins(plan)
        if record(PLAN)!=plan_record:raise RuntimeError('Plan changed before final publication')
        result['passed']=True;result['complete']=True
    except (Exception,KeyboardInterrupt) as exc:
        result['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
        if child is not None:result['stopped_worker']=stop_child(child)
    result.update(completed_utc=utc(),wall_seconds=time.monotonic()-started,independent_reference_review='pending');atomic_json(run_dir/'results.json',result)
    atomic_json(run_dir/'terminal.json',dict(complete=result['complete'],passed=result['passed'],status='complete' if result['passed'] else 'failed',results=record(run_dir/'results.json'),plan=plan_record))
    print(json.dumps(dict(passed=result['passed'],complete=result['complete'],run_dir=plan['run_dir'],errors=result['errors'])))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','worker']);parser.add_argument('--ordinal',type=int);parser.add_argument('--expected-plan-sha');args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='run':raise SystemExit(run())
    elif args.ordinal is None or args.expected_plan_sha is None:parser.error('worker requires --ordinal and --expected-plan-sha')
    else:raise SystemExit(worker(args.ordinal,args.expected_plan_sha))
