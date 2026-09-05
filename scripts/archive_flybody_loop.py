"""Archive completed loop journals without rerunning or changing source evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'validation/flybody-loop'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    original_path = OUT/'results.json'
    report = json.loads(original_path.read_text())
    if 'archival' in report:
        raise FileExistsError('Completed archival must not be overwritten')
    assert report['complete']
    plan_hash = sha(OUT/'plan.json')
    assert plan_hash == report['plan_sha256']
    archive = ROOT/'runs'/('flybody-loop-'+plan_hash[:12])
    archive.mkdir(exist_ok=False)
    shutil.copy2(original_path, archive/'results-original.json')
    receipt = {'operation': 'Post-run relocation of intact raw directories and deterministic gzip copies; no simulation.',
               'archiver_sha256': sha(__file__), 'plan_sha256': plan_hash,
               'original_results': {'path': str((archive/'results-original.json').relative_to(ROOT)),
                                    'sha256': sha(original_path)},
               'path_mapping': {}, 'journals': []}
    frames = OUT/'frames'
    frames.mkdir(exist_ok=True)
    summaries = []
    for row in report['conditions']:
        name = row['condition']
        old, new = OUT/name, archive/name
        receipt['path_mapping'][str(old.relative_to(ROOT))] = str(new.relative_to(ROOT))
        old_hashes = {str(p.relative_to(old)): sha(p) for p in old.rglob('*') if p.is_file()}
        shutil.move(str(old), str(new))
        for rel, value in old_hashes.items():
            assert sha(new/rel) == value
        for image in new.glob('*.png'):
            shutil.copy2(image, frames/(name+'-'+image.name))
        raw = new/'events.jsonl'
        assert sha(raw) == row['journal']['sha256']
        compressed = raw.with_suffix('.jsonl.gz')
        with raw.open('rb') as src, compressed.open('xb') as dest:
            with gzip.GzipFile(filename='', mode='wb', fileobj=dest, compresslevel=6, mtime=0) as gz:
                shutil.copyfileobj(src, gz)
        verified = hashlib.sha256()
        with gzip.open(compressed, 'rb') as stream:
            while chunk := stream.read(1024*1024):
                verified.update(chunk)
        assert verified.hexdigest() == row['journal']['sha256']
        row['journal']['original_execution_path'] = row['journal']['path']
        row['journal']['path'] = str(raw.relative_to(ROOT))
        row['journal']['gzip_path'] = str(compressed.relative_to(ROOT))
        row['journal']['gzip_sha256'] = sha(compressed)
        row['raw_directory'] = str(new.relative_to(ROOT))
        row['archived_condition_sha256'] = sha(new/'condition.json')
        receipt['journals'].append(dict(row['journal'], raw_bytes=raw.stat().st_size,
                                        gzip_bytes=compressed.stat().st_size,
                                        all_original_file_hashes=old_hashes))
        physical, neural = row['physical_intervals'], row['neural_intervals']
        points = np.asarray([row['initial_diagnostics']['pose_cm_quat'][:3]] +
                            [(np.asarray(x['position_mm'])/10).tolist() for x in physical])*10
        speed = np.linalg.norm(np.diff(points[:, :2], axis=0), axis=1)/.002
        first_feed = next((x['tick']*.002 for x in physical if x['motor']['behavior'] == 'feed'), None)
        summaries.append({'condition': name, 'completed_ticks': row['completed_ticks'],
                          'all_condition_gates_pass': row['all_declared_condition_gates_pass'],
                          'path_length_mm_2ms_chords': float(speed.sum()*.002),
                          'net_planar_displacement_mm': float(np.linalg.norm(points[-1, :2]-points[0, :2])),
                          'muted_steady_speed_median_mm_s_0p85_to1p2': float(np.median(speed[425:600])) if len(speed) >= 600 else None,
                          'after_restore_speed_median_mm_s_1p5_to2': float(np.median(speed[750:1000])) if len(speed) >= 1000 else None,
                          'minimum_upright_z': min(x['up_z'] for x in physical),
                          'maximum_qacc_abs_native': max(x['qacc_abs_max_native'] for x in physical),
                          'maximum_clock_error_s': max(x['clock_max_error_s'] for x in physical),
                          'maximum_resource_residual': max(x['resource_residual_max'] for x in physical),
                          'minimum_neural_voltage_mv': min(x['voltage_mv']['min'] for x in neural),
                          'total_graph_spikes': sum(x['total_spikes'] for x in neural),
                          'first_feed_completed_interval_end_s': first_feed,
                          'muted_neural_spikes': row['muted_neural_spikes'],
                          **row['observed_endpoints']})
    receipt['original_files_preserved'] = True
    receipt['historical_path_note'] = 'Paths inside byte-preserved manifests/telemetry/condition files identify their original execution location; resolve through path_mapping.'
    (OUT/'archival.json').write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n')
    report['archival'] = {'receipt': 'validation/flybody-loop/archival.json',
                         'sha256': sha(OUT/'archival.json'),
                         'original_results_sha256': receipt['original_results']['sha256']}
    original_path.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    summary = {'scope': 'Post hoc descriptive summaries only; no new gates, fits or simulation.',
               'script_sha256': sha(__file__), 'plan_sha256': plan_hash,
               'results_sha256': sha(original_path), 'conditions': summaries,
               'paired_mechanisms': report['paired_mechanisms'],
               'sampling': '2ms displacement chords; steady mute slice uses intervals0.85–1.2s,post-restore1.5–2s; no smoothing.',
               'biological_behavior_validated': False}
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'archive': str(archive), 'conditions': summaries}, indent=2), flush=True)


if __name__ == '__main__':
    main()
