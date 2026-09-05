#!/usr/bin/env python3
"""Real-graph timestep/method comparison with exactly shared external events."""
from dataclasses import asdict,replace
from pathlib import Path
import json
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome
from fruitfly.conductance import ConductanceNetwork,ConductanceParameters,SynapticEvents


def main():
    graph=Connectome.load('data/processed/malecns_v1',verify=True)
    sources=graph.select(['ORN_DM1','ORN_DM4'])
    motor=graph.select(['DNg97','DNp09','DNa01','DNa02','DNb05','DNg34'])
    duration_ms,stimulus_ms,coupling_ms=100,50,5
    # Common event grid aligns all neural steps. Identical input events, not
    # merely equal RNG seeds with different numbers of random draws per dt.
    event_grid_ms=.2
    rng=np.random.default_rng(42)
    ticks,channels=np.nonzero(rng.random((round(stimulus_ms/event_grid_ms),len(sources))) < 150*event_grid_ms/1000)
    event_times=ticks*event_grid_ms
    event_indices=sources[channels]
    result={'purpose':'Full graph numerical method/timestep sensitivity with identical external synaptic events',
            'dataset':'male-cns:v1.0','neurons':len(graph.neuron_ids),'edges':len(graph.targets),
            'duration_ms':duration_ms,'stimulus_ms':stimulus_ms,'coupling_ms':coupling_ms,
            'external_event_grid_ms':event_grid_ms,'external_event_rate_hz':150,'external_event_count':len(ticks),
            'input_ids':graph.neuron_ids[sources].tolist(),'seed':42,'conditions':[]}
    snapshots={}
    for method in ['exponential','pade22']:
        for dt in [.2,.1,.05]:
            params=replace(ConductanceParameters(),voltage_method=method,dt_ms=dt)
            brain=ConductanceNetwork.from_connectome(graph,parameters=params,seed=42)
            brain.advance(dt,outputs=[])
            brain.reset(seed=42)
            total_spikes=edges=0
            motor_counts=np.zeros(len(motor),dtype=np.int64)
            t0=perf_counter()
            for start in range(0,duration_ms,coupling_ms):
                keep=(event_times>=start)&(event_times<start+coupling_ms)
                events=SynapticEvents(event_indices[keep],event_times[keep],1)
                batch=brain.advance(coupling_ms,events=events,outputs=motor)
                total_spikes+=batch.total_spikes
                edges+=batch.traversed_edges
                motor_counts+=batch.counts(motor)
            wall=perf_counter()-t0
            label=f'{method}_dt_{dt}'
            snapshots[label]=(brain.voltage_mv.copy(),brain.excitatory_g.copy(),brain.inhibitory_g.copy())
            row={'name':label,'parameters':asdict(params),'wall_seconds':wall,'network_spikes':total_spikes,
                 'traversed_edges':edges,'voltage_min_mv':float(brain.voltage_mv.min()),'voltage_max_mv':float(brain.voltage_mv.max()),
                 'motor_counts':[{'body_id':int(graph.neuron_ids[i]),'type':graph.neurons.type.iloc[i],
                                  'side':graph.neurons.somaSide.iloc[i],'count':int(count)} for i,count in zip(motor,motor_counts)]}
            result['conditions'].append(row)
            print(label,'wall',round(wall,3),'spikes',total_spikes,'motor',motor_counts.tolist(),flush=True)
    reference=result['conditions'][2]
    reference_state=snapshots[reference['name']]
    for row in result['conditions']:
        current=snapshots[row['name']]
        row['relative_total_spike_count_difference_vs_exponential_dt005']=abs(row['network_spikes']-reference['network_spikes'])/max(1,reference['network_spikes'])
        row['final_voltage_rmse_vs_exponential_dt005_mv']=float(np.sqrt(np.mean((current[0]-reference_state[0])**2)))
        row['final_voltage_max_abs_difference_vs_exponential_dt005_mv']=float(np.max(np.abs(current[0]-reference_state[0])))
        if row['parameters']['voltage_method']=='pade22':
            exact=snapshots[f"exponential_dt_{row['parameters']['dt_ms']}"]
            row['voltage_rmse_vs_same_dt_exponential_mv']=float(np.sqrt(np.mean((current[0]-exact[0])**2)))
    result['completed']=True
    result['interpretation']='Shared-event numerical comparison only. Recurrent threshold events can make final-state differences non-monotonic. No biological convergence or parameter fit is inferred.'
    Path('validation/conductance-numerics.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
