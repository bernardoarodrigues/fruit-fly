#!/usr/bin/env python3
"""Manufactured checks; no real-network stimulus outcomes are inspected."""
from pathlib import Path
import json
import traceback
import copy
import numpy as np
from check_navigation_mbon_intervention_kernel import exact,fixture
import kc_gamma_intervention_kernel as mod
from prepare_kc_gamma_contact_mask import record,write,ROOT

OUT=ROOT/'validation/kc-gamma-intervention-kernel-checks.json'
def main():
    if OUT.exists():raise FileExistsError('Preserve first check result')
    checks={};error=None
    def ck(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def rejects(name,fn):
        try:fn()
        except (ValueError,RuntimeError):ck(name,True)
        else:ck(name,False)
    def make(edges=(),values=(),window=None,recurrent=False,base=False):
        ids,ptr,tgt,w,inputs,sel=fixture(recurrent)
        if base:return mod.original.FactorialNetwork(ids,ptr,tgt,w,'H1',inputs,sel,11)
        return mod.GammaContactNetwork(ids,ptr,tgt,w,'H1',inputs,sel,11,modified_edge_indices=edges,retained_weights=values,delivery_window=window)
    try:
        mod.original.configure_threads(1)
        ck('seven single anchor patches',len(mod.DERIVATION)==7)
        for name,edges,values,window in [('empty',[],[],None),('inactive',[0,3],[0.,25.],[1000,1100])]:
            a=make(recurrent=True,base=True);b=make(edges,values,window,True)
            for n in [a,b]:n.s[::3]=20.;n.h[:]=np.resize([0.,.1,3.,100.],12)
            u=np.random.default_rng(12).random((120,3));p=np.array([.35,.2,.4])
            oa=a.advance(u,p,log_selected_events=True);ob=b.advance(u,p,log_selected_events=True)
            ck(name+' every original output byte',exact(oa,ob));ck(name+' full checkpoint',exact(a.checkpoint(),b.checkpoint()))
            ck(name+' no changed delivery',not b.last_contact_intervention['counts'].any())
        # Delayed arrivals at19,21,...; only21 modified, including queued pre-window spikes.
        n=make([1,4],[0.,1.234567890123],[21,23]);u=np.zeros((80,2));p=np.ones(2)
        out=n.advance(u,p,log_selected_events=True)
        events=out['selected_events'];side=n.last_contact_intervention
        changed=events[events[:,4]==3]
        ck('inclusive start exclusive end',len(changed)>0 and np.all(changed[:,0]==21))
        ck('only declared edges',np.isin(changed[:,2],[1,4]).all())
        ck('sidecar count',int(side['counts'].sum())==len(changed))
        ck('accepted counters retain graph deliveries',np.array_equal(out['per_tick']['edge_counts'][:,0],out['per_tick']['edge_counts'][:,1]+out['per_tick']['edge_counts'][:,2]))
        weights=fixture()[3].astype(float);ret={1:0.,4:1.234567890123};b=np.exp(-.1/5.)
        for k in range(80):
            expected_s=out['selected_s'][k]*b;expected_h=out['selected_h'][k]*b;count=np.zeros(2,np.int64);removed=0.
            for tick,source,e,target,disposition in events[events[:,0]==k]:
                if disposition in [1,2]:continue
                w=weights[e]
                if disposition==3:
                    ck(f'disposition declared {k} {e}',e in ret and 21<=k<23)
                    count[int(ret[e]!=0.)]+=1;removed+=w-ret[e];w=ret[e]
                if w<0:expected_h[target]+=-w/23.
                else:expected_s[target]+=w
            ck(f'p event reconstruction {k}',np.allclose(expected_s,out['selected_s'][k+1],atol=2e-13,rtol=0))
            ck(f'h event reconstruction {k}',np.allclose(expected_h,out['selected_h'][k+1],atol=2e-13,rtol=0))
            ck(f'changed counts {k}',np.array_equal(count,side['counts'][k]))
            ck(f'removed sum {k}',removed==side['removed_weight_sum'][k])
        # Chunking and restoration cannot shift delivery-window timing.
        split=make([1,4],[0.,1.234567890123],[21,23]);offset=0
        for length in [20,1,1,1,57]:
            o=split.advance(u[offset:offset+length],p,log_selected_events=True)
            ck(f'chunk exact selected states {offset}',exact(o['selected_s'],out['selected_s'][offset:offset+length+1]) and exact(o['selected_v'],out['selected_v'][offset:offset+length+1]))
            offset+=length
        ck('chunk full checkpoint',exact(n.checkpoint(),split.checkpoint()))
        a=make();a.advance(u[:20],p);cp=a.checkpoint();ids,ptr,tgt,w,_,_=fixture()
        restored=mod.GammaContactNetwork.from_checkpoint(ids,ptr,tgt,w,cp,modified_edge_indices=[1,4],retained_weights=[0.,1.234567890123],delivery_window=[21,23])
        ck('restore exact checkpoint',exact(cp,restored.checkpoint()))
        restored.advance(u[20:],p);ck('restore full endpoint',exact(n.checkpoint(),restored.checkpoint()))
        ck('original weights intact',exact(restored.weights,fixture()[3]))
        blocked=make([1],[0.],[0,80]);blocked.blocked[0]=True;bo=blocked.advance(u,p,log_selected_events=True)
        ck('source block precedes modification',not blocked.last_contact_intervention['counts'].any() and not np.any(bo['selected_events'][:,4]==3))
        for name,edges,vals,window in [('negative edge',[0],[0.],[0,10]),('zero edge',[2],[0.],[0,10]),('negative retained',[1],[-1.],[0,10]),('nonfinite retained',[1],[float('nan')],[0,10]),('no reduction',[1],[9.],[0,10]),('duplicate',[1,1],[0.,1.],[0,10]),('outside',[99],[0.],[0,10]),('missing window',[1],[0.],None),('float tick',[1],[0.],[0.,10]),('empty window',[1],[0.],[10,10])]:
            rejects(name,lambda e=edges,v=vals,w=window:make(e,v,w))
        bad=copy.deepcopy(cp);bad['coherent_state']=False
        rejects('incoherent restore',lambda:restored.restore_checkpoint(bad))
        fail=make([1],[0.],[0,10]);fail.s[0]=float('nan');fo=fail.advance(u[:2],p)
        ck('failure retained',fo['status']=='failed' and fo['partial'] is not None and fail.last_contact_intervention['partial'] is not None)
        rejects('failed network cannot continue',lambda:fail.advance(u[:1],p))
    except Exception:error=traceback.format_exc()
    result=dict(passed=error is None,checks=checks,check_count=len(checks),error=error,inputs=[record(p) for p in [Path(__file__),ROOT/'scripts/kc_gamma_intervention_kernel.py',ROOT/'scripts/navigation_mbon_intervention_kernel.py',ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'scripts/check_navigation_mbon_intervention_kernel.py',ROOT/'scripts/prepare_kc_gamma_contact_mask.py']],source_derivation=mod.source_derivation(),scope='Synthetic graphs; all original inactive outputs and checkpoint bytes, independent delivery-state reconstruction, window/chunk/pending behavior, invalid configuration and partial failure. No biological acceptance.')
    write(OUT,result);print(json.dumps(dict(passed=result['passed'],checks=len(checks),error=error)))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
