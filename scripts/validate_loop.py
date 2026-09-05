"""Reproducible full-MaleCNS body assays; no anatomy substitute or silent fallback.

Run from repository root: .venv/bin/python scripts/validate_loop.py
Direct DN activation is a positive control, not odor-guided foraging evidence.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.simulation import SimulationRunner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--output", type=Path, default=Path("validation/closed-loop"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {"duration_s": args.seconds, "seed": 1, "conditions": [],
               "claim": "Sensorimotor interface positive/negative controls; uncalibrated behavior"}
    for assay, muted in (("sensory", False), ("motor_probe", False), ("motor_probe", True)):
        condition = f"{assay}{'-muted' if muted else ''}"
        config = {"seed": 1, "assay": assay, "probe_hz": 40, "coupling_s": .005}
        runner = SimulationRunner(config)
        try:
            runner.control({"type": "ablation", "enabled": muted})
            initial = runner.snapshot()
            positions = [initial["pose"]["position_mm"][:2]]
            started = time.perf_counter()
            for _ in range(round(args.seconds / .01)):
                final = runner.advance(.01)
                positions.append(final["pose"]["position_mm"][:2])
            seconds = time.perf_counter() - started
            positions = np.asarray(positions)
            displacement = float(np.linalg.norm(positions[-1] - positions[0]))
            result = {"condition": condition, "config": config, "initial": initial, "final": final,
                      "displacement_mm": displacement,
                      "path_length_mm": float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum()),
                      "wall_s": seconds, "realtime_factor_including_telemetry": args.seconds / seconds,
                      "finite_brain": bool(np.isfinite(runner.brain.voltage_mv).all() and np.isfinite(runner.brain.synaptic_mv).all()),
                      "finite_body": bool(np.isfinite(runner.body.data.qpos).all()),
                      "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
            Image.fromarray(runner.render("follow")).save(args.output / f"{condition}.png")
            results["conditions"].append(result)
            (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({k:result[k] for k in ("condition", "displacement_mm", "wall_s", "finite_brain")}), flush=True)
        finally:
            runner.close()
    control, probe, muted = results["conditions"]
    results["checks"] = {
        "all_actual_full_graph": all(x["final"]["neural"]["neurons"] == 166700 and x["final"]["neural"]["edges"] == 25582938 for x in results["conditions"]),
        "all_clocks_synchronized": all(abs(x["final"]["brain_t_s"]-x["final"]["t_s"]) < 1e-9 for x in results["conditions"]),
        "finite_states": all(x["finite_brain"] and x["finite_body"] for x in results["conditions"]),
        "resources_conserved": all(max(abs(v) for v in x["final"]["resource_balance"].values()) < 1e-8 for x in results["conditions"]),
        "direct_dn_probe_moves_body": probe["displacement_mm"] > 1,
        "muting_suppresses_locomotion": muted["displacement_mm"] < probe["displacement_mm"] * .1,
        "muted_brain_remains_active": muted["final"]["neural"]["total_spikes"] > 0,
    }
    results["odor_guided_foraging_validated"] = False
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results["checks"], indent=2))
    if not all(results["checks"].values()):
        raise SystemExit("One or more loop validation gates failed; inspect saved results")


if __name__ == "__main__":
    main()
