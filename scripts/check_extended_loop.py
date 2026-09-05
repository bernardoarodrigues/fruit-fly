"""Fixed ten-second full-graph robustness assay, not biological validation.

Tests the existing body, neural model and motor interface unchanged. All
conditions and gates are recorded before any rollout; failures remain evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.simulation import SimulationRunner

OUT = ROOT / "validation/extended-loop"
PLAN = OUT / "plan.json"
RESULT = OUT / "results.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def create_plan():
    if PLAN.exists():
        raise FileExistsError("The existing fixed plan must not be overwritten")
    sources = ["fruitfly/body.py", "fruitfly/simulation.py", "fruitfly/sensors.py",
               "fruitfly/neural.py", "fruitfly/physiology.py", "scripts/check_extended_loop.py"]
    plan = {"scope": __doc__, "seed": 1, "duration_s": 10, "sample_s": .05,
        "coupling_s": .005, "conditions": ["sensory", "motor_probe", "probe_mute_resume"],
        "interventions": {"probe_mute_resume": [{"t_s": 5., "muted": True},
                                                   {"t_s": 7., "muted": False}]},
        "base_config": {"seed": 1, "probe_hz": 40, "coupling_s": .005},
        "source_sha256": {p: sha(ROOT/p) for p in sources},
        "gates": {"all": "10 s complete; all sampled neural/body states finite; clocks synchronized; zero MuJoCo warnings; conserved resources <1e-8",
            "body": "After 0.3 s, thorax upright_z >=0.5; thorax x/y inside configured wall outer bounds (half_size+0.2 mm)",
            "probe": "Continuous direct-DNg97 probe sampled planar path >1 mm",
            "mute": "5.25–7 s requested rest and zero left/right commands, sampled planar speed <=1 mm/s median; neural spikes continue",
            "resume": "After 7 s, at least one nonzero locomotor command; no requirement to move through an obstruction"},
        "measurement_limits": ["Snapshots every50 ms, not a proof against between-sample excursions or missed short contacts.",
            "Wall interactions are sampled current MuJoCo contact geometry, not integrated contact impulse.",
            "Normalized resource and current-based neural-model physiology remain uncalibrated.",
            "Single seed, selected assay, flat small arena; no biological/general robustness claim.",
            "Vision and proprioception are default disabled; no new sensors or parameters are introduced."]}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(PLAN, plan)
    print("Fixed plan saved", sha(PLAN), flush=True)


def run():
    plan = json.loads(PLAN.read_text())
    if any(sha(ROOT/p) != h for p, h in plan["source_sha256"].items()):
        raise AssertionError("Planned source changed")
    report = {"complete": False, "plan_sha256": sha(PLAN), "conditions": []}
    write_json(RESULT, report)
    for condition in plan["conditions"]:
        config = dict(plan["base_config"], assay="sensory" if condition == "sensory" else "motor_probe")
        runner = SimulationRunner(config)
        try:
            frames, samples = [], []
            initial = runner.snapshot()
            model, data = runner.body.model, runner.body.data
            wall_ids = {i for i in range(model.ngeom) if model.geom(i).name in {"west", "east", "north", "south"}}
            if len(wall_ids) != 4:
                raise AssertionError("Exactly four named physical walls required")
            start = time.perf_counter()
            interventions = {round(x["t_s"]/plan["sample_s"]): x for x in plan["interventions"].get(condition, [])}
            for i in range(round(plan["duration_s"]/plan["sample_s"])):
                if i in interventions:
                    runner.control({"type": "ablation", "enabled": interventions[i]["muted"]})
                state = runner.advance(plan["sample_s"])
                wall_contacts = sum(int(c.geom1 in wall_ids or c.geom2 in wall_ids) for c in data.contact)
                samples.append({"t_s": state["t_s"], "brain_t_s": state["brain_t_s"],
                    "position_mm": state["pose"]["position_mm"],
                    "upright_z": float(data.xmat[runner.body._thorax_id].reshape(3, 3)[2, 2]),
                    "motor": state["motor"], "neural_spikes": state["neural"]["spikes"],
                    "neural_voltage_mv": state["neural"]["voltage_mv"],
                    "sampled_wall_contacts": wall_contacts,
                    "finite_body": bool(np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()),
                    "finite_brain": bool(np.isfinite(runner.brain.voltage_mv).all() and np.isfinite(runner.brain.synaptic_mv).all()),
                    "resource_residual_max": max(map(abs, state["resource_balance"].values()))})
                if (i+1) % 20 == 0:
                    print(condition, "t_s", state["t_s"], "position", state["pose"]["position_mm"], flush=True)
                if (i+1) in (100, 140, 200):
                    path = OUT/f"{condition}-{state['t_s']:04.1f}s.png"
                    Image.fromarray(runner.render("overview")).save(path)
                    frames.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
            wall = time.perf_counter()-start
            pos = np.array([initial["pose"]["position_mm"], *[s["position_mm"] for s in samples]])
            speed = np.linalg.norm(np.diff(pos[:, :2], axis=0), axis=1)/plan["sample_s"]
            for s, v in zip(samples, speed):
                s["sample_interval_planar_speed_mm_s"] = float(v)
            settled = [s for s in samples if s["t_s"] >= .3]
            h = runner.body.config.arena_half_size_mm
            checks = {"ten_seconds": abs(state["t_s"]-10) < 1e-12,
                "clocks": all(abs(s["t_s"]-s["brain_t_s"]) < 1e-9 for s in samples),
                "finite": all(s["finite_body"] and s["finite_brain"] for s in samples),
                "no_mujoco_warnings": not any(int(w.number) for w in data.warning),
                "resources": max(s["resource_residual_max"] for s in samples) < 1e-8,
                "upright": min(s["upright_z"] for s in settled) >= .5,
                "inside_arena": all(max(map(abs, s["position_mm"][:2])) <= h+.2 for s in settled)}
            if condition == "motor_probe":
                checks["probe_path_exceeds_1mm"] = float(speed.sum()*plan["sample_s"]) > 1
            if condition == "probe_mute_resume":
                muted = [s for s in samples if 5.25 <= s["t_s"] <= 7]
                checks["muted_output_is_rest"] = all(s["motor"]["behavior"] == "rest" and s["motor"]["left"] == s["motor"]["right"] == 0 for s in muted)
                checks["muted_median_speed_at_most_1"] = float(np.median([s["sample_interval_planar_speed_mm_s"] for s in muted])) <= 1
                checks["muted_neurons_continue"] = sum(s["neural_spikes"] for s in muted) > 0
                checks["resume_locomotor_command"] = any(max(s["motor"]["left"], s["motor"]["right"]) > 0 for s in samples if s["t_s"] > 7)
            record = {"condition": condition, "config": config, "run_dir": str(runner.run_dir),
                "run_manifest_sha256": sha(runner.run_dir/"manifest.json"),
                "graph_sha256": runner.brain.graph_sha256, "initial": initial, "final": state,
                "wall_s_with_three_renders": wall, "simulated_s_per_wall_s": 10/wall,
                "peak_process_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "path_length_mm_sampled": float(speed.sum()*plan["sample_s"]),
                "displacement_mm": float(np.linalg.norm(pos[-1, :2]-pos[0, :2])),
                "sampled_behavior_counts": dict(Counter(s["motor"]["behavior"] for s in samples)),
                "sampled_wall_contact_frames": sum(s["sampled_wall_contacts"] > 0 for s in samples),
                "warnings": [int(w.number) for w in data.warning], "samples": samples,
                "frames": frames, "checks": {k: bool(v) for k, v in checks.items()}}
            report["conditions"].append(record)
            write_json(RESULT, report)
        finally:
            runner.close()
    report["complete"] = True
    report["all_declared_gates_pass"] = all(all(r["checks"].values()) for r in report["conditions"])
    report["biological_fidelity_validated"] = False
    write_json(RESULT, report)
    print(json.dumps({r["condition"]: r["checks"] for r in report["conditions"]}, indent=2))
    if not report["all_declared_gates_pass"]:
        raise AssertionError("A declared robustness gate failed; retained for diagnosis")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    create_plan() if args.plan else run()
