#!/usr/bin/env python3
"""Independent saved-array review: direct CSR lookup and matrix-exponential impulse.

No producer/runtime imports, simulator construction, or parameter fitting.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy.linalg import expm
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "validation/orn-pn-transfer"


def artifact(suffix):
    return Path(str(BASE) + suffix)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    plan = json.loads(artifact("-plan.json").read_text())
    result = json.loads(artifact("-results.json").read_text())
    checks = []

    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})
        if not value:
            raise AssertionError(name)

    check("matching producer plan", sha(artifact("-plan.json")) == result["plan_sha256"])
    for rel, record in {**plan["sources"], **result["artifacts"]}.items():
        p = ROOT / rel
        check("source/artifact " + rel, p.stat().st_size == record["bytes"] and sha(p) == record["sha256"])
    graph = ROOT / "data/processed/malecns_v1"
    neurons = pd.read_feather(graph / "neurons.feather")
    gloms = tuple(plan["glomeruli"])
    orn = neurons.loc[neurons["type"].isin(["ORN_" + g for g in gloms]) & neurons["class"].eq("olfactory")]
    pn = neurons.loc[neurons["class"].eq("ALPN") & neurons["type"].fillna("").str.match(r"^(DM6|VM2|DL5|DM4)_")]
    selected = pd.read_csv(artifact("-neurons.csv"))
    check("independent exact population IDs", set(selected.bodyId) == set(orn.bodyId) | set(pn.bodyId))
    check("174 ORNs, 14 adPNs, 2 separate other PNs", len(orn) == 174 and len(pn) == 16
          and pn["type"].str.endswith("_adPN").sum() == 14)
    aliases = ("type", "hemibrainType", "flywireType", "supertype", "synonyms")
    expected_candidates = set()
    for row in neurons[["bodyId", *aliases]].itertuples(index=False, name=None):
        tokens = re.findall(r"[A-Za-z0-9]+", " ".join(str(x) for x in row[1:] if x is not None))
        if any(token.upper() in gloms for token in tokens):
            expected_candidates.add(row[0])
    candidates = pd.read_csv(artifact("-candidates.csv"))
    check("complete alias candidates via independent tokenization", set(candidates.bodyId) == expected_candidates)
    collisions = candidates[candidates.audit_decision.eq("case_collision_not_exact_antennal_glomerulus")]
    check("optic case collisions excluded", len(collisions) == 161 and not set(collisions.bodyId) & set(selected.bodyId))
    check("unknown ORN root sides retained", orn.rootSide.eq("unknown").sum() == 13
          and selected.loc[selected.audit_role.eq("ORN"), "rootSide"].eq("unknown").sum() == 13)

    arrays = {name: np.load(graph / (name + ".npy"), mmap_mode="r")
              for name in ("neuron_ids", "indptr", "targets", "weights", "contact_counts")}
    lookup = {int(body_id): i for i, body_id in enumerate(arrays["neuron_ids"])}
    pairs = pd.read_csv(artifact("-pairs.csv"))
    check("Cartesian product complete with unique pairs", len(pairs) == len(orn) * len(pn)
          and len(pairs.drop_duplicates(["pre_id", "post_id"])) == len(pairs))
    check("Cartesian product identity sets", set(pairs.pre_id) == set(orn.bodyId) and set(pairs.post_id) == set(pn.bodyId))
    checked_contacts = checked_weights = checked_indices = True
    for row in pairs.itertuples(index=False):
        i, j = lookup[row.pre_id], lookup[row.post_id]
        lo, hi = arrays["indptr"][[i, i + 1]]
        found = np.flatnonzero(arrays["targets"][lo:hi] == j)
        assert len(found) <= 1
        edge = int(lo + found[0]) if len(found) else -1
        count = int(arrays["contact_counts"][edge]) if edge >= 0 else 0
        weight = np.float32(arrays["weights"][edge]) if edge >= 0 else np.float32(0)
        checked_contacts &= count == row.contacts
        checked_weights &= weight.tobytes().hex() == row.weight_float32_hex and weight == np.float32(row.weight_mv)
        checked_indices &= (i, j, edge) == (row.pre_index, row.post_index, row.edge_index)
    check("every pair direct CSR contact lookup including absent edges", checked_contacts)
    check("every pair actual float32 weight bytes", checked_weights)
    check("every pair graph indices", checked_indices)
    core = pairs[(pairs.relation == "same_glomerulus_adPN") & (pairs.contacts > 0)]
    check("core anatomical totals", len(core) == 616 and core.contacts.sum() == 25884
          and (core.contacts.min(), core.contacts.max()) == (2, 155))
    p = plan["parameters"]
    A = np.array([[-1 / p["membrane_tau_ms"], 1 / p["membrane_tau_ms"]],
                  [0., -1 / p["synapse_tau_ms"]]])
    optimum = minimize_scalar(lambda t: -(expm(A * t) @ [0., 1.])[0], bounds=(0., 60.), method="bounded")
    factor = -optimum.fun
    check("independently optimized impulse extremum", abs(optimum.x - result["analytical"]["time_to_extremum_after_delivery_ms"]) < 2e-6
          and abs(factor - result["analytical"]["extremum_factor_per_weight"]) < 1e-13)
    peaks = core.weight_mv.to_numpy() * factor
    check("all core passive peaks and no crossing", np.allclose(peaks, core.passive_peak_mv, rtol=0, atol=2e-12)
          and max(peaks) < p["threshold_mv"] - p["resting_mv"])
    npz = np.load(artifact("-traces.npz"))
    times = npz["sample_time_ms"]
    check("complete 601-sample clock", np.array_equal(times, np.arange(601) * .1))
    # A spike at tick zero is delivered after integration at stamp 1.8 ms;
    # the first stored post-delivery state is the sample at 1.9 ms.
    delivery = round(p["delay_ms"] / p["dt_ms"]) + 1
    matrices = [expm(A * ((k - delivery) * p["dt_ms"])) if k >= delivery else np.zeros((2, 2))
                for k in range(len(times))]
    summaries = []
    for case in result["isolated_cases"]:
        name, w = case["name"], case["weight_mv"]
        theoretical = np.array([M @ [0., w] for M in matrices])
        expected_v = theoretical[:, 0] + p["resting_mv"]
        expected_g = theoretical[:, 1]
        crossing = np.flatnonzero(expected_v > p["threshold_mv"])
        crossing_index = int(crossing[0]) if len(crossing) else None
        check(name + " passive voltage arrays", np.allclose(npz[name + "_passive_voltage_mv"], expected_v, rtol=0, atol=2e-11))
        check(name + " passive synaptic arrays", np.allclose(npz[name + "_passive_synaptic_mv"], expected_g, rtol=0, atol=2e-11))
        if crossing_index is not None:
            expected_v[crossing_index:] = p["reset_mv"]
            expected_g[crossing_index:] = 0.
        v, g = npz[name + "_voltage_mv"], npz[name + "_synaptic_mv"]
        check(name + " actual PN reset and passive trajectory", np.allclose(v[:, 1], expected_v, rtol=0, atol=2e-11)
              and np.allclose(g[:, 1], expected_g, rtol=0, atol=2e-11))
        check(name + " source initialization and reset", v[0, 0] == p["threshold_mv"] + 1
              and np.all(v[1:, 0] == p["reset_mv"]) and np.all(g[:, 0] == 0))
        expected_spikes = [[0., 0.]] + ([[1., (crossing_index - 1) * p["dt_ms"]]] if crossing_index is not None else [])
        check(name + " actual ordered spike stamps", np.array_equal(npz[name + "_spikes_index_stamp_ms"], expected_spikes))
        summaries.append({"case": name, "predicted_crossing_sample": crossing_index,
                          "max_voltage_error_mv": float(np.max(abs(v[:, 1] - expected_v))),
                          "max_synaptic_error_mv": float(np.max(abs(g[:, 1] - expected_g)))})
    receipt = {"passed": all(c["passed"] for c in checks), "method": "Saved-data review using direct CSR lookup, independent alias tokenization, scipy.linalg.expm and bounded extremum optimization; no producer/runtime imports or simulation",
        "script_sha256": sha(__file__), "plan_sha256": sha(artifact("-plan.json")),
        "result_sha256": sha(artifact("-results.json")), "checks": checks,
        "cases": summaries, "pair_count": len(pairs), "core_edges": len(core),
        "core_contacts": int(core.contacts.sum()), "optimized_peak_ms": float(optimum.x),
        "core_passive_peak_mv": {"min": float(min(peaks)), "median": float(np.median(peaks)), "max": float(max(peaks))},
        "limits": "Does not establish per-contact release sites, female-to-male physiological equivalence, somatic voltage mapping, recurrent response or biological behavior. An engine construction count/edge traversal summary is producer evidence; saved arrays independently verify its specified isolated input response."}
    artifact("-independent-review.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": receipt["passed"], "checks": len(checks), "pairs": len(pairs), "cases": summaries}, indent=2))


if __name__ == "__main__":
    main()
