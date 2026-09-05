#!/usr/bin/env python3
"""Frozen fake-process parent checks; never launches workers or loads a graph."""
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import io
import json
import signal
import traceback
import experiment_inhibitory_recurrent_panel as runner
import inhibitory_recurrent_panel_archive as archive

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'runs/inhibitory-recurrent-panel-dispatch-fixtures'
PLAN = ROOT/'validation/inhibitory-recurrent-panel-dispatch-plan.json'
OUT = ROOT/'validation/inhibitory-recurrent-panel-dispatch-checks.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if BASE.exists() or PLAN.exists() or OUT.exists():
        raise RuntimeError('Refusing to overwrite frozen fake-process attempt')
    sources = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),Path(runner.__file__),Path(archive.__file__)]}
    PLAN.write_text(json.dumps(dict(version=1, frozen_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        scope='Parent orchestration with fake Popen objects and tiny saved reports only. No worker, kernel, graph or source-input execution.',
        cases=['successful sixty-trial order and single live worker', 'C0 resource limit before prefix',
               'C0 resource limit after prefix', 'C0 correctness failure', 'missing child result',
               'global budget before dispatch', 'global budget after final child', 'interrupt child then reap',
               'parent publication failure after launching child signals and reaps',
               'corrupted C0 checkpoint payload blocks altered dispatch despite unchanged completion marker',
               'prepared plan and source hash guards reject modifications without source input loading',
               'failed prerequisite stops prepare before input generation'],
        exclusions='Source checking, metrics, disk-free and child computation are mocked. Real archive JSON writes and parent dispatch/gate/finalization paths are exercised.'),indent=2)+'\n')
    BASE.mkdir()
    checks, errors, cases = [], [], {}

    def ck(name,value):
        checks.append(dict(name=name,passed=bool(value)))
        if not value: raise AssertionError(name)

    try:
        for case in ['success','resource_before_prefix','resource_after_prefix','correctness','missing_result','global_budget','final_global_budget','interrupt','parent_publication_failure','checkpoint_corrupt']:
            sandbox=BASE/case;sandbox.mkdir();(sandbox/'validation').mkdir();run=sandbox/'run';run.mkdir()
            order=[]
            combinations=[('C0',seed,c) for seed in [11,12,13] for c in runner.CONDITIONS]
            combinations += [(arm,seed,c) for c in runner.CONDITIONS for seed in [11,12,13] for arm in ['C1','H0','H1']]
            for arm,seed,condition in combinations:
                i=len(order);order.append(dict(ordinal=i,arm=arm,seed=seed,condition=condition,name=f'{i:02d}-{arm}-seed{seed}-{condition}'))
            plan=dict(run_dir='run',order=order,sources={},environment={},budgets=dict(global_wall_seconds=3600,
                global_output_bytes=0 if case=='global_budget' else 1024**3,min_free_bytes=1,failure_reserve_bytes=10**6),
                seeds=[11,12,13],condition_order=runner.CONDITIONS,graph_sha256='synthetic-no-graph-loaded')
            plan_path=sandbox/'validation/inhibitory-recurrent-panel-plan.json'
            plan_path.write_text(json.dumps(plan))
            digest=sha(plan_path)
            (run/'manifest.json').write_text(json.dumps(dict(plan=dict(path=str(plan_path.relative_to(sandbox)),bytes=plan_path.stat().st_size,sha256=digest))))
            launched=[];signals=[];live=set();reaped=[];fake={};max_live=[0]

            class Process:
                def __init__(self,args,**kwargs):
                    self.ordinal=int(args[args.index('--ordinal')+1]);self.pid=900000+self.ordinal
                    self.returncode=None;self.interrupted=False;self.wait_calls=0
                    launched.append(self.ordinal);live.add(self.pid);fake[self.pid]=self
                    max_live[0]=max(max_live[0],len(live))
                    if max_live[0]>1: raise AssertionError('Overlapping fake workers')
                    kwargs['stdout'].write(b'FAKE PROCESS ONLY; no neural run\n')
                    kwargs['stdout'].flush()

                def poll(self): return self.returncode

                def send_signal(self,sig):
                    signals.append([self.pid,int(sig)]);self.interrupted=True

                def terminate(self): self.send_signal(signal.SIGTERM)
                def kill(self): self.send_signal(signal.SIGKILL)

                def wait(self,timeout=None):
                    self.wait_calls+=1
                    if case=='interrupt' and not self.interrupted and self.wait_calls==1:
                        raise KeyboardInterrupt('Intentional parent interrupt with live fake child')
                    if self.returncode is not None: return self.returncode
                    spec=order[self.ordinal];directory=run/spec['name']
                    is_first=self.ordinal==0
                    resource=is_first and case.startswith('resource_')
                    failed=self.interrupted or (is_first and case in ['correctness','interrupt'])
                    prefix=not (is_first and case in ['resource_before_prefix','correctness','interrupt'])
                    status='resource_limited' if resource else 'correctness_or_interruption_failure' if failed else 'complete'
                    tick=500 if not prefix else 15000 if resource else 30000
                    if spec['arm']=='C0' and prefix:
                        archive.save_archive(directory/'checkpoint-15000',dict(tick=15000,coherent_state=True,synthetic=True,
                            seed=spec['seed'],arm='C0',graph_sha256=plan['graph_sha256']))
                        cp=directory/'checkpoint-15000.complete.json'
                        gate=dict(passed=True,seed=spec['seed'],condition=spec['condition'],arm='C0',tick=15000,
                                  plan_sha256=digest,checks=dict(synthetic=True),
                                  checkpoint=dict(path=str(cp.relative_to(sandbox)),bytes=cp.stat().st_size,sha256=sha(cp)))
                        (directory/'c0-prefix-gate.json').write_text(json.dumps(gate))
                        if case=='checkpoint_corrupt' and is_first:
                            with (directory/'checkpoint-15000.npz').open('ab') as f:f.write(b'intentional payload corruption')
                    report=dict(**spec,status=status,complete=status=='complete',last_durable_chunk_end_tick=tick,
                        c0_prefix_passed=prefix and spec['arm']=='C0',summary=None,errors=[],artifacts=[],
                        global_resource_stop=False,plan_sha256=digest,wall_seconds=0.01,resources={})
                    if case!='missing_result':
                        rp=directory/'result.json';rp.write_text(json.dumps(report))
                        terminal=dict(status=status,complete=status=='complete',global_resource_stop=False,
                            result=dict(path=str(rp.relative_to(sandbox)),bytes=rp.stat().st_size,sha256=sha(rp)),errors=[])
                        (directory/'terminal.json').write_text(json.dumps(terminal))
                    self.returncode=2 if resource else 1 if failed else -9 if case=='missing_result' else 0
                    live.remove(self.pid);reaped.append(self.pid)
                    return self.returncode

            def killpg(pid,sig): fake[pid].send_signal(sig)
            real_atomic=runner.atomic_json
            def atomic(path,value,**kwargs):
                if case=='parent_publication_failure' and Path(path).name=='active-worker.json':
                    raise IOError('Intentional parent active-worker publication failure')
                return real_atomic(path,value,**kwargs)
            output=io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(runner,'ROOT',sandbox))
                stack.enter_context(patch.object(archive,'ROOT',sandbox))
                stack.enter_context(patch.object(runner,'PLAN',plan_path))
                stack.enter_context(patch.object(runner,'check_sources',lambda *args,**kwargs:None))
                stack.enter_context(patch.object(runner,'paired_contrasts',lambda *args,**kwargs:dict(synthetic=True)))
                stack.enter_context(patch.object(runner,'atomic_json',atomic))
                stack.enter_context(patch.object(runner.subprocess,'Popen',Process))
                stack.enter_context(patch.object(runner.os,'killpg',killpg))
                stack.enter_context(patch.object(runner.os,'getpgid',lambda pid:pid))
                stack.enter_context(patch.object(runner.shutil,'disk_usage',lambda path:SimpleNamespace(free=0 if case=='final_global_budget' and len(reaped)==60 else 10**12)))
                stack.enter_context(redirect_stdout(output))
                code=runner.run_panel(plan)
            (sandbox/'parent-output.txt').write_text(output.getvalue())
            result=json.loads((run/'results.json').read_text())
            terminal=json.loads((run/'terminal.json').read_text())
            ck(case+':terminal_result_hash',terminal['results']['sha256']==sha(run/'results.json'))
            ck(case+':all_children_reaped',not live and len(reaped)==len(launched))
            ck(case+':sequential',max_live[0]<=1 and launched==list(range(len(launched))))
            if case=='success':
                ck(case+':sixty_complete',code==0 and result['complete'] and len(launched)==60)
                ck(case+':all_fifteen_gates',json.loads((run/'all-c0-prefixes-passed.json').read_text())['count']==15)
            elif case=='resource_before_prefix':
                ck(case+':no_altered_arms',len(launched)==15 and all(order[i]['arm']=='C0' for i in launched) and not result['complete'])
            elif case=='checkpoint_corrupt':
                ck(case+':no_altered_arms',len(launched)==15 and not result['complete'] and code!=0)
            elif case=='resource_after_prefix':
                ck(case+':complete_gates_allow_partial_panel',len(launched)==60 and not result['complete'] and code!=0)
            elif case in ['correctness','missing_result']:
                ck(case+':stop_after_first',len(launched)==1 and not result['complete'] and code!=0)
            elif case=='global_budget':
                ck(case+':no_launch',not launched and not result['complete'] and code!=0)
            elif case=='final_global_budget':
                ck(case+':final_resource_not_complete',len(launched)==60 and not result['complete'] and code!=0)
            elif case in ['interrupt','parent_publication_failure']:
                ck(case+':signal_and_reap',len(launched)==1 and bool(signals) and not result['complete'] and code!=0)
            cases[case]=dict(status=result['status'],complete=result['complete'],exit_code=code,launched_ordinals=launched,
                terminal_status=terminal['status'],terminal_complete=terminal['complete'],
                reaped_pids=reaped,signals=signals,maximum_live_workers=max_live[0])
        guard=BASE/'plan_guard';guard.mkdir();(guard/'run').mkdir()
        source_file=guard/'tiny-input.txt';source_file.write_text('original synthetic source')
        guard_plan=dict(run_dir='run',sources={'tiny-input.txt':dict(sha256=sha(source_file))},environment={});guard_path=guard/'plan.json'
        guard_path.write_text(json.dumps(guard_plan));guard_sha=sha(guard_path)
        (guard/'run/manifest.json').write_text(json.dumps(dict(plan=dict(sha256=guard_sha))))
        with patch.object(runner,'ROOT',guard),patch.object(runner,'PLAN',guard_path),patch.object(runner,'environment',lambda:{}):
            runner.check_sources(guard_plan,guard_sha)
            ck('plan_guard:original_passes',True)
            source_file.write_text('changed synthetic source')
            try:runner.check_sources(guard_plan,guard_sha)
            except RuntimeError:ck('source_guard:changed_file_refused',True)
            else:ck('source_guard:changed_file_refused',False)
            guard_path.write_text(json.dumps(dict(guard_plan,changed=True)))
            try:runner.check_sources(guard_plan,guard_sha)
            except RuntimeError:ck('plan_guard:changed_file_refused',True)
            else:ck('plan_guard:changed_file_refused',False)
        prerequisite=BASE/'failed_prerequisite';prerequisite.mkdir();(prerequisite/'validation').mkdir()
        (prerequisite/'validation/inhibitory-recurrent-panel-kernel-checks.json').write_text(json.dumps(dict(passed=False,synthetic=True)))
        with patch.object(runner,'ROOT',prerequisite),patch.object(runner,'PLAN',prerequisite/'absent-plan.json'):
            try:runner.prepare()
            except RuntimeError as error:ck('prepare:failed_prerequisite_refused','Prerequisite not passing' in str(error))
            else:ck('prepare:failed_prerequisite_refused',False)
        ck('prepare:no_run_created',not (prerequisite/'runs').exists())
    except Exception as error:
        errors.append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    for path,digest in sources.items():checks.append(dict(name='unchanged:'+path,passed=sha(ROOT/path)==digest))
    artifacts={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in BASE.rglob('*') if p.is_file()}
    result=dict(version=1,completed_utc=datetime.now(timezone.utc).isoformat(),passed=not errors and all(c['passed'] for c in checks),
        plan_sha256=sha(PLAN),source_sha256=sources,checks=checks,check_count=len(checks),errors=errors,cases=cases,artifacts=artifacts,
        limits=['All processes are fake; this does not verify OS signals, memory release or actual child code.',
                'Child report contents, source checks, metrics and free disk are mocked; no neural or reference-solver execution.',
                'Actual archive implementation has its own frozen filesystem test and independent review.'])
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),cases=cases,errors=errors),indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
