"""Independently recompute passive metrics by integer slices and math.fsum."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pyabf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-passive-measurement-review.json'


def mean(values):return math.fsum(map(float,values))/len(values)


def main():
    if OUT.exists():raise FileExistsError('Preserve completed review')
    plan_path=ROOT/'validation/apl-passive-measurement-plan.json'
    result_path=ROOT/'validation/apl-passive-measurements.json'
    plan=json.loads(plan_path.read_text());res=json.loads(result_path.read_text())
    join=json.loads((ROOT/'validation/apl-sk-workbook-join.json').read_text())
    assert res['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
    targets={}
    for b in join['books']:
        for s in b['sheets']:
            for c in s['cells']:targets[b['member'],s['name'],c['coordinate']]=c['cached_value']
    checks=0;max_error=0.;rows=[]
    for r,source in zip(res['files'],plan['files'],strict=True):
        assert r['member']==source['member'] and len(r['sweeps'])==26
        a=pyabf.ABF(str(ROOT/source['extracted_path']))
        b0,b1=r['baseline_sample_range'];p0,p1=r['plateau_sample_range']
        for s in r['sweeps']:
            a.setSweep(s['sweep'],channel=0);v=a.sweepY
            bv=mean(v[b0:b1]);dv=mean(v[p0:p1])-bv
            independent=[(bv,s['commanded']['held_baseline_mV']),
                         (dv,s['commanded']['delta_voltage_mV']),(-20*dv,s['commanded']['resistance_MOhm'])]
            if s['recorded']:
                a.setSweep(s['sweep'],channel=r['recorded_current_channel']);i=a.sweepY
                di=mean(i[p0:p1])-mean(i[b0:b1])
                independent.extend([(di,s['recorded']['delta_current_pA']),
                    (1000*dv/di,s['recorded']['resistance_MOhm'])])
            for calculated,saved in independent:
                error=abs(calculated-saved);max_error=max(max_error,error)
                assert error<1e-9,(r['member'],s['sweep'],calculated,saved)
                checks+=1
        values=np.array([s['commanded']['resistance_MOhm'] for s in r['sweeps']])
        linked=[j for j in r['linked_author_rows'] if j['sheet']=='intrinsic']
        name=Path(r['member']).name.lower()
        drug='after_NS8593_explicit_filename' if 'ns8593' in name else 'ambiguous_NS_filename' if '_fp_ns_' in name else 'baseline_filename'
        comparisons=[]
        for j in linked:
            standard=j['workbook'].endswith('APL_NS_SD_RS_final.xlsx')
            col=('P' if drug=='after_NS8593_explicit_filename' else 'G') if standard else 'H'
            target=None if drug=='ambiguous_NS_filename' else targets.get((j['workbook'],j['sheet'],f"{col}{j['row']}"))
            comparisons.append(dict(**j,author_cell=f"{col}{j['row']}" if target is not None else None,
                author_resistance_numeric_MOhm=target,
                mean_minus_author_MOhm=float(values.mean()-target) if isinstance(target,(int,float)) else None))
        recorded=[s['recorded']['resistance_MOhm'] for s in r['sweeps'] if s['recorded']]
        rows.append(dict(file_index=r['file_index'],member=r['member'],drug_filename_category=drug,
            comparisons=comparisons,mean_commanded_resistance_MOhm=float(values.mean()),
            mean_recorded_resistance_MOhm=mean(recorded) if recorded else None,
            min_commanded_resistance_MOhm=float(values.min()),max_commanded_resistance_MOhm=float(values.max()),
            first_sweep_resistance_MOhm=float(values[0]),last_sweep_resistance_MOhm=float(values[-1]),
            within_file_sd_MOhm=float(values.std(ddof=1)),
            mean_held_baseline_mV=mean([s['commanded']['held_baseline_mV'] for s in r['sweeps']]),
            max_abs_plateau_half_change_mV=max(abs(s['plateau_half_change_mV']) for s in r['sweeps'])))
    differences=[c['mean_minus_author_MOhm'] for r in rows for c in r['comparisons'] if c['mean_minus_author_MOhm'] is not None]
    currents=[s['recorded']['delta_current_pA'] for r in res['files'] for s in r['sweeps'] if s['recorded']]
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        results_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),independent_scalar_checks=checks,
        max_absolute_recomputation_error=max_error,
        recorded_current_sweeps=len(currents),missing_recorded_current_sweeps=2132-len(currents),
        recorded_delta_current_pA_quantiles=dict(zip(['min','median','max'],map(float,np.quantile(currents,[0,.5,1])))),
        source_comparison_count=len(differences),mean_minus_author_MOhm_quantiles=dict(zip(['min','median','max'],map(float,np.quantile(differences,[0,.5,1])))),
        files=rows,
        scope='All sweeps checked independently by integer slices and compensated scalar sums, using the same pyABF reader. This is not independent ABF binary decoding. Source comparisons use the declared all-sweep 100 ms windows, not a claim to reproduce author cursor/sweep selection. Filename ambiguities retained; no parameter fit or statistical condition inference.')
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__':main()
