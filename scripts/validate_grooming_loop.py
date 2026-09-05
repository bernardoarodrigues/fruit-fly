"""Full-MaleCNS grooming gate controls with a measured motor template.

This tests direct-DN activation and a declared motion adapter, not natural
sensory-driven grooming or biologically calibrated Shiu voltage dynamics.
"""
import copy
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.simulation import SimulationRunner


def main():
    base = json.loads(Path("configs/male-grooming-probe.json").read_text())
    output = Path("validation/grooming-loop")
    output.mkdir(parents=True, exist_ok=True)
    result = {"scope": __doc__, "duration_s": 1.4, "conditions": [], "complete": False}
    for condition in ("no_input", "direct_dn", "readout_muted", "readout_withdrawn"):
        config = copy.deepcopy(base)
        if condition == "no_input":
            config["probe_hz"] = 0
        runner = SimulationRunner(config)
        observations, frames = [], []
        try:
            if condition == "readout_muted":
                runner.control({"type": "ablation", "enabled": True})
            for step in range(140):
                if condition == "readout_withdrawn" and step == 40:
                    runner.control({"type": "ablation", "enabled": True})
                state = runner.advance(.01)
                if condition == "direct_dn" and step in (19, 39, 59, 79, 99, 119):
                    frames.append((state["t_s"], state["grooming"]["state"], runner.render()))
                observations.append({"t_s": state["t_s"], "behavior": state["behavior"],
                    "requested_behavior": state["requested_behavior"], "grooming": state["grooming"],
                    "grooming_left_hz": state["neural"]["output_rates"]["grooming_left"],
                    "brain_spikes": state["neural"]["spikes"]})
            if abs(state["brain_t_s"] - state["t_s"]) > 1e-10:
                raise AssertionError("Brain and physical clocks diverged")
            if not np.isfinite(runner.body.data.qpos).all() or not np.isfinite(runner.brain.voltage_mv).all():
                raise AssertionError("Nonfinite actual model state")
            if max(abs(v) for v in state["resource_balance"].values()) > 1e-8:
                raise AssertionError("Resource conservation failed")
            value = {"name": condition, "config": config, "final": state,
                     "observations": observations, "probe_neuron_ids": runner.graph.neuron_ids[runner.probe_indices].tolist()}
            result["conditions"].append(value)
            (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            if frames:
                import matplotlib.pyplot as plt
                fig, axes = plt.subplots(2, 3, figsize=(12, 7), constrained_layout=True)
                for axis, (t, phase, frame) in zip(axes.flat, frames):
                    axis.imshow(frame)
                    axis.set_title(f"{t:.2f}s · {phase}")
                    axis.axis("off")
                fig.suptitle("Direct left-DN stimulation → measured grooming template\nFemale-derived body/template; rigid antennae; uncalibrated neural dynamics")
                fig.savefig(output / "direct-dn-frames.png", dpi=150)
                plt.close(fig)
            print(condition, state["grooming"], flush=True)
        finally:
            runner.close()
    conditions = {c["name"]: c for c in result["conditions"]}
    pos = conditions["direct_dn"]["final"]["grooming"]
    controls = [conditions[key]["final"]["grooming"] for key in ("no_input", "readout_muted")]
    withdrawn = conditions["readout_withdrawn"]["final"]["grooming"]
    result["checks"] = {
        "direct_dn_completes_once": pos["completed_count"] == 1,
        "direct_dn_makes_physical_contact": pos["contact_s"] > 0,
        "tonic_request_does_not_loop": pos["state"] == "held",
        "controls_do_not_play": all(v["completed_count"] == 0 and v["contact_s"] == 0 for v in controls),
        "withdrawal_cancels": withdrawn["completed_count"] == 0 and withdrawn["cancelled_count"] >= 1,
        "muted_brain_remains_active": conditions["readout_muted"]["final"]["neural"]["total_spikes"] > 0,
    }
    result["complete"] = True
    (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["checks"], indent=2))
    if not all(result["checks"].values()):
        raise SystemExit("A causal grooming check failed; retain evidence and inspect")


if __name__ == "__main__":
    main()
