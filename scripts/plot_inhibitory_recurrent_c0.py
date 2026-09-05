#!/usr/bin/env python3
"""Render only frozen, independently audited C0 rates and paired contrasts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "validation/inhibitory-recurrent-panel-c0-audit-summary.json"
EXPECTED = "0942b7b1ba57a33391488aa36eb069f514e394a4295cd3b6a99b8e43f9394256"
CONDITIONS = ["constant_baseline", "ethyl_acetate", "isoamyl_acetate"]
COLORS = {"constant_baseline": "#226D78", "ethyl_acetate": "#D46725", "isoamyl_acetate": "#8951A1"}
LABELS = {"constant_baseline": "Constant baseline", "ethyl_acetate": "Ethyl acetate (EA)", "isoamyl_acetate": "Isoamyl acetate (IA)"}
SEEDS = [11, 12, 13]
STYLES = {11: "-", 12: (0, (5, 2.5)), 13: (0, (1.2, 2))}
MARKERS = {11: "o", 12: "s", 13: "^"}
SEED_COLORS = {11: "#1D3344", 12: "#59758A", 13: "#92A8B3"}


def record(path):
    b = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-stem", default="validation/inhibitory-recurrent-panel-c0-figure")
    args = parser.parse_args()
    stem = ROOT / args.output_stem
    outputs = [stem.with_suffix(suffix) for suffix in [".png", ".svg", ".json"]]
    if any(p.exists() for p in outputs):
        raise FileExistsError("Preserve the first rendering; use a distinct output stem for any visual correction")
    source_record = record(SOURCE)
    if source_record["sha256"] != EXPECTED:
        raise ValueError("Frozen audited aggregate hash changed")
    data = json.loads(SOURCE.read_text())
    if not data["passed"] or data["independently_reviewed_trials"] != 15:
        raise ValueError("Complete certified C0 evidence is required")
    trials = {(t["spec"]["seed"], t["spec"]["condition"]): t for t in data["trials"]}
    contrasts = {(r["seed"], r["cohort"]): r for r in data["contrasts"]}
    edges = [tick * data["dt_s"] for tick in data["window_edges_ticks"]]
    midpoints = [(a + b) / 2 for a, b in zip(edges[:-1], edges[1:])]
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10.5, "axes.titlesize": 12.5,
                         "axes.labelsize": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#89949B", "axes.linewidth": .7,
                         "xtick.color": "#46545E", "ytick.color": "#46545E",
                         "text.color": "#1D2D38", "axes.labelcolor": "#1D2D38",
                         "svg.fonttype": "none", "svg.hashsalt": "audited-c0-0942b7b1", "savefig.facecolor": "white"}):
        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.subplots_adjust(left=.075, right=.97, bottom=.17, top=.785, hspace=.52, wspace=.25)
        fig.suptitle("C0 response and activity after input withdrawal", x=.075, y=.985, ha="left", fontsize=19, fontweight="bold")
        fig.text(.075, .942, "Audited recurrent model  ·  Seven complete windows  ·  Seeds 11, 12 and 13 shown individually", fontsize=11.5)
        condition_handles = [Line2D([], [], color=COLORS[c], lw=2.3, label=LABELS[c]) for c in CONDITIONS]
        fig.legend(handles=condition_handles, loc="upper left", bbox_to_anchor=(.068, .908), ncol=3,
                   frameon=False, handlelength=2.5, columnspacing=1.7, fontsize=10.5)
        seed_handles = [Line2D([], [], color=SEED_COLORS[s], lw=1.7, ls=STYLES[s], marker=MARKERS[s], markersize=5,
                              label=f"Seed {s}") for s in SEEDS]
        fig.legend(handles=seed_handles, loc="upper right", bbox_to_anchor=(.978, .908), ncol=3,
                   frameon=False, handlelength=2.4, columnspacing=1.4, fontsize=10.5)
        for col, (cohort, title) in enumerate([("non_source", "Non-source population"), ("first_hop_non_source", "First-hop non-source population")]):
            ax = axes[0, col]
            ax.set_title(f"{'A' if col == 0 else 'B'}  {title}  (n = {data['cohort_identity'][cohort]['n']:,})", loc="left", pad=26)
            ax.axvspan(.5, 1., color="#C9CED3", alpha=.35, linewidth=0, zorder=0)
            ax.axvline(1.5, color="#505A62", lw=1.2, ls=(0, (5, 3)), zorder=1)
            ax.text(.75, 1.026, "Odor interval", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=9, color="#626E77")
            ax.text(1.5, 1.026, "Input off", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=9, color="#626E77")
            for seed in SEEDS:
                for condition in CONDITIONS:
                    rates = trials[(seed, condition)]["cohorts"][cohort]["mean_rates_hz"]
                    ax.stairs(rates, edges, baseline=None, color=COLORS[condition], lw=1.6, ls=STYLES[seed], alpha=.9)
                    ax.plot(midpoints, rates, linestyle="none", marker=MARKERS[seed], color=COLORS[condition], markersize=3.6,
                            markeredgewidth=.5, markeredgecolor="white", alpha=.95)
            ax.set_xlim(0, 3)
            ax.set_ylim(bottom=0)
            ax.set_xticks([0, .05, .5, 1, 1.5, 2, 2.5, 3])
            ax.set_xticklabels(["0", "", "0.5", "1.0", "1.5", "2.0", "2.5", "3.0"])
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Mean firing rate (Hz per cell)")
            ax.grid(axis="y", color="#DCE2E6", linewidth=.65, alpha=.75)
            ax.set_axisbelow(True)
            bottom = axes[1, col]
            bottom.set_title(f"{'C' if col == 0 else 'D'}  Paired pulse contrasts: {title.lower()}", loc="left", pad=13)
            bottom.axhline(0, color="#55636D", lw=1.15, zorder=0)
            fields = ["EA_minus_constant_pulse_hz", "IA_minus_constant_pulse_hz", "EA_minus_IA_pulse_hz"]
            for offset, seed in zip([-.11, 0, .11], SEEDS):
                values = [contrasts[(seed, cohort)][field] for field in fields]
                bottom.scatter([x + offset for x in range(3)], values, s=55, marker=MARKERS[seed],
                               facecolor=SEED_COLORS[seed], edgecolor="white", linewidth=.7, zorder=3)
            bottom.set_xticks([0, 1, 2], ["EA − constant", "IA − constant", "EA − IA"])
            bottom.set_xlim(-.45, 2.45)
            bottom.margins(y=.23)
            bottom.set_ylabel("Pulse rate difference (Hz per cell)")
            bottom.set_xlabel("Matched within each seed; pulse window [0.5, 1.0) s")
            bottom.grid(axis="y", color="#DCE2E6", linewidth=.65, alpha=.75)
            bottom.set_axisbelow(True)
        fig.text(.075, .105, "Three numerical seeds, not biological replicates. No pooled estimates or confidence intervals.", fontsize=10.5, fontweight="bold")
        fig.text(.075, .074, "No-input and source-output-blocked controls: non-source counts are zero in every window for all three seeds.", fontsize=10.3)
        fig.text(.075, .044, "Rates include all cells in each fixed cohort. Lines show window means at their true boundaries, not instantaneous traces. All five conditions remain in the source JSON.", fontsize=9.2, color="#5D6B75")
        fig.savefig(outputs[0], dpi=200, metadata={"Software": "Matplotlib " + matplotlib.__version__})
        fig.savefig(outputs[1], metadata={"Date": None, "Title": "Audited C0 recurrent model response and input withdrawal"})
        plt.close(fig)
    if record(SOURCE) != source_record:
        raise ValueError("Source changed during rendering; retain outputs as failed rendering evidence")
    manifest = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "source": source_record,
                "script": record(Path(__file__)), "outputs": [record(p) for p in outputs[:2]],
                "python": platform.python_version(), "matplotlib": matplotlib.__version__, "rendering_only": True,
                "data_fields": ["trials[].cohorts[non_source|first_hop_non_source].mean_rates_hz",
                                "contrasts[].EA_minus_constant_pulse_hz", "contrasts[].IA_minus_constant_pulse_hz", "contrasts[].EA_minus_IA_pulse_hz"],
                "display": {"time_boundaries_s": edges, "odor_interval_s": [.5, 1], "input_off_s": 1.5,
                            "numeric_seeds": SEEDS, "conditions_drawn": CONDITIONS, "all_conditions_retained_in_source": True,
                            "seed_encoding": "11 solid/circle, 12 dashed/square, 13 dotted/triangle; small x offsets in contrast panels only",
                            "no_pooling_no_confidence_intervals": True},
                "limits": ["Existing audited means and contrasts only; no new model execution or statistical analysis.",
                           "Graphical stairs depict half-open-window means, not instantaneous dynamics.",
                           "The 3-second C0 data do not establish physiological accuracy, indefinite stability or promotion."]}
    with outputs[2].open("x") as f:
        json.dump(manifest, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"manifest": record(outputs[2]), "outputs": manifest["outputs"]}))


if __name__ == "__main__":
    main()
