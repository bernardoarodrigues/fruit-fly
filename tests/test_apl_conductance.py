import numpy as np
from scipy.integrate import solve_ivp
from fruitfly.apl_conductance import passive_circuit, pulse, step


def test_passive_impedance():
    r=np.array([65.,45.]);tau=np.array([.002,.03]);cs,cd,gl,gc=passive_circuit(r,tau)
    for s in [0.,1j,10j,100j,1000j]:
        z=1/(s*cs/1000+gl+gc-gc*gc/(s*cd/1000+gc))
        np.testing.assert_allclose(z,np.sum(r/1000/(1+s*tau)),rtol=1e-12)


def test_ode_convergence_and_autonomous_recovery():
    circuit=passive_circuit([65.,45.],[.002,.03]);pars=np.array([20.,1.,.2,.6,20.]);rev=-40.
    def rhs(t,y,current):
        v,d,h,z=y;cs,cd,gl,gc=circuit;gf,gs,th,tz,scale=pars;m=max(v,0)/(scale+max(v,0));g=gf*m*h+gs*z
        return [1000*(-gl*v-gc*(v-d)-g*(v-rev)+current)/cs,1000*gc*(v-d)/cd,((1-m)-h)/th,(m-z)/tz]
    on=solve_ivp(lambda t,y:rhs(t,y,2000.),[0,.75],[0,0,1,0],method='DOP853',rtol=1e-10,atol=1e-11,dense_output=True)
    off=solve_ivp(lambda t,y:rhs(t,y,0.),[.75,3.55],on.y[:,-1],method='DOP853',rtol=1e-10,atol=1e-11,dense_output=True)
    errors=[]
    for dt in [.0001,.00005]:
        pred,state,minimum=pulse(circuit,pars,rev,True,dt=dt)
        t=np.arange(round(3.55/dt))*dt;ref=np.empty(len(t));mask=t<.75
        ref[mask]=on.sol(t[mask])[0];ref[~mask]=off.sol(t[~mask])[0]
        ref=ref.reshape(-1,round(.001/dt)).mean(axis=1)
        errors.append(np.sqrt(np.mean((pred-ref)**2)))
        assert minimum>=rev and pred[800:1500].min()<0 and state[3]>0
    assert errors[1]<.6*errors[0] and errors[1]<.08


def test_reversal_bound_and_gate_invariance():
    circuit=passive_circuit([65.,45.],[.002,.03]);pars=np.array([100.,20.,.01,.05,5.]);rev=-25.
    for dt in [.0001,.01,1.]:
        y=np.array([0.,0.,1.,0.])
        for i in range(100):
            y=step(y,2000. if i<10 else 0.,dt,circuit,pars,rev,True)
            assert min(y[:2])>=rev-1e-12 and 0<=y[2]<=1 and 0<=y[3]<=1
