#!/usr/bin/env python3
"""Read-only saved-file audit of the first actual panel worker, after exit."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import traceback

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/20260905T060501089987Z-inhibitory-recurrent-panel'
FIRST=RUN/'00-C0-seed11-no_input'
OUT=ROOT/'validation/inhibitory-recurrent-panel-first-worker-audit.json'
OBS=ROOT/'validation/inhibitory-recurrent-panel-first-worker-observations.json'
PLAN=ROOT/'validation/inhibitory-recurrent-panel-plan.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if OUT.exists():raise RuntimeError('Refusing to overwrite first-worker audit')
    checks=[];errors=[];details={};inputs={}
    def ck(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value:raise AssertionError(name)
    def pin(path):
        rec=dict(bytes=path.stat().st_size,sha256=sha(path));inputs[str(path.relative_to(ROOT))]=rec;return rec
    try:
        plan=json.loads(PLAN.read_text());pin(PLAN)
        ck('plan_identity',sha(PLAN)=='c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5')
        observations=json.loads(OBS.read_text());pin(OBS)
        report=json.loads((FIRST/'result.json').read_text());terminal=json.loads((FIRST/'terminal.json').read_text())
        started=json.loads((FIRST/'started.json').read_text());next_started=json.loads((RUN/'01-C0-seed11-constant_baseline/started.json').read_text())
        for path in [FIRST/'result.json',FIRST/'terminal.json',FIRST/'started.json',FIRST/'progress.json',FIRST/'worker.log',FIRST/'c0-prefix-gate.json',RUN/'manifest.json',RUN/'started.json',RUN/'01-C0-seed11-constant_baseline/started.json']:pin(path)
        ck('terminal_result_hash',terminal['result']['sha256']==sha(FIRST/'result.json') and terminal['result']['bytes']==(FIRST/'result.json').stat().st_size)
        ck('authoritative_complete',terminal['status']=='complete' and terminal['complete'] and not terminal['errors'] and not terminal['global_resource_stop'] and report['status']=='complete' and report['complete'] and not report['errors'])
        ck('complete_clocks',all(report[k]==30000 for k in ['completed_tick','last_durable_chunk_end_tick','last_complete_checkpoint_tick','confirmed_prefix_end_tick','counts_end_tick']))
        ck('first_identity',started['pid']==1747 and started['plan_sha256']==sha(PLAN) and report['ordinal']==0 and report['seed']==11 and report['arm']=='C0' and report['condition']=='no_input')
        ck('reported_no_input',report['spike_count']==report['candidate_count']==report['applied_count']==0 and report['c0_prefix_passed'])
        rows=observations['observations'];dead=next(r for r in rows if not r['first_pid_exists']);new=next(r for r in rows if r['active_worker']['pid']!=1747)
        ck('observed_exit_then_next_record',rows[0]['first_pid_exists'] and dead['active_worker']['pid']==1747 and not new['first_pid_exists'] and dead['monotonic']<new['monotonic'] and dead['utc']<new['active_worker']['started_utc'])
        ck('new_child_identity',new['active_worker']['pid']==next_started['pid']==2826 and next_started['ordinal']==1 and next_started['monotonic_start']>dead['monotonic'])
        records={r['path']:r for r in report['artifacts']}
        ck('unique_artifact_records',len(records)==len(report['artifacts'])==1827)
        for path,r in records.items():
            p=ROOT/path
            ck('artifact:'+path,p.stat().st_size==r['bytes'] and sha(p)==r['sha256'])
            inputs[path]=dict(bytes=r['bytes'],sha256=r['sha256'])
            if path.endswith('.complete.json'):
                m=json.loads(p.read_text())
                ck('completion:'+path,m['complete'] and m['version']==1 and all(records[a['path']]==a for a in m['artifacts']))
        files=[p for p in FIRST.rglob('*') if p.is_file()]
        expected=set(records)|{str((FIRST/name).relative_to(ROOT)) for name in ['started.json','progress.json','worker.log','result.json','terminal.json','c0-prefix-gate.json']}
        ck('exact_closed_file_set',set(str(p.relative_to(ROOT)) for p in files)==expected and len(files)==1833)
        ck('no_incomplete_publications',not any('.tmp-' in p.name or '.failure-' in p.name or p.name.endswith('.lock') for p in files))
        total=sum(p.stat().st_size for p in files);last_line=(FIRST/'worker.log').read_bytes().splitlines(keepends=True)[-1]
        ck('post_result_byte_delta',terminal['resources']['trial_output_bytes']-report['resources']['trial_output_bytes']==(FIRST/'result.json').stat().st_size)
        ck('final_bytes_exact',total==terminal['resources']['trial_output_bytes']+(FIRST/'terminal.json').stat().st_size+len(last_line))
        log_end=json.loads(last_line)
        ck('final_log_terminal',log_end['status']==terminal['status'] and log_end['tick']==30000 and log_end['wall_seconds']==terminal['wall_seconds'])
        # First worker has no closed trial directories. Root streams/selection
        # are pinned; the finite active record size is reconstructed using the
        # inspected atomic_json formatting. Parent progress is written later.
        run_name=str(RUN.relative_to(ROOT))
        root_sources=[r for p,r in plan['sources'].items() if p.startswith(run_name+'/') and '/' not in p[len(run_name)+1:]]
        active_bytes=len((json.dumps(rows[0]['active_worker'],indent=2,allow_nan=False)+'\n').encode())
        root_expected=sum(r['bytes'] for r in root_sources)+(RUN/'manifest.json').stat().st_size+(RUN/'started.json').stat().st_size+active_bytes
        ck('global_root_byte_offset_reconstruction',terminal['resources']['global_output_bytes']-terminal['resources']['trial_output_bytes']==root_expected)
        ck('resource_limits',terminal['resources']['trial_wall_seconds']<=plan['budgets']['trial_wall_seconds'] and total<=plan['budgets']['trial_output_bytes'] and
           terminal['resources']['worker_peak_rss_bytes']<=plan['budgets']['worker_peak_rss_bytes'] and terminal['resources']['free_bytes']>=plan['budgets']['min_free_bytes'])
        ck('timing_order',report['wall_seconds']<=terminal['resources']['trial_wall_seconds']<=terminal['wall_seconds'])
        details=dict(worker_pid=1747,next_worker_pid=2826,completed_tick=30000,authoritative_status=terminal['status'],
            producer_wall_seconds=terminal['wall_seconds'],producer_peak_rss_bytes=terminal['resources']['worker_peak_rss_bytes'],
            observed_ps_at_elapsed49s_rss_kib=610960,observed_ps_provenance='Read-only ps tool output in task transcript; not a peak measurement',
            worker_final_bytes=total,terminal_measured_bytes=terminal['resources']['trial_output_bytes'],terminal_bytes=(FIRST/'terminal.json').stat().st_size,
            final_log_line_bytes=len(last_line),byte_residual=0,files=len(files),archive_records=len(records),root_offset_reconstructed_bytes=root_expected,
            observed_first_absent_utc=dead['utc'],next_dispatch_record_utc=new['active_worker']['started_utc'],next_worker_start_utc=next_started['started_utc'],
            report_sha256=sha(FIRST/'result.json'),terminal_sha256=sha(FIRST/'terminal.json'),checks_reported_by_worker=report['checks_passed'])
        for path,record in inputs.items():ck('unchanged:'+path,sha(ROOT/path)==record['sha256'])
    except Exception as error:errors.append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    result=dict(version=1,completed_utc=datetime.now(timezone.utc).isoformat(),passed=not errors and all(c['passed'] for c in checks),
        scope='One closed real worker only; metadata/hash/byte audit and prior read-only PID observation. No process launch, signal, graph load, neural replay or live-run mutation.',
        script_sha256=sha(__file__),inputs=inputs,checks=checks,check_count=len(checks),errors=errors,details=details,
        limits=['PID evidence is a 20ms polling observation plus the inspected parent wait-before-dispatch order, not continuous OS tracing.',
                'Wall and peak RSS are worker reports; an independent ps sample confirms live RSS at one earlier instant, not the historical peak.',
                'Root-byte reconstruction uses the known finite JSON serialization of the saved first active-record observation.',
                'Raw-file hashes and completion records were checked; this is not an independent neuronal trajectory review or a panel-wide resource conclusion.'])
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),details=details,errors=errors),indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
