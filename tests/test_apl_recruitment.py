import numpy as np
from scipy.integrate import solve_ivp
from fruitfly.apl_conductance import passive_circuit
from fruitfly.apl_recruitment import pulse, step, _gates


def test_shared_gate_is_nested():
    for m in [0.,.2,1.]:
        _,z=_gates(.4,.3,m,.12,.2,.6,.6)
        np.testing.assert_allclose(z,m+(.3-m)*np.exp(-.12/.6),atol=1e-15)


def test_continuous_ode_and_same_observation_clock():
    circuit=passive_circuit([65.,45.],[.002,.03]);pars=np.array([40.,1.,.08,.05,.6,50.]);rev=-40.
    def rhs(t,y,current):
        v,d,h,z=y;cs,cd,gl,gc=circuit;gf,gs,th,ton,toff,scale=pars;m=max(v,0)/(scale+max(v,0));g=gf*m*h+gs*z
        return [1000*(current-gl*v-gc*(v-d)-g*(v-rev))/cs,1000*gc*(v-d)/cd,(1-m-h)/th,m*(1-z)/ton-(1-m)*z/toff]
    on=solve_ivp(lambda t,y:rhs(t,y,2000),[0,.75],[0,0,1,0],rtol=1e-10,atol=1e-11,method='DOP853',dense_output=True)
    off=solve_ivp(lambda t,y:rhs(t,y,0),[.75,3.55],on.y[:,-1],rtol=1e-10,atol=1e-11,method='DOP853',dense_output=True)
    t=np.arange(35500)/10000;ref=np.concatenate([on.sol(t[:7500])[0],off.sol(t[7500:])[0]]).reshape(-1,10).mean(axis=1)
    errors=[]
    for dt in [.00005,.000025]:
        pred,_,_=pulse(circuit,pars,rev,dt=dt);errors.append(np.sqrt(np.mean((pred-ref)**2)))
    assert errors[1]<.35*errors[0] and errors[0]<.01


def test_bound_gates_and_decay_without_reset():
    c=passive_circuit([65.,45.],[.002,.03]);p=np.array([100.,20.,.01,.01,3.,5.]);rev=-25.
    for dt in [.00005,.001,.1]:
        y=np.array([0.,0.,1.,0.])
        for i in range(100):
            y=step(y,2000. if i<20 else 0.,dt,c,p,rev)
            assert min(y[:2])>=rev-1e-10 and np.all(y[2:]>=-1e-14) and np.all(y[2:]<=1+1e-14)
    for _ in range(120000):y=step(y,0.,.001,c,p,rev)
    np.testing.assert_allclose(y,[0,0,1,0],atol=1e-10)
