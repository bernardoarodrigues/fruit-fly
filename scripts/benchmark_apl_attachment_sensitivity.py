#!/usr/bin/env python3
"""Fixed complete nearby-branch sensitivity batch; no anatomy correction or fit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
import numpy as np
from apl_skeleton_geometry import SkeletonForest
from apl_attachment_sensitivity import nearby_nonlocal
from apl_spatial_operator import split_at_attachments,electrotonic_lengths,exponential_sum

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-attachment-sensitivity-plan.json'
OUT=ROOT/'validation/apl-attachment-sensitivity-results.json'
ARRAYS=ROOT/'validation/apl-attachment-sensitivity-arrays.npz'


def pin(p):
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    if OUT.exists() or ARRAYS.exists(): raise FileExistsError('Preserve completed batch')
    plan=json.loads(PLAN.read_text())
    for s in plan['source_pins']: assert pin(ROOT/s['path'])['sha256']==s['sha256']
    begun=time.perf_counter();rng=np.random.default_rng(plan['seed'])
    geometry=np.load(ROOT/plan['geometry'],allow_pickle=False)
    baseline=np.load(ROOT/plan['baseline'],allow_pickle=False)
    stored={};results=[]
    for body in plan['body_ids']:
        pre=f'b{body}_'; f=SkeletonForest(ROOT/f'data/raw/male-apl-skeletons/{body}.swc')
        points=geometry[pre+'unique_contact_xyz_um'];edge=geometry[pre+'projection_edge_child_index']
        frac=geometry[pre+'projection_fraction'];res=geometry[pre+'projection_residual_um']
        alternative=nearby_nonlocal(f,points,edge,frac,res,plan['residual_envelope_um'],plan['minimum_path_separation_um'])
        ae,at,ar,separation,count=alternative;changed=count>0
        assert (f.component[ae]==f.component[edge]).all()
        assert (ar<=res+plan['residual_envelope_um']+1e-12).all()
        assert (separation[changed]>=plan['minimum_path_separation_um']).all()
        assert np.array_equal(ae[~changed],edge[~changed]) and np.array_equal(at[~changed],frac[~changed])
        # Independent all-segment enumeration at fixed-seed contact points.
        reference=[]
        for idx in rng.choice(len(points),plan['reference_points'],replace=False):
            v=f.xyz[f.parent]-f.xyz;sq=np.einsum('ij,ij->i',v,v)
            tt=np.clip(np.divide(np.einsum('ij,ij->i',points[idx]-f.xyz,v),sq,out=np.zeros(len(sq)),where=sq>0),0,1)
            rr=np.linalg.norm(points[idx]-f.xyz-tt[:,None]*v,axis=1)
            candidates=np.flatnonzero((rr<=res[idx]+plan['residual_envelope_um']+1e-12)&(f.component==f.component[edge[idx]]))
            eligible=[(float(rr[s]),int(s),float(tt[s]),f.attachment_distance(edge[idx],frac[idx],s,tt[s])) for s in candidates]
            eligible=[x for x in eligible if x[3]>=plan['minimum_path_separation_um']]
            assert len(eligible)==count[idx]
            if eligible:
                er,ee,et,ed=min(eligible)
                assert ee==ae[idx]
                np.testing.assert_allclose([er,et,ed],[ar[idx],at[idx],separation[idx]],atol=1e-9,rtol=0)
            reference.append(dict(unique_contact_index=int(idx),eligible_segments=len(eligible)))
        # Both maps share one expanded forest: only attachments change between arms.
        p,l,r,mapping,order=split_at_attachments(f.parent,f.length,f.radius,np.r_[edge,ae],np.r_[frac,at])
        orig_nodes,alt_nodes=np.split(mapping,2)
        np.testing.assert_allclose(l.sum(),f.length.sum(),atol=1e-8,rtol=0)
        e=electrotonic_lengths(p,l,r)
        np.testing.assert_allclose(e.sum(),electrotonic_lengths(f.parent,f.length,f.radius).sum(),atol=1e-8,rtol=0)
        inv=geometry[pre+'contact_unique_index']
        output_unique=baseline[pre+'output_unique_geometry_index'];output_inverse=baseline[pre+'output_contact_inverse']
        source_ids=[baseline[pre+'source_contact_indices_'+name] for name in plan['source_regions']]
        response=np.empty((2,4,3,len(output_unique)))
        cases=[];control_errors=[]
        for mi,dist in enumerate([l,e]):
            scale=plan['length_parameter_um'] if mi==0 else plan['length_parameter_um']*e.sum()/l.sum()
            # Two source maps, each observed through both output maps.
            for source_alt in [False,True]:
                srcmap=alt_nodes if source_alt else orig_nodes
                mass=np.zeros((len(p),3))
                for j,ids in enumerate(source_ids): np.add.at(mass[:,j],srcmap[inv[ids]],1/len(ids))
                np.testing.assert_allclose(mass.sum(0),1,atol=1e-10,rtol=0)
                field=exponential_sum(p,order,dist,scale,mass)
                assert np.isfinite(field).all() and field.min()>=0 and field.max()<=1+1e-10
                for output_alt in [False,True]:
                    vi=2*int(source_alt)+int(output_alt)
                    outmap=alt_nodes if output_alt else orig_nodes
                    response[mi,vi]=field[outmap[output_unique]].T
            control_error=float(np.max(np.abs(response[mi,0]-baseline[pre+'coupling'][mi,1])))
            assert control_error<1e-10;control_errors.append(control_error)
            for vi,variant in enumerate(plan['variants']):
                for j,region in enumerate(plan['source_regions']):
                    y=response[mi,vi,j][output_inverse];x=response[mi,0,j][output_inverse];delta=y-x
                    cases.append(dict(metric=plan['metrics'][mi],variant=variant,source_region=region,
                        contact_mean=float(y.mean()),control_mean=float(x.mean()),relative_mean_change=float(y.mean()/x.mean()-1),
                        contact_mean_absolute_change=float(np.abs(delta).mean()),
                        contact_rms_change=float(np.sqrt(np.mean(delta**2))),
                        contact_absolute_change_quantiles=np.quantile(np.abs(delta),[0,.5,.95,1]).tolist()))
        incoming=geometry[pre+'incoming'];kc=geometry[pre+'counterpart_is_kc']
        cohorts={}
        groups={'all_retained_contacts':np.arange(len(inv)),
                'KC_to_APL':np.flatnonzero(incoming&kc),'APL_to_KC':np.flatnonzero(~incoming&kc)}
        groups.update({name+'_input':ids for name,ids in zip(plan['source_regions'],source_ids)})
        for name,ids in groups.items():
            selected=inv[ids];is_changed=changed[selected];moved=selected[is_changed]
            cohorts[name]=dict(contacts=len(ids),changed_contacts=int(is_changed.sum()),changed_fraction=float(is_changed.mean()),
                moved_path_quantiles_um=np.quantile(separation[moved],[0,.5,.95,1]).tolist() if len(moved) else [],
                moved_extra_residual_quantiles_um=np.quantile(ar[moved]-res[moved],[0,.5,.95,1]).tolist() if len(moved) else [])
        for k,val in dict(alternative_edge=ae,alternative_fraction=at,alternative_residual_um=ar,
                           path_separation_um=separation,eligible_segment_count=count,coupling=response).items():stored[pre+k]=val
        results.append(dict(body_id=body,unique_contacts=len(points),changed_unique_contacts=int(changed.sum()),
                            expanded_nodes=len(p),cohorts=cohorts,reference_points=reference,
                            control_max_errors=control_errors,cases=cases))
    np.savez_compressed(ARRAYS,**stored)
    result=dict(status='passed_declared_attachment_sensitivity',completed_utc=datetime.now(timezone.utc).isoformat(),
                wall_seconds=time.perf_counter()-begun,plan=pin(PLAN),arrays=pin(ARRAYS),cells=results,
                scope='48 static probes including 12 controls; deterministic same-component reassignment is a stress test, not estimated anatomical uncertainty.',
                physiological_fit=False,neural_network_run=False,runtime_changed=False)
    with OUT.open('x') as out: json.dump(result,out,indent=2,allow_nan=False);out.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cells'},indent=2))


if __name__=='__main__':main()
