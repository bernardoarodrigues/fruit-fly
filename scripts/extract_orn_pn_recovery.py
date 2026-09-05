#!/usr/bin/env python3
"""Extract Fig S8B/D vector geometry under a frozen plan; no biological fitting.

Use bundled Python with pdfplumber for --prepare/--extract, project Python with
matplotlib for --plot. Plotting reads extracted files only. No neural imports.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / 'validation/orn-pn-recovery'
SUPPLEMENT = 'data/raw/orn-pn-physiology/kazama-wilson-2008-supplement.pdf'
PAPER = 'data/raw/orn-pn-physiology/kazama-wilson-2008.pdf'
SOURCE_HASHES = {
    SUPPLEMENT: 'b2903a4914cff0f556fa643e7aed111d74722ba840093b3a0ac6d81ccd07132a',
    PAPER: 'fb1d77bef1a95ca5274e57eeb7aae3be45f4d80dc972b40718fc62d4da2ddbe6',
}
PANELS = {
    'S8B': dict(x_ticks=[[117, 0.], [116, 1.], [114, 2.]], y_ticks=[[113, 0.], [112, 1.], [111, 2.], [109, 3.]],
                markers=list(range(133, 162, 2)), error_bars=list(range(132, 117, -1)), fit_curve=1,
                baseline=115, ordinate_axis=110, y_unit='pA', x_label='time after train (s)',
                y_label='uEPSC amplitude (pA)', protocol='Recovery following 50-200 Hz antennal-nerve trains; repeated post-train probes are visible in S8A.',
                normalization='Absolute plotted uEPSC amplitude in pA; no normalization applied here.',
                printed_time_constant_s=None),
    'S8D': dict(x_ticks=[[86, 0.], [85, 10.], [84, 20.], [82, 30.]], y_ticks=[[81, 0.], [80, .5], [78, 1.]],
                markers=list(range(93, 104, 2)), error_bars=list(range(92, 86, -1)), fit_curve=0,
                baseline=83, ordinate_axis=79, y_unit='recovery_ratio', x_label='pause duration (s)',
                y_label='recovery ratio', protocol='Pause between periods of 7 Hz antennal-nerve stimulation (S8C/D).',
                normalization='Recovery-ratio denominator is not explicitly defined in S8 caption or inspected methods; do not infer from terminal point.',
                printed_time_constant_s=7.5),
}


def out(suffix):
    return Path(str(PREFIX) + suffix)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_csv(path, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def read_json(path):
    return json.loads(Path(path).read_text())


def ensure_new(paths):
    for path in paths:
        if Path(path).exists():
            raise FileExistsError(f'Preserve existing artifact: {path}')


def load_geometry():
    import pdfplumber
    import pdfminer
    with pdfplumber.open(ROOT / SUPPLEMENT) as pdf:
        page = pdf.pages[13]
        assert len(pdf.pages) == 15 and (page.width, page.height) == (612, 792)
        assert len(page.curves) == 163 and len(page.chars) == 1325
        indices = set()
        for panel in PANELS.values():
            indices.update(i for i, value in panel['x_ticks'] + panel['y_ticks'])
            indices.update(panel['markers']); indices.update(i + 1 for i in panel['markers'])
            indices.update(panel['error_bars']); indices.update([panel['fit_curve'], panel['baseline'], panel['ordinate_axis']])
        curves = {str(i): page.curves[i] for i in sorted(indices)}
        # Normalize tuples exactly as JSON will store them for subsequent checks.
        curves = json.loads(canonical(curves))
        return dict(source_path=SUPPLEMENT, source_sha256=sha(ROOT / SUPPLEMENT), page_index=13,
                    page_number=14, page_size_points=[page.width, page.height], coordinate_convention='pdfplumber x from left; top from top; one PDF point = 1/72 inch',
                    object_counts={key: len(value) for key, value in page.objects.items()},
                    parser=dict(pdfplumber=pdfplumber.__version__, pdfminer=pdfminer.__version__), curves=curves)


def prepare():
    ensure_new([out('-plan.json'), out('-results.json')])
    for name, expected in SOURCE_HASHES.items():
        assert sha(ROOT / name) == expected
    geometry = load_geometry()
    assert geometry['parser'] == dict(pdfplumber='0.11.9', pdfminer='20251230')
    plan = dict(schema=1, prepared_utc=now(), git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        script_path=str(Path(__file__).relative_to(ROOT)), script_sha256=sha(__file__),
        source_inputs={name: dict(sha256=value, bytes=(ROOT / name).stat().st_size) for name, value in SOURCE_HASHES.items()},
        source_page_index=13, source_page_size_points=[612, 792], parser=geometry['parser'],
        selected_raw_geometry_sha256=hashlib.sha256(canonical(geometry)).hexdigest(), panels=PANELS,
        frozen_before_numerical_extraction=True,
        calibration='Affine coordinate conversion anchored only to first/last labeled ticks on each axis. Retain all intermediate tick residuals. Use actual D y=0 tick, not the lower horizontal baseline. No least-squares or biological curve fitting.',
        marker_rule='One observation per filled circular path. Require next stroke path identical. Center is midpoint of x0/x1 and top/bottom bounds; preserve full paths, bounds, center, line widths and source indices. Do not round to nominal stimulus times.',
        error_bar_rule='Use the assigned vertical vector centerline endpoints, including zero-height D terminal path. Require unique nearest-x matching to marker within0.2PDFpt; retain x offset, y midpoint offset, lower/upper endpoints and signed deviations from marker. Do not recenter, symmetrize, clip or label zero extent as zero sampling uncertainty.',
        fit_rule='Export every path endpoint in original order. Require cubic segments have first control=previous endpoint and second control=final endpoint: their loci are straight segments. Preserve all original cubic paths. These are the source printed fits; estimate no new parameters, no extrapolation.',
        uncertainty='Retain affine calibration residuals and per-marker/error-stroke halfwidth converted to axis units as graphical sensitivity quantities only. These are not statistical confidence intervals or a validated extraction error bound; do not add them to SEM.',
        data_status='Digitized figure-level plotted summaries and printed fit geometry, not original per-cell or trial measurements.',
        error_bar_status=dict(convention='mean +/- SEM across experiments in general paper methods',
            evidence='Main paper page index10, Data Analysis: All mean values are reported as mean ± SEM, averaged across experiments.',
            panel_caption_explicit=False, panel_specific_sample_size=None, observations_are_independent_experiments=False),
        biological_context=dict(species='Drosophila melanogaster', sex='female', age_days=[2, 7], glomerulus='VM2',
            measurement='Somatic PN whole-cell voltage-clamp uEPSCs after minimal antennal-nerve stimulation',
            evidence_pages=dict(main_methods=10, supplemental_methods=[1, 2, 3, 4], figure_S8=13),
            unknowns=['S8B/D panel-specific n and per-point n', 'Cell/trial identities and covariance',
                'Exact pooling across S8B train frequencies', 'Exact S8B post-train probe frequency',
                'Whether S8A 500ms example train duration applies to every S8B input',
                'S8D recovery-ratio denominator and normalization operation', 'Exact duration of S8D pre-pause 7Hz conditioning']),
        output_names=['-geometry.json', '-calibration.csv', '-points.csv', '-printed-fit.csv', '-results.json', '-digitization.png', '-plot-receipt.json'],
        no_fitting=True, no_neural_model=True, no_protocol_pooling=True)
    write_json(out('-plan.json'), plan)
    print(json.dumps(dict(frozen_plan=str(out('-plan.json').relative_to(ROOT)), sha256=sha(out('-plan.json'))), indent=2))


def extract():
    output_paths = [out(suffix) for suffix in ['-geometry.json', '-calibration.csv', '-points.csv', '-printed-fit.csv', '-results.json']]
    ensure_new(output_paths)
    plan = read_json(out('-plan.json'))
    assert sha(__file__) == plan['script_sha256'] and json.loads(canonical(PANELS)) == plan['panels']
    for name, record in plan['source_inputs'].items():
        assert sha(ROOT / name) == record['sha256'] and (ROOT / name).stat().st_size == record['bytes']
    geometry = load_geometry()
    assert hashlib.sha256(canonical(geometry)).hexdigest() == plan['selected_raw_geometry_sha256']
    assert geometry['parser'] == plan['parser']
    curves = geometry['curves']
    checks = []
    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
        assert passed, name
    calibrations, points, fit, summaries = [], [], [], []
    for name, config in plan['panels'].items():
        axis = {}
        for key in ['x', 'y']:
            ticks = config[key + '_ticks']
            coords = []
            for index, value in ticks:
                c = curves[str(index)]
                check(f'{name}:{key}-tick-{index}-centerline', len(c['pts']) == 2 and c['stroke'] and not c['fill']
                      and (c['width'] == 0. if key == 'x' else c['height'] == 0.))
                coords.append((c['x0'] + c['x1']) / 2. if key == 'x' else (c['top'] + c['bottom']) / 2.)
            scale = (ticks[-1][1] - ticks[0][1]) / (coords[-1] - coords[0])
            offset = ticks[0][1] - scale * coords[0]
            axis[key] = dict(scale=scale, offset=offset, anchor_coordinate=coords[0], anchor_value=ticks[0][1])
            residual = []
            for (index, value), coordinate in zip(ticks, coords):
                derived = (coordinate - coords[0]) * scale + ticks[0][1]
                expected_coord = (value - ticks[0][1]) / scale + coords[0]
                residual.append(coordinate - expected_coord)
                calibrations.append(dict(panel=name, axis=key, curve_index=index, tick_label_value=value,
                    pdf_coordinate_pt=coordinate, endpoint_anchored_value=derived,
                    residual_axis_units=derived - value, residual_pdf_points=coordinate - expected_coord,
                    scale_axis_units_per_pdf_point=scale, intercept_axis_units=offset,
                    anchor=(index in [ticks[0][0], ticks[-1][0]])))
            axis[key]['max_abs_tick_residual_points'] = max(abs(x) for x in residual)
            check(f'{name}:{key}-calibration-residual-below-0.1pt', max(abs(x) for x in residual) < .1)
        def convert(key, value):
            a = axis[key]
            return (value - a['anchor_coordinate']) * a['scale'] + a['anchor_value']
        panel_points = []
        for order, (mi, ei) in enumerate(zip(config['markers'], config['error_bars'], strict=True)):
            marker, stroke, error = curves[str(mi)], curves[str(mi + 1)], curves[str(ei)]
            check(f'{name}:marker-{mi}-single-fill-stroke-observation', marker['fill'] and not marker['stroke']
                  and stroke['stroke'] and not stroke['fill'] and marker['path'] == stroke['path'] and marker['pts'] == stroke['pts'])
            check(f'{name}:marker-{mi}-circular-bounds', len(marker['pts']) == 5 and
                  abs(marker['width'] - marker['height']) < .002 and 3.9 <= marker['width'] <= 4.5)
            check(f'{name}:error-{ei}-vertical-centerline', len(error['pts']) == 2 and error['width'] == 0
                  and error['stroke'] and not error['fill'])
            mx, my = (marker['x0'] + marker['x1']) / 2., (marker['top'] + marker['bottom']) / 2.
            ex, etop, ebottom = error['x0'], error['top'], error['bottom']
            ey = (etop + ebottom) / 2.
            nearest = min(config['error_bars'], key=lambda i: abs(curves[str(i)]['x0'] - mx))
            check(f'{name}:marker-{mi}-bar-pairing', nearest == ei and abs(mx - ex) < .2 and abs(my - ey) < .2,
                  marker_minus_bar_x_pt=mx - ex, marker_minus_bar_midpoint_top_pt=my - ey)
            x, y = convert('x', mx), convert('y', my)
            low, high = convert('y', ebottom), convert('y', etop)
            row = dict(panel=name, observation_index=order, source_page_index=13, marker_fill_curve_index=mi,
                marker_stroke_curve_index=mi + 1, error_curve_index=ei, marker_center_x_pt=mx, marker_center_top_pt=my,
                marker_x0_pt=marker['x0'], marker_x1_pt=marker['x1'], marker_top_pt=marker['top'], marker_bottom_pt=marker['bottom'],
                marker_stroke_width_pt=stroke['linewidth'], error_x_pt=ex, error_top_pt=etop, error_bottom_pt=ebottom,
                error_midpoint_top_pt=ey, error_stroke_width_pt=error['linewidth'],
                time_seconds=x, y_value=y, y_unit=config['y_unit'], error_time_seconds=convert('x', ex),
                error_y_low=low, error_y_high=high, error_midpoint_y=convert('y', ey),
                lower_extent_from_marker=y - low, upper_extent_from_marker=high - y,
                marker_minus_bar_x_pt=mx - ex, marker_minus_bar_midpoint_top_pt=my - ey,
                marker_minus_bar_time_seconds=x - convert('x', ex), marker_minus_bar_midpoint_y=y - convert('y', ey),
                drawn_error_bar_zero_height=error['height'] == 0.,
                marker_half_stroke_sensitivity_seconds=.5 * stroke['linewidth'] * abs(axis['x']['scale']),
                marker_half_stroke_sensitivity_y=.5 * stroke['linewidth'] * abs(axis['y']['scale']),
                error_half_stroke_sensitivity_y=.5 * error['linewidth'] * abs(axis['y']['scale']),
                error_statistic_basis='general_methods_mean_plus_minus_SEM_not_panel_specific', sample_size=None)
            check(f'{name}:marker-{mi}-reprojection', abs(x / axis['x']['scale'] + axis['x']['anchor_coordinate'] - mx) < 1e-10
                  and abs(y / axis['y']['scale'] + axis['y']['anchor_coordinate'] - my) < 1e-10)
            panel_points.append(row)
        points.extend(panel_points)
        c = curves[str(config['fit_curve'])]
        check(name + ':printed-fit-grey-stroke', c['stroke'] and not c['fill'] and c['stroking_color'] == [0., 0., 0., .60001])
        check(name + ':printed-fit-200-vertices', len(c['pts']) == len(c['path']) == 200 and c['path'][0][0] == 'm')
        previous = c['path'][0][1]
        for operation in c['path'][1:]:
            assert operation[0] == 'c' and operation[1] == previous and operation[2] == operation[3]
            previous = operation[-1]
        check(name + ':printed-fit-path-endpoints-complete', [op[-1] for op in c['path']] == c['pts'])
        for vertex, (xpt, ypt) in enumerate(c['pts']):
            fit.append(dict(panel=name, curve_index=config['fit_curve'], vertex_index=vertex,
                pdf_x_pt=xpt, pdf_top_pt=ypt, time_seconds=convert('x', xpt), y_value=convert('y', ypt),
                y_unit=config['y_unit'], value_status='digitized_printed_fit_not_new_fit'))
        check(name + ':marker-and-curve-time-order', all(panel_points[i]['time_seconds'] < panel_points[i + 1]['time_seconds'] for i in range(len(panel_points) - 1))
              and all(c['pts'][i][0] < c['pts'][i + 1][0] for i in range(len(c['pts']) - 1)))
        baseline = curves[str(config['baseline'])]
        summaries.append(dict(panel=name, point_count=len(panel_points), printed_curve_vertices=len(c['pts']),
            calibration=axis, horizontal_baseline_top_pt=baseline['top'], horizontal_baseline_y_value=convert('y', baseline['top']),
            marker_time_range_s=[panel_points[0]['time_seconds'], panel_points[-1]['time_seconds']],
            marker_y_range=[min(p['y_value'] for p in panel_points), max(p['y_value'] for p in panel_points)],
            max_abs_marker_error_x_offset_pt=max(abs(p['marker_minus_bar_x_pt']) for p in panel_points),
            max_abs_marker_error_y_midpoint_offset_pt=max(abs(p['marker_minus_bar_midpoint_top_pt']) for p in panel_points),
            zero_height_error_observations=[p['observation_index'] for p in panel_points if p['drawn_error_bar_zero_height']],
            point_outside_drawn_bar_observations=[p['observation_index'] for p in panel_points if not p['error_y_low'] <= p['y_value'] <= p['error_y_high']],
            printed_time_constant_s=config['printed_time_constant_s'], biological_sample_size=None))
    check('21-distinct-observations-not-42-drawing-objects', len(points) == 21)
    check('400-printed-curve-vertices-not-400-measurements', len(fit) == 400)
    write_json(out('-geometry.json'), geometry)
    write_csv(out('-calibration.csv'), calibrations)
    write_csv(out('-points.csv'), points)
    write_csv(out('-printed-fit.csv'), fit)
    # CSV must preserve every serialized scalar when read back with Python float.
    for suffix, rows in [('-points.csv', points), ('-printed-fit.csv', fit), ('-calibration.csv', calibrations)]:
        with out(suffix).open(newline='') as f:
            actual = list(csv.DictReader(f))
        assert len(actual) == len(rows)
        for a, expected in zip(actual, rows):
            for key, value in expected.items():
                assert (float(a[key]) == value if isinstance(value, float) else a[key] == ('' if value is None else str(value)))
        check('csv-roundtrip:' + suffix, True)
    check('all-source-and-script-hashes-still-match', sha(__file__) == plan['script_sha256'] and
          all(sha(ROOT / name) == record['sha256'] for name, record in plan['source_inputs'].items()))
    result = dict(schema=1, completed_utc=now(), plan_sha256=sha(out('-plan.json')), source_sha256=SOURCE_HASHES,
        passed=all(c['passed'] for c in checks), checks=checks, check_count=len(checks), panels=summaries,
        scope='Vector-derived figure observations, vertical bar extents and existing printed-fit paths only; no fitting, tau inference, normalization inference, pooling, model run, or original-trial claim.',
        error_bar_status=plan['error_bar_status'], biological_context=plan['biological_context'],
        artifacts={str(p.relative_to(ROOT)): dict(sha256=sha(p), bytes=p.stat().st_size) for p in output_paths[:-1]})
    write_json(out('-results.json'), result)
    print(json.dumps(dict(passed=result['passed'], checks=len(checks), points=len(points), printed_curve_vertices=len(fit), panels=summaries), indent=2))


def plot():
    ensure_new([out('-digitization.png'), out('-plot-receipt.json')])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plan, result = read_json(out('-plan.json')), read_json(out('-results.json'))
    assert result['passed'] and result['plan_sha256'] == sha(out('-plan.json')) and sha(__file__) == plan['script_sha256']
    for name, record in result['artifacts'].items():
        assert sha(ROOT / name) == record['sha256']
    with out('-points.csv').open(newline='') as f:
        points = list(csv.DictReader(f))
    with out('-printed-fit.csv').open(newline='') as f:
        fits = list(csv.DictReader(f))
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False,
                         'axes.spines.right': False, 'text.color': '#263346'})
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.5))
    for ax, name, color in zip(axes, ['S8B', 'S8D'], ['#137A88', '#79509A']):
        p = [r for r in points if r['panel'] == name]; f = [r for r in fits if r['panel'] == name]
        ax.plot([float(r['time_seconds']) for r in f], [float(r['y_value']) for r in f], color='#888888', lw=1.5, label='Printed fit path')
        ax.vlines([float(r['error_time_seconds']) for r in p], [float(r['error_y_low']) for r in p],
                  [float(r['error_y_high']) for r in p], color=color, lw=1.3, label='Drawn bar extents')
        ax.scatter([float(r['time_seconds']) for r in p], [float(r['y_value']) for r in p],
                   facecolors='white', edgecolors=color, s=38, zorder=3, label='Marker centers')
        ax.set_xlabel(plan['panels'][name]['x_label']); ax.set_ylabel(plan['panels'][name]['y_label'])
        ax.set_title('S8B | after high-frequency trains' if name == 'S8B' else 'S8D | pause in 7 Hz stimulation', loc='left')
        ax.set_ylim(0, 3.25 if name == 'S8B' else 1.12)
        ax.set_xlim(-.05 if name == 'S8B' else -.8, 2.1 if name == 'S8B' else 31.)
        ax.grid(axis='y', alpha=.15)
    fig.suptitle('VM2 synaptic recovery: digitized published geometry', x=.065, ha='left', y=.965, fontsize=16)
    fig.text(.065, .88, 'Kazama & Wilson (2008), Figure S8 | 21 plotted observations | two distinct protocols', fontsize=11)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.51, .075), ncol=3, frameon=False)
    fig.text(.065, .047, 'General methods: mean +/- SEM; S8 sample sizes and ratio denominator unspecified. No new fit or tau estimate.', fontsize=9)
    fig.text(.065, .015, 'Coordinates retain marker/bar offsets. Zero-height terminal bar is retained. These are figure-level values, not original trials.', fontsize=9)
    fig.subplots_adjust(left=.08, right=.98, top=.77, bottom=.25, wspace=.25)
    fig.savefig(out('-digitization.png'), dpi=170)
    plt.close(fig)
    inputs = [Path(__file__), out('-plan.json'), out('-results.json'), out('-points.csv'), out('-printed-fit.csv')]
    write_json(out('-plot-receipt.json'), dict(created_utc=now(), scope='Plot saved extraction tables only; no source PDF image embedded',
        matplotlib_version=matplotlib.__version__, inputs={str(p.relative_to(ROOT)): sha(p) for p in inputs},
        outputs={str(out('-digitization.png').relative_to(ROOT)): sha(out('-digitization.png'))}))
    print(str(out('-digitization.png')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true'); group.add_argument('--extract', action='store_true'); group.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.extract:
        extract()
    else:
        plot()
