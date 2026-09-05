import numpy as np
from scripts.apl_skeleton_geometry import SkeletonForest
from scripts.apl_attachment_sensitivity import node_distances,attachment_distances,nearby_nonlocal


def test_paths_and_candidate_search_against_scalar_brute_force(tmp_path):
    path=tmp_path/'test.swc'
    path.write_text('1 0 0 0 0 1 -1\n2 0 10 0 0 1 1\n3 0 0 1 0 1 1\n4 0 10 1 0 1 3\n5 0 10 0.2 0 1 -1\n')
    f=SkeletonForest(path,unit_um=1)
    i,j=np.meshgrid(np.arange(5),np.arange(5),indexing='ij')
    expected=np.array([[f.node_distance(a,b) for b in range(5)] for a in range(5)])
    np.testing.assert_allclose(node_distances(f,i,j),expected,atol=1e-13)
    pts=np.array([[10,.1,0],[7,.4,0],[3,.8,.2],[0,0,0],[10,.2,0],[30,30,1]])
    edge,t,res=f.attach(pts)
    for envelope in [.0,.512,1.]:
        got=nearby_nonlocal(f,pts,edge,t,res,envelope,10,chunk_size=2)
        for k,point in enumerate(pts):
            choices=[]
            for s in range(5):
                v=f.xyz[f.parent[s]]-f.xyz[s];q=v@v
                tt=np.clip((point-f.xyz[s])@v/q,0,1) if q else 0.
                rr=np.linalg.norm(point-f.xyz[s]-tt*v)
                dd=f.attachment_distance(edge[k],t[k],s,tt)
                np.testing.assert_allclose(attachment_distances(f,np.array([edge[k]]),np.array([t[k]]),np.array([s]),np.array([tt])),[dd],atol=1e-13)
                if f.component[s]==f.component[edge[k]] and rr<=res[k]+envelope+1e-12 and dd>=10:
                    choices.append((rr,s,tt,dd))
            assert got[4][k]==len(choices)
            if choices:
                rr,s,tt,dd=min(choices)
                np.testing.assert_allclose([got[0][k],got[1][k],got[2][k],got[3][k]],[s,tt,rr,dd],atol=1e-13)
            else:
                assert got[0][k]==edge[k] and got[1][k]==t[k] and got[3][k]==0
