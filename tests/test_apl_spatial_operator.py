import numpy as np
import pytest
from scipy.integrate import quad
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scripts.apl_spatial_operator import split_at_attachments, electrotonic_lengths, exponential_sum, forest_order


def test_taper_and_subdivision_match_integral():
    for r0,r1 in [(1.,1.),(.1,4.),(4.,.1),(1.,1.+1e-12)]:
        for count in [1,2,7,100]:
            p,l,r,n,o=split_at_attachments(np.array([0,0]),np.array([0.,13.]),
                                          np.array([r1,r0]),np.ones(count+1,dtype=int),np.linspace(0,1,count+1))
            value=electrotonic_lengths(p,l,r).sum()
            expected=quad(lambda x:1/np.sqrt(r0+(r1-r0)*x/13),0,13,epsabs=1e-12)[0]
            assert value==pytest.approx(expected,abs=1e-11)
            assert l.sum()==pytest.approx(13.,abs=1e-13)


@pytest.mark.parametrize('scale',[.01,1.,20.,float('inf')])
def test_tree_messages_equal_full_pairwise_kernel(scale):
    p=np.array([0,0,1,1,4,4]); l=np.array([0.,2.,3.,4.,0.,1.]);r=np.array([1.,.5,1.,2.,1.,1.])
    pp,ll,rr,nodes,order=split_at_attachments(p,l,r,np.array([2,3,1,1,4]),np.array([.3,.7,.25,.75,0.]))
    metric=electrotonic_lengths(pp,ll,rr)
    ix=np.flatnonzero(pp!=np.arange(len(pp)))
    adj=coo_matrix((np.r_[metric[ix],metric[ix]],(np.r_[ix,pp[ix]],np.r_[pp[ix],ix])),shape=(len(pp),len(pp))).tocsr()
    distances=dijkstra(adj,directed=False)
    kernel=np.exp(-distances/scale) if np.isfinite(scale) else np.isfinite(distances).astype(float)
    mass=np.zeros((len(pp),2));mass[nodes[0],0]=.2;mass[nodes[1],0]=.8;mass[nodes[4],1]=1.
    result=exponential_sum(pp,order,metric,scale,mass)
    np.testing.assert_allclose(result,kernel@mass,atol=2e-14,rtol=2e-14)
    assert (result[:4,1]==0).all()
    assert result.min()>=0 and result.max()<=1+1e-14


def test_repeated_contact_mass_and_zero_length_edges():
    p,l,r,n,o=split_at_attachments(np.array([0,0]),np.array([0.,4.]),np.ones(2),
                                  np.array([1,1,1]),np.array([.5,.5,.5]))
    mass=np.bincount(n,minlength=len(p)).astype(float)
    assert len(set(n))==1
    value=exponential_sum(p,o,l,2.,mass)
    assert value[n[0]]==pytest.approx(3.)
    assert value[0]==pytest.approx(3*np.exp(-1))
    p=np.array([0,0,1]);l=np.array([0.,0.,2.])
    np.testing.assert_allclose(exponential_sum(p,forest_order(p),l,2.,np.array([1.,0.,0.])),[1,1,np.exp(-1)])
