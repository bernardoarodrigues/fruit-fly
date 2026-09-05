#!/usr/bin/env python3
"""Bounded six-cell synthetic checks; never loads a connectome or body."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.neural import LIFNetwork, SparseDrive
from inhibitory_recurrent_kernel import FactorialNetwork
from experiment_or42a_summary import arrival_uniforms


def main():
    ids = np.arange(100,106,dtype=np.int64)
    ptr = np.array([0,3,4,5,5,6,6],np.int64)
    targets = np.array([1,2,3,0,1,1],np.int32)
    weights = np.array([1e5,-23.,0.,23.,-23.,23.],np.float32)
    inputs = np.array([0,4],np.int32)
    selected = np.arange(6,dtype=np.int32)
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
    def create(arm):
        return FactorialNetwork(ids,ptr,targets,weights,arm,inputs,selected)
    reference = LIFNetwork(ids,ptr,targets,weights,seed=11)
    shadow = reference._rng_state.copy()
    u = arrival_uniforms(shadow,300,2)
    probabilities = np.array([1.,1.])
    original = reference.advance(30.,drive=SparseDrive(inputs,rates_hz=10000.))
    check("reference_rng_exact",np.array_equal(reference._rng_state,shadow))
    outputs = {}
    for arm in ["C0","C1","H0","H1"]:
        net = create(arm)
        out = net.advance(u,probabilities,log_selected_events=True)
        outputs[arm] = out
        check(arm+":complete",out['status']=='complete' and net.tick==300)
        check(arm+":event_partition",np.array_equal(out['per_tick']['edge_counts'][:,0],out['per_tick']['edge_counts'][:,1]+out['per_tick']['edge_counts'][:,2]))
        check(arm+":zero_weight_edges_counted",out['per_tick']['edge_counts'][:,1,1].sum()>0)
        check(arm+":direct_candidates_exact",np.array_equal(out['candidate'],u<probabilities))
        fired=np.zeros_like(out['candidate'])
        for j,source in enumerate(inputs):
            fired[out['spike_ticks'][out['spike_indices']==source],j]=True
        check(arm+":direct_same_tick_rejection",np.array_equal(out['applied'],out['candidate']&~fired))
        check(arm+":distinct_target_eligibility_masks",np.array_equal(out['selected_direct_available'],out['selected_available']&~out['selected_fired']) and np.array_equal(out['selected_synaptic_available'],np.ones_like(out['selected_available']) if arm.endswith('1') else out['selected_direct_available']))
        pre=out['selected_prethreshold_v'];external=pre.copy()
        for j,source in enumerate(inputs):
            external[:,source]+=out['applied'][:,j]*68.75
        for phase,matrix in enumerate([pre,external,out['selected_v'][1:]]):
            check(arm+f":phase{phase}_minmax",np.array_equal(matrix.min(axis=1),out['per_tick']['phase_min_mv'][:,phase]) and np.array_equal(matrix.max(axis=1),out['per_tick']['phase_max_mv'][:,phase]))
            check(arm+f":phase{phase}_ids",np.array_equal(matrix.argmin(axis=1),out['per_tick']['phase_min_index'][:,phase]) and np.array_equal(matrix.argmax(axis=1),out['per_tick']['phase_max_index'][:,phase]))
        check(arm+":delay_first19",out['selected_events'][:,0].min()==19)
        events=out['selected_events']
        for status,countrow in [(0,1),(1,2),(2,3)]:
            count=np.zeros((300,3),np.int64)
            for tick,source,edge,target,disposition in events:
                if disposition==status:
                    sign=0 if weights[edge]<0 else (2 if weights[edge]>0 else 1)
                    count[tick,sign]+=1
            check(arm+f":logged_disposition{status}_counts",np.array_equal(count,out['per_tick']['edge_counts'][:,countrow]))
        ck=net.checkpoint();arrival=out['spike_ticks']+18
        pending=[out['spike_indices'][(arrival>=300)&(arrival%19==slot)] for slot in range(19)]
        check(arm+":pending_count_order",np.array_equal(ck['pending_count'],[len(row) for row in pending]) and np.array_equal(ck['pending'],np.concatenate(pending)))
        check(arm+":positive_states_or_canonical",np.all(net.h>=0) and (np.all(net.s>=0) if arm.startswith('H') else np.all(net.h==0)))
        if arm.endswith('1'):
            check(arm+":no_refractory_synapse_rejection",not out['per_tick']['edge_counts'][:,2].any())
        else:
            check(arm+":refractory_rejections_present",out['per_tick']['edge_counts'][:,2].sum()>0)
        if arm=='C0':
            check("C0:original_ordered_spikes",np.array_equal(out['spike_indices'],original.indices) and np.array_equal(out['spike_ticks']*.1,original.times_ms))
            r=reference.state_dict()
            for name,key in [('v','voltage_mv'),('s','synaptic_mv'),('last','last_spike_tick'),('refractory','refractory_ticks'),('blocked','ablated'),('pending_count','pending_count'),('pending','pending')]:
                check('C0:original_'+name,np.array_equal(ck[name],r[key]))
        chunked=create(arm);parts=[]
        for first,end in [(0,7),(7,71),(71,300)]:
            parts.append(chunked.advance(u[first:end],probabilities,log_selected_events=True))
        for key in ['v','s','h','last','refractory','blocked','pending_count','pending']:
            check(arm+':chunk_'+key,np.array_equal(ck[key],chunked.checkpoint()[key]))
        check(arm+':chunk_spikes',np.array_equal(np.concatenate([p['spike_indices'] for p in parts]),out['spike_indices']) and np.array_equal(np.concatenate([p['spike_ticks'] for p in parts]),out['spike_ticks']))
        check(arm+':chunk_selected_trace',np.array_equal(np.concatenate([parts[0]['selected_v']]+[p['selected_v'][1:] for p in parts[1:]]),out['selected_v']))
        quiet=create(arm);z=quiet.advance(u[:30],np.zeros(2))
        check(arm+':zero_input',len(z['spike_indices'])==0 and np.all(quiet.v==-52) and not quiet.s.any() and not quiet.h.any())
        delayed=create(arm)
        delayed.advance(u[:2],np.array([1.,0.]))
        delayed.blocked[0]=True
        block=delayed.advance(u[2:20],np.zeros(2),log_selected_events=True)
        check(arm+':block_at_delivery',np.array_equal(block['per_tick']['edge_counts'].sum(axis=0)[3],[1,1,1]) and not block['per_tick']['edge_counts'][:,0].any())
        check(arm+':block_keeps_source_spike',len(delayed.checkpoint()['pending'])==0 and delayed.last[0]==1)
    # Excitation-only kernels coincide exactly across voltage factors.
    for package in [0,1]:
        nets=[FactorialNetwork(ids,ptr,targets,np.abs(weights),arm,inputs,selected) for arm in ['C'+str(package),'H'+str(package)]]
        pair=[n.advance(u,probabilities) for n in nets]
        check(f'package{package}:excitation_only_bitwise',all(np.array_equal(pair[0][k],pair[1][k]) for k in ['spike_indices','spike_ticks','selected_v','selected_s','candidate','applied']))
    fail=create('H1');prefix=fail.advance(u[:5],np.zeros(2));fail.h[2]=np.nan
    error=fail.advance(u[:5],np.zeros(2))
    check('failure:explicit_partial',error['status']=='failed' and error['completed_ticks']==0 and error['end_tick']==5 and not error['coherent_state'] and error['failure']['phase']=='partial_integration' and error['failure']['cell_index']==2 and error['failure']['completed_prefix_end_tick']==5 and error['failure']['last_completed_transition_tick']==4)
    check('failure:state_and_prefix_retained',fail.tick==5 and prefix['completed_ticks']==5 and np.isnan(fail.checkpoint()['h'][2]) and error['partial'] is not None)
    try:
        fail.advance(u[:1],np.zeros(2));denied=False
    except RuntimeError:
        denied=True
    check('failure:continuation_denied',denied)
    bad=create('C0');before=bad.checkpoint()
    try:
        bad.advance(np.array([[np.nan,0.]]),np.zeros(2));denied=False
    except ValueError:
        denied=True
    check('invalid_input:reject_before_mutation',denied and bad.tick==0 and np.array_equal(bad.v,before['v']))
    paths=[Path(__file__),ROOT/'scripts/inhibitory_recurrent_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'fruitfly/neural.py']
    report={'scope':'Synthetic six-cell recurrent graph only; no connectome/body loaded','checks':checks,'check_count':len(checks),'passed':all(checks.values()),'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    print(json.dumps(report,indent=2,allow_nan=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
