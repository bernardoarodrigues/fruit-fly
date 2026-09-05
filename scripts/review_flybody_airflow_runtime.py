#!/usr/bin/env python3
"""Independently review saved opt-in airflow evidence; never construct a simulator.

Uses source XML/NumPy kinematics, byte/hash comparisons, and saved journals.
Does not import the airflow producer, fruitfly runtime, FlyBody or MuJoCo.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import traceback

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from review_flybody_airflow import xml_bodies, kinematics

OUT=ROOT/"validation/flybody-airflow-runtime"
EXPECTED_PLAN="1c5f1b6946f993fe880ce14a37ca46ffa78d0be51da87cf3e6ff148347db3e7d"
REVISION="6a1577b9c1817d74dd757d04c4a8e494f06deaa4"
NATIVE=("native_time_s","tick","qpos","qvel","qacc","act","ctrl","native_action","canonical_action",
    "actuator_ids","action_names","pose_cm_quat","target_pose_cm_quat","up_z","support_dyne_by_leg",
    "contacts","antenna_positions_mm","tibia_velocity_rad_s","command","warnings","finite","source_terminated")
NEURAL=("start_ms","end_ms","ordered_drive_sha256","full_event_sha256","downstream_event_sha256",
    "total_spikes","traversed_edges","monitored_counts","voltage_mv","rng_state_before","rng_state_after",
    "positive_input_cells_by_encoder","max_input_event_rate_hz_by_encoder","listed_input_refractory_zero",
    "sensory_outgoing_mask","blocked_neuron_count","all_neuron_counts","sensory_and_motor_events")


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())


def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def git_bytes(path,revision=REVISION):
    return subprocess.check_output(["git","show",revision+":"+path],cwd=ROOT)


def method(source,cls,name):
    tree=ast.parse(source)
    parent=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in parent.body if isinstance(n,ast.FunctionDef) and n.name==name)


def bundles(path,physical_event):
    """At most one completed interval in memory; all array order is retained."""
    current={}
    with gzip.open(path,"rt") as f:
        for line in f:
            event=json.loads(line);kind=event["event"]
            if kind=="initial":yield event
            elif kind=="coupling_start":current={"coupling_start":event}
            elif kind=="encoder":current.setdefault("encoder",[]).append(event)
            elif kind in ("neural_start","neural_complete","ordered_spikes"):current[kind]=event
            elif kind==physical_event:
                current["physical"]=event;yield current;current={}


def spike_blocks(path):
    """Independent FFSPK001 reader, without importing the recorder."""
    with gzip.open(path,"rb") as f:
        if f.read(8)!=b"FFSPK001":raise ValueError("Wrong lossless spike magic")
        size=f.read(4)
        if len(size)!=4:raise EOFError("Truncated spike metadata length")
        length=struct.unpack("<I",size)[0]
        if not 0<length<65536:raise ValueError("Invalid metadata length")
        raw=f.read(length)
        if len(raw)!=length:raise EOFError("Truncated spike metadata")
        metadata=json.loads(raw)
        if metadata["plan_sha256"]!=EXPECTED_PLAN:raise ValueError("Wrong spike-stream plan")
        while header:=f.read(32):
            if len(header)!=32:raise EOFError("Truncated spike block")
            tick,n,start,end=struct.unpack("<QQdd",header)
            if n>166700*20:raise ValueError("Invalid spike block count")
            raw_ids=f.read(n*8);raw_times=f.read(n*8)
            if len(raw_ids)!=n*8 or len(raw_times)!=n*8:raise EOFError("Truncated spike arrays")
            ids=np.frombuffer(raw_ids,dtype="<i8");times=np.frombuffer(raw_times,dtype="<f8")
            yield dict(tick=tick,count=n,start=start,end=end,ids=ids,times=times,
                hash=hashlib.sha256(struct.pack("<Q",n)+raw_ids+raw_times).hexdigest())


def review(report):
    checks=report["checks"]
    def check(name,passed,detail=None):
        checks.append(dict(name=name,passed=bool(passed),detail=detail))
        if not passed:raise AssertionError(name)
    def receipt(path):
        path=Path(path);value=dict(path=str(path.relative_to(ROOT)),sha256=sha(path),bytes=path.stat().st_size)
        report["evidence"].append(value);return value
    def close(actual,expected,tol=1e-10):
        a,b=np.asarray(actual),np.asarray(expected)
        if a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():raise AssertionError("Invalid geometry shape/value")
        error=float(np.max(np.abs(a-b)))
        if error>tol:raise AssertionError(f"Geometry difference {error} exceeds {tol}")
        return error

    plan=read(OUT/"plan.json");result=read(OUT/"result.json");condition=result["condition"]
    check("frozen_runtime_plan",sha(OUT/"plan.json")==EXPECTED_PLAN==result["plan_sha256"] and plan["source_revision"]==REVISION)
    check("producer_completed_gate_record",result["complete"] and result["passed"] and condition["all_condition_gates_pass"])
    check("declared_scope",plan["ticks"]==1000 and plan["duration_s"]==2. and plan["coupling_s"]==.002 and plan["seed"]==11
        and plan["config"]["body"]["enable_wind"] is True and plan["mute_intervals_ticks"]==[[300,600]])
    prior_plan=read(ROOT/"validation/flybody-rolling-loop/plan.json")
    normalized=json.loads(json.dumps(plan["config"]));del normalized["body"]["enable_wind"]
    check("configuration_only_opt_in_differs",normalized==prior_plan["config"])
    check("producer_retains_failure_clock_artifacts",not condition["failures"] and condition["returned_physical_ticks"]==condition["validated_physical_ticks"]==1000
        and condition["actual_final_or_failure_state"]["stage_clocks"]["brain_t_ms"]==2000.
        and condition["worker_exit_code_after_close"] is not None)
    for path in (OUT/"plan.json",OUT/"result.json",ROOT/"scripts/review_flybody_airflow.py",Path(__file__)):
        receipt(path)
    live_drift={}
    frozen_code=[]
    for path,expected in plan["source_sha256"].items():
        live_drift[path]=sha(ROOT/path)!=expected
        if path.startswith(("fruitfly/","scripts/")):
            frozen_code.append(path)
            check("git_source_identity:"+path,hashlib.sha256(git_bytes(path)).hexdigest()==expected)
        else:check("data_receipt_identity:"+path,sha(ROOT/path)==expected)
    report["live_source_drift_from_frozen_plan"]=live_drift
    report["frozen_source_hashes"]=plan["source_sha256"]
    unchanged=("fruitfly/neural.py","fruitfly/sensors.py","fruitfly/proprioception.py","fruitfly/data.py",
        "fruitfly/simulation.py","fruitfly/wind.py","fruitfly/physiology.py","fruitfly/flybody_persistent_task.py")
    check("neural_encoder_physiology_and_wind_source_unchanged",all(plan["source_sha256"][p]==prior_plan["source_sha256"][p] for p in unchanged))
    worker_now=git_bytes("fruitfly/flybody_worker.py");worker_old=git_bytes("fruitfly/flybody_worker.py",REVISION+"^")
    for name in ("_policy","advance"):
        check("unchanged_worker_method:"+name,ast.dump(method(worker_now,"Worker",name),include_attributes=False)==ast.dump(method(worker_old,"Worker",name),include_attributes=False))
    module_tree=ast.parse(git_bytes("fruitfly/flybody_airflow.py"))
    sample=method(git_bytes("fruitfly/flybody_airflow.py"),"FlyBodyAirflow","sample")
    native_calls=[n.func.attr for n in ast.walk(sample) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=="mujoco"]
    check("module_sample_only_native_call_is_read_jacobian",native_calls==["mj_jac"])
    header=ROOT/"tmp/flybody-env/lib/python3.10/site-packages/mujoco/include/mujoco/mujoco.h"
    receipt(header)
    check("installed_jacobian_API_takes_const_model_and_data", "mj_jac(const mjModel* m, const mjData* d," in header.read_text())
    bridge_tree=ast.parse(git_bytes("fruitfly/flybody_bridge.py"))
    config_class=next(n for n in bridge_tree.body if isinstance(n,ast.ClassDef) and n.name=="FlyBodyConfig")
    wind_default=next(n.value for n in config_class.body if isinstance(n,ast.AnnAssign) and n.target.id=="enable_wind")
    check("disabled_by_default",ast.literal_eval(wind_default) is False)

    module_plan=read(ROOT/"validation/flybody-airflow-module/plan.json")
    module=read(ROOT/"validation/flybody-airflow-module/result.json")
    old_geometry=read(ROOT/"validation/flybody-airflow-geometry.json")
    old_review=read(ROOT/"validation/flybody-airflow-independent-review.json")
    for path in ("validation/flybody-airflow-module/plan.json","validation/flybody-airflow-module/result.json",
        "validation/flybody-airflow-geometry.json","validation/flybody-airflow-independent-review.json",
        "data/raw/flybody/source/flybody/fruitfly/assets/fruitfly.xml"):
        receipt(ROOT/path)
    check("module_plan_and_exact_module_bytes",module["passed"] and module["plan_sha256"]==sha(ROOT/"validation/flybody-airflow-module/plan.json")
        and module["module_sha256"]==plan["source_sha256"]["fruitfly/flybody_airflow.py"])
    check("saved_zero_step_module_state_and_actor_bytes",module["physics_steps"]==0 and module["initial_time_s"]==module["final_time_s"]==0
        and module["native_state_before"]==module["native_state_after"]
        and module["actor_observation_before"]==module["actor_observation_after"])
    check("module_source_chain",all(sha(ROOT/path)==expected for path,expected in module_plan["source_sha256"].items()))
    check("prior_independent_geometry_pass",old_review["passed"] and old_geometry["passed"])
    manifest=read(ROOT/"validation/flybody-source-manifest.json")
    bad=[row["path"] for row in manifest["files"] if sha(ROOT/"data/raw/flybody/source"/row["path"])!=row["sha256"]]
    check("all_native_upstream_source_files",not bad,dict(files=len(manifest["files"]),mismatches=bad))
    bodies=xml_bodies(old_geometry["joints"])
    basis=bodies["head"]["rotation"].T
    close(basis,module["metadata"]["basis_in_head"],1e-12)
    probe_errors=[]
    for saved in module["probes"]:
        analytical,rotation=kinematics(np.asarray(saved["qpos"]),np.asarray(saved["qvel"]),bodies,basis)
        errs=dict(position_mm=close(saved["sample"]["antenna_origin_positions_mm"],[p["origin"]*10 for p in analytical]),
            velocity_mm_s=close(saved["sample"]["antenna_origin_velocity_world_mm_s"],[p["velocity"]*10 for p in analytical]),
            head_rotation=close(saved["sample"]["head_to_world"],rotation))
        check("saved_probe_unchanged:"+saved["case"],saved["data_before"]==saved["data_after"] and saved["time_s"]==0 and saved["state_unchanged"])
        probe_errors.append(dict(case=saved["case"],errors=errs))
    check("four_distinct_module_probes",len(probe_errors)==4 and len({r["case"] for r in probe_errors})==4)
    report["module_analytical_probe_errors"]=probe_errors

    for item in condition["files"].values():check("raw_file_hash:"+item["path"],sha(ROOT/item["path"])==item["sha256"])
    journal=ROOT/condition["journal"]["path"];receipt(journal)
    h=hashlib.sha256();record_count=byte_count=0;events=Counter();last_event=None
    with gzip.open(journal,"rb") as f:
        for line in f:
            h.update(line);byte_count+=len(line);record_count+=1
            event=json.loads(line);events[event["event"]]+=1;last_event=event["event"]
    check("full_closed_journal_digest",h.hexdigest()==condition["journal"]["uncompressed_sha256"] and byte_count==condition["journal"]["uncompressed_bytes"]
        and record_count==condition["journal"]["records"] and last_event=="condition_end")
    check("actual_event_stage_counts",events["physical_returned"]==events["physical_complete"]==events["neural_complete"]==events["ordered_spikes"]==1000
        and events["encoder"]==3000 and events["condition_failure"]==0 and events["actual_state_retained"]==1)
    runner_manifest=read(ROOT/condition["run_dir"]/"runner/manifest.json")
    air=np.r_[runner_manifest["body_config"]["wind_mm_s"],0.]
    check("native_airflow_metadata",condition["body_metadata"]["airflow_module_sha256"]==plan["source_sha256"]["fruitfly/flybody_airflow.py"]
        and condition["body_metadata"]["airflow_geometry"]["mechanical_or_neural_transduction"] is False
        and runner_manifest["body_config"]["enable_wind"] is True)
    old_ref=plan["references"]["locomotor_feedback"]
    old_path=ROOT/old_ref["journal_gzip_path"]
    check("original_2s_journal_identity",sha(old_path)==old_ref["journal_gzip_sha256"]);receipt(old_path)
    rolling_result=read(ROOT/"validation/flybody-rolling-loop/results.json")
    rolling=next(c for c in rolling_result["conditions"] if c["condition"]=="locomotor_feedback")
    rolling_path=ROOT/rolling["journal"]["path"]
    check("previous_rolling_actor_journal_identity",sha(rolling_path)==rolling["journal"]["sha256"]);receipt(rolling_path)
    actual=bundles(journal,"physical_returned");old=bundles(old_path,"physical_complete");prior=bundles(rolling_path,"physical_returned")
    spikes=spike_blocks(ROOT/condition["lossless_spikes"]["path"])
    geometry_errors={key:0. for key in ("position_mm","velocity_mm_s","head_rotation","relative_flow_mm_s","horizontal_speed_mm_s","source_azimuth_deg")}
    total_spikes=0;matched=hashlib.sha256();ticks=[]
    final_neural=None
    try:
        for index in range(1001):
            a,b,c=next(actual),next(old),next(prior)
            if index==0:
                d,od,pd=a["diagnostics"],b["diagnostics"],c["diagnostics"];state=a["state"]
            else:
                d,od,pd=a["physical"]["diagnostics"],b["physical"]["diagnostics"],c["physical"]["diagnostics"]
                state=a["physical"]["state"]
                for x,y in zip(a["encoder"],b["encoder"],strict=True):
                    for field in ("encoder","actual_local_observation","actual_drive"):
                        if canonical(x[field])!=canonical(y[field]):raise AssertionError(f"Encoder prefix {index}:{field}")
                for field in ("brain_t_ms","duration_ms","actual_drive","rng_state"):
                    if canonical(a["neural_start"][field])!=canonical(b["neural_start"][field]):raise AssertionError(f"Input/RNG prefix {index}:{field}")
                for field in NEURAL:
                    if canonical(a["neural_complete"][field])!=canonical(b["neural_complete"][field]):raise AssertionError(f"Neural prefix {index}:{field}")
                spike=next(spikes);n=a["neural_complete"]
                if spike["tick"]!=index-1 or spike["hash"]!=n["full_event_sha256"] or spike["count"]!=n["total_spikes"]:raise AssertionError("Lossless spike block differs from neural journal")
                if spike["start"]!=n["start_ms"] or spike["end"]!=n["end_ms"] or not np.isfinite(spike["times"]).all() or np.any(spike["times"]<spike["start"]) or np.any(spike["times"]>=spike["end"]):raise AssertionError("Spike timing differs")
                unique,counts=np.unique(spike["ids"],return_counts=True)
                if unique.tolist()!=n["all_neuron_counts"]["neuron_ids"] or counts.tolist()!=n["all_neuron_counts"]["counts"]:raise AssertionError("Lossless spike counts differ")
                total_spikes+=spike["count"];final_neural=n
            for field in NATIVE:
                if canonical(d[field])!=canonical(od[field]):raise AssertionError(f"Original native prefix {index}:{field}")
            if d["actor_input_sha256"]!=pd["actor_input_sha256"]:raise AssertionError(f"Actual actor input hash changed at {index}")
            analytical,rotation=kinematics(np.asarray(d["qpos"]),np.asarray(d["qvel"]),bodies,basis)
            origin=np.asarray([p["origin"]*10 for p in analytical]);velocity=np.asarray([p["velocity"]*10 for p in analytical])
            flow=(air-velocity)@rotation;horizontal=np.linalg.norm(flow[:,:2],axis=1)
            g=d["airflow_geometry"];w=state["wind"]
            values={"position_mm":close(g["antenna_origin_positions_mm"],origin),
                "velocity_mm_s":close(g["antenna_origin_velocity_world_mm_s"],velocity),
                "head_rotation":close(g["head_to_world"],rotation),
                "relative_flow_mm_s":close(w["relative_velocity_head_mm_s"],flow),
                "horizontal_speed_mm_s":close(w["horizontal_speed_mm_s"],horizontal)}
            close(g["antenna_origin_positions_mm"],d["antenna_positions_mm"])
            close(w["sensor_position_world_mm"],origin);close(w["sensor_velocity_world_mm_s"],velocity)
            close(rotation.T@rotation,np.eye(3),1e-12)
            if abs(np.linalg.det(rotation)-1)>1e-12 or w["enabled"] is not True or w["mechanical_or_neural_transduction"] is not False:raise AssertionError("Flow frame/claim flags changed")
            if w["antenna_order"]!=["L","R"] or w["head_axes"]!=["forward","left","up"]:raise AssertionError("Airflow frame labels changed")
            angle_error=0.
            for v,speed,angle in zip(flow,horizontal,w["source_azimuth_deg"],strict=True):
                expected=float(np.degrees(np.arctan2(v[1],-v[0]))) if speed>1e-9 else None
                if expected is None:
                    if angle is not None:raise AssertionError("Undefined horizontal azimuth should be null")
                else:angle_error=max(angle_error,abs((angle-expected+180)%360-180))
            if angle_error>1e-9:raise AssertionError("Source azimuth differs from source kinematics")
            values["source_azimuth_deg"]=angle_error
            for key,value in values.items():geometry_errors[key]=max(geometry_errors[key],value)
            ticks.append(d["tick"]);matched.update(canonical({k:d[k] for k in NATIVE}));matched.update(d["actor_input_sha256"].encode())
        if next(actual,None) is not None or next(old,None) is not None or next(spikes,None) is not None:raise AssertionError("Unexpected extra regression intervals")
    finally:
        actual.close();old.close();prior.close();spikes.close()
    check("1001_native_geometry_and_actor_samples",ticks==list(range(1001)))
    check("1000_original_input_RNG_neural_prefix_and_lossless_blocks",total_spikes==condition["lossless_spikes"]["events"])
    report["runtime_geometry_max_abs_errors"]=geometry_errors
    report["matched_native_actor_prefix_sha256"]=matched.hexdigest()
    report["samples"]=dict(native_geometry=1001,actor_input_hashes=1001,neural_intervals=1000,lossless_spikes=total_spikes)
    state_receipt=condition["actual_final_or_failure_state"];state=read(ROOT/state_receipt["state"]["path"])
    checkpoint=ROOT/state_receipt["brain_checkpoint"]["path"];receipt(checkpoint)
    check("failure_state_receipt",sha(ROOT/state_receipt["state"]["path"])==state_receipt["state"]["sha256"]
        and state["runner_failure"] is None and state["stage_clocks"]["host_physiology_t_s"] is None
        and state["stage_clocks"]["brain_t_ms"]==2000. and abs(state["stage_clocks"]["native_time_s"]-2.)<1e-9)
    with np.load(checkpoint,allow_pickle=False) as z:
        metadata=json.loads(z["metadata"].item())
        check("checkpoint_graph_clock_rng_and_voltages",metadata["graph_sha256"]==plan["graph_sha256"] and metadata["tick"]==20000
            and metadata["parameters"]==plan["neural_parameters"]
            and z["rng_state"].tolist()==final_neural["rng_state_after"]
            and float(z["voltage_mv"].min())==final_neural["voltage_mv"]["min"] and float(z["voltage_mv"].max())==final_neural["voltage_mv"]["max"])
        check("pending_checkpoint_arrays_retained",all(name in z for name in ("pending","pending_count","synaptic_mv","last_spike_tick","current_mv","previous_drive")))
    check("no_model_imported_or_simulated",not any(name=="mujoco" or name.startswith(("mujoco.","flybody.","fruitfly.")) for name in sys.modules))
    report["scope_limits"]=["One seed, one 2 s native/neural path; no general or indefinite behavioral guarantee",
        "Proximal antenna body origins only, not distal arista/sensillum or near-body flow",
        "No wind force, antenna deflection, measured female response, neural wind transduction or steering",
        "Module no-mutation bytes cover nine named native arrays and saved actor observations, not every MuJoCo field",
        "Failures are retained by the unchanged reviewed recorder; no new failing simulation was generated"]


def main():
    destination=OUT/"independent-review.json"
    if destination.exists():raise FileExistsError("Preserve the existing independent review")
    if not (OUT/"result.json").exists():raise SystemExit("Wait for the frozen regression to close")
    report=dict(created_utc=datetime.now(timezone.utc).isoformat(),review_kind="Saved-evidence and source review; no model execution",
        reviewer_sha256=sha(Path(__file__)),frozen_revision=REVISION,numpy_version=np.__version__,checks=[],evidence=[],passed=False)
    try:
        review(report);report["passed"]=all(c["passed"] for c in report["checks"])
    except BaseException as error:
        report["failure"]=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    destination.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"passed":report["passed"],"checks":len(report["checks"]),"failure":report.get("failure"),
        "geometry":report.get("runtime_geometry_max_abs_errors")},indent=2))
    if not report["passed"]:raise SystemExit(1)


if __name__=="__main__":main()
