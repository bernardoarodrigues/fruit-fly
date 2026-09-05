#!/usr/bin/env python3
"""Six frozen inactive-window probes against published 5 ms historical chunks."""
import json
import traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from prepare_kc_gamma_contact_mask import ROOT,GRAPH,record,write
from inhibitory_recurrent_panel_archive import load_archive
from check_navigation_mbon_intervention_kernel import exact
from kc_gamma_intervention_kernel import GammaContactNetwork,original

BASE=ROOT/'validation/kc-gamma-checkpoint-parity'
def main():
    planpath=Path(str(BASE)+'-plan.json');resultpath=Path(str(BASE)+'-results.json')
    if planpath.exists() or resultpath.exists():raise FileExistsError('Preserve first parity attempt')
    panelpath=ROOT/'validation/inhibitory-recurrent-panel-plan.json';panel=json.loads(panelpath.read_text());old=ROOT/panel['run_dir'];trials=[panel['order'][i] for i in [26,29,32,35,38,41]]
    maskpath=ROOT/'validation/kc-gamma-contact-mask-arrays.npz';checkpath=ROOT/'validation/kc-gamma-intervention-kernel-checks.json';checks=json.loads(checkpath.read_text());assert checks['passed']
    for r in checks['inputs']:assert record(ROOT/r['path'])==r
    paths=[Path(__file__),maskpath,checkpath,panelpath,ROOT/'scripts/kc_gamma_intervention_kernel.py',ROOT/'scripts/navigation_mbon_intervention_kernel.py',ROOT/'scripts/inhibitory_recurrent_panel_kernel.py',ROOT/'scripts/inhibitory_factorial_solver.py',ROOT/'scripts/inhibitory_recurrent_panel_archive.py',ROOT/'scripts/check_navigation_mbon_intervention_kernel.py',ROOT/'scripts/prepare_kc_gamma_contact_mask.py',old/'artifact-manifest.json',old/'terminal.json']+[GRAPH/(n+'.npy') for n in ['neuron_ids','indptr','targets','weights']]
    for spec in trials:
        for stem in [old/spec['name']/'checkpoint-05000',old/spec['name']/'chunk-0100',old/f'input-seed{spec["seed"]}']:
            paths += [Path(str(stem)+ext) for ext in ['.json','.npz','.complete.json']]
    pins=[record(p) for p in dict.fromkeys(paths)];terminal=json.loads((old/'terminal.json').read_text());assert record(old/'artifact-manifest.json')==terminal['artifact_manifest']
    historical={r['path']:r for r in json.loads((old/'artifact-manifest.json').read_text())['artifacts']}
    for r in pins:
        if r['path'] in historical:assert r==historical[r['path']]
    write(planpath,dict(created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,trials=trials,probe_ticks=[5000,5050],inactive_delivery_window=[10000,15000],threads=4,scope='Exactly six 50-tick inactive probes, original48 observations. Every original returned field must match saved historical chunk. No active intervention, outcome analysis or parameter search.'))
    result=dict(passed=False,checks=0,trials=[],error=None,plan=record(planpath));error=None
    try:
        original.configure_threads(4);graph=tuple(np.load(GRAPH/(n+'.npy')) for n in ['neuron_ids','indptr','targets','weights'])
        with np.load(maskpath,allow_pickle=False) as a:edges=a['edge_indices'];retained=a['retained_weight']
        for spec in trials:
            cp=load_archive(old/spec['name']/'checkpoint-05000');reference=load_archive(old/spec['name']/'chunk-0100');stream=load_archive(old/f'input-seed{spec["seed"]}')
            net=GammaContactNetwork.from_checkpoint(*graph,cp,modified_edge_indices=edges,retained_weights=retained,delivery_window=[10000,15000]);initial=net.checkpoint()
            assert all(exact(initial[k],cp[k]) for k in initial);result['checks']+=len(initial)
            p=np.full(len(cp['input_indices']),panel['condition_rates_hz'][spec['condition']][1])*.1/1000.
            out=net.advance(stream['uniforms'][5000:5050],p,log_selected_events=True,event_indices=reference['schema']['event_graph_indices'])
            for k,v in out.items():
                assert exact(v,reference[k]),(spec['name'],k);result['checks']+=1
            assert not net.last_contact_intervention['counts'].any() and not net.last_contact_intervention['removed_weight_sum'].any();result['checks']+=1
            result['trials'].append(dict(spec=spec,passed=True,original_output_fields=len(out),probe_ticks=50))
        assert [record(ROOT/r['path']) for r in pins]==pins;result['checks']+=len(pins);result['passed']=True
    except Exception:result['error']=traceback.format_exc()
    result['completed_utc']=datetime.now(timezone.utc).isoformat();write(resultpath,result);print(json.dumps(result))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
