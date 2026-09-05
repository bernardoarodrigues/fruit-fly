#!/usr/bin/env python3
"""Plot saved scalar-reference predictions. Does not execute the model."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "validation/synaptic-depression-reference"


def path(suffix):
    return Path(str(PREFIX) + suffix)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if path("-plot-receipt.json").exists():
        raise FileExistsError("Preserve the saved plot receipt")
    result = json.loads(path("-results.json").read_text())
    assert result["passed"] and not result["model_fitted"] and not result["runtime_integrated"]
    with np.load(path("-arrays.npz")) as src:
        arrays = {name: src[name] for name in src.files}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.labelcolor": "#273348", "text.color": "#273348"})
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.7))
    for rate, color in zip((15, 20, 50), ("#116E80", "#945998", "#CD6940")):
        times = arrays[f"train_{rate}_times_s"][28:]*1000
        amps = arrays[f"train_{rate}_normalized_test_amplitude"]
        axes[0].plot(times, amps, "o-", ms=3, lw=1.6, color=color, label=f"{rate} Hz")
    axes[0].set(xlabel="Time after test onset (ms)", ylabel="Event amplitude / first test amplitude",
                xlim=(0, 500), ylim=(0, 1.05), title="A  Event depression after 7 Hz baseline")
    axes[0].legend(frameon=False)
    for window, marker, color in ((.1, "o", "#116E80"), (.5, "s", "#945998")):
        rows = [r for r in result["charge_predictions"] if r["window_s"] == window]
        axes[1].plot([r["rate_hz"] for r in rows], [r["normalized_to_same_window_100hz"] for r in rows],
                     marker=marker, color=color, label=f"First {int(window*1000)} ms")
    axes[1].axhline(1, color="#B5BCC5", lw=1, ls=":")
    axes[1].set(xlabel="Test rate (Hz)", ylabel="Integrated response / 100 Hz value",
                xlim=(10, 210), ylim=(0, 1.25), title="B  Normalized response area")
    axes[1].set_xticks([20, 50, 100, 200])
    axes[1].legend(frameon=False, loc="lower right")
    t = arrays["recovery_200_baseline1_time_after_nominal_train_end_s"]
    v = arrays["recovery_200_baseline1_fraction_of_deficit_recovered"]
    axes[2].plot(t, v, color="#116E80", lw=2)
    axes[2].axhline(.99, color="#B5BCC5", lw=1, ls=":")
    axes[2].set(xlabel="Time since recovery anchor (s)", ylabel="Fraction of initial deficit recovered",
                xlim=(0, 2), ylim=(0, 1.05), title="C  Same recovery law in every scenario")
    axes[2].text(.08, .22, "Recovery τ = 0.3 s\n99% of deficit recovered in 1.382 s", transform=axes[2].transAxes)
    for ax in axes:
        ax.grid(axis="y", alpha=.16)
        ax.title.set_fontsize(10)
        ax.tick_params(labelsize=9)
    fig.suptitle("Published scalar reference under fly stimulation scenarios", fontsize=16, x=.07, ha="left", y=.96)
    fig.text(.07, .865, "MODEL PREDICTIONS ONLY · f = 0.75 · recovery τ = 300 ms · response decay = 2 ms", fontsize=10)
    fig.text(.07, .03, "No fly data fitted or overlaid. Event timing and recovery anchors are declared simulation conventions. Area has arbitrary amplitude units.", fontsize=9)
    fig.subplots_adjust(left=.075, right=.98, top=.74, bottom=.20, wspace=.34)
    fig.savefig(path("-predictions.png"), dpi=160)
    fig.savefig(path("-predictions.svg"))
    plt.close(fig)
    sources = [Path(__file__).resolve(), path("-results.json"), path("-arrays.npz")]
    receipt = {"scope": "Plot of saved predictions only; no model execution or measurement comparison",
               "matplotlib_version": matplotlib.__version__,
               "inputs": {str(p.relative_to(ROOT)): sha(p) for p in sources},
               "outputs": {str(path(s).relative_to(ROOT)): sha(path(s)) for s in ("-predictions.png", "-predictions.svg")}}
    path("-plot-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
