"""Zero-step repeat-camera diagnostic; preserve the failed pixel-equality gate."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import validate_flybody_habitat_visual as visual
import validate_flybody_habitat as original

PLAN = ROOT/"validation/flybody-habitat-render-diagnostic-plan.json"
RESULT = ROOT/"validation/flybody-habitat-render-diagnostic-results.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prepare",action="store_true")
    args = p.parse_args()
    old = json.loads(visual.RESULT.read_text())
    if args.prepare:
        assert not PLAN.exists()
        original.write(PLAN,{"sources_sha256":{x:original.sha(ROOT/x) for x in (
            "scripts/diagnose_flybody_habitat_render.py","scripts/validate_flybody_habitat_visual.py",
            "fruitfly/flybody_worker.py","fruitfly/flybody_habitat.py","validation/flybody-habitat-visual-results.json")},
            "reason":"Original visual receipt preserves a failed exact-pixel comparison between worker and a separately constructed source camera. Save repeated images and poses/scenes to distinguish source display behavior from physical mutation.",
            "sequence":["worker","source","worker","source","worker"],"seed":11,"physics_steps":0,
            "policy_advances":0,"scope":"Diagnostic only; no changed runtime or overwritten pixel gate. Exact render-pose and scene equality are inspected independently of pixel equality."})
        print(original.sha(PLAN))
        return
    assert not RESULT.exists()
    plan = json.loads(PLAN.read_text())
    assert all(original.sha(ROOT/p)==h for p,h in plan["sources_sha256"].items())
    import numpy as np
    from PIL import Image
    from dm_control.mujoco.engine import MovableCamera
    config = dict(json.loads(visual.PLAN.read_text())["config"],habitat=None)
    cls,module = original.observed_class(ROOT/"fruitfly/flybody_worker.py","default_render_diagnostic")
    worker = cls(config,11)
    directory = ROOT/"runs"/("flybody-habitat-render-diagnostic-"+original.sha(PLAN)[:12])
    directory.mkdir()
    images,records = [],[]
    before = original.snapshot(worker)
    initial_model = visual.model_bytes(worker)
    source = MovableCamera(worker.env.physics,height=config["height"],width=config["width"])
    source.set_pose(lookat=[0.,0.,0.],distance=5.,azimuth=135,elevation=-55)
    try:
        for index,which in enumerate(plan["sequence"]):
            rgb = worker.render("overview") if which=="worker" else source.render().copy()
            camera = worker.camera if which=="worker" else source
            path = directory/(str(index)+"-"+which+".png")
            Image.fromarray(rgb).save(path)
            images.append(rgb)
            pose = camera.get_pose()
            scene = [{"type":int(g.type),"objtype":int(g.objtype),"objid":int(g.objid),"pos":g.pos.tolist(),
                "mat":g.mat.tolist(),"size":g.size.tolist(),"rgba":g.rgba.tolist()} for g in camera.scene.geoms[:camera.scene.ngeom]]
            records.append({"which":which,"path":str(path.relative_to(ROOT)),"sha256":original.sha(path),
                "pose":{"lookat":pose.lookat.tolist(),"distance":pose.distance,"azimuth":pose.azimuth,"elevation":pose.elevation},
                "scene":scene,"model_bytes_unchanged":initial_model==visual.model_bytes(worker),
                "native_state_unchanged":before==original.snapshot(worker)})
        comparisons = []
        for index in range(1,len(images)):
            diff = images[index].astype(int)-images[0].astype(int)
            comparisons.append({"reference":0,"other":index,"pixels_exact":bool(not diff.any()),
                "different_pixels":int(np.any(diff!=0,axis=2).sum()),"maximum_channel_difference":int(np.abs(diff).max()),
                "pose_exact":records[index]["pose"]==records[0]["pose"],"scene_fields_exact":records[index]["scene"]==records[0]["scene"]})
        original.write(RESULT,{"plan_sha256":original.sha(PLAN),"original_failed_pixel_gate_retained":str(visual.RESULT.relative_to(ROOT)),
            "records":records,"comparisons":comparisons,"native_steps":0,"policy_advances":0,
            "all_sampled_native_and_model_unchanged":all(r["native_state_unchanged"] and r["model_bytes_unchanged"] for r in records),
            "scope":plan["scope"]})
        print(json.dumps(comparisons),flush=True)
    finally:
        del source
        worker.close()


if __name__=="__main__":
    main()
