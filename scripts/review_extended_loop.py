"""Recompute completed extended-loop gates from retained records, without physics.

This verifies saved-data arithmetic and consistency, not the absent continuous
trajectory, native MuJoCo clock, full state arrays or force-bearing wall touch.
Failed experiment gates are retained; review success means faithful recomputation.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"validation/extended-loop"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((OUT/"plan.json").read_text())
    original = json.loads((OUT/"results.json").read_text())
    if original.get("complete") is not True:
        raise RuntimeError("Experiment is still incomplete; no final review receipt written")
    source_paths = [OUT/"plan.json", OUT/"results.json", *[ROOT/p for p in plan["source_sha256"]]]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    checks = {"plan_hash_matches_result": hashes["validation/extended-loop/plan.json"] == original["plan_sha256"],
              "planned_source_hashes_match": all(sha(ROOT/p) == h for p, h in plan["source_sha256"].items()),
              "all_three_conditions_in_planned_order": [r["condition"] for r in original["conditions"]] == plan["conditions"],
              "same_full_graph_all_conditions": len({r["graph_sha256"] for r in original["conditions"]}) == 1,
              "no_biological_validation_claim": original["biological_fidelity_validated"] is False}
    records = []
    for record in original["conditions"]:
        name = record["condition"]
        samples = record["samples"]
        run = ROOT/record["run_dir"]
        manifest = json.loads((run/"manifest.json").read_text())
        lines = [json.loads(line) for line in (run/"telemetry.jsonl").read_text().splitlines()]
        snapshots = [r for r in lines if "control" not in r]
        controls = [r for r in lines if "control" in r]
        hashes[str((run/"manifest.json").relative_to(ROOT))] = sha(run/"manifest.json")
        hashes[str((run/"telemetry.jsonl").relative_to(ROOT))] = sha(run/"telemetry.jsonl")
        n = round(plan["duration_s"]/plan["sample_s"])
        times = np.asarray([s["t_s"] for s in samples])
        expected_times = np.arange(1, n+1)*plan["sample_s"]
        checks[name+"_all_expected_sample_times"] = len(samples) == n and np.allclose(times, expected_times, rtol=0, atol=1e-12)
        checks[name+"_run_manifest_hash"] = sha(run/"manifest.json") == record["run_manifest_sha256"]
        checks[name+"_config_and_graph_match_manifest"] = record["config"] == manifest["config"] and record["graph_sha256"] == manifest["graph_sha256"]
        expected_controls = [{"control": {"type": "ablation", "enabled": x["muted"]}, "t_s": x["t_s"]}
                             for x in plan["interventions"].get(name, [])]
        checks[name+"_exact_control_times"] = controls == expected_controls
        checks[name+"_all_snapshots_present"] = len(snapshots) == n
        checks[name+"_sample_observables_match_run_log"] = len(snapshots) == len(samples) and all(
            s["t_s"] == t["t_s"] and s["brain_t_s"] == t["brain_t_s"]
            and s["position_mm"] == t["pose"]["position_mm"] and s["motor"] == t["motor"]
            and s["neural_spikes"] == t["neural"]["spikes"] and s["neural_voltage_mv"] == t["neural"]["voltage_mv"]
            and s["resource_residual_max"] == max(abs(v) for v in t["resource_balance"].values())
            for s, t in zip(samples, snapshots))
        pos = np.asarray([record["initial"]["pose"]["position_mm"], *[s["position_mm"] for s in samples]])
        segment_length = np.hypot(np.diff(pos[:, 0]), np.diff(pos[:, 1]))
        speed = segment_length/plan["sample_s"]
        checks[name+"_saved_interval_speeds_match"] = np.allclose(speed, [s["sample_interval_planar_speed_mm_s"] for s in samples], rtol=0, atol=1e-12)
        checks[name+"_saved_path_and_displacement_match"] = (abs(float(segment_length.sum())-record["path_length_mm_sampled"]) < 1e-12
            and abs(float(np.hypot(*(pos[-1, :2]-pos[0, :2])))-record["displacement_mm"]) < 1e-12)
        checks[name+"_saved_behavior_and_wall_frame_counts_match"] = (dict(Counter(s["motor"]["behavior"] for s in samples)) == record["sampled_behavior_counts"]
            and sum(s["sampled_wall_contacts"] > 0 for s in samples) == record["sampled_wall_contact_frames"])
        # Integer sample indexing avoids rounding-dependent interval membership.
        settled_index = np.flatnonzero(expected_times >= .3)
        h = manifest["body_config"]["arena_half_size_mm"]
        gates = {"ten_seconds": abs(times[-1]-plan["duration_s"]) < 1e-12,
                 "clocks": all(abs(s["t_s"]-s["brain_t_s"]) < 1e-9 for s in samples),
                 "finite": all(s["finite_body"] and s["finite_brain"] for s in samples),
                 "no_mujoco_warnings": not any(record["warnings"]),
                 "resources": max(s["resource_residual_max"] for s in samples) < 1e-8,
                 "upright": min(samples[i]["upright_z"] for i in settled_index) >= .5,
                 "inside_arena": bool(np.all(np.abs(pos[settled_index+1, :2]) <= h+.2))}
        extra = {}
        if name == "motor_probe":
            gates["probe_path_exceeds_1mm"] = segment_length.sum() > 1
        if name == "probe_mute_resume":
            indices = np.arange(1, n+1)
            mute_i = np.flatnonzero((indices >= round(5.25/plan["sample_s"])) & (indices <= round(7/plan["sample_s"])))
            resume_i = np.flatnonzero(indices > round(7/plan["sample_s"]))
            muted = [samples[i] for i in mute_i]
            gates["muted_output_is_rest"] = all(s["motor"]["behavior"] == "rest" and s["motor"]["left"] == s["motor"]["right"] == 0 for s in muted)
            gates["muted_median_speed_at_most_1"] = np.median(speed[mute_i]) <= 1
            gates["muted_neurons_continue"] = sum(s["neural_spikes"] for s in muted) > 0
            gates["resume_locomotor_command"] = any(max(samples[i]["motor"]["left"], samples[i]["motor"]["right"]) > 0 for i in resume_i)
            extra = {"muted_sample_count": len(muted), "muted_sample_endpoints_s": [samples[i]["t_s"] for i in mute_i],
                     "muted_median_interval_speed_mm_s": float(np.median(speed[mute_i])),
                     "muted_total_graph_spikes": sum(s["neural_spikes"] for s in muted),
                     "muted_nonzero_spike_intervals": sum(s["neural_spikes"] > 0 for s in muted),
                     "resume_nonzero_command_intervals": sum(max(samples[i]["motor"]["left"], samples[i]["motor"]["right"]) > 0 for i in resume_i)}
            checks[name+"_mute_state_transitions_match_logs"] = all(t["neural"]["ablated"] == (5 < t["t_s"] <= 7) for t in snapshots)
        gates = {k: bool(v) for k, v in gates.items()}
        checks[name+"_every_declared_gate_recomputed"] = gates == record["checks"]
        frame_records = []
        for frame in record["frames"]:
            p = ROOT/frame["path"]
            digest = sha(p)
            hashes[frame["path"]] = digest
            frame_records.append({"path": frame["path"], "sha256": digest})
            checks[name+"_frame_"+p.stem+"_hash"] = digest == frame["sha256"]
        records.append({"condition": name, "recomputed_gates": gates, "failed_gates": [k for k, v in gates.items() if not v],
            "sample_count": len(samples), "path_length_mm_sampled": float(segment_length.sum()),
            "minimum_sampled_upright_z_after_settling": min(samples[i]["upright_z"] for i in settled_index),
            "max_resource_residual": max(s["resource_residual_max"] for s in samples),
            "sampled_wall_nearcontact_frames": record["sampled_wall_contact_frames"],
            "frames": frame_records, **extra})
    recomputed_pass = all(all(r["recomputed_gates"].values()) for r in records)
    checks["overall_pass_flag_recomputed"] = recomputed_pass == original["all_declared_gates_pass"]
    checks["all_reviewed_files_unchanged"] = all(sha(ROOT/p) == h for p, h in hashes.items())
    result = {"scope": __doc__, "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_script_sha256": sha(Path(__file__)), "source_sha256": hashes,
        "checks": {k: bool(v) for k, v in checks.items()}, "recomputed_experiment_all_gates_pass": recomputed_pass,
        "conditions": records, "limits": ["No physics rerun or mutation.",
            "Raw qpos/qvel/full neural state, thorax orientation matrix, wall geom pairs/forces and native data.time were not saved; their flags are retained witnesses, not independently reconstructable states.",
            "Wall near-contact counts include MuJoCo generated contacts within the configured 0.001 mm pair margin, without active/force/distance filtering.",
            "Behavior and motor are requested-command endpoint samples; path/speed are 50 ms chord measurements.",
            "5.25-second endpoint speed covers 5.20–5.25 seconds; 7-second endpoint precedes resume control.",
            "Finite current-based neural dynamics are not physiologically plausible by virtue of finiteness.",
            "RSS is process-lifetime peak, not a per-condition memory-growth trace.",
            "Single seed, three ten-second selected engineering trials do not establish natural behavior or long-term/general robustness."]}
    (OUT/"independent-review.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"review_checks": len(checks), "all_review_checks_pass": all(checks.values()),
                      "experiment_all_gates_pass": recomputed_pass, "failed_review_checks": [k for k, v in checks.items() if not v]}, indent=2))
    if not all(checks.values()):
        raise AssertionError("Saved-data review found a mismatch; inspect receipt")


if __name__ == "__main__":
    main()
