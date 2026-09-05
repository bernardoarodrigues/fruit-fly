#!/usr/bin/env python3
"""Validate the new H saved-data reviewer against retained tiny fixtures only."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,traceback
import numpy as np
import review_inhibitory_recurrent_panel_H as reviewer
from inhibitory_panel_reference_audit import ReferenceAuditError

ROOT=Path(__file__).resolve().parents[1]
STEM=ROOT/'validation/inhibitory-recurrent-panel-H-review-preflight'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def decode(node,z=None):
    if isinstance(node,dict):
        if 'array' in node:return z[node['array']]
        if set(node)=={'nonfinite'}:return float(node['nonfinite'])
        if set(node)=={'dtype','shape','values'}:return np.asarray(decode(node['values']),dtype=node['dtype']).reshape(node['shape'])
        return {k:decode(v,z) for k,v in node.items()}
    if isinstance(node,list):return [decode(v,z) for v in node]
    return node

def main():
    plan_path=Path(str(STEM)+'-plan.json');result_path=Path(str(STEM)+'-results.json');raw_path=Path(str(STEM)+'-arrays.npz')
    if any(p.exists() for p in [plan_path,result_path,raw_path]):raise FileExistsError('Preserve first preflight execution')
    paths=['scripts/check_inhibitory_recurrent_panel_H_review.py','scripts/review_inhibitory_recurrent_panel_H.py',
        'scripts/review_inhibitory_recurrent_panel_trial.py','scripts/inhibitory_panel_reference_audit.py',
        'validation/inhibitory-recurrent-parallel-arrays.json','validation/inhibitory-recurrent-parallel-arrays.npz',
        'validation/inhibitory-recurrent-panel-numerics-review-cases.json','validation/inhibitory-recurrent-panel-plan.json',
        'validation/inhibitory-panel-reference-audit-results.json']
    sources={p:sha(ROOT/p) for p in paths}
    plan=dict(frozen_utc=datetime.now(timezone.utc).isoformat(),source_sha256=sources,
        scope='No network or producer execution. Reconstruct p/h from saved H0/H1 128-cell,300-tick fixtures; validate fixed-reference dispatch on an explicitly mocked retained dispatch fixture using one actual saved scalar input.',
        checks=['Exact p/h arrays for both packages from saved accepted edges and eligibility.',
            'Three global labels deduplicate with a later first-available target; p=0 ratio negative infinity remains eligible.',
            'One actual independent scalar evaluation is cached across two recorded rows.',
            'Changed saved predecessor and missing reference population are detected.',
            'Injected KeyboardInterrupt and structured solver failure preserve exact current inputs and already completed rows/cache.'],
        failure_policy='Retain initial plan, arrays and result even on failure; no retry or source mutation.')
    plan_path.write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
    checks=[];arrays={};evidence={};error=None
    def ck(name,value):checks.append(dict(name=name,passed=bool(value)))
    original=reviewer.evaluate
    try:
        meta=json.loads((ROOT/paths[4]).read_text())
        with np.load(ROOT/paths[5],allow_pickle=False) as z:
            fixture=decode(meta['fixture'],z);selected=fixture['selected'];weights=fixture['weights']
            for arm in ['H0','H1']:
                out=decode(meta[arm+':full_output']['serial'],z);accepted=[[] for _ in range(300)]
                cols={int(v):i for i,v in enumerate(selected)}
                for tick,src,edge,target,status in out['selected_events']:
                    if status==0:accepted[int(tick)].append((cols[int(target)],float(weights[edge])))
                p,h=reviewer.reconstruct_h_states(out['selected_s'][0],out['selected_h'][0],out['selected_available'],out['selected_fired'],accepted,int(arm[1]),float(np.exp(-.1/5.)))
                ck(arm+'_p_exact',reviewer.exact(p,out['selected_s'][1:]));ck(arm+'_h_exact',reviewer.exact(h,out['selected_h'][1:]))
                ck(arm+'_exercises_available_unavailable_and_firing',out['selected_available'].any() and (~out['selected_available']).any() and out['selected_fired'].any())
                ck(arm+'_accepted_positive_and_negative_edges',any(w>0 for row in accepted for _,w in row) and any(w<0 for row in accepted for _,w in row))
                arrays[arm+'_reconstructed_p']=p;arrays[arm+'_reconstructed_h']=h
        case=decode(json.loads((ROOT/paths[6]).read_text())['dedup_and_later_targets']);out=case['input'];out['end_tick']=104;out['reference_intervals']['partial']=None;out['panel_reference_checks']=case['rows']
        tolerances=json.loads((ROOT/paths[7]).read_text())['tolerances_mv'];selected=np.array([7,19],np.int32)
        A=reviewer.Audit();cache={};rows=[]
        reviewer.audit_references(A,out,selected,selected,cache,rows,tolerances,0,64)
        ck('saved_reference_fixture_checks',not A.failures);ck('two_rows_one_actual_reference_evaluation',len(rows)==2 and len(cache)==1)
        ck('first_available_ticks_retained',[int(row[1]) for row in rows]==[102,103])
        arrays['independent_reference_rows']=np.asarray(rows,np.float64)
        evidence['reference_fixture_categories']=A.categories
        bad=copy.deepcopy(out);bad['panel_reference_checks'][0]['v']+=1
        B=reviewer.Audit();reviewer.audit_references(B,bad,selected,selected,cache,[],tolerances,0,64)
        ck('changed_recorded_predecessor_detected',any(f['check']=='saved_reference_exact_precedent' for f in B.failures))
        bad=copy.deepcopy(out);bad['panel_reference_checks'].pop();B=reviewer.Audit()
        try:reviewer.audit_references(B,bad,selected,selected,cache,[],tolerances,0,64)
        except ValueError:ck('missing_reference_population_rejected',True)
        else:ck('missing_reference_population_rejected',False)
        # A second fixture invocation with a distinct before-v tuple forces a new
        # helper call, after the successful two-row/cache evidence above exists.
        bad=copy.deepcopy(out);bad['reference_intervals']['values'][:,0]+=1;bad['selected_v']+=1
        for row in bad['panel_reference_checks']:row['v']+=1
        for kind in ['interrupt','solver_failure']:
            def fail(*args):
                if kind=='interrupt':raise KeyboardInterrupt('deliberate saved-row preflight interruption')
                raise ReferenceAuditError(dict(inputs=dict(zip(['v','p','h','dt'],args)),method='time_domain_ode',partial=dict(quad_v=-52.,order64_v=-52.),error_type='RuntimeError',message='deliberate preflight failure',traceback='injected'))
            reviewer.evaluate=fail;B=reviewer.Audit();saved_rows=copy.deepcopy(rows);saved_cache=cache.copy()
            try:reviewer.audit_references(B,bad,selected,selected,saved_cache,saved_rows,tolerances,1,64)
            except (KeyboardInterrupt,ReferenceAuditError) as exc:
                context=B.current_reference
                ck(kind+'_exact_context',context['chunk']==1 and context['tick']==102 and context['index']==7 and context['inputs']==[-51.,0.,3.,.1])
                ck(kind+'_completed_results_preserved',saved_rows==rows and saved_cache==cache and len(saved_rows)==2 and len(saved_cache)==1)
                ck(kind+'_failed_status',context['status']==('interrupted' if kind=='interrupt' else 'failed'))
                ck(kind+'_structured_context',context['helper_record'] is None if kind=='interrupt' else context['helper_record']['method']=='time_domain_ode' and 'quad_v' in context['helper_record']['partial'])
                evidence[kind]=context
            else:ck(kind+'_raised',False)
    except (Exception,KeyboardInterrupt) as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    finally:reviewer.evaluate=original
    for p,h in sources.items():ck('source_unchanged:'+p,sha(ROOT/p)==h)
    np.savez_compressed(raw_path,**arrays)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(plan_path),source_sha256=sources,passed=error is None and all(c['passed'] for c in checks),checks=checks,error=error,evidence=evidence,
        arrays=dict(path=str(raw_path.relative_to(ROOT)),bytes=raw_path.stat().st_size,sha256=sha(raw_path)),
        limits=['The dispatch fixture is intentionally mocked and is not a physical trajectory. Only its single saved scalar input was evaluated.',
            'The p/h checks inspect retained fixture events and states. They do not generate or rerun spikes.',
            'Injected interruption checks exercise reference-boundary retention; no process signal, archive failure or live full trial was tested.'])
    result_path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(passed=result['passed'],checks=len(checks),failed=[c for c in checks if not c['passed']],error=error),indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
