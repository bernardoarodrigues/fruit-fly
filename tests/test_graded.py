from dataclasses import replace

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from fruitfly.conductance import ConductanceDrive, ConductanceNetwork, ConductanceParameters, SynapticEvents
from fruitfly.graded import GradedPopulationSpec, MixedNetwork


SPEC = GradedPopulationSpec((100,), resting_mv=-35, membrane_tau_ms=15,
    release_reference_mv=-35, release_baseline_hz_equiv=50,
    release_gain_hz_equiv_per_mv=5, release_max_hz_equiv=200, release_tau_ms=7)


def network(edges=(), *, n=3, specs=(SPEC,), parameters=None, seed=11, cls=MixedNetwork):
    edges = sorted(edges)
    indptr = np.zeros(n+1, dtype=np.int64)
    for source, _, _ in edges:
        indptr[source+1] += 1
    np.cumsum(indptr, out=indptr)
    kwargs = dict(parameters=parameters, seed=seed)
    if cls is MixedNetwork:
        kwargs["graded_populations"] = specs
    return cls(np.arange(n, dtype=np.int64)+100, indptr,
               np.array([e[1] for e in edges], dtype=np.int32),
               np.array([e[2] for e in edges], dtype=np.float32), **kwargs)


@pytest.mark.parametrize("method", ["exponential", "pade22"])
def test_no_graded_cells_exactly_preserves_spiking_backend(method):
    p = replace(ConductanceParameters(), voltage_method=method)
    edges = [(0, 1, 52), (1, 2, -23), (2, 0, 15)]
    base = network(edges, parameters=p, cls=ConductanceNetwork)
    mixed = network(edges, specs=(), parameters=p)
    for net in (base, mixed):
        net.voltage_mv[1] = -44
    drive = ConductanceDrive([0], rates_hz=230)
    events = SynapticEvents([0, 1, 1], [0, 15, 70], [1, 100, 2], [False, True, False])
    a, b = [net.advance(100, drive=drive, events=events) for net in (base, mixed)]
    np.testing.assert_array_equal(a.indices, b.indices)
    np.testing.assert_array_equal(a.times_ms, b.times_ms)
    assert a.total_spikes == b.total_spikes and a.traversed_edges == b.traversed_edges
    for name in ("voltage_mv", "excitatory_g", "inhibitory_g", "_rng_state"):
        np.testing.assert_array_equal(getattr(base, name), getattr(mixed, name))


def test_graded_cell_does_not_spike_or_reset_and_keeps_incoming_connections():
    net = network([(1, 0, 52)])
    # Graded rest is already above the global LIF threshold. It is not a spike.
    net.voltage_mv[1] = -44
    result = net.advance(10, events=SynapticEvents([0], [0], 100))
    assert 0 not in result.indices
    assert 1 in result.indices
    assert net.voltage_mv[0] > -35
    assert net.release_hz_equiv[0] > SPEC.release_baseline_hz_equiv
    assert net.excitatory_g[0] > 0
    assert net.last_spike_tick[0] == -(2**60)
    assert net.voltage_mv[0] <= net.parameters.excitatory_reversal_mv


def test_delayed_continuous_release_has_signed_edges_and_no_invented_prehistory():
    net = network([(0, 1, 52), (0, 2, -23)])
    assert np.all(net.excitatory_g == 0) and np.all(net.inhibitory_g == 0)
    assert net.release_hz_equiv[0] == 50
    net.advance(1.8)
    assert np.all(net.excitatory_g == 0) and np.all(net.inhibitory_g == 0)
    batch = net.step()  # time-zero release arrives at the end of the 1.8 ms tick
    assert batch.total_spikes == 0
    assert net.excitatory_g[1] == pytest.approx(50*.1/1000)
    assert net.inhibitory_g[2] == pytest.approx(50*.1/1000)
    assert net.voltage_mv[1] == net.voltage_mv[2] == -52
    net.step()
    assert net.voltage_mv[1] > -52 > net.voltage_mv[2]


def test_outgoing_suppression_blocks_queued_release_but_not_source_voltage_or_release():
    net = network([(0, 1, 52)])
    net.advance(.5)
    net.ablate([0])
    net.advance(10, drive=ConductanceDrive([0], current_mv=10))
    assert net.voltage_mv[0] > -35 and net.release_hz_equiv[0] > 50
    assert net.excitatory_g[1] == 0
    net.ablate([0], enabled=False)
    net.step()
    assert net.excitatory_g[1] > 0


def test_hyperpolarization_reduces_tonic_release_without_negative_conductance():
    params = replace(ConductanceParameters(), delay_ms=0, threshold_mv=-1)
    control, inhibited = [network([(0, 1, 52)], parameters=params) for _ in range(2)]
    control.advance(100)
    inhibited.advance(100, drive=ConductanceDrive([0], current_mv=-20))
    assert inhibited.release_hz_equiv[0] < .01
    assert 0 <= inhibited.excitatory_g[1] < control.excitatory_g[1]/100
    assert inhibited.voltage_mv[1] < control.voltage_mv[1]


def test_mixed_dynamics_converges_to_independent_continuous_ode():
    p = replace(ConductanceParameters(), delay_ms=0, threshold_mv=-1)
    # No spikes: independently solve sender voltage/release, postsynaptic ge/gi
    # and voltage. Release mass drives conductance as r/1000 event equivalents/ms.
    def ode(t, y):
        v0, r, ge, gi, ve, vi = y
        target = np.clip(50+5*(v0+35), 0, 200)
        return [(-35-v0+10)/15, (target-r)/7,
                -ge/5+r/1000, -gi/5+r/1000,
                (-52-ve+ge*(0-ve))/20, (-52-vi+gi*(-75-vi))/20]
    expected = solve_ivp(ode, [0, 50], [-35, 50, 0, 0, -52, -52],
                         rtol=1e-12, atol=1e-13).y[:, -1]
    errors = []
    for dt in (.2, .1, .05):
        net = network([(0, 1, 52), (0, 2, -23)], parameters=replace(p, dt_ms=dt))
        assert net.advance(50, drive=ConductanceDrive([0], current_mv=10)).total_spikes == 0
        actual = np.r_[net.voltage_mv[0], net.release_hz_equiv[0],
                       net.excitatory_g[1], net.inhibitory_g[2], net.voltage_mv[1:]]
        errors.append(float(np.max(np.abs(actual-expected))))
    # End-of-tick source injection is first order, unlike isolated midpoint LIF.
    assert errors[1] < errors[0]/1.8 and errors[2] < errors[1]/1.8
    assert errors[2] < .03


def test_chunking_checkpoint_reset_and_recording_do_not_change_mixed_dynamics(tmp_path):
    edges = [(0, 1, 52), (1, 2, 30), (2, 0, -23)]
    whole, split = [network(edges) for _ in range(2)]
    drive = ConductanceDrive([0, 1], rates_hz=[0, 120], current_mv=[5, 0])
    a = whole.advance(40, drive=drive)
    first = split.advance(7.3, drive=drive)
    path = tmp_path/"mixed.npz"
    split.save_checkpoint(path)
    restored = network(edges, seed=999)
    restored.load_checkpoint(path)
    second = restored.advance(32.7, drive=drive)
    np.testing.assert_array_equal(a.indices, np.r_[first.indices, second.indices])
    np.testing.assert_array_equal(a.times_ms, np.r_[first.times_ms, second.times_ms])
    for name in ("voltage_mv", "excitatory_g", "inhibitory_g", "release_hz_equiv", "_release_pending"):
        np.testing.assert_array_equal(getattr(whole, name), getattr(restored, name))
    restored.reset()
    silent = restored.advance(40, drive=drive, outputs=[])
    assert silent.total_spikes == a.total_spikes and len(silent.indices) == 0
    np.testing.assert_array_equal(restored.voltage_mv, whole.voltage_mv)
    np.testing.assert_array_equal(restored.release_hz_equiv, whole.release_hz_equiv)


def test_checkpoint_rejects_changed_spec_and_invalid_release_atomically():
    net = network([(0, 1, 52)])
    net.advance(.5)
    state = net.state_dict()
    other = network([(0, 1, 52)], specs=(replace(SPEC, release_tau_ms=8),))
    with pytest.raises(ValueError, match="specification differs"):
        other.load_state_dict(state)
    for key in ("release_hz_equiv", "release_pending"):
        invalid = net.state_dict()
        invalid[key].flat[0] = np.nan
        with pytest.raises(ValueError, match="graded checkpoint"):
            net.load_state_dict(invalid)
        assert net.tick == 5
        np.testing.assert_array_equal(net.release_hz_equiv, state["release_hz_equiv"])


def test_graded_spec_requires_exact_unique_ids_and_valid_explicit_parameters():
    with pytest.raises(ValueError, match="multiple"):
        network(specs=(SPEC, SPEC))
    with pytest.raises(ValueError, match="Unknown neuron"):
        network(specs=(replace(SPEC, neuron_ids=(999,)),))
    for changes in ({"release_tau_ms": 0}, {"release_gain_hz_equiv_per_mv": -1},
                    {"release_baseline_hz_equiv": 300}, {"resting_mv": np.nan}):
        with pytest.raises(ValueError):
            replace(SPEC, **changes)
    for value in (True, np.bool_(True), [2], "2", 1+2j):
        with pytest.raises(ValueError, match="finite numbers"):
            replace(SPEC, release_tau_ms=value)
    normalized = replace(SPEC, release_tau_ms=np.float32(2))
    assert type(normalized.release_tau_ms) is float
    assert network(specs=(normalized,)).release_hz_equiv[0] == 50


def test_extremely_slow_release_retains_positive_integrated_mass():
    spec = replace(SPEC, release_baseline_hz_equiv=0, release_tau_ms=1e18)
    net = network([(0, 1, 52)], specs=(spec,))
    net.step(drive=ConductanceDrive([0], current_mv=10))
    target = 5*(net.voltage_mv[0]+35)
    # In this small-z limit r(t)=target*t/tau to machine accuracy, hence the
    # analytic integral is target*dt^2/(2*tau), converted from ms to seconds.
    expected = target*.1**2/(2*1e18*1000)
    assert expected > 0
    assert net._release_pending[net.delay_ticks, 0] == pytest.approx(expected, rel=1e-12, abs=0)
