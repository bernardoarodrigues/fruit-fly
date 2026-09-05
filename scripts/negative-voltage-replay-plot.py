#!/usr/bin/env python3
"""Plot saved two-cell replay states; no replay or simulation execution."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT/"validation/negative-voltage-replay"


def path(suffix):
    return Path(str(PREFIX)+suffix)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if path("-plot-receipt.json").exists():
        raise FileExistsError("Preserve plot receipt")
    result = json.loads(path("-results.json").read_text())
    assert result["passed"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "text.color": "#273348"})
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0), sharey=True)
    configs = [("locomotor_feedback", "Locomotor feedback", "#116E80"),
               ("locomotor_sensory_block", "Odor/sweet/club outputs blocked", "#945998"),
               ("sensory_only", "Sensory only", "#CD6940")]
    input_paths = [Path(__file__).resolve(), path("-results.json")]
    for name, label, color in configs:
        archive = path(f"-{name}-arrays.npz")
        input_paths.append(archive)
        with np.load(archive) as src:
            times = src["sample_time_ms"]/1000
            voltage = src["voltage_mv"]
        for j, ax in enumerate(axes):
            ax.plot(times, voltage[:,j], lw=.8, alpha=.8, color=color, label=label)
    for ax, title in zip(axes, ("67052 · lLN2T_b", "13314 · M_vPNml50")):
        ax.axhline(-52, color="#A7ADB7", lw=1, ls="--")
        ax.set(title=title, xlabel="Recorded experiment time (s)", xlim=(0,12))
        ax.grid(axis="y", alpha=.16)
    axes[0].set_ylabel("Replayed point-neuron voltage (model mV)")
    fig.suptitle("Negative endpoint states reproduced from recorded inputs", fontsize=16, x=.075, ha="left", y=.97)
    fig.text(.075,.88,"Two target cells only · source spikes held fixed · exact endpoint agreement · no physiological voltage calibration", fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.52,.04), ncol=3, frameon=False)
    fig.text(.075,.018,"Dashed line: −52 mV model rest. All saved 0.1 ms state samples are plotted. No gain or parameter changes.",fontsize=9)
    fig.subplots_adjust(left=.09, right=.975, top=.77, bottom=.22, wspace=.15)
    fig.savefig(path("-voltages.png"), dpi=170)
    plt.close(fig)
    receipt = {"scope":"Read-only plot of saved replay arrays", "matplotlib_version":matplotlib.__version__,
               "inputs":{str(p.relative_to(ROOT)):sha(p) for p in input_paths},
               "outputs":{str(path("-voltages.png").relative_to(ROOT)):sha(path("-voltages.png"))}}
    path("-plot-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")


if __name__=="__main__":
    main()
