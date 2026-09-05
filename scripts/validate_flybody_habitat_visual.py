"""Prove habitat scene edits do not enter native model/data or actor inputs."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

for key,value in {"TF_CPP_MIN_LOG_LEVEL":"2","CUDA_VISIBLE_DEVICES":"-1","OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1"}.items():
    os.environ[key] = value
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import validate_flybody_habitat as original

PLAN = ROOT/"validation/flybody-habitat-visual-execution-plan.json"
RESULT = ROOT/"validation/flybody-habitat-visual-results.json"
FILES = ["scripts/validate_flybody_habitat_visual.py", "scripts/validate_flybody_habitat.py",
    "fruitfly/flybody_worker.py", "fruitfly/flybody_habitat.py", "fruitfly/flybody_bridge.py", "fruitfly/flybody_persistent_task.py",
    "validation/flybody-habitat-visual-design-plan.json", "validation/flybody-habitat-results.json"]


def verify(plan):
    for path,digest in plan["source_sha256"].items():
        if original.sha(ROOT/path)!=digest:
            raise ValueError("Visual source changed: "+path)


def model_bytes(worker):
    import numpy as np
    import mujoco
    buffer = np.empty(mujoco.mj_sizeModel(worker.m.ptr),dtype=np.uint8)
    mujoco.mj_saveModel(worker.m.ptr,buffer=buffer)
    return buffer.tobytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true")
    mode.add_argument("--run",action="store_true")
    args = parser.parse_args()
    prior = json.loads(original.RESULT.read_text())
    if args.prepare:
        if PLAN.exists() or RESULT.exists():
            raise FileExistsError("Preserve prior visual proof")
        original.write(PLAN,{"schema":1,"source_sha256":{p:original.sha(ROOT/p) for p in FILES},
            "config":prior["cases"]["habitat_wall_push"]["config"],"seed":11,"parity_intervals":100,
            "render_cameras":["overview","follow","side","overview"],
            "scene_only":"Resource cylinder display center +0.05 mm Z; ghost geom/traj site display alpha 0. All compiled geometry/sensing left unchanged.",
            "native_model_check":"Entire compiled MjModel serialized with mj_saveModel before/after each render; identical MJB bytes",
            "native_data_check":"Nine explicit arrays from original snapshot, all cached observations, actor hash and native time. Save actual arrays/actor before/after paused renders",
            "parity_check":"Reset and 100 control ticks after paused renders vs first 101 saved actual actor/native samples from original habitat wall trial; identical state fields including raw contact diagnostics",
            "legacy_camera_check":"Habitat disabled: no callback and rendered output unchanged vs manually constructed source MovableCamera at identical pose",
            "scope":"Small renderer/native parity check, no new wall run or change to prior outcomes. Visual offset is not food height or collision geometry."})
        print("Frozen visual execution plan",original.sha(PLAN),flush=True)
        return
    if RESULT.exists():
        raise FileExistsError("Preserve prior visual proof")
    plan = json.loads(PLAN.read_text())
    verify(plan)
    import numpy as np
    from PIL import Image
    directory = ROOT/"runs"/("flybody-habitat-visual-"+original.sha(PLAN)[:12])
    directory.mkdir()
    worker_class,module = original.observed_class(ROOT/"fruitfly/flybody_worker.py","habitat_visual_worker")
    worker = worker_class(plan["config"],plan["seed"])
    checks,records = {},[]
    with gzip.open(ROOT/prior["data_directory"]/"habitat_wall_push-states.jsonl.gz","rt") as stream:
        old_rows = [json.loads(line) for line in stream]
    with np.load(ROOT/prior["data_directory"]/"habitat_wall_push-arrays.npz") as z:
        old_actor = z["actor"].copy()
    before_arrays = {k:np.asarray(getattr(worker.d,k)).copy() for k in original.READONLY_FIELDS}
    actor_before = worker.actor_values.copy()
    try:
        for index,camera in enumerate(plan["render_cameras"]):
            before = original.snapshot(worker)
            before_model = model_bytes(worker)
            rgb = worker.render(camera)
            after = original.snapshot(worker)
            after_model = model_bytes(worker)
            path = directory/(str(index)+"-"+camera+".png")
            Image.fromarray(rgb).save(path)
            edits = worker.habitat.last_render_scene_edits
            resource_edits = [e for e in edits if e["change"]=="resource_marker_lift"]
            checks[camera+str(index)+"_model_identical"] = before_model==after_model
            checks[camera+str(index)+"_native_identical"] = before==after
            checks[camera+str(index)+"_two_resource_lifts"] = len(resource_edits)==2 and all(
                np.array_equal(e["before"]["position_cm"][:2],e["after"]["position_cm"][:2])
                and abs(e["after"]["position_cm"][2]-e["before"]["position_cm"][2]-.005)<1e-8 for e in resource_edits)
            checks[camera+str(index)+"_ghost_hidden"] = any(e["change"]=="hide_reference_ghost" for e in edits)
            checks[camera+str(index)+"_trajectory_hidden"] = any(e["change"]=="hide_reference_trajectory" for e in edits)
            records.append({"camera":camera,"image":str(path.relative_to(ROOT)),"image_sha256":original.sha(path),
                "sampled_state_before":before,"sampled_state_after":after,"model_before_sha256":original.sha_bytes(before_model),
                "model_after_sha256":original.sha_bytes(after_model),"scene_edits":edits})
        np.savez_compressed(directory/"paused-arrays.npz",actor_before=actor_before,actor_after=worker.actor_values,
            **{"before_"+k:v for k,v in before_arrays.items()},
            **{"after_"+k:np.asarray(getattr(worker.d,k)) for k in original.READONLY_FIELDS})
        mismatches = []
        rows,actors = [],[]
        for tick in range(plan["parity_intervals"]+1):
            if tick:
                worker.advance(20.,0.,"walk")
            state = dict(worker.state,guard_diagnostics=original.guards(worker))
            rows.append(state)
            actors.append(worker.actor_values.copy())
            for key,value in old_rows[tick].items():
                if state.get(key)!=value:
                    mismatches.append({"tick":tick,"field":key})
        with gzip.open(directory/"parity-states.jsonl.gz","wt") as stream:
            for row in rows:
                stream.write(json.dumps(row,separators=(",",":"),allow_nan=False)+"\n")
        np.savez_compressed(directory/"parity-actor.npz",actor=np.asarray(actors))
        checks["actual_actor_parity"] = np.array_equal(actors,old_actor[:len(actors)])
        checks["all_saved_native_state_parity"] = not mismatches
        checks["100_control_ticks"] = worker.tick==100
        metadata = worker.metadata()
        worker.close()
        config = dict(plan["config"],habitat=None)
        worker = worker_class(config,plan["seed"])
        before = original.snapshot(worker)
        current_image = worker.render("overview")
        from dm_control.mujoco.engine import MovableCamera
        reference_camera = MovableCamera(worker.env.physics,height=config["height"],width=config["width"])
        reference_camera.set_pose(lookat=[0.,0.,0.],distance=5.,azimuth=135,elevation=-55)
        source_image = reference_camera.render().copy()
        checks["default_no_scene_callback"] = worker.camera._scene_callback is None
        checks["default_source_camera_pixels_exact"] = np.array_equal(current_image,source_image)
        checks["default_render_native_unchanged"] = before==original.snapshot(worker)
        del reference_camera
        verify(plan)
        checks["source_hashes_unchanged"] = True
        original.write(RESULT,{"schema":1,"plan_sha256":original.sha(PLAN),"passed":bool(all(checks.values())),
            "checks":{k:bool(v) for k,v in checks.items()},"check_count":len(checks),"renders":records,
            "metadata":metadata,"parity_mismatches":mismatches,"parity_samples":len(rows),"data_directory":str(directory.relative_to(ROOT)),
            "artifacts":{str(p.relative_to(ROOT)):original.sha(p) for p in directory.iterdir()},"scope":plan["scope"]})
        print(json.dumps({"passed":bool(all(checks.values())),"checks":len(checks),"failed":[k for k,v in checks.items() if not v]}),flush=True)
    finally:
        worker.close()


if __name__=="__main__":
    main()
