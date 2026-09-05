"""Inspect publication geometry only; never export neural-trace vertices/values.

Requires the frozen phase-1 plan. Curve points are accessed only for the three
illustrated light-command transitions, not for voltage/current/firing traces.
"""
from pathlib import Path
import hashlib
import json
import sys

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/ln-inhibitory-transfer/nagelwilson2016.pdf'
PLAN = ROOT / 'validation/ln-inhibitory-transfer-extraction-plan.json'
OUTPUT = ROOT / 'validation/ln-inhibitory-transfer-layout.json'


def receipt(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def bounds(obj):
    return {k: obj[k] for k in ['x0', 'top', 'x1', 'bottom']}


def main():
    assert not OUTPUT.exists(), 'Refusing to overwrite layout evidence'
    assert receipt(SOURCE)['sha256'] == '3991919a050c83687014e9204f76cc1f48e6dd91949204156a81ab16f294ecfe'
    assert receipt(PLAN)['sha256'] == '7ab0617c680e3d6949e167e8096d5301e997c7ce87d6c2d5fbefa63325da2f1d'
    with pdfplumber.open(SOURCE) as pdf:
        page = pdf.pages[8]
        object_inventory = []
        for kind in ['rect', 'curve', 'image']:
            for index, obj in enumerate(page.objects[kind]):
                if 220 < obj['top'] < 430 and obj['x0'] > 140:
                    item = {'kind': kind, 'index_within_kind_on_page': index,
                            'bounds_pt': bounds(obj)}
                    item.update({k: obj.get(k) for k in ['stroke', 'fill', 'linewidth',
                                 'stroking_color', 'non_stroking_color', 'srcsize']})
                    item['number_of_vertices'] = len(obj.get('pts', []))
                    object_inventory.append(item)
        # These paths are gray LIGHT COMMAND artwork, located above the traces.
        light_paths = [{'curve_index': i, 'bounds_pt': bounds(page.curves[i]),
                        'illustrated_command_polygon_vertices_pt': page.curves[i]['pts']}
                       for i in [126, 134, 152]]
        assert all(p['bounds_pt']['bottom'] < 234 for p in light_paths)
        bars = {str(i): bounds(page.rects[i]) for i in [135, 136, 140, 141]}
        scale_D = page.rects[136]['x1'] - page.rects[136]['x0']
        scale_F = (page.rects[140]['x1'] - page.rects[140]['x0']) / .2
        # Ink-width envelopes, selected from the transition paths above. They
        # bound artwork coordinates, not measured photon timing or biological noise.
        left_on = [183.431, 183.860]
        left_off = [240.924, 241.425]
        right_on = [390.498, 391.143]
        left_on_mid = sum(left_on) / 2
        right_on_mid = sum(right_on) / 2
        windows = {
            'C_D_light_duration_s_ink_bound': [(left_off[0] - left_on[1]) / scale_D,
                                             (left_off[1] - left_on[0]) / scale_D],
            'C_D_display_s_approx_relative_to_light': [(154.863 - left_on_mid) / scale_D,
                                                       (284.312 - left_on_mid) / scale_D],
            'E_F_display_s_approx_relative_to_light': [(346.661 - right_on_mid) / scale_F,
                                                       (478.448 - right_on_mid) / scale_F],
            'classification': 'Inferred from plotted command and scale artwork; not an acquisition-clock record',
        }
        artifact = {
            'source': receipt(SOURCE), 'frozen_plan': receipt(PLAN),
            'script': receipt(Path(__file__).resolve()),
            'runtime': {'python': sys.version, 'pdfplumber': pdfplumber.__version__},
            'pdf_page_1based': 9, 'printed_page': 4333,
            'page_size_pt': [page.width, page.height],
            'coordinates': 'PDF points; pdfplumber top-left origin, y increasing downward',
            'page_object_counts': {k: len(v) for k, v in page.objects.items()},
            'figure_C_to_F_object_inventory': object_inventory,
            'scale_bar_rectangles': bars, 'light_command_geometry': light_paths,
            'layout_time_scale_pt_per_s': {'C_D': scale_D, 'E_F': scale_F},
            'layout_current_scale_pt_per_pA': {
                'D': (page.rects[135]['bottom'] - page.rects[135]['top']) / 4,
                'F': (page.rects[141]['bottom'] - page.rects[141]['top']) / 4},
            'illustrated_light_transition_x_bounds_pt': {'C_D_on': left_on,
                                                        'C_D_off': left_off, 'E_F_on': right_on},
            'display_windows': windows,
            'future_declared_windows_fit_expanded_display': all(
                windows['E_F_display_s_approx_relative_to_light'][0] <= a < b <=
                windows['E_F_display_s_approx_relative_to_light'][1]
                for a, b in [(-.15, -.05), (.05, .15), (.25, .35)]),
            'recoverability': {
                'D_black_mean_curve_index': 234, 'D_gray_envelope_curve_index': 233,
                'D_cyan_curve_index': 232, 'E_green_curve_indices': list(range(143, 150)),
                'F_black_curve_index': 235, 'F_gray_envelope_curve_index': 231,
                'neural_vectors_are_filled_outlines_not_original_sample_centerlines': True,
                'E_separate_SEM_vector_identified': False,
                'D_raster_images_overlap_control_region': True,
                'phase2_needed_before_trace_recoverability_is_demonstrated': True},
            'neural_trace_vertices_exported': False, 'neural_trace_values_digitized': False,
            'fit_or_simulation': False,
        }
    with OUTPUT.open('x') as stream:
        stream.write(json.dumps(artifact, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': receipt(OUTPUT), 'windows': windows,
                      'future_windows_fit': artifact['future_declared_windows_fit_expanded_display']}, indent=2))


if __name__ == '__main__':
    main()
