"""Independent saved-scene, journal and image audit; never imports a simulator."""
from __future__ import annotations

import ast
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/flybody-habitat-scene-independent-review.json"
FINAL, VISUAL, CONTACT = "62129a3", "ef6e230", "fd19b56"
CHECKS, INPUTS, SOURCES = {}, {}, {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(name, condition):
    if name in CHECKS:
        if CHECKS[name] != bool(condition):
            raise ValueError("Conflicting repeated check: " + name)
        return  # Shared pinned inputs count once, not once per referring receipt.
    CHECKS[name] = bool(condition)


def read(path):
    data = (ROOT / path).read_bytes()
    INPUTS[path] = {"sha256": sha(data), "bytes": len(data)}
    return data


def obj(path):
    return json.loads(read(path))


def git(path, commit):
    data = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    SOURCES[f"{commit}:{path}"] = sha(data)
    return data


def plan_sources(plan, commit):
    for path, expected in plan.get("source_sha256", plan.get("sources_sha256", {})).items():
        # Source is resolved at the executed revision, even after later edits.
        data = git(path, commit) if path.startswith(("fruitfly/", "scripts/", "configs/")) else read(path)
        check(f"pin:{commit}:{path}", sha(data) == expected)


def artifacts(receipt):
    for path, spec in receipt["artifacts"].items():
        data = read(path)
        check("artifact:" + path, sha(data) == (spec["sha256"] if isinstance(spec, dict) else spec))
        if isinstance(spec, dict):
            check("size:" + path, len(data) == spec["bytes"])


def journal(path):
    data = read(path)
    return [json.loads(line) for line in gzip.decompress(data).splitlines()]


def functions(source):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(source))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def main():
    scene_plan = obj("validation/flybody-habitat-scene-execution-plan.json")
    scene = obj("validation/flybody-habitat-scene-results.json")
    visual_plan = obj("validation/flybody-habitat-visual-execution-plan.json")
    visual = obj("validation/flybody-habitat-visual-results.json")
    diagnostic_plan = obj("validation/flybody-habitat-render-diagnostic-plan.json")
    diagnostic = obj("validation/flybody-habitat-render-diagnostic-results.json")
    original = obj("validation/flybody-habitat-results.json")
    original_plan = obj("validation/flybody-habitat-execution-plan.json")
    final_ui = obj("validation/flybody-habitat-viewer-final/inspection.json")
    prior_ui = obj("validation/flybody-habitat-viewer/inspection.json")
    final_ui_plan = obj("validation/flybody-habitat-viewer-final-plan.json")
    prior_ui_plan = obj("validation/flybody-habitat-viewer-plan.json")
    for p, r, name in [(scene_plan, scene, "scene"), (visual_plan, visual, "visual"),
                       (diagnostic_plan, diagnostic, "render-diagnostic"),
                       (original_plan, original, "original")]:
        path = "validation/flybody-habitat-" + ({"original": "execution-plan", "render-diagnostic": "render-diagnostic-plan"}.get(name, name + "-execution-plan")) + ".json"
        check(name + ":plan_binding", r["plan_sha256"] == INPUTS[path]["sha256"])
    check("scene:predeclared_plan", scene["plan_sha256"] == "14229a078298ce3ba43761a05aed602ff7d2463ffa727d4ea3b7afb85795edf2")
    for p, c in [(scene_plan, FINAL), (visual_plan, VISUAL), (diagnostic_plan, VISUAL),
                 (original_plan, CONTACT), (final_ui_plan, FINAL), (prior_ui_plan, VISUAL)]:
        plan_sources(p, c)
    for receipt in [scene, visual, original, final_ui, prior_ui]:
        artifacts(receipt)
    check("producer_final_26_of_26", scene["passed"] and len(scene["checks"]) == 26 and all(scene["checks"].values()))
    check("prior_visual_26_of_27_retained", not visual["passed"] and len(visual["checks"]) == 27
          and [k for k, v in visual["checks"].items() if not v] == ["default_source_camera_pixels_exact"])
    check("prior_physical_failure_retained", not original["passed"] and original["wall_trial_outcome"]["source_terminated"])

    habitat = git("fruitfly/flybody_habitat.py", FINAL)
    worker = git("fruitfly/flybody_worker.py", FINAL)
    old_worker = git("fruitfly/flybody_worker.py", CONTACT)
    now_functions, old_functions = functions(worker), functions(old_worker)
    check("worker_only_render_function_changed", set(now_functions) == set(old_functions)
          and [k for k in now_functions if now_functions[k] != old_functions[k]] == ["render"])
    hf, ho = functions(habitat), functions(git("fruitfly/flybody_habitat.py", CONTACT))
    check("habitat_old_functions_only_bind_changed", [k for k in ho if hf[k] != ho[k]] == ["bind"])
    check("habitat_only_new_callback", set(hf) - set(ho) == {"render_scene_callback"})
    source_fields = next(ast.literal_eval(n.value) for n in ast.parse(habitat).body
                         if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCENE_GEOM_FIELDS" for t in n.targets))
    header_path = "tmp/flybody-env/lib/python3.10/site-packages/mujoco/include/mujoco/mjvisualize.h"
    header = read(header_path).decode()
    body = header.split("struct mjvGeom_ {", 1)[1].split("};", 1)[0]
    fields = re.findall(r"^\s*(?:int|float|char|mjtByte)\s+(\w+)\s*(?:\[\d+\])?;", body, re.M)
    check("public_field_inventory_matches_independent_C_header", len(fields) == 20 and list(source_fields) == fields)
    check("camera_sequence", [r["camera"] for r in scene["renders"]] == scene_plan["cameras"] == ["overview", "follow", "side", "overview"])
    summaries = []
    readonly = ["qpos", "qvel", "qacc", "act", "ctrl", "sensordata", "xpos", "xmat", "cvel"]
    with np.load(ROOT / visual["data_directory"] / "paused-arrays.npz", allow_pickle=False) as z:
        paused = {k: z[k].copy() for k in z.files}
    for number, (row, previous) in enumerate(zip(scene["renders"], visual["renders"])):
        prefix = f"render{number}:"
        edits = previous["scene_edits"]
        # Independently retained v1 IDs, rather than the final removal result,
        # determine which entries should disappear from the saved final scene.
        refs = {(e["native_object_type"], e["native_object_id"]): e["change"] for e in edits if e["change"].startswith("hide_reference_")}
        resources = {(e["native_object_type"], e["native_object_id"]): e for e in edits if e["change"] == "resource_marker_lift"}
        expected, removed, changes = [], [], []
        before, after = row["scene_before"], row["scene_after"]
        check(prefix + "all_records_have_all_20_fields", all(set(r) == set(fields) for r in before + after))
        for i, source in enumerate(before):
            key = (source["objtype"], source["objid"])
            if key in refs:
                removed.append({"original_scene_index": i, "native_object_type": key[0], "native_object_id": key[1], "kind": refs[key].removeprefix("hide_reference_")})
                continue
            target = copy.deepcopy(source)
            if key in resources:
                check(prefix + f"resource{key[1]}_original_position", source["pos"] == resources[key]["before"]["position_cm"])
                target["pos"][2] = float(np.float32(float(source["pos"][2]) + .005))
            if target["segid"] != -1:
                target["segid"] = len(expected)
            changes.append({"original_index": i, "retained_index": len(expected),
                            "changed_fields": [k for k in fields if target[k] != source[k]]})
            expected.append(target)
        check(prefix + "every_survivor_field_exact", expected == after)
        check(prefix + "removal_exact_against_prior_ID_evidence", removed == row["scene_filter"]["removed"])
        check(prefix + "no_reference_ID_retained", not set(refs).intersection((r["objtype"], r["objid"]) for r in after))
        check(prefix + "only_two_resources_and_segid_changed", len(resources) == 2 and all(set(c["changed_fields"]) <= {"pos", "segid"} for c in changes))
        check(prefix + "counts", len(before) == 228 and len(after) == 92 and len(removed) == 136
              and row["scene_filter"]["original_count"] == len(before) and row["scene_filter"]["retained_count"] == len(after))
        check(prefix + "native_hashes_equal", row["native_before"] == row["native_after"] == previous["sampled_state_before"])
        check(prefix + "nine_array_inventory", set(row["native_before"]["arrays"]) == set(readonly))
        for field in readonly:
            check(prefix + "raw_paused_" + field, np.array_equal(paused["before_" + field], paused["after_" + field])
                  and sha(paused["before_" + field].tobytes()) == row["native_before"]["arrays"][field])
        check(prefix + "full_model_serialization_hashes_equal", row["model_before_sha256"] == row["model_after_sha256"] == previous["model_before_sha256"] == previous["model_after_sha256"])
        check(prefix + "paused_clock_and_actor", row["native_before"]["time"] == 0 and row["native_before"]["actor"] == sha(paused["actor_before"].tobytes()) == sha(paused["actor_after"].tobytes()))
        summaries.append({"camera": row["camera"], "before": len(before), "after": len(after),
                          "removed_by_kind": dict(Counter(r["kind"] for r in removed)),
                          "survivor_field_comparisons": len(after) * len(fields), "changes": [c for c in changes if c["changed_fields"]]})

    rows = journal(scene["data_directory"] + "/parity-states.jsonl.gz")
    old_rows = journal(original["data_directory"] + "/habitat_wall_push-states.jsonl.gz")
    with np.load(ROOT / scene["data_directory"] / "parity-actor.npz", allow_pickle=False) as z:
        actors = z["actor"].copy()
    with np.load(ROOT / original["data_directory"] / "habitat_wall_push-arrays.npz", allow_pickle=False) as z:
        old_actors = z["actor"][:101].copy()
    check("parity:101_by_741_float32", actors.shape == old_actors.shape == (101, 741) and actors.dtype == old_actors.dtype == np.float32)
    check("parity:all_actual_actor_values", np.array_equal(actors, old_actors))
    check("parity:101_rows", len(rows) == 101)
    for i, row in enumerate(rows):
        check(f"parity:row{i}:all_original_fields", all(k in row and row[k] == v for k, v in old_rows[i].items()))
        check(f"parity:row{i}:actor_hash", sha(actors[i].tobytes()) == row["actor_input_sha256"])
        check(f"parity:row{i}:clock_and_counter", row["tick"] == row["source_control_tick"] == i and abs(row["native_time_s"] - i * .002) < 1e-12)
        check(f"parity:row{i}:finite_and_not_terminated", row["finite"] and not row["source_terminated"] and all(np.all(np.isfinite(row[k])) for k in ["qpos", "qvel", "qacc", "ctrl", "act"]))

    images = []
    for i, r in enumerate(diagnostic["records"]):
        check(f"diagnostic:image{i}:hash", sha(read(r["path"])) == r["sha256"])
        images.append(np.asarray(Image.open(ROOT / r["path"]), dtype=np.int16))
    pixel_comparisons = []
    for c in diagnostic["comparisons"]:
        a, b = c["reference"], c["other"]
        delta = np.abs(images[a] - images[b])
        found = dict(c, pixels_exact=bool(not np.any(delta)), different_pixels=int(np.any(delta != 0, axis=-1).sum()),
                     maximum_channel_difference=int(delta.max()), pose_exact=diagnostic["records"][a]["pose"] == diagnostic["records"][b]["pose"],
                     scene_fields_exact=diagnostic["records"][a]["scene"] == diagnostic["records"][b]["scene"])
        check(f"diagnostic:pair{a}-{b}:recomputed", found == c)
        pixel_comparisons.append(found)
    check("diagnostic:later_four_images_identical", all(np.array_equal(images[1], im) for im in images[2:]))
    check("diagnostic:zero_steps_reported", diagnostic["native_steps"] == diagnostic["policy_advances"] == 0)

    reset = obj("validation/flybody-habitat-viewer/8774/reset.json")["telemetry"]
    groups = ["pose", "senses", "physiology", "neural", "stimuli", "physics", "behavior"]
    ui_summary = []
    for camera in ["overview", "follow", "side", "final-state"]:
        state = obj("validation/flybody-habitat-viewer-final/" + camera + ".json")
        telem = state["telemetry"]
        check("UI:" + camera + ":paused_zero", state["paused"] and state["status"] == "paused"
              and telem["t_s"] == telem["brain_t_s"] == state["frame_t_s"] == 0 and state["error"] is None)
        check("UI:" + camera + ":camera", state["camera"] == ("overview" if camera == "final-state" else camera))
        check("UI:" + camera + ":seven_scientific_groups_exact", all(telem[k] == reset[k] for k in groups))
        a, b = copy.deepcopy(telem["body_metadata"]), copy.deepcopy(reset["body_metadata"])
        check("UI:" + camera + ":runtime_source_hashes", a["worker_sha256"] == sha(worker) and a["habitat_module_sha256"] == sha(habitat))
        removed_metadata = {"final_worker_log": a.pop("worker_log"), "prior_worker_log": b.pop("worker_log"),
                            "final_module_hash": a.pop("habitat_module_sha256"), "prior_module_hash": b.pop("habitat_module_sha256"),
                            "new_reference_filter": a["habitat"]["display"].pop("reference_filter")}
        check("UI:" + camera + ":metadata_only_declared_changes", a == b and removed_metadata["new_reference_filter"] == "Removed from MjvScene, including shadow/reflection passes")
        ui_summary.append({"camera": state["camera"], "path": camera + ".json", "metadata_differences": removed_metadata})
    check("UI:final_plan_binding", final_ui["runtime_source_commit"] == FINAL and final_ui["plan_sha256"] == INPUTS["validation/flybody-habitat-viewer-final-plan.json"]["sha256"])
    check("UI:prior_plan_binding", prior_ui["runtime_source_commit"] == VISUAL and prior_ui["plan_sha256"] == INPUTS["validation/flybody-habitat-viewer-plan.json"]["sha256"])
    failed = obj("validation/flybody-habitat-viewer/8775/failed.json")
    failure = failed["failure_diagnostics"]
    cached = failure["cached_body_diagnostics"]
    failure_journal = [json.loads(line) for line in read("validation/flybody-habitat-viewer/8775/failure-journal.jsonl").splitlines()]
    check("UI:failure_journal_matches_API", failure_journal == [failure])
    clocks = dict(last_image=failed["frame_t_s"], last_completed_advance=failed["telemetry"]["t_s"], failure_neural=failure["brain_t_s"], failure_physical=cached["native_time_s"])
    check("UI:four_distinct_clock_roles", clocks == prior_ui["clocks_s"] and clocks["last_image"] < clocks["last_completed_advance"] < clocks["failure_physical"] and abs(clocks["failure_neural"] - clocks["failure_physical"]) < 1e-12)
    check("UI:physical_failure_retained_at_384", cached["tick"] == 384 and cached["source_terminated"] and not failed["worker_alive"] and failed["status"] == "error" and failed["telemetry_basis"] == "last_completed_advance")
    check("UI:actual_failure_same_saved_native_state", all(cached[k] == v for k, v in old_rows[-1].items() if k != "guard_diagnostics"))
    # Recheck every input after reading; this audit only writes its own receipt.
    for path, value in list(INPUTS.items()):
        check("input_still_stable:" + path, sha((ROOT / path).read_bytes()) == value["sha256"])
    receipt = {"schema": 1, "passed": all(CHECKS.values()), "check_count": len(CHECKS),
        "checks": CHECKS, "failed_checks": [k for k, v in CHECKS.items() if not v],
        "reviewer_script_sha256": sha(Path(__file__).read_bytes()), "runtime_source_commit": FINAL,
        "prior_visual_source_commit": VISUAL, "original_contact_source_commit": CONTACT,
        "source_sha256": SOURCES, "input_artifacts": INPUTS, "public_geom_fields": fields,
        "scenes": summaries, "actor_shape": list(actors.shape), "actor_values_compared": int(actors.size),
        "native_rows_compared": len(rows), "native_original_fields_per_row": len(old_rows[0]),
        "pixel_comparisons": pixel_comparisons, "final_ui": ui_summary, "failure_clocks_s": clocks,
        "physics_or_neural_steps_run_by_reviewer": 0,
        "visual_inspection": {"method": "Independent offline inspection of saved final overview/follow/side JPGs and prior v1 follow JPG using the image viewer; no live browser inspection.",
            "result": "Final three views show smooth resource regions, one fly and its floor reflection, with no visible dotted reference tracks. Prior v1 follow shows dotted tracks extending toward the food region.",
            "paths": ["validation/flybody-habitat-viewer-final/overview.jpg", "validation/flybody-habitat-viewer-final/follow.jpg", "validation/flybody-habitat-viewer-final/side.jpg", "validation/flybody-habitat-viewer/8774/follow-frame.jpg"]},
        "limits": ["Scene ID classification is corroborated by the prior saved edit list and pinned name-selection source; full compiled native ID/name inventory is not archived.",
            "Final render native arrays and full MJB serialization are retained as hashes, not final per-render raw arrays or MJB bytes. Prior paused raw arrays corroborate all nine hash values; full model byte equality itself is producer evidence.",
            "Cached observation equality is hash evidence. Final habitat-null native/model invariance and absent callback are producer booleans plus inspected source, not separate raw before/after records.",
            "Diagnostic model/native invariance is retained only as booleans; its pixels, camera poses and seven scene fields can be recomputed. The original failed default pixel pair was not saved, so the repeat diagnostic does not establish that original mismatch magnitude.",
            "Saved browser snapshots and frames are reviewed offline; this reviewer did not operate or inspect the live browser. Final saved state does not establish present server state.",
            "The final UI has seven exact scientific telemetry groups; body metadata differs in the log path, module hash and added display filter declaration.",
            "Four paused scene records and 100 walking intervals cover these conditions only. The original 64/65 contact, 29/31 shallow-probe and 26/27 alpha-render receipts remain failures, with native physical termination at .768 s. No obstacle avoidance, indefinite containment or physiological validation follows."]}
    OUT.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: receipt[k] for k in ["passed", "check_count", "failed_checks", "actor_values_compared"]}))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
