#!/usr/bin/env python3
"""Static scientific figure from the independently audited full-panel aggregate."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "validation/inhibitory-recurrent-panel-combined-analysis.json"
OUT = ROOT / "validation/inhibitory-recurrent-panel-combined-figure-v3.png"
MANIFEST = OUT.with_suffix(".json")


def record(path):
    b = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def main():
    if OUT.exists() or MANIFEST.exists():
        raise FileExistsError("Preserve first rendering")
    before = record(SRC)
    data = json.loads(SRC.read_text())
    assert data["passed"] and data["independently_reviewed_trials"] == 60
    arms = ["C0", "C1", "H0", "H1"]
    colors = {"C0":"#465d82", "C1":"#ca713c", "H0":"#299182", "H1":"#9a4b87"}
    styles = ["-", "--", ":"]
    markers = ["o", "s", "^"]
    seeds = [11,12,13]
    lookup = {(t["spec"]["arm"],t["spec"]["seed"],t["spec"]["condition"]):t for t in data["trials"]}
    contrasts = {(t["arm"],t["seed"],t["cohort"]):t for t in data["stimulus_contrasts"]}
    plt.rcParams.update({"font.size":11, "axes.titlesize":13, "axes.labelsize":11,
                         "axes.spines.top":False, "axes.spines.right":False, "savefig.facecolor":"white"})
    fig, axs = plt.subplots(2,2,figsize=(14,9.4))
    fig.subplots_adjust(left=.085,right=.97,bottom=.17,top=.80,hspace=.43,wspace=.25)
    fig.suptitle("Full recurrent inhibitory factorial", fontsize=21, x=.085, y=.965, ha="left", weight="bold")
    fig.text(.085,.923,"60 completed trials  ·  4 arms × 5 input conditions × 3 paired seeds  ·  166,700 neurons", fontsize=12)
    arm_handles = [Line2D([0],[0],color=colors[a],lw=2.5,label=a) for a in arms]
    seed_handles = [Line2D([0],[0],color="#555555",lw=1.4,ls=styles[i],marker=markers[i],markersize=5,label=f"seed {s}") for i,s in enumerate(seeds)]
    fig.legend(handles=arm_handles+seed_handles,ncol=7,loc="upper left",bbox_to_anchor=(.078,.898),frameon=False,columnspacing=1.8)
    for ax,cohort,title in zip(axs[0],["non_source","first_hop_non_source"],
                              ["A  Nonsource activity under constant input", "B  First-hop activity under constant input"]):
        for a in arms:
            for si,seed in enumerate(seeds):
                v=lookup[a,seed,"constant_baseline"]["cohorts"][cohort]["mean_rates_hz"]
                ax.stairs(v,np.array(data["window_edges_ticks"])*.0001,baseline=None,color=colors[a],ls=styles[si],lw=1.4,alpha=.9)
        ax.axvspan(1.5,3,color="#e7e8ec",alpha=.6,zorder=-2)
        ax.axvline(1.5,color="#888888",ls="--",lw=.9)
        ax.text(.75,1.02,"11 Hz imposed input",transform=ax.get_xaxis_transform(),ha="center",fontsize=10)
        ax.text(2.25,1.02,"external input off",transform=ax.get_xaxis_transform(),ha="center",fontsize=10)
        ax.set(xlabel="Simulated time (s)",ylabel="Window mean spikes/s/cell",xlim=(0,3))
        ax.set_title(title,pad=31,loc="left")
        ax.set_ylim(bottom=0);ax.grid(axis="y",alpha=.16)
    for ax,cohort,title in zip(axs[1],["first_hop_non_source","non_source"],
                              ["C  First-hop matched pulse contrasts", "D  Nonsource matched pulse contrasts"]):
        for ai,a in enumerate(arms):
            for ci,key in enumerate(["EA_minus_constant_hz","IA_minus_constant_hz"]):
                x=ai+(-.17 if ci==0 else .17)
                for si,seed in enumerate(seeds):
                    y=contrasts[a,seed,cohort][key][2]
                    ax.scatter(x+(si-1)*.055,y,s=45,marker=markers[si],edgecolors=colors[a],
                               facecolors=colors[a] if ci==0 else "white",linewidths=1.25,zorder=3)
        ax.axhline(0,color="#777777",lw=.8)
        ax.set_xticks(range(4),arms)
        ax.set(ylabel="Pulse minus matched constant (Hz/cell)",xlim=(-.5,3.5))
        ax.set_title(title,loc="left",pad=13)
        ax.grid(axis="y",alpha=.16)
    fig.text(.085,.108,"Filled markers: ethyl acetate     Open markers: isoamyl acetate     Pulse window: 0.5–1.0 s",fontsize=11)
    fig.text(.085,.025,"Top: seven fixed window means, not instantaneous traces. Bottom: every seed shown; no confidence intervals.\nNo-input and source-output-blocked controls have zero nonsource spikes in every arm and seed.\nPersistence is observed only through 3 s; numerical bounds and local contrast do not validate physiology or behavior.",fontsize=9.5,color="#444444",linespacing=1.65)
    fig.savefig(OUT,dpi=220)
    plt.close(fig)
    assert record(SRC) == before
    MANIFEST.write_text(json.dumps(dict(source=before,script=record(Path(__file__)),output=record(OUT),
        plot="All four arms and three individual paired RNG seeds. Constant-input window means and predefined matched pulse differences; no biological confidence intervals or newly fitted targets.",
        rendering_correction="Version 1 duplicated panel titles and overlapped footnotes. Version 2 fixed layout. Independent visual review caught default stairs closure to zero at 3 s; version 3 uses baseline=None to avoid implying unobserved cessation. Numerical input unchanged; prior scripts, PNGs and manifests retained."),indent=2)+"\n")
    print(json.dumps(record(OUT)))


if __name__ == "__main__":
    main()
