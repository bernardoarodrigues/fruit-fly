"""Separate feeding circuit effects from body-induced changes in taste input.

Follow-up to the retained failed closed-loop input-equality assumption in
audit_feeding_motor_recruitment.py. No runtime/model parameters are changed.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.simulation import SimulationRunner
from fruitfly.neural import LIFNetwork, SparseDrive


def event_hash_update(digest, batch, selected):
    keep = np.isin(batch.indices, selected)
    digest.update(np.asarray(batch.neuron_ids[keep], dtype="<i8").tobytes())
    digest.update(np.asarray(batch.times_ms[keep], dtype="<f8").tobytes())


def main():
    prior_path = ROOT/"validation/feeding-motor-recruitment.json"
    prior = json.loads(prior_path.read_text())
    if prior["checks"]["mute_preserves_ordered_input_and_all_monitored_events"]:
        raise AssertionError("This follow-up expects the documented failed equality assumption")
    out = ROOT/"validation/feeding-afferent-replay.json"
    report = {"scope": __doc__, "complete": False,
        "prior_experiment_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "plan": {"seeds": [11, 12], "duration_ms": 500, "coupling_ms": 5,
            "source": "Recapture each original taste baseline exactly, then replay its ordered input arrays to neural-only clones",
            "replay_conditions": ["unblocked", "fdg_outputs_blocked"],
            "fdg_ids": [12617, 14321], "tuning": None,
            "body_or_intake_prediction_from_replay": False}, "seeds": []}
    out.write_text(json.dumps(report, indent=2)+"\n")
    for seed in (11, 12):
        old = next(c for c in prior["conditions"] if c["seed"] == seed and c["condition"] == "taste")
        runner = SimulationRunner(old["config"])
        try:
            graph, parameters = runner.graph, runner.brain.parameters
            selected = runner.brain.indices_for_ids([c["bodyId"] for c in prior["catalogue"]])
            fdg = graph.select(["GNG588"])
            original = runner.brain.advance
            inputs, contact_schedule = [], []
            original_event_hash, input_hash = hashlib.sha256(), hashlib.sha256()
            original_counts = np.zeros(len(selected), dtype=np.int64)
            def capture(*args, **kwargs):
                drive = kwargs["drive"]
                inputs.append({"indices": drive.indices.tolist(), "rates_hz": drive.rates_hz.tolist()})
                contact_schedule.append({"t_ms": runner.brain.time_ms,
                    "food_contact_by_leg": runner.body.observe()["food_contact_by_leg"]})
                input_hash.update(np.asarray(drive.indices, dtype="<i8").tobytes())
                input_hash.update(np.asarray(drive.rates_hz, dtype="<f8").tobytes())
                batch = original(*args, **kwargs)
                event_hash_update(original_event_hash, batch, selected)
                original_counts[:] += batch.counts(selected)
                return batch
            runner.brain.advance = capture
            final = runner.advance(.5)
            baseline_check = (input_hash.hexdigest() == old["ordered_input_sha256"]
                and original_counts.tolist() == old["catalogue_order_counts"]
                and final["physiology"]["food_ingested"] == old["food_ingested"])
            runner.brain.advance = original
            if not baseline_check:
                raise AssertionError("Original closed-loop baseline failed exact reproduction")
            record = {"seed": seed, "baseline_reproduced_exactly": baseline_check,
                "graph_sha256": runner.brain.graph_sha256, "catalogue": prior["catalogue"],
                "ordered_input_sha256": input_hash.hexdigest(), "ordered_inputs_by_5ms_interval": inputs,
                "actual_contact_schedule": contact_schedule, "baseline_events": final["events"],
                "baseline_monitored_event_sha256": original_event_hash.hexdigest(),
                "baseline_counts": original_counts.tolist(), "replays": []}
        finally:
            runner.close()
        for condition in ("unblocked", "fdg_outputs_blocked"):
            net = LIFNetwork.from_connectome(graph, parameters=parameters, seed=seed)
            if condition == "fdg_outputs_blocked":
                net.ablate(fdg)
            digest = hashlib.sha256()
            counts = np.zeros(len(selected), dtype=np.int64)
            samples = []
            for arrays in inputs:
                batch = net.advance(5, drive=SparseDrive(arrays["indices"], rates_hz=arrays["rates_hz"]))
                event_hash_update(digest, batch, selected)
                n = batch.counts(selected)
                counts += n
                samples.append({"t_ms": net.time_ms, "counts": n.tolist(),
                    "voltage_mv": net.voltage_mv[selected].tolist(),
                    "network_min_voltage_mv": float(net.voltage_mv.min()), "total_spikes": batch.total_spikes})
            kinds = graph.neurons.type.iloc[selected]
            result = {"condition": condition, "monitored_event_sha256": digest.hexdigest(),
                "catalogue_order_counts": counts.tolist(),
                "per_type_total_spikes": {kind: int(counts[kinds.eq(kind)].sum()) for kind in sorted(kinds.unique())},
                "samples": samples, "body_simulated": False, "food_ingested": None,
                "explicit_blocked_neuron_ids": [12617, 14321] if condition != "unblocked" else []}
            record["replays"].append(result)
            print(json.dumps({"seed": seed, "condition": condition, "per_type_total_spikes": result["per_type_total_spikes"]}), flush=True)
            del net
        record["unblocked_replay_exact"] = record["replays"][0]["monitored_event_sha256"] == record["baseline_monitored_event_sha256"]
        report["seeds"].append(record)
        out.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    report["checks"] = {"both_original_baselines_reproduced": all(r["baseline_reproduced_exactly"] for r in report["seeds"]),
        "both_unblocked_replays_exact": all(r["unblocked_replay_exact"] for r in report["seeds"]),
        "full_100_intervals_preserved_per_seed": all(len(r["ordered_inputs_by_5ms_interval"]) == 100 for r in report["seeds"])}
    report["complete"] = True
    out.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["checks"], indent=2))
    if not all(report["checks"].values()):
        raise AssertionError("Afferent replay did not reproduce the recorded baseline")


if __name__ == "__main__":
    main()
