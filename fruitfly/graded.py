"""Experimental mixed spiking/graded conductance dynamics on one retained graph.

Continuous release is a declared hypothesis in spike-event-equivalents/second,
not a measured firing rate. All graded parameters must be supplied explicitly.
No biological identity is inferred from a neuron's name or resting voltage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from numbers import Real

import numpy as np
from numba import njit

from .conductance import ConductanceNetwork
from .neural import _integer_array, _uniform


@dataclass(frozen=True)
class GradedPopulationSpec:
    neuron_ids: tuple[int, ...]
    resting_mv: float
    membrane_tau_ms: float
    release_reference_mv: float
    release_baseline_hz_equiv: float
    release_gain_hz_equiv_per_mv: float
    release_max_hz_equiv: float
    release_tau_ms: float

    def __post_init__(self):
        ids = _integer_array(self.neuron_ids, np.int64, "Graded neuron IDs")
        if not len(ids) or len(np.unique(ids)) != len(ids):
            raise ValueError("Graded neuron IDs must be nonempty and unique")
        object.__setattr__(self, "neuron_ids", tuple(int(v) for v in ids))
        values = {k: v for k, v in asdict(self).items() if k != "neuron_ids"}
        if not all(isinstance(v, Real) and not isinstance(v, (bool, np.bool_))
                   and np.isfinite(v) for v in values.values()):
            raise ValueError("Graded parameters must be finite numbers")
        for key, value in values.items():
            object.__setattr__(self, key, float(value))
        if min(self.membrane_tau_ms, self.release_tau_ms, self.release_max_hz_equiv) <= 0:
            raise ValueError("Graded time constants and release maximum must be positive")
        if not 0 <= self.release_baseline_hz_equiv <= self.release_max_hz_equiv:
            raise ValueError("Graded baseline must lie in [0, release maximum]")
        if self.release_gain_hz_equiv_per_mv < 0:
            raise ValueError("Graded release gain must be nonnegative")


@njit(cache=True)
def _mixed_kernel(
    n_steps, first_tick, dt, rest, reset, threshold, tau, e_rev, i_rev,
    e_half_decay, i_half_decay, e_conversion, i_conversion, use_pade22,
    voltage, excitatory, inhibitory, last_spike, refractory, current,
    poisson_indices, probabilities, input_weights, rng_state, indptr, targets,
    weights, ablated, delay_ticks, pending, pending_count, record,
    event_indices, event_ticks, event_weights, event_inhibitory,
    graded_slot, graded_indices, graded_parameters, release, release_pending,
):
    # The spiking update/order matches conductance._conductance_kernel. An empty
    # graded specification is checked for bitwise parity with that backend.
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
            k = graded_slot[i]
            ge, gi = excitatory[i], inhibitory[i]
            available = k >= 0 or tick - last_spike[i] >= refractory[i]
            if available:
                local_rest = graded_parameters[k, 0] if k >= 0 else rest
                local_tau = graded_parameters[k, 1] if k >= 0 else tau
                if ge == 0.0 and gi == 0.0:
                    decay = np.exp(-dt / local_tau) if k >= 0 else passive_decay
                    voltage[i] = local_rest + (voltage[i]-local_rest)*decay + current[i]*(1-decay)
                else:
                    ge_mid, gi_mid = ge*e_half_decay, gi*i_half_decay
                    total_g = 1.0 + ge_mid + gi_mid
                    equilibrium = (local_rest + ge_mid*e_rev + gi_mid*i_rev + current[i])/total_g
                    z = dt*total_g/local_tau
                    if use_pade22 and z <= 1.0:
                        z2 = z*z
                        decay = (12.0-6.0*z+z2)/(12.0+6.0*z+z2)
                    else:
                        decay = np.exp(-z)
                    voltage[i] = equilibrium + (voltage[i]-equilibrium)*decay
                if k < 0 and voltage[i] > threshold:
                    fired[n_fired] = i
                    n_fired += 1
                    last_spike[i] = tick
                    if record[i]:
                        if recorded == len(output_i):
                            next_i = np.empty(2*len(output_i), dtype=np.int32)
                            next_t = np.empty(2*len(output_t), dtype=np.int64)
                            next_i[:recorded], next_t[:recorded] = output_i, output_t
                            output_i, output_t = next_i, next_t
                        output_i[recorded], output_t[recorded] = i, tick
                        recorded += 1
            else:
                voltage[i] = reset
            excitatory[i], inhibitory[i] = ge*e_decay, gi*i_decay
        total_spikes += n_fired
        destination = (tick+delay_ticks) % ring_size
        offset = pending_count[destination]
        for k in range(n_fired):
            pending[destination, offset+k] = fired[k]
        pending_count[destination] = offset+n_fired
        # Exact relaxation/integral for a release target frozen at the updated
        # membrane voltage. Applying its mass at tick end is first order overall.
        for k in range(len(graded_indices)):
            i = graded_indices[k]
            reference, baseline, gain, maximum, release_tau = graded_parameters[k, 2:]
            target = min(maximum, max(0.0, baseline+gain*(voltage[i]-reference)))
            z = dt/release_tau
            one_minus_decay = -np.expm1(-z)
            # Avoid cancellation of 1-(1-exp(-z))/z for very slow release.
            if z < 1e-4:
                relaxation_mean = z*(.5+z*(-1/6+z*(1/24-z/120)))
            else:
                relaxation_mean = 1-one_minus_decay/z
            average_rate = release[k]+(target-release[k])*relaxation_mean
            release[k] += (target-release[k])*one_minus_decay
            release_pending[destination, k] = max(0.0, average_rate)*dt/1000.0
        source_slot = tick % ring_size
        for k in range(pending_count[source_slot]):
            source = pending[source_slot, k]
            if not ablated[source]:
                for edge in range(indptr[source], indptr[source+1]):
                    target, weight = targets[edge], weights[edge]
                    if weight > 0:
                        excitatory[target] += weight*e_conversion
                    elif weight < 0:
                        inhibitory[target] -= weight*i_conversion
                    traversed_edges += 1
        pending_count[source_slot] = 0
        for k in range(len(graded_indices)):
            source, mass = graded_indices[k], release_pending[source_slot, k]
            if mass > 0 and not ablated[source]:
                for edge in range(indptr[source], indptr[source+1]):
                    target, weight = targets[edge], weights[edge]
                    if weight > 0:
                        excitatory[target] += mass*weight*e_conversion
                    elif weight < 0:
                        inhibitory[target] -= mass*weight*i_conversion
                    traversed_edges += 1
            release_pending[source_slot, k] = 0.0
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


class MixedNetwork(ConductanceNetwork):
    """Optional nonspiking cells with their actual incoming and outgoing edges.

    Reset uses each graded rest voltage and its corresponding release target;
    the delay queue starts empty (no invented pre-simulation synaptic history).
    Graph signs and weights are unchanged, including zero-sign unknown outputs.
    """

    def __init__(self, neuron_ids, indptr, targets, weights, *, graded_populations,
                 parameters=None, seed=0):
        super().__init__(neuron_ids, indptr, targets, weights, parameters=parameters, seed=seed)
        specs = tuple(graded_populations)
        if any(not isinstance(spec, GradedPopulationSpec) for spec in specs):
            raise ValueError("Expected explicit GradedPopulationSpec objects")
        self.graded_spec_json = json.dumps([asdict(s) for s in specs], sort_keys=True, separators=(",", ":"))
        ids = [identifier for spec in specs for identifier in spec.neuron_ids]
        if len(set(ids)) != len(ids):
            raise ValueError("A neuron cannot belong to multiple graded populations")
        self.graded_indices = self.indices_for_ids(ids)
        self._graded_slot = np.full(self.n_neurons, -1, dtype=np.int32)
        self._graded_slot[self.graded_indices] = np.arange(len(ids), dtype=np.int32)
        rows = []
        for spec in specs:
            if not self.parameters.inhibitory_reversal_mv < spec.resting_mv < self.parameters.excitatory_reversal_mv:
                raise ValueError("Graded rest must lie between conductance reversal potentials")
            values = [spec.resting_mv, spec.membrane_tau_ms, spec.release_reference_mv,
                      spec.release_baseline_hz_equiv, spec.release_gain_hz_equiv_per_mv,
                      spec.release_max_hz_equiv, spec.release_tau_ms]
            rows.extend([values]*len(spec.neuron_ids))
        self._graded_parameters = np.array(rows, dtype=np.float64).reshape((-1, 7))
        self.release_hz_equiv = np.zeros(len(ids), dtype=np.float64)
        self._release_pending = np.zeros((self.delay_ticks+1, len(ids)), dtype=np.float64)
        self.reset()

    def reset(self, *, seed=None, keep_ablations=False):
        super().reset(seed=seed, keep_ablations=keep_ablations)
        if hasattr(self, "_release_pending"):
            p = self._graded_parameters
            self.voltage_mv[self.graded_indices] = p[:, 0]
            self.release_hz_equiv[:] = np.clip(p[:, 3]+p[:, 4]*(p[:, 0]-p[:, 2]), 0, p[:, 5])
            self._release_pending.fill(0)

    def _run_dynamics(self, steps, poisson_indices, probabilities, input_weights, record, event_arrays):
        p = self.parameters
        return _mixed_kernel(
            steps, self.tick, p.dt_ms, p.resting_mv, p.reset_mv, p.threshold_mv,
            p.membrane_tau_ms, p.excitatory_reversal_mv, p.inhibitory_reversal_mv,
            np.exp(-p.dt_ms/(2*p.excitatory_tau_ms)), np.exp(-p.dt_ms/(2*p.inhibitory_tau_ms)),
            p.excitatory_gain/(p.excitatory_reversal_mv-p.resting_mv),
            p.inhibitory_gain/(p.resting_mv-p.inhibitory_reversal_mv), p.voltage_method == "pade22",
            self.voltage_mv, self.excitatory_g, self.inhibitory_g, self.last_spike_tick,
            self.refractory_ticks, self._current_mv, poisson_indices, probabilities,
            input_weights, self._rng_state, self.indptr, self.targets, self.weights,
            self.ablated, self.delay_ticks, self._pending, self._pending_count, record, *event_arrays,
            self._graded_slot, self.graded_indices, self._graded_parameters,
            self.release_hz_equiv, self._release_pending)

    def state_dict(self):
        state = super().state_dict()
        state.update(backend="mixed-graded-conductance-v1", graded_spec_json=self.graded_spec_json,
                     release_hz_equiv=self.release_hz_equiv.copy(), release_pending=self._release_pending.copy())
        return state

    def load_state_dict(self, state):
        if state.get("backend") != "mixed-graded-conductance-v1":
            raise ValueError("Checkpoint belongs to another neural backend")
        if str(state.get("graded_spec_json")) != self.graded_spec_json:
            raise ValueError("Checkpoint graded population specification differs")
        for name, destination, scale in (("release_hz_equiv", self.release_hz_equiv, 1.),
                                        ("release_pending", self._release_pending, self.parameters.dt_ms/1000)):
            value = np.asarray(state[name])
            maximum = self._graded_parameters[:, 5]*scale
            if (value.shape != destination.shape or value.dtype != np.float64
                    or not np.isfinite(value).all() or np.any(value < 0)
                    or np.any(value > maximum*(1+1e-12))):
                raise ValueError(f"Invalid graded checkpoint array: {name}")
        # A graded cell must never be queued as a spike. Check before any writes.
        pending = np.asarray(state["pending"])
        if np.any(np.isin(pending, self.graded_indices)):
            raise ValueError("Graded cell incorrectly queued as a spike")
        base = dict(state, backend="conductance-lif-v1")
        super().load_state_dict(base)
        self.release_hz_equiv[:] = state["release_hz_equiv"]
        self._release_pending[:] = state["release_pending"]
