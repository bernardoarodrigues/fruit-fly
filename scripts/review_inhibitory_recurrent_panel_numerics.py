#!/usr/bin/env python3
"""Worker source and tiny reference-dispatch review; never execute a network."""
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import hashlib
import inspect
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import experiment_inhibitory_recurrent_panel as worker
BASE=ROOT/'validation/inhibitory-recurrent-panel-numerics-review'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(x):
    if isinstance(x,np.ndarray):return dict(dtype=str(x.dtype),shape=list(x.shape),values=safe(x.tolist()))
    if isinstance(x,np.generic):x=x.item()
    if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v) for v in x]
    if isinstance(x,float) and not np.isfinite(x):return dict(nonfinite=repr(x))
    return x

def main():
    checks={};cases={}
    def ck(n,v):checks[n]=bool(v)
    frozen=json.loads((ROOT/'validation/inhibitory-factorial-solver-results.json').read_text())
    one=next(c for c in frozen['cases'] if c['case']['v']==-52 and c['case']['p']==0 and c['case']['h']==3 and c['case']['dt']==.1)
    pv=one['production'][0]
    tol=dict(production_vs_quad=1e-8,order32_vs64=1e-8,ode_vs_quad=2e-8,quad_error_estimate=1e-9)
    selected=np.array([7,19],np.int32);targets=selected.copy()
    def fixture(unique=False):
        values=np.tile(np.array([-52.,0.,3.,.1,pv,abs(pv+45),(1+3)*.1/20,*one['production'][3:5],one['production'][5],one['production'][6],-np.inf]),(3,1))
        return dict(start_tick=100,completed_ticks=4,
            reference_intervals=dict(found=np.ones(3,bool),ticks=np.array([101,102,103] if unique else [102]*3,np.int64),graph_indices=np.array([55,7,19] if unique else [7]*3,np.int32),values=values),
            selected_available=np.array([[False,False],[False,False],[True,False],[True,True]],bool),
            selected_v=np.full((5,2),-52.),selected_s=np.zeros((5,2)),selected_h=np.full((5,2),3.),selected_prethreshold_v=np.full((4,2),pv))
    def mock_run(out,which=None,error=None,accuracy=False):
        call_counts=dict(q=0,ode=0,high=0)
        def call(name,result):
            def f(*args):
                call_counts[name]+=1
                if name==which and call_counts[name]==2:raise error
                return result
            return f
        q=(pv+1e-6,0.) if accuracy else (pv,0.)
        with patch.object(worker,'hybrid_reference',side_effect=call('q',q)),patch.object(worker,'ode_reference',side_effect=call('ode',(pv,'MOCK',0))),patch.object(worker,'hybrid_step',side_effect=call('high',one['production'])):
            result=worker.reference_checks(out,selected,targets,'H1',tol)
        return result,call_counts
    out=fixture();result,calls=mock_run(out)
    ck('deduplicated_two_records',len(result)==2)
    ck('all_global_and_target_selection_reasons',result[0]['selection']==['global:0','global:1','global:2','target_first_available'])
    ck('first_available_target_rows',[(q['tick'],q['index']) for q in result]==[(102,7),(103,19)])
    ck('dedup_once_per_method',calls==dict(q=2,ode=2,high=2))
    ck('mock_success_all_pass',all(q['passed'] for q in result))
    cases['dedup_and_later_targets']=dict(input=out,rows=result,calls=calls)
    for method,label in [('q','adaptive_quadrature'),('ode','independent_ode'),('high','order64')]:
        result,calls=mock_run(fixture(True),method,ValueError('deliberate reference failure'))
        ck(method+':prior_result_retained',result[0]['passed'] and result[0]['index']==55)
        ck(method+':failed_identity_state',result[1]['tick']==102 and result[1]['index']==7 and result[1]['v']==-52. and result[1]['p']==0 and result[1]['h']==3.)
        ck(method+':failed_method_and_error',result[1]['method_in_progress']==label and result[1]['error']['type']=='ValueError' and not result[1]['passed'])
        ck(method+':later_unattempted',result[2]['not_attempted_after_failure'] is True and not result[2]['passed'])
        if method!='q':ck(method+':earlier_method_values_retained',result[1]['quad_v']==pv)
        if method=='high':ck(method+':ode_value_retained',result[1]['ode_v']==pv)
        cases[method+'_failure']=dict(rows=result,calls=calls)
    result,calls=mock_run(fixture(True),'ode',KeyboardInterrupt('deliberate interrupt'))
    ck('interrupt:failed_row_retained',result[1]['error']['type']=='KeyboardInterrupt' and not result[1]['passed'] and result[2]['not_attempted_after_failure'])
    cases['reference_interrupt']=dict(rows=result,calls=calls)
    result,calls=mock_run(fixture(True),accuracy=True)
    ck('numerical_gate_failure_stops_later_refs',not result[0]['passed'] and result[0]['production_quad_error']>tol['production_vs_quad'] and all(q['not_attempted_after_failure'] for q in result[1:]))
    cases['accuracy_gate_failure']=dict(rows=result,calls=calls)
    empty=fixture();empty['reference_intervals']['found'][:]=False;empty['selected_available'][:]=False
    result,calls=mock_run(empty)
    ck('no_available_reference_no_calls',result==[] and not any(calls.values()))
    with patch.object(worker,'hybrid_reference',side_effect=AssertionError('C must not reference')):
        ck('C_arm_no_H_references',worker.reference_checks(fixture(),selected,targets,'C0',tol)==[])
    # Three scalar reference methods are evaluated once on a previously saved
    # frozen scalar input; there is no network, threshold/reset or new spike.
    real=fixture();real['reference_intervals']['found'][1:]=False;real['selected_available'][:]=False
    result=worker.reference_checks(real,selected,targets,'H1',tol)
    ck('real_frozen_scalar_reference_pass',len(result)==1 and result[0]['passed'])
    ck('real64_preserves_frozen_result',result[0]['order64_v']==one['order64_mv'])
    cases['one_saved_scalar_input']=dict(frozen_case=one,row=result)
    # Arithmetic verification of source queue boundaries and merged old bins.
    ticks=np.array([0,1,18,19,31,31,32],np.int64);indices=np.array([0,1,2,3,1,4,5],np.int32);end=32
    mask=ticks>=end-18;slot=(ticks[mask]+18)%19
    queued=[indices[mask][slot==s] for s in range(19)]
    explicit=[indices[(ticks+18>=end)&((ticks+18)%19==s)] for s in range(19)]
    ck('own_pending_boundary_formula',all(np.array_equal(a,b) for a,b in zip(queued,explicit)))
    ck('zero_rate_off_all_conditions',all((json.loads((ROOT/'validation/or42a-summary-plan.json').read_text())['conditions'][c]+[0.])[-1]==0 for c in worker.CONDITIONS))
    ck('C0_merged_window_edges',np.array_equal(worker.EDGES[:5],[0,500,5000,10000,15000]))
    ck('event_audit_ranges_chunk_aligned',all(a%50==b%50==0 for a,b in worker.AUDIT_RANGES))
    paths=[Path(worker.__file__),ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'validation/inhibitory-factorial-solver-results.json',Path(__file__)]
    hashes={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths}
    data=BASE.with_name(BASE.name+'-cases.json');data.write_text(json.dumps(safe(cases),indent=2,allow_nan=False)+'\n')
    receipt=dict(completed_utc=datetime.now(timezone.utc).isoformat(),scope='Independent worker source review, mock-only reference dispatch and one saved scalar interval reference comparison; no neural network or full graph executed',
        inputs=hashes,reference_function_sha256=hashlib.sha256(inspect.getsource(worker.reference_checks).encode()).hexdigest(),
        passed=all(checks.values()),check_count=len(checks),checks=checks,
        cases=dict(path=str(data.relative_to(ROOT)),bytes=data.stat().st_size,sha256=sha(data)),
        limits=['Not an executed trial or whole-panel validation.','Global H numerical references are fixed samples, not a full network reference integration.','Mock arrays test dispatch and retention, not a physical multi-tick trajectory.','Raw kernel failure intervals remain raw evidence; reference_checks examines completed-prefix reference samples only.','Threshold margin within measured reference error is reported unresolved, not promoted as timing robustness.'])
    p=BASE.with_name(BASE.name+'.json');p.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=receipt['passed'],checks=len(checks),failed=[k for k,v in checks.items() if not v],runner_sha256=hashes[str(Path(worker.__file__).relative_to(ROOT))]['sha256'],receipt_sha256=sha(p)),indent=2))
    return 0 if receipt['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
