#!/usr/bin/env python3
"""Fixed sensitivity screen, not a fit to make the fly move or forage."""
from dataclasses import asdict, replace
from pathlib import Path
import argparse
import json
import platform
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome
from fruitfly.conductance import ConductanceNetwork, ConductanceParameters, ConductanceDrive
from fruitfly.neural import LIFNetwork, SparseDrive


def run_condition(graph, parameters, duration_ms, off_ms, left_hz=150, right_hz=150, *, shiu=False):
    brain = LIFNetwork.from_connectome(graph,seed=42) if shiu else ConductanceNetwork.from_connectome(graph,parameters=parameters,seed=42)
    left=graph.select(['ORN_DM1','ORN_DM4'],side='L')
    right=graph.select(['ORN_DM1','ORN_DM4'],side='R')
    sources=np.concatenate([left,right])
    rates=np.repeat([left_hz,right_hz],[len(left),len(right)])
    motor=graph.select(['DNg97','DNp09','DNa01','DNa02','DNb05','DNb06','DNg13','DNg34','DNg100','DNg75'])
    outputs=np.unique(np.concatenate([sources,motor]))
    brain.advance(.1,outputs=[])
    brain.reset(seed=42)
    counts=np.zeros(brain.n_neurons,dtype=np.int64)
    vmin,vmax=float('inf'),float('-inf')
    motor_v=np.zeros(len(motor))
    phases=[]
    for phase,ms,stimulus_rates in [('stimulus',duration_ms,rates),('offset',off_ms,np.zeros_like(rates))]:
        totals=edges=0
        phase_counts=np.zeros(brain.n_neurons,dtype=np.int64)
        t0=perf_counter()
        for tick in range(round(ms)):
            drive=SparseDrive(sources,rates_hz=stimulus_rates) if shiu else ConductanceDrive(sources,rates_hz=stimulus_rates)
            activity=brain.advance(1,drive=drive,outputs=outputs)
            phase_counts += np.bincount(activity.indices,minlength=brain.n_neurons)
            totals+=activity.total_spikes
            edges+=activity.traversed_edges
            vmin=min(vmin,float(brain.voltage_mv.min()))
            vmax=max(vmax,float(brain.voltage_mv.max()))
            if phase=='stimulus': motor_v+=brain.voltage_mv[motor]
        phases.append({'phase':phase,'duration_ms':ms,'network_spikes':totals,'traversed_edges':edges,
                       'wall_seconds':perf_counter()-t0,
                       'sensory_output_mean_hz':float(phase_counts[sources].mean()*1000/ms),
                       'motor_readouts':[{'body_id':int(graph.neuron_ids[i]),'type':graph.neurons.type.iloc[i],
                                          'side':graph.neurons.somaSide.iloc[i],'rate_hz':float(phase_counts[i]*1000/ms)} for i in motor]})
        counts+=phase_counts
    return {'backend':'shiu-current-lif' if shiu else 'conductance-lif-v1',
            'parameters':asdict(brain.parameters),'seed':42,'left_input_event_hz':left_hz,'right_input_event_hz':right_hz,
            'input_neurons':len(sources),'input_neuron_ids':graph.neuron_ids[sources].tolist(),
            'voltage_min_mv':vmin,'voltage_max_mv':vmax,'all_voltages_finite':bool(np.isfinite(brain.voltage_mv).all()),
            'inside_reversal_bounds':None if shiu else bool(vmin>=parameters.inhibitory_reversal_mv-1e-9 and vmax<=parameters.excitatory_reversal_mv+1e-9),
            'mean_motor_voltage_during_stimulus':[{'body_id':int(graph.neuron_ids[i]),'mean_mv':float(v/duration_ms)} for i,v in zip(motor,motor_v)],
            'phases':phases}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-ms',type=int,default=100)
    parser.add_argument('--off-ms',type=int,default=100)
    parser.add_argument('--output',type=Path,default=Path('validation/conductance-calibration.json'))
    parser.add_argument('--only',nargs='+',help='Run only these named sensitivity conditions')
    parser.add_argument('--skip-shiu',action='store_true')
    parser.add_argument('--voltage-method',choices=['exponential','pade22'],default='exponential')
    args=parser.parse_args()
    if min(args.duration_ms,args.off_ms)<=0: parser.error('Both phases must be positive integer milliseconds')
    graph=Connectome.load('data/processed/malecns_v1',verify=True)
    base=ConductanceParameters(voltage_method=args.voltage_method)
    # Prespecified sensitivity choices; no target trajectories or behavior scores.
    conditions=[('default',base,150,150)]
    conditions += [(f'global_gain_{gain}',replace(base,excitatory_gain=gain,inhibitory_gain=gain),150,150) for gain in [.1,.25,.5]]
    conditions += [(f'inhibitory_reversal_{rev}',replace(base,inhibitory_reversal_mv=rev),150,150) for rev in [-80,-70,-65]]
    conditions += [(f'inhibitory_gain_{gain}',replace(base,inhibitory_gain=gain),150,150) for gain in [.25,.5,2]]
    conditions += [(f'excitatory_gain_{gain}',replace(base,excitatory_gain=gain),150,150) for gain in [.25,.5]]
    conditions += [(f'resting_{rest}',replace(base,resting_mv=rest,reset_mv=rest),150,150) for rest in [-60,-65]]
    conditions += [('default_left150_right5',base,150,5),('default_left5_right150',base,5,150)]
    if args.only:
        unknown=set(args.only)-{condition[0] for condition in conditions}
        if unknown: parser.error(f'Unknown condition names: {sorted(unknown)}')
        conditions=[condition for condition in conditions if condition[0] in args.only]
    result={'purpose':'Prespecified neural parameter sensitivity, not biological fit or motor policy optimization',
            'dataset':'male-cns:v1.0','neurons':len(graph.neuron_ids),'edges':len(graph.targets),
            'platform':platform.platform(),'input_semantics':'Conductance backend rates are excitatory presynaptic event rates; actual ORN output rates are reported separately. Shiu uses original voltage stimulation.',
            'conditions':[]}
    if not args.skip_shiu:
        result['conditions'].append({'name':'shiu_reference',**run_condition(graph,None,args.duration_ms,args.off_ms,shiu=True)})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    for name,parameters,left,right in conditions:
        value={'name':name,**run_condition(graph,parameters,args.duration_ms,args.off_ms,left,right)}
        result['conditions'].append(value)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        phase=value['phases'][0]
        print(name,'vmin',round(value['voltage_min_mv'],2),'spikes',phase['network_spikes'],
              'wall',round(phase['wall_seconds'],2),
              'motor',[(r['type'],r['side'],r['rate_hz']) for r in phase['motor_readouts'] if r['type'] in ['DNg97','DNa01','DNa02','DNb05','DNg34']],flush=True)
    result['completed']=True
    result['selected_parameter_set']=None
    result['interpretation']='Conductance bounds are numerical evidence only; no parameter set selected for behavior. Short single-seed conditions are diagnostics, not measured fly responses.'
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
