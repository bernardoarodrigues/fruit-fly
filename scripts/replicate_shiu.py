#!/usr/bin/env python3
"""Run a declared subset of the pinned Shiu sugar-GRN/MN9 experiments.

No source code/data is vendored. Point --reference at a clean checkout of
https://github.com/philshiu/Drosophila_brain_model at PINNED_COMMIT.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.neural import LIFNetwork, SparseDrive

PINNED_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
RELEASE_FILES = {
    "630": ("2023_03_23_completeness_630_final.csv", "2023_03_23_connectivity_630_final.parquet"),
    "783": ("Completeness_783.csv", "Connectivity_783.parquet"),
}


def notebook_literal(path, name):
    notebook = json.loads(path.read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        try:
            parsed = ast.parse("".join(cell["source"]))
        except SyntaxError:
            continue
        for statement in parsed.body:
            if isinstance(statement, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in statement.targets
            ):
                return ast.literal_eval(statement.value)
    raise ValueError(f"Missing literal {name} in {path}")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def load_graph(reference, release):
    comp_name, con_name = RELEASE_FILES[release]
    ids = pd.read_csv(reference / comp_name, index_col=0).index.to_numpy(dtype=np.int64)
    columns = ["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"]
    table = pd.read_parquet(reference / con_name, columns=columns)
    pre = table[columns[0]].to_numpy(dtype=np.int64)
    post = table[columns[1]].to_numpy(dtype=np.int32)
    if pre.min() < 0 or pre.max() >= len(ids):
        raise ValueError("Source index outside completeness table")
    # Stable order preserves within-source summation order of the original table.
    if np.any(pre[1:] < pre[:-1]):
        order = np.argsort(pre, kind="stable")
        pre, post = pre[order], post[order]
        signed_count = table[columns[2]].to_numpy()[order]
    else:
        signed_count = table[columns[2]].to_numpy()
    pointers = np.concatenate(([0], np.cumsum(np.bincount(pre, minlength=len(ids))))).astype(np.int64)
    brain = LIFNetwork(ids, pointers, post, (signed_count * .275).astype(np.float32))
    return brain


def reference_parity(reference, release, brain, sensory, duration_ms, rate_hz, seed):
    """Same fixed external events on our full graph and original Brian2 builder.

    The original equations/graph/reset are imported unchanged. Its stochastic
    PoissonInput is replaced only for this numerical test by a fixed replay,
    since the engines deliberately use different random generators.
    """
    import brian2 as b
    b.start_scope()
    b.prefs.codegen.target = "numpy"
    b.defaultclock.dt = brain.parameters.dt_ms * b.ms
    spec = importlib.util.spec_from_file_location("shiu_reference_model", reference / "model.py")
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    params = dict(original.default_params)
    n_steps = round(duration_ms / brain.parameters.dt_ms)
    schedule = np.random.default_rng(seed).random((n_steps, len(sensory))) < rate_hz * brain.parameters.dt_ms / 1000
    brain.reset(seed=seed)
    outputs = []
    started = perf_counter()
    for tick in range(n_steps):
        outputs.append(brain.step(drive=SparseDrive(sensory, rates_hz=schedule[tick] * (1000 / brain.parameters.dt_ms))))
    engine_wall = perf_counter() - started
    engine_i = np.concatenate([result.indices for result in outputs])
    engine_t = np.concatenate([result.times_ms for result in outputs])
    started = perf_counter()
    comp_name, con_name = RELEASE_FILES[release]
    neurons, synapses, monitor = original.create_model(reference / comp_name, reference / con_name, params)
    neurons.rfc[sensory] = 0 * b.ms
    ticks, channel = np.nonzero(schedule)
    external = b.SpikeGeneratorGroup(len(sensory), channel, ticks * brain.parameters.dt_ms * b.ms)
    input_synapses = b.Synapses(external, neurons, on_pre="v += input_weight", namespace={"input_weight": params["w_syn"] * params["f_poi"]})
    input_synapses.connect(i=np.arange(len(sensory)), j=sensory)
    network = b.Network(neurons, synapses, monitor, external, input_synapses)
    build_wall = perf_counter() - started
    started = perf_counter()
    network.run(duration_ms * b.ms)
    reference_wall = perf_counter() - started
    reference_i, reference_t = np.asarray(monitor.i), np.asarray(monitor.t / b.ms)
    exact_indices = bool(np.array_equal(engine_i, reference_i))
    exact_ticks = bool(len(engine_t) == len(reference_t) and np.allclose(engine_t, reference_t, rtol=0, atol=1e-9))
    voltage_error = float(np.max(np.abs(brain.voltage_mv - np.asarray(neurons.v / b.mV))))
    synapse_error = float(np.max(np.abs(brain.synaptic_mv - np.asarray(neurons.g / b.mV))))
    return {
        "kind": "full_graph_numerical_parity_fixed_external_event_replay",
        "duration_ms": duration_ms, "rate_hz": rate_hz, "seed": seed,
        "external_voltage_event_count": int(schedule.sum()),
        "engine_spikes": int(len(engine_i)), "brian2_spikes": int(len(reference_i)),
        "all_spike_indices_equal": exact_indices, "all_spike_ticks_equal": exact_ticks,
        "max_final_voltage_error_mv": voltage_error,
        "max_final_synaptic_error_mv": synapse_error,
        "engine_wall_seconds": engine_wall, "brian2_build_wall_seconds": build_wall,
        "brian2_run_wall_seconds": reference_wall, "brian2_version": b.__version__,
        "parameter_precision_difference": "engine edge weights float32, original Brian2 weights float64",
        "passed": exact_indices and exact_ticks and voltage_error < 1e-3 and synapse_error < 1e-3,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--release", choices=RELEASE_FILES, default="630")
    parser.add_argument("--duration-ms", type=float, default=1000)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--rates-hz", type=float, nargs="+", default=[0, 100, 200])
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--brian-parity-ms", type=float, default=100)
    parser.add_argument("--output", type=Path, default=Path("validation/shiu/results.json"))
    args = parser.parse_args()
    if args.trials < 1 or args.duration_ms <= 0:
        parser.error("Trials and duration must be positive")
    reference = args.reference.resolve()
    commit = subprocess.check_output(["git", "-C", str(reference), "rev-parse", "HEAD"], text=True).strip()
    if commit != PINNED_COMMIT:
        raise ValueError(f"Expected source commit {PINNED_COMMIT}, got {commit}")
    subprocess.run(["git", "-C", str(reference), "diff", "--exit-code", "HEAD", "--", "model.py", "example.ipynb", "figures.ipynb", *RELEASE_FILES[args.release]], check=True, capture_output=True)
    sugar_ids = notebook_literal(reference / "figures.ipynb", "neu_sugar")
    mn9_id = notebook_literal(reference / "figures.ipynb", "id_mn9")
    print("Loading full source graph", flush=True)
    started = perf_counter()
    brain = load_graph(reference, args.release)
    load_wall = perf_counter() - started
    # Fail if the release lacks a source experiment neuron; do not silently map.
    sensory = brain.indices_for_ids(sugar_ids)
    motor = brain.indices_for_ids([mn9_id])
    print(f"Loaded {brain.n_neurons} neurons / {brain.n_edges} edges; validating numerical replay", flush=True)
    brain.advance(.1, outputs=[])  # separately exclude JIT warmup from trial times
    result = {
        "source_repository": "https://github.com/philshiu/Drosophila_brain_model",
        "source_commit": commit, "source_license": "MIT; reference code remains in its own checkout",
        "release": args.release, "notebook_declared_release": "630",
        "source_file_sha256": {name: sha256(reference / name) for name in ["model.py", "figures.ipynb", "example.ipynb", *RELEASE_FILES[args.release]]},
        "graph_sha256": brain.graph_sha256, "neuron_count": brain.n_neurons,
        "edge_count": brain.n_edges, "load_wall_seconds": load_wall,
        "parameters": asdict(brain.parameters), "sugar_grn_ids": sugar_ids,
        "readout": {"name": "MN9", "source_id": mn9_id},
        "platform": platform.platform(), "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scope": "Selected source-notebook sugar-GRN activation conditions; not all figures or biological predictive-accuracy replication",
        "published_default_duration_ms": 1000, "published_default_trials": 30,
        "duration_ms": args.duration_ms, "trials_per_rate": args.trials,
        "rates_hz": args.rates_hz, "conditions": [],
    }
    if args.brian_parity_ms > 0:
        result["numerical_parity"] = reference_parity(reference, args.release, brain, sensory, args.brian_parity_ms, 150, args.seed)
        print(json.dumps(result["numerical_parity"]), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for rate in args.rates_hz:
        records = []
        for trial in range(args.trials):
            trial_seed = args.seed + trial
            brain.reset(seed=trial_seed)
            start = perf_counter()
            activity = brain.advance(args.duration_ms, drive=SparseDrive(sensory, rates_hz=rate), outputs=motor)
            wall = perf_counter() - start
            records.append({"seed": trial_seed, "mn9_spikes": len(activity.indices),
                            "mn9_rate_hz": len(activity.indices) * 1000 / args.duration_ms,
                            "network_spikes": activity.total_spikes,
                            "traversed_edges": activity.traversed_edges, "wall_seconds": wall})
            if trial % 5 == 0 or trial + 1 == args.trials:
                print(f"rate={rate:g}Hz trial={trial+1}/{args.trials} MN9={records[-1]['mn9_rate_hz']:g}Hz wall={wall:.2f}s", flush=True)
        rates = np.array([record["mn9_rate_hz"] for record in records])
        condition = {"input_rate_hz": rate, "mn9_mean_hz": float(rates.mean()),
                     "mn9_std_hz": float(rates.std(ddof=1)) if len(rates) > 1 else None,
                     "mn9_sem_hz": float(rates.std(ddof=1) / np.sqrt(len(rates))) if len(rates) > 1 else None,
                     "trials": records}
        result["conditions"].append(condition)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    result["completed"] = True
    result["interpretation"] = {
        "quiet_control_mn9_zero": all(c["mn9_mean_hz"] == 0 for c in result["conditions"] if c["input_rate_hz"] == 0),
        "response_comparison_to_published_figure_data": "Not quantified; published numerical source figure values were not imported. Report measured rates without claiming an empirical acceptance threshold.",
        "missing_783_sugar_grn": "720575940620900446; source ID does not exist in supplied v783 completeness table; crosswalk not established",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {args.output}", flush=True)
    if "numerical_parity" in result and not result["numerical_parity"]["passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
