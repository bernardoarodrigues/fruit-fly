#!/usr/bin/env python3
"""Read-only anatomy audit and isolated tests of the unchanged LIF impulse.

No full graph simulation, parameter estimation, or runtime file writes. Prepare
the plan before --run; the plan pins this script and all source/input bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.data import Connectome
from fruitfly.neural import LIFNetwork, LIFParameters

PREFIX = ROOT / "validation/orn-pn-transfer"
GRAPH = ROOT / "data/processed/malecns_v1"
GLOMERULI = ("DM6", "VM2", "DL5", "DM4")
ALIAS_COLUMNS = ("type", "hemibrainType", "flywireType", "supertype", "synonyms")
PARAMETERS = LIFParameters()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def path(suffix):
    return Path(str(PREFIX) + suffix)


def write_json(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def source_paths():
    return [Path(__file__).resolve(), ROOT / "fruitfly/neural.py", ROOT / "fruitfly/data.py",
            GRAPH / "manifest.json", GRAPH / "neurons.feather",
            *(GRAPH / (n + ".npy") for n in ("neuron_ids", "indptr", "targets", "contact_counts", "weights", "signs")),
            ROOT / "validation/orn-pn-physiology-sources.json",
            ROOT / "data/raw/orn-pn-physiology/kazama-wilson-2008.pdf",
            ROOT / "data/raw/orn-pn-physiology/kazama-wilson-2008-supplement.pdf"]


def prepare():
    if path("-plan.json").exists():
        raise FileExistsError("Do not overwrite a frozen plan")
    write_json(path("-plan.json"), {
        "schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sources": {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in source_paths()},
        "parameters": asdict(PARAMETERS), "glomeruli": GLOMERULI,
        "population_rule": "Exact case-sensitive ORN_{g} and {g}_adPN. Retain other matching ALPN classes separately. Retain case-insensitive alias candidates with inclusion/exclusion reasons; do not merge optic Dm4/Dm6 with antennal DM4/DM6.",
        "edges": "Enumerate Cartesian product of selected ORNs and all selected ALPNs; retain zero-contact pairs, cross-glomerulus pairs, unknown root sides, and other PN classes separately. No strength filter.",
        "impulse": "Closed-form unthresholded passive response for tau_m=20 ms, tau_s=5 ms, actual float32 graph weights; threshold crossing is a separate prediction, not an unthresholded runtime run.",
        "isolated_cases": "Deterministic real same-glomerulus adPN minimum, median-nearest, maximum, largest subthreshold, smallest threshold-crossing edge by continuous peak. Also synthetic 1-,161-,162-contact positive numerical controls and -1-contact sign control. One forced presynaptic spike at stamp 0, no drive/incoming PN/feedback; 60 ms at unchanged 0.1 ms dt.",
        "initialization": "Set only the isolated presynaptic initial voltage to threshold+1 mV; default resting PN, no changes to parameters, thresholds, refractory behavior or engine source.",
        "sample_clock": "Initial state at time0; kernel spike stamp=tick*dt; delivery occurs in synapses slot at stamp1.8ms and its post-step state sample is1.9ms. Compare closed form relative to the post-delivery boundary, without altering delay.",
        "checks": {"closed_form_voltage_absolute_tolerance_mv": 2e-11, "closed_form_synaptic_absolute_tolerance_mv": 2e-11,
                   "actual_source_spikes": 1, "edge_visits": 1, "no_parameter_changes": True,
                   "crossing": "First sampled passive > threshold predicts PN spike at sample_time-dt. Before crossing use closed form; at and after crossing require native reset and zero synaptic state. No biological fit acceptance threshold."},
        "claim_limit": "Numerical/anatomical audit only. Female pooled somatic unitary measurements cannot directly calibrate male point-neuron voltage or per-contact release-site strength. No runtime promotion."
    })
    print(f"Prepared {path('-plan.json').relative_to(ROOT)} sha256={sha(path('-plan.json'))}")


def passive(t, w):
    tm, ts = PARAMETERS.membrane_tau_ms, PARAMETERS.synapse_tau_ms
    return w * ts / (tm-ts) * (np.exp(-np.asarray(t)/tm) - np.exp(-np.asarray(t)/ts))


def population(neurons):
    pattern = r"(?<![A-Za-z0-9])(?:" + "|".join(GLOMERULI) + r")(?![A-Za-z0-9])"
    mask = pd.Series(False, index=neurons.index)
    for c in ALIAS_COLUMNS:
        mask |= neurons[c].fillna("").astype(str).str.contains(pattern, case=False, regex=True)
    candidates = neurons.loc[mask].copy()
    roles, glomeruli, decisions = [], [], []
    for _, row in candidates.iterrows():
        typ = str(row["type"])
        if typ in {f"ORN_{g}" for g in GLOMERULI} and row["class"] == "olfactory":
            role, glom, decision = "ORN", typ[4:], "included_exact_olfactory_type"
        elif typ in {f"{g}_adPN" for g in GLOMERULI} and row["class"] == "ALPN":
            role, glom, decision = "adPN", typ[:-5], "included_exact_adPN_type"
        elif row["class"] == "ALPN" and re.match(r"^(DM6|VM2|DL5|DM4)_", typ):
            role, glom, decision = "other_PN", typ.split("_")[0], "retained_other_PN_class"
        else:
            matches = sorted(set(re.findall(pattern, " ".join(str(row[c]) for c in ALIAS_COLUMNS))))
            role, glom = "excluded_candidate", "|".join(matches)
            decision = "ambiguous_exact_case_alias_requires_review" if matches else "case_collision_not_exact_antennal_glomerulus"
        roles.append(role); glomeruli.append(glom); decisions.append(decision)
    candidates["audit_role"] = roles
    candidates["audit_glomerulus"] = glomeruli
    candidates["audit_decision"] = decisions
    columns = ["bodyId", "audit_role", "audit_glomerulus", "audit_decision", "type", "class", "superclass",
               "rootSide", "somaSide", "entryNerve", "consensus_nt", "model_sign", *ALIAS_COLUMNS[1:]]
    candidates = candidates[columns].sort_values("bodyId")
    selected = candidates.loc[candidates.audit_role != "excluded_candidate"].copy()
    return candidates, selected


def distribution(values):
    v = np.asarray(values, dtype=float)
    if not len(v):
        return {"n": 0}
    return {"n": len(v), "min": float(v.min()), "median": float(np.median(v)),
            "mean": float(v.mean()), "max": float(v.max()),
            "q25": float(np.quantile(v, .25)), "q75": float(np.quantile(v, .75))}


def run():
    plan = json.loads(path("-plan.json").read_text())
    if path("-results.json").exists():
        raise FileExistsError("Do not overwrite an executed receipt")
    for name, record in plan["sources"].items():
        assert sha(ROOT / name) == record["sha256"], f"Source changed: {name}"
    assert asdict(PARAMETERS) == plan["parameters"]
    checks = []
    def check(name, value, **details):
        checks.append({"name": name, "pass": bool(value), **details})

    # Source bytes were all checked above, and Connectome verifies its manifest.
    graph = Connectome.load(GRAPH, verify=True)
    counts = np.load(GRAPH / "contact_counts.npy", mmap_mode="r")
    candidates, neurons = population(graph.neurons)
    candidates.to_csv(path("-candidates.csv"), index=False)
    neurons.to_csv(path("-neurons.csv"), index=False)
    check("no_unresolved_exact_case_candidates", not candidates.audit_decision.eq("ambiguous_exact_case_alias_requires_review").any())
    orns = neurons[neurons.audit_role == "ORN"]
    pns = neurons[neurons.audit_role.isin(["adPN", "other_PN"])]
    check("ORN_annotation_and_sign", orns.consensus_nt.eq("acetylcholine").all() and orns.model_sign.eq(1).all() and orns.entryNerve.eq("AN").all())
    check("core_PN_annotation_and_sign", pns.loc[pns.audit_role.eq("adPN"), "consensus_nt"].eq("acetylcholine").all())
    index = {int(i): k for k, i in enumerate(graph.neuron_ids)}
    peak_t = PARAMETERS.membrane_tau_ms * PARAMETERS.synapse_tau_ms / (PARAMETERS.membrane_tau_ms-PARAMETERS.synapse_tau_ms) * np.log(PARAMETERS.membrane_tau_ms/PARAMETERS.synapse_tau_ms)
    peak_factor = float(passive(peak_t, 1.))
    gap = PARAMETERS.threshold_mv-PARAMETERS.resting_mv
    rows = []
    for _, pre in orns.iterrows():
        i = index[int(pre.bodyId)]
        first, last = int(graph.indptr[i]), int(graph.indptr[i+1])
        outgoing = {int(graph.targets[k]): k for k in range(first, last)}
        for _, post in pns.iterrows():
            j = index[int(post.bodyId)]
            edge = outgoing.get(j)
            n = int(counts[edge]) if edge is not None else 0
            w = float(graph.weights[edge]) if edge is not None else 0.
            relation = "same_glomerulus_" + post.audit_role if pre.audit_glomerulus == post.audit_glomerulus else "cross_glomerulus_" + post.audit_role
            rows.append(dict(pre_id=int(pre.bodyId), post_id=int(post.bodyId), pre_index=i, post_index=j,
                             pre_type=pre["type"], post_type=post["type"], pre_glomerulus=pre.audit_glomerulus,
                             post_glomerulus=post.audit_glomerulus, pre_root_side=pre.rootSide, post_soma_side=post.somaSide,
                             relation=relation, edge_index=edge if edge is not None else -1, contacts=n,
                             weight_mv=w, weight_float32_hex=np.float32(w).tobytes().hex(),
                             passive_peak_mv=w*peak_factor, passive_continuous_crosses_threshold=w*peak_factor > gap))
    pairs = pd.DataFrame(rows)
    pairs.to_csv(path("-pairs.csv"), index=False)
    edges = pairs.loc[pairs.contacts > 0].copy()
    edges.to_csv(path("-edges.csv"), index=False)
    expected_weights = edges.contacts.to_numpy(np.float32) * np.float32(graph.manifest["weight_scale_mv"])
    check("all_selected_edge_float32_weights_match_contact_rule", np.array_equal(expected_weights, edges.weight_mv.to_numpy(np.float32)))
    check("all_selected_direct_weights_positive", bool((edges.weight_mv > 0).all()))
    core = edges.loc[edges.relation == "same_glomerulus_adPN"].sort_values(["contacts", "pre_id", "post_id"])
    group_summary = {}
    for g in GLOMERULI:
        potential = pairs.loc[(pairs.relation == "same_glomerulus_adPN") & pairs.pre_glomerulus.eq(g)]
        actual = potential.loc[potential.contacts > 0]
        o = orns.loc[orns.audit_glomerulus.eq(g)]
        p = pns.loc[pns.audit_glomerulus.eq(g) & pns.audit_role.eq("adPN")]
        group_summary[g] = {"ORNs": len(o), "ORN_root_sides": o.rootSide.fillna("null").value_counts().to_dict(),
                            "adPNs": len(p), "adPN_ids_by_soma_side": {side: grp.bodyId.tolist() for side, grp in p.groupby("somaSide", dropna=False)},
                            "potential_pairs": len(potential), "direct_edges": len(actual), "absent_pairs": len(potential)-len(actual),
                            "contacts": distribution(actual.contacts), "weight_mv": distribution(actual.weight_mv),
                            "passive_peak_mv": distribution(actual.passive_peak_mv),
                            "passive_threshold_crossing_edges": int(actual.passive_continuous_crosses_threshold.sum()),
                            "contact_total": int(actual.contacts.sum()),
                            "annotation_side_groups": [{"ORN_root_side": sides[0], "PN_soma_side": sides[1], "direct_edges": len(grp), "contacts": distribution(grp.contacts)} for sides, grp in actual.groupby(["pre_root_side", "post_soma_side"], dropna=False)]}

    # Choose cases by frozen rank rules; biological values are not tuned.
    representatives = [("real_minimum", core.iloc[0]),
                       ("real_median_nearest", core.iloc[(core.contacts.to_numpy()-np.median(core.contacts)).__abs__().argmin()]),
                       ("real_maximum", core.iloc[-1])]
    for label, frame in (("real_largest_subthreshold", core.loc[~core.passive_continuous_crosses_threshold]),
                         ("real_smallest_crossing", core.loc[core.passive_continuous_crosses_threshold])):
        if len(frame):
            representatives.append((label, frame.iloc[-1] if "subthreshold" in label else frame.iloc[0]))
    cases = [{"name": label, "origin": "actual_male_same_glomerulus_adPN_edge", "pre_id": int(row.pre_id),
              "post_id": int(row.post_id), "contacts": int(row.contacts), "weight_mv": float(row.weight_mv)} for label, row in representatives]
    for n in (1, 161, 162, -1):
        cases.append({"name": f"synthetic_contacts_{n}", "origin": "synthetic_numerical_control_not_additional_anatomy",
                      "pre_id": -1, "post_id": -2, "contacts": abs(n), "weight_mv": float(np.float32(n)*np.float32(.275))})
    saved = {}
    summaries = []
    dt = PARAMETERS.dt_ms
    steps = round(60/dt)
    sample_time = np.arange(steps+1)*dt
    delivery_index = round(PARAMETERS.delay_ms/dt)+1
    delivered_time = delivery_index*dt
    elapsed = np.maximum(0, sample_time-delivered_time)
    available = np.arange(steps+1) >= delivery_index
    for case in cases:
        network = LIFNetwork([case["pre_id"], case["post_id"]], [0, 1, 1], [1], [case["weight_mv"]], seed=0)
        network.voltage_mv[0] = PARAMETERS.threshold_mv+1.
        voltage = np.empty((steps+1, 2)); synaptic = np.empty_like(voltage)
        voltage[0] = network.voltage_mv; synaptic[0] = network.synaptic_mv
        spikes, traversals = [], 0
        for k in range(steps):
            batch = network.step()
            spikes.extend(zip(batch.indices.tolist(), batch.times_ms.tolist()))
            traversals += batch.traversed_edges
            voltage[k+1] = network.voltage_mv; synaptic[k+1] = network.synaptic_mv
        spikes = np.asarray(spikes, dtype=float).reshape(-1, 2)
        expected_voltage = PARAMETERS.resting_mv + passive(elapsed, case["weight_mv"])
        expected_synaptic = np.where(available, case["weight_mv"]*np.exp(-elapsed/PARAMETERS.synapse_tau_ms), 0.)
        crossings = np.flatnonzero(expected_voltage > PARAMETERS.threshold_mv)
        cross = int(crossings[0]) if len(crossings) else None
        mask = np.arange(steps+1) < cross if cross is not None else np.ones(steps+1, dtype=bool)
        verror = float(np.max(np.abs(voltage[mask, 1]-expected_voltage[mask])))
        gerror = float(np.max(np.abs(synaptic[mask, 1]-expected_synaptic[mask])))
        pn_spikes = spikes[spikes[:, 0] == 1, 1].tolist()
        pre_spikes = spikes[spikes[:, 0] == 0, 1].tolist()
        expected_pn = [(cross-1)*dt] if cross is not None else []
        check(case["name"]+":passive_voltage_before_any_crossing", verror < plan["checks"]["closed_form_voltage_absolute_tolerance_mv"], max_error_mv=verror)
        check(case["name"]+":passive_synaptic_before_any_crossing", gerror < plan["checks"]["closed_form_synaptic_absolute_tolerance_mv"], max_error_mv=gerror)
        check(case["name"]+":spike_stamps", pre_spikes == [0.] and pn_spikes == expected_pn,
              actual_pre_stamps_ms=pre_spikes, actual_PN_stamps_ms=pn_spikes, predicted_PN_stamps_ms=expected_pn)
        check(case["name"]+":one_edge_delivery", traversals == 1, traversals=traversals)
        check(case["name"]+":unchanged_parameters_and_clock", asdict(network.parameters) == plan["parameters"] and network.time_ms == 60.)
        check(case["name"]+":finite", np.isfinite(voltage).all() and np.isfinite(synaptic).all())
        if cross is not None:
            check(case["name"]+":reset_at_and_after_threshold", np.all(voltage[cross:, 1] == PARAMETERS.reset_mv) and np.all(synaptic[cross:, 1] == 0.))
        key = case["name"]
        saved.update({key+"_voltage_mv": voltage, key+"_synaptic_mv": synaptic, key+"_spikes_index_stamp_ms": spikes,
                      key+"_passive_voltage_mv": expected_voltage, key+"_passive_synaptic_mv": expected_synaptic})
        summaries.append({**case, "passive_continuous_extremum_delta_mv": case["weight_mv"]*peak_factor,
                          "passive_sampled_positive_peak_delta_mv": float((expected_voltage-PARAMETERS.resting_mv).max()),
                          "actual_saved_positive_peak_delta_mv": float((voltage[:, 1]-PARAMETERS.resting_mv).max()),
                          "predicted_crossing_sample_index": cross, "actual_PN_spike_stamps_ms": pn_spikes,
                          "max_precross_voltage_error_mv": verror, "max_precross_synaptic_error_mv": gerror})
    saved["sample_time_ms"] = sample_time
    np.savez_compressed(path("-traces.npz"), **saved)
    check("runtime_sources_unchanged_after_audit", all(sha(ROOT / n) == r["sha256"] for n, r in plan["sources"].items()))
    result = {
        "schema": 1, "finished_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(path("-plan.json")),
        "passed": all(c["pass"] for c in checks), "checks": checks,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "graph": {k: graph.manifest[k] for k in ("dataset", "sex", "neurons", "edges", "retained_synaptic_contacts", "weight_scale_mv", "license")},
        "selection": {"ORNs": len(orns), "adPNs": int(neurons.audit_role.eq("adPN").sum()), "other_PNs": int(neurons.audit_role.eq("other_PN").sum()),
                      "candidate_decisions": candidates.audit_decision.value_counts().to_dict(),
                      "excluded_candidate_types": candidates.loc[candidates.audit_role.eq("excluded_candidate"), "type"].value_counts().to_dict(),
                      "all_PN_candidate_types": pns["type"].value_counts().to_dict(),
                      "pair_count": len(pairs), "direct_edges": len(edges),
                      "edge_relation_counts": edges.relation.value_counts().to_dict(),
                      "edge_relation_contact_totals": {k: int(v) for k, v in edges.groupby("relation").contacts.sum().items()}},
        "same_glomerulus_adPN_summary": group_summary,
        "all_core_edges": {"edges": len(core), "contacts": distribution(core.contacts), "passive_peak_mv": distribution(core.passive_peak_mv),
                           "passive_threshold_crossing_edges": int(core.passive_continuous_crosses_threshold.sum())},
        "analytical": {"equations": "dg/dt=-g/tau_s; du/dt=(-u+g)/tau_m; g(0+)=signed weight; u(0)=0; u(t)=w*tau_s/(tau_m-tau_s)*(exp(-t/tau_m)-exp(-t/tau_s)).",
                       "time_to_extremum_after_delivery_ms": float(peak_t), "extremum_factor_per_weight": peak_factor,
                       "positive_peak_per_nominal_contact_mv": .275*peak_factor,
                       "positive_peak_per_actual_float32_one_contact_mv": float(np.float32(.275))*peak_factor,
                       "threshold_gap_mv": gap, "continuous_threshold_nominal_contact_equivalent": gap/(.275*peak_factor),
                       "measurement_6p19mv_nominal_contact_equivalent_noncalibrating": 6.19/(.275*peak_factor),
                       "postdelivery_state_sample_ms": delivered_time,
                       "interpretation": "Contact-equivalent arithmetic is dimensional context only, not a fitted contact number, release-site estimate, somatic prediction or gain recommendation."},
        "isolated_cases": summaries, "isolated_neurons_per_case": 2, "isolated_duration_ms_per_case": 60,
        "full_graph_simulated": False, "parameters_changed": False,
        "artifacts": {str(path(s).relative_to(ROOT)): {"sha256": sha(path(s)), "bytes": path(s).stat().st_size} for s in ("-candidates.csv", "-neurons.csv", "-pairs.csv", "-edges.csv", "-traces.npz")},
    }
    write_json(path("-results.json"), result)
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "selection": result["selection"], "core": result["all_core_edges"], "analytical": result["analytical"], "cases": summaries}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else run()
