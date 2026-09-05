import numpy as np
from scipy.integrate import quad
from scripts.apl_reporter_filter import linear_filter,profile_gain


def test_exact_linear_forcing_and_subdivision():
    t=np.array([0.,.3,1.1,2.]);u=np.array([.2,1.,-.3,.4]);q=np.array([0.,.1,.3,.5,1.1,1.7,2.])
    for tau in [.01,.2,3.,1000.]:
        got=linear_filter(t,u,q,tau)
        expected=[]
        for x in q:
            breaks=np.r_[t[t<x],x]
            expected.append(sum(quad(lambda s:np.exp(-(x-s)/tau)*np.interp(s,t,u)/tau,a,b,epsabs=1e-12)[0]
                                for a,b in zip(breaks[:-1],breaks[1:])))
        np.testing.assert_allclose(got,expected,atol=2e-12,rtol=2e-12)
        fine=np.unique(np.r_[t,(t[:-1]+t[1:])/2])
        np.testing.assert_allclose(got,linear_filter(fine,np.interp(fine,t,u),q,tau),atol=2e-12,rtol=2e-12)
    np.testing.assert_array_equal(linear_filter(t,u,q,0),np.interp(q,t,u))


def test_nonnegative_bound_and_gain_solution():
    q=np.linspace(0,10,101)
    for tau in [.001,.5,1000.]:
        y=linear_filter([0,2,4,10],[0,1,0,0],q,tau)
        assert y.min()>=0 and y.max()<=1
    x=np.array([.1,.4,.8]);y=2*x
    gain,error=profile_gain(x,y)
    assert abs(gain-2)<1e-14 and error<1e-25
    assert profile_gain(x,-y)[0]==0
