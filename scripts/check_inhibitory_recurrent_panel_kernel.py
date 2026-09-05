#!/usr/bin/env python3
"""Frozen small synthetic parity/selection checks; no anatomical graph loaded."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import sys
import time
import numpy as np
import numba

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import inhibitory_recurrent_parallel as legacy
import inhibitory_recurrent_panel_kernel as panel
from inhibitory_factorial_solver import hybrid_step, coefficients, NODES32, WEIGHTS32
BASE=ROOT/'validation/inhibitory-recurrent-panel-kernel'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def equal(a,b):
    if isinstance(a,np.ndarray):return isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
    if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return type(a)==type(b) and a==b

def main():
    plan=BASE.with_name(BASE.name+'-plan.json');receipt=BASE.with_name(BASE.name+'-checks.json')
    if plan.exists() or receipt.exists():raise RuntimeError('Refusing to overwrite frozen attempt')
    sources=[Path(__file__),ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_recurrent_parallel.py',ROOT/'scripts/inhibitory_factorial_solver.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    write(plan,dict(frozen_utc=datetime.now(timezone.utc).isoformat(),source_sha256=hashes,
        scope='Synthetic64-cell graph only, fixed48 traces and independently64-cell reference oracle; no full graph',
        steps=120,seed=11,threads=4,selected_indices=list(range(48)),event_subset=[7,19],
        graph='64 cells; three edges each to offsets1,3,7 modulo64; weights100,-46,0 float32',
        input='8 cells spaced by8; fixedprobability.2, callerdefault_rng11; same uniforms across arms',
        tests=['all four arms legacy output/checkpoint exact except new fields',
            'default versus2-target and empty event logs; full48 traces unchanged; invalid subset rejected before mutation',
            'reference extrema independently selected from full64 traces, including unselected winners',
            'earliesttick/lowestindex ties; unavailable exclusion; h0 excluded ratio; p0 valid negativeinfinity; log ratio avoids division overflow',
            'failure prefix/partial reference separation and existing failure arrays exact; event selection may change across chunks'],
        reference_names=list(panel.REFERENCE_NAMES),reference_columns=list(panel.REFERENCE_COLUMNS),
        retention='All comparisons and fixtures retained as NPZ plus JSON array tree',
        environment=dict(python=sys.version,numpy=np.__version__,numba=numba.__version__)))
    checks={};arrays={};meta={};errors=[];began=time.perf_counter()
    def ck(name,value):checks[name]=bool(value)
    def archive(value,key):
        if isinstance(value,np.ndarray):arrays[key]=value.copy();return dict(array=key,dtype=str(value.dtype),shape=list(value.shape))
        if isinstance(value,dict):return {k:archive(v,key+'__'+k) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [archive(v,key+'__'+str(i)) for i,v in enumerate(value)]
        if isinstance(value,np.generic):value=value.item()
        if isinstance(value,float) and not np.isfinite(value):return dict(nonfinite=repr(value))
        return value
    def compare(name,left,right):
        ck(name,equal(left,right));meta[name]=dict(left=archive(left,name+'__left'),right=archive(right,name+'__right'))
    def old_fields(out):
        result={k:v for k,v in out.items() if k!='reference_intervals'}
        result['schema']={k:v for k,v in result['schema'].items() if k not in ['event_graph_indices','reference_names','reference_columns']}
        return result
    def expected_refs(out,first=0):
        # Independent ranking from full retained traces, not panel selection code.
        available=out['selected_available'];p=out['selected_s'][:-1];h=out['selected_h'][:-1]
        margin=np.abs(out['selected_prethreshold_v']+45.)
        ratio=np.full(p.shape,np.nan)
        for k,i in zip(*np.where(available & (h>0))):ratio[k,i]=math.log(float(p[k,i]))-math.log(float(h[k,i])) if p[k,i]>0 else -np.inf
        rows=[]
        for rank in range(3):
            candidates=list(zip(*np.where(available if rank!=2 else available&(h>0))))
            if not candidates:rows.append(None);continue
            def score(pair):
                k,i=pair
                return -h[k,i] if rank==0 else (margin[k,i] if rank==1 else -ratio[k,i])
            k,i=min(candidates,key=score)
            before=out['selected_v'][k,i];s=p[k,i];ih=h[k,i]
            calc=hybrid_step(float(before),float(s),float(ih),.1,*coefficients(.1),NODES32,WEIGHTS32)
            values=np.array([before,s,ih,.1,out['selected_prethreshold_v'][k,i],margin[k,i],(1.+ih)*.1/20.,calc[3],calc[4],calc[5],calc[6],ratio[k,i]])
            rows.append(dict(tick=int(k+first),index=int(i),values=values))
        return rows
    def check_refs(name,refs,expected):
        meta[name]=dict(actual=archive(refs,name+'__actual'),expected=archive(expected,name+'__expected'))
        for rank,row in enumerate(expected):
            ck(name+f':rank{rank}_found',bool(refs['found'][rank])==(row is not None))
            if row is not None:
                ck(name+f':rank{rank}_identity',refs['ticks'][rank]==row['tick'] and refs['graph_indices'][rank]==row['index'])
                # Logs are independently computed with Python libm; compare their
                # floating result separately from the exact retained state fields.
                ck(name+f':rank{rank}_state_and_solver',equal(refs['values'][rank,:11],row['values'][:11]))
                actual,expected=refs['values'][rank,11],row['values'][11]
                ck(name+f':rank{rank}_log_ratio',bool((np.isnan(actual) and np.isnan(expected)) or actual==expected or (np.isfinite(actual) and np.isfinite(expected) and abs(actual-expected)<1e-12)))
    try:
        panel.configure_threads(4)
        n=64;ids=np.arange(100,164,dtype=np.int64);ptr=np.arange(0,(n+1)*3,3,dtype=np.int64)
        target=np.array([(i+j)%n for i in range(n) for j in [1,3,7]],np.int32)
        weight=np.tile(np.array([100.,-46.,0.],np.float32),n)
        selected=np.arange(48,dtype=np.int32);events=np.array([7,19],np.int32);inputs=np.arange(0,n,8,dtype=np.int32)
        u=np.random.default_rng(11).random((120,len(inputs)));prob=np.full(len(inputs),.2)
        meta['fixture']=archive(dict(ids=ids,ptr=ptr,targets=target,weights=weight,selected=selected,events=events,inputs=inputs,u=u,prob=prob),'fixture')
        def create(module,arm,all_selected=False):
            net=module.FactorialNetwork(ids,ptr,target,weight.copy(),arm,inputs,np.arange(n,dtype=np.int32) if all_selected else selected)
            net.s[::3]=20.
            if arm.startswith('H'):net.h[:]=np.resize(np.array([0.,.1,3.,100.]),n)
            return net
        for arm in ['C0','C1','H0','H1']:
            a,b,c,d=[create(m,arm) for m in [legacy,panel,panel,panel]]
            old=a.advance(u,prob,log_selected_events=True)
            default=b.advance(u,prob,log_selected_events=True)
            subset=c.advance(u,prob,log_selected_events=True,event_indices=events)
            empty=d.advance(u,prob,log_selected_events=True,event_indices=[])
            compare(arm+':legacy_output',old,old_fields(default));compare(arm+':legacy_checkpoint',a.checkpoint(),b.checkpoint())
            compare(arm+':subset_checkpoint',b.checkpoint(),c.checkpoint())
            compare(arm+':empty_checkpoint',b.checkpoint(),d.checkpoint())
            compare(arm+':subset_events',default['selected_events'][np.isin(default['selected_events'][:,3],events)],subset['selected_events'])
            ck(arm+':empty_events',len(empty['selected_events'])==0)
            for key in default:
                if key not in ['selected_events','schema']:compare(arm+':subset_'+key,default[key],subset[key])
            ck(arm+':fixed48_trace_population',default['selected_v'].shape==(121,48) and subset['selected_v'].shape==(121,48))
            ck(arm+':complete',default['status']=='complete')
            if arm.startswith('H'):
                oracle=create(legacy,arm,True).advance(u,prob,log_selected_events=True)
                check_refs(arm+':global_refs',default['reference_intervals'],expected_refs(oracle))
                meta[arm+':oracle']=archive(oracle,arm+'__oracle')
            else:ck(arm+':no_h_references',not default['reference_intervals']['found'].any())
            # Change only event selection between chunk boundaries.
            a,b=create(legacy,arm),create(panel,arm)
            for start,end,select in [(0,17,events),(17,61,selected),(61,120,events)]:
                old=a.advance(u[start:end],prob,log_selected_events=True)
                new=b.advance(u[start:end],prob,log_selected_events=True,event_indices=select)
                old['selected_events']=old['selected_events'][np.isin(old['selected_events'][:,3],select)]
                compare(arm+f':chunk{start}_legacy',old,old_fields(new))
            compare(arm+':chunk_final',a.checkpoint(),b.checkpoint())
        # Quiet one/two-tick fixtures give exact ties and ratio domains.
        for kind in ['ties','h0','p0','unavailable','ratio_overflow','unselected_winner']:
            net=create(panel,'H1',True);net.s[:]=0.;net.h[:]=0.;net.v[:]=-52.
            if kind=='ties':net.h[:]=3.
            elif kind=='p0':net.h[5:7]=3.
            elif kind=='unavailable':net.h[5]=1e8;net.last[5]=0;net.h[6]=3.
            elif kind=='ratio_overflow':net.h[5]=1e-300;net.s[5]=1e100;net.h[6]=1e-200;net.s[6]=1e100
            elif kind=='unselected_winner':net.h[60]=1e4;net.s[61]=100.;net.h[61]=1e-200
            before=net.checkpoint()
            old=legacy.FactorialNetwork(ids,ptr,target,weight.copy(),'H1',inputs,np.arange(n,dtype=np.int32))
            for key in ['v','s','h','last','refractory','blocked']:getattr(old,key)[:]=getattr(net,key)
            out=net.advance(u[:2],np.zeros(len(inputs)),log_selected_events=True)
            oracle=old.advance(u[:2],np.zeros(len(inputs)),log_selected_events=True)
            check_refs('fixture:'+kind,out['reference_intervals'],expected_refs(oracle))
            meta['fixture:'+kind+':states']=archive(dict(before=before,output=out,oracle=oracle),'fixture_'+kind)
            if kind=='ties':ck('ties:earliest_tick_lowest_cell',np.array_equal(out['reference_intervals']['graph_indices'],[0,0,0]) and out['reference_intervals']['ticks'][0]==0 and out['reference_intervals']['ticks'][2]==0)
            if kind=='h0':ck('h0:ratio_missing',not out['reference_intervals']['found'][2])
            if kind=='p0':ck('p0:valid_negative_infinity',out['reference_intervals']['found'][2] and out['reference_intervals']['graph_indices'][2]==5 and np.isneginf(out['reference_intervals']['values'][2,11]))
            if kind=='unavailable':ck('unavailable:largest_h_excluded',out['reference_intervals']['graph_indices'][0]==6)
            if kind=='ratio_overflow':ck('ratio:overflow_avoided',out['reference_intervals']['graph_indices'][2]==5 and np.isfinite(out['reference_intervals']['values'][2,11]) and out['reference_intervals']['values'][2,11]>math.log(np.finfo(float).max))
            if kind=='unselected_winner':ck('global:outside_default48',out['reference_intervals']['graph_indices'][0]==60 and out['reference_intervals']['graph_indices'][2]==61)
        # Failure after five completed ticks must not merge attempted-tick refs.
        for arm in ['H0','H1']:
            a,b=create(legacy,arm,True),create(panel,arm,True)
            for net in [a,b]:
                net.s[:]=0.;net.h[:]=0.;net.weights[0]=np.inf
                net.pending_count[5]=1;net._pending[5,0]=0
            old=a.advance(u[:10],np.zeros(len(inputs)),log_selected_events=True)
            new=b.advance(u[:10],np.zeros(len(inputs)),log_selected_events=True,event_indices=events)
            old['selected_events']=old['selected_events'][np.isin(old['selected_events'][:,3],events)]
            old['partial']['selected_events']=old['partial']['selected_events'][np.isin(old['partial']['selected_events'][:,3],events)]
            compare(arm+':failure_legacy',old,old_fields(new));compare(arm+':failure_checkpoint',a.checkpoint(),b.checkpoint())
            ck(arm+':failure_boundary',new['completed_ticks']==5 and new['status']=='failed')
            check_refs(arm+':failure_complete_refs',new['reference_intervals'],expected_refs(old))
            partial=new['reference_intervals']['partial'];ck(arm+':partial_attempt_only',np.all(partial['ticks'][partial['found']]==5))
            # An interval failure at cell5 must exclude speculative later cells.
            a,b=create(legacy,arm,True),create(panel,arm,True)
            for net in [a,b]:net.s[5]=-1.;net.h[60]=1e100
            old=a.advance(u[:2],prob,log_selected_events=True);new=b.advance(u[:2],prob,log_selected_events=True)
            compare(arm+':interval_failure_legacy',old,old_fields(new));compare(arm+':interval_failure_checkpoint',a.checkpoint(),b.checkpoint())
            ck(arm+':no_failed_tick_complete_refs',not new['reference_intervals']['found'].any())
            refs=new['reference_intervals']['partial'];ck(arm+':speculative_failure_refs_excluded',np.all(refs['graph_indices'][refs['found']]<5))
            meta[arm+':interval_failure_refs']=archive(new['reference_intervals'],arm+'__interval_failure_refs')
        for invalid in [[63],[7,7],[-1],[1.5]]:
            net=create(panel,'H1');before=net.checkpoint();denied=False
            try:net.advance(u[:1],prob,event_indices=invalid)
            except ValueError:denied=True
            ck('invalid_event_'+repr(invalid),denied and equal(before,net.checkpoint()))
        ck('threads:four',panel.parallel_runtime_info()['numba_threads']==4)
    except Exception as exc:
        import traceback
        errors.append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    for path,digest in hashes.items():ck('unchanged:'+path,sha(ROOT/path)==digest)
    npz=BASE.with_name(BASE.name+'-arrays.npz');np.savez_compressed(npz,**arrays)
    js=BASE.with_name(BASE.name+'-arrays.json');write(js,meta)
    report=dict(scope='Bounded synthetic panel logging/reference selection checks only',source_sha256=hashes,
        plan_sha256=sha(plan),checks=checks,check_count=len(checks),passed=all(checks.values()) and not errors,
        errors=errors,wall_seconds=time.perf_counter()-began,
        artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [npz,js]},
        runtime=panel.parallel_runtime_info())
    write(receipt,report);print(json.dumps(report,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
