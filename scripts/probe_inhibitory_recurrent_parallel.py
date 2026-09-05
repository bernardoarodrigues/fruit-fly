#!/usr/bin/env python3
"""Matched four-thread comparison against immutable serial probe artifacts."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

import numpy as np
import numba

from probe_inhibitory_recurrent_v2 import archive, environment, sha, state_hash, write_json
from inhibitory_recurrent_parallel import FactorialNetwork, configure_threads

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/inhibitory-recurrent-parallel-performance-plan.json'
OUT=ROOT/'validation/inhibitory-recurrent-parallel-performance'
SERIAL=ROOT/'validation/inhibitory-recurrent-performance-v2'
GRAPH=ROOT/'data/processed/malecns_v1'
ARMS=['C0','C1','H0','H1']


def freeze():
    if PLAN.exists() or OUT.exists():raise RuntimeError('Refusing to replace plan or run')
    sr=json.loads((SERIAL/'results.json').read_text())
    if not sr['complete'] or not all(c['passed'] for c in sr['checks']):raise RuntimeError('Serial probe incomplete')
    paths=[Path(__file__),ROOT/'scripts/inhibitory_recurrent_parallel.py',
        ROOT/'scripts/inhibitory_recurrent_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',
        ROOT/'scripts/probe_inhibitory_recurrent_v2.py',ROOT/'fruitfly/neural.py',
        ROOT/'validation/inhibitory-recurrent-parallel-checks.json',
        ROOT/'validation/inhibitory-recurrent-parallel-independent-review.json',
        ROOT/'validation/inhibitory-recurrent-performance-plan-v2.json',SERIAL/'results.json']
    paths.extend(SERIAL.rglob('*.npz'))
    paths += [GRAPH/(key+'.npy') for key in ('neuron_ids','indptr','targets','weights')]
    plan=dict(schema=1,frozen_utc=datetime.now(timezone.utc).isoformat(),environment=environment(),
        sources={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths},
        purpose='Exact matched four-thread performance comparison; unchanged neural equations and input. No scientific stimulus/seed panel or model promotion.',
        arms=ARMS,seed=11,threads=4,duration_ms=50,chunk_ms=5,dt_ms=.1,
        input='Reuse every saved serial uniform/probability/selection/RNG-boundary value; no new generator',
        equality='Every saved numeric chunk array compared by dtype, shape and bytes; final complete canonical arrays and each 5ms state digest compared to serial. Global intermediate arrays were not archived by serial, so their digests are producer summaries.',
        timing='Fresh construction and warmup separate from kernel calls. Serial timings are the prior same-protocol run, not paired simultaneous measurements or a timing-confidence study. Four-thread mode is fixed before results.',
        budget=dict(wall_seconds=600,output_bytes=2*1024**3,peak_rss_bytes=8*1024**3),
        enforcement='Execution timer after preflight hashes; check before/after each5mschunk and arm-final archive; one operation can overshoot; final hashes/report outside enforcement.',
        failure='Retain failure/result and any partial checkpoint, mark uncaught execution state incoherent and do not resume. No tuning after failed parity; a numerical mismatch blocks scientific panel use.',
        limits=['50ms baseline does not represent later inhibitory load or establish stability.','Parallel speed does not establish physiology or justify H1 promotion.'])
    write_json(PLAN,plan);print(json.dumps(dict(plan=str(PLAN),sha256=sha(PLAN))))


def arrays(x,prefix='root'):
    if isinstance(x,np.ndarray):return {prefix:x}
    out={}
    if isinstance(x,dict):
        for k,v in x.items():out.update(arrays(v,prefix+'__'+k))
    return out


def run():
    plan=json.loads(PLAN.read_text())
    for p,r in plan['sources'].items():
        if sha(ROOT/p)!=r['sha256']:raise RuntimeError('Changed source: '+p)
    if environment()!=plan['environment']:raise RuntimeError('Environment drift')
    OUT.mkdir();began=time.perf_counter()
    result=dict(schema=1,plan_sha256=sha(PLAN),started_utc=datetime.now(timezone.utc).isoformat(),complete=False,arms=[],checks=[],errors=[])
    def ck(name,value):
        result['checks'].append(dict(name=name,passed=bool(value)))
        if not value:raise RuntimeError('Failed check: '+name)
    def budget():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        measured=dict(wall_seconds=time.perf_counter()-began,output_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),peak_rss_bytes=rss)
        result['resources']=measured
        if any(measured[k]>v for k,v in plan['budget'].items()):raise RuntimeError('Engineering resource limit: '+str(measured))
    net=None;armdir=None;executing=False;confirmed_tick=0
    try:
        configure_threads(4);ck('four_threads',numba.get_num_threads()==4)
        t=time.perf_counter()
        tiny=FactorialNetwork(np.arange(128,dtype=np.int64),np.zeros(129,np.int64),np.empty(0,np.int32),np.empty(0,np.float32),'H1',np.array([0],np.int32),np.array([0,1],np.int32),seed=11)
        tiny.h[:]=3.;tiny.s[:]=3.
        tiny.advance(np.array([[.5]]),np.array([.0011]),log_selected_events=True)
        result['warmup_seconds']=time.perf_counter()-t
        result['threading_layer']=numba.threading_layer()
        graph=tuple(np.load(GRAPH/(key+'.npy')) for key in ('neuron_ids','indptr','targets','weights'))
        with np.load(SERIAL/'input-stream.npz') as a:
            u=a['root__uniforms'];states=a['root__logical_rng_boundaries'];prob=a['root__probabilities'];inputs=a['root__input_indices']
        with np.load(SERIAL/'selection.npz') as a:selected=a['root__indices']
        old=json.loads((SERIAL/'results.json').read_text());oldarms={a['arm']:a for a in old['arms']}
        for arm in ARMS:
            budget();armdir=OUT/arm;armdir.mkdir();t=time.perf_counter()
            net=FactorialNetwork(*graph,arm,inputs,selected,seed=11)
            confirmed_tick=0
            ar=dict(arm=arm,construction_seconds=time.perf_counter()-t,chunks=[],complete=False);result['arms'].append(ar)
            initial=net.checkpoint();initial['logical_rng_state']=int(states[0]);archive(armdir/'initial',initial)
            for chunk in range(10):
                budget();start=chunk*50;confirmed_tick=net.tick;t=time.perf_counter();executing=True
                out=net.advance(u[start:start+50],prob,log_selected_events=True)
                executing=False;confirmed_tick=out['end_tick'];elapsed=time.perf_counter()-t
                out['logical_rng_before']=int(states[start]);out['logical_rng_completed_prefix']=int(states[net.tick])
                cp=net.checkpoint();out['checkpoint_digest']=state_hash(cp)
                archive(armdir/f'chunk-{chunk:02d}',out)
                ar['chunks'].append(dict(chunk=chunk,kernel_seconds=elapsed,end_tick=net.tick,spikes=len(out['spike_indices']),state_sha256=out['checkpoint_digest']))
                ck(f'{arm}:{chunk}:complete',out['status']=='complete' and net.tick==start+50)
                actual=arrays(out)
                with np.load(SERIAL/arm/f'chunk-{chunk:02d}.npz',allow_pickle=False) as expected:
                    ck(f'{arm}:{chunk}:array_names',set(actual)==set(expected.files))
                    for key in expected.files:
                        a,b=actual[key],expected[key]
                        ck(f'{arm}:{chunk}:{key}',a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes())
                ck(f'{arm}:{chunk}:state_digest',out['checkpoint_digest']==oldarms[arm]['chunks'][chunk]['state_sha256'])
                write_json(OUT/'progress.json',result)
                print(json.dumps(dict(arm=arm,tick=net.tick,kernel_seconds=elapsed)),flush=True)
                budget()
            final=net.checkpoint();final['logical_rng_state']=int(states[500]);archive(armdir/'final',final)
            with np.load(SERIAL/arm/'final.npz',allow_pickle=False) as expected:
                actual=arrays(final)
                ck(arm+':final_array_names',set(actual)==set(expected.files))
                for key in expected.files:
                    a,b=actual[key],expected[key]
                    ck(arm+':final:'+key,a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes())
            budget()
            ar['kernel_seconds']=sum(c['kernel_seconds'] for c in ar['chunks'])
            ar['serial_kernel_seconds']=oldarms[arm]['kernel_seconds']
            ar['observed_serial_over_parallel_ratio']=ar['serial_kernel_seconds']/ar['kernel_seconds']
            ar['complete']=True;net=None
        result['complete']=True
    except (Exception,KeyboardInterrupt) as error:
        result['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        if net is not None and armdir is not None:
            try:
                cp=net.checkpoint();cp['logical_rng_completed_prefix']=int(states[min(net.tick,500)])
                if executing:
                    cp['coherent_state']=False
                    cp['confirmed_prefix_end_tick']=confirmed_tick
                    cp['logical_rng_completed_prefix']=int(states[confirmed_tick])
                    cp['uncaught_execution_exception']='Unknown partial chunk or wrapper return failure; confirmed_prefix_end_tick/RNG denote the pre-call boundary. The separate mutable tick field may already have advanced and is not a confirmed prefix. Do not resume.'
                archive(armdir/'failure-checkpoint',cp)
            except Exception as nested:result['errors'].append(dict(checkpoint_error=repr(nested)))
    finally:
        result['execution_wall_seconds']=time.perf_counter()-began
        for p,r in plan['sources'].items():
            try:same=sha(ROOT/p)==r['sha256']
            except Exception:same=False
            result['checks'].append(dict(name='unchanged:'+p,passed=same))
            if not same:result['complete']=False
        result['artifacts']={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in OUT.rglob('*') if p.is_file() and p.name not in ('results.json','progress.json')}
        result['wall_seconds']=time.perf_counter()-began;result['finished_utc']=datetime.now(timezone.utc).isoformat()
        write_json(OUT/'results.json',result)
        print(json.dumps(dict(complete=result['complete'],checks=len(result['checks']),errors=result['errors'],wall_seconds=result['wall_seconds'])),flush=True)
    return 0 if result['complete'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','run']);a=parser.parse_args()
    if a.action=='freeze':freeze()
    else:raise SystemExit(run())
