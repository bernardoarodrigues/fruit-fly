"""Numerical/control tests independent of connectome biological validation."""
from dataclasses import asdict, replace

import numpy as np
import pytest
from scipy.linalg import expm

from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive


def network(edges=(), n=4, parameters=None, seed=31):
    edges = sorted(edges)
    pointers = np.zeros(n + 1, dtype=np.int64)
    for source, target, weight in edges:
        pointers[source + 1] += 1
    np.cumsum(pointers, out=pointers)
    return LIFNetwork(np.arange(n, dtype=np.int64) + 1000, pointers,
                      np.array([e[1] for e in edges], dtype=np.int32),
                      np.array([e[2] for e in edges], dtype=np.float32),
                      parameters=parameters, seed=seed)


def scalar_reference(net, duration_ms, current):
    """Matrix-exponential state updates and list-of-edges event scheduling.

    Uses SciPy expm instead of the engine's hand-derived coefficients, and a
    dictionary of delayed events instead of its CSR/ring implementation.
    """
    p = net.parameters
    # State is (v-rest, g, constant drive); the third coordinate is held fixed.
    generator = np.array([[-1 / p.membrane_tau_ms, 1 / p.membrane_tau_ms,
                           1 / p.membrane_tau_ms],
                          [0, -1 / p.synapse_tau_ms, 0], [0, 0, 0]])
    transition = expm(generator * p.dt_ms)
    state = np.column_stack((net.voltage_mv - p.resting_mv, net.synaptic_mv, current))
    last = [-10**12] * net.n_neurons
    queue = {}
    spikes, voltage, synaptic = [], [], []
    edges = [(i, int(net.targets[k]), float(net.weights[k]))
             for i in range(net.n_neurons)
             for k in range(net.indptr[i], net.indptr[i + 1])]
    for tick in range(round(duration_ms / p.dt_ms)):
        active = [tick - last[i] >= round(p.refractory_ms / p.dt_ms)
                  for i in range(net.n_neurons)]
        fired = []
        for i in range(net.n_neurons):
            if active[i]:
                state[i] = transition @ state[i]
                if state[i, 0] + p.resting_mv > p.threshold_mv:
                    fired.append(i)
                    last[i] = tick
                    active[i] = False
                    spikes.append((tick, i))
        for source, target, weight in edges:
            if source in fired:
                queue.setdefault(tick + round(p.delay_ms / p.dt_ms), []).append((target, weight))
        for target, weight in queue.pop(tick, []):
            if active[target]:
                state[target, 1] += weight
        for i in fired:
            state[i, :2] = [p.reset_mv - p.resting_mv, 0]
        voltage.append(state[:, 0].copy() + p.resting_mv)
        synaptic.append(state[:, 1].copy())
    return spikes, np.asarray(voltage), np.asarray(synaptic)


def test_scalar_expm_reference_with_recurrence_and_inhibition():
    net = network([(0, 1, 80), (0, 2, 12), (1, 2, 95), (2, 0, -60),
                   (2, 3, 75), (3, 1, -35)], n=4)
    net.voltage_mv[:] = [-44, -50, -49, -52]
    net.synaptic_mv[:] = [4, 2, -3, 1]
    current = np.array([11, 1, 0, 2])
    expected_spikes, expected_v, expected_g = scalar_reference(net, 80, current)
    actual_spikes, actual_v, actual_g = [], [], []
    for tick in range(800):
        output = net.step(drive=SparseDrive(np.arange(4), current_mv=current))
        actual_spikes.extend((tick, int(i)) for i in output.indices)
        actual_v.append(net.voltage_mv.copy())
        actual_g.append(net.synaptic_mv.copy())
    assert actual_spikes == expected_spikes
    assert len(actual_spikes) > 4
    np.testing.assert_allclose(actual_v, expected_v, rtol=0, atol=3e-11)
    np.testing.assert_allclose(actual_g, expected_g, rtol=0, atol=3e-11)


def test_analytic_equal_time_constants():
    params = replace(LIFParameters(), synapse_tau_ms=20)
    net = network(n=1, parameters=params)
    net.synaptic_mv[0] = 4
    _, v, g = scalar_reference(net, 2, [0])
    net.advance(2)
    np.testing.assert_allclose(net.voltage_mv, v[-1], atol=1e-12)
    np.testing.assert_allclose(net.synaptic_mv, g[-1], atol=1e-12)


def test_delay_preserves_causality_across_short_calls():
    net = network([(0, 1, 100)], n=2)
    net.voltage_mv[0] = -44
    first = net.advance(1.8)
    np.testing.assert_equal(first.times_ms, [0])
    assert net.synaptic_mv[1] == 0 and net.voltage_mv[1] == -52
    net.step()  # tick 18, event delivery after integration
    assert net.synaptic_mv[1] == 100 and net.voltage_mv[1] == -52
    net.step()  # tick 19: first physical influence on membrane
    assert net.voltage_mv[1] > -52


def test_zero_delay_still_delivers_after_threshold():
    net = network([(0, 1, 100)], n=2, parameters=replace(LIFParameters(), delay_ms=0))
    net.voltage_mv[0] = -44
    net.step()
    assert net.synaptic_mv[1] == 100 and net.voltage_mv[1] == -52
    net.step()
    assert net.voltage_mv[1] > -52


def test_refractory_clamps_both_states_drops_arrivals_and_resets_g():
    net = network([(0, 1, 100)], n=2)
    net.voltage_mv[:] = -44
    net.synaptic_mv[:] = 3
    net.step()
    np.testing.assert_equal(net.synaptic_mv, [0, 0])
    np.testing.assert_equal(net.voltage_mv, [-52, -52])
    # Inject a value to distinguish clamping from silent synaptic decay.
    net.synaptic_mv[1] = 7
    net.advance(2.1)
    assert net.synaptic_mv[1] == 7  # also rejects the incoming tick-18 event
    net.step()  # first active tick = spike tick + 22
    assert net.synaptic_mv[1] < 7 and net.voltage_mv[1] > -52


def test_poisson_chunk_invariance_and_seed_reset():
    edges = [(0, 1, 80), (1, 2, 70), (2, 3, -25), (3, 0, 20)]
    whole = network(edges)
    chunked = network(edges)
    drive = SparseDrive([0, 3], rates_hz=[150, 200])
    expected = whole.advance(120, drive=drive)
    parts = [chunked.advance(value, drive=drive) for value in [0.1, 1.8, 0.1, 15, 3, 100]]
    np.testing.assert_array_equal(np.concatenate([p.indices for p in parts]), expected.indices)
    np.testing.assert_array_equal(np.concatenate([p.times_ms for p in parts]), expected.times_ms)
    np.testing.assert_array_equal(chunked.voltage_mv, whole.voltage_mv)
    np.testing.assert_array_equal(chunked.synaptic_mv, whole.synaptic_mv)
    assert sum(part.total_spikes for part in parts) == expected.total_spikes
    assert len(expected.indices) > 10
    whole.reset()
    repeated = whole.advance(120, drive=drive)
    np.testing.assert_array_equal(repeated.times_ms, expected.times_ms)
    whole.reset(seed=32)
    changed = whole.advance(120, drive=drive)
    assert not np.array_equal(changed.times_ms, expected.times_ms)


def test_poisson_input_changes_next_tick_and_zero_refractory_semantics():
    net = network(n=1)
    drive = SparseDrive([0], rates_hz=10000)
    assert net.step(drive=drive).total_spikes == 0
    assert net.voltage_mv[0] > -45  # applied in synapses slot
    first = net.step(drive=drive)
    np.testing.assert_equal(first.times_ms, [.1])
    assert net.voltage_mv[0] == -52  # same-tick Poisson input is discarded
    rest = net.advance(1, drive=drive)
    np.testing.assert_allclose(rest.times_ms, [.3, .5, .7, .9, 1.1])


def test_checkpoint_preserves_pending_events_rng_and_intervention(tmp_path):
    edges = [(0, 1, 100), (1, 2, 80), (2, 3, -10)]
    original = network(edges)
    original.voltage_mv[0] = -44
    original.ablate([2])
    drive = SparseDrive([0], rates_hz=170)
    original.advance(.5, drive=drive)  # first spike still queued for tick 18
    path = tmp_path / "brain.npz"
    original.save_checkpoint(path)
    restored = network(edges, seed=999)
    restored.load_checkpoint(path)
    expected = original.advance(80, drive=drive)
    actual = restored.advance(80, drive=drive)
    np.testing.assert_array_equal(actual.times_ms, expected.times_ms)
    np.testing.assert_array_equal(actual.indices, expected.indices)
    np.testing.assert_array_equal(restored.voltage_mv, original.voltage_mv)
    np.testing.assert_array_equal(restored.synaptic_mv, original.synaptic_mv)
    assert restored.ablated[2]
    wrong_graph = network([(0, 1, 101), (1, 2, 80), (2, 3, -10)])
    with pytest.raises(ValueError, match="connectome"):
        wrong_graph.load_checkpoint(path)


def test_recording_filter_does_not_change_dynamics():
    one = network([(0, 1, 150)], n=2)
    two = network([(0, 1, 150)], n=2)
    drive = SparseDrive([0], rates_hz=500)
    all_spikes = one.advance(50, drive=drive)
    selected = two.advance(50, drive=drive, outputs=[1])
    assert np.all(selected.indices == 1)
    np.testing.assert_equal(selected.times_ms, all_spikes.times_ms[all_spikes.indices == 1])
    np.testing.assert_array_equal(one.voltage_mv, two.voltage_mv)
    assert selected.total_spikes == all_spikes.total_spikes


def test_ablation_suppresses_outgoing_edges_including_pending_events():
    net = network([(0, 1, 150)], n=2)
    net.voltage_mv[0] = -44
    assert net.step().indices.tolist() == [0]
    net.ablate([0])
    output = net.advance(10)
    assert output.traversed_edges == 0
    assert net.synaptic_mv[1] == 0 and net.voltage_mv[1] == -52
    net.reset(keep_ablations=True)
    assert net.ablated[0]
    net.reset()
    assert not net.ablated.any()


def test_quiescent_graph_does_not_scan_edges():
    net = network([(0, 1, 1), (1, 2, 1), (2, 0, 1)])
    output = net.advance(100, outputs=[])
    assert output.total_spikes == output.traversed_edges == 0
    np.testing.assert_equal(net.voltage_mv, [-52] * 4)


@pytest.mark.parametrize("bad", [SparseDrive([0, 0], rates_hz=1),
                                  SparseDrive([4], rates_hz=1),
                                  SparseDrive([0.5], rates_hz=1),
                                  SparseDrive([0], rates_hz=-1),
                                  SparseDrive([0], rates_hz=10001),
                                  SparseDrive([0], current_mv=np.nan)])
def test_invalid_drive_fails_before_advancing(bad):
    net = network()
    with pytest.raises(ValueError):
        net.advance(1, drive=bad)
    assert net.time_ms == 0


def test_rejects_fractional_clock_duration():
    with pytest.raises(ValueError, match="multiples"):
        network().advance(.15)


def test_rejects_lossy_graph_index_casts():
    with pytest.raises(ValueError, match="integer array"):
        LIFNetwork([100, 101], [0, 1, 1], [.5], [1])
    with pytest.raises(ValueError, match="range"):
        LIFNetwork([100, 101], [0, 1, 1], [2**32], [1])


def test_brian2_deterministic_parity_with_delays_inhibition_and_refractory():
    b = pytest.importorskip("brian2")
    b.start_scope()
    b.prefs.codegen.target = "numpy"
    p = LIFParameters()
    edges = [(0, 1, 80), (0, 2, 12), (1, 2, 95), (2, 0, -60),
             (2, 3, 75), (3, 1, -35)]
    ours = network(edges, n=4)
    ours.voltage_mv[:] = [-44, -50, -49, -52]
    ours.synaptic_mv[:] = [4, 2, -3, 1]
    current = np.array([11, 1, 0, 2])
    group = b.NeuronGroup(4, """
        dv/dt = (-52*mV-v+g+drive)/(20*ms) : volt (unless refractory)
        dg/dt = -g/(5*ms) : volt (unless refractory)
        drive : volt
        rfc : second
        """, method="linear", threshold="v > -45*mV",
        reset="v = -52*mV; g = 0*mV", refractory="rfc", dt=p.dt_ms*b.ms)
    group.v = ours.voltage_mv * b.mV
    group.g = ours.synaptic_mv * b.mV
    group.drive = current * b.mV
    group.rfc = p.refractory_ms * b.ms
    syn = b.Synapses(group, group, "w:volt", on_pre="g += w", delay=p.delay_ms*b.ms)
    syn.connect(i=[e[0] for e in edges], j=[e[1] for e in edges])
    syn.w = np.asarray([e[2] for e in edges]) * b.mV
    spikes = b.SpikeMonitor(group)
    states = b.StateMonitor(group, ["v", "g"], record=True, when="end")
    b.Network(group, syn, spikes, states).run(80*b.ms)
    outputs, voltages, conductances = [], [], []
    for tick in range(800):
        outputs.append(ours.step(drive=SparseDrive(np.arange(4), current_mv=current)))
        voltages.append(ours.voltage_mv.copy())
        conductances.append(ours.synaptic_mv.copy())
    np.testing.assert_array_equal(np.concatenate([o.indices for o in outputs]), np.asarray(spikes.i))
    np.testing.assert_allclose(np.concatenate([o.times_ms for o in outputs]), spikes.t / b.ms, atol=1e-12)
    np.testing.assert_allclose(voltages, np.asarray(states.v / b.mV).T, rtol=0, atol=4e-11)
    np.testing.assert_allclose(conductances, np.asarray(states.g / b.mV).T, rtol=0, atol=4e-11)


def test_brian2_poisson_scheduling_parity_at_probability_one():
    b = pytest.importorskip("brian2")
    b.start_scope()
    b.prefs.codegen.target = "numpy"
    group = b.NeuronGroup(1, """
        dv/dt = (-52*mV-v+g)/(20*ms) : volt (unless refractory)
        dg/dt = -g/(5*ms) : volt (unless refractory)
        rfc : second
        """, method="linear", threshold="v > -45*mV",
        reset="v = -52*mV; g = 0*mV", refractory="rfc", dt=.1*b.ms)
    group.v = -52*b.mV
    group.rfc = 0*b.ms
    poisson = b.PoissonInput(group, "v", N=1, rate=10000*b.Hz, weight=68.75*b.mV)
    spikes = b.SpikeMonitor(group)
    b.Network(group, poisson, spikes).run(3*b.ms)
    ours = network(n=1).advance(3, drive=SparseDrive([0], rates_hz=10000))
    np.testing.assert_allclose(ours.times_ms, spikes.t / b.ms, atol=1e-12)
