#!/usr/bin/env python3
"""Static post-hoc plot of the frozen navigation readouts; no model/reducer calls."""
from pathlib import Path
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT/'validation/navigation-ladder-readouts.json'
EXPECTED = '0bd0f559b206d247cdaea268490cd21d7a4ff7a808c3437ae137f7b916886291'
OUTPUT = ROOT/'validation/navigation-ladder-readouts.png'
GROUPS = ['ORN_VM7d', 'VM7d_adPN', 'MBON12_14', 'FB5AB', 'hDeltaC', 'hDeltaK',
          'PFL3', 'DN_all', 'DNa02', 'DNg97', 'DNb05', 'DNg34']
LABELS = ['VM7d ORN', 'VM7d adPN', 'MBON12–14', 'FB5AB', 'hDeltaC', 'hDeltaK',
          'PFL3', 'All descending neurons', 'DNa02', 'DNg97 / oDN1', 'DNb05', 'DNg34']
ARMS = ['C0', 'C1', 'H0', 'H1']
COLORS = ['#2767A3', '#D58116', '#258D67', '#9B4CA6']
SEEDS = [11, 12, 13]
MARKERS = ['o', '^', 's']


def main():
    raw = INPUT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError('Frozen readout hash changed')
    data = json.loads(raw)
    assert data['passed'] and len(data['trials']) == 60
    assert data['window_edges_ticks'][2:4] == [5000, 10000]
    assert data['window_edges_ticks'][6:8] == [25000, 30000] and data['dt_s'] == .0001
    contrasts = {(x['arm'], x['seed'], x['cohort']): x for x in data['contrasts']}
    trials = {(x['spec']['arm'], x['spec']['seed'], x['spec']['condition']): x for x in data['trials']}
    values = np.empty((2, len(GROUPS), 4, 3))
    for gi, group in enumerate(GROUPS):
        assert data['group_definitions'][group]['count'] > 0
        for ai, arm in enumerate(ARMS):
            for si, seed in enumerate(SEEDS):
                row = contrasts[arm, seed, group]
                ea = trials[arm, seed, 'ethyl_acetate']['cohorts'][group]
                baseline = trials[arm, seed, 'constant_baseline']['cohorts'][group]
                assert row['available'] and ea['availability'] == baseline['availability'] == 'mapped'
                pulse = row['EA_minus_constant_hz'][2]
                assert pulse == ea['mean_rates_hz'][2] - baseline['mean_rates_hz'][2]
                values[0, gi, ai, si] = pulse
                values[1, gi, ai, si] = ea['mean_rates_hz'][6]
    assert np.isfinite(values).all() and (values[1] >= 0).all()

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.titlesize': 12, 'axes.labelsize': 10, 'axes.linewidth': .7,
                         'savefig.facecolor': 'white', 'figure.facecolor': 'white'})
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 8.5), sharey=True)
    fig.subplots_adjust(left=.225, right=.975, top=.785, bottom=.22, wspace=.13)
    fig.text(.025, .955, 'Navigation populations: pulse modulation and retained activity',
             fontsize=17, weight='bold', va='top')
    fig.text(.025, .915, 'Post hoc rescore of the same 60 neural trials • three paired simulation seeds • no wind or body assay',
             fontsize=10.5, color='#444444', va='top')
    arms_legend = [Line2D([], [], color=c, marker='o', linestyle='none', label=a, markersize=6)
                   for a, c in zip(ARMS, COLORS)]
    seeds_legend = [Line2D([], [], color='#555555', marker=m, linestyle='none', label=f'Seed {s}', markersize=5)
                    for s, m in zip(SEEDS, MARKERS)]
    fig.legend(handles=arms_legend, loc='upper left', bbox_to_anchor=(.218, .884), ncol=4,
               frameon=False, columnspacing=1.3, handletextpad=.35)
    fig.legend(handles=seeds_legend, loc='upper left', bbox_to_anchor=(.58, .884), ncol=3,
               frameon=False, columnspacing=1.1, handletextpad=.35)
    arm_offsets = [-.255, -.085, .085, .255]
    seed_offsets = [-.036, 0, .036]
    for panel, ax in enumerate(axes):
        for gi in range(len(GROUPS)):
            if gi % 2 == 0:ax.axhspan(gi-.5, gi+.5, color='#F1F4F7', zorder=0)
        ax.axvline(0, color='#6C747B', lw=.9, zorder=1)
        for ai, color in enumerate(COLORS):
            for si, marker in enumerate(MARKERS):
                y = np.arange(len(GROUPS)) + arm_offsets[ai] + seed_offsets[si]
                ax.scatter(values[panel, :, ai, si], y, color=color, marker=marker,
                           s=22, edgecolors='white', linewidths=.25, zorder=3)
        ax.set_ylim(len(GROUPS)-.5, -.5)
        ax.set_xscale('symlog', linthresh=1, linscale=1, base=10)
        ax.grid(axis='x', color='#CFD5DA', lw=.65, alpha=.75)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='y', length=0, pad=12)
        ax.tick_params(axis='x', labelsize=9)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
        ax.minorticks_off()
    axes[0].set_yticks(np.arange(len(GROUPS)), [f'{name}   (n={data["group_definitions"][group]["count"]:,})'
                                             for name, group in zip(LABELS, GROUPS)])
    axes[0].set_xlim(-15, 450)
    axes[0].xaxis.set_major_locator(FixedLocator([-10, -1, 0, 1, 10, 100, 400]))
    axes[1].set_xlim(-.10, 600)
    axes[1].xaxis.set_major_locator(FixedLocator([0, .5, 1, 10, 100, 500]))
    axes[0].set_title('A  Matched pulse contrast', loc='left', pad=11, weight='bold')
    axes[1].set_title('B  Late-OFF activity after EA', loc='left', pad=11, weight='bold')
    axes[0].set_xlabel('EA − constant baseline, 0.5–1.0 s\nΔ mean firing rate (Hz per cell)', labelpad=9)
    axes[1].set_xlabel('External inputs off, 2.5–3.0 s\nMean firing rate (Hz per cell)', labelpad=9)
    fig.text(.225, .035, 'Axes are linear within ±1 Hz and logarithmic outside; contrast and rate use different limits.\n'
             'Every marker is one simulation seed; vertical offsets only separate markers. No confidence intervals.\n'
             'Population means do not identify a localized activity bump or demonstrate navigation/body behavior.',
             fontsize=9.2, color='#4A4A4A', va='bottom', linespacing=1.5)
    fig.savefig(OUTPUT, dpi=200, metadata={'Software': 'Matplotlib', 'SourceSHA256': EXPECTED,
        'Scope': 'Posthoc same60 neural trials; no wind/body; individual technical seeds, no confidence intervals'})
    plt.close(fig)
    if hashlib.sha256(INPUT.read_bytes()).hexdigest() != EXPECTED:
        raise RuntimeError('Input changed during figure creation; preserve output as failed attempt')
    print(json.dumps({'output':str(OUTPUT), 'bytes':OUTPUT.stat().st_size,
        'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), 'input_sha256':EXPECTED,
        'plotted_values':int(values.size), 'cohorts':GROUPS, 'seeds':SEEDS, 'no_model_execution':True}))


if __name__ == '__main__':main()
