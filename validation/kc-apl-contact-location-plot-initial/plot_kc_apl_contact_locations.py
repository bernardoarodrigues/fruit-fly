#!/usr/bin/env python3
"""Plot completed anatomical partitions; no anatomical compartment inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'validation/kc-apl-contact-location'
GROUPS = ['<missing>', 'ALIN', 'ALPN', 'APL (type override)', 'CX', 'DAN',
          'Kenyon_Cell', 'MBON', 'known_graph_source_not_in_prior_input_inventory',
          'outside_modeled_graph']
LABELS = ['Missing source class', 'ALIN', 'ALPN', 'APL (type override)', 'CX', 'DAN',
          'Kenyon_Cell', 'MBON', 'Known-graph inventory anomaly', 'Outside modeled graph']
COLORS = ['#808A92', '#E58324', '#238645', '#9166AD', '#3D609B', '#C84544',
          '#239FB5', '#916945', '#171C21', '#C49815']
SAMPLE_SIZE = 5000
MAX_DISPLAY_ROIS = 12
UM_PER_VOXEL = .008


def path(suffix):
    return BASE.with_name(BASE.name + suffix)


def record(p):
    p = Path(p)
    h = hashlib.sha256()
    with p.open('rb') as f:
        while block := f.read(8 * 1024 ** 2):
            h.update(block)
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=h.hexdigest())


def label(value):
    if value is None:
        return '[null]'
    if value == '':
        return '[empty string]'
    return value


def rank_hash(ordinals):
    """SplitMix64 permutation of absolute source-row ordinals; no RNG state."""
    x = np.asarray(ordinals, dtype=np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def samples(selected_path, target_codes, apl_code, expected_counts):
    reservoirs = [None, None]
    seen = np.zeros_like(expected_counts)
    finite_counts = [0, 0]
    columns = ['source_row_ordinal', 'source_group_code', 'target_column', 'x_post', 'y_post']
    for batch in pq.ParquetFile(selected_path).iter_batches(batch_size=131072, columns=columns):
        d = {key: batch.column(batch.schema.get_field_index(key)).to_numpy() for key in columns}
        ordinal, source, target = d['source_row_ordinal'], d['source_group_code'], d['target_column']
        assert np.all((target >= 0) & (target < len(target_codes)))
        assert np.all((source >= 0) & (source < len(GROUPS)))
        target_set = (target_codes[target] == apl_code).astype(np.int8)
        np.add.at(seen, (target_set, source), 1)
        finite = np.isfinite(d['x_post']) & np.isfinite(d['y_post'])
        for which in [0, 1]:
            use = (target_set == which) & finite
            finite_counts[which] += int(use.sum())
            if not use.any():
                continue
            take = dict(ordinal=ordinal[use].astype('<i8'), source=source[use].astype('<i2'),
                        x=d['x_post'][use].astype(np.float64), y=d['y_post'][use].astype(np.float64),
                        rank=rank_hash(ordinal[use]))
            previous = reservoirs[which]
            if previous is not None:
                take = {key: np.concatenate([previous[key], values]) for key, values in take.items()}
            if len(take['ordinal']) > SAMPLE_SIZE:
                keep = np.argpartition(take['rank'], SAMPLE_SIZE - 1)[:SAMPLE_SIZE]
                take = {key: values[keep] for key, values in take.items()}
            reservoirs[which] = take
    assert np.array_equal(seen, expected_counts), 'Parquet group/target counts differ from displayed denominators'
    for which in [0, 1]:
        item = reservoirs[which]
        assert item is not None and len(item['ordinal']) == min(SAMPLE_SIZE, finite_counts[which])
        order = np.argsort(item['rank'], kind='stable')
        reservoirs[which] = {key: values[order] for key, values in item.items()}
    return reservoirs, finite_counts


def main(expected_results_sha):
    output, receipt = path('-figure.png'), path('-plot-receipt.json')
    if output.exists() or receipt.exists():
        raise FileExistsError('Preserve existing figure/receipt')
    rp, pp = path('-results.json'), path('-plan.json')
    assert record(rp)['sha256'] == expected_results_sha
    r, plan = json.loads(rp.read_text()), json.loads(pp.read_text())
    assert r['passed'] and not r['errors'] and all(r['checks'].values())
    assert not any(r[k] for k in ['compartment_assignment', 'claw_assignment', 'model_changes', 'physiological_validation'])
    assert record(pp)['sha256'] == r['plan_sha256']
    summary = r['summary']
    assert summary['source_groups'] == plan['source_groups'] == GROUPS
    assert summary['target_types'] == plan['target_types']
    roi_labels = summary['roi_labels']
    apl_code = summary['target_types'].index('APL')
    selected = ROOT / summary['selected_artifact']['path']
    arrays = ROOT / r['arrays']['path']
    assert record(selected) == summary['selected_artifact']
    assert record(arrays) == r['arrays']
    pins = [record(Path(__file__)), record(rp), record(pp), record(arrays), record(selected)]
    with np.load(arrays, allow_pickle=False) as z:
        codes = z['target_type_codes'].copy()
        by_type = z['type_group_roi_contacts'].copy()
        dense = z['target_group_roi_contacts']
        assert by_type.shape == (len(plan['target_types']), len(GROUPS), len(roi_labels))
        assert by_type.dtype == np.int64 and by_type.min() >= 0
        kc, apl = codes != apl_code, codes == apl_code
        assert kc.sum() == 4064 and apl.sum() == 2
        counts = np.stack([by_type[np.arange(len(by_type)) != apl_code].sum(axis=0), by_type[apl_code]])
        assert np.array_equal(counts[0], dense[kc].sum(axis=0))
        assert np.array_equal(counts[1], dense[apl].sum(axis=0))
        assert np.array_equal(counts.sum(axis=0), np.asarray(summary['group_roi_contacts']))
        assert counts.sum() == summary['selected_rows']
    denominators = counts.sum(axis=2)
    assert int(denominators[:, -1].sum()) == summary['outside_graph_rows']
    assert summary['known_source_missing_pair_rows'] == 0
    pooled_roi = counts.sum(axis=(0, 1))
    order = np.lexsort((np.arange(len(roi_labels)), -pooled_roi))
    keep = order[:MAX_DISPLAY_ROIS]
    omitted = order[MAX_DISPLAY_ROIS:]
    bins = [[int(x)] for x in keep] + ([list(map(int, omitted))] if len(omitted) else [])
    bin_labels = [label(roi_labels[x]) for x in keep]
    if len(omitted):
        bin_labels.append(f'Other {len(omitted)} raw ROIs')
    display = np.stack([counts[:, :, indices].sum(axis=2) for indices in bins], axis=2)
    assert np.array_equal(display.sum(axis=2), denominators)
    percentages = np.divide(100. * display, denominators[:, :, None],
                            out=np.full(display.shape, np.nan), where=denominators[:, :, None] != 0)
    sample, finite_counts = samples(selected, codes, apl_code, denominators)

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
        'axes.spines.top': False, 'axes.spines.right': False,
        'figure.facecolor': 'white', 'savefig.facecolor': 'white'})
    fig = plt.figure(figsize=(16, 12))
    fig.text(.04, .97, 'Where retained contacts reach KC and APL targets', fontsize=18, weight='bold', va='top')
    fig.text(.04, .934,
        f'MaleCNS raw partner rows: {summary["selected_rows"]:,} total • {summary["modeled_rows"]:,} from modeled sources • '
        f'{summary["outside_graph_rows"]:,} from outside the modeled graph', fontsize=11, color='#414C57', va='top')
    fig.text(.04, .906,
        'Heatmaps: percent of each source-group row total, restricted to the indicated target population. n counts contacts, not source cells.',
        fontsize=10, color='#414C57', va='top')
    cmap = plt.colormaps['Blues'].copy()
    cmap.set_bad('#E8E8E8')
    for which, left, title in [(0, .205, 'A  KC targets: 4,064 cells'), (1, .64, 'B  APL targets: 2 cells')]:
        ax = fig.add_axes([left, .53, .33, .325])
        im = ax.imshow(percentages[which], cmap=cmap, vmin=0, vmax=100, aspect='auto', interpolation='none')
        total = int(denominators[which].sum())
        ax.set_title(f'{title} | {total:,} contacts', loc='left', fontsize=11, weight='bold', pad=10)
        ax.set_xticks(np.arange(len(bin_labels)))
        labels = [x.replace('CentralBrain-unspecified', 'CentralBrain-\nunspecified') for x in bin_labels]
        ax.set_xticklabels(labels, rotation=65, ha='right', fontsize=8.3)
        ax.set_yticks(range(len(GROUPS)))
        yl = [f'{LABELS[i]}   n={int(n):,}' if which == 0 else f'n={int(n):,}'
              for i, n in enumerate(denominators[which])]
        ax.set_yticklabels(yl, fontsize=8.6)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-.5, len(bin_labels), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(GROUPS), 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=.75)
        ax.tick_params(which='minor', length=0)
        for row in range(len(GROUPS)):
            for col in range(len(bin_labels)):
                v = percentages[which, row, col]
                if np.isfinite(v) and v >= 1:
                    ax.text(col, row, f'{v:.0f}' if v >= 10 else f'{v:.1f}', ha='center', va='center',
                            fontsize=7.6, color='white' if v >= 55 else '#25303B')
            if denominators[which, row] == 0:
                ax.text((len(bin_labels)-1)/2, row, 'No contacts: percentage undefined',
                        fontsize=8, color='#616A73', ha='center', va='center')
    cax = fig.add_axes([.978, .53, .009, .325])
    cb = fig.colorbar(im, cax=cax, ticks=[0, 25, 50, 75, 100])
    cb.ax.tick_params(labelsize=8, length=2)
    cb.ax.set_title('%', fontsize=9, pad=6)
    other_total = int(counts[:, :, omitted].sum()) if len(omitted) else 0
    fig.text(.04, .427,
        f'Raw ROI names are retained. Display groups {len(omitted)} lower-count ROIs ({other_total:,} contacts) into Other; '
        f'all {len(roi_labels)} ROI totals remain in data and receipt. Gray rows have n=0.', fontsize=9.6, color='#414C57')

    all_x = np.concatenate([a['x'] * UM_PER_VOXEL for a in sample])
    all_y = np.concatenate([a['y'] * UM_PER_VOXEL for a in sample])
    xpad = max(1., float(np.ptp(all_x)) * .025)
    ypad = max(1., float(np.ptp(all_y)) * .025)
    limits = (float(all_x.min() - xpad), float(all_x.max() + xpad),
              float(all_y.min() - ypad), float(all_y.max() + ypad))
    for which, left, title in [(0, .075, 'C  Postsynaptic coordinates: KC sample'),
                                (1, .56, 'D  Postsynaptic coordinates: APL sample')]:
        ax = fig.add_axes([left, .165, .39, .205])
        a = sample[which]
        for group, color in enumerate(COLORS):
            take = a['source'] == group
            ax.scatter(a['x'][take] * UM_PER_VOXEL, a['y'][take] * UM_PER_VOXEL,
                       s=3 if group < 8 else 8, alpha=.44 if group < 8 else .8,
                       c=color, marker='o' if group < 8 else 'x', edgecolors='none' if group < 8 else None)
        ax.set(xlim=limits[:2], ylim=limits[2:], xlabel='Raw x_post × 0.008 (µm)', ylabel='Raw y_post × 0.008 (µm)')
        ax.set_aspect('equal', adjustable='box')
        ax.set_title(title + f' | {len(a["ordinal"]):,} rows', loc='left', fontsize=11, weight='bold', pad=9)
        ax.grid(alpha=.13)
    handles = [Line2D([], [], color=COLORS[i], marker='o' if i < 8 else 'x', linestyle='none',
                      markersize=5, label=LABELS[i]) for i in range(len(GROUPS))]
    fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.04, .085), ncol=5,
               frameon=False, fontsize=9, columnspacing=2.)
    fig.text(.04, .025,
        'Scatter is a deterministic subset of contact rows with finite x/y, colored by source group; native axes are unreoriented and z is omitted.\n'
        f'Repeated raw identities remain counted. Known-source missing-edge rows: {summary["known_source_missing_pair_rows"]:,}. '
        'Outside-graph sources are included in raw anatomy, not supplied to the neural model.\n'
        'ROI labels and 2D positions do not assign claws, axons, dendrites, electrical compartments or physiological efficacy.',
        fontsize=9.5, color='#414C57', linespacing=1.45, va='bottom')
    fig.savefig(output, dpi=180, metadata={'ResultsSHA256': expected_results_sha,
        'Scope': 'Raw anatomical contacts, source-group row denominators, deterministic coordinate subsample; no compartment inference'})
    plt.close(fig)
    assert all(record(ROOT / q['path']) == q for q in pins), 'Plot inputs changed; retain figure for investigation'
    sample_records = []
    for which, a in enumerate(sample):
        sample_records.append(dict(target='KC' if which == 0 else 'APL', retained_sample_size=len(a['ordinal']),
            finite_coordinate_rows=finite_counts[which], excluded_nonfinite_rows=int(denominators[which].sum()) - finite_counts[which],
            ordered_source_row_ordinal_sha256=hashlib.sha256(a['ordinal'].astype('<i8').tobytes()).hexdigest(),
            source_group_counts=np.bincount(a['source'], minlength=len(GROUPS)).tolist()))
    report = dict(schema='kc-apl-contact-location-plot/v1', created_utc=datetime.now(timezone.utc).isoformat(), passed=True,
        inputs=pins, output=record(output), plot_only=True, model_execution=False,
        target_order=['KC', 'APL'], source_groups=GROUPS, raw_roi_labels=roi_labels,
        all_target_group_roi_contacts=counts.tolist(), source_group_denominators=denominators.tolist(),
        percent_definition='100 * contacts(source_group, target_population, displayed_ROI) / contacts(source_group, target_population, all_ROIs)',
        zero_denominator='undefined/NaN, gray; never converted to zero percent',
        display_roi_index_bins=bins, display_roi_labels=bin_labels, display_counts=display.tolist(),
        display_percentages=[[[None if not np.isfinite(x) else float(x) for x in row] for row in target] for target in percentages],
        deterministic_sample=dict(method='Smallest5000 SplitMix64-permuted original absolute source-row ordinals separately for KC/APL; no RNG. Sort selected ranks before hashing/plotting.',
            sample_size_per_target_limit=SAMPLE_SIZE, coordinate_scale_um_per_voxel=UM_PER_VOXEL,
            source='x_post/y_post from selected raw partner rows, no anatomical axis assignment', samples=sample_records),
        selected_partition=dict(total=summary['selected_rows'], modeled=summary['modeled_rows'], outside_graph=summary['outside_graph_rows'],
                                known_source_missing_pair=summary['known_source_missing_pair_rows']),
        limits=['Percentages describe spatial distribution within source group, not postsynaptic input share, efficacy or source-cell prevalence.',
                'All raw rows retained, including repeated identities and outside-graph sources; no model gain/current or compartment inference.',
                'Source-class missingness and known-graph inventory anomalies remain different groups.',
                'Raw primary feather was not rehashed by this plot; completed source audit is pinned by result/plan. Selected parquet and plotting inputs were rehashed.'])
    with receipt.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(output=record(output), receipt=record(receipt)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-results-sha', required=True)
    args = parser.parse_args()
    main(args.expected_results_sha)
