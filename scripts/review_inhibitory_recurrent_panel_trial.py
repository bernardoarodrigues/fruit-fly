#!/usr/bin/env python3
"""Independent saved-data audit. No producer, kernel or simulator imports."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/inhibitory-recurrent-panel-plan.json'

class Audit:
    def __init__(self):self.categories={};self.failures=[];self.hashed={};self.decoded_archives=0;self.decoded_arrays=0
    def ck(self,name,value,context=None):
        row=self.categories.setdefault(name,dict(checked=0,passed=0));row['checked']+=1;row['passed']+=int(bool(value))
        if not value:self.failures.append(dict(check=name,context=context))
        return bool(value)
    def sha(self,path,cache=True):
        path=Path(path)
        if cache and str(path) in self.hashed:return self.hashed[str(path)]
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
        value=h.hexdigest()
        if cache:self.hashed[str(path)]=value
        return value
    def record(self,r):
        path=ROOT/r['path'];return self.ck('artifact_hash_and_size',path.stat().st_size==r['bytes'] and self.sha(path)==r['sha256'],r['path'])
    def archive(self,stem):
        stem=Path(stem);npz=Path(str(stem)+'.npz');schema=Path(str(stem)+'.json');marker=Path(str(stem)+'.complete.json')
        incomplete=Path(str(stem)+'.publish.lock').exists() or bool(list(stem.parent.glob(stem.name+'.tmp-*'))) or bool(list(stem.parent.glob(stem.name+'.failure-*')))
        if not self.ck('archive_no_incomplete_evidence',not incomplete,str(stem)):raise ValueError('Incomplete archive')
        head=json.loads(schema.read_text());complete=json.loads(marker.read_text())
        valid=(complete.get('format')=='inhibitory-recurrent-panel-completion' and complete.get('version')==1 and complete.get('complete') is True and head.get('format')=='inhibitory-recurrent-panel' and head.get('version')==1 and head.get('transaction')==complete.get('transaction'))
        if not self.ck('archive_header_transaction',valid,str(stem)):raise ValueError('Bad archive header')
        expected=[str(npz.relative_to(ROOT)),str(schema.relative_to(ROOT))]
        if not self.ck('archive_marker_payload_paths',[r['path'] for r in complete['artifacts']]==expected,str(stem)):raise ValueError('Wrong payload paths')
        if not all(self.record(r) for r in complete['artifacts']):raise ValueError('Archive checksum mismatch')
        with np.load(npz,allow_pickle=False) as z:
            if len(set(z.files))!=len(z.files):raise ValueError('Duplicate payload names')
            arrays={k:z[k] for k in z.files}
        used=set()
        def array(desc):
            key=desc['key'];a=arrays[key]
            if key in used:raise ValueError('Duplicate array reference')
            used.add(key)
            valid=(list(a.shape)==desc['shape'] and a.itemsize==desc['itemsize'] and a.size==desc['count'] and a.nbytes==desc['bytes'] and json.loads(json.dumps(np.lib.format.dtype_to_descr(a.dtype)))==desc['dtype'] and hashlib.sha256(a.tobytes(order='C')).hexdigest()==desc['sha256'] and not a.dtype.hasobject)
            if not self.ck('array_descriptor_and_bytes',valid,str(stem)+':'+key):raise ValueError('Array descriptor mismatch')
            self.decoded_arrays+=1;return a
        def decode(node):
            k=node['kind']
            if k in ['array','numpy_scalar']:
                a=array(node['array']);return a[()] if k=='numpy_scalar' else a
            if k=='scalar':return node['value']
            if k=='nonfinite':return {'nan':float('nan'),'positive_infinity':float('inf'),'negative_infinity':-float('inf')}[node['nonfinite']]
            if k in ['list','tuple']:
                items=[decode(v) for v in node['items']];return tuple(items) if k=='tuple' else items
            if k=='dict':
                components={}
                if 'spikes' in node:
                    packed=array(node['spikes']['array']);h=node['spikes']['header']
                    valid=(packed.dtype.descr==[('tick','<i8'),('index','<i4')] and packed.itemsize==12 and packed.ndim==1 and h['version']==1 and h['count']==len(packed) and h['shape']==list(packed.shape) and h['dtype']==[['tick','<i8'],['index','<i4']] and h['itemsize']==12 and h['sha256']==hashlib.sha256(packed.tobytes()).hexdigest())
                    if not self.ck('packed_spike_header',valid,str(stem)):raise ValueError('Bad packed spikes')
                    for f in ['tick','index']:
                        original=packed[f].astype(np.dtype(h['original_'+f+'_dtype']))
                        if not self.ck('packed_spike_original_bytes',np.array_equal(original,packed[f]) and hashlib.sha256(original.tobytes()).hexdigest()==h['original_'+f+'_sha256'],str(stem)+':'+f):raise ValueError('Spike reconstruction mismatch')
                        components[f]=original
                value={}
                for key,child in node['items']:
                    if key in value:raise ValueError('Duplicate dict key')
                    value[key]=components[child['component']] if child['kind']=='spike_component' else decode(child)
                return value
            raise ValueError('Unknown archive node')
        result=decode(head['tree'])
        self.ck('all_payload_arrays_referenced',used==set(arrays),str(stem));self.decoded_archives+=1
        return result

def exact(a,b):return isinstance(a,np.ndarray) and isinstance(b,np.ndarray) and a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,default=PLAN);parser.add_argument('--ordinal',type=int,default=0);args=parser.parse_args()
    if not args.plan.exists():raise SystemExit('Awaiting actual frozen plan; no audit result written')
    plan=json.loads(args.plan.read_text());spec=plan['order'][args.ordinal];run=ROOT/plan['run_dir'];directory=run/spec['name']
    if spec['arm']!='C0' or spec['condition']!='no_input':raise SystemExit('This bounded audit currently covers C0 no-input only')
    if not (directory/'terminal.json').exists():raise SystemExit('Awaiting authoritative terminal receipt; incomplete trials are not certified')
    terminal=json.loads((directory/'terminal.json').read_text());report=json.loads((directory/'result.json').read_text())
    if terminal['status']!='complete' or terminal['complete'] is not True:raise SystemExit('Trial is not scientifically complete; preserve its actual status and review failure separately')
    output=ROOT/'validation'/('inhibitory-recurrent-panel-'+spec['name']+'-independent-review.json')
    if output.exists():raise SystemExit('Refusing to overwrite completed audit')
    audit=Audit();began=time.perf_counter();error=None
    try:
        plan_hash=audit.sha(args.plan)
        audit.record(terminal['result'])
        audit.ck('report_complete',report['status']=='complete' and report['complete'] and not report['errors'])
        audit.ck('report_trial_identity',all(report[k]==spec[k] for k in ['ordinal','name','arm','seed','condition']))
        audit.ck('completed_clocks',all(report[k]==30000 for k in ['completed_tick','last_durable_chunk_end_tick','last_complete_checkpoint_tick','confirmed_prefix_end_tick','counts_end_tick']))
        for path,r in plan['sources'].items():audit.ck('frozen_source_hash',audit.sha(ROOT/path)==r['sha256'] and (ROOT/path).stat().st_size==r['bytes'],path)
        for r in report['artifacts']:audit.record(r)
        audit.ck('no_failure_files',not list(directory.glob('*failure*')) and not list(directory.glob('*.publish.lock')) and not list(directory.glob('*.tmp-*')))
        selection=audit.archive(run/'selection');stream=audit.archive(run/f'input-seed{spec["seed"]}')
        inputs,selected,targets=selection['inputs'],selection['selected'],selection['targets'];u=stream['uniforms'];rng=stream['logical_rng_boundaries']
        audit.ck('input_shapes_and_domain',u.shape==(30000,36) and rng.shape==(30001,) and len(inputs)==36 and len(selected)==48 and np.isfinite(u).all() and np.all((u>=0)&(u<1)))
        n=plan['neurons'];counts=np.zeros((7,n),np.int64);last=np.full(n,-(2**60),np.int64);tail_i=np.empty(0,np.int32);tail_t=np.empty(0,np.int64)
        initial=audit.archive(directory/'checkpoint-00000');prior=None;totals=dict(spikes=0,candidates=0,applied=0,references=0)
        expected_rfc=np.full(n,22,np.int64);expected_rfc[inputs]=0
        def checkpoint(tick):
            cp=initial if tick==0 else audit.archive(directory/f'checkpoint-{tick:05d}')
            audit.ck('checkpoint_clock_identity',cp['tick']==tick and cp['time_ms']==tick*.1 and cp['coherent_state'] and cp['arm']==spec['arm'] and cp['seed']==spec['seed'] and cp['graph_sha256']==plan['graph_sha256'] and cp['logical_rng_state']==int(rng[tick]) and cp['confirmed_prefix_end_tick']==tick and cp['last_durable_chunk_end_tick']==tick,tick)
            audit.ck('checkpoint_fixed_membership',exact(cp['input_indices'],inputs) and exact(cp['selected_indices'],selected) and exact(cp['refractory'],expected_rfc) and not cp['blocked'].any(),tick)
            slots=(tail_t+18)%19;pc=np.bincount(slots,minlength=19).astype(np.int64);pending=np.concatenate([tail_i[slots==s] for s in range(19)])
            audit.ck('checkpoint_own_spike_history',exact(cp['last'],last) and exact(cp['pending_count'],pc) and exact(cp['pending'],pending),tick)
            audit.ck('checkpoint_raw_counts',exact(cp['window_counts_observed'],counts),tick)
            audit.ck('checkpoint_quiet_full_state',all(cp[k].shape==(n,) and cp[k].dtype==np.float64 for k in ['v','s','h']) and np.all(cp['v']==-52.) and np.all(cp['s']==0) and np.all(cp['h']==0),tick)
            for key in ['v','s','h','last','refractory','blocked','pending_count','pending']:
                audit.ck('checkpoint_matches_initial_'+key,exact(cp[key],initial[key]),tick)
            if prior is not None:audit.ck('checkpoint_selected_matches_raw',all(exact(cp[k][selected],prior[k]) for k in ['v','s','h']),tick)
            return cp
        checkpoint(0);prefix=None
        for chunk in range(600):
            start=chunk*50;end=start+50;out=audit.archive(directory/f'chunk-{chunk:04d}')
            audit.ck('chunk_complete_clock',out['status']=='complete' and out['coherent_state'] and out['failure'] is None and out['partial'] is None and out['start_tick']==start and out['end_tick']==end and out['completed_ticks']==50 and out['requested_ticks']==50,chunk)
            ii,tt=out['spike_indices'],out['spike_ticks']
            audit.ck('raw_spike_dtype_order',ii.dtype==np.int32 and tt.dtype==np.int64 and ii.shape==tt.shape and np.all((tt>=start)&(tt<end)) and np.all((ii>=0)&(ii<n)) and (len(tt)<2 or np.all((tt[1:]>tt[:-1])|((tt[1:]==tt[:-1])&(ii[1:]>ii[:-1])))),chunk)
            wins=np.searchsorted(np.array(plan['window_edges_ticks']),tt,side='right')-1;np.add.at(counts,(wins,ii),1);np.maximum.at(last,ii,tt)
            tail_i=np.concatenate([tail_i,ii]);tail_t=np.concatenate([tail_t,tt]);keep=tail_t+18>=end;tail_i,tail_t=tail_i[keep],tail_t[keep]
            audit.ck('zero_input_no_events',not len(ii) and out['candidate'].shape==(50,36) and not out['candidate'].any() and not out['applied'].any() and out['selected_events'].shape==(0,5),chunk)
            audit.ck('selected_fixed_shapes',all(out['selected_'+k].shape==(51,48) for k in ['v','s','h']) and out['selected_prethreshold_v'].shape==(50,48),chunk)
            audit.ck('selected_quiet_state',np.all(out['selected_v']==-52.) and not out['selected_s'].any() and not out['selected_h'].any() and np.all(out['selected_prethreshold_v']==-52.),chunk)
            audit.ck('selected_masks',np.all(out['selected_available']) and not out['selected_fired'].any() and np.all(out['selected_direct_available']) and np.all(out['selected_synaptic_available']) and exact(out['selected_delivery_available'],out['selected_direct_available']),chunk)
            if prior is not None:audit.ck('selected_continuity',all(exact(out['selected_'+k][0],prior[k]) for k in ['v','s','h']),chunk)
            prior={k:out['selected_'+k][-1].copy() for k in ['v','s','h']}
            d=out['per_tick'];audit.ck('quiet_global_phase_diagnostics',np.all(d['phase_min_mv']==-52.) and np.all(d['phase_max_mv']==-52.) and not d['phase_min_index'].any() and not d['phase_max_index'].any() and not d['phase_nonfinite_count'].any() and not d['phase_below_reversal_count'].any() and not d['state_invalid_count'].any() and not d['edge_counts'].any() and np.all(d['phase_reached']==5),chunk)
            audit.ck('quiet_work_counts',np.all(d['work'][:,0]==n) and not d['work'][:,1:].any() and not d['solver'][:,:3].any() and np.all(d['solver'][:,3]==.005),chunk)
            telemetry=out['panel_telemetry'];audit.ck('input_rng_rate_telemetry',telemetry['rate_hz']==0 and telemetry['logical_rng_before']==int(rng[start]) and telemetry['logical_rng_completed_prefix']==int(rng[end]) and telemetry['spike_count']==telemetry['source_spikes']==telemetry['candidate_count']==telemetry['applied_count']==0 and all(v==0 for v in telemetry['cohort_spikes'].values()),chunk)
            events=selected if any(a<=start<b for a,b in plan['audit_ranges_ticks']) else targets
            audit.ck('event_audit_selection',exact(telemetry['event_indices'],events) and out['schema']['event_graph_indices']==events.tolist(),chunk)
            for key,state,edgeskey in [('voltage',-52.,'voltage_histogram_edges'),('synaptic',0.,'synaptic_histogram_edges'),('h',0.,'h_histogram_edges')]:
                edges=np.r_[-np.inf,plan[edgeskey],np.inf];hist=np.zeros(len(edges)-1,np.int64);hist[np.searchsorted(edges,state,side='right')-1]=n
                audit.ck('quiet_'+key+'_histogram',exact(telemetry[key+'_histogram'],hist),chunk)
            audit.ck('producer_chunk_gates_and_no_H_refs',all(out['panel_checks'].values()) and out['panel_reference_checks']==[] and not out['reference_intervals']['found'].any(),chunk)
            totals['spikes']+=len(ii);totals['candidates']+=int(out['candidate'].sum());totals['applied']+=int(out['applied'].sum());totals['references']+=len(out['panel_reference_checks'])
            if end in plan['checkpoint_ticks']:
                cp=checkpoint(end)
                if end==15000:prefix=cp
            if chunk%100==99:print(json.dumps(dict(audited_chunks=chunk+1,tick=end,failed_checks=len(audit.failures))),flush=True)
        wc=audit.archive(directory/'window-counts')
        audit.ck('window_counts_raw_reconstruction',exact(wc['observed_window_counts'],counts) and wc['completed_tick']==30000 and wc['raw_archive_end_tick']==30000)
        audit.ck('reported_totals',totals==dict(spikes=report['spike_count'],candidates=report['candidate_count'],applied=report['applied_count'],references=report['reference_intervals']))
        audit.ck('summary_windows_complete',report['summary']['completed_tick']==30000 and all(report['summary']['window_complete']) and report['summary']['complete_window_count']==7)
        for name,rows in report['summary']['cohort_metrics'].items():
            audit.ck('quiet_cohort_metrics',all(q['complete'] and q['observed_spikes']==q['spike_count']==q['recruited_cells']==0 and q['population_rate_hz']==q['mean_cell_rate_hz']==q['active_fraction']==0 for q in rows),name)
        gate=json.loads((directory/'c0-prefix-gate.json').read_text());audit.ck('durable_c0_gate',gate['passed'] and all(gate['checks'].values()) and gate['plan_sha256']==plan_hash and gate['tick']==15000 and gate['seed']==spec['seed'] and gate['condition']==spec['condition'] and report['c0_prefix_passed'])
        audit.record(gate['checkpoint']);audit.record(gate['old_trace'])
        with np.load(ROOT/gate['old_trace']['path'],allow_pickle=False) as z:
            audit.ck('old_C0_prefix_endpoints',exact(prefix['v'],z['final_voltage_mv']) and exact(prefix['s'],z['final_synaptic_mv']))
            audit.ck('old_C0_prefix_counts',exact(np.stack([counts[0]+counts[1],counts[2],counts[3]]),z['all_neuron_window_spike_counts']))
            audit.ck('old_C0_prefix_zero_stream',len(z['all_spike_ticks'])==len(z['all_spike_graph_indices'])==len(z['requested_arrival_ticks'])==0 and int(z['initial_rng_state'][0])==int(rng[0]) and int(z['final_rng_state'][0])==int(rng[15000]))
        audit.ck('terminal_result_still_unchanged',audit.sha(directory/'result.json',False)==terminal['result']['sha256'] and audit.sha(args.plan,False)==plan_hash)
    except Exception as exc:
        import traceback
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
    result=dict(schema=1,completed_utc=datetime.now(timezone.utc).isoformat(),trial=spec,plan_sha256=audit.sha(args.plan),
        source_sha256={str(Path(__file__).relative_to(ROOT)):audit.sha(Path(__file__))},
        terminal_sha256=audit.sha(directory/'terminal.json'),result_sha256=audit.sha(directory/'result.json'),
        passed=not audit.failures and error is None,check_count=sum(v['checked'] for v in audit.categories.values()),categories=audit.categories,failures=audit.failures,error=error,
        decoded_archives=audit.decoded_archives,decoded_arrays=audit.decoded_arrays,wall_seconds=time.perf_counter()-began,
        scope='All600 completed C0 no-input chunks and all complete boundary checkpoints; independent saved-file decoder and arithmetic only. No producer imports or neural execution.',
        limits=['Only the named completed no-input trial is certified.','Activity-bearing and H trials require additional reference/state audits and actual terminal status checks.','Hashes and completion markers establish saved-file consistency, not hardware power-loss behavior.','H reference ranking over unselected cells is a producer capture claim; without all-cell time cubes its global optimality cannot be independently reconstructed solely from saved traces.'])
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(output=str(output),passed=result['passed'],checks=result['check_count'],failures=result['failures'],error=error),indent=2))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
