#!/usr/bin/env python3
"""H0/H1 saved-data audit and independent fixed-interval references; no network execution."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,time,hashlib,math
import numpy as np
from review_inhibitory_recurrent_panel_trial import Audit,exact,ROOT,PLAN
from inhibitory_panel_reference_audit import evaluate


REFERENCE_COLUMNS = ['chunk','tick','graph_index','before_v_mv','p_mv','h','dt_ms','production_v_mv',
    'producer_quad_v_mv','producer_64_v_mv','producer_ode_v_mv','independent_quad_v_mv',
    'independent_quad_error_mv','independent_64_v_mv','independent_ode_v_mv',
    'production_quad_error_mv','production_64_error_mv','ode_quad_error_mv','threshold_margin_mv','timing_unresolved']


def reconstruct_h_states(initial_p,initial_h,available,fired,accepted,package,decay):
    """Selected synapse arithmetic from saved eligibility/events; no spikes generated."""
    p=initial_p.copy();h=initial_h.copy();ps=np.empty(available.shape);hs=np.empty(available.shape)
    for k in range(len(available)):
        if package:p*=decay;h*=decay
        else:p[available[k]]*=decay;h[available[k]]*=decay
        for col,w in accepted[k]:
            if w<0.:h[col]+=-w*(1./23.)
            else:p[col]+=w
        if not package:p[fired[k]]=0.;h[fired[k]]=0.
        ps[k]=p;hs[k]=h
    return ps,hs


def audit_references(A,o,selected,targets,cache,rows,tolerances,chunk,n):
    raw=o['reference_intervals'];expected={};names=['global:'+str(k) for k in range(3)]
    def add(key,state,label):
        if key in expected:
            A.ck('reference_duplicate_exact_state',exact(expected[key]['state'],state),(chunk,key))
            expected[key]['labels'].append(label)
        else:expected[key]=dict(state=state,labels=[label])
    for k in range(3):
        if raw['found'][k]:
            key=(int(raw['ticks'][k]),int(raw['graph_indices'][k]));v=raw['values'][k]
            A.ck('reference_completed_interval_domain',o['start_tick']<=key[0]<o['end_tick'] and 0<=key[1]<n and np.isfinite(v[:11]).all() and v[1]>=0 and v[2]>=0,(chunk,k))
            A.ck('reference_record_margin_stiffness',v[5]==abs(v[4]+45.) and v[6]==(1.+v[2])*.1/20. and v[3]==.1,(chunk,k))
            add(key,v[:5].copy(),names[k])
            positions=np.flatnonzero(selected==key[1])
            if len(positions):
                j=int(positions[0]);t=key[0]-o['start_tick'];state=np.array([o['selected_v'][t,j],o['selected_s'][t,j],o['selected_h'][t,j],.1,o['selected_prethreshold_v'][t,j]])
                A.ck('global_reference_selected_precedent',o['selected_available'][t,j] and exact(v[:5],state),(chunk,k))
    available=o['selected_available'];h=o['selected_h'][:-1];p=o['selected_s'][:-1]
    if available.any():
        A.ck('global_max_h_dominates_selected',raw['found'][0] and raw['values'][0,2]>=h[available].max(),chunk)
        A.ck('global_nearest_threshold_dominates_selected',raw['found'][1] and raw['values'][1,5]<=np.abs(o['selected_prethreshold_v'][available]+45.).min(),chunk)
    ratio_mask=available&(h>0)
    if ratio_mask.any():
        rr=np.full(int(ratio_mask.sum()),-np.inf);pp=p[ratio_mask];hh=h[ratio_mask];positive=pp>0;rr[positive]=np.log(pp[positive])-np.log(hh[positive])
        A.ck('global_log_ratio_dominates_selected',raw['found'][2] and raw['values'][2,11]>=rr.max()-1e-12,chunk)
    if raw['found'][2]:
        value=raw['values'][2];lr=math.log(float(value[1]))-math.log(float(value[2])) if value[1]>0 else -np.inf
        A.ck('global_log_ratio_reconstruction',value[2]>0 and (lr==value[11] or (np.isfinite(lr) and abs(lr-value[11])<=1e-12)),chunk)
    for target in targets:
        j=int(np.flatnonzero(selected==target)[0]);found=np.flatnonzero(available[:,j])
        if len(found):
            t=int(found[0]);key=(o['start_tick']+t,int(target));state=np.array([o['selected_v'][t,j],o['selected_s'][t,j],o['selected_h'][t,j],.1,o['selected_prethreshold_v'][t,j]])
            add(key,state,'target_first_available')
    saved=o['panel_reference_checks']
    if not A.ck('exact_reference_selection_population',[(r['tick'],r['index']) for r in saved]==list(expected),chunk):raise ValueError('Saved reference population differs')
    A.ck('no_partial_references_in_complete_chunk',raw['partial'] is None,chunk)
    for r in saved:
        key=(r['tick'],r['index']);state=expected[key]['state'];recorded=np.array([r['v'],r['p'],r['h'],r['dt'],r['production_v']])
        A.ck('saved_reference_exact_precedent',exact(state,recorded) and r['selection']==expected[key]['labels'],(chunk,key))
        A.ck('saved_reference_success',r['passed'] and r.get('method_in_progress') is None and 'error' not in r and not r.get('not_attempted_after_failure',False),(chunk,key))
        pq=abs(state[4]-r['quad_v']);p64=abs(state[4]-r['order64_v']);oq=abs(r['ode_v']-r['quad_v']);margin=abs(state[4]+45.)
        A.ck('producer_reference_error_arithmetic',pq==r['production_quad_error'] and p64==r['production_order64_error'] and oq==r['ode_quad_error'] and margin==r['threshold_margin_mv'] and r['margin_within_observed_reference_error']==(margin<=max(pq,p64,oq)),(chunk,key))
        A.ck('producer_reference_frozen_gates',pq<=tolerances['production_vs_quad'] and p64<=tolerances['order32_vs64'] and oq<=tolerances['ode_vs_quad'] and r['quad_error_estimate']<=tolerances['quad_error_estimate'],(chunk,key))
        numeric_key=tuple(float(x) for x in state[:4])
        A.current_reference=dict(chunk=chunk,tick=key[0],index=key[1],inputs=list(numeric_key),completed_rows=len(rows),status='evaluating' if numeric_key not in cache else 'cached')
        if numeric_key not in cache:
            try:cache[numeric_key]=evaluate(*numeric_key)
            except (Exception,KeyboardInterrupt) as exc:
                A.current_reference.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error_type=type(exc).__name__,error=str(exc),helper_record=getattr(exc,'record',None),method_limit='A bare interruption does not expose the helper method or its unfinished local partial values.')
                A.ck('independent_reference_evaluation',False,A.current_reference.copy())
                raise
        q=cache[numeric_key];error_quad=abs(state[4]-q['quad_v']);error64=abs(state[4]-q['order64_v']);error_ode=abs(q['ode_v']-q['quad_v'])
        good=bool(np.isfinite([q['quad_v'],q['quad_error_estimate'],q['order64_v'],q['ode_v']]).all() and error_quad<=tolerances['production_vs_quad'] and error64<=tolerances['order32_vs64'] and error_ode<=tolerances['ode_vs_quad'] and q['quad_error_estimate']<=tolerances['quad_error_estimate'])
        unresolved=margin<=max(error_quad,error64,error_ode)
        rows.append([chunk,key[0],key[1],*state[:4],state[4],r['quad_v'],r['order64_v'],r['ode_v'],q['quad_v'],q['quad_error_estimate'],q['order64_v'],q['ode_v'],error_quad,error64,error_ode,margin,int(unresolved)])
        A.current_reference['status']='completed' if good else 'accuracy_gate_failed'
        if not A.ck('independent_reference_frozen_gates',good,(chunk,key)):raise ValueError('Independent reference accuracy gate failed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ordinal',type=int,default=16);args=parser.parse_args()
    plan=json.loads(PLAN.read_text());spec=plan['order'][args.ordinal];directory=ROOT/plan['run_dir']/spec['name'];run=directory.parent
    if spec['arm'] not in ['H0','H1']:raise SystemExit('This separate reviewer covers completed H0/H1 trials only')
    terminal=json.loads((directory/'terminal.json').read_text())
    if terminal['status']!='complete' or not terminal['complete']:raise SystemExit('Noncomplete or correctness/retention/interruption trial excluded; review its prefix separately')
    dest=ROOT/'validation'/('inhibitory-recurrent-panel-'+spec['name']+'-H-review.json')
    if dest.exists() or dest.with_name(dest.stem+'-references.npz').exists():raise SystemExit('Preserve first H review execution and reference artifacts')
    A=Audit();began=time.perf_counter();error=None;reference_rows=[];reference_cache={};stats=dict(spikes=0,candidates=0,applied=0,reconstructed_selected_edges=0,fully_audited_chunks=0)
    review_sources={}
    try:
        review_paths=[Path(__file__),ROOT/'scripts/review_inhibitory_recurrent_panel_trial.py',ROOT/'scripts/inhibitory_panel_reference_audit.py',ROOT/'validation/inhibitory-panel-reference-audit-results.json']
        review_sources={str(p.relative_to(ROOT)):A.sha(p,False) for p in review_paths}
        helper_validation=json.loads(review_paths[-1].read_text());helper_name='scripts/inhibitory_panel_reference_audit.py'
        helper_ok=(helper_validation['passed'] and helper_validation['complete'] and helper_validation['source_sha256'][helper_name]==review_sources[helper_name]=='2a20ac9ed6b5dfd312b7f7aeb83028920c403f8972374213d731fcafddbea743' and review_sources[str(review_paths[-1].relative_to(ROOT))]=='4985dac16fe3192c6e703cafa3aaf42ab4251c75a5952baef8b65aeb950abafd')
        if not A.ck('validated_independent_helper_source',helper_ok):raise ValueError('Independent helper validation/source mismatch')
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
            A.ck('checkpoint_finite_H_state',all(cp[k].dtype==np.float64 and cp[k].shape==(n,) and np.isfinite(cp[k]).all() for k in ['v','s','h']) and np.all(cp['v']>=-75.-1e-10) and np.all(cp['s']>=0) and np.all(cp['h']>=0),tick)
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
            before=o['selected_v'][:-1];pre=o['selected_prethreshold_v']
            held=np.full_like(before[~avail],-52.) if package else before[~avail]
            A.ck('H_unavailable_voltage_hold',exact(pre[~avail],held),chunk)
            A.ck('H_selected_lower_bound',np.all(pre>=-75.-1e-10) and np.all(o['selected_v']>=-75.-1e-10),chunk)
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
            syn,conductance=reconstruct_h_states(prior['s'],prior['h'],avail,fire,accepted,package,bb)
            A.ck('selected_synapse_conductance_bitwise',exact(syn,o['selected_s'][1:]) and exact(conductance,o['selected_h'][1:]),chunk)
            A.ck('global_edge_partition',exact(d['edge_counts'][:,0],d['edge_counts'][:,1]+d['edge_counts'][:,2]),chunk)
            # Full visited-edge counts follow raw delayed sources without visiting each edge.
            visits=np.zeros(50,np.int64);np.add.at(visits,dt[~blocked[di]],np.diff(ptr)[di[~blocked[di]]]);A.ck('global_edge_visits_from_spikes',exact(visits,d['edge_counts'][:,0,:].sum(axis=1)),chunk)
            A.ck('global_finite_phase_and_checks',not d['phase_nonfinite_count'].any() and not d['state_invalid_count'].any() and np.all(d['phase_reached']==5) and all(o['panel_checks'].values()) and not d['phase_below_reversal_count'].any(),chunk)
            audit_references(A,o,selected,targets,reference_cache,reference_rows,plan['tolerances_mv'],chunk,n)
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
            stats['fully_audited_chunks']=chunk+1
            if chunk%100==99:print(json.dumps(dict(chunks=chunk+1,spikes=stats['spikes'],failed=len(A.failures))),flush=True)
        wc=A.archive(directory/'window-counts');A.ck('raw_count_matrix',exact(counts,wc['observed_window_counts']) and wc['completed_tick']==wc['raw_archive_end_tick']==30000)
        for name,idx in cohorts.items():
            digest=hashlib.sha256(idx.astype('<i8').tobytes()).hexdigest();A.ck('cohort_order_hash',digest==report['summary']['cohort_index_sha256'][name],name)
            for w,row in enumerate(report['summary']['cohort_metrics'][name]):
                vals=counts[w,idx];total=int(vals.sum());duration=float((boundaries[w+1]-boundaries[w])*.0001);active=int(np.count_nonzero(vals));size=len(idx)
                A.ck('raw_cohort_metrics',row['complete'] and row['population_size']==size and row['observed_spikes']==row['spike_count']==total and row['recruited_cells']==active and row['population_rate_hz']==total/duration and row['mean_cell_rate_hz']==total/(duration*size) and row['active_fraction']==active/size,(name,w))
        A.ck('saved_reference_count',len(reference_rows)==report['reference_intervals'])
        A.ck('reported_totals',stats['spikes']==report['spike_count'] and stats['candidates']==report['candidate_count'] and stats['applied']==report['applied_count'])
        if old is not None:
            gate=json.loads((directory/'c0-prefix-gate.json').read_text());A.ck('durable_C0_gate',gate['passed'] and all(gate['checks'].values()) and gate['plan_sha256']==ph and gate['tick']==15000 and report['c0_prefix_passed']);A.record(gate['old_trace']);A.record(gate['checkpoint'])
            A.ck('old_C0_full_endpoints',exact(cp_prefix['v'],old['final_voltage_mv']) and exact(cp_prefix['s'],old['final_synaptic_mv']) and int(rng[15000])==int(old['final_rng_state'][0]) and cursor==len(old['all_spike_ticks']))
            A.ck('old_C0_all_cell_counts',exact(np.stack([counts[0]+counts[1],counts[2],counts[3]]),old['all_neuron_window_spike_counts']))
        A.ck('final_source_and_result_stable',A.sha(PLAN,False)==ph and A.sha(directory/'result.json',False)==terminal['result']['sha256'])
        stats['reference_intervals']=len(reference_rows);stats['unique_reference_inputs']=len(reference_cache);stats['independent_threshold_unresolved']=sum(int(row[-1]) for row in reference_rows)
        stats['off_nonsource_counts']=[int(counts[w,cohorts['non_source']].sum()) for w in [4,5,6]];stats['off_source_counts']=[int(counts[w,inputs].sum()) for w in [4,5,6]];stats['forward_counts']=[int(counts[w,cohorts['motor:forward']].sum()) for w in range(7)]
    except (Exception,KeyboardInterrupt) as exc:
        import traceback
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    review_sources_final={p:A.sha(ROOT/p,False) for p in review_sources}
    A.ck('reviewer_dependencies_unchanged',review_sources_final==review_sources)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),trial=spec,plan_sha256=A.sha(PLAN),source_sha256=review_sources,final_source_sha256=review_sources_final,terminal_sha256=A.sha(directory/'terminal.json'),result_sha256=A.sha(directory/'result.json'),passed=not A.failures and error is None,check_count=sum(c['checked'] for c in A.categories.values()),categories=A.categories,failures=A.failures,error=error,statistics=stats,decoded_archives=A.decoded_archives,decoded_arrays=A.decoded_arrays,wall_seconds=time.perf_counter()-began,scope='Completed H0/H1 saved-data verification and independent selected fixed-interval scalar references; no neural simulation or producer/kernel/metric helper imports',limits=['Full global voltage trajectories between checkpoints are not reconstructed. Selected48 p/h and direct/reset algebra are checked at every tick; independent H integration is limited to the predeclared saved reference intervals.','Global winner optimality over unselected cells is not independently reconstructible without an all-cell time cube; selected-population dominance and saved state/selection identity are checked.','Global accepted/unavailable edge totals are checked as a partition; exact full-graph delivery visits and selected event dispositions are reconstructed.','Numerical accuracy and the lower bound do not establish physiology, seed robustness, or H1 promotion.'])
    reference_path=dest.with_name(dest.stem+'-references.npz')
    np.savez_compressed(reference_path,values=np.asarray(reference_rows,np.float64).reshape(-1,len(REFERENCE_COLUMNS)))
    result['reference_evaluation_state']=getattr(A,'current_reference',None)
    result['completed_unique_reference_evaluations']=[dict(inputs=list(k),result=v) for k,v in reference_cache.items()]
    result['independent_references']=dict(records=len(reference_rows),unique_saved_inputs=len(reference_cache),columns=REFERENCE_COLUMNS,artifact=dict(path=str(reference_path.relative_to(ROOT)),bytes=reference_path.stat().st_size,sha256=A.sha(reference_path)))
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(path=str(dest),passed=result['passed'],checks=result['check_count'],failures=result['failures'],error=error,statistics=stats),indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
