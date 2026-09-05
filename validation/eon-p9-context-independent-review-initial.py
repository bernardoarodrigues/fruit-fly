"""Independent saved-data review. No producer/engine imports and no neural rerun."""
from pathlib import Path
import datetime,hashlib,json
import numpy as np
import pandas as pd
B=Path(__file__).resolve().parents[1]
P=B/'validation/eon-p9-context-plan.json';D=B/'validation/eon-p9-context'
OUT=B/'validation/eon-p9-context-independent-review.json'
if OUT.exists():raise FileExistsError(OUT)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def npz(p):
 with np.load(p,allow_pickle=False)as f:return {k:f[k]for k in f.files}
checks=[]
def check(name,passed,detail=None):
 checks.append({'name':name,'passed':bool(passed),**({'detail':detail}if detail is not None else {})})
def same(name,a,b):check(name,np.array_equal(a,b))
plan=json.loads(P.read_text());report=json.loads((D/'results.json').read_text())
check('result_plan_hash',report['plan_sha256']==sha(P))
check('complete_fixed_panel',report['complete'] and len(report['trials'])==12 and len(plan['condition_order'])==6 and plan['seeds']==[11,12])
for p,h in plan['source_sha256'].items():check('source_sha:'+p,sha(B/p)==h)
g=B/'data/processed/malecns_v1';ids=np.load(g/'neuron_ids.npy',mmap_mode='r');indptr=np.load(g/'indptr.npy',mmap_mode='r')
cells=pd.read_feather(g/'neurons.feather')
same('graph_metadata_row_ids',ids,cells.bodyId.to_numpy());check('graph_ids_strict_sorted',np.all(np.diff(ids)>0))
sources=np.asarray(plan['source_indices']);selected=np.asarray(plan['selected_indices']);n=len(ids)
expected_ids=[10783,11177,87710,91221,91302,92929,93294,94367,123191,151556,162704,219573,526151]
same('exact_thirteen_source_ids',ids[sources],expected_ids)
same('exact_source_types',cells.type.iloc[sources].to_numpy(),['DNp09']*2+['LgAG2']*11)
same('selected_id_row_join',ids[selected],plan['selected_ids'])
check('both_negative_targets_retained',set([67052,13314])<=set(ids[selected]))
motor=set(x for k,v in plan['groups'].items()if k not in ['p9','taste']for x in v['indices'])
check('source_motor_readout_disjoint',not (set(sources)&motor))
params=plan['parameters'];dt=params['dt_ms'];delay=round(params['delay_ms']/dt);ring=delay+1;ref=round(params['refractory_ms']/dt)
check('frozen_clocks',dt==.1 and delay==18 and ring==19 and plan['neural_ticks']==5000 and plan['duration_ms']==500)
# Independently reimplement bit arithmetic using Python ints, not the engine helper.
def rng(seed):
 mask=(1<<64)-1;s=int(np.random.SeedSequence(seed).generate_state(1,dtype=np.uint64)[0]) or 1
 initial=s;u=np.empty((5000,13));ends=[]
 for t in range(5000):
  for c in range(13):
   s^=s>>12;s^=(s<<25)&mask;s^=s>>27;s&=mask
   z=(s*2685821657736338717)&mask;u[t,c]=(z>>11)*(1.0/9007199254740992.0)
  if (t+1)%10==0:ends.append(s)
 return initial,s,u,np.asarray(ends,dtype=np.uint64)
rngs={seed:rng(seed)for seed in plan['seeds']}
all_inputs={};trial_rows=[];hashes={}
for seed in plan['seeds']:
 for cond in plan['condition_order']:
  key=f'{seed}:{cond}';p=D/f'seed-{seed}'/cond
  summary=json.loads((p/'summary.json').read_text());rows=[json.loads(l)for l in (p/'samples.jsonl').read_text().splitlines()]
  data={f:npz(p/(f+'.npz'))for f in ['spikes','states','inputs','initial','final-or-failure']}
  sp,st,inp,init,fin=[data[f]for f in ['spikes','states','inputs','initial','final-or-failure']]
  im=json.loads(str(init['metadata']));fm=json.loads(str(fin['metadata']));si=sp['indices'];ticks=sp['ticks'];spec=plan['conditions'][cond]
  r=next(x for x in report['trials']if x['seed']==seed and x['condition']==cond)
  check(key+':summary_equals_panel',r==summary)
  for path,h in summary['artifacts'].items():check(key+':artifact_sha:'+Path(path).name,sha(B/path)==h)
  hashes[str((p/'summary.json').relative_to(B))]=sha(p/'summary.json')
  check(key+':metadata',im['seed']==fm['seed']==seed and im['tick']==0 and fm['tick']==5000 and im['parameters']==fm['parameters']==params and im['graph_sha256']==fm['graph_sha256']==plan['graph_sha256'])
  check(key+':complete_grid',len(rows)==500 and summary['complete'] and summary['neural_ticks']==5000)
  same(key+':sample_clock',st['sample_ms'],np.arange(501))
  same(key+':journal_start_ticks',[x['start_tick']for x in rows],np.arange(0,5000,10))
  same(key+':journal_end_ticks',[x['end_tick']for x in rows],np.arange(10,5001,10))
  same(key+':input_ids',inp['source_ids'],expected_ids);same(key+':input_indices',inp['source_indices'],sources)
  same(key+':selected_indices',st['selected_indices'],selected);same(key+':selected_ids',st['selected_ids'],ids[selected])
  rates=np.r_[np.full(2,spec['p9_hz']),np.full(11,spec['taste_hz'])];same(key+':rates',inp['rates_hz'],rates)
  ri,re,u,ends=rngs[seed];same(key+':independent_uniform_bits',inp['uniforms'],u)
  same(key+':rng_endpoints', [int(init['rng_state'][0]),int(fin['rng_state'][0])],[ri,re])
  same(key+':journal_rng_after',[x['rng_after']for x in rows],ends)
  same(key+':journal_rng_before',[x['rng_before']for x in rows],np.r_[np.uint64(ri),ends[:-1]])
  check(key+':draw_count',summary['expected_rng_draws']==65000)
  candidate=u<(rates*dt/1000);same(key+':candidate_events',inp['candidate'],candidate)
  check(key+':spike_bounds',si.ndim==ticks.ndim==1 and len(si)==len(ticks) and np.all((si>=0)&(si<n)) and np.all((ticks>=0)&(ticks<5000)))
  check(key+':spike_order_unique',np.all((np.diff(ticks)>0)|((np.diff(ticks)==0)&(np.diff(si)>0))))
  count=np.bincount(si,minlength=n);same(key+':all_cell_counts',st['all_neuron_spike_counts'],count)
  check(key+':total_spikes',len(si)==summary['total_spikes']==sum(x['total_spikes']for x in rows))
  column=np.full(n,-1);column[sources]=np.arange(13);src=column[si];keep=src>=0;fire=np.zeros((5000,13),bool);fire[ticks[keep],src[keep]]=True
  applied=candidate&~fire;same(key+':inferred_applied_from_same_tick_threshold',inp['applied_inferred'],applied)
  same(key+':actual_source_counts',summary['actual_source_spikes'],count[sources])
  same(key+':candidate_total',summary['candidate_events'],candidate.sum(0));same(key+':applied_total',summary['applied_events_inferred'],applied.sum(0))
  same(key+':candidate_per_ms',[x['candidate_events']for x in rows],candidate.reshape(500,10,13).sum(1))
  same(key+':applied_per_ms',[x['applied_events_inferred']for x in rows],applied.reshape(500,10,13).sum(1))
  same(key+':source_spikes_per_ms',[x['source_counts']for x in rows],fire.reshape(500,10,13).sum(1))
  blocked=np.zeros(n,bool)
  if spec['outgoing_block']:blocked[plan['groups'][spec['outgoing_block']]['indices']]=True
  same(key+':initial_mask',init['ablated'],blocked);same(key+':final_mask',fin['ablated'],blocked)
  check(key+':initial_rest',np.all(init['voltage_mv']==-52)and np.all(init['synaptic_mv']==0)and np.all(init['last_spike_tick']==-(2**60))and np.all(init['refractory_ticks']==ref)and np.all(init['pending_count']==0)and len(init['pending'])==0)
  check(key+':zero_current_both_endpoints',not init['current_mv'].any()and not fin['current_mv'].any())
  same(key+':final_previous_drive',fin['previous_drive'],sources)
  expected_ref=np.full(n,ref);expected_ref[sources]=0;same(key+':final_common_eligibility',fin['refractory_ticks'],expected_ref)
  same(key+':sample_common_eligibility',st['refractory_ticks'][1:],np.broadcast_to(expected_ref[selected],(500,len(selected))))
  for field in ['voltage_mv','synaptic_mv','last_spike_tick','refractory_ticks']:
   same(key+':initial_selected_'+field,st[field][0],init[field][selected]);same(key+':final_selected_'+field,st[field][-1],fin[field][selected])
  check(key+':finite_retained_states',all(np.isfinite(a[f]).all()for a in [st,init,fin]for f in ['voltage_mv','synaptic_mv']))
  expected_last=np.full(n,-(2**60),np.int64);np.maximum.at(expected_last,si,ticks);same(key+':all_last_spike_final',fin['last_spike_tick'],expected_last)
  # Reconstruct every selected last-spike sample directly from the recorded stream.
  lst=np.empty((501,len(selected)),np.int64)
  for col,idx in enumerate(selected):
   ts=ticks[si==idx];pos=np.searchsorted(ts,np.arange(501)*10,side='left')-1
   lst[:,col]=np.where(pos>=0,np.r_[-(2**60),ts][pos+1],-(2**60))
  same(key+':selected_last_spike_all_samples',st['last_spike_tick'],lst)
  due=ticks+delay;delivered=(due<5000)&~blocked[si];visits=np.zeros(500,np.int64)
  np.add.at(visits,due[delivered]//10,np.diff(indptr)[si[delivered]])
  same(key+':delayed_unblocked_edge_visits',visits,[x['traversed_edges']for x in rows])
  pend=[si[(due>=5000)&(due%ring==slot)]for slot in range(ring)]
  same(key+':pending_counts',fin['pending_count'],[len(x)for x in pend]);same(key+':pending_source_order',fin['pending'],np.concatenate(pend))
  per_ms=np.bincount(ticks//10,minlength=500);same(key+':all_spikes_per_ms',per_ms,[x['total_spikes']for x in rows])
  for name,grp in plan['groups'].items():
   member=np.isin(si,grp['indices']);same(key+':group_per_ms:'+name,np.bincount(ticks[member]//10,minlength=500),[x['group_counts'][name]for x in rows])
  for window in r['windows']:
   a,b=window['start_ms'],window['end_ms'];wc=np.bincount(si[(ticks>=round(a/dt))&(ticks<round(b/dt))],minlength=n)
   for name,grp in plan['groups'].items():
    vals=wc[grp['indices']];reported=window['groups'][name]
    check(key+':window:'+str(a)+'-'+str(b)+':'+name,reported['count']==int(vals.sum())and reported['per_cell_counts']==vals.tolist()and reported['mean_rate_hz']==float(vals.mean()/((b-a)/1000)))
  late=(ticks>=500)&np.isin(si,plan['groups']['forward']['indices'])
  check(key+':50_500ms_forward_silent',not late.any())
  if cond=='no_events':check(key+':no_events_no_spikes',len(si)==0 and not candidate.any())
  if cond=='p9_only_p9_outputs_blocked':check(key+':source_block_no_other_spikes',np.isin(si,sources[:2]).all())
  check(key+':sampled_extrema_summary',min(x['voltage_min_mv']for x in rows)==summary['voltage_min_sampled_mv']and max(x['voltage_max_mv']for x in rows)==summary['voltage_max_sampled_mv'])
  check(key+':endpoint_global_extrema',fin['voltage_mv'].min()==rows[-1]['voltage_min_mv']and fin['voltage_mv'].max()==rows[-1]['voltage_max_mv'])
  all_inputs[(seed,cond)]={'uniforms':inp['uniforms'],'candidate':candidate,'applied':applied,'spikes':(si,ticks)}
  minidx=int(fin['voltage_mv'].argmin())
  trial_rows.append({'seed':seed,'condition':cond,'total_spikes':len(si),'source_actual_spikes':count[sources].tolist(),'candidate_counts':candidate.sum(0).tolist(),'applied_counts_inferred':applied.sum(0).tolist(),'rejected_candidate_events':int((candidate&fire).sum()),'forward_late_per_cell_counts':np.bincount(si[ticks>=500],minlength=n)[plan['groups']['forward']['indices']].tolist(),'global_minimum_sampled_journal_mv':summary['voltage_min_sampled_mv'],'independently_read_final_minimum_mv':float(fin['voltage_mv'][minidx]),'final_minimum_cell_id':int(ids[minidx]),'minimum_retained_selected_mv':float(st['voltage_mv'].min()),'windows':r['windows']})
 print(key,'reviewed',flush=True)
comparisons=[]
for seed in plan['seeds']:
 base=all_inputs[(seed,'no_events')]
 for cond in plan['condition_order']:same(f'{seed}:{cond}:common_uniforms_all_conditions',all_inputs[(seed,cond)]['uniforms'],base['uniforms'])
 for aa,bb in [('p9_only','p9_only_p9_outputs_blocked'),('p9_plus_taste','p9_plus_taste_taste_outputs_blocked')]:
  a,b=all_inputs[(seed,aa)],all_inputs[(seed,bb)];same(f'{seed}:{aa}:blocked_pair_candidates',a['candidate'],b['candidate'])
  comparisons.append({'seed':seed,'a':aa,'b':bb,'same_candidates':bool(np.array_equal(a['candidate'],b['candidate'])),'applied_mask_differences':int(np.count_nonzero(a['applied']!=b['applied'])),'same_source_spike_stream':bool(all(np.array_equal(x[np.isin(a['spikes'][0],sources)],y[np.isin(b['spikes'][0],sources)])for x,y in zip(a['spikes'],b['spikes'])))})
result={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Independent retained-data audit; source arithmetic reimplemented without importing producer or neural engine; no graph simulation, parameter changes or body execution. Reviewer previously authored Eon source extraction and reviewed assay source, but did not author or run this assay.','plan_sha256':sha(P),'panel_results_sha256':sha(D/'results.json'),'review_script_sha256':sha(Path(__file__)),'trial_summary_hashes':hashes,'passed':all(x['passed']for x in checks),'check_count':len(checks),'failed_checks':[x for x in checks if not x['passed']],'checks':checks,'trials':trial_rows,'matched_input_comparisons':comparisons,'limits':['Only two stochastic seeds from one male graph, six fixed500ms conditions; no uncertainty estimate or biological replication.','Source Eon results used female FlyWire,1s and30trials with additional ascending inputs; this is not exact source reproduction.','Common candidate arrival schedules do not imply identical applied voltage increments or source spike streams after recurrent feedback.','Applied-event masks are inferred from recorded same-tick spikes plus reviewed zero-refractory kernel ordering; original kernel writes are not separately instrumented.','Checkpoint endpoints and selected1ms states are independently retained; global interior1ms extrema are journal reports, and full interior membrane/synaptic states are unavailable for an independent full recurrence replay.','Physiologically implausible negative voltages remain. Finite-number execution success does not establish acceptable physiological voltage bounds; the frozen plan explicitly excludes voltage range as a success gate.','Forward readout silence50–500ms is an observation under these finite imposed inputs, not proof of absent anatomical pathways or behavior in a body.','No readout/model/default promotion or motor coupling is justified by this review.']}
OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'passed':result['passed'],'check_count':len(checks),'failed':result['failed_checks'],'matched_input_comparisons':comparisons}),flush=True)
if not result['passed']:raise SystemExit(1)
