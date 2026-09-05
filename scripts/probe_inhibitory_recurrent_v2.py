#!/usr/bin/env python3
"""Frozen, disposable recurrent performance probe; never a runtime default."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time
import traceback

import numpy as np
import numba
from numba import njit
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.neural import LIFNetwork, SparseDrive
from inhibitory_recurrent_kernel import FactorialNetwork
from inhibitory_factorial_solver import hybrid_step, coefficients, NODES32, WEIGHTS32

PLAN = ROOT / 'validation/inhibitory-recurrent-performance-plan-v2.json'
OUT = ROOT / 'validation/inhibitory-recurrent-performance-v2'
GRAPH = ROOT / 'data/processed/malecns_v1'
ARMS = ['reference', 'C0', 'C1', 'H0', 'H1']


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def write_json(p, x):
    Path(p).write_text(json.dumps(x, indent=2, allow_nan=False)+'\n')


def environment():
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                numpy=np.__version__, numba=numba.__version__, scipy=scipy.__version__)


def freeze():
    if PLAN.exists() or OUT.exists():
        raise RuntimeError('Refusing to replace frozen plan or run')
    old = json.loads((ROOT/'validation/or42a-summary-experiment.json').read_text())
    trial = next(t for t in old['trials'] if t['seed']==11 and t['condition']=='constant_baseline')
    paths = [Path(__file__), ROOT/'scripts/probe_inhibitory_recurrent.py',
        ROOT/'validation/inhibitory-recurrent-performance-plan.json',
        ROOT/'validation/inhibitory-recurrent-performance/results.json',
        ROOT/'scripts/inhibitory_recurrent_kernel.py',
        ROOT/'scripts/inhibitory_factorial_solver.py', ROOT/'fruitfly/neural.py',
        ROOT/'validation/inhibitory-factorial-solver-plan.json',
        ROOT/'validation/inhibitory-recurrent-input-audit.json',
        ROOT/'validation/inhibitory-recurrent-kernel-checks.json',
        ROOT/'validation/inhibitory-recurrent-kernel-independent-review.json',
        ROOT/'validation/or42a-summary-plan.json', ROOT/'validation/or42a-summary-experiment.json',
        ROOT/trial['run_dir']/'trace.npz', ROOT/trial['run_dir']/'samples.jsonl']
    paths += [GRAPH/(name+'.npy') for name in ('neuron_ids','indptr','targets','weights')]
    plan = dict(schema=1, frozen_utc=datetime.now(timezone.utc).isoformat(),
        purpose='C0 exact source parity and measured recurrent execution cost; not the scientific stimulus/seed panel',
        execution_order=ARMS, seed=11, duration_ms=50, dt_ms=.1, chunk_ms=5,
        rate_hz=11, graph_sha256='e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8',
        old_trial=trial['run_dir'], environment=environment(),
        sources={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths},
        budget=dict(wall_seconds=600, output_bytes=2*1024**3, peak_rss_bytes=8*1024**3,
            enforcement='Checked before and after each 5 ms chunk and each arm. One chunk/archive operation can overshoot; compilation, input generation and scalar grid count toward wall budget. Preflight source hashing is before execution; final source rechecks/artifact hashing/report writing are outside enforcement. No process kill.'),
        scalar_grid=dict(source='validation/inhibitory-factorial-solver-plan.json',cases=125,repetitions=128,
            method='Every frozen case is an independent interval with its own dt/coefficient; warmed compiled nested loop; no changing state between repetitions'),
        pairing='Immutable Python integer xorshift64* stream; initial SeedSequence(11) uint64. Kernel receives uniforms and has no RNG. Logical RNG boundaries are recorded separately.',
        c0_gate='Before altered arms: exact every-5ms full-state digest and final arrays against fresh original reference; old 50ms ordered spikes, candidates/applied flags, RNG, edge visits and extrema. Old prefix alone has no full state checkpoint.',
        direct_events='36 fixed Or42a sources, rate*.1/1000; applied reference inferred from candidates and same-tick spikes under zero source refractory; factorial instrumented writes compared to inference.',
        selection='36 input cells, two earlier inhibitory targets, ten fixed motor cells; no body or decoder execution',
        retention='Each chunk: all spikes, candidate/applied masks, selected traces/events, per-tick global phase diagnostics and edge/work counts. Initial/final full mutable checkpoints. No full all-cell time cube.',
        failure='Preserve partial files, failed checks and checkpoint; stop further arms after failed C0 parity or numerical failure. Resource termination is an engineering outcome, not biological rejection.',
        limits=['Quiet baseline may greatly underestimate later inhibitory work. Scalar cost is a separate workload, not a neural-time forecast.',
            'This probe does not establish physiology, stimulus contrasts, seed robustness or absence of persistent activity. No H1 promotion.'])
    plan['amendment']='Initial probe failed while compiling scalar timing helper, before graph load or any full-graph arm. Replace only dynamic indexing of the heterogeneous solver tuple with seven literal indices. Preserve original source, plan, input stream and failed receipt. Same arms, inputs, solver, cases, tolerances and budgets.'
    write_json(PLAN, plan)
    print(json.dumps(dict(plan=str(PLAN),sha256=sha(PLAN))))


def streams(seed, steps, ninputs):
    state = int(np.random.SeedSequence(seed).generate_state(1,dtype=np.uint64)[0]) or 1
    mask=(1<<64)-1
    u=np.empty((steps,ninputs)); states=np.empty(steps+1,np.uint64);states[0]=state
    for k in range(steps):
        for j in range(ninputs):
            state ^= state>>12; state ^= (state<<25)&mask; state ^= state>>27
            u[k,j]=(((state*2685821657736338717)&mask)>>11)/float(1<<53)
        states[k+1]=state
    return u,states


def archive(stem, data):
    arrays={}
    def convert(x, key):
        if isinstance(x,np.ndarray):
            arrays[key]=x
            return dict(array=key,shape=list(x.shape),dtype=str(x.dtype))
        if isinstance(x,dict): return {k:convert(v,key+'__'+k) for k,v in x.items()}
        if isinstance(x,(list,tuple)): return [convert(v,key+'__'+str(i)) for i,v in enumerate(x)]
        if isinstance(x,np.generic): return x.item()
        return x
    meta=convert(data,'root')
    np.savez_compressed(stem.with_suffix('.npz'),**arrays)
    write_json(stem.with_suffix('.json'),meta)


def canonical(net, reference=False):
    s=net.state_dict()
    if not reference: return s
    return dict(v=s['voltage_mv'],s=s['synaptic_mv'],h=np.zeros_like(s['voltage_mv']),
        last=s['last_spike_tick'],refractory=s['refractory_ticks'],blocked=s['ablated'],
        pending_count=s['pending_count'],pending=s['pending'],tick=s['tick'],seed=s['seed'],
        graph_sha256=s['graph_sha256'],coherent_state=True,original_complete_state=s)


STATE_KEYS=('v','s','h','last','refractory','blocked','pending_count','pending')
def state_hash(s):
    h=hashlib.sha256()
    h.update(str(s['tick']).encode())
    for key in STATE_KEYS:
        a=s[key];h.update(key.encode());h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()


@njit(cache=True)
def scalar_tile(grid, repetitions):
    results=np.empty((len(grid),7));checksum=0.
    for repeat in range(repetitions):
        for i in range(len(grid)):
            v,p,h,dt,a,b,c=grid[i]
            result=hybrid_step(v,p,h,dt,a,b,c,NODES32,WEIGHTS32)
            results[i,0]=result[0]
            results[i,1]=result[1]
            results[i,2]=result[2]
            results[i,3]=result[3]
            results[i,4]=result[4]
            results[i,5]=result[5]
            results[i,6]=result[6]
            checksum+=result[0]
    return results,checksum


def run():
    plan=json.loads(PLAN.read_text())
    for path, rec in plan['sources'].items():
        if sha(ROOT/path)!=rec['sha256']: raise RuntimeError('Pinned input changed: '+path)
    if environment()!=plan['environment']: raise RuntimeError('Environment changed after freeze')
    OUT.mkdir()
    began=time.perf_counter()
    result=dict(schema=1,plan_sha256=sha(PLAN),started_utc=datetime.now(timezone.utc).isoformat(),
        complete=False,checks=[],arms=[],errors=[],warmup={},environment=environment())
    def ck(name,value):
        result['checks'].append(dict(name=name,passed=bool(value)))
        if not value: raise RuntimeError('Failed check: '+name)
    def budget():
        wall=time.perf_counter()-began
        size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform!='darwin':rss*=1024
        result['resources']=dict(wall_seconds=wall,output_bytes=size,peak_rss_bytes=rss)
        limits=plan['budget']
        if wall>limits['wall_seconds'] or size>limits['output_bytes'] or rss>limits['peak_rss_bytes']:
            raise RuntimeError('Engineering resource budget reached: '+str(result['resources']))
    current=None;arm_dir=None;execution_in_progress=False
    try:
        op=json.loads((ROOT/'validation/or42a-summary-plan.json').read_text())
        inputs=np.array(op['source_graph_indices'],np.int32)
        u,states=streams(11,500,len(inputs));prob=np.full(len(inputs),11.)*.1/1000.
        archive(OUT/'input-stream',dict(uniforms=u,logical_rng_boundaries=states,probabilities=prob,input_indices=inputs))
        # Compile the same signatures on two cells, without advancing the full graph.
        tiny=(np.array([1,2],np.int64),np.array([0,1,2],np.int64),np.array([1,0],np.int32),np.array([1.,-1.],np.float32))
        t=time.perf_counter();r=LIFNetwork(*tiny,seed=11);r.advance(.1,drive=SparseDrive(np.array([0],np.int32),rates_hz=11.))
        result['warmup']['reference_seconds']=time.perf_counter()-t
        t=time.perf_counter()
        for arm in ARMS[1:]:
            n=FactorialNetwork(*tiny,arm,np.array([0],np.int32),np.array([0,1],np.int32));n.h[1]=.1 if arm.startswith('H') else 0.
            n.advance(np.ones((1,1))*.5,np.array([.0011]),log_selected_events=True)
        result['warmup']['factorial_seconds']=time.perf_counter()-t
        cases=json.loads((ROOT/plan['scalar_grid']['source']).read_text())['cases']
        grid=np.array([[c['v'],c['p'],c['h'],c['dt'],*coefficients(c['dt'])] for c in cases])
        ck('scalar_grid_count',len(grid)==125)
        t=time.perf_counter();scalar_tile(grid,1);result['warmup']['scalar_seconds']=time.perf_counter()-t
        t=time.perf_counter();sr,checksum=scalar_tile(grid,128);seconds=time.perf_counter()-t
        archive(OUT/'scalar-grid',dict(grid=grid,results=sr,checksum=checksum,repetitions=128))
        result['scalar_grid']=dict(intervals=16000,seconds=seconds,intervals_per_second=16000/seconds,
            positive_h_intervals=int(np.count_nonzero(grid[:,2]>0)*128),max_iterations=int(sr[:,5].max()),checksum=checksum)
        budget()
        graph=tuple(np.load(GRAPH/(key+'.npy')) for key in ('neuron_ids','indptr','targets','weights'))
        ids=graph[0]; index={int(v):i for i,v in enumerate(ids)}
        motor_ids=[v for group in op['motor_groups'].values() for v in group]
        selected=np.array(sorted(set(inputs.tolist()+[index[v] for v in [67052,13314]+motor_ids])),np.int32)
        archive(OUT/'selection',dict(indices=selected,body_ids=ids[selected],input_body_ids=ids[inputs]))
        ck('source_ids',np.array_equal(ids[inputs],op['source_body_ids']))
        old=np.load(ROOT/plan['old_trial']/'trace.npz',allow_pickle=False)
        old_samples=[json.loads(line) for line in (ROOT/plan['old_trial']/'samples.jsonl').read_text().splitlines()][:10]
        old_mask=old['all_spike_ticks']<500
        old_candidate=np.zeros_like(u,dtype=bool);old_applied=np.zeros_like(old_candidate)
        mask=old['requested_arrival_ticks']<500
        at=old['requested_arrival_ticks'][mask];ac=old['requested_arrival_source_column'][mask]
        old_candidate[at,ac]=True;old_applied[at,ac]=old['applied_direct_voltage_arrival'][mask]
        refs=[];reference_final=None
        for arm in ARMS:
            budget();arm_dir=OUT/arm;arm_dir.mkdir()
            t=time.perf_counter()
            if arm=='reference':
                current=LIFNetwork(*graph,seed=11)
                current.advance(0.,drive=SparseDrive(inputs,rates_hz=11.))
            else:current=FactorialNetwork(*graph,arm,inputs,selected,seed=11)
            construction=time.perf_counter()-t
            ck(arm+'_graph',current.graph_sha256==plan['graph_sha256'])
            initial=canonical(current,arm=='reference');initial['logical_rng_state']=int(states[0]);archive(arm_dir/'initial',initial)
            ar=dict(arm=arm,construction_seconds=construction,chunks=[],complete=False);result['arms'].append(ar)
            ii=[];tt=[];candidates=[];applied=[]
            for chunk in range(10):
                budget();start=chunk*50;end=start+50;t=time.perf_counter()
                if arm=='reference':
                    execution_in_progress=True
                    batch=current.advance(5.,drive=SparseDrive(inputs,rates_hz=11.))
                    execution_in_progress=False
                    kernel_seconds=time.perf_counter()-t
                    ticks=np.rint(batch.times_ms/.1).astype(np.int64)
                    cand=u[start:end]<prob;app=cand.copy()
                    for cell,tick in zip(batch.indices,ticks):
                        columns=np.flatnonzero(inputs==cell)
                        if len(columns):app[tick-start,columns[0]]=False
                    out=dict(status='complete',end_tick=end,completed_ticks=50,coherent_state=True,
                        spike_indices=batch.indices,spike_ticks=ticks,candidate=cand,applied=app,
                        traversed_edges=batch.traversed_edges,
                        applied_accounting='Inferred candidate AND no same-tick source firing; source refractory zero')
                else:
                    execution_in_progress=True
                    out=current.advance(u[start:end],prob,log_selected_events=True)
                    execution_in_progress=False
                    kernel_seconds=time.perf_counter()-t
                t=time.perf_counter();checkpoint=canonical(current,arm=='reference')
                logical_end=current.tick
                out['logical_rng_before']=int(states[start]);out['logical_rng_completed_prefix']=int(states[logical_end])
                out['logical_rng_note']='External stream ownership; partial failed tick may already have used supplied inputs, see phase'
                out['checkpoint_digest']=state_hash(checkpoint)
                archive(arm_dir/f'chunk-{chunk:02d}',out)
                vmin=float(current.voltage_mv.min());vmax=float(current.voltage_mv.max())
                obs=dict(chunk=chunk,start_tick=start,end_tick=current.tick,kernel_seconds=kernel_seconds,
                    telemetry_archive_seconds=time.perf_counter()-t,spikes=len(out['spike_indices']),
                    vmin=vmin if np.isfinite(vmin) else None,vmax=vmax if np.isfinite(vmax) else None,
                    extrema_nonfinite=[not bool(np.isfinite(vmin)),not bool(np.isfinite(vmax))],state_sha256=out['checkpoint_digest'])
                ar['chunks'].append(obs)
                ck(arm+f'_chunk{chunk}_complete',out['status']=='complete' and current.tick==end)
                ii.append(out['spike_indices']);tt.append(out['spike_ticks']);candidates.append(out['candidate']);applied.append(out['applied'])
                if arm=='reference':
                    ck(f'reference_rng_{chunk}',int(current._rng_state[0])==int(states[end])==old_samples[chunk]['rng_after'])
                    ck(f'reference_old_extrema_{chunk}',obs['vmin']==old_samples[chunk]['global_voltage_min_mv'] and obs['vmax']==old_samples[chunk]['global_voltage_max_mv'])
                    ck(f'reference_old_edges_{chunk}',out['traversed_edges']==old_samples[chunk]['actual_edge_visits'])
                    refs.append(dict(out=out,obs=obs))
                elif arm=='C0':
                    ck(f'C0_checkpoint_{chunk}',out['checkpoint_digest']==refs[chunk]['obs']['state_sha256'])
                    for key in ('spike_indices','spike_ticks','candidate','applied'):
                        ck(f'C0_{key}_{chunk}',np.array_equal(out[key],refs[chunk]['out'][key]))
                    ck(f'C0_edges_{chunk}',int(out['per_tick']['edge_counts'][:,0,:].sum())==refs[chunk]['out']['traversed_edges'])
                if arm!='reference':
                    ck(arm+f'_edge_partition_{chunk}',np.array_equal(out['per_tick']['edge_counts'][:,0],out['per_tick']['edge_counts'][:,1]+out['per_tick']['edge_counts'][:,2]))
                    ck(arm+f'_finite_{chunk}',not out['per_tick']['state_invalid_count'].any() and not out['per_tick']['phase_nonfinite_count'].any())
                    if arm.startswith('H'):ck(arm+f'_lower_bound_{chunk}',not out['per_tick']['phase_below_reversal_count'].any())
                write_json(OUT/'progress.json',result)
                print(json.dumps(dict(arm=arm,tick=current.tick,kernel_seconds=kernel_seconds,spikes=obs['spikes'])),flush=True)
                budget()
            final=canonical(current,arm=='reference');final['logical_rng_state']=int(states[500]);archive(arm_dir/'final',final)
            budget()
            ar['kernel_seconds']=sum(x['kernel_seconds'] for x in ar['chunks'])
            ar['spikes']=sum(len(x) for x in ii)
            ar['complete']=True
            if arm in ('reference','C0'):
                ck(arm+'_old_spikes',np.array_equal(np.concatenate(ii),old['all_spike_graph_indices'][old_mask]) and np.array_equal(np.concatenate(tt),old['all_spike_ticks'][old_mask]))
                ck(arm+'_old_candidates',np.array_equal(np.concatenate(candidates),old_candidate))
                ck(arm+'_old_applied',np.array_equal(np.concatenate(applied),old_applied))
            if arm=='reference':reference_final=final
            if arm=='C0':
                for key in STATE_KEYS:ck('C0_final_exact_'+key,final[key].dtype==reference_final[key].dtype and final[key].tobytes()==reference_final[key].tobytes())
            current=None;del initial,checkpoint,final;gc.collect()
        result['complete']=True
    except (Exception, KeyboardInterrupt) as error:
        result['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        if current is not None and arm_dir is not None:
            try:
                failure=canonical(current,result['arms'][-1]['arm']=='reference')
                failure['logical_rng_completed_prefix']=int(states[min(current.tick,500)])
                if execution_in_progress:
                    failure['coherent_state']=False
                    failure['uncaught_execution_exception']='Operation raised without returning progress. Arrays may contain an unknown partial chunk; tick and logical RNG identify only the prior completed prefix. Do not resume.'
                archive(arm_dir/'failure-checkpoint',failure)
            except Exception as nested:result['errors'].append(dict(checkpoint_error=repr(nested)))
    finally:
        result['execution_wall_seconds']=time.perf_counter()-began
        for path, rec in plan['sources'].items():
            try:unchanged=sha(ROOT/path)==rec['sha256']
            except Exception:unchanged=False
            result['checks'].append(dict(name='post_run_source_unchanged:'+path,passed=unchanged))
            if not unchanged:result['complete']=False
        result['wall_seconds']=time.perf_counter()-began
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        result['artifacts']={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in OUT.rglob('*') if p.is_file() and p.name not in ('results.json','progress.json')}
        write_json(OUT/'results.json',result)
        print(json.dumps(dict(complete=result['complete'],checks=len(result['checks']),errors=result['errors'],wall_seconds=result['wall_seconds'])),flush=True)
    return 0 if result['complete'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','run']);args=parser.parse_args()
    if args.action=='freeze':freeze()
    else:raise SystemExit(run())
