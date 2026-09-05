"""Frozen, bounded native habitat validation; no neural run or policy changes."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
PLAN = ROOT / "validation/flybody-habitat-execution-plan.json"
RESULT = ROOT / "validation/flybody-habitat-results.json"
FILES = ["scripts/validate_flybody_habitat.py", "fruitfly/flybody_worker.py", "fruitfly/flybody_bridge.py",
         "fruitfly/flybody_habitat.py", "fruitfly/flybody_persistent_task.py", "fruitfly/flybody_airflow.py",
         "configs/male-flybody-rolling-habitat.json", "tests/test_flybody_habitat.py",
         "validation/flybody-habitat-design-plan.json", "validation/flybody-source-manifest.json",
         "validation/flybody-walking-acquisition.json", "validation/flybody-stance-actuator-audit.json"]
CASES = ["frozen_default", "new_default", "rolling_prefix", "habitat_wall_push", "offset_geometry"]
ARRAY_FIELDS = ["qpos", "qvel", "qacc", "act", "ctrl", "canonical_action", "native_action",
    "pose_cm_quat", "target_pose_cm_quat", "actuator_force_preceding_stage", "actuator_length",
    "actuator_activation", "velocity_world_mm_s", "angular_velocity_world_rad_s", "support_dyne_by_leg",
    "ground_force_g_mm_s2", "antenna_positions_mm", "claw_positions_mm", "warnings"]
READONLY_FIELDS = ["qpos", "qvel", "qacc", "act", "ctrl", "sensordata", "xpos", "xmat", "cvel"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def prepare():
    if PLAN.exists() or RESULT.exists():
        raise FileExistsError("Preserve earlier habitat plan/results")
    from dataclasses import asdict
    from fruitfly.flybody_bridge import FlyBodyConfig
    design = json.loads((ROOT/"validation/flybody-habitat-design-plan.json").read_text())
    config = asdict(FlyBodyConfig())
    config["source_path"] = str(ROOT/config["source_path"])
    write(PLAN,{"schema":1,"prepared_utc":datetime.now(timezone.utc).isoformat(),
        "source_sha256":{p:sha(ROOT/p) for p in FILES},"baseline":design["frozen_baseline_worker"],
        "seed":11,"config":config,"cases":CASES,
        "commands":{"frozen_default":"1000 ticks: walk 20 mm/s yaw 0 for [0,.6) and [1.2,2); rest otherwise",
            "new_default":"Same 1000 ticks and original bounded mode",
            "rolling_prefix":"250 ticks: walk 20 mm/s yaw 0; rolling, no habitat",
            "habitat_wall_push":"At most 600 ticks: walk 20 mm/s yaw 0; 30x24 mm centered habitat; stop only at source exception/termination or 1.2 s",
            "offset_geometry":"Zero policy/control steps; center (1,-1) mm, same dimensions; compiled geometry and overview render"},
        "physical_clocks_s":{"physics":.0002,"control":.002},
        "gates":{"legacy":"Every sampled old state field and actual float32 actor value is exactly equal for reset plus all 1000 control steps",
            "precontact":"Exact old fields and actual float32 actor equality for reset plus all 250 rolling control steps; no habitat wall contacts in this prefix",
            "contact":"Actual active wall contact and nonzero force during bounded positive-x trial; retain all outcomes including native physical failure",
            "containment":"Root XY inside inner rectangle at every saved positive-x trial sample; does not establish full mesh containment or zero soft penetration",
            "geometry":"Four compiled collidable walls with copied compiled floor friction/solref/solimp, correct mm/cm sizes; same-center resource footprints and offset visible plane",
            "detached":"Four separately labeled translated-root contact probes at reset; mj_forward on copies only; no policy steps. Save qpos, qvel and diagnostic contacts",
            "reset_render":"Explicit reset after retaining trial endpoint; exact initial native state/actor; three render cameras with sampled native arrays/observations/time unchanged"},
        "guard_policy":"Keep strict native qacc norm 1e14, speed 50 cm/s, angular speed 200 rad/s, reference error .3 cm. No gains, steering, recentering or parameter changes.",
        "limits":["Finite-height open top over original infinite collision plane; no indefinite containment or avoidance claim",
            "Source female-derived body and learned walking controller, no male morphology claim",
            "Food/water are noncolliding planar regions; no liquid physics or wall-based ingestion",
            "Odor puffs retain unbounded uniform advection without wall-flow/odor-boundary coupling",
            "Diagnostics at .002 s endpoints; raw force arrays are the worker preceding force stage plus detached endpoint floor/wall forces, not every .0002 s substep"],
        "lightweight_test_command":".venv/bin/python -m pytest tests/test_flybody_habitat.py tests/test_flybody_bridge.py -q"})
    print("Frozen habitat execution plan",sha(PLAN),flush=True)


def verify(plan):
    for p,h in plan["source_sha256"].items():
        if sha(ROOT/p)!=h:
            raise ValueError("Frozen habitat source changed: "+p)
    if sha(ROOT/plan["baseline"]["path"])!=plan["baseline"]["sha256"]:
        raise ValueError("Frozen baseline changed")


def data_dir():
    return ROOT/"runs"/("flybody-habitat-"+sha(PLAN)[:12])


def observed_class(path, name):
    import numpy as np
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT  # Asset lookup only; loaded source bytes remain frozen.
    class ObservedWorker(module.Worker):
        def _policy(self, observation):
            self.actor_keys = list(observation)
            self.actor_shapes = {k:list(np.asarray(v).shape) for k,v in observation.items()}
            self.actor_values = np.concatenate([np.asarray(v,np.float32).ravel() for v in observation.values()]).astype('<f4')
            return super()._policy(observation)
    return ObservedWorker, module


def snapshot(worker):
    import numpy as np
    return {"arrays":{k:sha_bytes(np.asarray(getattr(worker.d,k)).tobytes()) for k in READONLY_FIELDS},
        "time":float(worker.d.time),"actor":worker.actor_input_sha256,
        "cached_observation":{k:sha_bytes(np.asarray(v).tobytes()) for k,v in worker.step_result.observation.items()}}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def guards(worker):
    import numpy as np
    task,physics = worker.env.task,worker.env.physics
    return {"qacc_norm":float(np.linalg.norm(worker.d.qacc)),
        "linear_cm_s":float(np.linalg.norm(task._walker.observables.velocimeter(physics))),
        "angular_rad_s":float(np.linalg.norm(task._walker.observables.gyro(physics))),
        "reference_error_cm":float(np.linalg.norm(task.observables['walker/ref_displacement'](physics)[0]))}


def inspect_geometry(worker):
    import numpy as np
    m,h = worker.m,worker.habitat
    fid = m.name2id(h.floor_identifier,"geom")
    record = copy.deepcopy(h.metadata)
    record["floor_contact_parameters"] = {k:getattr(m,k)[fid].tolist() for k in ("geom_friction","geom_solref","geom_solimp")}
    record["floor_contype"] = int(m.geom_contype[fid])
    record["floor_conaffinity"] = int(m.geom_conaffinity[fid])
    record["floor_condim"] = int(m.geom_condim[fid])
    record["wall_condim"] = [int(m.geom_condim[g]) for g in h.wall_ids]
    half = np.asarray(h.config.inner_size_mm)/2
    center = np.asarray(h.config.center_mm)
    height,thickness = h.config.wall_height_mm,h.config.wall_thickness_mm
    checks = {"floor_center":bool(np.array_equal(m.geom_pos[fid,:2]*10,center)),
        "visible_extent":bool(np.allclose(m.geom_size[fid,:2]*10,half+thickness,rtol=0,atol=1e-14))}
    for i,gid in enumerate(h.wall_ids):
        axis,sign = i//2,(-1 if i%2==0 else 1)
        pos = np.r_[center,h.floor_z_cm*10+height/2]
        pos[axis] += sign*(half[axis]+thickness/2)
        size = np.r_[half,height/2]
        size[axis] = thickness/2
        if axis==0:
            size[1] += thickness
        checks[m.id2name(gid,"geom")+"_geometry"] = bool(np.allclose(m.geom_pos[gid]*10,pos,rtol=0,atol=1e-14) and np.allclose(m.geom_size[gid]*10,size,rtol=0,atol=1e-14))
        checks[m.id2name(gid,"geom")+"_contact"] = bool(m.geom_contype[gid]==m.geom_conaffinity[gid]==1
            and m.geom_condim[gid]==m.geom_condim[fid]
            and all(np.array_equal(getattr(m,k)[gid],getattr(m,k)[fid]) for k in ("geom_friction","geom_solref","geom_solimp")))
    for kind,region in record["resource_regions"].items():
        checks[kind+"_footprint"] = bool(np.array_equal(region["center_mm"][:2],worker.config[kind+"_position_mm"])
            and region["radius_mm"]==worker.config[kind+"_radius_mm"] and not region["separate_collision_geometry"])
    return {"metadata":record,"checks":checks}


def detached_probes(worker):
    import mujoco
    import numpy as np
    before = snapshot(worker)
    m,d,h = worker.m,worker.d,worker.habitat
    bid = worker.root_id
    joint = None
    while bid:
        for j in range(int(m.body_jntadr[bid]),int(m.body_jntadr[bid]+m.body_jntnum[bid])):
            if m.jnt_type[j]==mujoco.mjtJoint.mjJNT_FREE:
                joint = j
        if joint is not None:
            break
        bid = int(m.body_parentid[bid])
    if joint is None:
        raise ValueError("No native free root joint")
    adr = int(m.jnt_qposadr[joint])
    probes = []
    for i,gid in enumerate(h.wall_ids):
        axis,sign = i//2,(-1 if i%2==0 else 1)
        data = copy.copy(d.ptr)
        desired = np.asarray(h.config.center_mm)/10
        desired[axis] += sign*(h.config.inner_size_mm[axis]/20-.02)
        delta = desired-np.asarray(worker.state["pose_cm_quat"][:2])
        data.qpos[adr:adr+2] += delta
        mujoco.mj_forward(m.ptr,data)
        sample = h.sample(m,data,data.xpos[worker.root_id])
        matches = [c for c in sample["wall_contacts"] if c["wall"]==m.id2name(gid,"geom") and c["active"]]
        forces = np.sum([c["force_world_dyne_on_fly"] for c in matches],axis=0) if matches else np.zeros(3)
        probes.append({"wall":m.id2name(gid,"geom"),"free_joint":m.id2name(joint,"joint"),"qpos_address":adr,
            "root_translation_cm":delta.tolist(),"qpos":data.qpos.tolist(),"qvel":data.qvel.tolist(),
            "sample":sample,"native_time_s":float(data.time),"policy_steps":0,
            "active_count":len(matches),"summed_force_world_dyne_on_fly":forces.tolist(),
            "inward_normal_force":bool(sign*forces[axis]<0)})
    after = snapshot(worker)
    return {"probes":probes,"before":before,"after":after,"sampled_live_state_unchanged":before==after,
        "evidence_scope":"Nine named native arrays, time, actor hash and cached observations. Detached translated-root poses use forward computation only, no integrated trajectory or empirical wall behavior."}


def run_case(case,plan):
    import numpy as np
    from PIL import Image
    directory = data_dir()
    result_path = directory/(case+".json")
    if result_path.exists():
        raise FileExistsError("Preserve completed case")
    config = copy.deepcopy(plan["config"])
    if case not in ("frozen_default","new_default"):
        config.update(reference_mode="rolling",horizon_s=None)
    if case in ("habitat_wall_push","offset_geometry"):
        config["habitat"] = {"inner_size_mm":[30.,24.],"center_mm":[0.,0.] if case=="habitat_wall_push" else [1.,-1.],
            "wall_height_mm":6.,"wall_thickness_mm":1.}
    path = ROOT/(plan["baseline"]["path"] if case=="frozen_default" else "fruitfly/flybody_worker.py")
    worker_class,module = observed_class(path,"habitat_worker_"+case)
    worker = None
    rows,actors = [],[]
    result = {"case":case,"plan_sha256":sha(PLAN),"config":config,"worker_path":str(path),"worker_sha256":sha(path)}
    journal_path = directory/(case+"-states.jsonl.gz")
    try:
        worker = worker_class(config,plan["seed"])
        result["metadata"] = worker.metadata()
        result["actor_keys"] = worker.actor_keys
        result["actor_shapes"] = worker.actor_shapes
        initial = copy.deepcopy(worker.state)
        initial_actor = worker.actor_values.copy()
        with gzip.open(journal_path,"wt") as stream:
            def record():
                row = copy.deepcopy(worker.state)
                row["guard_diagnostics"] = guards(worker)
                rows.append(row)
                actors.append(worker.actor_values.copy())
                stream.write(json.dumps(module.clean_json(row),allow_nan=False,separators=(",",":"))+"\n")
                stream.flush()
            record()
            if config["habitat"] is not None:
                result["geometry"] = inspect_geometry(worker)
                if case=="habitat_wall_push":
                    result["detached_contact_probes"] = detached_probes(worker)
                before = snapshot(worker)
                rgb = worker.render("overview")
                Image.fromarray(rgb).save(directory/(case+"-initial-overview.png"))
                result["initial_render_unchanged"] = before==snapshot(worker)
            limit = 1000 if case in ("frozen_default","new_default") else (250 if case=="rolling_prefix" else (600 if case=="habitat_wall_push" else 0))
            for tick in range(limit):
                on = case not in ("frozen_default","new_default") or tick<300 or tick>=600
                command = (20.,0.,"walk") if on else (0.,0.,"rest")
                try:
                    worker.advance(*command)
                except Exception as exc:
                    result["native_failure"] = {"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc(),
                        "attempted_interval":tick,"native_time_s":float(worker.d.time),"worker_failed":worker.failed}
                    record()
                    break
                record()
                if (tick+1)%250==0:
                    print(case,"native ticks",tick+1,flush=True)
        result["samples"] = len(rows)
        result["completed_control_intervals"] = worker.tick
        result["endpoint"] = rows[-1]
        if case=="habitat_wall_push":
            endpoint = copy.deepcopy(worker.state)
            if worker.failed:
                before = snapshot(worker)
                try:
                    worker.advance(20.,0.,"walk")
                except RuntimeError as exc:
                    result["failure_latch"] = {"message":str(exc),"sampled_state_unchanged":before==snapshot(worker)}
            result["endpoint_render"] = {}
            for camera in ("overview","follow","side"):
                before = snapshot(worker)
                Image.fromarray(worker.render(camera)).save(directory/(case+"-endpoint-"+camera+".png"))
                result["endpoint_render"][camera] = {"sampled_state_unchanged":before==snapshot(worker)}
            worker.reset(plan["seed"])
            result["reset"] = {"initial_state_exact":worker.state==initial,"actual_actor_exact":bool(np.array_equal(worker.actor_values,initial_actor)),
                "failed_cleared":not worker.failed,"time_s":float(worker.d.time),"metadata_geometry_exact":worker.metadata()["habitat"]==result["metadata"]["habitat"],
                "initial_state":worker.state,"retained_endpoint_equal":endpoint=={k:v for k,v in rows[-1].items() if k!="guard_diagnostics"}}
        result["operational_error"] = None
    except Exception as exc:
        result["operational_error"] = {"type":type(exc).__name__,"message":str(exc),"traceback":traceback.format_exc()}
    finally:
        if rows:
            np.savez_compressed(directory/(case+"-arrays.npz"),actor=np.asarray(actors,dtype='<f4'),
                native_time_s=np.asarray([r["native_time_s"] for r in rows]),tick=np.asarray([r["tick"] for r in rows]),
                **{key:np.asarray([r[key] for r in rows]) for key in ARRAY_FIELDS})
        if worker is not None:
            worker.close()
        result["artifacts"] = {str(p.relative_to(ROOT)):sha(p) for p in sorted(directory.glob(case+"-*")) if p.is_file()}
        write(result_path,module.clean_json(result))
    print(json.dumps({"case":case,"samples":result.get("samples"),"native_failure":bool(result.get("native_failure")),"operational_error":result.get("operational_error")}),flush=True)


def summarize(plan):
    import numpy as np
    directory = data_dir()
    reports = {case:json.loads((directory/(case+".json")).read_text()) for case in CASES}
    checks = {}
    states = {}
    arrays = {}
    for case,r in reports.items():
        checks[case+"_operational"] = r.get("operational_error") is None
        if not checks[case+"_operational"]:
            continue
        with gzip.open(directory/(case+"-states.jsonl.gz"),"rt") as stream:
            states[case] = [json.loads(line) for line in stream]
        with np.load(directory/(case+"-arrays.npz")) as z:
            arrays[case] = {k:z[k] for k in z.files}
        checks[case+"_actor_hashes"] = all(sha_bytes(a.tobytes())==r["actor_input_sha256"] for a,r in zip(arrays[case]["actor"],states[case]))
        checks[case+"_clocks"] = bool(np.max(abs(arrays[case]["native_time_s"]-arrays[case]["tick"]*.002))<1e-10)
        checks[case+"_finite"] = all(s["finite"] and all(np.isfinite(v).all() for v in arrays[case].values()) for s in states[case])
        checks[case+"_warnings_zero"] = bool(not arrays[case]["warnings"].any())
        if "geometry" in r:
            checks.update({case+"_"+k:v for k,v in r["geometry"]["checks"].items()})
            checks[case+"_initial_render"] = r["initial_render_unchanged"]
    for left,right,count,label in (("frozen_default","new_default",1001,"legacy"),("rolling_prefix","habitat_wall_push",251,"precontact")):
        if left not in states or right not in states:
            checks[label+"_available"] = False
            continue
        checks[label+"_length"] = min(len(states[left]),len(states[right]))>=count
        mismatches = []
        for tick,(a,b) in enumerate(zip(states[left][:count],states[right][:count])):
            for key,value in a.items():
                if value!=b.get(key):
                    mismatches.append({"tick":tick,"field":key})
        checks[label+"_state_exact"] = not mismatches and checks[label+"_length"]
        checks[label+"_actor_exact"] = bool(np.array_equal(arrays[left]["actor"][:count],arrays[right]["actor"][:count]))
        reports[right][label+"_mismatches"] = mismatches[:100]
    trial = reports["habitat_wall_push"]
    outcome = None
    if "habitat_wall_push" in states:
        rows = states["habitat_wall_push"]
        allcontacts = [(i,c) for i,r in enumerate(rows) for c in r["habitat"]["wall_contacts"]]
        active = [(i,c) for i,c in allcontacts if c["active"] and np.linalg.norm(c["force_world_dyne_on_fly"])>0]
        checks["prefix_no_wall_contact"] = all(not r["habitat"]["wall_contacts"] for r in rows[:251])
        checks["wall_active_force_observed"] = bool(active)
        checks["root_xy_contained_all_samples"] = all(r["habitat"]["root_inside_inner_xy"] for r in rows)
        probes = trial.get("detached_contact_probes",{})
        checks["detached_probes_no_live_mutation"] = probes.get("sampled_live_state_unchanged",False)
        checks["all_four_wall_probes_inward_contact"] = len(probes.get("probes",[]))==4 and all(p["active_count"]>0 and p["inward_normal_force"] for p in probes["probes"])
        reset = trial.get("reset",{})
        checks["reset_exact"] = all(reset.get(k,False) for k in ("initial_state_exact","actual_actor_exact","failed_cleared","metadata_geometry_exact","retained_endpoint_equal"))
        checks["three_camera_sampled_state_unchanged"] = len(trial.get("endpoint_render",{}))==3 and all(c["sampled_state_unchanged"] for c in trial["endpoint_render"].values())
        if trial.get("native_failure"):
            checks["failed_state_latched"] = trial.get("failure_latch",{}).get("sampled_state_unchanged",False)
        outcome = {"end_time_s":rows[-1]["native_time_s"],"endpoint_root_mm":rows[-1]["habitat"]["root_position_mm"],
            "first_contact_time_s":rows[allcontacts[0][0]]["native_time_s"] if allcontacts else None,
            "first_active_force_time_s":rows[active[0][0]]["native_time_s"] if active else None,
            "minimum_contact_distance_mm":min((c["dist_mm"] for _,c in allcontacts),default=None),
            "maximum_contact_force_dyne":max((float(np.linalg.norm(c["force_world_dyne_on_fly"])) for _,c in allcontacts),default=None),
            "active_contact_samples":len(set(i for i,c in active)),"native_failure":trial.get("native_failure"),
            "endpoint_guard_diagnostics":rows[-1]["guard_diagnostics"],"source_terminated":rows[-1]["source_terminated"],
            "interpretation":"A retained physical failure is an outcome, not avoidance or sustained-controller success. Gate pass covers geometry, unchanged prefix, diagnostics and tested root containment."}
    verify(plan)
    write(RESULT,{"schema":1,"plan_sha256":sha(PLAN),"passed":bool(checks) and all(checks.values()),"checks":checks,
        "check_count":len(checks),"wall_trial_outcome":outcome,"cases":reports,
        "data_directory":str(directory.relative_to(ROOT)),"artifacts":{str(p.relative_to(ROOT)):sha(p) for p in sorted(directory.iterdir()) if p.is_file()},
        "limits":plan["limits"]})
    print(json.dumps({"passed":all(checks.values()),"checks":len(checks),"failed":[k for k,v in checks.items() if not v],"wall_trial_outcome":outcome}),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true")
    mode.add_argument("--run",action="store_true")
    mode.add_argument("--case",choices=CASES)
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return
    plan = json.loads(PLAN.read_text())
    verify(plan)
    directory = data_dir()
    if args.case:
        run_case(args.case,plan)
        return
    if RESULT.exists() or directory.exists():
        raise FileExistsError("Preserve previous habitat execution")
    directory.mkdir()
    for case in CASES:
        env = dict(os.environ,TF_CPP_MIN_LOG_LEVEL="2",CUDA_VISIBLE_DEVICES="-1",OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1")
        with (directory/(case+".log")).open("wb") as stream:
            result = subprocess.run([str(ROOT/"tmp/flybody-env/bin/python"),str(Path(__file__).resolve()),"--case",case],
                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        print(case,"process exit",result.returncode,flush=True)
        if result.returncode:
            raise RuntimeError("Case process failed; raw log retained: "+case)
    summarize(plan)


if __name__=="__main__":
    main()
