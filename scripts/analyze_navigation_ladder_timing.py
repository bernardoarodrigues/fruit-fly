#!/usr/bin/env python3
"""Frozen post-hoc reduction of six saved H1 spike streams; no model imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'validation/navigation-ladder-timing-plan.json'
RESULT = ROOT / 'validation/navigation-ladder-timing-results.json'
ARRAYS = ROOT / 'validation/navigation-ladder-timing-arrays.npz'
PANEL = ROOT / 'validation/inhibitory-recurrent-panel-plan.json'
STAGE0 = ROOT / 'validation/navigation-ladder-readouts.json'
ANATOMY = ROOT / 'validation/navigation-ladder-anatomy.json'
NAMES = ['ORN_VM7d', 'VM7d_adPN', 'MBON12', 'MBON13', 'MBON14', 'MBON12_14', 'FB5AB']
EXPECTED_PANEL = 'c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5'
EXPECTED_MANIFEST = 'c8410ecea4923be0f090daff7e7a14a4ba375e51cfaafd3851d1a040f69bf9e6'
BIN = 250
END = 30000
DT_S = .0001


def sha(b):
    return hashlib.sha256(b).hexdigest()


def record(p):
    p = Path(p); b = p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)), bytes=len(b), sha256=sha(b))


def load(p):
    return json.loads(Path(p).read_text())


def write_new(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def histogram(indices, ticks, lookup):
    cols = lookup[indices]
    keep = cols >= 0
    return np.bincount((ticks[keep] // BIN) * (lookup.max()+1) + cols[keep],
                       minlength=(END//BIN)*(lookup.max()+1)).reshape(END//BIN, -1)


def fixture():
    lookup = np.array([-1, 0, -1, 1], dtype=np.int32)
    ticks = np.array([0, 249, 250, 499, 500, 4999, 5000, 5999, 6000, 9000, 9999, 10000, 15000, 29999])
    indices = np.array([1, 3, 1, 2, 3, 1, 1, 3, 1, 3, 1, 1, 3, 1])
    expected = np.zeros((120, 2), dtype=np.int64)
    for i, t in zip(indices, ticks):
        if i in (1, 3): expected[int(t)//250, 0 if i == 1 else 1] += 1
    actual = histogram(indices, ticks, lookup)
    if not np.array_equal(actual, expected): raise AssertionError('manufactured bin arithmetic')
    if int(actual[20:24].sum()) != 2 or int(actual[36:40].sum()) != 2:
        raise AssertionError('manufactured early/late windows')
    if histogram(np.array([], dtype=int), np.array([], dtype=int), lookup).any():
        raise AssertionError('empty stream')
    return dict(passed=True, checks=4, scope='Manufactured integer half-open binning/early/late/empty checks only')


def prepare():
    if PLAN.exists() or RESULT.exists() or ARRAYS.exists(): raise FileExistsError('Preserve frozen timing outputs')
    pure = fixture()
    panel = load(PANEL); stage = load(STAGE0); anatomy = load(ANATOMY)
    if record(PANEL)['sha256'] != EXPECTED_PANEL or not stage['passed'] or not anatomy['passed']:
        raise AssertionError('panel and completed Stage0 required')
    run = ROOT / panel['run_dir']; terminal = load(run/'terminal.json')
    if not terminal['complete'] or terminal['status'] != 'complete': raise AssertionError('parent must be complete')
    for r in [terminal['results'], terminal['artifact_manifest']]:
        if record(ROOT/r['path']) != r: raise AssertionError('final publication hash')
    if terminal['artifact_manifest']['sha256'] != EXPECTED_MANIFEST: raise AssertionError('immutable final manifest')
    for r in [stage['plan'], stage['array_artifact']]:
        if record(ROOT/r['path']) != r: raise AssertionError('Stage0 artifact pin')
    groups = {k: anatomy['groups'][k] for k in NAMES}
    if any(groups[k] != stage['group_definitions'][k] for k in NAMES): raise AssertionError('Stage0 cohort identity')
    specs = [s for s in panel['order'] if s['arm']=='H1' and s['condition'] in ('constant_baseline','ethyl_acetate')]
    if len(specs)!=6 or {s['seed'] for s in specs}!={11,12,13}: raise AssertionError('six selected trials')
    paths = [Path(__file__), PANEL, STAGE0, ANATOMY, ROOT/stage['plan']['path'], ROOT/stage['array_artifact']['path'],
             run/'terminal.json', run/'results.json', run/'artifact-manifest.json',
             ROOT/'data/processed/malecns_v1/neuron_ids.npy']
    inputs = [record(p) for p in paths]
    for spec in specs:
        t = load(run/spec['name']/'terminal.json'); r = record(run/spec['name']/'result.json')
        if not t['complete'] or t['status']!='complete' or r != t['result']: raise AssertionError('completed trial publication')
        inputs.extend([record(run/spec['name']/'terminal.json'), r])
    plan = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), inputs=inputs,
        run_dir=panel['run_dir'], trials=specs, cohorts=groups, bin_edges_ticks=list(range(0,END+1,BIN)),
        coarse_edges_ticks=panel['window_edges_ticks'], dt_s=DT_S, neurons=panel['neurons'],
        early_pulse_ticks=[5000,6000], late_pulse_ticks=[9000,10000], boundaries_ticks=[5000,10000,15000],
        selection='Post-hoc H1 EA versus constant diagnostic, seeds11/12/13, chosen after Stage0. No cross-arm, biological or promotion claim.',
        method='Independently read packed tick<int64/index<int32> spike records from all600 chunks per trial. Validate final-manifest and completion-marker hashes; reduce only55 selected cells. Check exact per-cell coarse counts against final checkpoint and Stage0 NPZ, and cohort totals against Stage0 JSON.',
        timing='Integer emission stamp k denotes thresholder output after that tick integration. Nominal graph synapse slot is k+18 (1.8ms) after integration of that later tick, conditional on outgoing transmission. Post-step state clock would be k+1. Exported spikes are not measured afferent arrivals or evoked latencies; ongoing baseline already exists.',
        metrics=['25ms per-cell counts and cohort rates','Exact selected emitted spike indices/ticks/body IDs','100ms early/late pulse counts and matched EA-minus-constant contrasts','First/last spike in each coarse window and around each boundary (descriptive, not evoked latency)','MBON spikes strictly after final mapped VM7d PN spike (descriptive order, not autonomous recurrence proof)'],
        limits=['No neural/producer imports, propagation, solver or fitting.','No synaptic depression, receptor mechanism or unique causal localization inferred from spike timing.','Selected emitted spikes and counts only; no reconstruction of unsaved all-neuron voltage or actual edge arrivals.','Coarse PFL3 pulse counts are already zero; no hidden pulse burst is inferred or sought.','All analyses are reuse of the same six simulations, not six new observations.'],
        manufactured_checks=pure, outputs=[str(RESULT.relative_to(ROOT)),str(ARRAYS.relative_to(ROOT))])
    write_new(PLAN,plan); print(json.dumps(record(PLAN)))


class Reader:
    def __init__(self, manifest):
        self.manifest = {r['path']:r for r in manifest['artifacts']}
        self.checked = {}; self.counts = {}; self.current = None

    def check(self, category, passed):
        self.counts[category] = self.counts.get(category,0)+1
        if not passed: raise AssertionError(category+' at '+str(self.current))

    def verify(self, path):
        rel = str(Path(path).relative_to(ROOT))
        if rel not in self.checked:
            r = record(path); self.check('manifest-file',r == self.manifest[rel]); self.checked[rel] = r
        return self.checked[rel]

    def header(self, stem):
        paths = {k:Path(str(stem)+k) for k in ['.json','.npz','.complete.json']}
        for p in paths.values(): self.verify(p)
        h = load(paths['.json']); m = load(paths['.complete.json'])
        self.check('bundle-complete',h['format']=='inhibitory-recurrent-panel' and h['version']==1 and
                   m['format']=='inhibitory-recurrent-panel-completion' and m['version']==1 and m['complete'] and h['transaction']==m['transaction'])
        self.check('marker-payloads',m['artifacts']==[self.checked[str(paths[k].relative_to(ROOT))] for k in ['.npz','.json']])
        return h, paths['.npz']

    def array(self, descriptor, z):
        a = z[descriptor['key']]
        self.check('array-descriptor',not a.dtype.hasobject and list(a.shape)==descriptor['shape'] and a.nbytes==descriptor['bytes'] and
                   a.itemsize==descriptor['itemsize'] and a.size==descriptor['count'] and
                   json.loads(json.dumps(np.lib.format.dtype_to_descr(a.dtype)))==descriptor['dtype'] and sha(a.tobytes())==descriptor['sha256'])
        return a

    def spikes(self, stem):
        h,p = self.header(stem); tree=h['tree']; items=dict(tree['items']); desc=tree['spikes']; head=desc['header']
        with np.load(p,allow_pickle=False) as z: a=self.array(desc['array'],z)
        self.check('packed-spikes',a.dtype.descr==[('tick','<i8'),('index','<i4')] and a.itemsize==12 and a.ndim==1 and
                   head['version']==1 and head['count']==len(a) and head['shape']==list(a.shape) and head['itemsize']==12 and
                   head['dtype']==[['tick','<i8'],['index','<i4']] and head['sha256']==sha(a.tobytes()))
        self.check('original-spike-bytes',all(sha(a[f].astype(head['original_'+f+'_dtype']).tobytes())==head['original_'+f+'_sha256'] for f in ['tick','index']))
        return a,items


def first_last(ticks):
    return dict(count=len(ticks), first_tick=int(ticks[0]) if len(ticks) else None,last_tick=int(ticks[-1]) if len(ticks) else None)


def analyze():
    if RESULT.exists() or ARRAYS.exists(): raise FileExistsError('Preserve first timing execution')
    plan=load(PLAN); plan_record=record(PLAN); start=time.perf_counter()
    result=dict(schema=1,passed=False,plan=plan_record,selection=plan['selection'],timing=plan['timing'],limits=plan['limits'],trials=[])
    arrays={}; reader=None; context=None
    try:
        for r in plan['inputs']:
            if record(ROOT/r['path'])!=r: raise AssertionError('Changed frozen input '+r['path'])
        run=ROOT/plan['run_dir']; reader=Reader(load(run/'artifact-manifest.json')); stage=load(STAGE0)
        coarse=np.asarray(plan['coarse_edges_ticks']); groups=plan['cohorts']; graph_ids=np.load(ROOT/'data/processed/malecns_v1/neuron_ids.npy',allow_pickle=False)
        selected=np.unique(np.concatenate([g['indices'] for g in groups.values()])).astype(np.int32)
        reader.check('55-selected-cells',len(selected)==55 and len(graph_ids)==plan['neurons'])
        lookup=np.full(plan['neurons'],-1,dtype=np.int32);lookup[selected]=np.arange(len(selected),dtype=np.int32)
        for name,g in groups.items(): reader.check('exact-cohort-IDs',graph_ids[g['indices']].tolist()==g['body_ids'])
        arrays.update(graph_indices=selected,body_ids=graph_ids[selected],bin_edges_ticks=np.array(plan['bin_edges_ticks']),coarse_edges_ticks=coarse)
        with np.load(ROOT/stage['array_artifact']['path'],allow_pickle=False) as z:
            stage_indices=z['graph_indices'];stage_counts=z['counts']
        pos=np.searchsorted(stage_indices,selected);reader.check('Stage0-index-mapping',np.array_equal(stage_indices[pos],selected))
        stage_lookup={t['spec']['name']:(i,t) for i,t in enumerate(stage['trials'])}
        counts_all=[]
        for spec in plan['trials']:
            context=dict(trial=spec['name'],chunk=None);reader.current=context
            directory=run/spec['name']; report=load(directory/'result.json')
            h,p=reader.header(directory/'checkpoint-30000');meta=dict(h['tree']['items'])
            reader.check('checkpoint-state',meta['tick']['value']==END and meta['coherent_state']['value'] and
                         meta['arm']['value']=='H1' and meta['seed']['value']==spec['seed'])
            with np.load(p,allow_pickle=False) as z: cp=reader.array(meta['window_counts_observed']['array'],z)[:,selected]
            count=np.zeros((120,len(selected)),dtype=np.int64); pieces=[]; total=0
            arrays['trial_'+str(spec['ordinal'])+'_counts25_observed']=count
            result['active_trial']=context
            for chunk in range(600):
                context['chunk']=chunk;reader.current=context
                packed,items=reader.spikes(directory/f'chunk-{chunk:04d}')
                lo=chunk*50;hi=lo+50;ii=packed['index'];tt=packed['tick']
                reader.check('chunk-clock-status',items['status']['value']=='complete' and items['coherent_state']['value'] and
                    items['failure']['value'] is None and items['partial']['value'] is None and
                    items['start_tick']['value']==lo and items['end_tick']['value']==hi and
                    items['completed_ticks']['value']==items['requested_ticks']['value']==50)
                reader.check('emitted-spike-order',np.all((tt>=lo)&(tt<hi)) and np.all((ii>=0)&(ii<plan['neurons'])) and
                    (len(tt)<2 or np.all((tt[1:]>tt[:-1])|((tt[1:]==tt[:-1])&(ii[1:]>ii[:-1])))))
                keep=lookup[ii]>=0;pieces.append(packed[keep].copy());count+=histogram(ii,tt,lookup);total+=len(packed)
                result['active_trial']=dict(**context,validated_end_tick=hi,selected_spikes=int(count.sum()),all_spikes=total)
            spikes=np.concatenate(pieces); prefix='trial_'+str(spec['ordinal'])
            arrays[prefix+'_spikes']=spikes;arrays[prefix+'_spike_body_ids']=graph_ids[spikes['index']]
            reader.check('full-spike-total',total==report['spike_count'])
            direct=np.zeros_like(count)
            np.add.at(direct,(spikes['tick']//BIN,lookup[spikes['index']]),1)
            reader.check('selected-lossless-count-roundtrip',np.array_equal(direct,count))
            coarse_counts=np.stack([count[a//BIN:b//BIN].sum(axis=0) for a,b in zip(coarse[:-1],coarse[1:])])
            stage_i,old=stage_lookup[spec['name']]
            reader.check('checkpoint-and-Stage0-per-cell-counts',np.array_equal(coarse_counts,cp) and np.array_equal(coarse_counts,stage_counts[stage_i][:,pos]))
            cm={}
            for name,g in groups.items():
                cols=lookup[g['indices']]; c=count[:,cols].sum(axis=1);times=spikes['tick'][np.isin(spikes['index'],g['indices'])]
                oldcounts=[int(coarse_counts[j,cols].sum()) for j in range(7)]
                reader.check('Stage0-cohort-counts',oldcounts==old['cohorts'][name]['counts'])
                early=int(c[20:24].sum());late=int(c[36:40].sum())
                cm[name]=dict(cells=len(cols),counts25=c.tolist(),rates25_hz=(c/(.025*len(cols))).tolist(),coarse_counts=oldcounts,
                    early_pulse_count=early,late_pulse_count=late,early_pulse_hz=early/(.1*len(cols)),late_pulse_hz=late/(.1*len(cols)),
                    late_minus_early_hz=(late-early)/(.1*len(cols)),whole=first_last(times),
                    coarse_first_last=[first_last(times[(times>=a)&(times<b)]) for a,b in zip(coarse[:-1],coarse[1:])],
                    boundaries={str(b):dict(last_before=first_last(times[times<b])['last_tick'],first_at_or_after=first_last(times[times>=b])['first_tick']) for b in plan['boundaries_ticks']})
            last_pn=cm['VM7d_adPN']['whole']['last_tick'];mbon=spikes['tick'][np.isin(spikes['index'],groups['MBON12_14']['indices'])]
            tr=dict(spec=spec,all_raw_spikes=total,selected_spikes=len(spikes),validated_end_tick=END,cohorts=cm,
                mbon_spikes_strictly_after_last_mapped_PN_spike=None if last_pn is None else first_last(mbon[mbon>last_pn]))
            result['trials'].append(tr);counts_all.append(count)
        arrays['counts25']=np.array(counts_all)
        paired=[]
        for seed in [11,12,13]:
            a={t['spec']['condition']:t for t in result['trials'] if t['spec']['seed']==seed}
            for name in NAMES:
                ea=a['ethyl_acetate']['cohorts'][name];base=a['constant_baseline']['cohorts'][name]
                paired.append(dict(seed=seed,cohort=name,EA_minus_constant_rates25_hz=(np.array(ea['rates25_hz'])-base['rates25_hz']).tolist(),
                    early_pulse_EA_minus_constant_hz=ea['early_pulse_hz']-base['early_pulse_hz'],
                    late_pulse_EA_minus_constant_hz=ea['late_pulse_hz']-base['late_pulse_hz'],
                    difference_of_late_minus_early_hz=ea['late_minus_early_hz']-base['late_minus_early_hz']))
        result['paired_contrasts']=paired
        for r in plan['inputs']: reader.check('frozen-input-at-end',record(ROOT/r['path'])==r)
        reader.check('plan-unchanged',record(PLAN)==plan_record)
        result.pop('active_trial',None);result['passed']=True
    except (Exception,KeyboardInterrupt) as e:
        if 'pieces' in locals() and pieces:
            arrays['failure_validated_selected_spikes']=np.concatenate(pieces)
        result['error']=dict(type=type(e).__name__,message=str(e),context=context,traceback=traceback.format_exc())
    with ARRAYS.open('xb') as f: np.savez_compressed(f,**arrays)
    result.update(array_artifact=record(ARRAYS),created_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start,
                  check_categories={} if reader is None else reader.counts,
                  checked_manifest_files=0 if reader is None else len(reader.checked))
    result['check_count']=sum(result['check_categories'].values())
    if reader is not None:
        digest=hashlib.sha256()
        for p in sorted(reader.checked): digest.update(json.dumps(reader.checked[p],sort_keys=True,separators=(',',':')).encode()+b'\n')
        result['checked_file_receipts_digest']=digest.hexdigest()
    write_new(RESULT,result)
    print(json.dumps(dict(passed=result['passed'],checks=result['check_count'],result=record(RESULT),arrays=result['array_artifact'],error=result.get('error'))))
    return 0 if result['passed'] else 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','analyze']);args=parser.parse_args()
    if args.action=='prepare': prepare();return 0
    return analyze()


if __name__=='__main__': raise SystemExit(main())
