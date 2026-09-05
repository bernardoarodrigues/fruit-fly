#!/usr/bin/env python3
"""Audit both APL forests and attach retained contact endpoints as one batch."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from apl_skeleton_geometry import SkeletonForest

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'validation/male-apl-geometry-plan.json'
OUT=ROOT/'validation/male-apl-geometry-results.json'
ARRAYS=ROOT/'validation/male-apl-geometry-arrays.npz'


def pin(path):
    p=Path(path)
    return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def quantiles(values):
    return dict(zip(['min','median','p95','p99','max'],map(float,np.quantile(values,[0,.5,.95,.99,1]))))


def main():
    if OUT.exists() or ARRAYS.exists():
        raise FileExistsError('Preserve first completed geometry batch')
    started=time.perf_counter()
    plan=json.loads(PLAN.read_text())
    for p in plan['source_pins']:
        assert pin(ROOT/p['path'])['sha256']==p['sha256']
    neurons=pd.read_feather(ROOT/plan['neurons'])
    apl=neurons[neurons.type.eq('APL')]
    assert sorted(apl.bodyId.tolist())==plan['body_ids']
    kc=set(neurons.loc[neurons['class'].eq('Kenyon_Cell'),'bodyId'].astype(int))
    assert len(kc)==4064
    cols=['body_pre','body_post','source_row_ordinal','source_graph_index','target_graph_index',
          'x_pre','y_pre','z_pre','x_post','y_post','z_post']
    contacts=pq.read_table(ROOT/plan['contacts'],columns=cols).to_pandas()
    arrays={}
    summaries=[]
    checks=0
    rng=np.random.default_rng(plan['seed'])
    for body in plan['body_ids']:
        sk=SkeletonForest(ROOT/f'data/raw/male-apl-skeletons/{body}.swc')
        n=len(sk.ids)
        edge=np.flatnonzero(sk.parent!=np.arange(n))
        adjacency=coo_matrix((np.r_[sk.length[edge],sk.length[edge]],
                              (np.r_[edge,sk.parent[edge]],np.r_[sk.parent[edge],edge])),shape=(n,n)).tocsr()
        # Dijkstra independently checks LCA path lengths and disconnected roots.
        source_nodes=np.unique(np.r_[sk.roots,rng.choice(n,plan['reference_nodes'],replace=False)])
        references=dijkstra(adjacency,directed=False,indices=source_nodes)
        max_path_error=0.
        for row, i in enumerate(source_nodes):
            for j in np.unique(np.r_[sk.roots,rng.choice(n,plan['reference_nodes'],replace=False)]):
                a,b=sk.node_distance(i,j),float(references[row,j])
                assert np.isinf(a)==np.isinf(b)
                if np.isfinite(a):
                    max_path_error=max(max_path_error,abs(a-b))
                    assert abs(a-b)<=plan['path_atol_um']
                checks+=1
        endpoints=[]
        for incoming in (True,False):
            mask=contacts['body_post' if incoming else 'body_pre'].eq(body)
            subset=contacts.loc[mask]
            which='post' if incoming else 'pre'
            other='body_pre' if incoming else 'body_post'
            endpoints.append(dict(incoming=incoming,df=subset,other=subset[other].fillna(-1).to_numpy(np.int64),
                                  xyz=subset[[f'{ax}_{which}' for ax in 'xyz']].to_numpy(float)*.008))
        coords=np.concatenate([e['xyz'] for e in endpoints])
        unique,inverse=np.unique(coords,axis=0,return_inverse=True)
        projection,frac,residual=sk.attach(unique)
        assert np.isfinite(residual).all() and np.all((frac>=0)&(frac<=1))
        max_projection_error=0.
        # Brute-force all segments for independently selected contact points.
        choices=rng.choice(len(unique),plan['reference_points'],replace=False)
        vec=sk.xyz[sk.parent]-sk.xyz
        denom=np.einsum('ij,ij->i',vec,vec)
        for q in choices:
            point=unique[q]
            dot=((point-sk.xyz)*vec).sum(axis=1)
            t=np.minimum(1,np.maximum(0,np.divide(dot,denom,out=np.zeros(n),where=denom>0)))
            distances=np.sqrt(((sk.xyz+t[:,None]*vec-point)**2).sum(axis=1))
            err=abs(float(distances.min())-residual[q])
            max_projection_error=max(max_projection_error,err)
            assert err<=plan['projection_atol_um']
            checks+=1
        # Compare paths between distinct projected edges with independently
        # inserted graph vertices. Original segment edges retain equal length.
        attachment_errors=[]
        for _ in range(plan['reference_pairs']):
            i,j=rng.choice(len(unique),2,replace=False)
            ei,ej=int(projection[i]),int(projection[j])
            if ei==ej:
                expected=abs(frac[i]-frac[j])*sk.length[ei]
            else:
                g=adjacency.tocoo()
                rr=list(g.row); cc=list(g.col); dd=list(g.data)
                for new,e,t in [(n,ei,frac[i]),(n+1,ej,frac[j])]:
                    for end,w in [(e,t*sk.length[e]),(sk.parent[e],(1-t)*sk.length[e])]:
                        rr.extend([new,int(end)]);cc.extend([int(end),new]);dd.extend([w,w])
                augmented=coo_matrix((dd,(rr,cc)),shape=(n+2,n+2)).tocsr()
                expected=float(dijkstra(augmented,directed=False,indices=n)[n+1])
            got=sk.attachment_distance(ei,frac[i],ej,frac[j])
            assert np.isinf(got)==np.isinf(expected)
            if np.isfinite(got):
                attachment_errors.append(abs(got-expected))
                assert abs(got-expected)<=plan['path_atol_um']
            checks+=1
        prefix=f'b{body}_'
        for key,value in dict(node_ids=sk.ids,parent=sk.parent,xyz_um=sk.xyz,radius_um=sk.radius,
                              component=sk.component,root_distance_um=sk.root_distance,
                              unique_contact_xyz_um=unique,contact_unique_index=inverse,
                              projection_edge_child_index=projection,projection_fraction=frac,
                              projection_residual_um=residual).items():
            arrays[prefix+key]=value
        source_rows=np.concatenate([e['df'].source_row_ordinal.to_numpy(np.int64) for e in endpoints])
        other=np.concatenate([e['other'] for e in endpoints])
        incoming_flags=np.concatenate([np.full(len(e['df']),e['incoming']) for e in endpoints])
        counterpart_kc=np.array([x in kc for x in other])
        for key,value in dict(source_row_ordinal=source_rows,counterpart_body_id=other,
                              incoming=incoming_flags,counterpart_is_kc=counterpart_kc).items():
            arrays[prefix+key]=value
        groups=[]
        for incoming in (True,False):
            for iskc in (True,False):
                mask=(incoming_flags==incoming)&(counterpart_kc==iskc)
                ui=inverse[mask]
                groups.append(dict(incoming=incoming,counterpart_is_kc=iskc,contact_rows=int(mask.sum()),
                                   unique_locations=len(np.unique(ui)),
                                   residual_um=quantiles(residual[ui]) if len(ui) else None,
                                   attached_component_counts=np.bincount(sk.component[projection[ui]],minlength=len(sk.roots)).tolist()))
        annotation=apl.loc[apl.bodyId.eq(body)].iloc[0]
        summaries.append(dict(body_id=body,instance=annotation.instance,
                              status=annotation.status,statusLabel=annotation.statusLabel,
                              graph_index=int(annotation.name),nodes=n,edges=len(edge),
                              root_node_ids=sk.ids[sk.roots].tolist(),component_node_counts=np.bincount(sk.component).tolist(),
                              length_um=quantiles(sk.length[edge]),total_length_um=float(sk.length.sum()),
                              radius_um=quantiles(sk.radius),radius_floor_count=int((sk.radius==.256).sum()),
                              contact_rows=len(coords),unique_contact_locations=len(unique),groups=groups,
                              max_node_path_error_um=max_path_error,max_projection_error_um=max_projection_error,
                              max_attachment_path_error_um=max(attachment_errors,default=0.)))
    np.savez_compressed(ARRAYS,**arrays)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started,
                status='completed_geometry_and_contact_attachment_audit',plan=pin(PLAN),arrays=pin(ARRAYS),
                source_pins=plan['source_pins'],reference_checks=checks,skeletons=summaries,
                graph_changed=False,artificial_bridges_added=False,neural_simulation_run=False,
                electrical_model_calibrated=False,
                scope='All retained incoming APL endpoints and APL outgoing endpoints onto selected KC/APL targets; not every outgoing APL contact in the CNS.')
    with OUT.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
