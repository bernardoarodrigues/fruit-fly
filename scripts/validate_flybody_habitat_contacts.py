"""Separate zero-step shallow wall probes; preserve the initial deep-overlap failure."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

for key,value in {"TF_CPP_MIN_LOG_LEVEL":"2","CUDA_VISIBLE_DEVICES":"-1","OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1"}.items():
    os.environ[key] = value
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import validate_flybody_habitat as original

PLAN = ROOT/"validation/flybody-habitat-shallow-contact-plan.json"
RESULT = ROOT/"validation/flybody-habitat-shallow-contact-results.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true")
    mode.add_argument("--run",action="store_true")
    args = parser.parse_args()
    old_plan = json.loads(original.PLAN.read_text())
    original.verify(old_plan)
    if args.prepare:
        if PLAN.exists() or RESULT.exists():
            raise FileExistsError("Preserve previous shallow-contact proof")
        original.write(PLAN,{"schema":1,"prepared_utc":datetime.now(timezone.utc).isoformat(),
            "source_sha256":{**old_plan["source_sha256"],
                "scripts/validate_flybody_habitat_contacts.py":original.sha(__file__),
                "validation/flybody-habitat-execution-plan.json":original.sha(original.PLAN),
                "validation/flybody-habitat-results.json":original.sha(original.RESULT)},
            "reason":"Initial detached positive-x pose produced penetration up to 1.543 mm across a 1 mm wall and contacts on multiple box faces. Its net inward-force gate failed. Preserve that result; test a defined shallow contact boundary separately.",
            "physics_steps":0,"policy_advances":0,"seed":11,"bisection_iterations":40,"additional_translation_mm":.01,
            "maximum_penetration_mm":.02,"inner_plane_distance_tolerance_mm":.02,
            "protocol":"For each wall use source reset as no-contact lower bound and the saved original deep-overlap pose as contact upper bound. On fresh MjData copies bisect the scalar root XY translation 40 times by presence of target-wall active contact. Translate 0.01 mm beyond first contact along the same inward-to-outward axis and mj_forward a fresh copy. Never assign the probe pose to live data.",
            "gates":["Both initial bisection brackets valid","Four shallow probes have active contacts and net force inward",
                "Every target contact depth is at most 0.02 mm and point lies within 0.02 mm of inner wall plane",
                "Raw local force and frame reconstruct world force exactly; contact normals point toward habitat interior",
                "Nine named live native arrays, native clock, actual actor hash and cached observation bytes remain identical",
                "No policy, native integration or neural steps; source files unchanged"],
            "limits":"Static source-pose collision geometry/solver probes only. No dynamic reliability or avoidance claim; original controller termination remains unchanged."})
        print("Frozen shallow-contact plan",original.sha(PLAN),flush=True)
        return
    if RESULT.exists():
        raise FileExistsError("Preserve previous shallow-contact proof")
    plan = json.loads(PLAN.read_text())
    for path,digest in plan["source_sha256"].items():
        if original.sha(ROOT/path)!=digest:
            raise ValueError("Shallow-contact source changed: "+path)
    import numpy as np
    import mujoco
    old = json.loads(original.RESULT.read_text())
    original_trial = old["cases"]["habitat_wall_push"]
    worker_class,module = original.observed_class(ROOT/"fruitfly/flybody_worker.py","shallow_contact_worker")
    worker = worker_class(original_trial["config"],plan["seed"])
    checks,probes = {},[]
    before = original.snapshot(worker)
    initial = {k:np.asarray(getattr(worker.d,k)).tolist() for k in original.READONLY_FIELDS}
    m,h = worker.m,worker.habitat
    try:
        for index,old_probe in enumerate(original_trial["detached_contact_probes"]["probes"]):
            axis,sign = index//2,(-1 if index%2==0 else 1)
            wall = old_probe["wall"]
            gid = m.name2id(wall,"geom")
            adr = old_probe["qpos_address"]
            upper_translation = np.asarray(old_probe["root_translation_cm"])
            def sample(fraction,extra_cm=0.):
                data = copy.copy(worker.d.ptr)
                delta = upper_translation*fraction
                delta[axis] += sign*extra_cm
                data.qpos[adr:adr+2] += delta
                mujoco.mj_forward(m.ptr,data)
                result = h.sample(m,data,data.xpos[worker.root_id])
                contacts = [c for c in result["wall_contacts"] if c["wall"]==wall and c["active"]]
                return data,delta,result,contacts
            lower_contacts = sample(0.)[3]
            upper_contacts = sample(1.)[3]
            checks[wall+"_brackets"] = not lower_contacts and bool(upper_contacts)
            low,high = 0.,1.
            history = []
            for iteration in range(plan["bisection_iterations"]):
                mid = (low+high)/2
                contacts = sample(mid)[3]
                history.append({"iteration":iteration,"fraction":mid,"target_active_contacts":len(contacts),
                    "min_target_distance_mm":min((c["dist_mm"] for c in contacts),default=None)})
                if contacts:
                    high = mid
                else:
                    low = mid
            data,delta,result,contacts = sample(high,plan["additional_translation_mm"]/10)
            forces = np.sum([c["force_world_dyne_on_fly"] for c in contacts],axis=0) if contacts else np.zeros(3)
            normals,inferred = [],[]
            for contact in contacts:
                orientation = 1. if contact["geom1"]==gid else -1.
                frame = np.asarray(contact["frame_world_rows"])
                local = np.asarray(contact["local_force_torque_dyne_dyne_cm"])
                normals.append((orientation*frame[0]).tolist())
                inferred.append(bool(np.array_equal(orientation*(local[:3]@frame),contact["force_world_dyne_on_fly"])))
            wall_plane = h.config.center_mm[axis]+sign*h.config.inner_size_mm[axis]/2
            checks[wall+"_active_inward_force"] = bool(contacts) and sign*forces[axis]<0
            checks[wall+"_inward_normals"] = bool(normals) and all(sign*n[axis]<0 for n in normals)
            checks[wall+"_shallow_contact"] = bool(contacts) and all(-plan["maximum_penetration_mm"]<=c["dist_mm"]<=0 for c in contacts)
            checks[wall+"_inner_face_points"] = bool(contacts) and all(abs(c["position_mm"][axis]-wall_plane)<=plan["inner_plane_distance_tolerance_mm"] for c in contacts)
            checks[wall+"_force_transform_exact"] = bool(inferred) and all(inferred)
            checks[wall+"_finite"] = bool(all(np.isfinite(c["position_mm"]+c["force_world_dyne_on_fly"]+c["local_force_torque_dyne_dyne_cm"]+[c["dist_mm"]]).all() for c in contacts))
            probes.append({"wall":wall,"compiled_wall_geom_id":gid,"axis":axis,"outward_sign":sign,"inner_plane_mm":wall_plane,
                "free_joint":old_probe["free_joint"],"qpos_address":adr,"upper_translation_cm":upper_translation.tolist(),
                "bisection_history":history,"final_bracket":[low,high],"root_translation_cm":delta.tolist(),
                "qpos":data.qpos.tolist(),"qvel":data.qvel.tolist(),"sample":result,"native_time_s":float(data.time),
                "active_target_count":len(contacts),"inward_normals_world":normals,"summed_force_world_dyne_on_fly":forces.tolist()})
        after = original.snapshot(worker)
        final = {k:np.asarray(getattr(worker.d,k)).tolist() for k in original.READONLY_FIELDS}
        checks["sampled_live_native_state_unchanged"] = before==after and initial==final
        checks["zero_native_policy_steps"] = worker.tick==0 and worker.d.time==0
        checks["source_hashes_unchanged"] = all(original.sha(ROOT/p)==v for p,v in plan["source_sha256"].items())
        original.write(RESULT,{"schema":1,"plan_sha256":original.sha(PLAN),"passed":bool(checks) and bool(all(checks.values())),
            "checks":{k:bool(v) for k,v in checks.items()},"check_count":len(checks),"probes":probes,
            "sampled_state_before":before,"sampled_state_after":after,"native_arrays_before":initial,"native_arrays_after":final,
            "native_array_names":original.READONLY_FIELDS,"initial_actor_values_f32":worker.actor_values.tolist(),
            "metadata":worker.metadata(),"original_failure_retained":str(original.RESULT.relative_to(ROOT)),
            "original_failure_receipt_sha256":original.sha(original.RESULT),"physics_steps":0,"policy_advances":0,"limits":plan["limits"]})
        print(json.dumps({"passed":bool(all(checks.values())),"checks":len(checks),"failed":[k for k,v in checks.items() if not v]}),flush=True)
    finally:
        worker.close()


if __name__=="__main__":
    main()
