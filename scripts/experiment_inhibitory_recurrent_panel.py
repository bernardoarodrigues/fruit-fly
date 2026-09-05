#!/usr/bin/env python3
"""Frozen 60-trial inhibitory panel, isolated workers and durable raw evidence."""
from __future__ import annotations
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import shutil
import subprocess
import sys
import time
import traceback
import warnings

import numpy as np
import numba
import scipy
from scipy.integrate import IntegrationWarning

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/inhibitory-recurrent-panel-plan.json'
GRAPH=ROOT/'data/processed/malecns_v1'
from inhibitory_recurrent_panel_kernel import FactorialNetwork, configure_threads, parallel_runtime_info
from inhibitory_recurrent_panel_archive import atomic_json, save_archive, load_archive
from inhibitory_recurrent_panel_metrics import build_cohorts, accumulate_chunk, summarize_counts, paired_contrasts
from inhibitory_factorial_solver import hybrid_reference, ode_reference, hybrid_step, coefficients, NODES64, WEIGHTS64

CONDITIONS=['no_input','constant_baseline','ethyl_acetate','isoamyl_acetate','ethyl_acetate_source_outputs_blocked']
SEEDS=[11,12,13]
EDGES=np.array([0,500,5000,10000,15000,20000,25000,30000],np.int64)
CHECKPOINTS={0,500,5000,10000,15000,20000,25000,30000}
AUDIT_RANGES=[(0,500),(5000,5500),(15000,15500),(29500,30000)]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def record(path):
    p=Path(path)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p))


def environment():
    return dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
                numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__)


def utc():return datetime.now(timezone.utc).isoformat()


def exact(a,b):return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()


def streams(seed):
    state=int(np.random.SeedSequence(seed).generate_state(1,dtype=np.uint64)[0]) or 1
    mask=(1<<64)-1
    values=np.empty((30000,36));states=np.empty(30001,np.uint64);states[0]=state
    for tick in range(30000):
        for col in range(36):
            state^=state>>12;state^=(state<<25)&mask;state^=state>>27
            values[tick,col]=(((state*2685821657736338717)&mask)>>11)/float(1<<53)
        states[tick+1]=state
    return values,states


def prepare():
    if PLAN.exists():raise FileExistsError('Preserve frozen panel plan')
    prerequisites=['validation/inhibitory-recurrent-panel-kernel-checks.json','validation/inhibitory-recurrent-panel-archive-checks.json',
        'validation/inhibitory-recurrent-panel-metrics-checks.json','validation/inhibitory-recurrent-panel-preflight-review.json',
        'validation/inhibitory-recurrent-parallel-performance/results.json','validation/inhibitory-recurrent-parallel-performance-independent-review.json']
    for name in prerequisites:
        r=json.loads((ROOT/name).read_text())
        if not r.get('passed',r.get('complete',False)):raise RuntimeError('Prerequisite not passing: '+name)
        if isinstance(r.get('checks'),list) and not all(c.get('passed',False) for c in r['checks']):raise RuntimeError('Prerequisite has a failed check: '+name)
    preflight=json.loads((ROOT/'validation/inhibitory-recurrent-panel-preflight-review.json').read_text())
    required={'scripts/experiment_inhibitory_recurrent_panel.py','scripts/inhibitory_recurrent_panel_kernel.py',
        'scripts/inhibitory_recurrent_panel_archive.py','scripts/inhibitory_recurrent_panel_metrics.py','scripts/inhibitory_factorial_solver.py'}
    if not required.issubset(preflight['reviewed_sources']):raise RuntimeError('Preflight lacks required source review')
    for path,r in preflight['reviewed_sources'].items():
        if sha(ROOT/path)!=r['sha256'] or (ROOT/path).stat().st_size!=r['bytes']:raise RuntimeError('Preflight source is stale: '+path)
    for r in preflight['component_reviews']:
        if not r['passed'] or sha(ROOT/r['path'])!=r['sha256']:raise RuntimeError('Preflight component is failed/stale')
    old=json.loads((ROOT/'validation/or42a-summary-plan.json').read_text())
    prior=json.loads((ROOT/'validation/or42a-summary-experiment.json').read_text())
    run=ROOT/'runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-inhibitory-recurrent-panel')
    run.mkdir()
    stream_records=[]
    for seed in SEEDS:
        u,state=streams(seed)
        stream_records+=save_archive(run/f'input-seed{seed}',dict(seed=seed,uniforms=u,logical_rng_boundaries=state))
    ids=np.load(GRAPH/'neuron_ids.npy');cohorts=build_cohorts(ids,old)
    inputs=np.asarray(old['source_graph_indices'],np.int32)
    index={int(v):i for i,v in enumerate(ids)}
    targets=np.array([index[67052],index[13314]],np.int32)
    motor=[index[v] for group in old['motor_groups'].values() for v in group]
    selected=np.array(sorted(set(inputs.tolist()+targets.tolist()+motor)),np.int32)
    stream_records+=save_archive(run/'selection',dict(inputs=inputs,selected=selected,targets=targets,
        selected_body_ids=ids[selected],cohorts=cohorts,cohort_body_ids={k:ids[v] for k,v in cohorts.items()}))
    order=[]
    for seed in SEEDS:
        for condition in CONDITIONS:order.append(dict(arm='C0',seed=seed,condition=condition))
    for condition in CONDITIONS:
        for seed in SEEDS:
            for arm in ('C1','H0','H1'):order.append(dict(arm=arm,seed=seed,condition=condition))
    for i,t in enumerate(order):t['ordinal']=i;t['name']=f'{i:02d}-{t["arm"]}-seed{t["seed"]}-{t["condition"]}'
    source_names=['scripts/experiment_inhibitory_recurrent_panel.py','scripts/inhibitory_recurrent_panel_kernel.py',
        'scripts/inhibitory_recurrent_panel_archive.py','scripts/inhibitory_recurrent_panel_metrics.py',
        'scripts/inhibitory_factorial_solver.py','validation/inhibitory-recurrent-panel-kernel-checks.json',
        'validation/inhibitory-recurrent-panel-archive-checks.json','validation/inhibitory-recurrent-panel-metrics-checks.json',
        'validation/inhibitory-recurrent-panel-preflight-review.json',
        'validation/inhibitory-recurrent-parallel-performance/results.json',
        'validation/inhibitory-recurrent-parallel-performance-independent-review.json',
        'validation/inhibitory-recurrent-input-audit.json','validation/or42a-summary-plan.json',
        'validation/or42a-summary-experiment.json','fruitfly/neural.py']
    source_names += ['data/processed/malecns_v1/'+n+'.npy' for n in ('neuron_ids','indptr','targets','weights')]
    old_trials=[]
    for t in prior['trials']:
        old_trials.append(dict(seed=t['seed'],condition=t['condition'],run_dir=t['run_dir']))
        source_names += [t['run_dir']+'/trace.npz',t['run_dir']+'/samples.jsonl']
    sources={p:record(ROOT/p) for p in source_names}
    sources.update({r['path']:r for r in stream_records})
    plan=dict(schema=1,frozen_utc=utc(),run_dir=str(run.relative_to(ROOT)),environment=environment(),sources=sources,
        order=order,seeds=SEEDS,condition_order=CONDITIONS,condition_rates_hz={c:old['conditions'][c]+[0.] for c in CONDITIONS},
        schedule_boundaries_ticks=[0,5000,10000,15000,30000],window_edges_ticks=EDGES.tolist(),
        checkpoint_ticks=sorted(CHECKPOINTS),audit_ranges_ticks=AUDIT_RANGES,threads=4,dt_ms=.1,chunk_ticks=50,
        graph_sha256=old['graph_sha256'],neurons=len(ids),edges=old['edges'],old_trials=old_trials,
        input_semantics='All36sources always listed with refractory0, no direct current, direct68.75mV voltage events afterthreshold; same-tickspike rejects directevent inallarms; source-output block is delivery mask only.',
        c0_gate='EveryC0first1500ms mustmatch originalspikes,candidates/applied,RNG,3windowcounts,fullendpointv/s. All15durableprefixgates beforealteredarms. No intermediatefulloldcheckpoint claim.',
        tolerances_mv=dict(hybrid_lower_bound=1e-10,production_vs_quad=1e-8,order32_vs64=1e-8,ode_vs_quad=2e-8,quad_error_estimate=1e-9),
        reference_selection='Bothtargets firstavailabletick within eachchunk plus maxh/stiffness,minthresholdmargin,maxlog(p/h) overavailableintervals perchunk. Preserveexactownprecedingstates anddeduplicateby(tick,index). Allfailuresretained.',
        reference_methods='Frozen scalar adaptiveattenuationquad,independentDOP853/RadauODE,and64-pointsame-equation quadrature; evaluateonlysavedselectedintervals, nomodelrerun orfit.',
        budgets=dict(trial_wall_seconds=3600,trial_output_bytes=4*1024**3,worker_peak_rss_bytes=8*1024**3,
            global_wall_seconds=86400,global_output_bytes=64*1024**3,failure_reserve_bytes=512*1024**2,min_free_bytes=10*1024**3),
        enforcement='Onefreshworkeratatime; checksaroundeach5mschunk/checkpoint and terminalbudgetreceipts afterresults/logclose. Oneoperationcanovershoot; terminalreceiptitself/lastloglinearethefinalunmeasuredoperation. Globaltimerstartsatruninvocation(includingpreflight); priorprepare/reviewexcluded. Pertrialfromworkerfunctionentrythroughfinalartifacts; processimportstartupisin globaltime. Filesystemusageincludeslogs/temps. Closedtrialdirectorybytesarecachedperworker underexclusivewritercontract; currentdirectory/rootfilesrescanperchunk, parentfullrescanperdispatch/finalization. Reserveis additionalfailureoutputonly. No biologicalspikeceiling.',
        dispatch='All15C0 first(seed-majorconditionorder), thencondition-majorseed-majorC1/H0/H1. Resource-limitedtrialcanbefollowedbyfreshnexttrialifglobalresourcespass; correctness/interruption/retentionfailurehalts. Neverresumeorreplaceatrial.',
        retention='Bulkdurablearchivesinignoredrunsdirectory; Gittracksfrozenplan,code,reviews,compactfinalmanifestandsummaries. Typed12bytespikes; all48selectedtraces; targeteventsalltime,otherselectedeventsonlyfixedauditranges; allglobalphase/work/edgecounts; completeboundarycheckpoints.',
        voltage_histogram_edges=[-1000,-500,-250,-150,-100,-90,-80,-75,-70,-65,-60,-55,-52,-50,-45,-40,0,20,50,100,250,500,1000],
        synaptic_histogram_edges=[-1e6,-1e4,-1000,-100,-10,-1,0,1,10,100,1000,1e4,1e6],
        h_histogram_edges=[0,.1,1,3,10,30,100,300,1000,1e4,1e6],
        histogram_overflow_bins=True,
        claim_limits=['Three numerical seeds are not biological replicates.','A finite3s test cannot establishlong-term stability.','Thispaneldoesnotcalibratephysiologicalamplitude/timingorpromoteH1.'])
    atomic_json(PLAN,plan)
    atomic_json(run/'manifest.json',dict(plan=record(PLAN),created_utc=utc(),run_dir=plan['run_dir']))
    print(json.dumps(dict(plan=str(PLAN),sha256=sha(PLAN),run_dir=str(run))),flush=True)


class ResourceStop(RuntimeError):
    def __init__(self,reasons,global_stop=False):
        self.reasons=reasons;self.global_stop=global_stop
        super().__init__('; '.join(reasons))


def tree_bytes(directory):return sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file())


def check_sources(plan,expected_plan_sha=None):
    run=ROOT/plan['run_dir']
    manifest=json.loads((run/'manifest.json').read_text())
    expected=manifest['plan']['sha256']
    if expected_plan_sha is not None and expected_plan_sha!=expected:raise RuntimeError('Invocation plan hash differs from prepared manifest')
    if sha(PLAN)!=expected or json.loads(PLAN.read_text())!=plan:raise RuntimeError('Frozen plan changed')
    if (run/'started.json').exists() and json.loads((run/'started.json').read_text())['plan_sha256']!=expected:
        raise RuntimeError('Plan hash differs from active run')
    for p,r in plan['sources'].items():
        if sha(ROOT/p)!=r['sha256']:raise RuntimeError('Frozen source/input changed: '+p)
    if environment()!=plan['environment']:raise RuntimeError('Frozen environment changed')


def c0_gates(plan):
    run=ROOT/plan['run_dir'];records=[];missing=[]
    for spec in plan['order'][:15]:
        path=run/spec['name']/'c0-prefix-gate.json'
        if not path.exists():missing.append(spec['name']);continue
        gate=json.loads(path.read_text())
        if not (gate['passed'] and all(gate['checks'].values()) and gate['seed']==spec['seed'] and gate['condition']==spec['condition'] and gate['tick']==15000 and gate['plan_sha256']==sha(PLAN)):
            raise RuntimeError('Invalid or failed C0 prefix gate: '+spec['name'])
        checkpoint=ROOT/gate['checkpoint']['path']
        if checkpoint!=run/spec['name']/'checkpoint-15000.complete.json':raise RuntimeError('Unexpected C0 checkpoint path')
        if sha(checkpoint)!=gate['checkpoint']['sha256']:raise RuntimeError('C0 checkpoint completion changed')
        cp=load_archive(run/spec['name']/'checkpoint-15000')
        if not (cp['coherent_state'] and cp['tick']==15000 and cp['seed']==spec['seed'] and cp['arm']=='C0' and cp['graph_sha256']==plan['graph_sha256']):
            raise RuntimeError('C0 checkpoint identity/state mismatch')
        records.append(record(path))
    return records,missing


def reference_checks(out,selected,targets,arm,tolerances):
    if not arm.startswith('H'):return []
    records={}
    ref=out['reference_intervals']
    for k in range(3):
        if ref['found'][k]:
            v=ref['values'][k]
            key=(int(ref['ticks'][k]),int(ref['graph_indices'][k]))
            if key in records:records[key]['selection'].append('global:'+str(k))
            else:records[key]=dict(tick=key[0],index=key[1],v=float(v[0]),p=float(v[1]),h=float(v[2]),dt=float(v[3]),production_v=float(v[4]),selection=['global:'+str(k)])
    if out['completed_ticks']:
        for target in targets:
            j=int(np.flatnonzero(selected==target)[0]);available=np.flatnonzero(out['selected_available'][:,j])
            if len(available):
                k=int(available[0]);key=(out['start_tick']+k,int(target))
                if key in records:records[key]['selection'].append('target_first_available')
                else:records[key]=dict(tick=key[0],index=key[1],v=float(out['selected_v'][k,j]),p=float(out['selected_s'][k,j]),h=float(out['selected_h'][k,j]),dt=.1,
                    production_v=float(out['selected_prethreshold_v'][k,j]),selection=['target_first_available'])
    stopped=False
    for r in records.values():
        r.update(passed=False,margin_within_observed_reference_error=False)
        if stopped:r['not_attempted_after_failure']=True;continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',IntegrationWarning)
                r['method_in_progress']='adaptive_quadrature'
                q,qe=hybrid_reference(r['v'],r['p'],r['h'],r['dt']);r.update(quad_v=q,quad_error_estimate=qe)
                r['method_in_progress']='independent_ode'
                ode,method,nfev=ode_reference(r['v'],r['p'],r['h'],r['dt']);r.update(ode_v=ode,ode_method=method,ode_nfev=nfev)
                r['method_in_progress']='order64'
                a,b,c=coefficients(r['dt'])
                high=hybrid_step(r['v'],r['p'],r['h'],r['dt'],a,b,c,NODES64,WEIGHTS64);r['order64_v']=high[0]
            r.update(production_quad_error=abs(r['production_v']-q),production_order64_error=abs(r['production_v']-high[0]),ode_quad_error=abs(ode-q),method_in_progress=None)
            r['passed']=bool(all(np.isfinite([q,qe,ode,high[0]])) and r['production_quad_error']<=tolerances['production_vs_quad']
                and r['production_order64_error']<=tolerances['order32_vs64'] and r['ode_quad_error']<=tolerances['ode_vs_quad'] and qe<=tolerances['quad_error_estimate'])
            r['threshold_margin_mv']=abs(r['production_v']+45.)
            r['margin_within_observed_reference_error']=r['threshold_margin_mv']<=max(r['production_quad_error'],r['production_order64_error'],r['ode_quad_error'])
            stopped=not r['passed']
        except (Exception,KeyboardInterrupt) as error:
            r['error']=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc());stopped=True
    return list(records.values())


def trial(plan,ordinal,expected_plan_sha):
    entered=time.monotonic()
    check_sources(plan,expected_plan_sha)
    if plan['order'][ordinal]['arm']!='C0' and c0_gates(plan)[1]:raise RuntimeError('Direct worker dispatch cannot bypass all15C0prefixes')
    spec=plan['order'][ordinal];run=ROOT/plan['run_dir'];directory=run/spec['name']
    directory.mkdir(exist_ok=True)
    if (directory/'started.json').exists():raise FileExistsError('Refuse trial restart')
    global_start=json.loads((run/'started.json').read_text())['monotonic_start']
    if entered<global_start:raise RuntimeError('Monotonic clock precedes global start; possible reboot')
    atomic_json(directory/'started.json',dict(**spec,pid=os.getpid(),started_utc=utc(),monotonic_start=entered,plan_sha256=sha(PLAN)))
    report=dict(**spec,status='running',complete=False,c0_prefix_passed=False,completed_tick=0,last_durable_chunk_end_tick=0,
        last_complete_checkpoint_tick=0,confirmed_prefix_end_tick=0,checks_passed=0,errors=[],resources={},timing=dict(kernel=0.,reference=0.,archive=0.,telemetry=0.),
        spike_count=0,candidate_count=0,applied_count=0,reference_intervals=0,reference_threshold_ambiguities=0,artifacts=[])
    net=None;out=None;unpublished=False;executing=False;counts=None;counts_tick=0;count_candidate=None;counts_ready=False;confirmed=0;tail_i=np.empty(0,np.int32);tail_t=np.empty(0,np.int64)
    prior_last=None;prior_selected=None;old_data=None;spike_cursor=0;ref_rows=[];failure_before=None
    closed_directory_bytes=sum(tree_bytes(p) for p in run.iterdir() if p.is_dir() and p!=directory)
    def ck(name,value):
        if not value:raise RuntimeError('Correctness check failed: '+name)
        report['checks_passed']+=1
    def budget():
        now=time.monotonic();limits=plan['budgets']
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        current_bytes=tree_bytes(directory);root_bytes=sum(p.stat().st_size for p in run.iterdir() if p.is_file())
        usage=dict(trial_wall_seconds=now-entered,global_wall_seconds=now-global_start,trial_output_bytes=current_bytes,
            global_output_bytes=closed_directory_bytes+current_bytes+root_bytes,worker_peak_rss_bytes=rss,free_bytes=shutil.disk_usage(run).free)
        report['resources']=usage;reasons=[];global_stop=False
        for key in ('trial_wall_seconds','trial_output_bytes','worker_peak_rss_bytes','global_wall_seconds','global_output_bytes'):
            if usage[key]>limits[key]:
                reasons.append(key+' exceeded');global_stop|=key.startswith('global')
        if usage['free_bytes']<limits['min_free_bytes']:reasons.append('free-space floor');global_stop=True
        if reasons:raise ResourceStop(reasons,global_stop)
    def save(stem,data):
        t=time.perf_counter();records=save_archive(directory/stem,data);report['timing']['archive']+=time.perf_counter()-t
        report['artifacts'].extend(records)
        return records
    def checkpoint(tick,stem=None):
        cp=net.checkpoint();cp.update(logical_rng_state=int(states[tick]),window_counts_observed=counts.copy(),last_durable_chunk_end_tick=report['last_durable_chunk_end_tick'],confirmed_prefix_end_tick=confirmed)
        ck('checkpoint own-history last',exact(cp['last'],prior_last))
        slots=(tail_t+18)%19
        pc=np.bincount(slots,minlength=19).astype(np.int64)
        pending=np.concatenate([tail_i[slots==s] for s in range(19)])
        ck('checkpoint own-history queue',exact(cp['pending_count'],pc) and exact(cp['pending'],pending))
        save(stem or f'checkpoint-{tick:05d}',cp);report['last_complete_checkpoint_tick']=tick
    try:
        budget();check_sources(plan)
        configure_threads(plan['threads'])
        graph=tuple(np.load(GRAPH/(key+'.npy')) for key in ('neuron_ids','indptr','targets','weights'))
        selection=load_archive(run/'selection');inputs=selection['inputs'];selected=selection['selected'];targets=selection['targets'];cohorts=selection['cohorts']
        stream=load_archive(run/f'input-seed{spec["seed"]}');u=stream['uniforms'];states=stream['logical_rng_boundaries']
        net=FactorialNetwork(*graph,spec['arm'],inputs,selected,seed=spec['seed'])
        blocked=spec['condition'].endswith('source_outputs_blocked')
        if blocked:net.blocked[inputs]=True
        ck('graph',net.graph_sha256==plan['graph_sha256'])
        counts=np.zeros((7,len(graph[0])),np.int64);prior_last=np.full(len(graph[0]),-(2**60),np.int64)
        checkpoint(0)
        if spec['arm']=='C0':
            old=next(t for t in plan['old_trials'] if t['seed']==spec['seed'] and t['condition']==spec['condition'])
            with np.load(ROOT/old['run_dir']/'trace.npz',allow_pickle=False) as z:old_data={k:z[k] for k in z.files}
            old_samples=[json.loads(line) for line in (ROOT/old['run_dir']/'samples.jsonl').read_text().splitlines()]
            ck('old initial RNG',int(old_data['initial_rng_state'][0])==int(states[0]))
        v_edges=np.r_[-np.inf,plan['voltage_histogram_edges'],np.inf]
        s_edges=np.r_[-np.inf,plan['synaptic_histogram_edges'],np.inf]
        h_edges=np.r_[-np.inf,plan['h_histogram_edges'],np.inf]
        for chunk in range(600):
            budget();start=chunk*50;end=start+50;counts_ready=False;count_candidate=None
            rate=plan['condition_rates_hz'][spec['condition']][int(np.searchsorted([5000,10000,15000],start,side='right'))]
            probabilities=np.full(36,rate)*.1/1000.
            event_indices=selected if any(a<=start<b for a,b in AUDIT_RANGES) else targets
            t=time.perf_counter();confirmed=net.tick;executing=True
            out=net.advance(u[start:end],probabilities,log_selected_events=True,event_indices=event_indices)
            executing=False;confirmed=out['end_tick'];unpublished=True
            report['timing']['kernel']+=time.perf_counter()-t
            report['confirmed_prefix_end_tick']=confirmed;report['completed_tick']=confirmed
            t=time.perf_counter();checks={}
            done=out['completed_ticks'];ii=out['spike_indices'];tt=out['spike_ticks']
            checks['status_complete']=out['status']=='complete' and confirmed==end
            checks['candidate_exact']=exact(out['candidate'],u[start:start+done]<probabilities)
            expected_applied=out['candidate'].copy()
            source_cols=np.full(net.n_neurons,-1,np.int32);source_cols[inputs]=np.arange(36)
            source_spike=source_cols[ii]>=0
            expected_applied[tt[source_spike]-start,source_cols[ii[source_spike]]]=False
            checks['applied_exact']=exact(out['applied'],expected_applied)
            checks['edge_partition']=np.array_equal(out['per_tick']['edge_counts'][:,0],out['per_tick']['edge_counts'][:,1]+out['per_tick']['edge_counts'][:,2])
            checks['finite_state']=not out['per_tick']['state_invalid_count'].any() and not out['per_tick']['phase_nonfinite_count'].any()
            checks['hybrid_bound']=not spec['arm'].startswith('H') or not out['per_tick']['phase_below_reversal_count'].any()
            if prior_selected is not None:
                checks['selected_continuity']=all(exact(out['selected_'+key][0],prior_selected[key]) for key in ('v','s','h'))
            if len(ii):
                order=np.argsort(ii,kind='stable');si=ii[order];st=tt[order];same=si[1:]==si[:-1]
                first=np.r_[True,~same]
                checks['refractory']=bool(np.all(st[1:][same]-st[:-1][same]>=net.refractory[si[1:][same]]) and np.all(st[first]-prior_last[si[first]]>=net.refractory[si[first]]))
            else:checks['refractory']=True
            count_candidate=counts.copy()
            accumulate_chunk(count_candidate,ii,tt,start_tick=start,end_tick=confirmed);counts_ready=True
            np.maximum.at(prior_last,ii,tt)
            tail_i=np.concatenate((tail_i,ii));tail_t=np.concatenate((tail_t,tt));keep=tail_t>=confirmed-18
            tail_i,tail_t=tail_i[keep],tail_t[keep]
            if spec['condition']=='no_input':
                checks['no_input_rest']=not len(ii) and bool(np.all(net.v==-52.)) and not net.s.any() and not net.h.any()
            if blocked:
                checks['blocked_no_nonsource']=bool(np.all(source_spike))
                checks['blocked_no_accepted_edges']=not out['per_tick']['edge_counts'][:,1].any()
            if old_data is not None and end<=15000:
                old_end=int(np.searchsorted(old_data['all_spike_ticks'],end,side='left'))
                checks['c0_spikes']=exact(ii,old_data['all_spike_graph_indices'][spike_cursor:old_end]) and exact(tt,old_data['all_spike_ticks'][spike_cursor:old_end]);spike_cursor=old_end
                ca=old_data['requested_arrival_ticks'];mask=(ca>=start)&(ca<end)
                oc=np.zeros_like(out['candidate']);oa=np.zeros_like(oc)
                oc[ca[mask]-start,old_data['requested_arrival_source_column'][mask]]=True
                oa[ca[mask]-start,old_data['requested_arrival_source_column'][mask]]=old_data['applied_direct_voltage_arrival'][mask]
                checks['c0_direct']=exact(out['candidate'],oc) and exact(out['applied'],oa)
                old_s=old_samples[chunk]
                checks['c0_rng']=int(states[start])==old_s['rng_before'] and int(states[end])==old_s['rng_after']
                checks['c0_edge_visits']=int(out['per_tick']['edge_counts'][:,0].sum())==old_s['actual_edge_visits']
                checks['c0_extrema']=float(net.v.min())==old_s['global_voltage_min_mv'] and float(net.v.max())==old_s['global_voltage_max_mv']
            telemetry=dict(global_voltage_min=float(net.v.min()),global_voltage_max=float(net.v.max()),
                voltage_histogram=np.histogram(net.v,v_edges)[0],synaptic_histogram=np.histogram(net.s,s_edges)[0],h_histogram=np.histogram(net.h,h_edges)[0],
                spike_count=len(ii),source_spikes=int(source_spike.sum()),candidate_count=int(out['candidate'].sum()),applied_count=int(out['applied'].sum()),
                event_indices=event_indices.copy(),logical_rng_before=int(states[start]),logical_rng_completed_prefix=int(states[confirmed]),rate_hz=rate,
                cohort_spikes={name:int(np.isin(ii,idx).sum()) for name,idx in cohorts.items()})
            report['timing']['telemetry']+=time.perf_counter()-t
            t=time.perf_counter();ref_rows=reference_checks(out,selected,targets,spec['arm'],plan['tolerances_mv']);report['timing']['reference']+=time.perf_counter()-t
            checks['reference_accuracy']=all(r['passed'] for r in ref_rows)
            out.update(panel_telemetry=telemetry,panel_checks=checks,panel_reference_checks=ref_rows)
            save(f'chunk-{chunk:04d}',out);unpublished=False
            report['last_durable_chunk_end_tick']=confirmed
            counts=count_candidate;counts_tick=confirmed
            prior_selected={k:out['selected_'+k][-1].copy() for k in ('v','s','h')}
            report['spike_count']+=len(ii);report['candidate_count']+=int(out['candidate'].sum());report['applied_count']+=int(out['applied'].sum())
            report['reference_intervals']+=len(ref_rows);report['reference_threshold_ambiguities']+=sum(r['margin_within_observed_reference_error'] for r in ref_rows)
            for name,value in checks.items():ck(name,value)
            if end in CHECKPOINTS:checkpoint(end)
            if old_data is not None and end==15000:
                prefix_checks=dict(voltage=exact(net.v,old_data['final_voltage_mv']),synaptic=exact(net.s,old_data['final_synaptic_mv']),
                    all_spikes_consumed=spike_cursor==len(old_data['all_spike_ticks']),rng=int(states[15000])==int(old_data['final_rng_state'][0]),
                    counts=exact(np.stack((counts[0]+counts[1],counts[2],counts[3])),old_data['all_neuron_window_spike_counts']))
                atomic_json(directory/'c0-prefix-gate.json',dict(seed=spec['seed'],condition=spec['condition'],tick=15000,plan_sha256=expected_plan_sha,passed=all(prefix_checks.values()),checks=prefix_checks,
                    old_trace=record(ROOT/old['run_dir']/'trace.npz'),checkpoint=record(directory/'checkpoint-15000.complete.json')))
                for name,value in prefix_checks.items():ck('C0prefix:'+name,value)
                report['c0_prefix_passed']=True
            budget()
            atomic_json(directory/'progress.json',report,overwrite=True)
            if chunk%20==19:print(json.dumps(dict(trial=spec['name'],tick=end,spikes=report['spike_count'],elapsed=time.monotonic()-entered)),flush=True)
        report['complete']=True;report['status']='complete'
    except (Exception,KeyboardInterrupt) as error:
        report['status']='resource_limited' if isinstance(error,ResourceStop) else 'correctness_or_interruption_failure'
        report['global_resource_stop']=bool(isinstance(error,ResourceStop) and error.global_stop)
        report['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        failure_before=tree_bytes(directory)
        try:
            if unpublished and out is not None:
                save('failure-unpublished-chunk',out);report['last_durable_chunk_end_tick']=out['end_tick']
                if counts_ready:counts=count_candidate;counts_tick=out['end_tick']
            if net is not None:
                cp=net.checkpoint();cp.update(last_durable_chunk_end_tick=report['last_durable_chunk_end_tick'],last_complete_checkpoint_tick=report['last_complete_checkpoint_tick'],
                    confirmed_prefix_end_tick=confirmed,logical_rng_confirmed_prefix=int(states[confirmed]),window_counts_observed=counts,counts_end_tick=counts_tick)
                if executing:
                    cp['coherent_state']=False;cp['uncaught_execution_exception']='Unknownpartialchunkorwrapperreturnfailure; confirmedclock/RNGarepre-call. Mutabletickmayalreadyhaveadvanced. Do notresume.'
                save('failure-state',cp)
            retained=tree_bytes(directory)-failure_before
            report['failure_retention_bytes']=retained
            if retained>plan['budgets']['failure_reserve_bytes']:raise RuntimeError('Failure reserve exceeded')
        except Exception as failure:
            report['status']='retention_failure';report['errors'].append(dict(type=type(failure).__name__,message=str(failure)))
    finally:
        if counts is not None:
            try:
                report['counts_end_tick']=counts_tick
                report['summary']=summarize_counts(counts,counts_tick,cohorts)
                save('window-counts',dict(observed_window_counts=counts,completed_tick=counts_tick,raw_archive_end_tick=report['last_durable_chunk_end_tick']))
            except Exception as error:
                report['status']='retention_failure';report['complete']=False;report['errors'].append(dict(summary_error=repr(error)))
        try:check_sources(plan)
        except Exception as error:
            report['status']='correctness_or_interruption_failure';report['complete']=False;report['errors'].append(dict(post_source_check=repr(error)))
        report['wall_seconds']=time.monotonic()-entered;report['finished_utc']=utc()
        report['runtime']=parallel_runtime_info()
        if report['complete']:
            try:budget()
            except ResourceStop as error:
                report['status']='resource_limited';report['complete']=False;report['global_resource_stop']=error.global_stop;report['errors'].append(dict(final_budget=str(error)))
        report['status_scope']='Before final publication budget; terminal.json is authoritative for dispatch'
        atomic_json(directory/'result.json',report)
        terminal=dict(status=report['status'],complete=report['complete'],global_resource_stop=report.get('global_resource_stop',False),result=record(directory/'result.json'),errors=[])
        try:budget()
        except ResourceStop as error:
            if terminal['status'] in ('complete','resource_limited'):
                terminal.update(status='resource_limited',complete=False)
            terminal['global_resource_stop']|=error.global_stop;terminal['errors'].append(str(error))
        if failure_before is not None:
            terminal['failure_retention_bytes_through_result']=tree_bytes(directory)-failure_before
            if terminal['failure_retention_bytes_through_result']>plan['budgets']['failure_reserve_bytes']:
                terminal.update(status='retention_failure',complete=False);terminal['errors'].append('Failure reserve exceeded through finalization')
        terminal.update(resources=report['resources'],finished_utc=utc(),wall_seconds=time.monotonic()-entered)
        atomic_json(directory/'terminal.json',terminal)
        print(json.dumps(dict(trial=spec['name'],status=terminal['status'],tick=report['last_durable_chunk_end_tick'],wall_seconds=terminal['wall_seconds'])),flush=True)
    return 0 if terminal['status']=='complete' else (2 if terminal['status']=='resource_limited' else 1)


def run_panel(plan):
    run=ROOT/plan['run_dir'];started=time.monotonic()
    expected_sha=sha(PLAN);check_sources(plan,expected_sha)
    atomic_json(run/'started.json',dict(pid=os.getpid(),started_utc=utc(),monotonic_start=started,plan_sha256=expected_sha))
    result=dict(schema=1,plan_sha256=expected_sha,run_dir=plan['run_dir'],complete=False,status='running',trials=[],errors=[],started_utc=utc())
    process=None
    def global_budget():
        usage=dict(global_wall_seconds=time.monotonic()-started,global_output_bytes=tree_bytes(run),free_bytes=shutil.disk_usage(run).free)
        result['resources']=usage
        return usage['global_wall_seconds']>plan['budgets']['global_wall_seconds'] or usage['global_output_bytes']>plan['budgets']['global_output_bytes'] or usage['free_bytes']<plan['budgets']['min_free_bytes']
    try:
        check_sources(plan,expected_sha)
        for spec in plan['order']:
            if global_budget():
                result['status']='global_resource_limit';break
            if spec['arm']!='C0':
                gates,missing=c0_gates(plan)
                if missing:
                    result['status']='resource_limited_missing_c0_prefix';result['missing_c0_prefixes']=missing;break
                if not (run/'all-c0-prefixes-passed.json').exists():atomic_json(run/'all-c0-prefixes-passed.json',dict(passed=True,count=15,gates=gates))
            directory=run/spec['name'];directory.mkdir()
            with (directory/'worker.log').open('xb') as log:
                check_sources(plan,expected_sha)
                process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'trial','--ordinal',str(spec['ordinal']),'--expected-plan-sha',expected_sha],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                atomic_json(run/'active-worker.json',dict(**spec,pid=process.pid,started_utc=utc()),overwrite=True)
                print(json.dumps(dict(event='trial_started',**spec,pid=process.pid)),flush=True)
                code=process.wait()
            rp=directory/'result.json'
            tp=directory/'terminal.json'
            if not rp.exists() or not tp.exists():raise RuntimeError('Worker terminated without result/terminal; retain prior durablefiles, exit='+str(code))
            report=json.loads(rp.read_text());terminal=json.loads(tp.read_text())
            if terminal['result']['sha256']!=sha(rp):raise RuntimeError('Worker result changed after terminal receipt')
            result['trials'].append(dict(**spec,status=terminal['status'],complete=terminal['complete'],
                completed_tick=report['last_durable_chunk_end_tick'],counts_end_tick=report.get('counts_end_tick',0),result=record(rp),terminal=record(tp),summary=report.get('summary'),c0_prefix_passed=report['c0_prefix_passed']))
            atomic_json(run/'progress.json',result,overwrite=True)
            print(json.dumps(dict(event='trial_finished',trial=spec['name'],status=terminal['status'],tick=report['last_durable_chunk_end_tick'])),flush=True)
            if code not in (0,2):raise RuntimeError('Correctness/interruption/retention failure: '+spec['name'])
            if terminal['status'] not in ('complete','resource_limited'):raise RuntimeError('Invalid successful worker terminal status')
            if terminal.get('global_resource_stop') or global_budget():result['status']='global_resource_limit';break
        else:
            result['complete']=all(t['complete'] for t in result['trials']) and len(result['trials'])==60
            result['status']='complete' if result['complete'] else 'resource_limited_partial_panel'
    except (Exception,KeyboardInterrupt) as error:
        result['status']='failed';result['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            result['interrupted_worker']=dict(pid=process.pid,returncode=process.returncode,retention='Worker may retain failure checkpoint; after forced termination only previously durable files are guaranteed')
    finally:
        try:
            check_sources(plan,expected_sha)
            eligible={(t['seed'],t['arm'],t['condition']):t['summary'] for t in result['trials'] if t.get('summary') is not None and t['status'] in ('complete','resource_limited')}
            result['contrast_exclusions']=[dict(trial=t['name'],status=t['status'],reason='No summary or trial correctness/retention/interruption failure') for t in result['trials'] if (t['seed'],t['arm'],t['condition']) not in eligible]
            result['contrasts']=paired_contrasts(eligible) if eligible else None
            if not eligible:result['contrasts_unavailable_reason']='No eligible trial summaries; missing windows are not zero responses'
        except Exception as error:
            result.update(status='failed',complete=False);result['errors'].append(dict(final_source_or_analysis_error=repr(error)))
        if global_budget():
            result['global_resource_stop']=True;result['complete']=False
            if result['status']!='failed':result['status']='global_resource_limit'
        manifest=[]
        for p in run.rglob('*'):
            if p.is_file():manifest.append(record(p))
        atomic_json(run/'artifact-manifest.json',dict(schema=1,plan_sha256=expected_sha,artifacts=manifest))
        result['artifact_manifest']=record(run/'artifact-manifest.json')
        result['wall_seconds']=time.monotonic()-started;result['finished_utc']=utc()
        result['status_scope']='Before final publication budget; terminal.json is authoritative'
        atomic_json(run/'results.json',result)
        atomic_json(ROOT/'validation/inhibitory-recurrent-panel-results.json',result)
        terminal=dict(status=result['status'],complete=result['complete'],results=record(run/'results.json'),artifact_manifest=result['artifact_manifest'])
        if global_budget():
            terminal.update(global_resource_stop=True,complete=False)
            if terminal['status']!='failed':terminal['status']='global_resource_limit'
        terminal.update(resources=result['resources'],finished_utc=utc())
        atomic_json(run/'terminal.json',terminal)
        atomic_json(ROOT/'validation/inhibitory-recurrent-panel-terminal.json',terminal)
        print(json.dumps(dict(status=terminal['status'],complete=terminal['complete'],trials=len(result['trials']),wall_seconds=result['wall_seconds'])),flush=True)
    return 0 if terminal['complete'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','trial']);parser.add_argument('--ordinal',type=int);parser.add_argument('--expected-plan-sha');args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:
        plan=json.loads(PLAN.read_text())
        if args.action=='trial':
            if args.ordinal is None or not 0<=args.ordinal<60 or not args.expected_plan_sha:parser.error('trial requires ordinal0..59 and expected-plan-sha')
            raise SystemExit(trial(plan,args.ordinal,args.expected_plan_sha))
        raise SystemExit(run_panel(plan))
