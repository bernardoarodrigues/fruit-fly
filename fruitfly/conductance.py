"""Conductance-based extension; separate from the replicated Shiu LIF model.

Conductances are nonnegative ratios to the leak conductance. Sparse graph
weights remain signed mV priors and are converted at the resting potential.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numba import njit

from .neural import (LIFNetwork, LIFParameters, SparseDrive, SpikeBatch,
                     _integer_array, _steps, _uniform)


@dataclass(frozen=True)
class ConductanceParameters:
    dt_ms: float = .1
    resting_mv: float = -52.0
    reset_mv: float = -52.0
    threshold_mv: float = -45.0
    membrane_tau_ms: float = 20.0
    excitatory_tau_ms: float = 5.0
    inhibitory_tau_ms: float = 5.0
    refractory_ms: float = 2.2
    delay_ms: float = 1.8
    excitatory_reversal_mv: float = 0.0
    inhibitory_reversal_mv: float = -75.0
    excitatory_gain: float = 1.0
    inhibitory_gain: float = 1.0
    input_event_gleak: float = 1.0
    voltage_method: str = "exponential"

    def __post_init__(self):
        if not all(np.isfinite(value) for key,value in asdict(self).items() if key != "voltage_method"):
            raise ValueError("Conductance parameters must be finite")
        if self.voltage_method not in ("exponential", "pade22"):
            raise ValueError("voltage_method must be exponential or pade22")
        if min(self.dt_ms, self.membrane_tau_ms, self.excitatory_tau_ms, self.inhibitory_tau_ms) <= 0:
            raise ValueError("Time step and time constants must be positive")
        if min(self.excitatory_gain, self.inhibitory_gain, self.input_event_gleak) < 0:
            raise ValueError("Conductance gains must be nonnegative")
        if not self.inhibitory_reversal_mv < self.resting_mv < self.threshold_mv < self.excitatory_reversal_mv:
            raise ValueError("Require inhibitory reversal < resting < threshold < excitatory reversal")
        if not self.inhibitory_reversal_mv <= self.reset_mv < self.threshold_mv:
            raise ValueError("Reset must lie inside reversal bounds and below threshold")
        _steps(self.refractory_ms, self.dt_ms)
        _steps(self.delay_ms, self.dt_ms)


@dataclass(frozen=True)
class ConductanceDrive:
    """External presynaptic events plus optional effective membrane current.

    An input event increments excitatory conductance, not membrane voltage.
    ``rates_hz`` describes input events; the target ORN's actual output firing
    rate must be measured separately. The normal refractory duration is retained.
    """
    indices: Any
    rates_hz: Any = None
    current_mv: Any = None
    event_gleak: Any = None


@dataclass(frozen=True)
class SynapticEvents:
    """Timestamped external synaptic events in absolute ms and leak ratios.

    Repeated neuron indices/events are allowed. All events must belong to the
    current advance interval and align to its fixed neural clock. Future graph
    events persist in the engine's delay queue; future external events are the
    responsibility of the sensory/recording subsystem.
    """
    indices: Any
    times_ms: Any
    conductance_gleak: Any = 1.0
    inhibitory: Any = False


@njit(cache=True)
def _conductance_kernel(
    n_steps, first_tick, dt, rest, reset, threshold, tau, e_rev, i_rev,
    e_half_decay, i_half_decay, e_conversion, i_conversion, use_pade22,
    voltage, excitatory, inhibitory, last_spike, refractory, current,
    poisson_indices, probabilities, input_weights, rng_state, indptr, targets,
    weights, ablated, delay_ticks, pending, pending_count, record,
    event_indices, event_ticks, event_weights, event_inhibitory,
):
    output_i = np.empty(128, dtype=np.int32)
    output_t = np.empty(128, dtype=np.int64)
    recorded = total_spikes = traversed_edges = 0
    fired = np.empty(len(voltage), dtype=np.int32)
    ring_size = len(pending_count)
    e_decay, i_decay = e_half_decay**2, i_half_decay**2
    passive_decay = np.exp(-dt / tau)
    next_event = 0
    for tick in range(first_tick, first_tick + n_steps):
        n_fired = 0
        for i in range(len(voltage)):
            ge, gi = excitatory[i], inhibitory[i]
            available = tick - last_spike[i] >= refractory[i]
            if available:
                if ge == 0.0 and gi == 0.0:
                    voltage[i] = rest + (voltage[i] - rest) * passive_decay + current[i] * (1 - passive_decay)
                else:
                    # Exact frozen-conductance voltage transition at the midpoint
                    # of the exponentially decaying conductances. This is second
                    # order in dt between impulses and preserves reversal bounds.
                    ge_mid, gi_mid = ge * e_half_decay, gi * i_half_decay
                    total_g = 1.0 + ge_mid + gi_mid
                    equilibrium = (rest + ge_mid * e_rev + gi_mid * i_rev + current[i]) / total_g
                    z = dt * total_g / tau
                    if use_pade22 and z <= 1.0:
                        z2 = z*z
                        decay = (12.0 - 6.0*z + z2) / (12.0 + 6.0*z + z2)
                    else:
                        # Padé[2/2] tends back to one at large z; retaining the
                        # exact exponential here avoids that stiff-limit error.
                        decay = np.exp(-z)
                    voltage[i] = equilibrium + (voltage[i] - equilibrium) * decay
                if voltage[i] > threshold:
                    fired[n_fired] = i
                    n_fired += 1
                    last_spike[i] = tick
                    if record[i]:
                        if recorded == len(output_i):
                            next_i = np.empty(2 * len(output_i), dtype=np.int32)
                            next_t = np.empty(2 * len(output_t), dtype=np.int64)
                            next_i[:recorded] = output_i
                            next_t[:recorded] = output_t
                            output_i, output_t = next_i, next_t
                        output_i[recorded], output_t[recorded] = i, tick
                        recorded += 1
            else:
                voltage[i] = reset
            # Synapses continue to decay during refractory; they are not reset
            # by the spike and continue to receive arriving events.
            excitatory[i], inhibitory[i] = ge * e_decay, gi * i_decay
        total_spikes += n_fired
        destination = (tick + delay_ticks) % ring_size
        offset = pending_count[destination]
        for k in range(n_fired):
            pending[destination, offset + k] = fired[k]
        pending_count[destination] = offset + n_fired
        source_slot = tick % ring_size
        for k in range(pending_count[source_slot]):
            source = pending[source_slot, k]
            if not ablated[source]:
                for edge in range(indptr[source], indptr[source+1]):
                    target, weight = targets[edge], weights[edge]
                    if weight > 0:
                        excitatory[target] += weight * e_conversion
                    elif weight < 0:
                        inhibitory[target] -= weight * i_conversion
                    traversed_edges += 1
        pending_count[source_slot] = 0
        for k in range(len(poisson_indices)):
            if _uniform(rng_state) < probabilities[k]:
                excitatory[poisson_indices[k]] += input_weights[k]
        while next_event < len(event_ticks) and event_ticks[next_event] == tick:
            target = event_indices[next_event]
            if event_inhibitory[next_event]:
                inhibitory[target] += event_weights[next_event]
            else:
                excitatory[target] += event_weights[next_event]
            next_event += 1
        for k in range(n_fired):
            voltage[fired[k]] = reset
    return output_i[:recorded], output_t[:recorded], total_spikes, traversed_edges


class ConductanceNetwork(LIFNetwork):
    """Same graph/clock/recording interface, with different declared physiology.

    Inherited graph validation, ablation, checkpoint serialization, ID mapping
    and spike-batch types are shared; the Shiu integration kernel is not changed.
    """

    def __init__(self, neuron_ids, indptr, targets, weights, *,
                 parameters: ConductanceParameters | None = None, seed: int = 0):
        p = parameters or ConductanceParameters()
        super().__init__(neuron_ids, indptr, targets, weights, seed=seed,
                         parameters=LIFParameters(dt_ms=p.dt_ms, resting_mv=p.resting_mv,
                                                  reset_mv=p.reset_mv, threshold_mv=p.threshold_mv,
                                                  membrane_tau_ms=p.membrane_tau_ms,
                                                  synapse_tau_ms=p.excitatory_tau_ms,
                                                  refractory_ms=p.refractory_ms, delay_ms=p.delay_ms,
                                                  poisson_weight_mv=0))
        self.parameters = p
        self.excitatory_g = np.zeros(self.n_neurons, dtype=np.float64)
        self.inhibitory_g = np.zeros(self.n_neurons, dtype=np.float64)
        # synaptic_mv is a compatibility diagnostic: equivalent signed drive AT
        # REST, never the actual voltage-dependent current in the new equation.
        self.reset()

    def reset(self, *, seed: int | None = None, keep_ablations: bool = False):
        super().reset(seed=seed, keep_ablations=keep_ablations)
        if hasattr(self, "excitatory_g"):
            self.excitatory_g.fill(0)
            self.inhibitory_g.fill(0)

    def _events(self, events, end_tick):
        if events is None:
            return (np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int64),
                    np.empty(0, dtype=np.float64), np.empty(0, dtype=np.bool_))
        indices = _integer_array(events.indices, np.int32, "event indices")
        if np.any(indices < 0) or np.any(indices >= self.n_neurons):
            raise ValueError("Event neuron index outside graph")
        times = self._values(events.times_ms, len(indices))
        ticks = np.rint(times / self.parameters.dt_ms).astype(np.int64)
        if not np.allclose(ticks * self.parameters.dt_ms, times, rtol=1e-10, atol=1e-10):
            raise ValueError("Event timestamps must align with dt_ms")
        if np.any(ticks < self.tick) or np.any(ticks >= end_tick):
            raise ValueError("External event outside current advance interval")
        weights = self._values(events.conductance_gleak, len(indices))
        if np.any(weights < 0):
            raise ValueError("Event conductances must be nonnegative")
        inhibitory = np.asarray(events.inhibitory, dtype=np.bool_)
        if inhibitory.ndim == 0:
            inhibitory = np.full(len(indices), inhibitory, dtype=np.bool_)
        if inhibitory.shape != (len(indices),):
            raise ValueError("inhibitory must be scalar or one boolean per event")
        order = np.argsort(ticks, kind="stable")
        return indices[order], ticks[order], weights[order], inhibitory[order]

    def advance(self, duration_ms: float, *, drive: ConductanceDrive | SparseDrive | None = None,
                outputs=None, events: SynapticEvents | None = None) -> SpikeBatch:
        steps = _steps(duration_ms, self.parameters.dt_ms)
        drive = drive or ConductanceDrive([])
        selected = self._indices(drive.indices)
        rates = self._values(drive.rates_hz, len(selected))
        probabilities = rates * self.parameters.dt_ms / 1000
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise ValueError("Input event rates must lie in [0, 1000/dt_ms]")
        if getattr(drive, "poisson_weight_mv", None) is not None:
            raise ValueError("Voltage jumps are unsupported; use ConductanceDrive.event_gleak")
        input_weights = self._values(getattr(drive, "event_gleak", None), len(selected), self.parameters.input_event_gleak)
        if np.any(input_weights < 0):
            raise ValueError("Input event conductances must be nonnegative")
        current = self._values(drive.current_mv, len(selected))
        event_arrays = self._events(events, self.tick + steps)
        record = np.ones(self.n_neurons, dtype=np.bool_) if outputs is None else np.zeros(self.n_neurons, dtype=np.bool_)
        if outputs is not None:
            record[self._indices(outputs)] = True
        self._current_mv[self._previous_drive] = 0
        self._current_mv[selected] = current
        self._previous_drive = selected
        # No stimulus-dependent refractory changes, including legacy SparseDrive.
        p = self.parameters
        poisson_indices = selected if drive.rates_hz is not None else np.empty(0, dtype=np.int32)
        start_ms = self.time_ms
        indices, ticks, total, work = self._run_dynamics(
            steps, poisson_indices, probabilities, input_weights, record, event_arrays)
        self.tick += steps
        self.synaptic_mv[:] = (self.excitatory_g * (p.excitatory_reversal_mv-p.resting_mv)
                               + self.inhibitory_g * (p.inhibitory_reversal_mv-p.resting_mv))
        return SpikeBatch(indices, ticks*p.dt_ms, self.neuron_ids[indices], start_ms,
                          self.time_ms, int(total), int(work))

    def _run_dynamics(self, steps, poisson_indices, probabilities, input_weights, record, event_arrays):
        """Integration hook; validation and public recording semantics are shared."""
        p = self.parameters
        return _conductance_kernel(
            steps, self.tick, p.dt_ms, p.resting_mv, p.reset_mv, p.threshold_mv,
            p.membrane_tau_ms, p.excitatory_reversal_mv, p.inhibitory_reversal_mv,
            np.exp(-p.dt_ms / (2*p.excitatory_tau_ms)), np.exp(-p.dt_ms / (2*p.inhibitory_tau_ms)),
            p.excitatory_gain / (p.excitatory_reversal_mv-p.resting_mv),
            p.inhibitory_gain / (p.resting_mv-p.inhibitory_reversal_mv),
            p.voltage_method == "pade22",
            self.voltage_mv, self.excitatory_g, self.inhibitory_g, self.last_spike_tick,
            self.refractory_ticks, self._current_mv, poisson_indices, probabilities,
            input_weights, self._rng_state, self.indptr, self.targets, self.weights,
            self.ablated, self.delay_ticks, self._pending, self._pending_count, record, *event_arrays,
        )

    def step(self, *, drive=None, outputs=None, events=None):
        return self.advance(self.parameters.dt_ms, drive=drive, outputs=outputs, events=events)

    def state_dict(self):
        state = super().state_dict()
        state.update(backend="conductance-lif-v1", excitatory_g=self.excitatory_g.copy(),
                     inhibitory_g=self.inhibitory_g.copy())
        return state

    def load_state_dict(self, state):
        if state.get("backend") != "conductance-lif-v1":
            raise ValueError("Checkpoint belongs to another neural backend")
        for name in ("excitatory_g", "inhibitory_g"):
            value = np.asarray(state[name])
            if value.shape != (self.n_neurons,) or value.dtype != np.float64 or not np.all(np.isfinite(value)) or np.any(value < 0):
                raise ValueError(f"Invalid checkpoint conductance: {name}")
        super().load_state_dict(state)
        self.excitatory_g[:] = state["excitatory_g"]
        self.inhibitory_g[:] = state["inhibitory_g"]
