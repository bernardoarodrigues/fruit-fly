"""Final scene-removal proof; retain previous visual flaws and physical failures."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import validate_flybody_habitat_visual as visual
import validate_flybody_habitat as original

PLAN = ROOT/"validation/flybody-habitat-scene-execution-plan.json"
RESULT = ROOT/"validation/flybody-habitat-scene-results.json"
FILES = ["scripts/validate_flybody_habitat_scene.py","scripts/validate_flybody_habitat_visual.py",
    "scripts/validate_flybody_habitat.py","fruitfly/flybody_worker.py","fruitfly/flybody_habitat.py",
    "fruitfly/flybody_bridge.py","fruitfly/flybody_persistent_task.py",
    "validation/flybody-habitat-scene-design-plan.json","validation/flybody-habitat-results.json",
    "validation/flybody-habitat-visual-results.json","validation/flybody-habitat-render-diagnostic-results.json"]


def verify(plan):
    assert all(original.sha(ROOT/p)==h for p,h in plan["source_sha256"].items())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare",action="store_true")
    args = parser.parse_args()
    if args.prepare:
        assert not PLAN.exists()
        original.write(PLAN,{"source_sha256":{p:original.sha(ROOT/p) for p in FILES},"seed":11,
            "cameras":["overview","follow","side","overview"],"parity_intervals":100,
            "scope":"Remove source reference ghost/trajectory visual geoms from disposable scene, retain marker lift. No compiled/native/controller/neural edits.",
            "gates":["Final scenes contain no ghost geom or traj site IDs; removed list matches every such source scene entry",
                "Every surviving public MjvGeom field equals original except specified resource Z lift and compact segmentation indices",
                "Whole compiled MJB bytes and nine native arrays, actor hash, cached observations and time equal before/after all four renders",
                "Reset plus 100 native intervals and 741-value actor samples equal retained original habitat trial",
                "Default habitat-null worker still has no scene callback; its paused render preserves model/native data"],
            "manual_visual_check":"Inspect overview/follow/side PNGs for reference dots/ghost shadow/reflection artifacts and smooth resource markers; retain source floor reflection of the actual fly.",
            "retained_failures":"Original 64/65 physical/probe receipt, 29/31 shallow probe receipt, 26/27 v1 renderer receipt and close-view alpha-shadow flaw remain unchanged."})
        print("Frozen scene execution plan",original.sha(PLAN),flush=True)
        return
    assert not RESULT.exists()
    plan = json.loads(PLAN.read_text());verify(plan)
    import numpy as np
    import mujoco
    from PIL import Image
    from fruitfly.flybody_habitat import SCENE_GEOM_FIELDS
    prior = json.loads(original.RESULT.read_text())
    config = prior["cases"]["habitat_wall_push"]["config"]
    cls,module = original.observed_class(ROOT/"fruitfly/flybody_worker.py","scene_removal_worker")
    worker = cls(config,plan["seed"])
    directory = ROOT/"runs"/("flybody-habitat-scene-"+original.sha(PLAN)[:12]);directory.mkdir()
    checks,renders = {},[]
    callback = worker.habitat.render_scene_callback
    def scene_values(scene):
        return [{k:(getattr(g,k).tolist() if isinstance(getattr(g,k),np.ndarray) else getattr(g,k)) for k in SCENE_GEOM_FIELDS}
            for g in scene.geoms[:scene.ngeom]]
    def observed_callback(physics,scene):
        worker.scene_before = scene_values(scene)
        callback(physics,scene)
        worker.scene_after = scene_values(scene)
    worker.habitat.render_scene_callback = observed_callback
    try:
        for index,camera in enumerate(plan["cameras"]):
            before = original.snapshot(worker);model_before = visual.model_bytes(worker)
            image = worker.render(camera)
            after = original.snapshot(worker);model_after = visual.model_bytes(worker)
            path = directory/(str(index)+"-"+camera+".png");Image.fromarray(image).save(path)
            expected,removed = [],[]
            for source in worker.scene_before:
                row = dict(source)
                is_site = row["objtype"]==int(mujoco.mjtObj.mjOBJ_SITE)
                ghost = row["objtype"]==int(mujoco.mjtObj.mjOBJ_GEOM) and row["objid"] in worker.habitat.visual_ghost_ids
                trajectory = is_site and row["objid"] in worker.habitat.visual_trajectory_ids
                if ghost or trajectory:
                    removed.append((row["objtype"],row["objid"]))
                    continue
                if is_site and row["objid"] in worker.habitat.visual_resource_ids:
                    position = np.asarray(row["pos"],dtype=np.float32);position[2] += .005
                    row["pos"] = position.tolist()
                if row["segid"]!=-1:
                    row["segid"] = len(expected)
                expected.append(row)
            suffix = camera+str(index)
            checks[suffix+"_entire_model_unchanged"] = model_before==model_after
            checks[suffix+"_native_actor_unchanged"] = before==after
            checks[suffix+"_survivor_fields_exact"] = expected==worker.scene_after
            checks[suffix+"_removed_ids_exact"] = removed==[(r["native_object_type"],r["native_object_id"]) for r in worker.habitat.last_render_scene_filter["removed"]]
            checks[suffix+"_no_reference_ids"] = bool(removed) and all((r["objtype"],r["objid"]) not in removed for r in worker.scene_after)
            renders.append({"camera":camera,"image":str(path.relative_to(ROOT)),"image_sha256":original.sha(path),
                "native_before":before,"native_after":after,"model_before_sha256":original.sha_bytes(model_before),
                "model_after_sha256":original.sha_bytes(model_after),"scene_before":worker.scene_before,"scene_after":worker.scene_after,
                "scene_filter":worker.habitat.last_render_scene_filter})
        with gzip.open(ROOT/prior["data_directory"]/"habitat_wall_push-states.jsonl.gz","rt") as f:
            old_rows = [json.loads(line) for line in f]
        with np.load(ROOT/prior["data_directory"]/"habitat_wall_push-arrays.npz") as z:
            old_actor = z["actor"].copy()
        rows,actors,mismatches = [],[],[]
        for tick in range(plan["parity_intervals"]+1):
            if tick:worker.advance(20.,0.,"walk")
            state = dict(worker.state,guard_diagnostics=original.guards(worker));rows.append(state);actors.append(worker.actor_values.copy())
            mismatches += [{"tick":tick,"field":k} for k,v in old_rows[tick].items() if state.get(k)!=v]
        with gzip.open(directory/"parity-states.jsonl.gz","wt") as f:
            for r in rows:f.write(json.dumps(r,separators=(",",":"),allow_nan=False)+"\n")
        np.savez_compressed(directory/"parity-actor.npz",actor=np.asarray(actors))
        checks["101_actor_samples_exact"] = np.array_equal(actors,old_actor[:len(actors)])
        checks["101_native_samples_exact"] = not mismatches
        checks["100_intervals_completed"] = worker.tick==100
        metadata = worker.metadata();worker.close()
        worker = cls(dict(config,habitat=None),plan["seed"])
        before = original.snapshot(worker);model_before = visual.model_bytes(worker)
        worker.render("overview")
        checks["default_no_callback"] = worker.camera._scene_callback is None
        checks["default_native_model_unchanged"] = before==original.snapshot(worker) and model_before==visual.model_bytes(worker)
        verify(plan);checks["source_hashes_unchanged"] = True
        original.write(RESULT,{"plan_sha256":original.sha(PLAN),"passed":bool(all(checks.values())),
            "checks":{k:bool(v) for k,v in checks.items()},"check_count":len(checks),"renders":renders,"metadata":metadata,
            "native_parity_mismatches":mismatches,"data_directory":str(directory.relative_to(ROOT)),
            "artifacts":{str(p.relative_to(ROOT)):original.sha(p) for p in directory.iterdir()},
            "scope":plan["scope"],"retained_failures":plan["retained_failures"]})
        print(json.dumps({"passed":bool(all(checks.values())),"checks":len(checks),"failed":[k for k,v in checks.items() if not v]}),flush=True)
    finally:worker.close()


if __name__=="__main__":main()
