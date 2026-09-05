#!/usr/bin/env python3
"""Independently review saved fullgraph/FlyBody journals; never run a simulator."""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/flybody-loop"
REVISION = "928e062"
DT = .002
LEGS = ("LF", "LM", "LH", "RF", "RM", "RH")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def same(a, b, tolerance=0.):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape, (a.shape, b.shape)
    assert np.isfinite(a).all() and np.isfinite(b).all()
    error = float(np.max(np.abs(a-b))) if a.size else 0.
    assert error <= tolerance, error
    return error


def check_drive(drive, ids):
    raw = {k: v for k, v in drive.items() if k != "ordered_drive_sha256"}
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert digest == drive["ordered_drive_sha256"]
    indices = np.asarray(drive["indices"], dtype=int)
    assert len(set(indices)) == len(indices)
    same(ids[indices], drive["neuron_ids"])
    assert drive["current_mv"] is drive["poisson_weight_mv"] is None
    assert drive["disable_refractory"] is True
    assert len(indices) == len(drive["rates_hz"])
    assert np.isfinite(drive["rates_hz"]).all() and np.all(np.asarray(drive["rates_hz"]) >= 0)


def main():
    plan, results, summary, archive = [read(OUT / x) for x in ("plan.json", "results.json", "summary.json", "archival.json")]
    assert results["plan_sha256"] == archive["plan_sha256"] == summary["plan_sha256"] == sha(OUT / "plan.json")
    assert summary["results_sha256"] == sha(OUT / "results.json")
    assert results["archival"]["sha256"] == sha(OUT / "archival.json")
    assert sha(ROOT / archive["original_results"]["path"]) == archive["original_results"]["sha256"]
    frozen_sources = {}
    for path, expected in plan["source_sha256"].items():
        # Ignored dataset manifests remain local; tracked experiment code is
        # resolved at its frozen revision, independently of subsequent UI work.
        proc = subprocess.run(["git", "show", f"{REVISION}:{path}"], cwd=ROOT, capture_output=True)
        content = proc.stdout if proc.returncode == 0 else (ROOT / path).read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if not path.startswith("docs/"):
            assert actual == expected, path
        frozen_sources[path] = {"sha256": actual, "declared_sha256": expected, "matches_plan": actual == expected,
                               "read_from": REVISION if proc.returncode == 0 else "local ignored data"}
    assert all(results["source_hashes_unchanged_after"].values())
    assert archive["archiver_sha256"] == summary["script_sha256"] == sha(ROOT / "scripts/archive_flybody_loop.py")
    neurons_path = ROOT / "data/processed/malecns_v1/neurons.feather"
    neurons = pd.read_feather(neurons_path, columns=["bodyId", "type", "rootSide", "somaSide", "entryNerve"])
    ids = np.load(ROOT / "data/processed/malecns_v1/neuron_ids.npy", allow_pickle=False)
    same(neurons.bodyId.values, ids)
    assert len(ids) == 166700
    assert np.load(ROOT / "data/processed/malecns_v1/targets.npy", mmap_mode="r", allow_pickle=False).shape == (25582938,)
    side = neurons.rootSide.fillna(neurons.somaSide)

    def select(types, lateral=None, nerve=None):
        mask = neurons.type.isin(types)
        if lateral is not None:
            mask &= side.eq(lateral)
        if nerve is not None:
            mask &= neurons.entryNerve.eq(nerve)
        return np.flatnonzero(mask.values)

    odor_groups = [select(["ORN_DM1", "ORN_DM4"], s) for s in ("L", "R")]
    taste_groups, club_groups = [], []
    for leg in LEGS:
        nerve = {"F": "ProLN", "M": "MesoLN", "H": "MetaLN"}[leg[1]]
        taste_groups.append(select(["LgAG2", "LgLG4"], leg[0], nerve))
        club_groups.append(select(["SNpp40", "SNpp47", "SNpp56", "SNpp57", "SNpp60"], leg[0], nerve))
    groups = {"odor": np.concatenate(odor_groups), "sweet": np.unique(np.concatenate(taste_groups)),
              "club": np.unique(np.concatenate(club_groups)), "motor_forward": select(["DNg97"]),
              "motor_turn_left": select(["DNa01", "DNa02"], "L"),
              "motor_turn_right": select(["DNa01", "DNa02"], "R"),
              "motor_feeding": select(["MN9"]), "motor_escape": select(["DNp01"])}
    sensory = np.concatenate([groups[k] for k in ("odor", "sweet", "club")])
    assert len(set(sensory)) == len(sensory)
    condition_reviews, pairs = [], []
    for condition, archived, displayed in zip(results["conditions"], archive["journals"], summary["conditions"], strict=True):
        name = condition["condition"]
        assert name == displayed["condition"]
        folder = ROOT / condition["raw_directory"]
        for rel, expected in archived["all_original_file_hashes"].items():
            assert sha(folder / rel) == expected, (name, rel)
        raw = folder / "events.jsonl"
        assert sha(raw) == condition["journal"]["sha256"] == archived["sha256"]
        assert sha(ROOT / archived["gzip_path"]) == archived["gzip_sha256"]
        with gzip.open(ROOT / archived["gzip_path"], "rb") as stream:
            digest = hashlib.sha256()
            while chunk := stream.read(1024*1024):
                digest.update(chunk)
        assert digest.hexdigest() == sha(raw)
        for image, expected in condition["frames"].items():
            assert sha(OUT / "frames" / (name + "-" + image)) == expected
        for key, indices in groups.items():
            same(np.sort(condition["groups"][key]["indices"]), np.sort(indices))
            same(ids[np.asarray(condition["groups"][key]["indices"])], condition["groups"][key]["neuron_ids"])
        assert condition["neural_parameters"] == {"dt_ms": .1, "resting_mv": -52., "reset_mv": -52.,
            "threshold_mv": -45., "membrane_tau_ms": 20., "synapse_tau_ms": 5., "refractory_ms": 2.2,
            "delay_ms": 1.8, "poisson_weight_mv": 68.75}
        total = round(condition["design"]["duration_s"] / DT)
        assert condition["complete"] and not condition["failures"] and condition["completed_ticks"] == total
        assert condition["worker_exit_code_after_close"] == 0
        assert condition["lifecycle_initial_pass"]
        expected_blocks = condition["design"]["outgoing_blocks"]
        blocked_count = len(set(i for g in expected_blocks for i in groups[g]))
        previous = condition["initial_diagnostics"]
        initial_phys = condition["initial"]["physiology"]
        previous_phys = initial_phys
        metadata = condition["initial"]["body_metadata"]
        assert (metadata["physics_timestep_s"], metadata["control_timestep_s"]) == (.0002, .002)
        assert metadata["initialization_settling_s"] == 0 and metadata["horizon_s"] == 2
        food_position = condition["design"]["food_position_mm"]
        config = read(folder / "runner/manifest.json")["config"]
        event_counts = collections.Counter()
        ticks, bundles, neural_records, points = 0, [], [], [np.asarray(previous["pose_cm_quat"][:3])*10]
        adaptation = np.zeros(2)
        rate_state = {k: 0. for k in groups if k.startswith("motor_")}
        totals = collections.Counter()
        maxima = collections.defaultdict(float)
        intervention_events = []
        sweet_positive = False
        minimum_voltage = minimum_upright = float("inf")
        maximum_acceleration = 0.
        first_feed_end = None
        physical_digest = hashlib.sha256()
        with raw.open() as stream:
            for record_number, line in enumerate(stream):
                event = json.loads(line)
                assert event["record"] == record_number
                kind = event["event"]
                event_counts[kind] += 1
                if kind.startswith("intervention_"):
                    intervention_events.append((kind, event["tick"]))
                    continue
                if kind in ("condition_start", "initial", "condition_end"):
                    continue
                bundles.append(event)
                if kind != "physical_complete":
                    continue
                assert [e["event"] for e in bundles] == ["coupling_start", "encoder", "encoder", "encoder", "neural_start", "neural_complete", "physical_complete"]
                assert all(e["tick"] == ticks for e in bundles)
                start, *encoders, neural_start, neural, physical = bundles
                assert [e["encoder"] for e in encoders] == ["odor", "sweet", "club"]
                obs = start["physical_observation"]
                d, state = physical["diagnostics"], physical["state"]
                same(obs["pose"]["position_mm"], np.asarray(previous["pose_cm_quat"][:3])*10)
                same(obs["proprioception"]["joint_velocities_rad_s"]["tibia_pitch"], previous["tibia_velocity_rad_s"])
                same(obs["proprioception"]["speed_mm_s"], np.linalg.norm(np.asarray(previous["velocity_world_mm_s"])[:2]))
                for resource, position, radius in (("food", food_position, 3.), ("water", [5., 7.], 2.)):
                    # Actual default water region is taken from the initial
                    # source config if explicitly supplied by this assay.
                    position = config["body"].get(resource + "_position_mm", position)
                    radius = config["body"].get(resource + "_radius_mm", radius)
                    contact = {leg: False for leg in LEGS}
                    for c in previous["contacts"]:
                        if c["active"] and c["is_tarsal"] and c["dist_cm"] <= 0:
                            if np.linalg.norm(np.asarray(c["position_mm"][:2])-position) <= radius:
                                contact[c["leg"]] = True
                    assert obs[resource + "_contact_by_leg"] == contact
                    assert obs["taste_" + resource] == any(contact.values())
                for e in encoders:
                    local = e["actual_local_observation"]
                    assert local == {"t_s": obs["t_s"], "antenna_odor": obs["antenna_odor"],
                        "hunger": obs["physiology"]["hunger"], "food_contact_by_leg": obs["food_contact_by_leg"],
                        "tibia_pitch_velocity_rad_s": obs["proprioception"]["joint_velocities_rad_s"]["tibia_pitch"]}
                    check_drive(e["actual_drive"], ids)
                concentration = np.asarray(obs["antenna_odor"])
                occupancy = concentration/(1e8+concentration)
                odor_rates = 5 + 145*occupancy*(1+.5*np.clip(obs["physiology"]["hunger"], 0, 1))/(1+adaptation)
                adaptation += (occupancy-adaptation)*(1-np.exp(-DT/.3))
                expected_indices = [np.concatenate(odor_groups)]
                expected_rates = [np.repeat(odor_rates, [len(g) for g in odor_groups])]
                for k, members in enumerate((taste_groups, club_groups)):
                    rates = (np.asarray([100. if obs["food_contact_by_leg"][leg] else 0. for leg in LEGS]) if k == 0 else
                             30*np.abs(previous["tibia_velocity_rad_s"])/(5+np.abs(previous["tibia_velocity_rad_s"])))
                    active = [(g, r) for g, r in zip(members, rates, strict=True) if r > 0]
                    expected_indices.append(np.concatenate([g for g, _ in active]) if active else np.array([], dtype=int))
                    expected_rates.append(np.concatenate([np.full(len(g), r) for g, r in active]) if active else np.array([]))
                for e, indices, rates in zip(encoders, expected_indices, expected_rates, strict=True):
                    same(e["actual_drive"]["indices"], indices)
                    maxima["encoder_rate_error_hz"] = max(maxima["encoder_rate_error_hz"], same(e["actual_drive"]["rates_hz"], rates, 1e-12))
                combined_indices, combined_rates = list(expected_indices), list(expected_rates)
                if condition["design"]["assay"] == "motor_probe":
                    combined_indices.append(groups["motor_forward"])
                    combined_rates.append(np.full(len(groups["motor_forward"]), 40.))
                check_drive(neural_start["actual_drive"], ids)
                same(neural_start["actual_drive"]["indices"], np.concatenate(combined_indices))
                same(neural_start["actual_drive"]["rates_hz"], np.concatenate(combined_rates), 1e-12)
                assert neural_start["actual_drive"]["ordered_drive_sha256"] == neural["ordered_drive_sha256"]
                assert neural_start["rng_state"] == neural["rng_state_before"]
                if neural_records:
                    assert neural_records[-1]["rng_state_after"] == neural["rng_state_before"]
                assert neural_start["duration_ms"] == 2.
                same([neural_start["brain_t_ms"], neural["start_ms"]], [ticks*2.]*2, 1e-9)
                same(neural["end_ms"], (ticks+1)*2., 1e-9)
                assert neural["blocked_neuron_count"] == blocked_count
                assert neural["sensory_outgoing_mask"] == (len(expected_blocks) == 3)
                assert state["neural"]["blocked_synaptic_outputs"] == sorted(expected_blocks)
                assert neural["finite_voltage"] and neural["finite_synaptic_state"] and neural["listed_input_refractory_zero"]
                counts = neural["all_neuron_counts"]
                assert len(set(counts["neuron_ids"])) == len(counts["neuron_ids"])
                assert counts["neuron_ids"] == sorted(counts["neuron_ids"])
                assert all(isinstance(x, int) and x > 0 for x in counts["counts"])
                assert sum(counts["counts"]) == counts["spikes"] == neural["total_spikes"]
                assert counts["event_sha256"] == neural["full_event_sha256"]
                count_map = dict(zip(counts["neuron_ids"], counts["counts"], strict=True))
                for key, g in groups.items():
                    event_group = neural["sensory_and_motor_events"][key]
                    expected = {int(i): count_map[int(i)] for i in ids[g] if int(i) in count_map}
                    assert dict(zip(event_group["neuron_ids"], event_group["counts"], strict=True)) == expected
                    assert event_group["spikes"] == sum(expected.values()) == neural["monitored_counts"][key]
                    totals[key] += event_group["spikes"]
                    if key.startswith("motor_"):
                        instantaneous = event_group["spikes"] / len(g) / DT
                        rate_state[key] += (1-np.exp(-DT/.05))*(instantaneous-rate_state[key])
                        maxima["motor_filtered_rate_error_hz"] = max(maxima["motor_filtered_rate_error_hz"], same(
                            rate_state[key], state["neural"]["output_rates"][key.removeprefix("motor_")], 1e-10))
                muted = condition["design"]["motor_mute"] and 300 <= ticks < 600
                if muted:
                    expected_motor = {"behavior": "rest", "left": 0., "right": 0.}
                    totals["muted_spikes"] += neural["total_spikes"]
                elif rate_state["motor_feeding"] > 5 and (obs["taste_food"] or obs["taste_water"]):
                    expected_motor = {"behavior": "feed", "left": 0., "right": 0.}
                else:
                    forward = np.clip(rate_state["motor_forward"]/40, 0, 1)
                    turn = np.clip((rate_state["motor_turn_left"]-rate_state["motor_turn_right"])/50, -.6, .6)
                    expected_motor = ({"behavior": "rest", "left": 0., "right": 0.} if forward < .05 and abs(turn) < .05 else
                        {"behavior": "walk", "left": float(np.clip(forward-turn, -1.2, 1.2)), "right": float(np.clip(forward+turn, -1.2, 1.2))})
                assert state["motor"]["behavior"] == expected_motor["behavior"]
                same([state["motor"][k] for k in ("left", "right")], [expected_motor[k] for k in ("left", "right")], 1e-12)
                totals["behavior_" + expected_motor["behavior"]] += 1
                if first_feed_end is None and expected_motor["behavior"] == "feed":
                    first_feed_end = (ticks+1)*DT
                enabled = expected_motor["behavior"] == "walk"
                assert d["command"]["policy_enabled"] == enabled
                if enabled:
                    lo, hi = [np.asarray(metadata[k], dtype=np.float32) for k in ("action_minimum", "action_maximum")]
                    canonical = np.asarray(d["canonical_action"], dtype=np.float32)
                    expected_action = lo + np.float32(.5)*(np.clip(canonical, -1, 1)+1)*(hi-lo)
                else:
                    expected_action = np.r_[np.ones(6), np.zeros(53)]
                same(d["native_action"], expected_action)
                same(np.asarray(d["ctrl"])[d["actuator_ids"]], d["native_action"])
                assert d["action_names"] == metadata["action_names"]
                drives = np.clip([state["motor"]["left"], state["motor"]["right"]], -1.2, 1.2)
                same(d["command"]["speed_mm_s"], 20*np.clip(drives.mean(), 0, 1) if enabled else 0., 1e-12)
                same(d["command"]["yaw_rad_s"], 2*np.clip((drives[1]-drives[0])/1.2, -1, 1) if enabled else 0., 1e-12)
                for key in ("qpos", "qvel", "qacc", "act", "ctrl", "native_action", "pose_cm_quat", "antenna_positions_mm", "tibia_velocity_rad_s"):
                    assert np.isfinite(d[key]).all()
                    physical_digest.update(key.encode()+b"\0")
                    physical_digest.update(np.asarray(d[key], dtype="<f8").tobytes())
                assert d["finite"] and not d["source_terminated"] and not any(d["warnings"])
                minimum_voltage = min(minimum_voltage, neural["voltage_mv"]["min"])
                minimum_upright = min(minimum_upright, d["up_z"])
                maximum_acceleration = max(maximum_acceleration, max(abs(x) for x in d["qacc"]))
                assert d["tick"] == ticks+1
                maxima["clock_error_s"] = max(maxima["clock_error_s"], same(
                    [state["t_s"], state["brain_t_s"], d["native_time_s"]], [(ticks+1)*DT]*3, 1e-9))
                p, resources = state["physiology"], state["resources"]
                nutrient = resources["food"]["remaining"] + p["crop"] + p["energy"] + p["energy_spent"] - resources["food"]["initial"] - initial_phys["energy"]
                water = resources["water"]["remaining"] + p["hydration"] + p["water_lost"] - resources["water"]["initial"] - initial_phys["hydration"]
                maxima["resource_balance_abs"] = max(maxima["resource_balance_abs"], abs(nutrient), abs(water))
                assert maxima["resource_balance_abs"] < 1e-8
                same([nutrient, water], [state["resource_balance"]["nutrient"], state["resource_balance"]["water"]])
                assert 0 <= p["energy"] <= p["capacities"]["energy"] and 0 <= p["crop"] <= p["capacities"]["crop"]
                assert 0 <= p["hydration"] <= p["capacities"]["hydration"]
                same(resources["food"]["initial"]-resources["food"]["remaining"], p["food_ingested"], 1e-12)
                food_delta = p["food_ingested"] - previous_phys["food_ingested"]
                assert 0 <= food_delta <= .08*DT+1e-12
                if food_delta > 0:
                    assert expected_motor["behavior"] == "feed" and np.linalg.norm(np.asarray(d["velocity_world_mm_s"])[:2]) <= 1.
                    assert any(c["active"] and c["is_tarsal"] and c["dist_cm"] <= 0 and
                               np.linalg.norm(np.asarray(c["position_mm"][:2])-food_position) <= 3.
                               for c in d["contacts"])
                totals["spikes"] += neural["total_spikes"]
                assert state["neural"]["total_spikes"] == totals["spikes"]
                assert state["neural"]["spikes"] == neural["total_spikes"]
                sweet_positive |= bool(len(expected_indices[1]))
                for key, value in condition["neural_intervals"][ticks].items():
                    assert neural[key] == value
                assert physical["checks"] == condition["physical_intervals"][ticks]
                neural_records.append({k: neural[k] for k in ("tick", "ordered_drive_sha256", "rng_state_before", "rng_state_after", "downstream_event_sha256")})
                points.append(np.asarray(d["pose_cm_quat"][:3])*10)
                previous, previous_phys, bundles, ticks = d, p, [], ticks+1
        assert ticks == total and not bundles
        assert sum(event_counts.values()) == archived["records"]
        assert event_counts == {"condition_start": 1, "initial": 1, "condition_end": 1, "coupling_start": total,
            "encoder": 3*total, "neural_start": total, "neural_complete": total, "physical_complete": total,
            **({"intervention_start": 2, "intervention_complete": 2} if condition["design"]["motor_mute"] else {})}
        assert intervention_events == ([(event, tick) for tick in (300, 600) for event in ("intervention_start", "intervention_complete")] if condition["design"]["motor_mute"] else [])
        assert totals["spikes"] == displayed["total_graph_spikes"]
        assert totals["muted_spikes"] == displayed["muted_neural_spikes"]
        assert totals["motor_feeding"] == displayed["feeding_motor_spikes"]
        assert {g: totals[g] for g in ("odor", "sweet", "club")} == displayed["source_spikes_by_group"]
        assert {k: totals["behavior_"+k] for k in ("rest", "walk", "feed")} == displayed["requested_behavior_counts"]
        assert sweet_positive == displayed["sweet_input_ever_positive"]
        same(state["physiology"]["food_ingested"], displayed["food_ingested"])
        assert displayed["first_feed_completed_interval_end_s"] == first_feed_end
        same(minimum_voltage, displayed["minimum_neural_voltage_mv"])
        same(minimum_upright, displayed["minimum_upright_z"])
        same(maximum_acceleration, displayed["maximum_qacc_abs_native"])
        same(maxima["clock_error_s"], displayed["maximum_clock_error_s"])
        same(maxima["resource_balance_abs"], displayed["maximum_resource_residual"])
        points = np.asarray(points)
        speed = np.linalg.norm(np.diff(points[:, :2], axis=0), axis=1)/DT
        same(speed.sum()*DT, displayed["path_length_mm_2ms_chords"], 1e-12)
        same(np.linalg.norm(points[-1, :2]-points[0, :2]), displayed["net_planar_displacement_mm"], 1e-12)
        for key, begin, end in (("muted_steady_speed_median_mm_s_0p85_to1p2", 425, 600), ("after_restore_speed_median_mm_s_1p5_to2", 750, 1000)):
            if total >= end:
                same(np.median(speed[begin:end]), displayed[key], 1e-12)
            else:
                assert displayed[key] is None
        condition_reviews.append({"condition": name, "ticks_checked": total, "event_counts": dict(event_counts),
            "maximum_errors": dict(maxima), "totals": dict(totals), "archived_journal_sha256": sha(raw),
            "archive_files_verified": len(archived["all_original_file_hashes"]), "frames_verified": len(condition["frames"]),
            "complete_native_trajectory_sha256": physical_digest.hexdigest(),
            "source_output_blocked_cell_count": blocked_count, "all_saved_tick_checks_pass": True})
        pairs.append(neural_records)
    mechanisms = {}
    for name, a, b in (("locomotor", pairs[0], pairs[1]), ("on_food", pairs[2], pairs[3])):
        first_input = first_downstream = first_matched = None
        prefix = True
        for x, y in zip(a, b, strict=True):
            if x["ordered_drive_sha256"] != y["ordered_drive_sha256"]:
                prefix = False
                if first_input is None:
                    first_input = x["tick"]
            if prefix:
                assert x["rng_state_before"] == y["rng_state_before"] and x["rng_state_after"] == y["rng_state_after"]
            if x["downstream_event_sha256"] != y["downstream_event_sha256"]:
                if first_downstream is None:
                    first_downstream = x["tick"]
                if prefix and first_matched is None:
                    first_matched = x["tick"]
        actual = {"first_ordered_input_difference_tick": first_input,
                  "first_non_sensory_spike_event_difference_tick": first_downstream,
                  "first_downstream_difference_with_identical_input_history_tick": first_matched}
        for key, value in actual.items():
            assert results["paired_mechanisms"][name][key] == summary["paired_mechanisms"][name][key] == value
        mechanisms[name] = actual
    assert mechanisms["locomotor"]["first_downstream_difference_with_identical_input_history_tick"] is not None
    assert summary["conditions"][2]["feeding_motor_spikes"] == summary["conditions"][3]["feeding_motor_spikes"] == 28
    same(summary["conditions"][2]["food_ingested"], summary["conditions"][3]["food_ingested"])
    assert condition_reviews[2]["complete_native_trajectory_sha256"] == condition_reviews[3]["complete_native_trajectory_sha256"]
    receipt = {"scope": "Independent saved-journal arithmetic and source review; no neural, policy or physics reruns",
        "passed_saved_journal_checks": True, "all_declared_sources_match_revision": all(x["matches_plan"] for x in frozen_sources.values()),
        "frozen_source_revision": REVISION, "source_hashes": frozen_sources,
        "reviewer_script_sha256": sha(__file__), "dataset_rows_sha256": sha(neurons_path),
        "artifact_hashes": {p.name: sha(p) for p in (OUT/"plan.json", OUT/"results.json", OUT/"summary.json", OUT/"archival.json")},
        "conditions": condition_reviews, "paired_mechanisms": mechanisms,
        "summary_slices": {"path": "Euclidean planar displacement chords of every completed2ms interval including initial pose; not native inertial-center velocity",
            "mute": "speed[425:600],175 intervals with start times0.850 through1.198s and end times0.852 through1.200s",
            "restore": "speed[750:1000],250 intervals with start times1.500 through1.998s and end times1.502 through2.000s",
            "first_feed": "End time of first interval commanded feed, not neural spike time, contact onset, or first swallowed nutrient"},
        "source_review": {"output_block": "neural.py checks ablated[source] only at synaptic delivery; source thresholds/spikes and supplied Poisson drives remain enabled. Full blocked mask is asserted by producer each tick; journal retains count and named groups, not full mask.",
            "no_double_counting": "Exactly one neural start/complete and one physical completion per tick; unique input indices and all-neuron IDs, summed per-neuron counts equal fullbatch and cumulative telemetry totals. Motor/source group totals checked separately, never added to fullgraph totals.",
            "passive_capture": "Capture wrapper calls each original encoder/brain advance once; recorded states do not create additional input or RNG draws.",
            "physical_feedback": "Actual prior native tibia velocity and tarsal floor contacts agree with input observations; independently calculated encoder transfer and filtered motor decoder agree with delivered commands.",
            "odor": "Bilateral sampled concentrations and transfer are retained. Source converts actual cached antenna origins from mm to m and queries PuffField; producer separately checks pure sample equality. Puff birth/state arrays are not journaled, so spatial plume sampling cannot be independently recomputed from these journals alone."},
        "limits": ["Ordered spike event timestamps are represented by hashes and per-neuron counts; hashes compare saved event equality but cannot be recomputed without original ID/time arrays.",
                   "Complete voltage, synaptic and blocked-mask arrays are not journaled; their finite/mask assertions are producer evidence, not an independent full-state check.",
                   "Reset/render/advance0 state equality is a producer assertion; journals retain only the resulting initial state.",
                   "Source output block preserves the input mechanism, not all later sensory-source spikes; recurrent feedback can change them.",
                   "The matched-prefix divergence demonstrates graph transmission of the collective blocked inputs; it does not isolate odor versus club contribution.",
                   "On-food MN9 count and abstract intake are unchanged by sweet-source block despite downstream spike differences; no sweet necessity claim.",
                   "No natural navigation, physiological firing/voltage, male-body mechanics, swallowing, full-cycle reproduction or persistent-viewer validation."]}
    (OUT / "independent-review.json").write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"passed_saved_journal_checks": True, "all_declared_sources_match_revision": receipt["all_declared_sources_match_revision"],
        "ticks": sum(c["ticks_checked"] for c in condition_reviews), "conditions": len(condition_reviews), "paired_mechanisms": mechanisms}, indent=2))


if __name__ == "__main__":
    main()
