import numpy as np
from scipy.integrate import solve_ivp
from scripts.apl_passive_kernels import plateau_factor,response,fit_modes


def test_finite_pulse_against_independent_ode():
    taus=np.array([.003,.17]);alpha=.37
    plateau=np.array([np.mean(1-np.exp(-np.arange(4000,5000)*.0001/tau)) for tau in taus])
    np.testing.assert_allclose([plateau_factor(tau) for tau in taus],plateau,rtol=1e-13)
    weights=np.array([alpha,1-alpha])/plateau
    on=solve_ivp(lambda t,x:(1-x)/taus,[0,.5],[0.,0.],rtol=1e-10,atol=1e-12,dense_output=True)
    off=solve_ivp(lambda t,x:-x/taus,[0,.2],on.y[:,-1],rtol=1e-10,atol=1e-12,dense_output=True)
    fit=dict(tau_fast_s=taus[0],tau_slow_s=taus[1],alpha=alpha)
    t=np.linspace(0,.2,201)
    np.testing.assert_allclose(response(t,fit),weights@on.sol(t),rtol=1e-8,atol=1e-9)
    np.testing.assert_allclose(response(t,fit,offset=True),weights@off.sol(t),rtol=1e-8,atol=1e-9)


def test_known_positive_mixture_recovered_without_offset_fit():
    t=np.arange(10,1000)/10000
    known=dict(tau_fast_s=.0025,tau_slow_s=.025,alpha=.45)
    fit=fit_modes(t,response(t,known),[.0005,.2])['two']
    assert fit['fit_mse']<1e-14
    np.testing.assert_allclose([fit['tau_fast_s'],fit['tau_slow_s'],fit['alpha']],list(known.values()),rtol=1e-5)
    np.testing.assert_allclose(response(t,fit,offset=True),response(t,known,offset=True),atol=1e-6)
