"""Independent identity, saved-history and neural-only feeding replay review.

No body is instantiated and no source experiment is overwritten. Exactness
means the retained observables match; it does not mean empirical validity or
complete biological/model-state equivalence. Seeds 11/12 are descriptive cases.
"""
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.data import Connectome
from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_events(digest, ids, times):
    digest.update(np.asarray(ids, dtype="<i8").tobytes())
    digest.update(np.asarray(times, dtype="<f8").tobytes())


def main():
    files = ["scripts/audit_feeding_motor_recruitment.py", "scripts/check_feeding_afferent_replay.py",
             "validation/feeding-motor-recruitment.json", "validation/feeding-afferent-replay.json",
             "docs/feeding-motor-expansion.md", "fruitfly/neural.py", "fruitfly/data.py",
             "fruitfly/sensors.py", "fruitfly/simulation.py", "fruitfly/body.py",
             "data/processed/malecns_v1/manifest.json", "data/processed/malecns_v1/neurons.feather"]
    hashes = {name: sha(ROOT/name) for name in files}
    prior = json.loads((ROOT/files[2]).read_text())
    replay = json.loads((ROOT/files[3]).read_text())
    checks = {}
    checks["historical_source_hashes_match"] = all(hashes[p] == h for p, h in prior["sources_sha256"].items())
    checks["replay_chain_hashes_match"] = (replay["prior_experiment_sha256"] == hashes[files[2]]
        and replay["script_sha256"] == hashes[files[1]])
    checks["failed_closed_loop_control_retained"] = prior["checks"]["mute_preserves_ordered_input_and_all_monitored_events"] is False
    graph = Connectome.load(ROOT/"data/processed/malecns_v1", verify=True)
    cells = graph.neurons
    mn = np.flatnonzero(cells.type.fillna("").str.match(r"^MN\d"))
    fdg = graph.select(["GNG588"])
    selected = np.sort(np.r_[mn, fdg])
    checks["exact_48_motor_cells_and_18_types"] = (len(mn) == 48 and cells.iloc[mn].type.nunique() == 18
        and cells.iloc[mn].superclass.eq("cb_motor").all())
    checks["exact_two_fdg_synonym_cells"] = (graph.neuron_ids[fdg].tolist() == [12617, 14321]
        and cells.iloc[fdg].synonyms.str.contains("Shiu 2022: Fdg", regex=False).all())
    checks["catalogue_matches_live_annotation"] = (graph.neuron_ids[selected].tolist() == [x["bodyId"] for x in prior["catalogue"]]
        and json.loads(cells.iloc[selected][list(prior["catalogue"][0])].to_json(orient="records")) == prior["catalogue"])
    checks["annotation_hash_matches"] = hashes[files[-1]] == prior["processed_annotation_sha256"]
    parameters = LIFParameters(**prior["neural_parameters"])
    orn = np.r_[graph.select(["ORN_DM1", "ORN_DM4"], side="L"),
                graph.select(["ORN_DM1", "ORN_DM4"], side="R")]
    groups = {side+leg: graph.select(["LgAG2", "LgLG4"], side=side, nerve=nerve)
        for side in ("L", "R") for leg, nerve in (("F", "ProLN"), ("M", "MesoLN"), ("H", "MetaLN"))}
    records = []
    for row in replay["seeds"]:
        seed = row["seed"]
        old = next(c for c in prior["conditions"] if c["seed"] == seed and c["condition"] == "taste")
        arrays = row["ordered_inputs_by_5ms_interval"]
        contacts = row["actual_contact_schedule"]
        source_events = np.asarray(old["events_bodyId_time_ms"], dtype=float).reshape(-1, 2)
        historical_hash = hashlib.sha256()
        input_hash = hashlib.sha256()
        for k, (drive, contact) in enumerate(zip(arrays, contacts)):
            # Use integer simulation ticks; an event exactly at 5 ms belongs to
            # the interval beginning there. No decimal-boundary approximation.
            selected_events = source_events[np.rint(source_events[:, 1]/parameters.dt_ms).astype(int)//50 == k]
            hash_events(historical_hash, selected_events[:, 0], selected_events[:, 1])
            expected_indices = np.r_[orn, *[ids for leg, ids in groups.items() if contact["food_contact_by_leg"][leg]]]
            expected_rates = np.r_[np.zeros(len(orn)), np.full(len(expected_indices)-len(orn), 100.)]
            checks[f"seed_{seed}_interval_{k}_contact_and_order"] = bool(
                contact["t_ms"] == k*5 and np.array_equal(expected_indices, drive["indices"])
                and np.array_equal(expected_rates, drive["rates_hz"]))
            input_hash.update(np.asarray(drive["indices"], dtype="<i8").tobytes())
            input_hash.update(np.asarray(drive["rates_hz"], dtype="<f8").tobytes())
        checks[f"seed_{seed}_historical_spike_times_match_recapture"] = historical_hash.hexdigest() == row["baseline_monitored_event_sha256"]
        checks[f"seed_{seed}_ordered_input_hash_matches"] = input_hash.hexdigest() == old["ordered_input_sha256"] == row["ordered_input_sha256"]
        checks[f"seed_{seed}_100_intervals"] = len(arrays) == len(contacts) == 100
        first_change = next(c["t_ms"] for c in contacts if c["food_contact_by_leg"] != contacts[0]["food_contact_by_leg"])
        record = {"seed": seed, "first_contact_change_ms": first_change,
                  "historical_monitored_event_sha256": historical_hash.hexdigest(), "replays": []}
        rng_by_condition = []
        for reference in row["replays"]:
            net = LIFNetwork.from_connectome(graph, parameters=parameters, seed=seed)
            checks[f"seed_{seed}_graph_matches"] = net.graph_sha256 == row["graph_sha256"] == old["graph_sha256"]
            blocked = reference["condition"] == "fdg_outputs_blocked"
            if blocked:
                net.ablate(fdg)
            monitored_hash, all_spike_hash = hashlib.sha256(), hashlib.sha256()
            rng_history, counts = [], np.zeros(len(selected), dtype=np.int64)
            samples_equal, refractory_equal = True, True
            for drive, reference_sample in zip(arrays, reference["samples"]):
                batch = net.advance(5, drive=SparseDrive(drive["indices"], rates_hz=drive["rates_hz"]))
                keep = np.isin(batch.indices, selected)
                hash_events(monitored_hash, batch.neuron_ids[keep], batch.times_ms[keep])
                hash_events(all_spike_hash, batch.neuron_ids, batch.times_ms)
                n = batch.counts(selected)
                counts += n
                samples_equal &= (n.tolist() == reference_sample["counts"]
                    and np.array_equal(net.voltage_mv[selected], reference_sample["voltage_mv"])
                    and float(net.voltage_mv.min()) == reference_sample["network_min_voltage_mv"]
                    and batch.total_spikes == reference_sample["total_spikes"]
                    and net.time_ms == reference_sample["t_ms"])
                expected_refractory = np.full(net.n_neurons, round(parameters.refractory_ms/parameters.dt_ms))
                expected_refractory[drive["indices"]] = 0
                refractory_equal &= np.array_equal(expected_refractory, net.refractory_ticks)
                rng_history.append(int(net._rng_state[0]))
            name = f"seed_{seed}_{reference['condition']}"
            checks[name+"_all_recorded_samples_exact"] = bool(samples_equal and len(reference["samples"]) == 100)
            checks[name+"_monitored_events_exact"] = monitored_hash.hexdigest() == reference["monitored_event_sha256"]
            checks[name+"_counts_exact"] = counts.tolist() == reference["catalogue_order_counts"]
            checks[name+"_declared_refractory_state_exact"] = bool(refractory_equal)
            checks[name+"_no_body_prediction"] = reference["body_simulated"] is False and reference["food_ingested"] is None
            rng_by_condition.append(rng_history)
            record["replays"].append({"condition": reference["condition"], "monitored_event_sha256": monitored_hash.hexdigest(),
                "all_spikes_sha256_new_review_only": all_spike_hash.hexdigest(), "rng_state_each_interval": rng_history,
                "final_time_ms": net.time_ms, "mn9_total_spikes": int(counts[cells.type.iloc[selected].eq("MN9")].sum()),
                "fdg_total_spikes": int(counts[cells.type.iloc[selected].eq("GNG588")].sum())})
            print(name, "samples:", bool(samples_equal), "events:", checks[name+"_monitored_events_exact"], flush=True)
            del net
        checks[f"seed_{seed}_rng_history_equal_across_intervention"] = rng_by_condition[0] == rng_by_condition[1]
        records.append(record)
    # Compact the 200 interval checks without hiding failures.
    interval_names = [k for k in checks if k.endswith("_contact_and_order")]
    checks["all_200_contact_derived_ordered_drives_exact"] = all(checks[k] for k in interval_names)
    failed_intervals = [k for k in interval_names if not checks.pop(k)]
    checks["source_files_unchanged_during_review"] = all(sha(ROOT/p) == h for p, h in hashes.items())
    report = {"scope": __doc__, "review_script_sha256": sha(Path(__file__)), "source_sha256": hashes,
        "versions": {p: version(p) for p in ("numpy", "numba", "pandas")}, "parameters": asdict(parameters),
        "input_contract": {"orn_count_first": len(orn), "orn_rates_hz": 0, "sweet_rates_hz": 100,
            "omitted_fields": {"current_mv": None, "poisson_weight_mv": None, "disable_refractory": True},
            "note": "Default voltage-jump weight from saved parameters; zero-rate listed ORNs still consume RNG and disable refractory."},
        "checks": {k: bool(v) for k, v in checks.items()}, "failed_intervals": failed_intervals, "seeds": records,
        "limitations": ["No body rerun or external biological experiment.",
            "Monitor is observational; exact event checks cover 48 MNs plus 2 Fdg cells, not every original graph spike/state.",
            "Replay freezes input arrays and cannot predict intake or unchanged sensory-source spike times under recurrent feedback.",
            "Two low-count histories establish no statistical confidence, biological necessity, coordination or swallowing.",
            "Underlying Shiu dynamics retain severe implausible hyperpolarization."]}
    (ROOT/"validation/feeding-independent-review.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report["checks"], indent=2))
    if not all(checks.values()):
        raise AssertionError("Independent feeding review found a mismatch; inspect receipt")


if __name__ == "__main__":
    main()
