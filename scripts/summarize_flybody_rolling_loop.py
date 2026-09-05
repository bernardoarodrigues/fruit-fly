#!/usr/bin/env python3
"""Post-run descriptive analysis of frozen rolling FlyBody journals; no simulation.

--inspect-closed prints available closed-condition summaries without creating
artifacts. --write requires all attempts concluded and refuses existing outputs.
This is outcome analysis, not a new preregistered behavioral success test.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/flybody-rolling-loop"
DOC = ROOT / "docs/flybody-rolling-loop-outcomes.md"
EXPECTED_PLAN = "3e5ca3ca6c91bbd240ff2530d351fd010dc5001e19078e2270a95022449c2498"
DT = .002
WINDOWS = ((0,300,"before_mute_1"),(300,600,"mute_1"),(600,1500,"after_mute_1"),
    (1500,1800,"mute_2"),(1800,4500,"after_mute_2"),(4500,5300,"mute_3"),(5300,6000,"after_mute_3"))
RESOURCE_FIELDS = ("energy","hydration","crop","food_ingested","water_ingested",
    "energy_spent","water_lost","feeding_s","resting_s","hunger","thirst")
COLORS = {"locomotor_feedback":"#146a9e","locomotor_sensory_block":"#cb6c1b","sensory_only":"#72558f"}
LABELS = {"locomotor_feedback":"Locomotor + sensory transmission", "locomotor_sensory_block":"Locomotor, sensory output blocked", "sensory_only":"Sensory only (no probe/mutes)"}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block:=stream.read(1024*1024):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())


def safe(value):
    if isinstance(value,np.ndarray):return safe(value.tolist())
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not np.isfinite(value):return {"nonfinite":repr(value)}
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [safe(v) for v in value]
    return value


def num(value):
    return float(value) if isinstance(value,(int,float)) else float("nan")


def stats(values):
    values=np.asarray(values,dtype=float)
    finite=values[np.isfinite(values)]
    return dict(samples=len(values),nonfinite_samples=int((~np.isfinite(values)).sum()),
        mean=float(finite.mean()) if len(finite) else None,
        minimum=float(finite.min()) if len(finite) else None,
        median=float(np.median(finite)) if len(finite) else None,
        maximum=float(finite.max()) if len(finite) else None)


def physiology_delta(first,last):
    return {key:num(last["physiology"][key])-num(first["physiology"][key]) for key in RESOURCE_FIELDS}


def endpoint_voltages(condition,plan,listed_ids,positive_ids):
    """Join saved endpoint voltages to exact graph IDs; never advance a model."""
    import pandas as pd
    checkpoint=condition.get("actual_final_or_failure_state",{}).get("brain_checkpoint")
    if checkpoint is None:return dict(available=False,reason="No retained checkpoint")
    path=ROOT/checkpoint["path"]
    if sha(path)!=checkpoint["sha256"]:raise ValueError("Final checkpoint changed")
    graph=ROOT/plan["config"]["connectome"]
    if sha(graph/"manifest.json")!=plan["source_sha256"][str((graph/"manifest.json").relative_to(ROOT))]:
        raise ValueError("Graph manifest differs from frozen plan")
    manifest=read(graph/"manifest.json")
    hashes={}
    for name in ("neuron_ids.npy","neurons.feather"):
        expected=(manifest["arrays"] | manifest["metadata"])[name]["sha256"]
        hashes[name]=sha(graph/name)
        if hashes[name]!=expected:raise ValueError("Endpoint identity artifact changed: "+name)
    if hashes["neurons.feather"]!=plan["source_sha256"][str((graph/"neurons.feather").relative_to(ROOT))]:
        raise ValueError("Neuron annotations differ from frozen plan")
    ids=np.load(graph/"neuron_ids.npy",allow_pickle=False)
    neurons=pd.read_feather(graph/"neurons.feather",columns=["bodyId","type","instance","superclass","somaSide","consensus_nt","model_sign"])
    np.testing.assert_array_equal(ids,neurons["bodyId"].to_numpy(dtype=np.int64))
    if len(np.unique(ids))!=len(ids):raise ValueError("Duplicate endpoint neuron IDs")
    with np.load(path,allow_pickle=False) as saved:
        metadata=json.loads(saved["metadata"].item());voltage=saved["voltage_mv"].copy()
    if metadata["graph_sha256"]!=plan["graph_sha256"] or metadata["parameters"]!=plan["neural_parameters"] or metadata["seed"]!=plan["seed"]:
        raise ValueError("Checkpoint graph/parameters differ from frozen trial")
    if voltage.shape!=ids.shape:raise ValueError("Checkpoint lacks full ordered neuron array")
    if not listed_ids<=set(ids.tolist()):raise ValueError("Actual drive contains unknown graph IDs")
    groups={k:set(condition["groups"][k]["neuron_ids"]) for k in ("odor","sweet","club")}
    groups["probe"]=set(condition["probe_ids"]) if condition["design"]["assay"]=="motor_probe" else set()
    if not listed_ids<=set.union(*groups.values()):
        raise ValueError("Actual listed source IDs extend beyond declared encoder/probe groups")
    fractions=(0,.001,.01,.05,.25,.5,.75,.95,.99,.999,1)
    def summarize(mask):
        values=voltage[mask];finite=values[np.isfinite(values)]
        return dict(neurons=len(values),finite_neurons=len(finite),nonfinite_neurons=int((~np.isfinite(values)).sum()),
            quantiles_mv={str(q):float(np.quantile(finite,q,method="linear")) for q in fractions} if len(finite) else {},
            strict_threshold_counts={str(limit):int((values<limit).sum()) for limit in (-100,-200)},
            strict_threshold_fraction_of_group={str(limit):float((values<limit).sum()/len(values)) if len(values) else None for limit in (-100,-200)})
    source_mask=np.isin(ids,list(listed_ids))
    stats_by_group={"all_neurons":summarize(np.ones(len(ids),dtype=bool)),
        "actual_listed_input_sources":summarize(source_mask),"other_neurons":summarize(~source_mask)}
    stats_by_group.update({key:summarize(np.isin(ids,list(value & listed_ids))) for key,value in groups.items()})
    def cell(index):
        row=neurons.iloc[index];body_id=int(ids[index])
        return dict(graph_index=int(index),body_id=body_id,voltage_mv=float(voltage[index]),
            **{k:None if pd.isna(row[k]) else row[k] for k in ("type","instance","superclass","somaSide","consensus_nt","model_sign")},
            actual_listed_input_source=body_id in listed_ids,
            actual_input_groups=[key for key,value in groups.items() if body_id in value and body_id in listed_ids],
            mapped_source_groups=[key for key,value in groups.items() if body_id in value],
            ever_positive_requested_input_rate=body_id in positive_ids)
    order=np.lexsort((ids,np.where(np.isfinite(voltage),voltage,np.inf)))
    worst=[cell(i) for i in order[:10] if np.isfinite(voltage[i])]
    source_order=[i for i in order if source_mask[i] and np.isfinite(voltage[i])]
    return safe(dict(available=True,checkpoint=checkpoint,metadata=metadata,
        endpoint_brain_time_ms=metadata["tick"]*metadata["parameters"]["dt_ms"],
        endpoint_scope="Saved state before cleanup; not trajectory-wide or within-tick extrema",
        graph_sha256=metadata["graph_sha256"],identity_sha256=hashes,
        identity_method="Hash-verified neuron_ids.npy order equals neurons.feather bodyId row order; checkpoint graph identity and parameter metadata equal frozen plan",
        source_definition="IDs actually listed in journal neural_start drives, including zero-rate members; probe category only when actually appended in motor_probe assay",
        actual_listed_input_ids=sorted(listed_ids),ever_positive_requested_input_ids=sorted(positive_ids),
        mapped_group_ids_never_listed_as_input={key:sorted(value-listed_ids) for key,value in groups.items()},
        voltage_by_group=stats_by_group,most_negative_cells=worst,
        most_negative_actual_input_source_cells=[cell(i) for i in source_order[:5]],
        transmitter_caveat="Consensus NT labels describe each cell's predicted output transmitter; they do not identify which incoming currents caused its voltage"))


def summarize_window(rows,neural,start,end,label,muted):
    physical=[r for r in rows if start<=r["tick"]<end]
    brains=[r for r in neural if start<=r["tick"]<end]
    result=dict(label=label,declared_start_s=start*DT,declared_end_s=end*DT,
        motor_mute_applied=muted,returned_physical_intervals=len(physical),
        completed_neural_intervals=len(brains),covered_returned_duration_s=len(physical)*DT,
        total_spikes=sum(r["spikes"] for r in brains),
        monitored_spikes=dict(sum((Counter(r["monitored"]) for r in brains),Counter())),
        sampled_neural_min_mv=stats([r["vmin"] for r in brains])["minimum"],
        sampled_neural_max_mv=stats([r["vmax"] for r in brains])["maximum"])
    if physical:
        result.update(planar_path_mm=float(sum(r["step_path"] for r in physical)),
            mean_interval_path_speed_mm_s=float(np.mean([r["step_path"]/DT for r in physical])),
            post_step_native_planar_speed_mm_s=stats([r["speed"] for r in physical]),
            last_100ms_native_planar_speed_mm_s=stats([r["speed"] for r in physical if r["tick"]>=end-50]),
            motor_command_counts=dict(Counter(r["motor"] for r in physical)),
            policy_enabled_intervals=sum(r["policy"] for r in physical),
            food_contact_samples=sum(r["taste_food"] for r in physical),
            resource_change=physiology_delta(physical[0]["before"],physical[-1]["state"]),
            start_position_mm=physical[0]["previous_position"],end_position_mm=physical[-1]["position"])
    return result


def analyze_condition(condition,plan):
    path=ROOT/condition["journal"]["path"]
    if sha(path)!=condition["journal"]["sha256"]:raise ValueError("Closed journal hash mismatch: "+str(path))
    initial=None;previous_state=None;previous_position=None
    rows=[];brains=[];journal_failures=[];interventions=[];last=None
    listed_ids=set();positive_ids=set()
    h=hashlib.sha256();raw_bytes=records=0
    with gzip.open(path,"rb") as stream:
        for line in stream:
            h.update(line);raw_bytes+=len(line);records+=1
            event=json.loads(line)
            kind=event["event"]
            if kind=="initial":
                initial=event;previous_state=event["state"]
                previous_position=np.asarray([num(x)*10 for x in event["diagnostics"]["pose_cm_quat"][:3]])
            elif kind=="neural_complete":
                brains.append(dict(tick=event["tick"],spikes=event["total_spikes"],
                    edges=event["traversed_edges"],vmin=num(event["voltage_mv"]["min"]),
                    vmax=num(event["voltage_mv"]["max"]),monitored=event["monitored_counts"],
                    positive_inputs=event["positive_input_cells_by_encoder"],
                    input_rate_max=event["max_input_event_rate_hz_by_encoder"]))
            elif kind=="neural_start":
                drive=event["actual_drive"]
                listed_ids.update(drive["neuron_ids"])
                positive_ids.update(neuron_id for neuron_id,rate in zip(drive["neuron_ids"],drive["rates_hz"],strict=True) if rate>0)
            elif kind=="physical_returned":
                if initial is None:raise ValueError("Physical return before initial state")
                d,state=event["diagnostics"],event["state"]
                position=np.asarray([num(x)*10 for x in d["pose_cm_quat"][:3]])
                velocity=np.asarray([num(x) for x in d["velocity_world_mm_s"][:2]])
                rows.append(dict(tick=event["tick"],native_t_s=num(d["native_time_s"]),
                    position=position,previous_position=previous_position.copy(),
                    step_path=float(np.linalg.norm(position[:2]-previous_position[:2])),
                    speed=float(np.linalg.norm(velocity)),motor=state["motor"]["behavior"],
                    left=num(state["motor"]["left"]),right=num(state["motor"]["right"]),
                    policy=bool(d["command"]["policy_enabled"]),
                    commanded_speed=num(d["command"]["speed_mm_s"]),
                    up_z=num(d["up_z"]),taste_food=bool(state["senses"]["taste_food"]),
                    before={"physiology":previous_state["physiology"]},
                    state={"physiology":state["physiology"],"resources":state["resources"],
                        "resource_balance":state["resource_balance"]}))
                previous_state=state;previous_position=position;last=state
            elif kind=="intervention_start":interventions.append(event)
            elif "failure" in kind:journal_failures.append(event)
    if h.hexdigest()!=condition["journal"]["uncompressed_sha256"] or raw_bytes!=condition["journal"]["uncompressed_bytes"]:
        raise ValueError("Decompressed journal differs from recorder receipt")
    if records!=condition["journal"]["records"]:raise ValueError("Journal record count mismatch")
    for collection in (rows,brains):
        if [r["tick"] for r in collection]!=list(range(len(collection))):
            raise ValueError("Missing/reordered completed interval in outcome analysis")
    mute_enabled=condition["design"]["motor_mute"]
    windows=[summarize_window(rows,brains,a,b,label,mute_enabled and label.startswith("mute_")) for a,b,label in WINDOWS]
    whole=summarize_window(rows,brains,0,plan["ticks"],"whole_returned_record",False)
    if rows and abs(whole["planar_path_mm"]-condition["metrics"]["planar_path_mm"])>1e-9:
        # A evaluator-failed physical_returned can extend the raw path beyond
        # the recorder's metrics. Preserve and label that actual distinction.
        whole["recorder_path_difference_mm"]=whole["planar_path_mm"]-condition["metrics"]["planar_path_mm"]
    positions=np.asarray([r["position"] for r in rows]) if rows else np.empty((0,3))
    food=np.asarray(plan["config"]["body"]["food_position_mm"])
    first_position=np.asarray([num(x)*10 for x in initial["diagnostics"]["pose_cm_quat"][:3]]) if initial else None
    resource=None
    if initial and last:
        resource=dict(units=last["physiology"]["units"],initial=initial["state"]["physiology"],
            final=last["physiology"],change=physiology_delta(initial["state"],last),
            initial_patches=initial["state"]["resources"],final_patches=last["resources"],
            final_balance_residual=last["resource_balance"],
            any_food_contact=any(r["taste_food"] for r in rows),
            any_sweet_positive_input=any(r["positive_inputs"]["sweet"]>0 for r in brains))
    recovery=[]
    if mute_enabled:
        for start,end in plan["mute_intervals_ticks"]:
            next_policy=next((r for r in rows if r["tick"]>=end and r["policy"]),None)
            recovery.append(dict(mute_start_s=start*DT,mute_end_s=end*DT,
                first_later_policy_command_start_s=next_policy["tick"]*DT if next_policy else None,
                first_later_policy_command_delay_s=(next_policy["tick"]-end)*DT if next_policy else None,
                first_500ms_after_release=summarize_window(rows,brains,end,min(end+250,plan["ticks"]),"post_release_500ms",False)))
    endpoint=endpoint_voltages(condition,plan,listed_ids,positive_ids)
    if endpoint["available"] and brains:
        q=endpoint["voltage_by_group"]["all_neurons"]["quantiles_mv"]
        endpoint["matches_last_completed_neural_record_extrema"]=bool(q.get("0")==brains[-1]["vmin"] and q.get("1")==brains[-1]["vmax"])
        endpoint["last_completed_neural_record_end_ms"]=(brains[-1]["tick"]+1)*DT*1000
    summary=dict(condition=condition["condition"],design=condition["design"],
        recorded_complete=condition["complete"],recorded_all_condition_gates_pass=condition["all_condition_gates_pass"],
        journal=dict(path=str(path.relative_to(ROOT)),sha256=sha(path),uncompressed_sha256=h.hexdigest(),records=records),
        spike_artifact=condition.get("lossless_spikes"),
        returned_intervals_in_journal=len(rows),completed_neural_intervals_in_journal=len(brains),
        validated_intervals=condition["validated_physical_ticks"],
        unmatched_completed_neural_intervals=len(brains)-len(rows),
        failures=condition["failures"],journal_failure_records=journal_failures,
        retained_actual_state=condition.get("actual_final_or_failure_state"),
        original_prefix=condition["original_prefix"],
        interventions=interventions,whole=whole,windows=windows,recovery=recovery,resources=resource,
        native_position_mm=dict(initial=first_position,final=positions[-1] if len(positions) else None,
            straight_line_displacement_mm=float(np.linalg.norm(positions[-1,:2]-first_position[:2])) if len(positions) else None,
            closest_recorded_body_center_to_food_mm=float(np.min(np.linalg.norm(positions[:,:2]-food,axis=1))) if len(positions) else None,
            body_center_is_not_a_tarsal_contact_test=True),
        positive_input_intervals={group:sum(r["positive_inputs"][group]>0 for r in brains) for group in ("odor","sweet","club")},
        maximum_input_event_rate_hz={group:max((r["input_rate_max"][group] for r in brains),default=None) for group in ("odor","sweet","club")},
        endpoint_voltage=endpoint,
        final_images={k:v for k,v in condition["files"].items() if k.startswith("final-") and k.endswith(".png")})
    return safe(summary),dict(rows=rows,brains=brains,initial_position=first_position)


def plot(traces,plan,destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    xy,path,speed,voltage=axes.flat
    for name,trace in traces.items():
        rows,brains=trace["rows"],trace["brains"];color=COLORS[name]
        if rows:
            points=np.vstack([trace["initial_position"],[r["position"] for r in rows]])
            xy.plot(points[:,0],points[:,1],color=color,label=LABELS[name],lw=1.5)
            xy.scatter(*points[-1,:2],color=color,s=22)
            times=np.asarray([(r["tick"]+1)*DT for r in rows])
            path.plot(np.r_[0,times],np.r_[0,np.cumsum([r["step_path"] for r in rows])],color=color,lw=1.5)
            # Disjoint 25-sample bins, with a shorter final bin if necessary.
            for target,values,reducer in ((speed,[r["speed"] for r in rows],np.mean),):
                groups=[slice(i,min(i+25,len(values))) for i in range(0,len(values),25)]
                target.plot([float(times[g].mean()) for g in groups],[float(reducer(values[g])) for g in groups],color=color,lw=1.2)
        if brains:
            t=np.asarray([(r["tick"]+1)*DT for r in brains]);v=np.asarray([r["vmin"] for r in brains])
            groups=[slice(i,min(i+25,len(v))) for i in range(0,len(v),25)]
            voltage.plot([float(t[g].mean()) for g in groups],[float(v[g].min()) for g in groups],color=color,lw=1.2)
    xy.add_patch(Circle(plan["config"]["body"]["food_position_mm"],3,color="#448844",alpha=.2))
    xy.scatter(*plan["config"]["body"]["food_position_mm"],marker="+",color="#336633",s=40)
    xy.set(title="Recorded body path; green disk is food region",xlabel="World x (mm)",ylabel="World y (mm)",aspect="equal")
    path.set(title="Cumulative planar path",ylabel="Path length (mm)")
    speed.set(title="Native planar speed: 50 ms sample means",ylabel="Speed (mm/s)")
    voltage.set(title="Lowest recorded voltage: 50 ms block minima",ylabel="Voltage (mV)")
    for axis in (path,speed,voltage):
        axis.set(xlabel="Declared coupling time (s)",xlim=(0,12))
        for a,b in plan["mute_intervals_s"]:axis.axvspan(a,b,color="#888888",alpha=.13,zorder=-10)
        axis.grid(alpha=.15)
    handles,labels=xy.get_legend_handles_labels()
    fig.legend(handles,labels,loc="outside lower center",ncol=3,frameon=False,fontsize=9)
    fig.suptitle("Frozen 12 s rolling FlyBody outcomes — one seed, engineering surrogate\nGray spans are motor-readout mutes in the locomotor pair only",fontsize=12)
    fig.savefig(destination,dpi=180,metadata={"Description":"Descriptive post-run analysis of frozen actual native and neural journals; no simulation or gain fitting."})
    plt.close(fig)
    return matplotlib.__version__


def fmt(value,digits=3):return "unavailable" if value is None else f"{value:.{digits}f}"


def endpoint_table(report):
    lines=["", "## Final-checkpoint voltage attribution", "", "These are endpoint measurements from the saved brain checkpoints before cleanup. They are distinct from the sampled trajectory extrema above. Fractions use all neurons in the stated group as denominator and strict `< −100` / `< −200` mV comparisons; nonfinite counts and linear-interpolated quantiles are explicit in the JSON.", "", "| Condition | Endpoint (s) | 0.1% quantile (mV) | 1% quantile (mV) | Median (mV) | Below −100 mV | Below −200 mV |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for c in report["conditions"]:
        e=c["endpoint_voltage"]
        if not e["available"]:continue
        v=e["voltage_by_group"]["all_neurons"];q=v["quantiles_mv"];f=v["strict_threshold_fraction_of_group"]
        lines.append(f"| `{c['condition']}` | {fmt(e['endpoint_brain_time_ms']/1000)} | {fmt(q.get('0.001'))} | {fmt(q.get('0.01'))} | {fmt(q.get('0.5'))} | {100*f['-100']:.3f}% | {100*f['-200']:.3f}% |")
    lines += ["", "| Condition | Cell ID | Recorded type | Consensus output NT | Endpoint voltage (mV) | Actual input role |", "| --- | ---: | --- | --- | ---: | --- |"]
    for c in report["conditions"]:
        for cell in c["endpoint_voltage"].get("most_negative_cells",[])[:3]:
            role=", ".join(cell["actual_input_groups"]) if cell["actual_listed_input_source"] else "Other neuron"
            lines.append(f"| `{c['condition']}` | {cell['body_id']} | {cell['type'] or 'unannotated'} | {cell['consensus_nt'] or 'unknown'} | {cell['voltage_mv']:.3f} | {role} |")
    lines += ["", "The JSON retains ten most negative cells and five most negative actual source cells per condition, plus separate distributions for all actual listed input cells, other neurons, each sensory group and the probe. Input membership comes from the actual ordered neural-drive records, including zero-rate members; the sensory-only trial's nominal probe identities are not classified as probe inputs. Hash-verified graph ID arrays and annotation row order provide the join. Consensus neurotransmitter labels describe each neuron's predicted output transmitter; they do not identify the incoming currents responsible for its voltage. This attribution identifies candidate cells for later calibration work without claiming a physiological mechanism or fitting a parameter."]
    return lines


def document(report):
    lines=["# Rolling full-neural FlyBody outcomes", "", "This is a descriptive analysis of the frozen recorded trials, not a new behavioral success test. No simulation was run for this analysis. One seed and one 12 s attempt per condition do not support population estimates or biological validation.", "",f"Plan SHA-256: `{report['plan_sha256']}`. The recorded overall gate result is **{report['recorded_all_declared_gates_pass']}**. Numerical and interface correctness are reviewed separately; these notes preserve the observed outcomes.","", "![Motion and sampled neural voltage](../validation/flybody-rolling-loop/motion.png)","", "## Whole records", "", "| Condition | Returned physical time (s) | Planar path (mm) | Mean native planar speed (mm/s) | Motor command counts | Sampled voltage range (mV) |", "| --- | ---: | ---: | ---: | --- | --- |"]
    for c in report["conditions"]:
        w=c["whole"]
        lines.append(f"| `{c['condition']}` | {fmt(w['covered_returned_duration_s'])} | {fmt(w.get('planar_path_mm'))} | {fmt(w.get('post_step_native_planar_speed_mm_s',{}).get('mean'))} | {json.dumps(w.get('motor_command_counts',{}),sort_keys=True)} | {fmt(w['sampled_neural_min_mv'])} to {fmt(w['sampled_neural_max_mv'])} |")
    lines += ["", "Path sums planar displacement between successive returned 2 ms body poses. Native speed is the norm of the separately recorded world-frame root-body linear velocity at each physical return. Their averages can differ. The voltage range uses all-neuron extrema sampled at the end of each 2 ms neural batch; it is not a continuous-time extreme. The figure uses 50 ms means for speed and minima of these sampled voltage minima. All unsmoothed window statistics remain in the JSON summary.","", "## Motion during and after the imposed mutes", "", "| Condition | Mute (s) | Path during mute (mm) | Mean speed (mm/s) | Last 100 ms mean speed (mm/s) | Neural spikes during mute | First later policy command delay (s) |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for c in report["conditions"]:
        if not c["design"]["motor_mute"]:continue
        for w,recovery in zip([w for w in c["windows"] if w["motor_mute_applied"]],c["recovery"],strict=True):
            lines.append(f"| `{c['condition']}` | {w['declared_start_s']:.1f}–{w['declared_end_s']:.1f} | {fmt(w.get('planar_path_mm'))} | {fmt(w.get('post_step_native_planar_speed_mm_s',{}).get('mean'))} | {fmt(w.get('last_100ms_native_planar_speed_mm_s',{}).get('mean'))} | {w['total_spikes']:,} | {fmt(recovery['first_later_policy_command_delay_s'])} |")
    lines += ["", "A muted rest/zero motor command is not a statement that all physical motion stops immediately. The source body can continue to move or settle under its unchanged physics and engineering adhesion/posture hold. The delay column locates the first later native command with the learned policy enabled; it does not use a fitted speed threshold or claim biological recovery. Neural execution continues through the mute. Windows with no returned states are reported as unavailable.","", "## Food and resources", "", "| Condition | Food-contact samples | Positive sweet-input intervals | Food ingested | Energy change | Hydration change | Feeding time (s) |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for c in report["conditions"]:
        r=c["resources"];delta=r["change"] if r else {}
        lines.append(f"| `{c['condition']}` | {c['whole'].get('food_contact_samples',0)} | {c['positive_input_intervals']['sweet']} | {fmt(delta.get('food_ingested'),6)} | {fmt(delta.get('energy'),6)} | {fmt(delta.get('hydration'),6)} | {fmt(delta.get('feeding_s'))} |")
    lines += ["", "Resources use normalized, uncalibrated engineering units. Body-center distance from food is retained as geometry only; actual tarsal contact is the relevant recorded taste gate. Positive encoder rates refer to the observation before its neural interval, while the contact count above samples physical returns, so these counts can differ at a boundary. The abstract intake mechanism requires tarsal contact, sufficiently low physical speed and a feed command; no proboscis or ingestion apparatus is simulated."]
    lines += endpoint_table(report)
    lines += ["", "## Interpretation and limits", "", "The locomotor pair receives direct 40 Hz descending-neuron excitation. Blocking sensory outgoing transmission tests this implementation's feedback consequences while retaining source input and spiking; downstream differences do not establish natural sensorimotor behavior. The retained paired-mechanism result identifies any initial downstream divergence under matched ordered input history. Later inputs depend on each moving body's trajectory and are not assumed equal.", ""]
    sensory=next((c for c in report["conditions"] if c["condition"]=="sensory_only"),None)
    if sensory:
        w=sensory["whole"]
        lines.append(f"The sensory-only trial had no descending-neuron probe or imposed mutes. Its recorded motor command counts were `{json.dumps(w.get('motor_command_counts',{}),sort_keys=True)}` over {fmt(w['covered_returned_duration_s'])} returned seconds, with {fmt(w.get('planar_path_mm'))} mm of physical path. These command labels and physical displacement are separate observations; neither is automatically evidence of natural walking or foraging.")
    lines += ["", "The learned walking policy, female-derived body surrogate, idealized body feedback, generated command preview, neutral posture hold and unbounded source floor remain engineering assumptions. The food position and radius were fixed; the arena and target were not adjusted to cause a result. Final Follow frames keep the fly inspectable outside the fixed overview. The large negative sampled Shiu voltages, when present, remain a physiological mismatch even if numerically finite. Wind neural input, compound-eye neural input, grooming and flight remain disabled. Twelve seconds cannot establish indefinite stability.","", "Failures and pending state are copied into the JSON outcome summary rather than dropped. A completed neural batch can precede a failed physical return; separate completed-neural/returned-physical counts and the retained checkpoint preserve that distinction.", "", "## Evidence", "", "- [Frozen plan](../validation/flybody-rolling-loop/plan.json), [recorded results](../validation/flybody-rolling-loop/results.json), and [descriptive outcome JSON](../validation/flybody-rolling-loop/outcome-summary.json).", "- [Analysis implementation](../scripts/summarize_flybody_rolling_loop.py) and [experiment methods](flybody-rolling-loop.md).", "- Each closed gzip journal is checked against its recorded compressed/decompressed hashes and record count. Raw paths, spike-artifact receipts, stage-aware retained states and final image receipts are in the outcome JSON.", "- This post-run analysis reports existing records; it does not add behavioral pass thresholds or rerun any model.", ""]
    return "\n".join(lines)


def main(write=False):
    plan_path=OUT/"plan.json";result_path=OUT/"results.json"
    if sha(plan_path)!=EXPECTED_PLAN:raise ValueError("Different frozen experiment plan")
    plan=read(plan_path)
    result_bytes=result_path.read_bytes();result=json.loads(result_bytes)
    result_sha=hashlib.sha256(result_bytes).hexdigest()
    if result["plan_sha256"]!=EXPECTED_PLAN:raise ValueError("Recorded result plan mismatch")
    summaries=[];traces={}
    for condition in result["conditions"]:
        summary,trace=analyze_condition(condition,plan)
        summaries.append(summary);traces[condition["condition"]]=trace
    report=dict(schema_version=1,analysis_created_utc=datetime.now(timezone.utc).isoformat(),
        analysis_kind="Post-run descriptive outcome analysis; no new behavior success thresholds or simulation",
        analysis_source_sha256=sha(Path(__file__)),plan_sha256=EXPECTED_PLAN,
        results_sha256=result_sha,recorded_attempts_complete=result["complete"],
        recorded_all_declared_gates_pass=result.get("all_declared_gates_pass"),
        recorded_paired_mechanism=result.get("locomotor_paired_mechanisms"),
        conditions=summaries,methods=dict(coupling_s=DT,windows=WINDOWS,
            motion="Consecutive returned planar body-pose displacement; native speed separately from post-step root-body world velocity",
            voltage="All-neuron min/max at each 2 ms neural return, not continuous-time extremes",
            resource_units="Normalized engineering units, uncalibrated",
            missing_or_nonfinite="Unavailable values retained explicitly; counts report nonfinite samples",
            independent_correctness_review="Separate reviewer; gate results here are attributed to the frozen recorder"))
    if not write:
        print(json.dumps(safe(report),indent=2,allow_nan=False));return
    if not result["complete"] or len(summaries)!=3:raise ValueError("All three attempts must close before final outcome artifacts")
    if sha(result_path)!=result_sha:raise ValueError("Result snapshot changed during analysis; preserve consistency")
    targets=[OUT/"outcome-summary.json",OUT/"motion.png",DOC]
    if any(p.exists() for p in targets):raise FileExistsError("Outcome artifacts already exist; preserve their identities")
    report["matplotlib_version"]=plot(traces,plan,OUT/"motion.png")
    report["motion_png_sha256"]=sha(OUT/"motion.png")
    (OUT/"outcome-summary.json").write_text(json.dumps(safe(report),indent=2,allow_nan=False)+"\n")
    DOC.write_text(document(report))
    print(json.dumps(dict(written=[str(p.relative_to(ROOT)) for p in targets],
        summary_sha256=sha(OUT/"outcome-summary.json"),motion_sha256=sha(OUT/"motion.png")),indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect-closed",action="store_true")
    mode.add_argument("--write",action="store_true")
    args=parser.parse_args()
    main(write=args.write)
