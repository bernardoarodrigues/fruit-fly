"""Read all annotated proboscis MNs during the existing full-graph taste assay.

This diagnoses motor recruitment. MN9-driven abstract intake is not swallowing.
No neural weights, decoder rules, body geometry or ingestion dynamics are fitted.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.simulation import SimulationRunner
from flygym_demo.complex_terrain import make_locomotion_fly


def main():
    output = ROOT/"validation/feeding-motor-recruitment.json"
    report = {"scope": __doc__, "complete": False,
        "plan": {"seeds": [11, 12], "duration_s": .5, "conditions":
            ["taste", "no_taste", "motor_muted", "sweet_outputs_blocked", "fdg_outputs_blocked"],
            "analysis": "All exact MN-number types plus GNG588; descriptive counts, no outcome-selected groups or tuning",
            "runtime_change": False, "claim_ceiling": "Imposed contact transduction and existing abstract ingestion; not an oral motor-program validation"},
        "sources_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), ROOT/"fruitfly/simulation.py", ROOT/"fruitfly/body.py", ROOT/"fruitfly/neural.py")},
        "conditions": []}
    fly = make_locomotion_fly()
    report["current_body"] = {"class": type(fly).__name__,
        "proboscis_joint_dofs": [str(d) for d in fly.get_jointdofs_order() if d.child.is_proboscis()],
        "proboscis_position_actuators": [str(d) for d in fly.get_actuated_jointdofs_order("position") if d.child.is_proboscis()],
        "mouth_contact_or_pump": "not implemented; taste assay uses tarsal contact and abstract stationary ingestion"}
    output.write_text(json.dumps(report, indent=2)+"\n")
    for seed in report["plan"]["seeds"]:
        for condition in report["plan"]["conditions"]:
            config = {"seed": seed, "enable_taste": condition != "no_taste",
                "sensory_parameters": {"odor_baseline_hz": 0, "odor_max_increment_hz": 0},
                "body": {"initial_position_mm": [6, 0, .8]}}
            runner = SimulationRunner(config)
            try:
                cells = runner.graph.neurons
                selected = np.flatnonzero(cells.type.fillna("").str.match(r"^MN\d") | cells.type.eq("GNG588"))
                fdg = runner.graph.select(["GNG588"])
                if tuple(runner.graph.neuron_ids[fdg]) != (12617, 14321):
                    raise AssertionError("Fdg synonym target identity changed")
                if not cells.loc[fdg, "synonyms"].fillna("").str.contains("Shiu 2022: Fdg", regex=False).all():
                    raise AssertionError("Fdg correspondence is not present in released synonyms")
                if len(selected) != 50 or not cells.loc[selected[cells.type.iloc[selected].ne("GNG588")], "superclass"].eq("cb_motor").all():
                    raise AssertionError("Audited48 proboscis MNs plus2 Fdg candidates changed")
                if "catalogue" not in report:
                    report["catalogue"] = json.loads(cells.iloc[selected][["bodyId", "type", "somaSide", "rootSide",
                        "exitNerve", "superclass", "consensus_nt", "model_sign", "flywireType", "synonyms"]].to_json(orient="records"))
                    report["processed_annotation_sha256"] = hashlib.sha256((ROOT/"data/processed/malecns_v1/neurons.feather").read_bytes()).hexdigest()
                    report["neural_parameters"] = asdict(runner.brain.parameters)
                if condition == "motor_muted":
                    runner.control({"type": "ablation", "enabled": True})
                elif condition == "sweet_outputs_blocked":
                    runner.control({"type": "synaptic_output", "group": "sweet", "blocked": True})
                elif condition == "fdg_outputs_blocked":
                    runner.brain.ablate(fdg)
                original_advance = runner.brain.advance
                samples, events = [], []
                ordered_input_hash = hashlib.sha256()
                def monitor(*args, **kwargs):
                    drive = kwargs["drive"]
                    ordered_input_hash.update(np.asarray(drive.indices, dtype="<i8").tobytes())
                    ordered_input_hash.update(np.asarray(drive.rates_hz, dtype="<f8").tobytes())
                    batch = original_advance(*args, **kwargs)
                    keep = np.isin(batch.indices, selected)
                    events.extend(zip(batch.neuron_ids[keep].tolist(), batch.times_ms[keep].tolist()))
                    samples.append({"t_ms": runner.brain.time_ms, "counts": batch.counts(selected).tolist(),
                        "voltage_mv": runner.brain.voltage_mv[selected].tolist(),
                        "network_min_voltage_mv": float(runner.brain.voltage_mv.min()),
                        "total_spikes": batch.total_spikes})
                    return batch
                runner.brain.advance = monitor
                initial = runner.snapshot()
                started = time.perf_counter()
                final = runner.advance(.5)
                elapsed = time.perf_counter()-started
                counts = np.asarray([s["counts"] for s in samples]).sum(axis=0)
                per_type = {kind: int(counts[cells.type.iloc[selected].eq(kind)].sum())
                            for kind in sorted(cells.type.iloc[selected].unique())}
                record = {"seed": seed, "condition": condition, "config": config,
                    "run_dir": str(runner.run_dir), "graph_sha256": runner.brain.graph_sha256,
                    "wall_s_excluding_construction": elapsed, "ordered_input_sha256": ordered_input_hash.hexdigest(),
                    "initial_taste_food": bool(initial["senses"]["taste_food"]),
                    "final_neural_time_ms": runner.brain.time_ms, "final_physics_time_s": runner.body.time_s,
                    "food_ingested": final["physiology"]["food_ingested"],
                    "resource_balance": final["resource_balance"], "per_type_total_spikes": per_type,
                    "catalogue_order_counts": counts.tolist(), "samples": samples,
                    "events_bodyId_time_ms": events,
                    "monitored_spikes_sha256": hashlib.sha256(np.asarray(events, dtype="<f8").reshape(-1, 2).tobytes()).hexdigest()}
                report["conditions"].append(record)
                output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
                print(json.dumps({k: record[k] for k in ("seed", "condition", "food_ingested", "per_type_total_spikes")}), flush=True)
                runner.brain.advance = original_advance
            finally:
                runner.close()
    rows = report["conditions"]
    report["checks"] = {
        "all_ten_conditions": len(rows) == 10,
        "same_full_graph": len({r["graph_sha256"] for r in rows}) == 1,
        "initial_actual_tarsal_contact": all(r["initial_taste_food"] for r in rows),
        "clocks_synchronized": all(r["final_neural_time_ms"] == 500 and abs(r["final_physics_time_s"]-.5) < 1e-12 for r in rows),
        "resources_conserved": all(max(map(abs, r["resource_balance"].values())) < 1e-8 for r in rows),
        "no_taste_or_source_block_no_monitored_spikes": all(not any(r["catalogue_order_counts"]) for r in rows
            if r["condition"] in ("no_taste", "sweet_outputs_blocked")),
        "mute_preserves_ordered_input_and_all_monitored_events": all(
            next(r for r in rows if r["seed"] == seed and r["condition"] == "taste")[field] ==
            next(r for r in rows if r["seed"] == seed and r["condition"] == "motor_muted")[field]
            for seed in (11, 12) for field in ("ordered_input_sha256", "monitored_spikes_sha256")),
    }
    report["complete"] = True
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["checks"], indent=2))
    if not all(report["checks"].values()):
        raise AssertionError("Feeding recruitment audit has failed controls; preserve and inspect results")


if __name__ == "__main__":
    main()
