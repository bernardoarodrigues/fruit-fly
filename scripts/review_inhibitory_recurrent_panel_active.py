#!/usr/bin/env python3
"""Active C0/C1 saved-data audit. No producer/kernel/metric helper imports."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,time,hashlib
import numpy as np
from review_inhibitory_recurrent_panel_trial import Audit,exact,ROOT,PLAN


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ordinal',type=int,default=1);args=parser.parse_args()
    plan=json.loads(PLAN.read_text());spec=plan['order'][args.ordinal];directory=ROOT/plan['run_dir']/spec['name'];run=directory.parent
    if spec['arm'] not in ['C0','C1']:raise SystemExit('H accuracy requires the separate numerical-reference extension; not certified by this C audit')
    terminal=json.loads((directory/'terminal.json').read_text())
    if terminal['status']!='complete' or not terminal['complete']:raise SystemExit('Noncomplete or correctness/retention/interruption trial excluded; review its prefix separately')
    dest=ROOT/'validation'/('inhibitory-recurrent-panel-'+spec['name']+'-active-review.json')
    if dest.exists():raise SystemExit('Preserve first active review execution')
    A=Audit();began=time.perf_counter();error=None;stats=dict(spikes=0,candidates=0,applied=0,reconstructed_selected_edges=0)
    try:
        report=json.loads((directory/'result.json').read_text());A.record(terminal['result']);ph=A.sha(PLAN)
        A.ck('complete_report_and_identity',report['complete'] and report['status']=='complete' and not report['errors'] and all(report[k]==spec[k] for k in ['ordinal','name','arm','seed','condition']))
        A.ck('completed_clocks',all(report[k]==30000 for k in ['completed_tick','last_durable_chunk_end_tick','confirmed_prefix_end_tick','counts_end_tick','last_complete_checkpoint_tick']))
        for p,r in plan['sources'].items():A.ck('frozen_source',A.sha(ROOT/p)==r['sha256'] and (ROOT/p).stat().st_size==r['bytes'],p)
        for r in report['artifacts']:A.record(r)
        selection=A.archive(run/'selection');stream=A.archive(run/f'input-seed{spec["seed"]}');selected=selection['selected'];inputs=selection['inputs'];targets=selection['targets'];cohorts=selection['cohorts']
        u,rng=stream['uniforms'],stream['logical_rng_boundaries'];n=plan['neurons'];ns=len(selected)
        A.ck('fixed_shapes',len(inputs)==36 and ns==48 and u.shape==(30000,36) and rng.shape==(30001,))
        graph=ROOT/'data/processed/malecns_v1';ptr=np.load(graph/'indptr.npy',mmap_mode='r');destinations=np.load(graph/'targets.npy',mmap_mode='r');weights=np.load(graph/'weights.npy',mmap_mode='r')
        columns=np.full(n,-1,np.int32);columns[selected]=np.arange(ns,dtype=np.int32)
        edge_parts=[]
        for start in range(0,len(destinations),1000000):edge_parts.append(start+np.flatnonzero(columns[destinations[start:start+1000000]]>=0))
        edges=np.concatenate(edge_parts).astype(np.int64);source=np.searchsorted(ptr,edges,side='right')-1
        filtered_ptr=np.r_[0,np.cumsum(np.bincount(source,minlength=n))];interesting=np.diff(filtered_ptr)>0
        edge_cols=columns[destinations[edges]]
        counts=np.zeros((7,n),np.int64);last=np.full(n,-(2**60),np.int64);tail_i=np.empty(0,np.int32);tail_t=np.empty(0,np.int64)
        rfc=np.full(n,22,np.int64);rfc[inputs]=0;blocked=np.zeros(n,bool)
        if spec['condition'].endswith('source_outputs_blocked'):blocked[inputs]=True
        initial=A.archive(directory/'checkpoint-00000');prior={k:initial[k][selected].copy() for k in ['v','s','h']};sel_last=last[selected].copy()
        cp_prefix=None;old=None;cursor=0
        if spec['arm']=='C0':
            old_spec=next(t for t in plan['old_trials'] if t['seed']==spec['seed'] and t['condition']==spec['condition'])
            with np.load(ROOT/old_spec['run_dir']/'trace.npz',allow_pickle=False) as z:old={k:z[k] for k in z.files}
            samples=[json.loads(s) for s in (ROOT/old_spec['run_dir']/'samples.jsonl').read_text().splitlines()]
        source_cols=np.full(n,-1,np.int32);source_cols[inputs]=np.arange(36)
        aa=float(np.exp(-.1/20.));bb=float(np.exp(-.1/5.));cc=5./15.*(aa-bb);package=int(spec['arm'][1]);boundaries=np.array(plan['window_edges_ticks'])
        def checkpoint(tick,cp=None):
            cp=A.archive(directory/f'checkpoint-{tick:05d}') if cp is None else cp
            A.ck('checkpoint_identity',cp['tick']==tick and cp['time_ms']==tick*.1 and cp['coherent_state'] and cp['graph_sha256']==plan['graph_sha256'] and cp['arm']==spec['arm'] and cp['seed']==spec['seed'] and cp['logical_rng_state']==int(rng[tick]) and cp['confirmed_prefix_end_tick']==tick and cp['last_durable_chunk_end_tick']==tick,tick)
            A.ck('checkpoint_membership',exact(cp['input_indices'],inputs) and exact(cp['selected_indices'],selected) and exact(cp['refractory'],rfc) and exact(cp['blocked'],blocked),tick)
            slots=(tail_t+18)%19;pending=np.concatenate([tail_i[slots==s] for s in range(19)]);pc=np.bincount(slots,minlength=19).astype(np.int64)
            A.ck('checkpoint_own_history',exact(cp['last'],last) and exact(cp['pending_count'],pc) and exact(cp['pending'],pending),tick)
            A.ck('checkpoint_counts',exact(cp['window_counts_observed'],counts),tick)
            A.ck('checkpoint_selected_state',all(exact(cp[k][selected],prior[k]) for k in ['v','s','h']),tick)
            A.ck('checkpoint_finite_C_state',all(cp[k].dtype==np.float64 and cp[k].shape==(n,) and np.isfinite(cp[k]).all() for k in ['v','s','h']) and not cp['h'].any(),tick)
            return cp
        checkpoint(0,initial)
        for chunk in range(600):
            start=50*chunk;end=start+50;o=A.archive(directory/f'chunk-{chunk:04d}');ii,tt=o['spike_indices'],o['spike_ticks'];d=o['per_tick'];tele=o['panel_telemetry']
            A.ck('chunk_clock',o['start_tick']==start and o['end_tick']==end and o['completed_ticks']==o['requested_ticks']==50 and o['status']=='complete' and o['coherent_state'] and o['partial'] is None and o['failure'] is None,chunk)
            A.ck('ordered_raw_spikes',ii.dtype==np.int32 and tt.dtype==np.int64 and ii.shape==tt.shape and np.all((tt>=start)&(tt<end)) and np.all((ii>=0)&(ii<n)) and (len(ii)<2 or np.all((tt[1:]>tt[:-1])|((tt[1:]==tt[:-1])&(ii[1:]>ii[:-1])))),chunk)
            order=np.argsort(ii,kind='stable');si,st=ii[order],tt[order];same=si[1:]==si[:-1];first=np.r_[True,~same] if len(si) else np.zeros(0,bool)
            A.ck('global_refractory_from_own_spikes',np.all(st[1:][same]-st[:-1][same]>=rfc[si[1:][same]]) and np.all(st[first]-last[si[first]]>=rfc[si[first]]),chunk)
            rate=plan['condition_rates_hz'][spec['condition']][np.searchsorted([5000,10000,15000],start,side='right')];candidate=u[start:end]<(np.full(36,rate)*.1/1000.);applied=candidate.copy();isource=source_cols[ii]>=0;applied[tt[isource]-start,source_cols[ii[isource]]]=False
            A.ck('direct_input_masks',exact(candidate,o['candidate']) and exact(applied,o['applied']),chunk)
            A.ck('rng_and_rate',tele['rate_hz']==rate and tele['logical_rng_before']==int(rng[start]) and tele['logical_rng_completed_prefix']==int(rng[end]),chunk)
            A.ck('selected_shapes_and_continuity',all(o['selected_'+k].shape==(51,48) and exact(o['selected_'+k][0],prior[k]) for k in ['v','s','h']),chunk)
            fire=np.zeros((50,ns),bool);selected_spike=columns[ii]>=0;fire[tt[selected_spike]-start,columns[ii[selected_spike]]]=True
            avail=np.zeros((50,ns),bool)
            for k in range(50):avail[k]=start+k-sel_last>=rfc[selected];sel_last[fire[k]]=start+k
            direct=avail&~fire
            A.ck('selected_eligibility_from_own_history',exact(avail,o['selected_available']) and exact(fire,o['selected_fired']) and exact(direct,o['selected_direct_available']) and exact(direct,o['selected_delivery_available']) and exact(np.ones_like(direct) if package else direct,o['selected_synaptic_available']),chunk)
            before=o['selected_v'][:-1];old_s=o['selected_s'][:-1];pre=before.copy();pre[avail]=-52.+(before[avail]+52.)*aa+old_s[avail]*cc+0.*(1.-aa)
            if package:pre[~avail]=-52.
            A.ck('C_prethreshold_bitwise',exact(pre,o['selected_prethreshold_v']),chunk)
            A.ck('strict_threshold_from_prestate',exact((pre>-45.)&avail,fire),chunk)
            post=pre.copy()
            for col,target in enumerate(inputs):post[:,columns[target]]+=applied[:,col]*68.75
            post[fire]=-52.
            A.ck('direct_and_reset_voltage_bitwise',exact(post,o['selected_v'][1:]),chunk)
            all_i=np.concatenate([tail_i,ii]);all_t=np.concatenate([tail_t,tt]);arrive=all_t+18;deliver=(arrive>=start)&(arrive<end);di,dt=all_i[deliver],arrive[deliver]-start
            event_indices=selected if any(a<=start<b for a,b in plan['audit_ranges_ticks']) else targets;event_mask=np.zeros(n,bool);event_mask[event_indices]=True
            expected_events=[];accepted=[[] for _ in range(50)]
            for src,k in zip(di[interesting[di]],dt[interesting[di]]):
                for pos in range(filtered_ptr[src],filtered_ptr[src+1]):
                    edge=int(edges[pos]);target=int(destinations[edge]);col=int(edge_cols[pos]);disposition=2 if blocked[src] else (0 if package or direct[k,col] else 1)
                    if disposition==0:accepted[k].append((col,float(weights[edge])))
                    if event_mask[target]:expected_events.append((start+int(k),int(src),edge,target,disposition))
            expected_events=np.asarray(expected_events,np.int64).reshape(-1,5)
            A.ck('selected_event_order_and_disposition',exact(expected_events,o['selected_events']),chunk)
            pred=prior['s'].copy();syn=np.empty((50,ns))
            for k in range(50):
                if package:pred*=bb
                else:pred[avail[k]]*=bb
                for col,w in accepted[k]:pred[col]+=w
                if not package:pred[fire[k]]=0.
                syn[k]=pred
            A.ck('selected_synapse_bitwise',exact(syn,o['selected_s'][1:]) and not o['selected_h'].any(),chunk)
            A.ck('global_edge_partition',exact(d['edge_counts'][:,0],d['edge_counts'][:,1]+d['edge_counts'][:,2]),chunk)
            # Full visited-edge counts follow raw delayed sources without visiting each edge.
            visits=np.zeros(50,np.int64);np.add.at(visits,dt[~blocked[di]],np.diff(ptr)[di[~blocked[di]]]);A.ck('global_edge_visits_from_spikes',exact(visits,d['edge_counts'][:,0,:].sum(axis=1)),chunk)
            A.ck('global_finite_phase_and_checks',not d['phase_nonfinite_count'].any() and not d['state_invalid_count'].any() and np.all(d['phase_reached']==5) and all(o['panel_checks'].values()) and o['panel_reference_checks']==[] and not o['reference_intervals']['found'].any(),chunk)
            A.ck('event_population_metadata',exact(tele['event_indices'],event_indices) and o['schema']['event_graph_indices']==event_indices.tolist(),chunk)
            A.ck('histogram_population_sums',all(int(tele[k+'_histogram'].sum())==n for k in ['voltage','synaptic','h']),chunk)
            A.ck('telemetry_counts',tele['spike_count']==len(ii) and tele['source_spikes']==int(isource.sum()) and tele['candidate_count']==int(candidate.sum()) and tele['applied_count']==int(applied.sum()) and all(tele['cohort_spikes'][name]==int(np.isin(ii,idx).sum()) for name,idx in cohorts.items()),chunk)
            if old is not None and end<=15000:
                stop=np.searchsorted(old['all_spike_ticks'],end,side='left');A.ck('old_C0_ordered_spikes',exact(ii,old['all_spike_graph_indices'][cursor:stop]) and exact(tt,old['all_spike_ticks'][cursor:stop]),chunk);cursor=int(stop)
                q=old['requested_arrival_ticks'];mask=(q>=start)&(q<end);ca=np.zeros_like(candidate);ap=np.zeros_like(applied);ca[q[mask]-start,old['requested_arrival_source_column'][mask]]=True;ap[q[mask]-start,old['requested_arrival_source_column'][mask]]=old['applied_direct_voltage_arrival'][mask]
                A.ck('old_C0_input_and_RNG',exact(candidate,ca) and exact(applied,ap) and samples[chunk]['rng_before']==int(rng[start]) and samples[chunk]['rng_after']==int(rng[end]),chunk)
            np.add.at(counts,(np.searchsorted(boundaries,tt,side='right')-1,ii),1);np.maximum.at(last,ii,tt)
            keep=all_t+18>=end;tail_i,tail_t=all_i[keep],all_t[keep];prior={k:o['selected_'+k][-1].copy() for k in ['v','s','h']}
            stats['spikes']+=len(ii);stats['candidates']+=int(candidate.sum());stats['applied']+=int(applied.sum());stats['reconstructed_selected_edges']+=len(expected_events)
            if end in plan['checkpoint_ticks']:
                cp=checkpoint(end)
                if end==15000:cp_prefix=cp
            if chunk%100==99:print(json.dumps(dict(chunks=chunk+1,spikes=stats['spikes'],failed=len(A.failures))),flush=True)
        wc=A.archive(directory/'window-counts');A.ck('raw_count_matrix',exact(counts,wc['observed_window_counts']) and wc['completed_tick']==wc['raw_archive_end_tick']==30000)
        for name,idx in cohorts.items():
            digest=hashlib.sha256(idx.astype('<i8').tobytes()).hexdigest();A.ck('cohort_order_hash',digest==report['summary']['cohort_index_sha256'][name],name)
            for w,row in enumerate(report['summary']['cohort_metrics'][name]):
                vals=counts[w,idx];total=int(vals.sum());duration=float((boundaries[w+1]-boundaries[w])*.0001);active=int(np.count_nonzero(vals));size=len(idx)
                A.ck('raw_cohort_metrics',row['complete'] and row['population_size']==size and row['observed_spikes']==row['spike_count']==total and row['recruited_cells']==active and row['population_rate_hz']==total/duration and row['mean_cell_rate_hz']==total/(duration*size) and row['active_fraction']==active/size,(name,w))
        A.ck('reported_totals',stats['spikes']==report['spike_count'] and stats['candidates']==report['candidate_count'] and stats['applied']==report['applied_count'])
        if old is not None:
            gate=json.loads((directory/'c0-prefix-gate.json').read_text());A.ck('durable_C0_gate',gate['passed'] and all(gate['checks'].values()) and gate['plan_sha256']==ph and gate['tick']==15000 and report['c0_prefix_passed']);A.record(gate['old_trace']);A.record(gate['checkpoint'])
            A.ck('old_C0_full_endpoints',exact(cp_prefix['v'],old['final_voltage_mv']) and exact(cp_prefix['s'],old['final_synaptic_mv']) and int(rng[15000])==int(old['final_rng_state'][0]) and cursor==len(old['all_spike_ticks']))
            A.ck('old_C0_all_cell_counts',exact(np.stack([counts[0]+counts[1],counts[2],counts[3]]),old['all_neuron_window_spike_counts']))
        A.ck('final_source_and_result_stable',A.sha(PLAN,False)==ph and A.sha(directory/'result.json',False)==terminal['result']['sha256'])
        stats['off_nonsource_counts']=[int(counts[w,cohorts['non_source']].sum()) for w in [4,5,6]];stats['off_source_counts']=[int(counts[w,inputs].sum()) for w in [4,5,6]];stats['forward_counts']=[int(counts[w,cohorts['motor:forward']].sum()) for w in range(7)]
    except Exception as exc:
        import traceback
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),trial=spec,plan_sha256=A.sha(PLAN),source_sha256={str(Path(__file__).relative_to(ROOT)):A.sha(Path(__file__)), 'scripts/review_inhibitory_recurrent_panel_trial.py':A.sha(ROOT/'scripts/review_inhibitory_recurrent_panel_trial.py')},terminal_sha256=A.sha(directory/'terminal.json'),result_sha256=A.sha(directory/'result.json'),passed=not A.failures and error is None,check_count=sum(c['checked'] for c in A.categories.values()),categories=A.categories,failures=A.failures,error=error,statistics=stats,decoded_archives=A.decoded_archives,decoded_arrays=A.decoded_arrays,wall_seconds=time.perf_counter()-began,scope='Completed C0/C1 saved-data verification only; no producer/kernel/metric helper imports or neural simulation',limits=['H intervals are explicitly outside this reviewer version.','Full global voltage trajectories between checkpoints are not independently reconstructed; selected48 voltage/synapse algebra is checked at every tick.','Global accepted/unavailable edge counts are checked as a partition; exact full-graph delivery visits and selected event dispositions are reconstructed.'])
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(path=str(dest),passed=result['passed'],checks=result['check_count'],failures=result['failures'],error=error,statistics=stats),indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
