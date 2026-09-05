#!/usr/bin/env python3
"""Frozen primary-summary excitation experiment, without runtime/model edits."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.data import Connectome
from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive, _uniform
from fruitfly.sensors import MotorDecoder

PLAN = ROOT / "validation/or42a-summary-plan.json"
REPORT = ROOT / "validation/or42a-summary-experiment.json"
CONDITIONS = {
    "no_input": [0., 0., 0.],
    "constant_baseline": [11., 11., 11.],
    "ethyl_acetate": [11., 149., 11.],
    "isoamyl_acetate": [11., 57.67908699377742, 11.],
    "ethyl_acetate_source_outputs_blocked": [11., 149., 11.],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


@njit(cache=True)
def arrival_uniforms(state, ticks, columns):
    """Read the frozen engine RNG algorithm on a separate state copy."""
    output = np.empty((ticks, columns), dtype=np.float64)
    for tick in range(ticks):
        for column in range(columns):
            output[tick, column] = _uniform(state)
    return output


def groups(graph):
    sources = graph.select(["ORN_VM7d"])
    sources = sources[np.argsort(graph.neuron_ids[sources])]
    first_hop = np.setdiff1d(np.unique(np.concatenate([
        graph.targets[graph.indptr[i]:graph.indptr[i+1]] for i in sources])), sources)
    return sources, first_hop, MotorDecoder(graph)


def create_plan(graph):
    if PLAN.exists():
        raise FileExistsError("Frozen plan already exists; it must not be silently overwritten")
    sources, first_hop, motor = groups(graph)
    primary = json.loads((ROOT / "validation/or42a-primary/results.json").read_text())
    assert primary["suggested_primary_summary_boundary"]["isoamyl_acetate_total_rate_hz"] == CONDITIONS["isoamyl_acetate"][1]
    probe = LIFNetwork.from_connectome(graph, seed=11)
    paths = [Path(__file__), ROOT/"fruitfly/neural.py", ROOT/"fruitfly/data.py", ROOT/"fruitfly/sensors.py",
             ROOT/"validation/or42a-primary/results.json", ROOT/"validation/or42a-primary/male-vm7d-population.csv",
             ROOT/"data/processed/malecns_v1/manifest.json", ROOT/"data/processed/malecns_v1/neurons.feather"]
    plan = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        purpose="Primary-summary EXCITATION events, not an afferent spike clamp or chemical encoder",
        execution="Standalone full male Shiu graph; no body, no runtime changes, trials sequential, fresh state each trial",
        seeds=[11,12,13], duration_ms=1500, sample_interval_ms=5, window_edges_ms=[0,500,1000,1500],
        conditions=CONDITIONS, condition_order=list(CONDITIONS),
        source_body_ids=graph.neuron_ids[sources].tolist(), source_graph_indices=sources.tolist(),
        source_sides=graph.neurons.iloc[sources].rootSide.tolist(), source_nerves=graph.neurons.iloc[sources].entryNerve.tolist(),
        first_hop_body_ids=graph.neuron_ids[first_hop].tolist(),
        motor_groups={k:graph.neuron_ids[v].tolist() for k,v in motor.groups.items()},
        graph_sha256=probe.graph_sha256, neurons=probe.n_neurons, edges=probe.n_edges,
        parameters=asdict(probe.parameters), source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
        drive=dict(rates_explicit_including_zero=True, current_mv=None, poisson_weight_mv=None,
                   disable_refractory=True, ordering="Ascending numeric source body IDs, all36 in every interval and control"),
        rate_caveat="11Hz baseline n17 combined with 138Hz EA delta n13 or raster IA delta46.67908699377742 n13; total rates are cross-summary engineering combinations. DoOR original offset unresolved. IA is a reserved chemical lookup, not a held-out prediction.",
        arrival_accounting="Replay _uniform on a COPY of the pre-block RNG state; verify exact post-block state. Bernoulli rate*dt arrivals. Applied direct voltage events exclude source-fired ticks because zero-refractory source cells are otherwise active. Save both sets separately.",
        synapse_accounting="Existing traversed_edges counts edge visits including inactive postsynaptic targets. Reconstruct each visit from all presynaptic spike times,18-tick delay,outdegree and block flag. Accepted postsynaptic updates are unavailable and not claimed.",
        motor_observation=dict(taste_food=False,taste_water=False),
        motor_caveat="Unrealized decoder diagnostics with synthetic false taste gates, not observed physical behavior",
        frozen_checks=["source_identity_and_exact18per_side_MxLbN", "unchanged_full_graph_and_parameters",
            "all300five_ms_samples_and15000ticks", "finite_neural_state_at_every5ms_boundary",
            "spike_times_within_interval_on_grid", "ordered36inputs_and_zero_refractory",
            "RNG_reconstruction_matches_every_interval", "source_direct_arrivals_partition_into_applied_or_same_tick_spike",
            "delayed_edge_visit_reconstruction_matches_each_interval", "blocked_source_edge_visits_zero",
            "no_input_zero_arrivals_and_zero_spikes", "same_input_arrivals_EA_vs_blocked_per_seed",
            "same_RNG_draw_count_and_final_state_all_conditions_per_seed"],
        non_gates=["Walking/feeding/attraction", "biological voltage range", "source spikes equal excitation events",
                   "monotonic downstream response", "Poisson spike timing or latency matches biology"],
        retention="Plan written before neural advance; progress summary after each trial, per-5ms JSONL and complete NPZ trace in ignored run directory. Exceptions retained without replacement.")
    assert len(sources)==36 and Counter(plan["source_sides"])=={"L":18,"R":18}
    assert set(plan["source_nerves"])=={"MxLbN"}
    assert plan["graph_sha256"]=="e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8"
    save_json(PLAN, plan)
    print(json.dumps({"frozen_plan":str(PLAN),"sha256":sha(PLAN)}),flush=True)


def run_trial(graph, plan, seed, condition, folder):
    folder.mkdir()
    sources, first_hop, motor = groups(graph)
    net = LIFNetwork.from_connectome(graph, parameters=LIFParameters(**plan["parameters"]), seed=seed)
    if condition.endswith("outputs_blocked"):
        net.ablate(sources)
    source_column = np.full(net.n_neurons, -1, dtype=np.int32)
    source_column[sources] = np.arange(len(sources))
    initial_rng = int(net._rng_state[0])
    chunks_i, chunks_t, arrival_t, arrival_c, applied_a = [], [], [], [], []
    counts = np.zeros((3, net.n_neurons), dtype=np.int64)
    samples = []
    checks = {name:True for name in ["clock", "finite_state", "spike_grid", "drive_contract", "rng_reconstruction", "arrivals_partition"]}
    start = time.perf_counter()
    error = None
    with (folder/"samples.jsonl").open("w") as log:
        try:
            for chunk in range(300):
                window = chunk//100
                rate = plan["conditions"][condition][window]
                first_tick = net.tick
                rng_before = int(net._rng_state[0])
                shadow_rng = net._rng_state.copy()
                arrivals = arrival_uniforms(shadow_rng, 50, 36) < rate*.1/1000
                batch = net.advance(5, drive=SparseDrive(sources, rates_hz=rate))
                ticks = np.rint(batch.times_ms/.1).astype(np.int64)
                chunks_i.append(batch.indices.copy()); chunks_t.append(ticks)
                np.add.at(counts[window], batch.indices, 1)
                firing = np.zeros((50,36), dtype=bool)
                columns = source_column[batch.indices]
                is_source = columns >= 0
                firing[ticks[is_source]-first_tick, columns[is_source]] = True
                rows, cols = np.nonzero(arrivals)
                applied = ~firing[rows,cols]
                arrival_t.append(rows+first_tick); arrival_c.append(cols); applied_a.append(applied)
                source_finite = bool(np.all(np.isfinite(net.voltage_mv)) and np.all(np.isfinite(net.synaptic_mv)))
                checks["clock"] &= net.tick==(chunk+1)*50 and net.time_ms==(chunk+1)*5
                checks["finite_state"] &= source_finite
                checks["spike_grid"] &= bool(np.allclose(batch.times_ms,ticks*.1,atol=1e-10,rtol=0) and np.all((ticks>=first_tick)&(ticks<net.tick)))
                checks["drive_contract"] &= bool(np.array_equal(net._previous_drive,sources) and np.all(net.refractory_ticks[sources]==0) and np.all(net._current_mv==0))
                checks["rng_reconstruction"] &= int(shadow_rng[0])==int(net._rng_state[0])
                checks["arrivals_partition"] &= len(rows)==int(applied.sum()+firing[rows,cols].sum())
                command = motor.decode(batch,.005,plan["motor_observation"])
                sample = dict(chunk=chunk,start_tick=first_tick,end_tick=net.tick,window=window,rate_hz=rate,
                    rng_before=rng_before,rng_after=int(net._rng_state[0]),rng_draws=1800,
                    requested_arrivals=len(rows),applied_direct_voltage_arrivals=int(applied.sum()),
                    same_tick_spike_rejected_arrivals=int((~applied).sum()),actual_source_spikes=int(is_source.sum()),
                    all_spikes=batch.total_spikes,actual_edge_visits=batch.traversed_edges,
                    global_voltage_min_mv=float(net.voltage_mv.min()),global_voltage_max_mv=float(net.voltage_mv.max()),
                    source_voltage_min_mv=float(net.voltage_mv[sources].min()),source_voltage_max_mv=float(net.voltage_mv[sources].max()),
                    all_state_finite=source_finite,motor_rates_hz=dict(motor.rates),unrealized_motor_command=command)
                samples.append(sample);log.write(json.dumps(sample,allow_nan=False)+"\n");log.flush()
        except Exception:
            error = traceback.format_exc()
    all_i=np.concatenate(chunks_i) if chunks_i else np.empty(0,dtype=np.int32)
    all_t=np.concatenate(chunks_t) if chunks_t else np.empty(0,dtype=np.int64)
    at=np.concatenate(arrival_t) if arrival_t else np.empty(0,dtype=np.int64)
    ac=np.concatenate(arrival_c) if arrival_c else np.empty(0,dtype=np.int64)
    applied=np.concatenate(applied_a) if applied_a else np.empty(0,dtype=bool)
    delivered_ticks=all_t+net.delay_ticks
    delivered=delivered_ticks<net.tick
    degree=np.diff(graph.indptr)
    edge_visits=np.zeros(len(samples),dtype=np.int64)
    eligible=delivered & ~net.ablated[all_i]
    np.add.at(edge_visits,delivered_ticks[eligible]//50,degree[all_i[eligible]])
    actual_edge_visits=np.array([s["actual_edge_visits"] for s in samples],dtype=np.int64)
    checks["delayed_edge_visit_accounting"] = bool(np.array_equal(edge_visits,actual_edge_visits))
    checks["blocked_source_delivery"] = not condition.endswith("outputs_blocked") or bool(np.all(net.ablated[sources]) and not np.any(eligible & (source_column[all_i]>=0)))
    checks["no_input_silence"] = condition!="no_input" or (len(at)==0 and len(all_i)==0)
    checks["full_graph_parameters"] = net.graph_sha256==plan["graph_sha256"] and asdict(net.parameters)==plan["parameters"]
    checks["completed"] = error is None and len(samples)==300
    source_mask=source_column[all_i]>=0
    np.savez_compressed(folder/"trace.npz", source_body_ids=graph.neuron_ids[sources],
        source_graph_indices=sources,all_spike_graph_indices=all_i,all_spike_ticks=all_t,
        requested_arrival_ticks=at,requested_arrival_source_column=ac,applied_direct_voltage_arrival=applied,
        all_neuron_window_spike_counts=counts,source_spike_ticks=all_t[source_mask],
        source_spike_body_ids=graph.neuron_ids[all_i[source_mask]],
        final_voltage_mv=net.voltage_mv,final_synaptic_mv=net.synaptic_mv,
        initial_rng_state=np.array([initial_rng],dtype=np.uint64),final_rng_state=net._rng_state,
        reconstructed_edge_visits_by5ms=edge_visits,actual_edge_visits_by5ms=actual_edge_visits)
    window_stats=[]
    for window in range(3):
        ss=samples[window*100:(window+1)*100]
        window_stats.append(dict(window=window,requested_hz_per_source=plan["conditions"][condition][window],
            expected_Bernoulli_arrivals=plan["conditions"][condition][window]*.5*36,
            realized_arrivals=sum(s["requested_arrivals"] for s in ss),
            applied_direct_voltage_arrivals=sum(s["applied_direct_voltage_arrivals"] for s in ss),
            actual_source_spikes=int(counts[window,sources].sum()),actual_source_mean_rate_hz=float(counts[window,sources].sum()/36/.5),
            actual_source_counts_by_body_id_order=counts[window,sources].tolist(),
            actual_source_spikes_by_side={side:int(counts[window,sources][graph.neurons.iloc[sources].rootSide.eq(side)].sum()) for side in ["L","R"]},
            non_source_spikes=int(counts[window].sum()-counts[window,sources].sum()),
            first_hop_non_source_spikes=int(counts[window,first_hop].sum()),
            all_spikes=int(counts[window].sum()),motor_group_spikes={k:int(counts[window,v].sum()) for k,v in motor.groups.items()},
            unrealized_motor_command_counts=dict(Counter(s["unrealized_motor_command"]["behavior"] for s in ss)),
            actual_edge_visits=sum(s["actual_edge_visits"] for s in ss),
            sampled_global_min_voltage_mv=min((s["global_voltage_min_mv"] for s in ss),default=None),
            sampled_global_max_voltage_mv=max((s["global_voltage_max_mv"] for s in ss),default=None)))
    result=dict(seed=seed,condition=condition,complete=error is None and len(samples)==300,error=error,
        initial_rng_state=initial_rng,final_rng_state=int(net._rng_state[0]),rng_draws=len(samples)*1800,
        run_dir=str(folder.relative_to(ROOT)),wall_seconds=time.perf_counter()-start,
        requested_arrival_sha256=hashlib.sha256(at.astype('<i8').tobytes()+ac.astype('<i8').tobytes()).hexdigest(),
        actual_source_spike_sha256=hashlib.sha256(all_t[source_mask].astype('<i8').tobytes()+graph.neuron_ids[all_i[source_mask]].astype('<i8').tobytes()).hexdigest(),
        accepted_postsynaptic_updates=None,accepted_postsynaptic_updates_reason="Not exposed by existing engine; edge visits are not accepted updates",
        final_neural_time_ms=net.time_ms,windows=window_stats,checks=checks,
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [folder/"trace.npz",folder/"samples.jsonl"]})
    save_json(folder/"result.json",result)
    return result


def run(graph):
    if REPORT.exists():
        raise FileExistsError("Experiment report exists; preserve original run")
    plan=json.loads(PLAN.read_text())
    for path,expected in plan["source_sha256"].items():
        if sha(ROOT/path)!=expected: raise ValueError(f"Source changed after freezing plan: {path}")
    sources,first_hop,motor=groups(graph)
    assert graph.neuron_ids[sources].tolist()==plan["source_body_ids"]
    assert graph.neuron_ids[first_hop].tolist()==plan["first_hop_body_ids"]
    assert {k:graph.neuron_ids[v].tolist() for k,v in motor.groups.items()}==plan["motor_groups"]
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder=ROOT/"runs"/f"{stamp}-or42a-summary";folder.mkdir()
    report=dict(schema_version=1,plan_sha256=sha(PLAN),run_dir=str(folder.relative_to(ROOT)),complete=False,trials=[])
    save_json(REPORT,report)
    for seed in plan["seeds"]:
        for condition in plan["condition_order"]:
            result=run_trial(graph,plan,seed,condition,folder/f"seed{seed}-{condition}")
            report["trials"].append(result);save_json(REPORT,report)
            print(json.dumps({"seed":seed,"condition":condition,"wall_s":result["wall_seconds"],"checks":result["checks"],
                "source_spikes":[w["actual_source_spikes"] for w in result["windows"]],
                "non_source_spikes":[w["non_source_spikes"] for w in result["windows"]]}),flush=True)
    checks={"all15trials":len(report["trials"])==15,
        "all_trial_numerical_checks":all(all(t["checks"].values()) for t in report["trials"]),
        "same_RNG_draw_count_and_final_state":True,"same_EA_and_blocked_requested_arrivals":True,
        "frozen_sources_still_match":all(sha(ROOT/p)==h for p,h in plan["source_sha256"].items())}
    for seed in plan["seeds"]:
        rows={t["condition"]:t for t in report["trials"] if t["seed"]==seed}
        checks["same_RNG_draw_count_and_final_state"] &= len({(t["rng_draws"],t["final_rng_state"]) for t in rows.values()})==1
        checks["same_EA_and_blocked_requested_arrivals"] &= rows["ethyl_acetate"]["requested_arrival_sha256"]==rows["ethyl_acetate_source_outputs_blocked"]["requested_arrival_sha256"]
    report.update(complete=True,checks=checks)
    save_json(REPORT,report)
    print(json.dumps(checks,indent=2),flush=True)
    if not all(checks.values()): raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["plan","run"])
    args=parser.parse_args()
    graph=Connectome.load(ROOT/"data/processed/malecns_v1",verify=True)
    if args.mode=="plan":create_plan(graph)
    else:run(graph)


if __name__=="__main__":main()
