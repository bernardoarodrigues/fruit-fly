#!/usr/bin/env python3
"""Complete static male APL propagation batch, independent of neural runtime."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time
import numpy as np
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from apl_spatial_operator import split_at_attachments,electrotonic_lengths,exponential_sum

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/apl-spatial-operator-plan.json'
OUT=ROOT/'validation/apl-spatial-operator-results.json'
ARRAYS=ROOT/'validation/apl-spatial-operator-arrays.npz'


def pin(p):
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def main():
    if OUT.exists() or ARRAYS.exists(): raise FileExistsError('Preserve completed batch')
    plan=json.loads(PLAN.read_text())
    for p in plan['source_pins']: assert pin(ROOT/p['path'])['sha256']==p['sha256']
    started=time.perf_counter()
    data=np.load(ROOT/plan['geometry'],allow_pickle=False)
    table=pq.read_table(ROOT/plan['contacts'],columns=['source_row_ordinal','primary_post']).to_pandas().set_index('source_row_ordinal')
    assert table.index.is_unique
    rng=np.random.default_rng(plan['seed'])
    stored={};summaries=[];reference_checks=0
    for body,side in [(10540,'R'),(10977,'L')]:
        pre=f'b{body}_'
        parent=data[pre+'parent'];xyz=data[pre+'xyz_um'];radius=data[pre+'radius_um']
        length=np.linalg.norm(xyz-xyz[parent],axis=1)
        p,l,r,point_nodes,order=split_at_attachments(parent,length,radius,
                data[pre+'projection_edge_child_index'],data[pre+'projection_fraction'])
        assert abs(l.sum()-length.sum())<plan['geometry_atol']
        original_e=electrotonic_lengths(parent,length,radius)
        e=electrotonic_lengths(p,l,r)
        assert abs(e.sum()-original_e.sum())<plan['geometry_atol']
        inverse=data[pre+'contact_unique_index']
        incoming=data[pre+'incoming'];kc=data[pre+'counterpart_is_kc']
        source_rows=data[pre+'source_row_ordinal']
        roi=table.loc[source_rows,'primary_post'].to_numpy()
        mass=np.zeros((len(p),3))
        source_counts=[]
        for j,name in enumerate(plan['source_regions']):
            selected=np.flatnonzero(incoming & kc & (roi==f'{name}({side})'))
            assert len(selected)>0
            np.add.at(mass[:,j],point_nodes[inverse[selected]],1/len(selected))
            source_counts.append(len(selected))
            stored[pre+'source_contact_indices_'+name]=selected
        np.testing.assert_allclose(mass.sum(0),np.ones(3),atol=plan['response_atol'],rtol=0)
        out_contact=np.flatnonzero(~incoming & kc)
        unique_out,output_inverse=np.unique(inverse[out_contact],return_inverse=True)
        out_nodes=point_nodes[unique_out]
        queries=rng.choice(len(out_nodes),plan['reference_outputs'],replace=False)
        node_components=np.full(len(p),-1,dtype=int)
        roots=np.flatnonzero(p==np.arange(len(p)))
        for ci,root in enumerate(roots): node_components[root]=ci
        for node in order:
            if p[node]!=node: node_components[node]=node_components[p[node]]
        expected_infinite=np.zeros_like(mass)
        for ci in range(len(roots)):
            mask=node_components==ci
            expected_infinite[mask]=mass[mask].sum(0)
        infinite=exponential_sum(p,order,l,float('inf'),mass)
        infinite_error=float(np.abs(infinite-expected_infinite).max())
        assert infinite_error<plan['response_atol'];reference_checks+=1
        # Refinement adds a midpoint to every positive-length expanded segment.
        pp,ll,rr,unused,oo=split_at_attachments(p,l,r,np.arange(len(p)),np.full(len(p),.5))
        fine_mass=np.zeros((len(pp),3));fine_mass[:len(p)]=mass
        ee=electrotonic_lengths(pp,ll,rr)
        assert abs(ll.sum()-l.sum())<plan['geometry_atol']
        assert abs(ee.sum()-e.sum())<plan['geometry_atol']
        responses=np.empty((2,3,3,len(out_nodes)))
        cases=[];max_ref=0.;refinement=[]
        for mi,(metric,dist) in enumerate([('constant_diameter',l),('source_radius',e)]):
            indices=np.flatnonzero(p!=np.arange(len(p)))
            adjacency=coo_matrix((np.r_[dist[indices],dist[indices]],
                                  (np.r_[indices,p[indices]],np.r_[p[indices],indices])),shape=(len(p),len(p))).tocsr()
            reference_dist=dijkstra(adjacency,directed=False,indices=out_nodes[queries])
            for li,lam in enumerate(plan['length_parameters_um']):
                scale=lam if mi==0 else lam*e.sum()/l.sum()
                before=time.perf_counter()
                field=exponential_sum(p,order,dist,scale,mass)
                elapsed=time.perf_counter()-before
                assert np.isfinite(field).all() and field.min()>=0 and field.max()<=1+plan['response_atol']
                expected=np.exp(-reference_dist/scale)@mass
                error=float(np.abs(field[out_nodes[queries]]-expected).max())
                assert error<=plan['response_atol'];max_ref=max(max_ref,error)
                reference_checks+=expected.size
                responses[mi,li]=field[out_nodes].T
                for j,region in enumerate(plan['source_regions']):
                    contact_field=field[out_nodes,j][output_inverse]
                    cases.append(dict(metric=metric,length_parameter_um=lam,source_region=region,
                        source_contacts=source_counts[j],scale=scale,scale_units='um' if mi==0 else 'sqrt(um)',
                        output_contact_mean=float(contact_field.mean()),output_unique_mean=float(field[out_nodes,j].mean()),
                        output_contact_quantiles=np.quantile(contact_field,[0,.5,.95,1]).tolist(),
                        reference_max_error=error,three_footprint_operator_seconds=elapsed))
                if lam==plan['refinement_length_um']:
                    fine_dist=ll if mi==0 else ee
                    # Preserve the fixed original metric scale when refining.
                    fine=exponential_sum(pp,oo,fine_dist,scale,fine_mass)
                    err=float(np.abs(fine[:len(p)]-field).max())
                    assert err<=plan['response_atol'];reference_checks+=1
                    refinement.append(dict(metric=metric,length_parameter_um=lam,max_original_node_error=err))
        for key,value in dict(parent=p,length_um=l,radius_um=r,point_nodes=point_nodes,
                              output_unique_geometry_index=unique_out,output_contact_indices=out_contact,
                              output_contact_inverse=output_inverse,coupling=responses).items():
            stored[pre+key]=value
        summaries.append(dict(body_id=body,original_nodes=len(parent),expanded_nodes=len(p),refined_nodes=len(pp),
                              components=len(roots),source_regions=plan['source_regions'],source_counts=source_counts,
                              total_length_um=float(l.sum()),total_electrotonic_length_sqrt_um=float(e.sum()),
                              global_length_to_electrotonic_ratio_sqrt_um=float(l.sum()/e.sum()),
                              output_contacts=len(out_contact),unique_output_sites=len(unique_out),
                              max_direct_sum_error=max_ref,infinite_scale_error=infinite_error,
                              refinement=refinement,cases=cases))
    np.savez_compressed(ARRAYS,**stored)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started,
                status='passed_static_spatial_operator_benchmark',plan=pin(PLAN),arrays=pin(ARRAYS),
                reference_checks=reference_checks,skeletons=summaries,source_pins=plan['source_pins'],
                physiological_fit=False,neural_network_run=False,runtime_changed=False,
                scope='36 static anatomical probes. ROI-wide unit-total input is not an ATP puff or measured KC spiking.')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(status=result['status'],wall_seconds=result['wall_seconds'],
                         reference_checks=reference_checks,arrays=result['arrays'],
                         cells=[{k:v for k,v in s.items() if k!='cases'} for s in summaries]),indent=2))


if __name__=='__main__':main()
