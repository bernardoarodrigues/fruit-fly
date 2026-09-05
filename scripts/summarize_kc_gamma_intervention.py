#!/usr/bin/env python3
"""Compact, source-pinned descriptive findings from the reviewed complete batch."""
from pathlib import Path
from datetime import datetime,timezone
import json
import numpy as np
from analyze_navigation_ladder_timing import record,load,write_new
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/kc-gamma-intervention-findings.json'
def main():
    if OUT.exists():raise FileExistsError('Preserve first descriptive summary')
    paths=[ROOT/'validation'/f for f in ['kc-gamma-intervention-analysis-plan.json','kc-gamma-intervention-analysis-results.json','kc-gamma-intervention-analysis-arrays.npz','kc-gamma-intervention-analysis-review.json','kc-gamma-intervention-independent-review.json','kc-gamma-intervention-numerics-results.json']]
    p,r=map(load,paths[:2]);assert all(load(q)['passed'] for q in [paths[1],*paths[3:]]) and record(paths[2])==r['array_artifact'];pins=[record(Path(__file__))]+[record(q) for q in paths]
    result=dict(created_utc=datetime.now(timezone.utc).isoformat(),inputs=pins,range_semantics='Descriptive min/max across six paired simulation cases, not uncertainty intervals or biological replication.',groups={},paired_pulse_gamma_contrast=[],checkpoint_1s={},promotion=False)
    for name in ['gamma_KC','other_KC','all_KC','APL','MBON12','MBON13','MBON14','MBON12_14','population','DNg97','DNp09','DN_all']:
        data={arm:np.array([t['arms'][arm]['cohorts'][name]['mean_rate_hz'] for t in r['trials']]) for arm in ['control','intervention']}
        result['groups'][name]={arm:dict(min_rate_hz=a.min(axis=0).tolist(),max_rate_hz=a.max(axis=0).tolist()) for arm,a in data.items()}
        result['groups'][name]['paired_delta_min_hz']=(data['intervention']-data['control']).min(axis=0).tolist();result['groups'][name]['paired_delta_max_hz']=(data['intervention']-data['control']).max(axis=0).tolist()
        if name=='gamma_KC':
            reduction=100*(1-data['intervention'][:,2]/data['control'][:,2]);result['gamma_pulse_percent_reduction_range']=[float(reduction.min()),float(reduction.max())]
    for pair in r['paired']:
        result['paired_pulse_gamma_contrast'].append(dict(seed=pair['seed'],control_hz=pair['cohorts']['gamma_KC']['control'][2],intervention_hz=pair['cohorts']['gamma_KC']['intervention'][2]))
    selected=np.array(p['selected_indices'])
    with np.load(paths[2],allow_pickle=False) as z:
        for group in ['gamma_KC','APL','MBON12_14']:
            cols=np.flatnonzero(np.isin(selected,p['cohorts'][group]));section=dict(observed_cells=len(cols),population_cells=len(p['cohorts'][group]),states={},reset_value_counts={})
            for k in ['v','s','h']:
                states={arm:np.array([z[f'trial_{t["ordinal"]}_{arm}_{k}_checkpoints'][1,cols].mean() for t in p['trials']]) for arm in ['control','intervention']}
                section['states'][k]={a:v.tolist() for a,v in states.items()};section['states'][k]['paired_delta']=(states['intervention']-states['control']).tolist()
            for arm in ['control','intervention']:section['reset_value_counts'][arm]=[int((z[f'trial_{t["ordinal"]}_{arm}_v_checkpoints'][1,cols]==-52.).sum()) for t in p['trials']]
            result['checkpoint_1s'][group]=section
    result['limitations']=['Subset checkpoint means are not full-population or continuous-time voltage summaries.','p-state and h units differ; these values are not voltage/current physiological measurements.','Identical coarse MBON/APL rate or ISI summaries do not prove all spike times or internal states are identical.','All six controls and seeds were previously examined.','Restoration and withdrawal coincide; no separate causal attribution.']
    assert [record(ROOT/q['path']) for q in pins]==pins;write_new(OUT,result);print(json.dumps(record(OUT)))
if __name__=='__main__':main()
