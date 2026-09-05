"""Persistent sparse Shiu-style LIF dynamics; all neural units are mV and ms.

This is a numerical model, not a claim of physiological completeness. The graph
importer owns anatomical provenance, neurotransmitter signs and weight scaling.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from numba import njit


@dataclass(frozen=True)
class LIFParameters:
    dt_ms: float = 0.1
    resting_mv: float = -52.0
    reset_mv: float = -52.0
    threshold_mv: float = -45.0
    membrane_tau_ms: float = 20.0
    synapse_tau_ms: float = 5.0
    refractory_ms: float = 2.2
    delay_ms: float = 1.8
    poisson_weight_mv: float = 68.75  # Shiu: 0.275 mV/contact * 250

    def __post_init__(self):
        if not all(np.isfinite(value) for value in asdict(self).values()):
            raise ValueError("All LIF parameters must be finite")
        if min(self.dt_ms, self.membrane_tau_ms, self.synapse_tau_ms) <= 0:
            raise ValueError("dt and time constants must be positive")
        if min(self.delay_ms, self.refractory_ms) < 0:
            raise ValueError("Delay and refractory duration must be nonnegative")
        if self.threshold_mv <= self.reset_mv:
            raise ValueError("Threshold must exceed reset voltage")
        _steps(self.delay_ms, self.dt_ms)
        _steps(self.refractory_ms, self.dt_ms)


def _steps(duration_ms: float, dt_ms: float) -> int:
    if not np.isfinite(duration_ms) or duration_ms < 0:
        raise ValueError("Duration must be finite and nonnegative")
    result = round(duration_ms / dt_ms)
    if not np.isclose(result * dt_ms, duration_ms, rtol=1e-10, atol=1e-10):
        raise ValueError("Duration, delay and refractory times must be multiples of dt_ms")
    return result


def _integer_array(value, dtype, name):
    array = np.asarray(value)
    if array.ndim != 1 or (array.size and array.dtype.kind not in "iu"):
        raise ValueError(f"{name} must be a one-dimensional integer array")
    bounds = np.iinfo(dtype)
    if array.size and (np.any(array < bounds.min) or np.any(array > bounds.max)):
        raise ValueError(f"{name} exceeds {np.dtype(dtype).name} range")
    return np.ascontiguousarray(array, dtype=dtype)


@dataclass(frozen=True)
class SparseDrive:
    """Held input for one advance; indices are graph positions, never body IDs.

    ``rates_hz`` implements Shiu's N=1 PoissonInput: a Bernoulli arrival with
    probability rate * dt. ``current_mv`` is an effective equilibrium-voltage
    displacement in dv/dt, not an electric current measured in amperes.
    Each supplied field can be scalar or have one value per unique index.
    Direct Poisson targets have zero refractory time by default, as in Shiu.
    """

    indices: Any
    rates_hz: Any = None
    current_mv: Any = None
    poisson_weight_mv: Any = None
    disable_refractory: bool = True


@dataclass(frozen=True)
class SpikeBatch:
    indices: np.ndarray
    times_ms: np.ndarray
    neuron_ids: np.ndarray
    start_ms: float
    end_ms: float
    total_spikes: int
    traversed_edges: int

    def counts(self, indices: Any = None) -> np.ndarray:
        """Recorded counts in requested graph-index order (all if omitted)."""
        if indices is None:
            if len(self.indices) == 0:
                return np.zeros(0, dtype=np.int64)
            return np.bincount(self.indices)
        requested = np.asarray(indices, dtype=np.int64)
        lookup = dict(zip(*np.unique(self.indices, return_counts=True)))
        return np.array([lookup.get(int(i), 0) for i in requested], dtype=np.int64)


@njit(cache=True)
def _uniform(rng_state):
    # xorshift64*: explicit state makes checkpoints and chunk boundaries exact.
    value = rng_state[0]
    value ^= value >> np.uint64(12)
    value ^= value << np.uint64(25)
    value ^= value >> np.uint64(27)
    rng_state[0] = value
    output = value * np.uint64(2685821657736338717)
    return float(output >> np.uint64(11)) * (1.0 / 9007199254740992.0)


@njit(cache=True)
def _advance_kernel(
    n_steps, first_tick, dt, rest, reset, threshold, a, b, synapse_coefficient,
    voltage, synaptic, last_spike, refractory, current, poisson_indices,
    probabilities, poisson_weights, rng_state, indptr, targets, weights,
    ablated, delay_ticks, pending, pending_count, record, initial_capacity,
):
    indices_out = np.empty(initial_capacity, dtype=np.int32)
    ticks_out = np.empty(initial_capacity, dtype=np.int64)
    recorded = 0
    total_spikes = 0
    traversed_edges = 0
    n_neurons = len(voltage)
    active = np.empty(n_neurons, dtype=np.bool_)
    fired = np.empty(n_neurons, dtype=np.int32)
    ring_size = len(pending_count)
    for tick in range(first_tick, first_tick + n_steps):
        n_fired = 0
        for i in range(n_neurons):
            available = tick - last_spike[i] >= refractory[i]
            active[i] = available
            if available:
                old_g = synaptic[i]
                voltage[i] = (rest + (voltage[i] - rest) * a
                              + old_g * synapse_coefficient + current[i] * (1.0 - a))
                synaptic[i] = old_g * b
                if voltage[i] > threshold:
                    fired[n_fired] = i
                    n_fired += 1
                    last_spike[i] = tick
                    # Brian's thresholder marks even rfc=0 cells refractory for
                    # the remainder of the current timestep.
                    active[i] = False
                    if record[i]:
                        if recorded == len(indices_out):
                            next_i = np.empty(len(indices_out) * 2, dtype=np.int32)
                            next_t = np.empty(len(ticks_out) * 2, dtype=np.int64)
                            next_i[:recorded] = indices_out
                            next_t[:recorded] = ticks_out
                            indices_out = next_i
                            ticks_out = next_t
                        indices_out[recorded] = i
                        ticks_out[recorded] = tick
                        recorded += 1
        total_spikes += n_fired
        # Enqueue presynaptic identities; visit edges only upon spike delivery.
        destination = (tick + delay_ticks) % ring_size
        offset = pending_count[destination]
        for k in range(n_fired):
            pending[destination, offset + k] = fired[k]
        pending_count[destination] = offset + n_fired
        source_slot = tick % ring_size
        for k in range(pending_count[source_slot]):
            source = pending[source_slot, k]
            if not ablated[source]:
                for edge in range(indptr[source], indptr[source + 1]):
                    target = targets[edge]
                    if active[target]:
                        synaptic[target] += weights[edge]
                    traversed_edges += 1
        pending_count[source_slot] = 0
        # Shiu PoissonInput writes voltage in the synapses slot, after threshold.
        for k in range(len(poisson_indices)):
            event = _uniform(rng_state) < probabilities[k]
            target = poisson_indices[k]
            if event and active[target]:
                voltage[target] += poisson_weights[k]
        # Reset after synaptic delivery (both membrane AND synaptic state).
        for k in range(n_fired):
            i = fired[k]
            voltage[i] = reset
            synaptic[i] = 0.0
    return indices_out[:recorded], ticks_out[:recorded], total_spikes, traversed_edges


class LIFNetwork:
    """CPU sparse-event engine with persistent state and a fixed anatomical graph."""

    def __init__(self, neuron_ids, indptr, targets, weights, *,
                 parameters: LIFParameters | None = None, seed: int = 0):
        self.parameters = parameters or LIFParameters()
        self.neuron_ids = _integer_array(neuron_ids, np.int64, "neuron_ids")
        self.indptr = _integer_array(indptr, np.int64, "indptr")
        self.targets = _integer_array(targets, np.int32, "targets")
        self.weights = np.ascontiguousarray(weights, dtype=np.float32)
        self.n_neurons = len(self.neuron_ids)
        self.n_edges = len(self.weights)
        if self.n_neurons == 0 or self.n_neurons > np.iinfo(np.int32).max:
            raise ValueError("Graph must contain 1..2^31-1 neurons")
        if len(np.unique(self.neuron_ids)) != self.n_neurons:
            raise ValueError("Neuron IDs must be unique")
        if (self.indptr.shape != (self.n_neurons + 1,) or self.indptr[0] != 0
                or self.indptr[-1] != self.n_edges or np.any(np.diff(self.indptr) < 0)):
            raise ValueError("Invalid outgoing CSR indptr")
        if (self.targets.shape != self.weights.shape or self.weights.ndim != 1
                or np.any(self.targets < 0) or np.any(self.targets >= self.n_neurons)):
            raise ValueError("Invalid CSR targets")
        if not np.all(np.isfinite(self.weights)):
            raise ValueError("Synaptic weights must be finite")
        # Arrays are shared without duplicating a large connectome; treat the
        # source graph as immutable for the lifetime of a network.
        self._fingerprint = None
        self._seed = int(seed)
        self.delay_ticks = _steps(self.parameters.delay_ms, self.parameters.dt_ms)
        self.voltage_mv = np.empty(self.n_neurons, dtype=np.float64)
        self.synaptic_mv = np.empty(self.n_neurons, dtype=np.float64)
        self.last_spike_tick = np.empty(self.n_neurons, dtype=np.int64)
        self.refractory_ticks = np.empty(self.n_neurons, dtype=np.int64)
        self.ablated = np.zeros(self.n_neurons, dtype=np.bool_)
        self._pending = np.empty((self.delay_ticks + 1, self.n_neurons), dtype=np.int32)
        self._pending_count = np.zeros(self.delay_ticks + 1, dtype=np.int64)
        self._rng_state = np.empty(1, dtype=np.uint64)
        self._current_mv = np.zeros(self.n_neurons, dtype=np.float64)
        self._previous_drive = np.empty(0, dtype=np.int32)
        self.reset()

    @classmethod
    def from_connectome(cls, connectome, **kwargs):
        return cls(connectome.neuron_ids, connectome.indptr, connectome.targets,
                   connectome.weights, **kwargs)

    @property
    def time_ms(self) -> float:
        return self.tick * self.parameters.dt_ms

    @property
    def graph_sha256(self) -> str:
        if self._fingerprint is None:
            digest = hashlib.sha256()
            for array in (self.neuron_ids, self.indptr, self.targets, self.weights):
                digest.update(str(array.shape).encode())
                digest.update(memoryview(array).cast("B"))
            self._fingerprint = digest.hexdigest()
        return self._fingerprint

    def _indices(self, indices) -> np.ndarray:
        raw = np.asarray(indices)
        if raw.ndim != 1 or (raw.size and raw.dtype.kind not in "iu"):
            raise ValueError("Neuron indices must be a one-dimensional integer array")
        if np.any(raw < 0) or np.any(raw >= self.n_neurons):
            raise ValueError("Neuron index outside graph")
        result = np.ascontiguousarray(raw, dtype=np.int32)
        if len(np.unique(result)) != len(result):
            raise ValueError("Neuron indices must be unique")
        return result

    def indices_for_ids(self, neuron_ids) -> np.ndarray:
        lookup = {int(identifier): i for i, identifier in enumerate(self.neuron_ids)}
        try:
            return np.array([lookup[int(i)] for i in neuron_ids], dtype=np.int32)
        except KeyError as error:
            raise ValueError(f"Unknown neuron ID: {error.args[0]}") from error

    def reset(self, *, seed: int | None = None, keep_ablations: bool = False):
        """Reset neural state/time/RNG; defaults to clearing interventions too."""
        if seed is not None:
            self._seed = int(seed)
        self.tick = 0
        self.voltage_mv.fill(self.parameters.resting_mv)
        self.synaptic_mv.fill(0.0)
        self.last_spike_tick.fill(-(2**60))
        self.refractory_ticks.fill(_steps(self.parameters.refractory_ms, self.parameters.dt_ms))
        self._pending_count.fill(0)
        self._current_mv.fill(0)
        self._previous_drive = np.empty(0, dtype=np.int32)
        # SeedSequence avoids the absorbing xorshift state at zero.
        seed_value = np.random.SeedSequence(self._seed).generate_state(1, dtype=np.uint64)[0]
        self._rng_state[0] = seed_value if seed_value else np.uint64(1)
        if not keep_ablations:
            self.ablated.fill(False)

    def ablate(self, indices, *, enabled: bool = True):
        """Suppress outgoing synapses at delivery, including already queued ones.

        This does not suppress incoming synapses or spikes. Motor-readout
        silencing belongs to the explicit downstream intervention adapter.
        """
        self.ablated[self._indices(indices)] = enabled

    @staticmethod
    def _values(value, count, default=0.0):
        if value is None:
            return np.full(count, default, dtype=np.float64)
        result = np.asarray(value, dtype=np.float64)
        if result.ndim == 0:
            result = np.full(count, float(result), dtype=np.float64)
        if result.shape != (count,) or not np.all(np.isfinite(result)):
            raise ValueError("Drive values must be finite scalars or one value per index")
        return np.ascontiguousarray(result)

    def advance(self, duration_ms: float, *, drive: SparseDrive | None = None,
                outputs=None) -> SpikeBatch:
        """Advance an integer number of timesteps without rebuilding any state.

        Output indices restrict recording only; an empty sequence disables
        spike storage while still returning total_spikes and edge-work counts.
        """
        steps = _steps(duration_ms, self.parameters.dt_ms)
        drive = drive or SparseDrive([])
        selected = self._indices(drive.indices)
        rates = self._values(drive.rates_hz, len(selected))
        probabilities = rates * self.parameters.dt_ms / 1000.0
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise ValueError("Poisson rates must be in [0, 1000/dt_ms] for N=1 input")
        current = self._values(drive.current_mv, len(selected))
        input_weights = self._values(drive.poisson_weight_mv, len(selected), self.parameters.poisson_weight_mv)
        record = np.ones(self.n_neurons, dtype=np.bool_) if outputs is None else np.zeros(self.n_neurons, dtype=np.bool_)
        if outputs is not None:
            record[self._indices(outputs)] = True
        # Validation above completes before any state is changed.
        self._current_mv[self._previous_drive] = 0
        self.refractory_ticks[self._previous_drive] = _steps(self.parameters.refractory_ms, self.parameters.dt_ms)
        self._current_mv[selected] = current
        if drive.rates_hz is not None and drive.disable_refractory:
            self.refractory_ticks[selected] = 0
        self._previous_drive = selected
        poisson_indices = selected if drive.rates_hz is not None else np.empty(0, dtype=np.int32)
        p = self.parameters
        a = np.exp(-p.dt_ms / p.membrane_tau_ms)
        b = np.exp(-p.dt_ms / p.synapse_tau_ms)
        if p.membrane_tau_ms == p.synapse_tau_ms:
            coefficient = p.dt_ms / p.membrane_tau_ms * a
        else:
            coefficient = p.synapse_tau_ms / (p.membrane_tau_ms - p.synapse_tau_ms) * (a - b)
        start_ms = self.time_ms
        indices, ticks, total, edge_visits = _advance_kernel(
            steps, self.tick, p.dt_ms, p.resting_mv, p.reset_mv, p.threshold_mv,
            a, b, coefficient, self.voltage_mv, self.synaptic_mv,
            self.last_spike_tick, self.refractory_ticks, self._current_mv,
            poisson_indices, probabilities, input_weights, self._rng_state,
            self.indptr, self.targets, self.weights, self.ablated, self.delay_ticks,
            self._pending, self._pending_count, record, max(128, min(8192, int(record.sum()))),
        )
        self.tick += steps
        return SpikeBatch(indices=indices, times_ms=ticks * p.dt_ms,
                          neuron_ids=self.neuron_ids[indices], start_ms=start_ms,
                          end_ms=self.time_ms, total_spikes=int(total),
                          traversed_edges=int(edge_visits))

    def step(self, *, drive: SparseDrive | None = None, outputs=None) -> SpikeBatch:
        return self.advance(self.parameters.dt_ms, drive=drive, outputs=outputs)

    def state_dict(self) -> dict:
        """Complete mutable state; graph arrays are verified by hash, not copied."""
        return {
            "version": 1, "parameters": asdict(self.parameters),
            "graph_sha256": self.graph_sha256, "tick": self.tick, "seed": self._seed,
            "voltage_mv": self.voltage_mv.copy(), "synaptic_mv": self.synaptic_mv.copy(),
            "last_spike_tick": self.last_spike_tick.copy(),
            "refractory_ticks": self.refractory_ticks.copy(), "ablated": self.ablated.copy(),
            "rng_state": self._rng_state.copy(), "current_mv": self._current_mv.copy(),
            "previous_drive": self._previous_drive.copy(),
            "pending_count": self._pending_count.copy(),
            # Never serialize uninitialized memory beyond valid queue entries.
            "pending": np.concatenate([self._pending[k, :n] for k, n in enumerate(self._pending_count)]),
        }

    def load_state_dict(self, state: dict):
        if (state["version"] != 1 or state["parameters"] != asdict(self.parameters)
                or state["graph_sha256"] != self.graph_sha256):
            raise ValueError("Checkpoint version, parameters or connectome differs")
        destinations = {
            "voltage_mv": self.voltage_mv, "synaptic_mv": self.synaptic_mv,
            "last_spike_tick": self.last_spike_tick, "refractory_ticks": self.refractory_ticks,
            "ablated": self.ablated, "rng_state": self._rng_state,
            "current_mv": self._current_mv, "pending_count": self._pending_count,
        }
        for name, destination in destinations.items():
            value = np.asarray(state[name])
            if value.shape != destination.shape or value.dtype != destination.dtype:
                raise ValueError(f"Invalid checkpoint array: {name}")
        for name in ("tick", "seed"):
            if (isinstance(state[name], (bool, np.bool_))
                    or not isinstance(state[name], (int, np.integer)) or state[name] < 0):
                raise ValueError(f"Invalid checkpoint integer: {name}")
        if any(not np.all(np.isfinite(state[name])) for name in ("voltage_mv", "synaptic_mv", "current_mv")):
            raise ValueError("Invalid checkpoint non-finite neural state or current")
        if state["rng_state"][0] == 0:
            raise ValueError("Invalid checkpoint RNG: zero is an absorbing state")
        if np.any(state["refractory_ticks"] < 0) or np.any(state["last_spike_tick"] >= state["tick"]):
            raise ValueError("Invalid checkpoint refractory or last-spike clock")
        pending = np.asarray(state["pending"])
        if pending.ndim != 1 or pending.dtype != np.int32:
            raise ValueError("Invalid checkpoint delayed source index dtype or shape")
        counts = state["pending_count"]
        if np.any(counts < 0) or np.any(counts > self.n_neurons) or sum(counts) != len(pending):
            raise ValueError("Invalid checkpoint delay queue")
        previous = self._indices(state["previous_drive"])
        if pending.size and (np.any(pending < 0) or np.any(pending >= self.n_neurons)):
            raise ValueError("Invalid checkpoint delayed source index")
        offset = 0
        for count in counts:
            if len(np.unique(pending[offset:offset+count])) != count:
                raise ValueError("Duplicate presynaptic spike in checkpoint delay slot")
            offset += count
        for name, destination in destinations.items():
            destination[:] = state[name]
        offset = 0
        for slot, count in enumerate(counts):
            self._pending[slot, :count] = pending[offset:offset + count]
            offset += count
        self._previous_drive = previous
        self.tick, self._seed = int(state["tick"]), int(state["seed"])

    def save_checkpoint(self, path: str | Path):
        state = self.state_dict()
        metadata = {key: state.pop(key) for key in ("version", "parameters", "graph_sha256", "tick", "seed")}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            np.savez_compressed(stream, metadata=json.dumps(metadata), **state)

    def load_checkpoint(self, path: str | Path):
        with np.load(path, allow_pickle=False) as archive:
            state = json.loads(str(archive["metadata"]))
            state.update({key: archive[key] for key in archive.files if key != "metadata"})
        self.load_state_dict(state)
