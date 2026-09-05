#!/usr/bin/env python3
"""Run the explicitly assigned H1 saved-data readers once, then index their evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ORDINALS = [26,29,32,35,38,41,44,47,50,53,56,59]
BASE = ROOT/'validation/inhibitory-recurrent-panel-H1-batch-review'
READER = 'scripts/review_inhibitory_recurrent_panel_H.py'
PINS = {
    READER:'80a68d09ed3d028a7bc193ab5471c270bf6576018c7cd04dab6852a500d64237',
    'scripts/inhibitory_panel_reference_audit.py':'2a20ac9ed6b5dfd312b7f7aeb83028920c403f8972374213d731fcafddbea743',
    'validation/inhibitory-panel-reference-audit-results.json':'4985dac16fe3192c6e703cafa3aaf42ab4251c75a5952baef8b65aeb950abafd',
}

def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def record(path):
    path=Path(path)
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=sha(path))
def immutable(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')

def inspect(spec,path):
    data=json.loads(path.read_text())
    result=dict(ordinal=spec['ordinal'],name=spec['name'],receipt=record(path),passed=data['passed'],
        check_count=data['check_count'],statistics=data['statistics'],wall_seconds=data['wall_seconds'],
        failures=data['failures'],error=data['error'],reviewer_sources=data['source_sha256'])
    same=data['trial']==spec
    same=same and all(data['source_sha256'].get(k)==v for k,v in PINS.items())
    same=same and data['source_sha256']==data['final_source_sha256']
    reference=data['independent_references'];artifact=reference['artifact'];ref_path=ROOT/artifact['path']
    valid=record(ref_path)==artifact
    with np.load(ref_path,allow_pickle=False) as z:
        values=z['values'];columns=reference['columns']
        valid=valid and z.files==['values'] and values.dtype==np.float64 and values.shape==(reference['records'],len(columns))
    numeric_names=['production_quad_error_mv','production_64_error_mv','ode_quad_error_mv','independent_quad_error_mv']
    maxima={k:float(values[:,columns.index(k)].max()) if len(values) else None for k in numeric_names}
    unresolved=int(values[:,columns.index('timing_unresolved')].sum()) if len(values) else 0
    valid=valid and unresolved==data['statistics'].get('independent_threshold_unresolved',unresolved)
    result.update(reference_artifact=artifact,reference_artifact_valid=bool(valid),identity_and_sources_match=bool(same),
        numerical_maxima_mv=maxima,threshold_timing_unresolved=unresolved,
        minimum_sampled_threshold_margin_mv=float(values[:,columns.index('threshold_margin_mv')].min()) if len(values) else None)
    result['batch_entry_passed']=bool(data['passed'] and same and valid and not data['failures'] and data['error'] is None)
    return result

def main():
    output=BASE.with_suffix('.json');log_path=BASE.with_suffix('.log');plan_path=BASE.with_name(BASE.name+'-plan.json')
    if any(p.exists() for p in [output,log_path,plan_path]):raise FileExistsError('Preserve existing batch attempt')
    for path,digest in PINS.items():
        if sha(ROOT/path)!=digest:raise ValueError('Frozen reader/helper mismatch: '+path)
    panel_path=ROOT/'validation/inhibitory-recurrent-panel-plan.json'
    panel=json.loads(panel_path.read_text());specs=[panel['order'][i] for i in ORDINALS]
    if panel['run_dir']!='runs/20260905T060501089987Z-inhibitory-recurrent-panel':raise ValueError('Wrong run')
    existing=[]
    for spec in specs:
        if spec['arm']!='H1':raise ValueError('Wrong assigned arm')
        d=ROOT/panel['run_dir']/spec['name'];terminal=json.loads((d/'terminal.json').read_text())
        if terminal['status']!='complete' or not terminal['complete']:raise ValueError('Trial incomplete: '+spec['name'])
        path=ROOT/'validation'/('inhibitory-recurrent-panel-'+spec['name']+'-H-review.json')
        ref=path.with_name(path.stem+'-references.npz')
        if ref.exists() and not path.exists():raise FileExistsError('Preserve orphan reference artifact: '+str(ref))
        if path.exists():existing.append(inspect(spec,path))
    frozen={**PINS,str(Path(__file__).resolve().relative_to(ROOT)):sha(__file__),
        'scripts/review_inhibitory_recurrent_panel_trial.py':sha(ROOT/'scripts/review_inhibitory_recurrent_panel_trial.py'),
        'validation/inhibitory-recurrent-panel-plan.json':sha(panel_path)}
    immutable(plan_path,dict(frozen_utc=now(),run_dir=panel['run_dir'],ordinals=ORDINALS,source_sha256=frozen,
        existing_receipts=existing,scope='One sequential batch of frozen saved-data reader invocations only; no model execution.',
        failure_policy='Inspect and skip existing receipts. Preserve all first failures and orphan artifacts. Stop batch on a failed receipt/reader; never retry or alter reader/helper.'))
    rows=[];error=None;started=now();t0=time.perf_counter()
    with log_path.open('x',buffering=1) as log:
        log.write(json.dumps(dict(started_utc=started,plan=record(plan_path)))+'\n')
        try:
            for spec in specs:
                path=ROOT/'validation'/('inhibitory-recurrent-panel-'+spec['name']+'-H-review.json')
                for name,digest in frozen.items():
                    if sha(ROOT/name)!=digest:raise ValueError('Frozen input/source changed: '+name)
                before=now();code=None;skipped=path.exists()
                log.write(json.dumps(dict(started_utc=before,ordinal=spec['ordinal'],name=spec['name'],skipped_existing=skipped))+'\n')
                if not skipped:
                    completed=subprocess.run([sys.executable,str(ROOT/READER),'--ordinal',str(spec['ordinal'])],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    code=completed.returncode
                if not path.exists():raise RuntimeError('Reader produced no receipt, return code '+str(code))
                row=inspect(spec,path);row.update(skipped_existing=skipped,reader_returncode=code,started_utc=before,finished_utc=now())
                rows.append(row);log.write(json.dumps(dict(finished_utc=row['finished_utc'],ordinal=spec['ordinal'],passed=row['batch_entry_passed'],returncode=code))+'\n')
                if code not in [None,0] or not row['batch_entry_passed']:raise RuntimeError('First failed H1 audit preserved: '+spec['name'])
        except (Exception,KeyboardInterrupt) as exc:
            error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());log.write(json.dumps(dict(batch_error=error))+'\n')
        log.write(json.dumps(dict(finished_utc=now(),indexed_trials=len(rows),error=error))+'\n')
    final={name:sha(ROOT/name) for name in frozen}
    all_checks=sum(row['check_count'] for row in rows)
    maxima={key:max(row['numerical_maxima_mv'][key] for row in rows if row['numerical_maxima_mv'][key] is not None) for key in rows[0]['numerical_maxima_mv']} if rows else {}
    out=dict(started_utc=started,completed_utc=now(),wall_seconds=time.perf_counter()-t0,plan=record(plan_path),log=record(log_path),
        source_sha256=frozen,final_source_sha256=final,run_dir=panel['run_dir'],ordinals=ORDINALS,
        complete=len(rows)==len(specs),passed=len(rows)==len(specs) and error is None and frozen==final and all(row['batch_entry_passed'] for row in rows),
        trials=rows,error=error,summary=dict(indexed_trials=len(rows),check_count=all_checks,
            numerical_maxima_mv=maxima,threshold_timing_unresolved=sum(row['threshold_timing_unresolved'] for row in rows),
            reference_intervals=sum(row['statistics'].get('reference_intervals',0) for row in rows),
            spikes=sum(row['statistics']['spikes'] for row in rows),
            selected_event_rows=sum(row['statistics']['reconstructed_selected_edges'] for row in rows)),
        limits=['Batch executes the frozen independent reader, not a new independent implementation of its checks.',
            'This batch author authored the independent scalar reference helper; that role is disclosed rather than counted as a separate numerical reviewer.',
            'Selected 48 p/h states, source events, direct/reset algebra and saved reference intervals are checked; full global inter-checkpoint voltage is not reconstructed.',
            'Global winning-reference optimality over unselected cells is not independently established. Numeric agreement does not validate physiology or promote H1.',
            'Only these 12 assigned H1 trials are in this batch; earlier H1 no-input receipts and the H0 batch remain separate.'])
    immutable(output,out)
    print(json.dumps(dict(path=str(output),passed=out['passed'],summary=out['summary'],error=error),indent=2))
    return 0 if out['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
