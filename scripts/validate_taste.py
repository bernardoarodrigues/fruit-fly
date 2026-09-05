"""Actual leg-contact -> full male neural graph -> feeding interface controls."""
from pathlib import Path
import sys
import json
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.simulation import SimulationRunner


def main():
    output = Path("validation/taste-contact")
    output.mkdir(parents=True, exist_ok=True)
    results = {"claim": "Tarsal sugar input and abstract stationary ingestion; not proboscis mechanics", "conditions": []}
    for name, enabled, muted in (("taste", True, False), ("no-taste", False, False),
                                 ("muted", True, True), ("sweet-synapses-blocked", True, False)):
        cfg = {"seed": 11, "enable_taste": enabled,
               "sensory_parameters": {"odor_baseline_hz": 0, "odor_max_increment_hz": 0},
               "body": {"initial_position_mm": [6, 0, .8]}}
        runner = SimulationRunner(cfg)
        try:
            runner.control({"type": "ablation", "enabled": muted})
            if name == "sweet-synapses-blocked":
                runner.control({"type": "synaptic_output", "group": "sweet", "blocked": True})
            initial = runner.snapshot()
            final = runner.advance(.5)
            result = {"condition": name, "config": cfg, "initial": initial, "final": final,
                      "contacts_by_leg": runner.body.observe()["food_contact_by_leg"],
                      "min_voltage_mv": float(runner.brain.voltage_mv.min()),
                      "max_voltage_mv": float(runner.brain.voltage_mv.max())}
            results["conditions"].append(result)
            print(json.dumps({"condition": name, "feeding_hz": runner.motor.rates["feeding"],
                              "food_ingested": final["physiology"]["food_ingested"]}), flush=True)
        finally:
            runner.close()
    taste, absent, muted, blocked = results["conditions"]
    results["checks"] = {
        "actual_contact": all(x["initial"]["senses"]["taste_food"] for x in results["conditions"]),
        "taste_drives_intake": taste["final"]["physiology"]["food_ingested"] > 0,
        "no_intake_without_neural_taste": absent["final"]["physiology"]["food_ingested"] == 0,
        "no_intake_with_muted_readout": muted["final"]["physiology"]["food_ingested"] == 0,
        "no_intake_with_sweet_synapses_blocked": blocked["final"]["physiology"]["food_ingested"] == 0,
        "blocked_sweet_cells_still_fire": blocked["final"]["neural"]["total_spikes"] > 0,
        "resources_conserved": all(max(map(abs, x["final"]["resource_balance"].values())) < 1e-8 for x in results["conditions"]),
    }
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results["checks"], indent=2))
    if not all(results["checks"].values()):
        raise SystemExit("Taste assay has failed gates; preserve and inspect results")


if __name__ == "__main__":
    main()
