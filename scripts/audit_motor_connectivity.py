#!/usr/bin/env python3
"""Diagnose real MaleCNS odor-to-DN activity without changing neural policy."""
from pathlib import Path
import json
import sys
from time import perf_counter

import numpy as np
from numba import njit
from scipy.sparse import csr_matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import Connectome
from fruitfly.neural import LIFNetwork, SparseDrive


@njit(cache=True)
def positive_bfs(indptr, targets, weights, sources):
    distance = np.full(len(indptr) - 1, -1, dtype=np.int32)
    queue = np.empty(len(distance), dtype=np.int32)
    head = tail = 0
    for source in sources:
        distance[source] = 0
        queue[tail] = source
        tail += 1
    while head < tail:
        source = queue[head]
        head += 1
        for edge in range(indptr[source], indptr[source + 1]):
            target = targets[edge]
            if weights[edge] > 0 and distance[target] == -1:
                distance[target] = distance[source] + 1
                queue[tail] = target
                tail += 1
    return distance


def main():
    graph = Connectome.load("data/processed/malecns_v1", verify=True)
    cells = graph.neurons
    brain = LIFNetwork.from_connectome(graph, seed=42)
    selected_types = ["DNg97", "DNp09", "DNa01", "DNa02", "DNb05", "DNb06", "DNg13",
                      "DNg33", "DNp32", "DNp12", "DNg100", "DNg75", "DNg34"]
    selected = graph.select(selected_types)
    orns = graph.select(["ORN_DM1", "ORN_DM4"])
    distance = positive_bfs(graph.indptr, graph.targets, graph.weights, orns)
    incoming = csr_matrix((graph.weights, graph.targets, graph.indptr), shape=(brain.n_neurons, brain.n_neurons)).tocsc()
    all_descending = np.flatnonzero(cells.superclass.eq("descending_neuron"))
    result = {"dataset": "male-cns:v1.0", "graph_sha256": brain.graph_sha256,
              "parameters": {"weight_scale_mv": .275, "seed": 42, "dt_ms": .1,
                             "duration_ms": 500, "state_sampling_interval_ms": 1},
              "input_types": ["ORN_DM1", "ORN_DM4"],
              "input_indices": orns.tolist(), "input_ids": graph.neuron_ids[orns].tolist(),
              "intervention": "none; baseline signed graph unchanged", "targets": [], "conditions": []}
    for index in selected:
        start, end = incoming.indptr[index:index+2]
        pre, weights = incoming.indices[start:end], incoming.data[start:end]
        grouped = {}
        for cell_type, weight in zip(cells.type.iloc[pre].fillna("untyped"), weights):
            grouped[cell_type] = grouped.get(cell_type, 0.0) + float(weight)
        row = cells.iloc[index]
        result["targets"].append({"index": int(index), "body_id": int(row.bodyId), "type": row.type,
                                  "side": row.somaSide, "consensus_nt": row.consensus_nt,
                                  "outgoing_sign": int(row.model_sign),
                                  "positive_edge_shortest_path_from_odor_hops": int(distance[index]),
                                  "incoming_neurons": len(pre),
                                  "excitatory_input_weight_mv": float(weights[weights>0].sum()),
                                  "inhibitory_input_weight_mv": float(weights[weights<0].sum()),
                                  "zero_weight_input_edges": int((weights==0).sum()),
                                  "strongest_presynaptic_types_by_abs_signed_weight": sorted(grouped.items(), key=lambda item: -abs(item[1]))[:20]})
    brain.advance(.1, outputs=[])
    for label, side_rates in [("bilateral_150Hz", (150,150)), ("left150_right5Hz", (150,5)), ("left5_right150Hz", (5,150))]:
        brain.reset(seed=42)
        groups = [graph.select(["ORN_DM1", "ORN_DM4"], side=side) for side in ["L","R"]]
        drive = SparseDrive(np.concatenate(groups), rates_hz=np.repeat(side_rates,[len(group) for group in groups]))
        counts = np.zeros(brain.n_neurons,dtype=np.int64)
        vs,gs=[],[]
        t0=perf_counter()
        for tick in range(500):
            batch=brain.advance(1,drive=drive)
            counts += np.bincount(batch.indices,minlength=brain.n_neurons)
            vs.append(brain.voltage_mv[selected].copy())
            gs.append(brain.synaptic_mv[selected].copy())
        vs,gs=np.asarray(vs),np.asarray(gs)
        records=[]
        for offset,index in enumerate(selected):
            start,end=incoming.indptr[index:index+2]
            pre,weights=incoming.indices[start:end],incoming.data[start:end]
            contribution=weights*counts[pre]/.5
            grouped={}
            for cell_type,value in zip(cells.type.iloc[pre].fillna('untyped'),contribution):
                grouped[cell_type]=grouped.get(cell_type,0.0)+float(value)
            records.append({'body_id':int(cells.bodyId.iloc[index]),'type':cells.type.iloc[index],
                            'side':cells.somaSide.iloc[index],'rate_hz':float(counts[index]/.5),
                            'sampled_v_mean_mv':float(vs[:,offset].mean()),'sampled_v_min_mv':float(vs[:,offset].min()),
                            'sampled_v_max_mv':float(vs[:,offset].max()),'sampled_g_mean_mv':float(gs[:,offset].mean()),
                            'presynaptic_excitatory_weight_times_rate_mv_per_s':float(contribution[weights>0].sum()),
                            'presynaptic_inhibitory_weight_times_rate_mv_per_s':float(contribution[weights<0].sum()),
                            'top_active_presynaptic_types_by_abs_weight_times_rate':sorted(grouped.items(),key=lambda pair:-abs(pair[1]))[:15]})
        top=all_descending[np.argsort(counts[all_descending])[-15:][::-1]]
        condition={'name':label,'rates_by_side_hz':dict(zip(['L','R'],side_rates)),
                   'network_spikes':int(counts.sum()),'wall_seconds':perf_counter()-t0,'readouts':records,
                   'top_descending': [{'body_id':int(cells.bodyId.iloc[i]),'type':cells.type.iloc[i],
                                       'side':cells.somaSide.iloc[i],'rate_hz':float(counts[i]/.5)} for i in top]}
        result['conditions'].append(condition)
        print(label,[(r['type'],r['side'],r['rate_hz'],round(r['sampled_v_mean_mv'],2)) for r in records],flush=True)
    result['caveats']=['Single seed per condition, diagnostic rather than calibrated assay.',
                       'Shortest positive path proves structural reachability only, not activation or causal sign of a multineuron circuit.',
                       'Weight-times-rate sums ignore postsynaptic refractory gating and event timing; they diagnose upstream excitation/inhibition, not exact conductance.',
                       'Voltage and synaptic state sampled each1ms; transients between samples can be missed.',
                       'No source sign or gain was changed to obtain motion.']
    Path('validation/motor-connectivity.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
