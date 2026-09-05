#!/usr/bin/env python3
"""Presentation of the frozen replay; no fitting, resampling or model selection."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "validation/inhibitory-factorial"
OUT = ROOT / "validation/inhibitory-factorial-figures"
CONDITIONS = ["locomotor_feedback", "locomotor_sensory_block", "sensory_only"]
LABELS = ["Locomotor feedback", "Sensory outputs blocked", "Sensory only"]
COLORS = ["#247ba0", "#c16121", "#477e46"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError("Preserve the earlier figures")
    results = json.loads((SOURCE / "results.json").read_text())
    if not results["passed"]:
        raise ValueError("This presentation requires a completed numerical result")
    OUT.mkdir()
    data = {}
    for condition in CONDITIONS:
        for arm in ["C0", "C1", "H0", "H1"]:
            path = SOURCE / f"{condition}-{arm}.npz"
            if sha(path) != results["artifacts"][str(path.relative_to(ROOT))]["sha256"]:
                raise ValueError("Changed source archive")
            with np.load(path) as z:
                data[condition, arm] = {k: z[k] for k in ["state", "fired", "pre_threshold_voltage_mv"]}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), sharex=True)
    time_s = np.arange(120001) * .0001
    for row, family in enumerate(["C", "H"]):
        for j, target in enumerate(["67052 · lLN2T_b", "13314 · M_vPNml50"]):
            ax = axes[row, j]
            for condition, label, color in zip(CONDITIONS, LABELS, COLORS):
                for package, style in [(0, "-"), (1, "--")]:
                    ax.plot(time_s, data[condition, family + str(package)]["state"][:, j, 0],
                            color=color, linestyle=style, lw=.65, alpha=.9,
                            label=label if package == 0 else None, rasterized=True)
            ax.axhline(-75., color="0.45", lw=.7, linestyle=":")
            ax.axhline(-52., color="0.65", lw=.7, linestyle=":")
            ax.set_xlim(0, 12)
            ax.set_ylim((-550, -40) if family == "C" else (-76, -43))
            ax.grid(alpha=.15)
            ax.set_ylabel(f"{family}0 / {family}1 voltage (mV)")
            if row == 0:
                ax.set_title(target)
            else:
                ax.set_xlabel("Recorded history time (s)")
    axes[0, 0].legend(loc="upper right", frameon=False, fontsize=8)
    fig.suptitle("Fixed-source inhibitory factorial · all histories and both handling packages", fontsize=14)
    fig.text(.5, .02, "Solid: freeze / reject / reset. Dashed: decay / receive / retain. Rows use different voltage scales.\n"
             "All 0.1 ms post-step samples shown; no smoothing. One original seed; no recurrent or physiological validation.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=[0, .065, 1, .95])
    fig.savefig(OUT / "all-histories.png", dpi=170)
    plt.close(fig)

    # This onset window is an explanatory, post-result visualization only.
    fig, axes = plt.subplots(3, 2, figsize=(12, 8.3), sharex=True)
    onset_conditions = ["locomotor_feedback", "sensory_only"]
    onset_time = np.arange(1001) * .1
    for col, condition in enumerate(onset_conditions):
        for arm, color in [("H0", "#247ba0"), ("H1", "#c16121")]:
            d = data[condition, arm]
            for row in range(3):
                axes[row, col].plot(onset_time, d["state"][:1001, 1, row], label=arm, color=color, lw=1.2)
            spikes = np.flatnonzero(d["fired"][:1000, 1])
            axes[0, col].scatter(spikes * .1, d["pre_threshold_voltage_mv"][spikes, 1], color=color, s=20, marker="x")
        for row, label in enumerate(["Voltage (mV)", "Positive state p (effective mV)", "Inhibitory state h (leak ratio)"]):
            axes[row, col].set_ylabel(label)
            axes[row, col].grid(alpha=.15)
            axes[row, col].set_xlim(0, 100)
        axes[0, col].axhline(-75., color="0.5", lw=.7, linestyle=":")
        axes[0, col].axhline(-45., color="0.5", lw=.7, linestyle=":")
        axes[0, col].set_ylim(-76, -43)
        axes[0, col].set_title(condition.replace("_", " ").capitalize())
        axes[0, col].legend(frameon=False)
        axes[-1, col].set_xlabel("Recorded history time (ms)")
    fig.suptitle("13314 · effect of retaining synapses after the isolated startup spike", fontsize=14)
    fig.text(.5, .015, "Post-result explanatory view of 0–100 ms; x markers are pre-reset threshold crossings.\n"
             "H0/H1 have identical spike times. Effective states are not measured currents or conductances.", ha="center", fontsize=9)
    fig.tight_layout(rect=[0, .055, 1, .95])
    fig.savefig(OUT / "projection-neuron-onset.png", dpi=170)
    plt.close(fig)
    receipt = {"source_results_sha256": sha(SOURCE / "results.json"),
               "script_sha256": sha(__file__), "source_plan_sha256": results["plan_sha256"],
               "operation": "All native post-step samples plotted without smoothing/resampling. Onset view chosen after results solely to explain handling difference; not a new test window.",
               "files": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in OUT.glob("*.png")}}
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
