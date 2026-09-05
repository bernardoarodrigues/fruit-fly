"""Run a bounded, pinned author-code reproduction of the Lanz hDeltaK/PFG model.

The GPL-3.0 author notebook is downloaded to ignored tmp/, hash checked, and
executed without changing its model functions. This wrapper is separate from
fruitfly's male graph/runtime. It reproduces one Figure 3 parameter point with
fast and slow PFG signaling, plus a smaller-step numerical comparison.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import platform
import time
import urllib.request
import warnings

os.environ.setdefault("MPLBACKEND", "Agg")
import numpy as np


COMMIT = "b52ee5742e96a579356bc475d01a08d640759789"
NOTEBOOK_SHA256 = "f3174d6a279fd5b488c79910d8336c2ae2baa69380e7268dd93450e908226a54"
URL = (f"https://raw.githubusercontent.com/nagellab/Lanzetal2025/{COMMIT}/"
       "model_code/recurrent_python_clean.ipynb")


def load_author_notebook(path: Path) -> dict:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=30) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != NOTEBOOK_SHA256:
            raise ValueError("Downloaded notebook does not match the audited source")
        path.write_bytes(content)
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != NOTEBOOK_SHA256:
        raise ValueError("Local notebook does not match the audited source")
    return json.loads(content)


def author_namespace(notebook: dict) -> dict:
    namespace = {}
    for index in (0, 3, 5, 8):
        source = "".join(notebook["cells"][index]["source"])
        exec(compile(source, f"Lanzetal2025-cell-{index}", "exec"), namespace)
    return namespace


def simulate(notebook: dict, *, fast: bool) -> tuple[dict, dict]:
    ns = author_namespace(notebook)
    source = "".join(notebook["cells"][10]["source"])
    tree = ast.parse(source)
    changed = 0
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "state_fast" for t in node.targets):
            node.value = ast.Constant(int(fast))
            changed += 1
    assert changed == 1
    ast.fix_missing_locations(tree)
    start = time.perf_counter()
    log = io.StringIO()
    with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stdout(log):
        warnings.simplefilter("always")
        exec(compile(tree, "Lanzetal2025-cell-10", "exec"), ns)
    info = {"wall_seconds": time.perf_counter() - start,
            "author_stdout": log.getvalue().strip(),
            "warnings": sorted(set(str(w.message) for w in caught)),
            "author_fitted_decay_per_sample": float(ns["exc_recoveries"][0, 0])}
    fit_rate = info["author_fitted_decay_per_sample"]
    info["author_fit_tau_s"] = -ns["dt"] / fit_rate if fit_rate < 0 else None
    # The author's zero fit value means their classifier did not identify
    # decay; it is not proof of indefinitely persistent activity.
    info["author_zero_fit_means"] = "classified nondecaying or fit not accepted"
    return ns, info


def metrics(ns: dict) -> dict:
    dt = ns["dt"]
    r = ns["r_HDK_ode"]
    if not np.isfinite(r).all():
        raise ValueError("Nonfinite author simulation output")
    contrast = np.ptp(r, axis=1)
    offset = int(ns["I_ext_ends"][0])
    initial = contrast[offset]
    after = contrast[offset:]
    below = np.flatnonzero(after <= initial / np.e)
    return {"min_activity": float(r.min()), "max_activity": float(r.max()),
            "contrast_at_stimulus_offset": float(initial),
            "contrast_1s_after_offset": float(contrast[offset + round(1 / dt)]),
            "contrast_5s_after_offset": float(contrast[offset + round(5 / dt)]),
            "contrast_final": float(contrast[-1]),
            "first_one_over_e_crossing_after_offset_s": float(below[0] * dt) if len(below) else None,
            "hdk_bump_peak_index_at_offset": int(np.argmax(r[offset])),
            "hdk_bump_peak_index_final": int(np.argmax(r[-1]))}


def finer_comparison(ns: dict) -> dict:
    fn = ns["run_simulation_ode"]
    kwargs = {key: ns[key] for key in inspect.signature(fn).parameters}
    for key in ("I_ext_HDK", "I_ext_PFG", "I_ext_EXR3"):
        kwargs[key] = np.repeat(kwargs[key], 2, axis=1)
    kwargs["dt"] = ns["dt"] / 2
    start = time.perf_counter()
    finer = fn(**kwargs)[0][::2]
    coarse = ns["r_HDK_ode"]
    return {"dt_s": kwargs["dt"], "wall_seconds": time.perf_counter() - start,
            "finite": bool(np.isfinite(finer).all()),
            "hdk_max_abs_activity_difference": float(np.max(np.abs(finer - coarse))),
            "hdk_rms_activity_difference": float(np.sqrt(np.mean((finer - coarse) ** 2)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=Path(
        "tmp/navigation-memory/upstream/model_code/recurrent_python_clean.ipynb"))
    parser.add_argument("--output", type=Path, default=Path("validation/navigation-memory-author-code.json"))
    args = parser.parse_args()
    notebook = load_author_notebook(args.notebook)
    result = {"scope": "bounded author-code reproduction; not a male whole-brain simulation or full figure replication",
              "repository": "https://github.com/nagellab/Lanzetal2025",
              "commit": COMMIT, "source_url": URL, "notebook_sha256": NOTEBOOK_SHA256,
              "upstream_code_license": "GPL-3.0", "python": platform.python_version(),
              "numpy": np.__version__, "source_cells": [0, 3, 5, 8, 10],
              "model_function_changes": [],
              "experiment_changes": ["state_fast selects 0 then 1", "extra dt/2 diagnostic bypasses author's fixed-sample fit helper"],
              "parameters": {"hdk_n": 30, "pfg_n": 18, "global_inhibitory_n": 1,
                             "inactive_extra_exc_unit_n": 1, "alpha": 10, "dt_s": 0.001,
                             "duration_s": 20, "stimulus_on_s": 5, "stimulus_off_s": 9,
                             "exc": 5.6, "inh": 3.6, "b_all_per_s": 25,
                             "a_fast_per_s": 4.63, "a_slow_per_s": 0.64,
                             "gaussian_sigma_both_directions_rad": 0.25,
                             "input": "1+cos(preferred angle) into both local populations"}, "runs": {}}
    traces = {}
    for fast in (False, True):
        label = "fast" if fast else "slow"
        ns, info = simulate(notebook, fast=fast)
        info.update(metrics(ns))
        if not fast:
            info["numerical_comparison"] = finer_comparison(ns)
        result["runs"][label] = info
        traces[label] = (ns["t"].copy(), np.ptp(ns["r_HDK_ode"], axis=1), ns["r_HDK_ode"].copy())
        print(label, json.dumps(info), flush=True)
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for column, label in enumerate(("fast", "slow")):
        t, contrast, activity = traces[label]
        axes[0, column].imshow(activity.T, origin="lower", aspect="auto", extent=[0, 20, 0, 30],
                               vmin=0, vmax=1, cmap="magma")
        axes[0, column].set(title=f"{label.capitalize()} PFG: author code", ylabel="hDeltaK index", xlabel="Time (s)")
        axes[1, column].plot(t, contrast)
        axes[1, column].axvspan(5, 9, color="gray", alpha=.2)
        axes[1, column].set(xlabel="Time (s)", ylabel="hDeltaK population max − min", xlim=(0, 20))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plot = args.output.with_suffix(".png")
    fig.savefig(plot, dpi=160)
    result["plot"] = str(plot)
    csv = args.output.with_suffix(".csv")
    np.savetxt(csv, np.column_stack((traces["fast"][0][::10], traces["fast"][1][::10], traces["slow"][1][::10])),
               delimiter=",", header="time_s,fast_hdk_contrast,slow_hdk_contrast", comments="")
    result["contrast_trace_100hz"] = str(csv)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
