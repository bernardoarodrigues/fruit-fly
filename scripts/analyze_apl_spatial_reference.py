#!/usr/bin/env python3
"""Read-only reduction of published spatial profiles; no refitting or simulation.

Use bundled spreadsheet Python. Raw Fig 7 observation slots are not animal IDs.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import warnings
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'validation/apl-spatial-reference-plan.json'
OUT = ROOT / 'validation/apl-spatial-reference-results.json'
DATA = ROOT / 'validation/apl-spatial-reference-data.json'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def pin(p):
    return dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def open_source(path):
    # No source save/export occurs, so unsupported formatting remains untouched.
    with warnings.catch_warnings(record=True) as captured:
        wf = openpyxl.load_workbook(path, read_only=False, data_only=False)
        wc = openpyxl.load_workbook(path, read_only=False, data_only=True)
    xml_sheets = []
    with zipfile.ZipFile(path) as z:
        for i in range(len(wc.sheetnames)):
            r = ET.fromstring(z.read(f'xl/worksheets/sheet{i+1}.xml'))
            xml_sheets.append({c.attrib['r']: float(c.find('s:v', NS).text)
                               for c in r.findall('.//s:c', NS)
                               if c.attrib.get('t', 'n') == 'n'
                               and c.find('s:v', NS) is not None
                               and c.find('s:v', NS).text is not None})
    return wf, wc, xml_sheets, sorted(set(str(w.message) for w in captured))


def main():
    if OUT.exists() or DATA.exists():
        raise FileExistsError('Preserve the first completed reduction')
    plan = json.loads(PLAN.read_text())
    for p in plan['source_pins']:
        assert pin(ROOT / p['path'])['sha256'] == p['sha256']
    numeric_checks = 0
    formula_checks = 0
    messages = []
    extracted = dict(fig7_observations=[], fig8_profiles={})
    f7 = ROOT / plan['fig7']
    wf, wc, xmls, msgs = open_source(f7)
    messages.extend(msgs)
    for si, sheet in enumerate(wc):
        for row in sheet:
            for c in row:
                if isinstance(c.value, (int, float)):
                    assert wf[sheet.title][c.coordinate].data_type != 'f'
                    assert math.isfinite(c.value) and c.value == xmls[si][c.coordinate]
                    numeric_checks += 1
        rows = list(sheet.values)
        # Top panels: literal branch labels define contiguous observation slots.
        for i, row in enumerate(rows):
            if not (isinstance(row[1], str) and row[1].startswith('Top panel ')):
                continue
            panel = row[1].split()[-1]
            header = rows[i + 1]
            assert header[0] == 'Distance'
            starts = [(j, v) for j, v in enumerate(header)
                      if isinstance(v, str) and 'branch (' in v]
            assert len(starts) == 2
            k = i + 2
            while k < len(rows) and isinstance(rows[k][0], (int, float)):
                for bi, (start, branch) in enumerate(starts):
                    end = starts[bi+1][0] if bi == 0 else sheet.max_column
                    for col in range(start, end):
                        value = rows[k][col]
                        if value is None:
                            continue
                        assert isinstance(value, (int, float))
                        extracted['fig7_observations'].append(dict(
                            sheet=sheet.title, panel=panel, section='top', branch=branch,
                            distance_um=rows[k][0], observation_slot=col-start+1,
                            cell=sheet.cell(k+1, col+1).coordinate, value=value))
                k += 1
        # Bottom panels preserve literal C/H/V labels where present. In the
        # negative-control sheet labels are absent; retain ordinal only.
        for i, row in enumerate(rows):
            starts = [(j, v.split()[-1]) for j, v in enumerate(row)
                      if isinstance(v, str) and v.startswith('Bottom panel ')]
            if not starts:
                continue
            k = i + 1
            while k < len(rows) and not any(isinstance(v, str) and v.startswith('Bottom panel ') for v in rows[k]):
                for start, panel in starts:
                    for col in range(start, start+3):
                        value = rows[k][col]
                        if isinstance(value, (int, float)):
                            region = rows[i+1][col] if rows[i+1][col] in ('C', 'H', 'V') else None
                            extracted['fig7_observations'].append(dict(
                                sheet=sheet.title, panel=panel, section='bottom', region=region,
                                region_slot=col-start+1, source_row=k+1,
                                cell=sheet.cell(k+1, col+1).coordinate, value=value))
                k += 1
    wf.close(); wc.close()
    f8 = ROOT / plan['fig8']
    wf, wc, xmls, msgs = open_source(f8)
    messages.extend(msgs)
    scores = []
    for si, name in enumerate(plan['sites']):
        s = wc[name]
        sf = wf[name]
        for row in s:
            for c in row:
                if isinstance(c.value, (int, float)):
                    assert c.value == xmls[si][c.coordinate] and math.isfinite(c.value)
                    numeric_checks += 1
                if sf[c.coordinate].data_type == 'f':
                    formula = sf[c.coordinate].value
                    match = re.fullmatch(r'=AVERAGE\(([A-Z]+\d+):([A-Z]+\d+)\)', formula)
                    if match:
                        vals = [x.value for rr in s[match[1]+':'+match[2]] for x in rr if x.value is not None]
                        expected = math.fsum(vals) / len(vals)
                    else:
                        assert re.fullmatch(r'=[A-Z]+\d+', formula), formula
                        expected = s[formula[1:]].value
                    assert abs(c.value - expected) <= 1e-14
                    formula_checks += 1
        profile = []
        for row in range(5, 33):
            dist = s.cell(row, 1).value
            assert dist == (row - 5) * 10
            for bi, branch in enumerate(['CtoH', 'CtoV']):
                obs = s.cell(row, 2 + 2*bi).value
                dye = s.cell(row, 3 + 2*bi).value
                predictions = {}
                for model, starts in plan['columns'][name].items():
                    for length, col in zip(plan['length_um'], starts):
                        c = s.cell(row, col + bi)
                        assert sf[c.coordinate].data_type != 'f'
                        predictions[f'{model}_{length}'] = c.value
                assert all((v is None) == (obs is None) for v in predictions.values())
                if obs is None:
                    continue
                profile.append(dict(distance_um=dist, branch=branch, observed=obs, dye=dye,
                                    observed_cell=s.cell(row, 2+2*bi).coordinate,
                                    predictions=predictions))
        # The complete shared prefix is duplicated in the source export.
        shared = [p for p in profile if p['distance_um'] <= 180]
        for d in range(0, 181, 10):
            h, v = [p for p in shared if p['distance_um'] == d]
            assert h['observed'] == v['observed'] and h['dye'] == v['dye']
            assert h['predictions'] == v['predictions']
        unique = [p for p in profile if p['branch'] == 'CtoH' or p['distance_um'] > 180]
        assert len(profile) == 54 and len(unique) == 35
        for model in ('connectome', 'backbone'):
            for length in plan['length_um']:
                key = f'{model}_{length}'
                metrics = {}
                for label, pts in [('unique_segments', unique), ('both_paths', profile)]:
                    residual = np.array([p['predictions'][key] - p['observed'] for p in pts])
                    # Independent scalar reduction verifies every aggregate.
                    mse = math.fsum((p['predictions'][key]-p['observed'])**2 for p in pts)/len(pts)
                    assert abs(float(np.mean(residual**2))-mse) < 1e-15
                    metrics[label] = dict(n=len(pts), rmse=math.sqrt(mse),
                                         mae=float(np.mean(np.abs(residual))), bias=float(np.mean(residual)))
                scores.append(dict(site=name, model=model, length_um=length, **metrics))
        extracted['fig8_profiles'][name] = profile
    wf.close(); wc.close()
    # Refuse to infer animal identity from observation slot numbering.
    cells = [(p['sheet'], p['cell']) for p in extracted['fig7_observations']]
    assert len(cells) == len(set(cells))
    with DATA.open('x') as f:
        json.dump(extracted, f, indent=2)
        f.write('\n')
    for p in plan['source_pins']:
        assert pin(ROOT / p['path'])['sha256'] == p['sha256']
    result = dict(completed_utc=datetime.now(timezone.utc).isoformat(),
                  status='completed_published_profile_reduction', plan=pin(PLAN),
                  data=pin(DATA), source_pins=plan['source_pins'],
                  numeric_cells_checked=numeric_checks, formula_caches_checked=formula_checks,
                  fig7_extracted_observations=len(cells), comparisons=scores,
                  reader_warnings=sorted(set(messages)), source_workbooks_unmodified=True,
                  fitted=False, simulation_run=False, physiology_promoted=False,
                  scope='All three sites and six published model variants; descriptive normalized-profile error only.')
    with OUT.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_pins',)}, indent=2))


if __name__ == '__main__':
    main()
