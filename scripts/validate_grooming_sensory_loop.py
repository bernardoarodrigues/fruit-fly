"""Prespecified full-body JO-F neural-input assay and causal interventions.

No physical stimulus transducer or natural grooming is validated. Fixed100Hz
imposed input and unchanged Shiu parameters, with seeds11/12; no rate search.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.data import sha256
from fruitfly.simulation import SimulationRunner, GROOMING_SENSORY_IDS


def run_condition(base, name, seed, output):
    config = copy.deepcopy(base)
    config["seed"] = seed
    if name == "no_input":
        config["probe_hz"] = 0
    runner = SimulationRunner(config)
    observations, frames = [], []
    source_hash = hashlib.sha256()
    source_counts = np.zeros(len(GROOMING_SENSORY_IDS), dtype=np.int64)
    dn_counts = np.zeros(2, dtype=np.int64)
    original_advance = runner.brain.advance

    def recorded_advance(*args, **kwargs):
        batch = original_advance(*args, **kwargs)
        selected = np.isin(batch.indices, runner.probe_indices)
        pairs = np.column_stack((batch.neuron_ids[selected],
            np.rint(batch.times_ms[selected] / runner.brain.parameters.dt_ms).astype(np.int64)))
        source_hash.update(pairs.astype("<i8", copy=False).tobytes())
        source_counts[:] += batch.counts(runner.probe_indices)
        dn_counts[:] += batch.counts(runner.motor.groups["grooming_left"])
        return batch

    runner.brain.advance = recorded_advance
    try:
        if name == "readout_muted":
            runner.control({"type": "ablation", "enabled": True})
        elif name == "source_output_blocked":
            runner.control({"type": "synaptic_output", "group": "grooming_sensory", "blocked": True})
            # A reset must preserve the configured source intervention.
            runner.control({"type": "reset"})
            assert np.all(runner.brain.ablated[runner.probe_indices])
        for step in range(280):
            state = runner.advance(.005)
            if name == "sensory_100hz" and seed == 11 and step in (39, 79, 119, 159, 199, 239):
                frames.append((state["t_s"], state["grooming"]["state"], runner.render()))
            observations.append({"t_s": state["t_s"], "behavior": state["behavior"],
                "requested_behavior": state["requested_behavior"], "grooming": state["grooming"],
                "grooming_left_hz": state["neural"]["output_rates"]["grooming_left"],
                "source_spikes": state["grooming_sensory_probe"]["source_spikes"],
                "brain_spikes": state["neural"]["spikes"],
                "voltage_mv": state["neural"]["voltage_mv"]})
        assert abs(state["brain_t_s"] - state["t_s"]) < 1e-10
        assert np.isfinite(runner.body.data.qpos).all()
        assert np.isfinite(runner.brain.voltage_mv).all()
        assert max(abs(v) for v in state["resource_balance"].values()) < 1e-8
        assert runner.graph.neuron_ids[runner.motor.groups["grooming_left"]].tolist() == [13624, 14537]
        assert state["grooming_sensory_probe"]["source_total_spikes"] == int(source_counts.sum())
        manifest = json.loads((runner.run_dir / "manifest.json").read_text())
        assert manifest["probe_input_order_ids"][-42:] == list(GROOMING_SENSORY_IDS)
        assert len(manifest["probe_input_order_ids"]) == 147
        assert not set(manifest["probe_input_order_ids"]) & {13624, 14537}
        value = {"name": name, "seed": seed, "config": config, "final": state,
            "observations": observations, "source_spike_counts": source_counts.tolist(),
            "source_spike_sha256": source_hash.hexdigest(),
            "source_spike_hash_format": "Chronological [bodyId, neural_tick] pairs, C-order little-endian int64",
            "left_dn_spike_counts": dn_counts.tolist(),
            "input_order_body_ids": manifest["probe_input_order_ids"],
            "manifest_path": str(runner.run_dir / "manifest.json"),
            "manifest_sha256": sha256(runner.run_dir / "manifest.json"),
            "sampled_minimum_voltage_mv": min(o["voltage_mv"]["minimum"] for o in observations)}
        if frames:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(2, 3, figsize=(12, 7), constrained_layout=True)
            for axis, (t, phase, frame) in zip(axes.flat, frames):
                axis.imshow(frame); axis.set_title(f"{t:.2f}s · {phase}"); axis.axis("off")
            fig.suptitle("Imposed left JO-F activation → full graph → female grooming template\nPutative subgroup crosswalk; rigid antennae; uncalibrated Shiu dynamics")
            fig.savefig(output / "sensory-frames.png", dpi=150)
            plt.close(fig)
        print(name, seed, "source spikes", int(source_counts.sum()), "DN spikes", dn_counts.tolist(),
              "completed", state["grooming"]["completed_count"], "contact_s", state["grooming"]["contact_s"], flush=True)
        return value
    finally:
        runner.close()


def main():
    base = json.loads(Path("configs/male-grooming-sensory-probe.json").read_text())
    output = Path("validation/grooming-sensory-loop")
    output.mkdir(parents=True, exist_ok=True)
    files = ["fruitfly/simulation.py", "fruitfly/neural.py", "fruitfly/sensors.py", "fruitfly/body.py",
             "fruitfly/grooming.py", "scripts/validate_grooming_sensory_loop.py",
             "configs/male-grooming-sensory-probe.json", "data/grooming/unilateral_left.npz"]
    result = {"scope": __doc__, "complete": False, "duration_s": 1.4,
        "source_sha256": {p: sha256(Path(p)) for p in files}, "conditions": [],
        "prespecified_conditions": [[name, seed] for seed in (11, 12)
            for name in ("no_input", "sensory_100hz", "readout_muted", "source_output_blocked")],
        "limits": ["Imposed independent 100Hz/cell Poisson voltage events, not measured JO-F firing",
            "Audited 42-cell anatomical union; older subgroup/experimental-driver crosswalk remains putative",
            "No physical touch, dust or wind transducer; no natural grooming claim",
            "Female-derived body and recorded motor template; rigid antennae",
            "Shiu voltage pathology and disabled refractory input cells remain unchanged"]}
    path = output / "results.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    for name, seed in result["prespecified_conditions"]:
        result["conditions"].append(run_condition(base, name, seed, output))
        path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    checks = {}
    for seed in (11, 12):
        rows = {c["name"]: c for c in result["conditions"] if c["seed"] == seed}
        active = rows["sensory_100hz"]
        quiet, muted, blocked = [rows[n] for n in ("no_input", "readout_muted", "source_output_blocked")]
        g = active["final"]["grooming"]
        controls = [c["final"]["grooming"] for c in (quiet, muted, blocked)]
        checks[str(seed)] = {
            "sensory_input_completes_once": g["completed_count"] == 1 and g["cancelled_count"] == 0,
            "sensory_input_makes_contact": g["contact_s"] > 0,
            "tonic_request_held_without_repeat": g["state"] == "held" and active["final"]["behavior"] == "rest",
            "all_controls_no_playback_or_contact": all(c["completed_count"] == c["cancelled_count"] == 0 and c["contact_s"] == 0 for c in controls),
            "no_input_no_spikes": quiet["final"]["neural"]["total_spikes"] == 0,
            "readout_mute_retains_neural_response": active["source_spike_sha256"] == muted["source_spike_sha256"] and active["left_dn_spike_counts"] == muted["left_dn_spike_counts"],
            "source_block_preserves_all_source_spikes": active["source_spike_sha256"] == blocked["source_spike_sha256"] and sum(blocked["source_spike_counts"]) > 0,
            "source_block_stops_downstream_spikes": blocked["final"]["neural"]["total_spikes"] == sum(blocked["source_spike_counts"]),
            "paired_input_order_identical": all(c["input_order_body_ids"] == active["input_order_body_ids"] for c in (quiet, muted, blocked)),
        }
    result["checks"] = checks
    result["sources_unchanged_during_run"] = all(sha256(Path(p)) == h for p, h in result["source_sha256"].items())
    result["complete"] = True
    result["passed"] = all(all(v.values()) for v in checks.values()) and result["sources_unchanged_during_run"]
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"checks": checks, "passed": result["passed"]}, indent=2))
    if not result["passed"]:
        raise SystemExit("Causal check failed; evidence retained without changing assay parameters")


if __name__ == "__main__":
    main()
