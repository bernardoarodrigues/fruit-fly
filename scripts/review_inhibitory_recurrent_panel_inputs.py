#!/usr/bin/env python3
"""Pure source-extracted panel input/mapping audit; never imports the runner.

Execute only the runner's random-stream function, literal scheduling/order
expressions and C0 comparison statements against saved or manufactured data.
No graph/kernel/model class is constructed and no prepare/run/trial is called.
"""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback
from types import SimpleNamespace

import numpy as np
from inhibitory_recurrent_panel_metrics import build_cohorts, summarize_counts, paired_contrasts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'scripts/experiment_inhibitory_recurrent_panel.py'
OUTPUT = ROOT/'validation/inhibitory-recurrent-panel-input-review.json'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2), b''): h.update(b)
    return h.hexdigest()


def assignment(node, name):
    return isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == name for x in node.targets)


def module(nodes):
    return compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(SOURCE), 'exec')


def expression(node):
    return compile(ast.fix_missing_locations(ast.Expression(body=node)), str(SOURCE), 'eval')


def audit():
    if OUTPUT.exists(): raise FileExistsError('Preserve the first input-review attempt')
    result=dict(schema=1, started_utc=datetime.now(timezone.utc).isoformat(), checks=[], inputs={}, exceptions=[],
                method='Read-only source extraction and saved-input/manufactured-data checks; no producer/model imports or neural run')

    def ck(name, value, detail=None):
        row=dict(name=name,passed=bool(value))
        if detail is not None: row['detail']=detail
        result['checks'].append(row)

    def pin(path):
        result['inputs'][str(path.relative_to(ROOT))]=dict(bytes=path.stat().st_size,sha256=sha(path))

    try:
        for p in (SOURCE, Path(__file__), ROOT/'scripts/inhibitory_recurrent_panel_metrics.py',
                  ROOT/'validation/inhibitory-recurrent-panel-metrics-checks.json',
                  ROOT/'validation/or42a-summary-plan.json',ROOT/'validation/or42a-summary-experiment.json',
                  ROOT/'data/processed/malecns_v1/neuron_ids.npy'):
            pin(p)
        text=SOURCE.read_text(); tree=ast.parse(text)
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        ns={'np':np}
        constants=[n for n in tree.body if isinstance(n,ast.Assign) and
                   any(isinstance(x,ast.Name) and x.id in ('CONDITIONS','SEEDS','EDGES','AUDIT_RANGES','CHECKPOINTS') for x in n.targets)]
        exec(module(constants+[functions['streams'],functions['exact']]),ns)
        conditions=['no_input','constant_baseline','ethyl_acetate','isoamyl_acetate','ethyl_acetate_source_outputs_blocked']
        edges=[0,500,5000,10000,15000,20000,25000,30000]
        ck('literal_conditions_seeds_windows', ns['CONDITIONS']==conditions and ns['SEEDS']==[11,12,13]
           and ns['EDGES'].tolist()==edges)
        ck('checkpoint_and_audit_boundaries', ns['CHECKPOINTS']==set(edges)
           and ns['AUDIT_RANGES']==[(0,500),(5000,5500),(15000,15500),(29500,30000)])
        prepare=functions['prepare'].body
        begin=next(i for i,n in enumerate(prepare) if assignment(n,'order'))
        order_nodes=prepare[begin:begin+4]
        ck('source_order_fragment_shape', len(order_nodes)==4 and all(isinstance(n,ast.For) for n in order_nodes[1:]))
        order_ns=dict(ns);exec(module(order_nodes),order_ns)
        order=order_ns['order']
        expected=[('C0',s,c) for s in (11,12,13) for c in conditions]
        expected += [(a,s,c) for c in conditions for s in (11,12,13) for a in ('C1','H0','H1')]
        ck('exact_60_job_order', [(t['arm'],t['seed'],t['condition']) for t in order]==expected
           and [t['ordinal'] for t in order]==list(range(60)) and len({t['name'] for t in order})==60)
        ck('all_15_C0_jobs_precede_altered', all(t['arm']=='C0' for t in order[:15])
           and all(t['arm']!='C0' for t in order[15:]))

        old=json.loads((ROOT/'validation/or42a-summary-plan.json').read_text())
        prior=json.loads((ROOT/'validation/or42a-summary-experiment.json').read_text())
        ids=np.load(ROOT/'data/processed/malecns_v1/neuron_ids.npy',mmap_mode='r')
        cohorts=build_cohorts(ids,old)
        result['cohort_sizes']={k:len(v) for k,v in cohorts.items()}
        ck('actual_cohorts_pinned_ID_join', len(cohorts['source'])==36 and len(cohorts['first_hop_non_source'])==365
           and ids[cohorts['targets']].tolist()==[67052,13314]
           and ids[cohorts['source']].tolist()==old['source_body_ids'])
        matched={(t['seed'],t['condition']):t for t in prior['trials']}
        ck('exact_15_original_trial_keys', len(prior['trials'])==len(matched)==15
           and set(matched)=={(s,c) for s in (11,12,13) for c in conditions})

        trial_nodes=list(ast.walk(functions['trial']))
        rate_node=next(n for n in trial_nodes if assignment(n,'rate'))
        probability_node=next(n for n in trial_nodes if assignment(n,'probabilities'))
        candidate_rates={c:old['conditions'][c]+[0.] for c in conditions}
        expected_rates={'no_input':[0.,0.,0.,0.],'constant_baseline':[11.,11.,11.,0.],
                        'ethyl_acetate':[11.,149.,11.,0.],'isoamyl_acetate':[11.,57.67908699377742,11.,0.],
                        'ethyl_acetate_source_outputs_blocked':[11.,149.,11.,0.]}
        ck('unchanged_condition_values_and_off_tail',candidate_rates==expected_rates)
        schedule={}
        for condition in conditions:
            rates=[];all_steps=True
            for start in range(0,30000,50):
                env=dict(ns,plan={'condition_rates_hz':candidate_rates},spec={'condition':condition},start=start)
                exec(module([rate_node,probability_node]),env)
                expected_rate=expected_rates[condition][min(start//5000,3)]
                rates.append(env['rate'])
                all_steps &= bool(env['rate']==expected_rate
                   and env['probabilities'].shape==(36,)
                   and np.array_equal(env['probabilities'],np.full(36,expected_rate)*.1/1000.))
            schedule[condition]=np.repeat(rates,50)
            ck('all_600_schedule_chunks:'+condition,all_steps,dict(chunks=600,ticks=30000,columns=36))
        ck('no_schedule_transition_inside_chunk',all(b%50==0 for b in [0,5000,10000,15000,30000]))
        result['rng']={}
        for seed in (11,12,13):
            uniforms, states=ns['streams'](seed)
            state=int(np.random.SeedSequence(seed).generate_state(1,dtype=np.uint64)[0]) or 1
            mask=(1<<64)-1
            same=int(states[0])==state
            for tick in range(30000):
                for col in range(36):
                    state=(state^(state>>12))&mask
                    state=(state^(state<<25))&mask
                    state=(state^(state>>27))&mask
                    expected_u=(((state*2685821657736338717)&mask)>>11)/(2**53)
                    same &= bool(uniforms[tick,col]==expected_u)
                same &= int(states[tick+1])==state
            ck('all_independent_xorshift_draws_and_boundaries:seed'+str(seed),same
               and uniforms.shape==(30000,36) and states.shape==(30001,))
            result['rng'][str(seed)]=dict(draws=uniforms.size,start=int(states[0]),end=int(states[-1]),
                uniform_sha256=hashlib.sha256(uniforms.tobytes()).hexdigest(),boundary_sha256=hashlib.sha256(states.tobytes()).hexdigest())
            for condition in conditions:
                t=matched[(seed,condition)];path=ROOT/t['run_dir'];pin(path/'trace.npz');pin(path/'samples.jsonl')
                with np.load(path/'trace.npz',allow_pickle=False) as z:
                    requested=z['requested_arrival_ticks'];columns=z['requested_arrival_source_column']
                    candidates=np.zeros((15000,36),bool);candidates[requested,columns]=True
                    expected_candidates=uniforms[:15000] < (schedule[condition][:15000,None]*.1/1000.)
                    ck(f'old_candidates:{seed}:{condition}',np.array_equal(candidates,expected_candidates))
                    ck(f'old_source_order:{seed}:{condition}',np.array_equal(z['source_graph_indices'],cohorts['source'])
                       and z['source_body_ids'].tolist()==old['source_body_ids'])
                    ck(f'old_rng_endpoints:{seed}:{condition}',int(z['initial_rng_state'][0])==int(states[0])
                       and int(z['final_rng_state'][0])==int(states[15000]))
                samples=[json.loads(s) for s in (path/'samples.jsonl').read_text().splitlines()]
                ck(f'all_old_5ms_rng_and_rates:{seed}:{condition}',len(samples)==300
                   and all(s['rng_before']==int(states[50*j]) and s['rng_after']==int(states[50*(j+1)])
                           and s['rate_hz']==schedule[condition][50*j] for j,s in enumerate(samples)))
                ck(f'off_probability_zero_draws_retained:{seed}:{condition}',not (uniforms[15000:] < 0.).any()
                   and len(states[15000:])==15001)

        # Execute the actual C0 matching block with manufactured ordered arrays,
        # not neural outputs, to check cursors, source columns and boundary ticks.
        old_block=next(n for n in trial_nodes if isinstance(n,ast.If)
                       and 'old_data is not None and end <= 15000'==ast.unparse(n.test))
        fake_ticks=np.array([0,49,50,499,500,14999],np.int64)
        fake_cells=np.array([0,1,0,1,0,1],np.int32)
        req=np.array([0,49,50,500,14999],np.int64);cols=np.array([0,1,0,1,0],np.int64)
        flags=np.array([True,False,True,True,False])
        fake_states=np.arange(30001,dtype=np.uint64)
        fake_old=dict(all_spike_ticks=fake_ticks,all_spike_graph_indices=fake_cells,
            requested_arrival_ticks=req,requested_arrival_source_column=cols,applied_direct_voltage_arrival=flags)
        fake_samples=[dict(rng_before=50*j,rng_after=50*(j+1),actual_edge_visits=0,
                          global_voltage_min_mv=-52.,global_voltage_max_mv=-52.) for j in range(300)]
        env=dict(ns,old_data=fake_old,old_samples=fake_samples,states=fake_states,spike_cursor=0,
                 net=SimpleNamespace(v=np.full(2,-52.)))
        good=True
        for chunk in range(300):
            start,end=chunk*50,(chunk+1)*50;keep=(fake_ticks>=start)&(fake_ticks<end)
            ca=np.zeros((50,36),bool);ap=np.zeros_like(ca);select=(req>=start)&(req<end)
            ca[req[select]-start,cols[select]]=True;ap[req[select]-start,cols[select]]=flags[select]
            env.update(start=start,end=end,chunk=chunk,ii=fake_cells[keep],tt=fake_ticks[keep],checks={},
                       out=dict(candidate=ca,applied=ap,per_tick={'edge_counts':np.zeros((50,4,3),np.int64)}))
            exec(module(old_block.body),env)
            good &= all(env['checks'].values())
        ck('actual_C0_source_matching_block_all_300_chunks',good and env['spike_cursor']==len(fake_ticks))
        prefix=next(n for n in trial_nodes if assignment(n,'prefix_checks'))
        merge=next(k.value for k in prefix.value.keywords if k.arg=='counts')
        counts=np.arange(7*3,dtype=np.int64).reshape(7,3)
        old_counts=np.stack((counts[:2].sum(axis=0),counts[2],counts[3]))
        env=dict(ns,counts=counts,old_data={'all_neuron_window_spike_counts':old_counts})
        ck('actual_C0_seven_to_three_window_merge',eval(expression(merge),env))
        env['old_data']['all_neuron_window_spike_counts']=old_counts.copy();env['old_data']['all_neuron_window_spike_counts'][0,1]+=1
        ck('C0_merge_detects_wrong_count',not eval(expression(merge),env))

        # Pure streaming integration fixture at a durable partial boundary.
        partial_counts=np.zeros((7,len(ids)),np.int64)
        summary=summarize_counts(partial_counts,17500,cohorts)
        ck('partial_first_off_window_is_not_complete',summary['window_complete']==[True,True,True,True,False,False,False]
           and summary['cohort_metrics']['source'][4]['spike_count'] is None)
        contrasts=paired_contrasts({(11,'C0','no_input'):summary})
        ck('missing_altered_trials_and_partial_off_are_null',all(r['difference_hz_per_cell'] is None
           for r in contrasts['rows'] if r['contrast'] in ('H0_minus_C0','H1_minus_C1','inhibition_by_handling_interaction')))

        # Execute only the parent's final source/analysis try block with source
        # checking stubbed. No dispatch, archive publication or worker executes.
        analysis=next(n for n in ast.walk(functions['run_panel']) if isinstance(n,ast.Try)
                      and not n.finalbody and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Name)
                      and x.func.id=='paired_contrasts' for x in ast.walk(n)))
        empty_result=dict(trials=[],status='global_resource_limit',complete=False,errors=[])
        analysis_ns=dict(np=np,check_sources=lambda *args:None,paired_contrasts=paired_contrasts,
                         plan={},expected_sha='fixture',result=empty_result)
        exec(module([analysis]),analysis_ns)
        ck('actual_parent_empty_analysis_is_explicitly_unavailable',not empty_result['errors']
           and empty_result['status']=='global_resource_limit' and empty_result.get('contrasts') is None)
        small={'one':np.array([0],np.int32)}
        full=summarize_counts(np.ones((7,1),np.int64),30000,small)
        limited_counts=np.ones((7,1),np.int64);limited_counts[4:]=0
        limited=summarize_counts(limited_counts,17500,small)
        analysis_result=dict(status='failed',complete=False,errors=[],trials=[
            dict(seed=11,arm='C0',condition='no_input',status='complete',summary=full),
            dict(seed=11,arm='C1',condition='no_input',status='resource_limited',summary=limited),
            dict(seed=11,arm='H0',condition='no_input',status='correctness_or_interruption_failure',summary=full),
            dict(seed=11,arm='H1',condition='no_input',status='complete',summary=full)])
        for t in analysis_result['trials']:
            t.update(name='fixture-'+t['arm'],complete=t['status']=='complete',
                     completed_tick=t['summary']['completed_tick'],counts_end_tick=t['summary']['completed_tick'])
        analysis_ns['result']=analysis_result
        exec(module([analysis]),analysis_ns)
        rows=analysis_result['contrasts']['rows']
        def row(label,window):
            return next(r for r in rows if r['contrast']==label and r['seed']==11 and
                        r['condition']=='no_input' and r['cohort']=='one' and r['window']==window)
        ck('actual_parent_excludes_clock_complete_failed_trial',not analysis_result['errors']
           and row('H0_minus_C0','pulse')['difference_hz_per_cell'] is None)
        ck('actual_parent_preserves_resource_complete_prefix',row('H1_minus_C1','pulse')['complete'])
        ck('actual_parent_resource_partial_off_is_unavailable',row('H1_minus_C1','off_early')['difference_hz_per_cell'] is None)
        result['source_lines']={name:dict(start=functions[name].lineno,end=functions[name].end_lineno)
                                for name in ('streams','prepare','trial','run_panel')}
        result['limits']=['Only explicitly extracted pure statements executed. No runner prepare/run/trial or model constructor called.',
            'Resource, archive publication, dispatch/failure behavior and numerical references require the separate reviewers.',
            'Saved original candidate/RNG/source mappings verified without decompressing full original spike streams.',
            'Passing arithmetic/record checks does not establish biological behavior, physiological calibration or model promotion.']
    except Exception as error:
        result['exceptions'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    finally:
        for path,rec in result['inputs'].items():
            ck('unchanged:'+path,sha(ROOT/path)==rec['sha256'])
        result['check_count']=len(result['checks'])
        result['passed']=not result['exceptions'] and all(c['passed'] for c in result['checks'])
        result['finished_utc']=datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps(dict(passed=result['passed'],checks=result['check_count'],exceptions=result['exceptions'],sha256=sha(OUTPUT))))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(audit())
