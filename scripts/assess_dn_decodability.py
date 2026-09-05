#!/usr/bin/env python3
"""Frozen odor-contrast assay; fits diagnostic readouts, never a motor policy.

All feature matrices come from the full MaleCNS conductance simulation. No
positions, odor-source locations, body reward, or selected foraging trajectories
are inputs to this experiment. Fixed priors, split and ridge penalty are declared
before evaluation, and all outcomes are saved, including failed generalization.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import hashlib
import json
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.conductance import ConductanceDrive, ConductanceNetwork, ConductanceParameters
from fruitfly.data import Connectome


CONTRASTS = [-.75, -.25, 0., .25, .75]
ALPHA = 1.0  # Fixed after standardizing and dividing by sqrt(variable features).
BASELINE_MS = 100.
STIMULUS_MS = 100.
COUPLING_MS = 5.


def fit_ridge(x, y):
    """Fixed-penalty dual ridge with intercept and training-only preprocessing."""
    mean, scale = x.mean(axis=0), x.std(axis=0)
    keep = scale > 1e-8
    feature_normalizer = np.sqrt(max(1, keep.sum()))
    z = (x[:, keep] - mean[keep]) / scale[keep] / feature_normalizer
    ymean = float(y.mean())
    dual = np.linalg.solve(z @ z.T + ALPHA * np.eye(len(z)), y - ymean)
    return {"mean": mean, "scale": scale, "keep": keep,
            "coef": z.T @ dual, "intercept": ymean, "feature_normalizer": feature_normalizer}


def predict(model, x):
    keep = model["keep"]
    return ((x[:, keep] - model["mean"][keep]) / model["scale"][keep] / model["feature_normalizer"]) @ model["coef"] + model["intercept"]


def metrics(y, pred):
    nonzero = y != 0
    denominator = float(np.square(y - y.mean()).sum())
    return {"n": len(y), "rmse": float(np.sqrt(np.square(y - pred).mean())),
            "r2": 1 - float(np.square(y - pred).sum()) / denominator if denominator else None,
            "sign_accuracy_nonzero": float((np.sign(y[nonzero]) == np.sign(pred[nonzero])).mean()) if nonzero.any() else None,
            "mean_abs_prediction_equal_input": float(np.abs(pred[~nonzero]).mean()) if (~nonzero).any() else None,
            "predictions": pred.tolist()}


def main():
    started = perf_counter()
    output = Path("validation/dn-decodability.json")
    bulk = Path("data/derived/dn-decodability.npz")
    graph = Connectome.load("data/processed/malecns_v1", verify=True)
    frame = graph.neurons
    dn = np.flatnonzero(frame.superclass.eq("descending_neuron").to_numpy()).astype(np.int32)
    left = graph.select(["ORN_DM1", "ORN_DM4"], side="L")
    right = graph.select(["ORN_DM1", "ORN_DM4"], side="R")
    sensory = np.concatenate([left, right])
    assert len(dn) and len(left) and len(right) and not np.intersect1d(dn, sensory).size
    recorded = np.concatenate([dn, sensory])
    params = replace(ConductanceParameters(), dt_ms=.2, voltage_method="pade22")
    brain = ConductanceNetwork.from_connectome(graph, parameters=params, seed=101)
    brain.advance(.2, outputs=[])
    brain.reset(seed=101)

    # Input rates are artificial presynaptic conductance events. The actual
    # modeled ORN spike rates are measured separately, never equated with input.
    def epoch(rate_left, rate_right, duration_ms):
        rates = np.r_[np.full(len(left), rate_left), np.full(len(right), rate_right)]
        drive = ConductanceDrive(sensory, rates_hz=rates)
        count = np.zeros(len(recorded), np.int64)
        spikes = edges = 0
        for _ in range(round(duration_ms / COUPLING_MS)):
            batch = brain.advance(COUPLING_MS, drive=drive, outputs=recorded)
            count += batch.counts(recorded)
            spikes += batch.total_spikes
            edges += batch.traversed_edges
        return count / (duration_ms / 1000), spikes, edges

    rows, baseline, responses = [], [], []
    total_spikes = total_edges = 0

    def append(split, seed, mean, contrast, base, block=None, ablated=False):
        nonlocal total_spikes, total_edges
        rates = [mean * (1 + contrast), mean * (1 - contrast)]
        t0 = perf_counter()
        response, spikes, edges = epoch(*rates, STIMULUS_MS)
        baseline.append(base.copy())
        responses.append(response)
        rows.append({"split": split, "seed": seed, "input_mean_hz": mean,
                     "input_contrast": contrast, "input_event_rates_hz": rates,
                     "block": block, "orn_outgoing_ablated": ablated,
                     "network_spikes": spikes, "traversed_edges": edges,
                     "stimulus_wall_seconds": perf_counter() - t0,
                     "actual_orn_output_hz": [float(response[len(dn):len(dn)+len(left)].mean()),
                                              float(response[len(dn)+len(left):].mean())]})
        total_spikes += spikes
        total_edges += edges
        if len(rows) % 10 == 0:
            print(f"{len(rows)} responses; {split}; elapsed {perf_counter()-started:.1f}s", flush=True)

    for split, seeds, means in [
        ("train", [101, 102, 103], [40., 100.]),
        ("heldout_seed", [1001, 1002, 1003], [40., 100.]),
        ("heldout_seed_and_intensity", [1001, 1002, 1003], [70., 130.]),
        ("orn_outgoing_ablation", [1001, 1002], [100.]),
    ]:
        for seed in seeds:
            for mean in means:
                for contrast in CONTRASTS:
                    brain.reset(seed=seed)
                    ablated = split == "orn_outgoing_ablation"
                    brain.ablate(sensory, enabled=ablated)
                    base, spikes, edges = epoch(5., 5., BASELINE_MS)
                    total_spikes += spikes
                    total_edges += edges
                    append(split, seed, mean, contrast, base, ablated=ablated)

    # Same learned readout in an evolving network, with a single initial
    # baseline and no state resets between stimuli. Label order is fixed.
    sequence = [-.75, .25, .75, -.25, 0., .75, -.75, 0., -.25, .25]
    for seed in [2001, 2002]:
        brain.reset(seed=seed)
        brain.ablate(sensory, enabled=False)
        base, spikes, edges = epoch(5., 5., BASELINE_MS)
        total_spikes += spikes
        total_edges += edges
        for block, contrast in enumerate(sequence):
            append("persistent_sequence", seed, 70. if block < 5 else 130., contrast, base, block=block)

    baseline = np.asarray(baseline)
    responses = np.asarray(responses)
    corrected = responses - baseline
    sides = frame.rootSide.fillna(frame.somaSide)
    candidates = ["DNg97", "DNa01", "DNa02", "DNb05", "DNg34", "DNp09"]
    named = np.flatnonzero(frame.type.iloc[dn].isin(candidates).to_numpy())
    paired, pair_names = [], []
    for kind in sorted(frame.type.iloc[dn].dropna().unique()):
        positions_l = np.flatnonzero((frame.type.iloc[dn].eq(kind) & sides.iloc[dn].eq("L")).to_numpy())
        positions_r = np.flatnonzero((frame.type.iloc[dn].eq(kind) & sides.iloc[dn].eq("R")).to_numpy())
        if len(positions_l) and len(positions_r):
            paired.append(corrected[:, positions_l].mean(axis=1) - corrected[:, positions_r].mean(axis=1))
            pair_names.append(kind)
    orn_rates = np.column_stack([corrected[:, len(dn):len(dn)+len(left)].mean(axis=1),
                                corrected[:, len(dn)+len(left):].mean(axis=1)])
    features = {"all_descending_baseline_corrected": corrected[:, :len(dn)],
                "bilateral_dn_type_differences": np.asarray(paired).T,
                "named_motor_dn_baseline_corrected": corrected[:, named],
                "actual_orn_output_comparator": orn_rates}
    y = np.asarray([row["input_contrast"] for row in rows])
    train = np.asarray([row["split"] == "train" for row in rows])
    feature_results = {}
    rng = np.random.default_rng(90817)
    # Shuffle within each (seed,intensity) block, preserving the contrast
    # distribution and excluding all held-out labels from model construction.
    permutations = []
    for _ in range(100):
        permuted = y[train].copy()
        for start in range(0, len(permuted), len(CONTRASTS)):
            permuted[start:start+len(CONTRASTS)] = rng.permutation(permuted[start:start+len(CONTRASTS)])
        permutations.append(permuted)
    splits = list(dict.fromkeys(row["split"] for row in rows))
    for name, x in features.items():
        model = fit_ridge(x[train], y[train])
        predicted = predict(model, x)
        result = {"feature_count": x.shape[1], "variable_training_features": int(model["keep"].sum()),
                  "alpha": ALPHA, "splits": {}}
        for split in splits:
            use = np.asarray([row["split"] == split for row in rows])
            result["splits"][split] = metrics(y[use], predicted[use])
            result["splits"][split]["by_seed"] = {
                str(seed): {k: v for k, v in metrics(y[use & np.asarray([row["seed"] == seed for row in rows])],
                                                   predicted[use & np.asarray([row["seed"] == seed for row in rows])]).items() if k != "predictions"}
                for seed in sorted({row["seed"] for row in rows if row["split"] == split})}
        for split in ["heldout_seed", "heldout_seed_and_intensity", "persistent_sequence"]:
            use = np.asarray([row["split"] == split for row in rows])
            null_r2 = np.asarray([metrics(y[use], predict(fit_ridge(x[train], shuffled), x[use]))["r2"] for shuffled in permutations])
            result["splits"][split]["shuffled_training_labels_r2_median"] = float(np.median(null_r2))
            result["splits"][split]["shuffled_training_labels_r2_p95"] = float(np.quantile(null_r2, .95))
        feature_results[name] = result

    bulk.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(bulk, baseline_hz=baseline, response_hz=responses,
                        recorded_neuron_ids=graph.neuron_ids[recorded], contrasts=y,
                        **{name: x for name, x in features.items()})
    result = {"completed": True, "purpose": "Odor input contrast decodability, not motor/foraging training",
              "model": "conductance-lif-v1", "parameters": asdict(params),
              "dataset": graph.manifest["dataset"], "neurons": len(graph.neuron_ids), "edges": len(graph.targets),
              "source_weight_sha256": graph.manifest["arrays"]["weights.npy"]["sha256"],
              "input_types": ["ORN_DM1", "ORN_DM4"], "left_input_ids": graph.neuron_ids[left].tolist(),
              "right_input_ids": graph.neuron_ids[right].tolist(), "dn_count": len(dn),
              "named_motor_types": candidates, "bilateral_dn_feature_types": pair_names,
              "baseline_ms": BASELINE_MS, "stimulus_ms": STIMULUS_MS, "coupling_ms": COUPLING_MS,
              "baseline_external_event_rate_hz": 5, "target_definition": "(left input event rate - right input event rate)/(left + right)",
              "regularization": "Ridge alpha1 fixed before run; intercept plus training-only per-feature z score divided by sqrt(variable feature count); constant features omitted",
              "split_unit": "Entire neural RNG seed and intensity condition; no frame splitting",
              "permutation_control": "100 training-only label permutations within each seed/intensity block, RNG90817",
              "bulk_arrays": {"path": str(bulk), "sha256": hashlib.sha256(bulk.read_bytes()).hexdigest(), "bytes": bulk.stat().st_size},
              "network_spikes_all_epochs": total_spikes, "traversed_edges_all_epochs": total_edges,
              "total_wall_seconds": perf_counter() - started, "rows": rows, "readouts": feature_results,
              "claim_ceiling": "No wind, calibrated odor chemistry, body, reward, or biological behavior target. This assay does not establish steering, upwind navigation, foraging, or benefit over direct sensory control. No runtime decoder is exported or installed."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    for name, values in feature_results.items():
        print(name, {split: {k: round(v, 3) for k, v in m.items() if k in ("r2", "rmse", "sign_accuracy_nonzero")}
                     for split, m in values["splits"].items()}, flush=True)
    print(f"Saved {output}; wall {perf_counter()-started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
