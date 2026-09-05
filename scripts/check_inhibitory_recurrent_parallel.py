#!/usr/bin/env python3
"""Frozen bounded synthetic comparison; no anatomical graph or body is loaded."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout
import hashlib
import io
import json
import platform
import re
import sys
import time
import numpy as np
import numba

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import inhibitory_recurrent_kernel as serial
import inhibitory_recurrent_parallel as parallel

BASE = ROOT/'validation/inhibitory-recurrent-parallel'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def main():
    plan_path=BASE.with_name(BASE.name+'-plan.json')
    receipt_path=BASE.with_name(BASE.name+'-checks.json')
    if plan_path.exists() or receipt_path.exists():
        raise RuntimeError('Refusing to replace frozen synthetic attempt')
    sources=[Path(__file__), ROOT/'scripts/inhibitory_recurrent_parallel.py', ROOT/'scripts/inhibitory_recurrent_kernel.py', ROOT/'scripts/inhibitory_factorial_solver.py']
    frozen={str(p.relative_to(ROOT)):sha(p) for p in sources}
    write(plan_path,dict(frozen_utc=datetime.now(timezone.utc).isoformat(),source_sha256=frozen,
        scope='128-cell deterministic synthetic graph and detached interval arrays only; no anatomical graph or body',
        fixture=dict(cells=128,steps=300,dt_ms=.1,inputs=list(range(0,128,16)),rng='NumPy default_rng seed11; caller-supplied draws',
            edges='Five outgoing per cell; offsets1,2,3,7,11 modulo128; weights46,-23,0,70000,-69 float32',
            probabilities=[.05,.1,.3,1.,0.,.02,.5,.01],initial_s='100 at each third cell, otherwise0',
            initial_h='H only: repeating0,.1,3,100,1e8; C allzero'),
        comparisons=['all four arms whole300ticks; complete output and checkpoint bytes',
            'all four arms chunked0:7,7:71,71:300; per-chunk all output/checkpoint bytes and full/chunk final bytes',
            'all four arms source block changed after2ticks before delayed delivery',
            'H0/H1 failures: multiple invalid available cells, unavailable invalid state, postdelivery infinite-edge corruption, lower-bound violation; completed prefix and partial evidence exact',
            'four worker IDs and optimized parfor evidence; detached valid/invalid/unavailable interval scratch leaves all native arrays unchanged',
            'one-thread versus four-thread H outputs and checkpoints exact'],
        parity='dtype,shape,raw bytes for every recursively contained array; exact scalar/schema equality',
        failure='Retain failures and raw arrays; no full graph or parameter revision',
        environment=dict(python=sys.version,numpy=np.__version__,numba=numba.__version__,platform=platform.platform())))
    checks={}; arrays={}; meta={}; errors=[]; began=time.perf_counter()
    def ck(name,value):
        checks[name]=bool(value)
    def archive(value,key):
        if isinstance(value,np.ndarray):
            arrays[key]=value.copy()
            return dict(array=key,shape=list(value.shape),dtype=str(value.dtype))
        if isinstance(value,dict):return {k:archive(v,key+'__'+k) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [archive(v,key+'__'+str(i)) for i,v in enumerate(value)]
        if isinstance(value,np.generic):value=value.item()
        if isinstance(value,float) and not np.isfinite(value):return dict(nonfinite=repr(value))
        return value
    def equal(a,b):
        if isinstance(a,np.ndarray):return isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
        if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
        if isinstance(a,(list,tuple)):return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
        return type(a)==type(b) and a==b
    def compare(name,left,right):
        ck(name,equal(left,right))
        meta[name]=dict(serial=archive(left,name+'__serial'),parallel=archive(right,name+'__parallel'))
    try:
        parallel.configure_threads(4)
        n=128;ids=np.arange(100,100+n,dtype=np.int64);ptr=np.arange(0,(n+1)*5,5,dtype=np.int64)
        targets=np.array([(i+d)%n for i in range(n) for d in [1,2,3,7,11]],np.int32)
        weights=np.tile(np.array([46.,-23.,0.,70000.,-69.],np.float32),n)
        inputs=np.arange(0,n,16,dtype=np.int32);selected=np.arange(n,dtype=np.int32)
        u=np.random.default_rng(11).random((300,len(inputs)));prob=np.array([.05,.1,.3,1.,0.,.02,.5,.01])
        meta['fixture']=archive(dict(neuron_ids=ids,indptr=ptr,targets=targets,weights=weights,inputs=inputs,selected=selected,uniforms=u,probabilities=prob),'fixture')
        def create(module,arm):
            net=module.FactorialNetwork(ids,ptr,targets,weights.copy(),arm,inputs,selected)
            net.s[::3]=100.
            if arm.startswith('H'):net.h[:]=np.resize(np.array([0.,.1,3.,100.,1e8]),n)
            return net
        finals={}
        for arm in ['C0','C1','H0','H1']:
            nets=[create(m,arm) for m in [serial,parallel]]
            out=[net.advance(u,prob,log_selected_events=True) for net in nets]
            ck(arm+':complete',all(o['status']=='complete' for o in out))
            compare(arm+':full_output',*out);compare(arm+':full_checkpoint',*[net.checkpoint() for net in nets])
            finals[arm]=nets[0].checkpoint()
            if arm.startswith('H'):
                parallel.configure_threads(1);single=create(parallel,arm)
                one=single.advance(u,prob,log_selected_events=True)
                compare(arm+':thread_mask_output',out[1],one);compare(arm+':thread_mask_checkpoint',nets[1].checkpoint(),single.checkpoint())
                parallel.configure_threads(4)
            nets=[create(m,arm) for m in [serial,parallel]]
            for start,end in [(0,7),(7,71),(71,300)]:
                out=[net.advance(u[start:end],prob,log_selected_events=True) for net in nets]
                compare(arm+f':chunk{start}_output',*out)
                compare(arm+f':chunk{start}_checkpoint',*[net.checkpoint() for net in nets])
            compare(arm+':full_chunk_checkpoint',finals[arm],nets[1].checkpoint())
            nets=[create(m,arm) for m in [serial,parallel]]
            prefix=[net.advance(u[:2],np.ones(len(inputs)),log_selected_events=True) for net in nets]
            compare(arm+':block_prefix',*prefix)
            for net in nets:net.blocked[0]=True
            out=[net.advance(u[2:30],np.zeros(len(inputs)),log_selected_events=True) for net in nets]
            compare(arm+':delivery_block_output',*out);compare(arm+':delivery_block_checkpoint',*[net.checkpoint() for net in nets])
            ck(arm+':actual_blocked_edges',out[0]['per_tick']['edge_counts'][:,3].sum()>0)
        for arm in ['H0','H1']:
            for kind in ['multiple_invalid','unavailable_invalid','postdelivery_infinite_edge','lower_bound']:
                nets=[create(m,arm) for m in [serial,parallel]]
                for net in nets:
                    net.s[:]=0.;net.h[:]=0.
                    net.advance(u[:5],np.zeros(len(inputs)))
                    if kind=='multiple_invalid':
                        net.v[1]=-44.;net.s[5]=-1.;net.h[90]=np.nan
                    elif kind=='unavailable_invalid':
                        net.last[5]=net.tick;net.h[5]=np.inf
                    elif kind=='postdelivery_infinite_edge':
                        # Deliberate post-construction corruption of an isolated
                        # synthetic edge exercises postdelivery failure retention.
                        net.weights[0]=np.inf
                        net._pending[net.tick % 19,0]=0
                        net.pending_count[net.tick % 19]=1
                    else:
                        net.v[5]=-76.
                out=[net.advance(u[:3],np.zeros(len(inputs)),log_selected_events=True) for net in nets]
                compare(arm+':failure_'+kind+'_output',*out)
                compare(arm+':failure_'+kind+'_checkpoint',*[net.checkpoint() for net in nets])
                ck(arm+':failure_'+kind+'_failed',all(o['status']=='failed' for o in out))
                denied=[]
                for net in nets:
                    try:net.advance(u[:1],np.zeros(len(inputs)));denied.append(False)
                    except RuntimeError:denied.append(True)
                ck(arm+':failure_'+kind+'_continuation_denied',all(denied))
        # Independent scratch evaluation also records actual worker participation.
        v=np.full(n,-52.);s=np.ones(n);h=np.resize(np.array([0.,.1,3.,100.,1e8]),n)
        last=np.full(n,-100,np.int64);refractory=np.full(n,22,np.int64)
        h[5]=np.nan;last[90]=0
        scratch=np.full((n,7),-999.);status=np.full(n,-9,np.int8);workers=np.full(n,-9,np.int32)
        before=[x.copy() for x in [v,s,h,last,refractory]]
        parallel._h_intervals(0,*parallel.coefficients(.1),v,s,h,last,refractory,scratch,status,workers)
        ck('scratch:no_native_mutation',all(equal(a,b) for a,b in zip(before,[v,s,h,last,refractory])))
        ck('scratch:four_actual_workers',np.array_equal(np.unique(workers),np.arange(4)))
        ck('scratch:error_and_unavailable_status',status[5]==1 and status[90]==2 and np.count_nonzero(status==0)==126)
        ck('scratch:unavailable_row_unwritten',np.all(scratch[90]==-999.))
        ck('runtime:four_threads',parallel.parallel_runtime_info()['numba_threads']==4)
        # Recompile only the detached scratch signature to retain optimization
        # metadata even when its native code came from an earlier disk cache.
        parallel._h_intervals.recompile()
        stream=io.StringIO()
        with redirect_stdout(stream):parallel._h_intervals.parallel_diagnostics(level=4)
        compiler=stream.getvalue();compiler_path=BASE.with_name(BASE.name+'-compiler.txt');compiler_path.write_text(compiler)
        ck('compiler:parallel_transformation','Parallel loop listing' in compiler and bool(re.search(r'prange\(len\(v\)\).*#\d+',compiler)))
        ck('compiler:no_fastmath',not parallel._h_intervals.targetoptions.get('fastmath',False))
        meta['scratch']=archive(dict(before=before,after=[v,s,h,last,refractory],scratch=scratch,status=status,workers=workers),'scratch')
        meta['parallel_runtime']=parallel.parallel_runtime_info()
    except Exception as exc:
        import traceback
        errors.append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    for path,digest in frozen.items():ck('unchanged:'+path,sha(ROOT/path)==digest)
    npz_path=BASE.with_name(BASE.name+'-arrays.npz');np.savez_compressed(npz_path,**arrays)
    meta_path=BASE.with_name(BASE.name+'-arrays.json');write(meta_path,meta)
    artifacts=[npz_path,meta_path]
    cp=BASE.with_name(BASE.name+'-compiler.txt')
    if cp.exists():artifacts.append(cp)
    receipt=dict(scope='Synthetic saved-data parity and actual parallel compilation only; no full graph',
        plan_sha256=sha(plan_path),source_sha256=frozen,checks=checks,check_count=len(checks),
        passed=all(checks.values()) and not errors,errors=errors,wall_seconds=time.perf_counter()-began,
        artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in artifacts},
        runtime=parallel.parallel_runtime_info())
    write(receipt_path,receipt);print(json.dumps(receipt,indent=2))
    return 0 if receipt['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
