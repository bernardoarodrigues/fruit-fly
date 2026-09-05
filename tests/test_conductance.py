from dataclasses import replace

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from fruitfly.conductance import (ConductanceDrive, ConductanceNetwork,
                                  ConductanceParameters, SynapticEvents)
from fruitfly.neural import LIFNetwork, SparseDrive


def network(edges=(), n=3, parameters=None, seed=11):
    edges = sorted(edges)
    indptr = np.zeros(n + 1, dtype=np.int64)
    for source, _, _ in edges:
        indptr[source + 1] += 1
    np.cumsum(indptr, out=indptr)
    return ConductanceNetwork(np.arange(n, dtype=np.int64)+100,
                              indptr, np.array([e[1] for e in edges], dtype=np.int32),
                              np.array([e[2] for e in edges], dtype=np.float32),
                              parameters=parameters, seed=seed)


def test_constant_conductance_equilibrium_analytic():
    params = replace(ConductanceParameters(), excitatory_tau_ms=1e12, inhibitory_tau_ms=1e12,
                     threshold_mv=-1)
    net = network(n=1, parameters=params)
    ge, gi = 3., 4.
    net.excitatory_g[0], net.inhibitory_g[0] = ge, gi
    equilibrium = (params.resting_mv + ge * params.excitatory_reversal_mv
                   + gi * params.inhibitory_reversal_mv) / (1 + ge + gi)
    expected = equilibrium + (params.resting_mv-equilibrium) * np.exp(-10*(1+ge+gi)/params.membrane_tau_ms)
    assert net.advance(10).total_spikes == 0
    assert net.voltage_mv[0] == pytest.approx(expected, abs=1e-10)


@pytest.mark.parametrize('method',['exponential','pade22'])
def test_voltage_stays_between_reversals_under_arbitrary_conductance_events(method):
    net = network(n=3,parameters=replace(ConductanceParameters(),voltage_method=method))
    net.advance(10,events=SynapticEvents([0,1,2],[0,0,0],1e8,[False,True,False]))
    assert np.all(net.voltage_mv >= net.parameters.inhibitory_reversal_mv)
    assert np.all(net.voltage_mv <= net.parameters.excitatory_reversal_mv)
    net.advance(10,events=SynapticEvents([0,1,2],[10,10,10],1e8,[True,False,True]))
    assert np.all(net.voltage_mv >= net.parameters.inhibitory_reversal_mv)
    assert np.all(net.voltage_mv <= net.parameters.excitatory_reversal_mv)
    assert np.all(np.isfinite(net.voltage_mv))


@pytest.mark.parametrize('method',['exponential','pade22'])
def test_midpoint_integrator_converges_to_independent_ode_solution(method):
    p = replace(ConductanceParameters(), threshold_mv=-1,voltage_method=method)
    def ode(t,state):
        v, ge, gi = state
        return [(p.resting_mv-v+ge*(p.excitatory_reversal_mv-v)+gi*(p.inhibitory_reversal_mv-v))/p.membrane_tau_ms,
                -ge/p.excitatory_tau_ms,-gi/p.inhibitory_tau_ms]
    reference = solve_ivp(ode,[0,20],[-52,3,1],rtol=1e-12,atol=1e-13).y[:,-1]
    errors=[]
    for step in [.2,.1,.05]:
        net=network(n=1,parameters=replace(p,dt_ms=step))
        net.excitatory_g[0],net.inhibitory_g[0]=3,1
        net.advance(20)
        errors.append(abs(net.voltage_mv[0]-reference[0]))
        np.testing.assert_allclose([net.excitatory_g[0],net.inhibitory_g[0]],reference[1:],atol=1e-12)
    assert errors[1] < errors[0]/3.5
    assert errors[2] < errors[1]/3.5
    assert errors[2] < 1e-4


def test_pade_matches_reference_in_controlled_network_with_stiff_inputs():
    edges=[(0,1,52),(1,2,-20),(2,0,20)]
    exact=network(edges)
    fast=network(edges,parameters=replace(ConductanceParameters(),voltage_method='pade22'))
    drive=ConductanceDrive([0],rates_hz=150)
    a=exact.advance(100,drive=drive,events=SynapticEvents([1],[10],1000,inhibitory=True))
    b=fast.advance(100,drive=drive,events=SynapticEvents([1],[10],1000,inhibitory=True))
    np.testing.assert_array_equal(a.indices,b.indices)
    np.testing.assert_array_equal(a.times_ms,b.times_ms)
    np.testing.assert_allclose(exact.voltage_mv,fast.voltage_mv,atol=1e-6,rtol=0)


def test_synaptic_impulse_uses_conductance_and_has_one_tick_causality():
    net=network(n=1)
    assert net.step(events=SynapticEvents([0],[0],1)).total_spikes == 0
    assert net.voltage_mv[0] == -52 and net.excitatory_g[0] == 1
    net.step()
    assert -52 < net.voltage_mv[0] < -45


def test_graph_delay_and_arrivals_during_refractory():
    net=network([(0,1,52)],n=2)
    net.voltage_mv[:]=-44
    output=net.step()
    assert output.total_spikes == 2
    net.advance(1.7)
    assert net.excitatory_g[1] == 0
    net.step() # graph event arrives at1.8ms during target's refractory period
    assert net.excitatory_g[1] == 1
    assert net.voltage_mv[1] == -52
    net.step()
    assert 0 < net.excitatory_g[1] < 1
    assert net.voltage_mv[1] == -52


def test_synapses_decay_and_are_not_reset_when_neuron_spikes():
    net=network(n=1)
    net.voltage_mv[0]=-44
    net.excitatory_g[0]=3
    net.inhibitory_g[0]=1
    assert net.step().total_spikes==1
    assert net.excitatory_g[0]==pytest.approx(3*np.exp(-.1/5))
    assert net.inhibitory_g[0]==pytest.approx(np.exp(-.1/5))
    net.step()
    assert net.voltage_mv[0] == -52
    assert net.excitatory_g[0]==pytest.approx(3*np.exp(-.2/5))


def test_poisson_never_disables_refractory_or_jumps_voltage():
    net=network(n=1)
    legacy_drive=SparseDrive([0],rates_hz=10000) # disable_refractory=True in this dataclass
    assert net.step(drive=legacy_drive).total_spikes == 0
    assert net.voltage_mv[0] == -52
    assert net.excitatory_g[0] == 1
    result=net.advance(100,drive=legacy_drive)
    assert result.total_spikes > 10
    assert np.min(np.diff(result.times_ms)) >= 2.2-1e-10
    assert net.refractory_ticks[0] == 22
    with pytest.raises(ValueError,match='Voltage jumps'):
        net.step(drive=SparseDrive([0],rates_hz=150,poisson_weight_mv=68.75))


def test_input_replay_and_poisson_are_chunk_invariant():
    edges=[(0,1,30),(1,2,-25),(2,0,20)]
    whole,chunked=network(edges),network(edges)
    drive=ConductanceDrive([0],rates_hz=180,event_gleak=2)
    first=whole.advance(100,drive=drive,events=SynapticEvents([0,0,1],[0,20,99.9],[1,2,4]))
    a=chunked.advance(20,drive=drive,events=SynapticEvents([0],[0],1))
    b=chunked.advance(80,drive=drive,events=SynapticEvents([0,1],[20,99.9],[2,4]))
    np.testing.assert_array_equal(first.indices,np.concatenate([a.indices,b.indices]))
    np.testing.assert_array_equal(first.times_ms,np.concatenate([a.times_ms,b.times_ms]))
    np.testing.assert_array_equal(whole.voltage_mv,chunked.voltage_mv)
    np.testing.assert_array_equal(whole.excitatory_g,chunked.excitatory_g)


def test_checkpoint_persists_both_conductances_pending_events_and_rng(tmp_path):
    edges=[(0,1,52),(1,2,-25)]
    original=network(edges)
    original.voltage_mv[0]=-44
    original.inhibitory_g[2]=1
    drive=ConductanceDrive([0],rates_hz=170)
    original.advance(.5,drive=drive)
    path=tmp_path/'conductance.npz'
    original.save_checkpoint(path)
    restored=network(edges,seed=999)
    restored.load_checkpoint(path)
    a=original.advance(50,drive=drive)
    b=restored.advance(50,drive=drive)
    np.testing.assert_array_equal(a.times_ms,b.times_ms)
    np.testing.assert_array_equal(original.voltage_mv,restored.voltage_mv)
    np.testing.assert_array_equal(original.excitatory_g,restored.excitatory_g)
    np.testing.assert_array_equal(original.inhibitory_g,restored.inhibitory_g)
    baseline=LIFNetwork(original.neuron_ids,original.indptr,original.targets,original.weights)
    with pytest.raises(ValueError):
        restored.load_state_dict(baseline.state_dict())


def test_conductance_checkpoint_rejects_nonfinite_current_atomically():
    net=network()
    state=net.state_dict()
    state['current_mv'][0]=np.nan
    with pytest.raises(ValueError,match='non-finite'):
        net.load_state_dict(state)
    assert net.time_ms==0 and np.all(net._current_mv==0)


def test_ablation_keeps_graph_and_recording_semantics():
    net=network([(0,1,52)],n=2)
    net.voltage_mv[0]=-44
    net.ablate([0])
    result=net.advance(10,outputs=[])
    assert result.total_spikes == 1 and len(result.indices) == 0
    assert result.traversed_edges == 0 and net.excitatory_g[1] == 0


@pytest.mark.parametrize('event',[SynapticEvents([0],[-.1]),SynapticEvents([0],[1]),
                                 SynapticEvents([0],[.15]),SynapticEvents([3],[0]),
                                 SynapticEvents([0],[0],-1)])
def test_invalid_events_do_not_advance(event):
    net=network()
    with pytest.raises(ValueError):
        net.advance(1,events=event)
    assert net.time_ms == 0
