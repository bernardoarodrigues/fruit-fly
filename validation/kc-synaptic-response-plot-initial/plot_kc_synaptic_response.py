#!/usr/bin/env python3
"""Plot retained KC waveform assay outputs only; no model/producer imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation/kc-synaptic-response'
ARMS = ['current_contact', 'current_amplitude_only', 'epsc_decay_anchored',
        'epsc_rise_anchored', 'intrinsic_boundary']
LABELS = ['Current contact', 'Current amplitude-only', 'EPSP decay anchored (EPSC fixed)',
          'EPSP rise anchored (EPSC fixed)', 'Intrinsic lower boundary']
COLORS = ['#88919B', '#24364A', '#087F8C', '#9451A6', '#C47720']
STYLES = ['-', ':', '-', '--', '-.']


def path(suffix):
    return BASE.with_name(BASE.name + suffix)


def record(p):
    p = Path(p)
    b = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(b),
                sha256=hashlib.sha256(b).hexdigest())


def main(expected_results_sha):
    output, receipt = path('-figure.png'), path('-plot-receipt.json')
    if output.exists() or receipt.exists():
        raise FileExistsError('Preserve the first figure and plot receipt')
    rp, pp, ap = path('-results.json'), path('-plan.json'), path('-arrays.npz')
    assert record(rp)['sha256'] == expected_results_sha
    r = json.loads(rp.read_text())
    plan = json.loads(pp.read_text())
    assert r['schema'] == plan['schema'] == 1
    assert r['passed'] and r['numerical_passed'] and r['complete_batch_analyzed']
    assert not r['errors'] and all(r['checks'].values())
    assert not r['biological_validation'] and not r['defaults_changed']
    assert record(pp)['sha256'] == r['plan_sha256']
    assert record(ap)['sha256'] == r['arrays_sha256']
    assert plan['arm_ids'] == [a['id'] for a in r['arms']] == ARMS
    pins = [record(Path(__file__)), record(rp), record(pp), record(ap)]
    for source, digest in plan['source_sha256'].items():
        pin = record(ROOT / source)
        assert pin['sha256'] == digest, 'Frozen source changed: ' + source
        pins.append(pin)
    # Printed Turner Fig. 3 summaries, not digitized data or fitted uncertainty.
    targets = [('epsc', 'rise_10_90_ms', 'EPSC 10–90% rise', .9, .4),
               ('epsc', 'asymptotic_decay_ms', 'EPSC late decay', 2.8, 1.2),
               ('epsp', 'rise_10_90_ms', 'EPSP 10–90% rise', 2.1, .5),
               ('epsp', 'asymptotic_decay_ms', 'EPSP late decay', 11.5, 5.3)]
    for field, mean in [('epsc_rise_ms', .9), ('epsc_decay_ms', 2.8),
                        ('epsp_rise_ms', 2.1), ('epsp_decay_ms', 11.5),
                        ('epsp_peak_mv', 1.4), ('intrinsic_tau_strict_lower_bound_ms', 200.)]:
        assert plan['targets'][field] == mean
    values, counts = {}, {}
    with np.load(ap, allow_pickle=False) as z:
        t = z['time_ms_0p1'].copy()
        assert t.ndim == 1 and t.size > 6000 and t[0] == 0
        assert np.isfinite(t).all() and np.all(np.diff(t) > 0)
        assert np.allclose(np.diff(t), .1, rtol=0, atol=1e-10)
        for name in ARMS:
            values[name] = {}
            for kind in ['epsp_mv', 'epsc_normalized', 'intrinsic_relaxation_mv']:
                y = z[f'{name}_0p1_{kind}'].copy()
                assert y.shape == t.shape and y.dtype == np.float64
                assert np.isfinite(y).all()
                values[name][kind] = y
        for kind, end in [('epsc_normalized', 15.), ('epsp_mv', 60.),
                          ('intrinsic_relaxation_mv', 600.)]:
            mask = (t >= 0) & (t <= end)
            counts[kind] = int(mask.sum())
    peaks = {a['id']: float(a['continuous']['epsp']['peak']) for a in r['arms']}
    assert all(v > 0 for v in peaks.values())
    assert all(abs(peaks[k] - 1.4) < 1e-10 for k in ARMS[1:])
    assert r['arms'][-1]['intrinsic']['tau_ms'] == 200.
    assert not r['arms'][-1]['intrinsic']['strict_gt200_satisfied']
    shared = {}
    for kind in ['epsc_normalized', 'epsp_mv', 'intrinsic_relaxation_mv']:
        a, b = (values[n][kind] for n in ARMS[:2])
        if kind == 'epsp_mv':
            a, b = a / peaks[ARMS[0]], b / peaks[ARMS[1]]
        shared[kind] = float(np.max(np.abs(a - b)))
        assert np.allclose(a, b, atol=1e-9, rtol=1e-9)
    candidate_epsc_shared = max(float(np.max(np.abs(
        values[n]['epsc_normalized'] - values[ARMS[2]]['epsc_normalized'])))
        for n in ARMS[3:])
    assert candidate_epsc_shared < 1e-9

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
        'axes.titlesize': 11, 'axes.labelsize': 9, 'axes.spines.top': False,
        'axes.spines.right': False, 'figure.facecolor': 'white', 'savefig.facecolor': 'white'})
    fig = plt.figure(figsize=(14, 9.5))
    grid = fig.add_gridspec(2, 1, left=.07, right=.98, bottom=.20, top=.80,
                          height_ratios=[1.15, 1], hspace=.66)
    trace_grid = grid[0].subgridspec(1, 3, wspace=.29)
    metric_grid = grid[1].subgridspec(1, 5, width_ratios=[1.1, 1, 1, 1, 1], wspace=.30)
    fig.text(.07, .97, 'Isolated KC synaptic-response compatibility',
             fontsize=18, weight='bold', va='top')
    fig.text(.07, .931, 'Model curves and reported summary means • Turner et al. (2008), female KC cohorts',
             fontsize=11, va='top', color='#48515B')
    fig.text(.07, .901, 'No source waveform recordings are plotted. Effective event at t=0; no PN/contact identity or APL model.',
             fontsize=10, va='top', color='#48515B')
    legend = [Line2D([], [], color=c, linestyle=s, lw=2, label=l)
              for c, s, l in zip(COLORS, STYLES, LABELS)]
    fig.legend(handles=legend, bbox_to_anchor=(.064, .88), loc='upper left',
               ncol=3, frameon=False, columnspacing=1.8, handlelength=3, fontsize=9)
    trace_specs = [('epsc_normalized', 15., 'A  Normalized EPSC proxy', 'Inward-current magnitude / peak'),
                   ('epsp_mv', 60., 'B  Amplitude-normalized EPSP', 'Depolarization / own continuous peak'),
                   ('intrinsic_relaxation_mv', 600., 'C  Separate intrinsic relaxation', 'Remaining displacement / initial magnitude')]
    for col, (kind, end, title, ylabel) in enumerate(trace_specs):
        ax = fig.add_subplot(trace_grid[0, col])
        mask = (t >= 0) & (t <= end)
        for i, name in enumerate(ARMS):
            y = values[name][kind]
            if kind == 'epsp_mv':
                y = y / peaks[name]
            elif kind == 'intrinsic_relaxation_mv':
                assert y[0] == -1.
                y = -y
            ax.plot(t[mask], y[mask], color=COLORS[i], linestyle=STYLES[i],
                    lw=2.7 if i == 0 else 1.65, alpha=.95)
        ax.set(xlim=(0, end), ylim=(-.025, 1.07), xlabel='Time from effective event (ms)', ylabel=ylabel)
        if col == 2:
            ax.set_xlabel('Time after releasing imposed displacement (ms)')
        ax.set_title(title, loc='left', weight='bold', pad=9)
        ax.grid(alpha=.17)
        if col == 0:
            ax.text(.98, .95, 'Three candidate EPSCs coincide.\nCurrent arms have instantaneous onset.',
                    ha='right', va='top', transform=ax.transAxes, fontsize=8.4,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.9))
        elif col == 1:
            ax.text(.98, .95, f'Unscaled contact peak: {peaks[ARMS[0]]:.4f} mV\nOther arms scaled to 1.4 mV.',
                    ha='right', va='top', transform=ax.transAxes, fontsize=8.4,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.9))
        else:
            ax.text(.98, .95, 'τm=200 ms: boundary only\nDoes not satisfy reported τm >200 ms.',
                    ha='right', va='top', transform=ax.transAxes, fontsize=8.4, color='#935617',
                    bbox=dict(facecolor='white', edgecolor='none', alpha=.9))

    metric_records = []
    row_labels = ['Reported mean ± dispersion', 'Current contact', 'Current amplitude-only',
                  'EPSP decay anchored\n(EPSC fixed)', 'EPSP rise anchored\n(EPSC fixed)', 'Intrinsic boundary']
    label_ax = fig.add_subplot(metric_grid[0, 0])
    label_ax.set(xlim=(0, 1), ylim=(5.7, -.7))
    label_ax.axis('off')
    for i, label in enumerate(row_labels):
        label_ax.text(0, i, label, fontsize=8.5, va='center', color='#222831')
    for j, (family, key, title, mean, dispersion) in enumerate(targets):
        ax = fig.add_subplot(metric_grid[0, j + 1])
        ax.axvline(mean, color='#BAC0C6', lw=.8, ls=':', zorder=0)
        ax.errorbar(mean, 0, xerr=dispersion, fmt='D', color='#222831',
                    ms=5, capsize=3, lw=1.2, zorder=4)
        predicted = []
        for i, arm in enumerate(r['arms']):
            v = float(arm['continuous'][family][key])
            assert np.isfinite(v) and v >= 0
            predicted.append(v)
            ax.scatter(v, i + 1, s=30, color=COLORS[i], zorder=4)
        ax.set_yticks(range(6))
        ax.set_yticklabels([''] * 6)
        ax.set_ylim(5.7, -.7)
        ax.tick_params(axis='y', length=0)
        ax.set_xlabel('Time (ms)' + ('; log scale' if j == 3 else ''))
        ax.set_title(title, loc='left', fontsize=10.2, weight='bold', pad=8)
        if j == 3:
            ax.set_xscale('log')
            ax.set_xlim(2., 280.)
            ax.set_xticks([3., 10., 30., 100., 200.], labels=['3', '10', '30', '100', '200'])
        else:
            ax.set_xlim(-.1, max(max(predicted), mean + dispersion) * 1.16)
        ax.grid(axis='x', alpha=.17)
        metric_records.append(dict(family=family, metric=key, reported_mean_ms=mean,
            reported_dispersion_ms=dispersion, model_predictions_ms=dict(zip(ARMS, predicted))))
    fig.text(.07, .461, 'D  Reported means versus model kinetics', fontsize=11, weight='bold', va='bottom')
    fig.text(.07, .436, 'Bars are reported dispersion of unspecified type, not confidence intervals or acceptance limits.',
             fontsize=9.2, color='#48515B', va='bottom')
    fig.text(.07, .09,
        'Current-contact and amplitude-only curves share normalized shape; overlapping lines are intentional.\n'
        'Model decay points are asymptotic poles; the experimental exponential-fit window is unavailable. EPSC and EPSP cohorts are not paired.\n'
        'Intrinsic panel shows normalized relaxation of an imposed −1 mV displacement, without pA, resistance or capacitance calibration.\n'
        'Deterministic local diagnostics; source means were already inspected. No biological validation, threshold fit or runtime parameter promotion.',
        fontsize=9.4, color='#48515B', linespacing=1.55, va='bottom')
    fig.savefig(output, dpi=180, metadata={'ResultsSHA256': expected_results_sha,
        'Scope': 'Retained deterministic local-model traces and printed summary means; no source recordings or biological validation'})
    plt.close(fig)
    assert all(record(ROOT / pin['path']) == pin for pin in pins), 'Input changed while plotting; preserve artifact'
    report = dict(schema='kc-synaptic-response-plot/v1', created_utc=datetime.now(timezone.utc).isoformat(),
        passed=True, inputs=pins, output=record(output), plot_only=True, model_execution=False,
        source_waveforms_plotted=False, source_summary_origin='Printed Turner 2008 Fig3/results; no new digitization',
        primary_dt_ms=.1, plotted_points_per_arm=counts, epsp_normalization='divide saved mV by continuous own-arm peak',
        unscaled_epsp_peaks_mv=peaks, current_normalized_curve_max_differences=shared,
        candidate_epsc_max_difference=candidate_epsc_shared, metrics=metric_records,
        intrinsic_lower_boundary_ms=200., intrinsic_strict_bound_satisfied=False,
        limitations=['Reported dispersion is not identified here as SD or SEM and is not a confidence interval.',
            'Late-decay comparison is conditional on an asymptotic interpretation; source fit windows are unspecified.',
            'EPSC is a normalized current proxy without pA amplitude; EPSP normalization hides absolute gain, separately disclosed.',
            'Intrinsic lower-bound case equals 200 ms and does not satisfy the strict greater-than measurement.',
            'No mapped PN spike/contact, APL, threshold fitting, network run or runtime promotion.'])
    with receipt.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(output=record(output), receipt=record(receipt)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-results-sha', required=True)
    args = parser.parse_args()
    main(args.expected_results_sha)
