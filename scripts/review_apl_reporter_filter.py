#!/usr/bin/env python3
"""Independent saved-array reduction and zero-tau boundary-fit check."""
from pathlib import Path
import json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-reporter-filter-review.json'
if OUT.exists():raise FileExistsError(OUT)
path=ROOT/'validation/apl-reporter-filter-results.json';r=json.loads(path.read_text())
a=np.load(ROOT/r['arrays']['path']);t=a['time_s'];checks=0;gain_errors=[]
assert r['declared_prediction_slots']==r['scored_predictions']+r['unscorable_prediction_slots']==320
for arm in r['arms']:
 assert len(arm['cases'])==78 and arm['unscorable_pairs']==[dict(panel='E',color_rank=10,role='secondary',reason='No positive dye peak for declared normalization',input_peak_dff=-0.0021925639703308784)]
 for model in arm['models']:
  assert model['tau_s']==0
  training=[a[c['array_key']] for c in arm['cases'] if c['role']=='calibration' and c['model']==model['name']]
  target=np.concatenate([x[0] for x in training]);driver=np.concatenate([x[6] for x in training])
  # Solve independently through least squares, with the declared nonnegative gain bound.
  expected=max(0.,float(np.linalg.lstsq(driver[:,None],target,rcond=None)[0][0]))
  gain_errors.append(abs(expected-model['gain']));assert gain_errors[-1]<1e-12
  for c in [x for x in arm['cases'] if x['model']==model['name']]:
   y,lo,hi,p,pl,ph,u=a[c['array_key']]
   np.testing.assert_allclose(p,model['gain']*u,rtol=0,atol=1e-12)
   residual=p-y;gap=np.clip(np.maximum(pl-hi,lo-ph),0,None)
   actual=[np.sqrt(np.mean(residual**2)),np.abs(residual).mean(),t[y.argmax()],t[p.argmax()],np.mean(gap<=1e-12),gap.max()]
   recorded=[c['normalized_rmse'],c['normalized_mae'],c['target_peak_s'],c['prediction_peak_s'],c['graphical_interval_overlap_fraction'],c['maximum_graphical_interval_gap']]
   np.testing.assert_allclose(actual,recorded,rtol=0,atol=1e-12);checks+=len(actual)
  for role in ['calibration','evaluation','secondary']:
   rows=[a[c['array_key']] for c in arm['cases'] if c['model']==model['name'] and c['role']==role]
   expected=np.sqrt(np.mean(np.concatenate([(x[3]-x[0])**2 for x in rows])))
   rec=next(x for x in arm['summaries'] if x['model']==model['name'] and x['role']==role)
   assert abs(expected-rec['pooled_normalized_rmse'])<1e-12;checks+=1
out=dict(status='passed_saved_array_and_boundary_gain_review',scalar_summary_checks=checks,independent_gain_solves=len(gain_errors),maximum_gain_error=max(gain_errors),
         source_result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_arrays_sha256=hashlib.sha256((ROOT/r['arrays']['path']).read_bytes()).hexdigest(),
         scope='Verifies saved predictions, normalized metrics and observed tau=0 gain fits. Does not establish a biological model or independent fit identifiability.')
with OUT.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out,indent=2))
