#!/usr/bin/env python3
"""Independent completed-panel hash/link/coverage audit; no model imports.

Each unique file is streamed through SHA256 at most once within this execution.
Later link checks reuse that immutable observed file record.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-final-integrity.json"
PLAN_SHA = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
categories, observed, failures = {}, {}, []


def check(category, passed, detail=None):
    counter = categories.setdefault(category, {"checked": 0, "passed": 0})
    counter["checked"] += 1
    if passed:
        counter["passed"] += 1
    else:
        failures.append({"category": category, "detail": detail})
        raise AssertionError(category + ": " + str(detail))


def record(path):
    path = Path(path)
    relative = str(path.relative_to(ROOT))
    if relative not in observed:
        h, n = hashlib.sha256(), 0
        with path.open("rb") as f:
            while block := f.read(1024 * 1024):
                n += len(block)
                h.update(block)
        observed[relative] = {"path": relative, "bytes": n, "sha256": h.hexdigest()}
    return observed[relative]


def read(path):
    return json.loads(Path(path).read_text())


def verify(expected, category):
    relative = Path(expected["path"])
    check("safe_relative_record_path", not relative.is_absolute() and ".." not in relative.parts, str(relative))
    actual = record(ROOT / relative)
    check(category, actual == expected, str(relative))
    return actual


def audit(out):
    plan = read(PLAN)
    check("exact_frozen_plan", record(PLAN)["sha256"] == PLAN_SHA)
    run = ROOT / plan["run_dir"]
    terminal = read(run / "terminal.json")
    check("authoritative_parent_complete", terminal["status"] == "complete" and terminal["complete"])
    result_record = verify(terminal["results"], "terminal_results_link")
    manifest_record = verify(terminal["artifact_manifest"], "terminal_manifest_link")
    results, manifest = read(ROOT / result_record["path"]), read(ROOT / manifest_record["path"])
    check("parent_results_complete", results["complete"] and results["status"] == "complete" and not results["errors"] and not results["contrast_exclusions"])
    check("parent_plan_and_manifest_identity", results["plan_sha256"] == manifest["plan_sha256"] == PLAN_SHA and
          results["artifact_manifest"] == terminal["artifact_manifest"] and results["run_dir"] == plan["run_dir"])
    manifest_rows = manifest["artifacts"]
    manifest_map = {r["path"]: r for r in manifest_rows}
    check("manifest_paths_unique", len(manifest_map) == len(manifest_rows))
    allowed_prefix = str(run.relative_to(ROOT)) + "/"
    check("manifest_only_this_run", all(p.startswith(allowed_prefix) for p in manifest_map))
    expected_extras = {str((run / name).relative_to(ROOT)) for name in ["artifact-manifest.json", "results.json", "terminal.json"]}
    actual_paths = {str(path.relative_to(ROOT)) for path in run.rglob("*") if path.is_file()}
    check("exact_saved_file_manifest_coverage", actual_paths == set(manifest_map) | expected_extras,
          {"missing": sorted(set(manifest_map) - actual_paths), "unlisted": sorted(actual_paths - set(manifest_map) - expected_extras)})
    out.update(archive_manifest=manifest_record, manifest_file_count=len(manifest_rows), manifest_bytes=sum(r["bytes"] for r in manifest_rows),
               manifest_extension_counts=dict(Counter(Path(p).suffix for p in manifest_map)),
               explicitly_linked_final_files_outside_manifest=sorted(expected_extras))
    for item in manifest_rows:
        verify(item, "manifest_file_sha256_and_size")
    out["all_manifest_files_verified"] = True
    for source in plan["sources"].values():
        verify(source, "frozen_source_sha256_and_size")
    plan_manifest = read(run / "manifest.json")
    check("initial_manifest_plan_link", verify(plan_manifest["plan"], "initial_plan_file_receipt") == record(PLAN))
    expected_design = set(itertools.product(["C0", "C1", "H0", "H1"], [11, 12, 13],
        ["no_input", "constant_baseline", "ethyl_acetate", "isoamyl_acetate", "ethyl_acetate_source_outputs_blocked"]))
    signature = lambda s: (s["arm"], s["seed"], s["condition"])
    check("frozen_plan_exact_4x5x3", len(plan["order"]) == 60 and {signature(s) for s in plan["order"]} == expected_design)
    check("parent_results_exact_4x5x3", len(results["trials"]) == 60 and {signature(s) for s in results["trials"]} == expected_design)
    check("parent_trial_order_matches_plan", [t["name"] for t in results["trials"]] == [s["name"] for s in plan["order"]])
    trial_records = []
    for spec, row in zip(plan["order"], results["trials"]):
        name = spec["name"]
        directory = run / name
        check("parent_trial_identity", all(row[k] == spec[k] for k in ["ordinal", "name", "arm", "seed", "condition"]), name)
        rr, tr = verify(row["result"], "parent_trial_result_link"), verify(row["terminal"], "parent_trial_terminal_link")
        check("trial_links_in_archive_manifest", manifest_map[rr["path"]] == rr and manifest_map[tr["path"]] == tr, name)
        child_terminal, child_result = read(ROOT / tr["path"]), read(ROOT / rr["path"])
        check("child_terminal_result_link", child_terminal["result"] == rr, name)
        check("all_trial_statuses_complete", row["status"] == child_terminal["status"] == child_result["status"] == "complete" and
              row["complete"] and child_terminal["complete"] and child_result["complete"] and not child_terminal["errors"] and not child_result["errors"], name)
        check("child_result_identity", all(child_result[k] == spec[k] for k in ["ordinal", "name", "arm", "seed", "condition"]), name)
        check("complete_trial_clocks", row["completed_tick"] == row["counts_end_tick"] == 30000 and
              all(child_result[k] == 30000 for k in ["completed_tick", "counts_end_tick", "last_durable_chunk_end_tick", "last_complete_checkpoint_tick", "confirmed_prefix_end_tick"]), name)
        check("parent_child_summary_equality", row["summary"] == child_result["summary"], name)
        check("complete_window_summary", child_result["summary"]["window_edges_ticks"] == plan["window_edges_ticks"] and
              child_result["summary"]["window_complete"] == [True] * 7 and child_result["summary"]["completed_tick"] == 30000, name)
        child_artifacts = child_result["artifacts"]
        check("unique_child_artifact_paths", len(child_artifacts) == len({a["path"] for a in child_artifacts}), name)
        for artifact in child_artifacts:
            check("child_artifact_link_matches_verified_manifest", manifest_map.get(artifact["path"]) == artifact == observed.get(artifact["path"]), artifact["path"])
        for tick in plan["checkpoint_ticks"]:
            for suffix in [".npz", ".json", ".complete.json"]:
                path = str((directory / f"checkpoint-{tick:05d}{suffix}").relative_to(ROOT))
                check("all_expected_checkpoints_retained", path in manifest_map, path)
        chunk_markers = {str(p.relative_to(ROOT)) for p in directory.glob("chunk-*.complete.json")}
        expected_markers = {str((directory / f"chunk-{k:04d}.complete.json").relative_to(ROOT)) for k in range(600)}
        check("exact_600_chunk_markers", chunk_markers == expected_markers, name)
        trial_records.append({"spec": spec, "result": rr, "terminal": tr, "spike_count": child_result["spike_count"],
                              "complete_windows": 7, "completed_tick": 30000, "child_artifact_links": len(child_artifacts)})
    marker_count = 0
    for name in manifest_map:
        if not name.endswith(".complete.json"):
            continue
        marker = read(ROOT / name)
        check("bundle_marker_complete_format", marker["complete"] and marker["format"] == "inhibitory-recurrent-panel-completion" and
              marker["version"] == 1 and isinstance(marker["transaction"], str), name)
        base = name[:-len(".complete.json")]
        check("bundle_payload_paths_exact", {a["path"] for a in marker["artifacts"]} == {base + ".npz", base + ".json"} and len(marker["artifacts"]) == 2, name)
        for artifact in marker["artifacts"]:
            check("bundle_link_matches_verified_manifest", manifest_map.get(artifact["path"]) == artifact == observed.get(artifact["path"]), artifact["path"])
        marker_count += 1
    check("bundle_marker_count", marker_count == 60 * (600 + 8 + 1) + 4)
    gates = read(run / "all-c0-prefixes-passed.json")
    check("all15_C0_gate_manifest", gates["passed"] and gates["count"] == 15 and len(gates["gates"]) == 15)
    for spec, gate in zip(plan["order"][:15], gates["gates"]):
        expected_path = str((run / spec["name"] / "c0-prefix-gate.json").relative_to(ROOT))
        check("C0_gate_identity_and_link", gate["path"] == expected_path and manifest_map[expected_path] == gate == observed[expected_path])
        content = read(ROOT / expected_path)
        check("C0_gate_declares_pass", content["passed"] and content["plan_sha256"] == PLAN_SHA and content["tick"] == 15000 and all(content["checks"].values()), expected_path)
    parent_terminal_record = record(run / "terminal.json")
    for suffix, primary in [("terminal", parent_terminal_record), ("results", result_record)]:
        copy = record(ROOT / "validation" / ("inhibitory-recurrent-panel-" + suffix + ".json"))
        check("validation_publication_exact_copy", (copy["bytes"], copy["sha256"]) == (primary["bytes"], primary["sha256"]), suffix)
    check("saved_file_set_still_unchanged", actual_paths == {str(path.relative_to(ROOT)) for path in run.rglob("*") if path.is_file()})
    out.update(passed=True, plan=record(PLAN), script=record(Path(__file__)), parent_terminal=parent_terminal_record,
               parent_results=result_record, trials=trial_records, complete_trial_count=60, complete_window_count=420,
               bundle_marker_count=marker_count, frozen_source_count=len(plan["sources"]),
               unique_files_hashed=len(observed), total_unique_bytes_hashed=sum(r["bytes"] for r in observed.values()),
               observed_file_receipt_digest=hashlib.sha256(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
               source_receipts={p: observed[p] for p in plan["sources"]})


def main():
    if OUT.exists():
        raise FileExistsError("Preserve the first final-integrity execution")
    started = time.perf_counter()
    out = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "scope": "Independent terminal/results/manifest and 60-trial coverage audit, one streamed hash computation per unique file within this execution. No producer/archive/metric/model imports, neural simulation, archive mutation or commit.",
           "limits": ["Hashes establish the retained bytes and reference consistency, not correctness of neural equations or biological validity.",
                      "Completion-marker payload links are checked; numerical array decoding and metadata/payload transaction reconstruction belong to the independent C/H readers.",
                      "Parent summaries are checked against pinned child summaries; this audit does not recompute metrics or contrasts from spikes.",
                      "One hashing pass over a completed local snapshot is not a cryptographic filesystem lock, power-loss guarantee or proof against a concurrent same-path rewrite afterward.",
                      "C0 gate claims are linked and checked for declared success, not numerically replayed here."]}
    try:
        audit(out)
    except Exception as error:
        out["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    out.update(categories=categories, failures=failures, check_count=sum(c["checked"] for c in categories.values()),
               checks_passed=sum(c["passed"] for c in categories.values()), hashed_files_before_stop=len(observed),
               wall_seconds=time.perf_counter() - started, finished_utc=datetime.now(timezone.utc).isoformat())
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False); f.write("\n")
    b = OUT.read_bytes()
    print(json.dumps({"passed": out["passed"], "checks": out["check_count"], "files": out.get("manifest_file_count"),
                      "receipt": str(OUT.relative_to(ROOT)), "sha256": hashlib.sha256(b).hexdigest(), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
