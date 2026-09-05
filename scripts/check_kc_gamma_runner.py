#!/usr/bin/env python3
"""Run the real worker/archive path on 12 manufactured cells; no male graph."""
import json
from pathlib import Path
import traceback
from datetime import datetime,timezone
import numpy as np
import experiment_kc_gamma_intervention as runner
from check_navigation_mbon_intervention_kernel import fixture
from inhibitory_recurrent_panel_archive import save_archive,atomic_json,load_archive
from kc_gamma_intervention_kernel import original
from prepare_kc_gamma_contact_mask import record,write,ROOT

OUT=ROOT/'validation/kc-gamma-runner-checks.json'
def main():
    if OUT.exists():raise FileExistsError('Preserve first runner check')
    work=ROOT/'runs'/('gamma-runner-fixture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));work.mkdir()
    sourcepins=[record(p) for p in [Path(__file__),ROOT/'scripts/experiment_kc_gamma_intervention.py',ROOT/'scripts/kc_gamma_intervention_kernel.py',ROOT/'scripts/inhibitory_recurrent_panel_archive.py',ROOT/'scripts/check_navigation_mbon_intervention_kernel.py']]
    write(work/'fixture-plan.json',dict(inputs=sourcepins,scope='One synthetic12-cell worker, original tick5000 through30000, including active and restored delivery windows. Frozen before simulation. No MaleCNS data or biological outcome analysis.',seed=211,probability=.5,modified_edges=[0,3],retained_weights=[0.,25.]))
    report=dict(passed=False,checks={},error=None,inputs=sourcepins,fixture_plan=record(work/'fixture-plan.json'),work_dir=str(work.relative_to(ROOT)))
    def ck(name,value):
        report['checks'][name]=bool(value)
        if not value:raise AssertionError(name)
    try:
        original.configure_threads(1);ids,ptr,tgt,w,inputs,selected=fixture(True)
        graphdir=work/'graph';graphdir.mkdir()
        for name,a in zip(['neuron_ids','indptr','targets','weights'],[ids,ptr,tgt,w]):np.save(graphdir/(name+'.npy'),a)
        u=np.random.default_rng(211).random((30000,len(inputs)));states=np.arange(30001,dtype=np.uint64)
        net=original.FactorialNetwork(ids,ptr,tgt,w,'H1',inputs,selected,11)
        out=net.advance(u[:5000],np.full(len(inputs),.5));cp=net.checkpoint();counts=np.zeros((7,len(ids)),np.int64)
        np.add.at(counts,(np.searchsorted(runner.WINDOWS,out['spike_ticks'],side='right')-1,out['spike_indices']),1)
        cp.update(window_counts_observed=counts,logical_rng_state=int(states[5000]))
        old=work/'old';d=old/'synthetic';d.mkdir(parents=True)
        save_archive(d/'checkpoint-05000',cp);save_archive(d/'chunk-0099',dict(spike_ticks=out['spike_ticks'][out['spike_ticks']>=4950],spike_indices=out['spike_indices'][out['spike_ticks']>=4950]))
        save_archive(old/'input-seed11',dict(uniforms=u,logical_rng_boundaries=states))
        mask=work/'mask.npz';np.savez(mask,edge_indices=np.array([0,3],np.int64),retained_weight=np.array([0.,25.]),source_indices=np.array([0,1],np.int64),baseline_weight=np.array([100.,100.]))
        run=work/'new';run.mkdir();planpath=work/'plan.json'
        spec=dict(ordinal=0,name='synthetic',condition='fixture',seed=11)
        plan=dict(inputs=sourcepins,trials=[spec],run_dir=str(run.relative_to(ROOT)),prior_run_dir=str(old.relative_to(ROOT)),threads=1,graph_sha256=net.graph_sha256,selected_indices=selected.tolist(),event_indices=selected.tolist(),delivery_window_ticks=[5000,15000],condition_rates_hz={'fixture':[5000.,5000.,5000.,0.]},checkpoint_ticks=[5000,10000,15000,20000,25000,30000],budgets=dict(trial_wall_seconds=300,worker_peak_rss_bytes=4*1024**3,trial_output_bytes=1024**3,min_free_bytes=1024**3))
        atomic_json(planpath,plan);runner.GRAPH=graphdir;runner.MASK=mask;runner.PLAN=planpath
        code=runner.worker(0,record(planpath)['sha256']);result=json.loads((run/'synthetic'/'result.json').read_text());term=json.loads((run/'synthetic'/'terminal.json').read_text())
        ck('worker completed',code==0 and result['passed'] and term['passed'])
        ck('full declared interval',result['completed_tick']==result['last_durable_chunk_end_tick']==30000)
        ck('actual modification exercised',result['modified_deliveries']>0)
        ck('terminal publication hash',term['result']==record(run/'synthetic'/'result.json'))
        for r in result['artifacts']:ck('archive '+r['path'],record(ROOT/r['path'])==r)
        for i in [100,299,300,599]:
            out=load_archive(run/'synthetic'/f'chunk-{i:04d}');side=out['contact_intervention']
            ck(f'window at chunk{i}',side['counts'].sum()>0 if i<300 else side['counts'].sum()==0)
        # Real archive restore includes intervention specification, even after restoration.
        final=load_archive(run/'synthetic'/'checkpoint-30000');ck('final specification retained',final['intervention_specification']['delivery_window_ticks']==[5000,15000])
        ck('source unchanged',[record(ROOT/r['path']) for r in sourcepins]==sourcepins)
        report.update(passed=True,worker_result=record(run/'synthetic'/'result.json'),worker_checks=result['checks'],modified_deliveries=result['modified_deliveries'])
    except Exception:report['error']=traceback.format_exc()
    report['check_count']=len(report['checks']);report['completed_utc']=datetime.now(timezone.utc).isoformat();write(OUT,report)
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
