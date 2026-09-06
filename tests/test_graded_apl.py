import numpy as np
import pytest
from scipy.integrate import solve_ivp
from fruitfly.graded_apl import GradedAPLState,advance_state,post_offset_voltage


@pytest.mark.parametrize('outward_tau',[.002,.002*(1+1e-12),.4])
def test_exact_update_against_ode_and_subdivision(outward_tau):
    tau=np.array([.002,.03]);r=np.array([60.,40.]);x=np.array([5.,-2.]);initial=GradedAPLState(x,30.)
    kwargs=dict(input_current_pA=20.,outward_target_pA=12.,resistance_MOhm=r,passive_tau_s=tau,outward_tau_s=outward_tau)
    exact=advance_state(initial,dt_s=.08,**kwargs)
    numerical=solve_ivp(lambda t,y:np.r_[(-y[:2]+r*(20-y[2])/1000)/tau,(12-y[2])/outward_tau],
                        [0,.08],np.r_[x,30.],rtol=1e-11,atol=1e-12)
    np.testing.assert_allclose(np.r_[exact.voltage_components_mV,exact.outward_current_pA],numerical.y[:,-1],atol=2e-10)
    split=initial
    for dt in [.007,.013,.06]:split=advance_state(split,dt_s=dt,**kwargs)
    np.testing.assert_allclose(np.r_[exact.voltage_components_mV,exact.outward_current_pA],np.r_[split.voltage_components_mV,split.outward_current_pA],atol=1e-12)


def test_zero_input_relaxes_and_vector_recovery_matches_state():
    x=np.array([4.,2.]);r=np.array([70.,30.]);tau=np.array([.003,.03]);state=GradedAPLState(x,25.)
    times=np.array([0,.01,.1,1.,100.])
    kwargs=dict(input_current_pA=0.,outward_target_pA=0.,resistance_MOhm=r,passive_tau_s=tau,outward_tau_s=.4)
    values=[advance_state(state,dt_s=t,**kwargs) for t in times]
    np.testing.assert_allclose(post_offset_voltage(times,x,r,tau,25.,.4),[v.voltage_components_mV.sum() for v in values],atol=1e-12)
    assert np.max(np.abs(values[-1].voltage_components_mV))<1e-50 and values[-1].outward_current_pA<1e-50
