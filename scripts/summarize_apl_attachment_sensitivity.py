#!/usr/bin/env python3
"""Reduce the closed spatial batch to individual KC observations, preserving partners."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/apl-attachment-sensitivity-kc-summary.json'


def main():
    if OUT.exists():raise FileExistsError('Preserve completed reduction')
    paths=['validation/apl-attachment-sensitivity-results.json','validation/apl-attachment-sensitivity-arrays.npz',
           'validation/male-apl-geometry-arrays.npz','validation/apl-spatial-operator-arrays.npz']
    result=json.loads((ROOT/paths[0]).read_text());data=np.load(ROOT/paths[1]);geo=np.load(ROOT/paths[2]);base=np.load(ROOT/paths[3])
    cells=[];summary_checks=0
    for cell in result['cells']:
        body=cell['body_id'];p=f'b{body}_';coupling=data[p+'coupling']
        inv=base[p+'output_contact_inverse'];ids=base[p+'output_contact_indices']
        kc,kc_inverse=np.unique(geo[p+'counterpart_body_id'][ids],return_inverse=True)
        counts=np.bincount(kc_inverse)
        assert counts.sum()==cell['cohorts']['APL_to_KC']['contacts'] and (kc>0).all()
        cases=[]
        for row in cell['cases']:
            mi=['constant_diameter','source_radius'].index(row['metric'])
            vi=['nearest_control','output_alternative','source_alternative','both_alternative'].index(row['variant'])
            ri=['CA','gL','aL'].index(row['source_region'])
            y=coupling[mi,vi,ri][inv];x=coupling[mi,0,ri][inv];delta=y-x
            actual=[y.mean(),x.mean(),y.mean()/x.mean()-1,np.abs(delta).mean(),np.sqrt(np.mean(delta**2)),*np.quantile(np.abs(delta),[0,.5,.95,1])]
            recorded=[row['contact_mean'],row['control_mean'],row['relative_mean_change'],row['contact_mean_absolute_change'],row['contact_rms_change'],*row['contact_absolute_change_quantiles']]
            np.testing.assert_allclose(actual,recorded,rtol=0,atol=1e-14);summary_checks+=len(actual)
            cx=np.bincount(kc_inverse,weights=x)/counts
            cy=np.bincount(kc_inverse,weights=y)/counts
            change=cy-cx;worst=int(np.argmax(np.abs(change)))
            cases.append(dict(metric=row['metric'],variant=row['variant'],source_region=row['source_region'],
                kc_absolute_change_quantiles=np.quantile(np.abs(change),[0,.5,.95,1]).tolist(),
                max_change_kc_body_id=int(kc[worst]),max_change_kc_contacts=int(counts[worst]),
                max_change_kc_control=float(cx[worst]),max_change_kc_alternative=float(cy[worst])))
        cells.append(dict(body_id=body,postsynaptic_kcs=len(kc),contact_count_quantiles=np.quantile(counts,[0,.5,.95,1]).tolist(),cases=cases))
    out=dict(status='saved_summary_reproduced',summary_scalar_checks=summary_checks,
             scope='Equal-weight summary across KCs of each KC mean per retained APL contact. No electrical conductance, release law or empirical error probability implied.',
             inputs=[dict(path=s,sha256=hashlib.sha256((ROOT/s).read_bytes()).hexdigest()) for s in paths],cells=cells)
    with OUT.open('x') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
    print('Verified',summary_checks,'saved scalar summaries')
    for cell in cells:
        print('APL',cell['body_id'],'KCs',cell['postsynaptic_kcs'])
        for c in cell['cases']:
            if c['metric']=='source_radius' and c['variant']=='both_alternative': print(c)


if __name__=='__main__':main()
