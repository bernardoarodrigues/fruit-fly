"""Independent arithmetic review of every drive-response measurement."""
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pyabf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-input-response-review.json'


def mean(v):return math.fsum(map(float,v))/len(v)


def main():
    if OUT.exists():raise FileExistsError('Preserve review')
    path=ROOT/'validation/apl-input-response-results.json';r=json.loads(path.read_text())
    h={f['member']:f for f in json.loads((ROOT/'validation/apl-sk-abf-headers.json').read_text())['records']}
    passive=json.loads((ROOT/'validation/apl-passive-measurements.json').read_text())
    rin={f['member']:mean([s['commanded']['resistance_MOhm'] for s in f['sweeps']]) for f in passive['files']}
    checks=0;maxerror=0.;comparison=[];matched2=[]
    for f in r['files']:
        a=pyabf.ABF(str(ROOT/h[f['member']]['extracted_path']))
        for s in f['sweeps']:
            a.setSweep(s['sweep'],channel=0);v=a.sweepY
            b0,b1=s['baseline_samples'];p0,p1=s['plateau_samples'];e0,e1=s['early_samples'];q0,q1=s['post_samples']
            base=mean(v[b0:b1]);plateau=mean(v[p0:p1]);early=mean(v[e0:e1]);post=min(map(float,v[q0:q1]))-base
            values=[(base,s['baseline_voltage_mV']),(plateau-base,s['plateau_delta_mV']),
                    (early-base,s['early_delta_mV']),(plateau-early,s['plateau_minus_early_mV']),(post,s['post_minimum_delta_mV'])]
            if s['recorded_current']:
                a.setSweep(s['sweep'],channel=f['current_channel']);c=a.sweepY
                values.append((mean(c[p0:p1])-mean(c[b0:b1]),s['recorded_current']['delta_pA']))
            for actual,saved in values:
                error=abs(actual-saved);assert error<1e-9;maxerror=max(maxerror,error);checks+=1
        if f['staircase']:
            s=next(s for s in f['sweeps'] if s['command_delta_pA']==1000)
            ratio=s['plateau_delta_mV']/rin[f['member']]
            comparison.append(dict(file_index=f['file_index'],member=f['member'],small_signal_resistance_MOhm=rin[f['member']],
                one_nA_plateau_delta_mV=s['plateau_delta_mV'],observed_over_linear=ratio,
                equivalent_missing_current_pA=1000*(1-ratio),
                scope='Deviation from the small-negative-step linear extrapolation, not a measurement of a particular ionic current.'))
        else:
            cell=f['author_rows'][0]['cell']
            possible=[x for x in passive['files'] if any(j['cell']==cell for j in x['linked_author_rows'])];assert len(possible)==1
            small=rin[possible[0]['member']];average=mean([s['plateau_delta_mV'] for s in f['sweeps']])
            matched2.append(dict(cell=cell,file_index=f['file_index'],small_signal_resistance_MOhm=small,
                two_nA_mean_plateau_delta_mV=average,observed_over_linear=average/(2*small)))
    currents=[s['recorded_current'] for f in r['files'] for s in f['sweeps'] if s['recorded_current']]
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),independent_scalar_checks=checks,max_absolute_error=maxerror,
        recorded_current_count=len(currents),missing_recorded_current_count=2197-len(currents),all_current_checks_pass=all(c['within_tolerance'] for c in currents),
        one_nA_ratio_min_median_max=np.quantile([c['observed_over_linear'] for c in comparison],[0,.5,1]).tolist(),
        two_nA_ratio_min_median_max=np.quantile([c['observed_over_linear'] for c in matched2],[0,.5,1]).tolist(),
        one_nA_comparisons=comparison,two_nA_comparisons=matched2,
        scope='All 2197 sweep arithmetic checked by compensated scalar sums/minima with the same ABF decoder. Pulse timing and first-peak indices are retained from producer, not independently redecoded. All original identities and missing channels remain explicit. No fitted drive law or ionic-current attribution.')
    OUT.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('one_nA_comparisons','two_nA_comparisons')},indent=2))


if __name__=='__main__':main()
