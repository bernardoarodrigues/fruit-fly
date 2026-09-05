#!/usr/bin/env python3
"""Experiment-local exact parallel H intervals; frozen serial kernel unchanged.

External randomness is supplied, never generated here. The caller owns its
immutable uniform streams, probabilities, run plan, archival and performance
budget. This module has no execution-on-import or full-network command.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import numpy as np
from numba import njit, prange, get_thread_id, get_num_threads, set_num_threads, threading_layer

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from inhibitory_factorial_solver import hybrid_step, coefficients, NODES32, WEIGHTS32

PHASE_NAMES = ("prethreshold", "postexternal", "postreset")
EDGE_COUNT_NAMES = ("visited_unblocked", "accepted", "target_unavailable", "source_blocked")
SIGN_NAMES = ("negative", "zero", "positive")
WORK_NAMES = ("available_cell_updates", "hybrid_quadrature_calls", "inverse_iterations_max")
SOLVER_NAMES = ("inverse_residual_max", "tail_bound_max_mv", "h_max_before", "stiffness_max_before")
EVENT_COLUMNS = ("tick", "source_index", "edge_index", "target_index", "disposition")
DISPOSITIONS = {"accepted": 0, "target_unavailable": 1, "source_blocked": 2}
FAILURES = {0: "none", 1: "hybrid_interval_failure", 2: "nonfinite_or_invalid_integrated_state",
            3: "pending_queue_capacity", 4: "nonfinite_or_invalid_postdelivery_state",
            5: "hybrid_lower_bound_violation"}
PROGRESS_PHASES = {0: "partial_integration", 1: "integration_complete", 2: "enqueue_complete",
                   3: "synaptic_delivery_complete", 4: "external_delivery_complete", 5: "reset_complete"}


def configure_threads(count=4):
    """Explicit caller-owned thread mask; never changed on module import."""
    if not isinstance(count, int) or count < 1:
        raise ValueError("Thread count must be a positive integer")
    set_num_threads(count)
    if get_num_threads() != count:
        raise RuntimeError("Requested Numba thread mask was not established")
    return count


def parallel_runtime_info():
    """Thread layer is available after the first parallel invocation."""
    try:
        layer = threading_layer()
    except ValueError:
        layer = None
    return {"numba_threads": get_num_threads(), "threading_layer": layer,
            "fastmath": False, "parallel_scope": "independent available H intervals only"}


@njit(cache=True, inline="never")
def _safe_h_interval(v, s, h, a, b, coefficient):
    # Catch inside an ordinary compiled function: the prange body has a single
    # entry/exit, and each cell writes only its own scratch row/status.
    try:
        result = hybrid_step(v, s, h, .1, a, b, coefficient, NODES32, WEIGHTS32)
        return result[0], result[1], result[2], result[3], result[4], result[5], result[6], 0
    except Exception:
        return 0., 0., 0., 0., 0., 0, 0., 1


@njit(cache=True, parallel=True)
def _h_intervals(tick, a, b, coefficient, v, s, h, last, refractory,
                 scratch, status, worker_ids):
    """Read native state; write only independent scratch, never commit state."""
    for cell in prange(len(v)):
        worker_ids[cell] = get_thread_id()
        if tick - last[cell] >= refractory[cell]:
            result = _safe_h_interval(v[cell], s[cell], h[cell], a, b, coefficient)
            scratch[cell, 0] = result[0]
            scratch[cell, 1] = result[1]
            scratch[cell, 2] = result[2]
            scratch[cell, 3] = result[3]
            scratch[cell, 4] = result[4]
            scratch[cell, 5] = result[5]
            scratch[cell, 6] = result[6]
            status[cell] = result[7]
        else:
            status[cell] = 2  # No interval evaluated; row must not be read.


@njit(cache=True)
def _append_spike(indices, ticks, used, cell, tick):
    if used == len(indices):
        ii = np.empty(2 * len(indices), np.int32)
        tt = np.empty(2 * len(ticks), np.int64)
        ii[:used], tt[:used] = indices, ticks
        indices, ticks = ii, tt
    indices[used], ticks[used] = cell, tick
    return indices, ticks


@njit(cache=True)
def _append_event(events, used, tick, source, edge, target, disposition):
    if used == len(events):
        bigger = np.empty((2 * len(events), 5), np.int64)
        bigger[:used] = events
        events = bigger
    events[used, 0], events[used, 1] = tick, source
    events[used, 2], events[used, 3], events[used, 4] = edge, target, disposition
    return events


@njit(cache=True)
def _run(first_tick, uniforms, probabilities, hybrid, package, a, b, coefficient,
         v, s, h, last, refractory, blocked, pending, pending_count,
         indptr, targets, weights, inputs, selected, selected_column, log_events):
    nsteps, nin = uniforms.shape
    ncells, nsel = len(v), len(selected)
    candidate = np.zeros((nsteps, nin), np.bool_)
    applied = np.zeros_like(candidate)
    sv = np.full((nsteps + 1, nsel), np.nan)
    ss, sh = np.full_like(sv, np.nan), np.full_like(sv, np.nan)
    spre = np.full((nsteps, nsel), np.nan)
    savail = np.zeros((nsteps, nsel), np.bool_)
    sfired = np.zeros_like(savail)
    sactive = np.zeros_like(savail)
    phase_min = np.full((nsteps, 3), np.nan)
    phase_max = np.full_like(phase_min, np.nan)
    min_index = np.full((nsteps, 3), -1, np.int32)
    max_index = np.full_like(min_index, -1)
    nonfinite = np.zeros((nsteps, 3), np.int64)
    below = np.zeros_like(nonfinite)
    state_invalid = np.zeros((nsteps, 2), np.int64)
    work = np.zeros((nsteps, 3), np.int64)
    solver = np.zeros((nsteps, 4), np.float64)
    edge_counts = np.zeros((nsteps, 4, 3), np.int64)
    progress = np.zeros(nsteps, np.int8)
    ii = np.empty(max(128, min(8192, ncells)), np.int32)
    tt = np.empty(len(ii), np.int64)
    events = np.empty((128, 5), np.int64)
    active = np.empty(ncells, np.bool_)
    fired = np.empty(ncells, np.int32)
    # Reused for every tick in this advance call; never part of native state.
    # C arms allocate zero-length buffers and never enter the parallel helper.
    scratch = np.empty((ncells if hybrid else 0, 7), np.float64)
    interval_status = np.empty(ncells if hybrid else 0, np.int8)
    worker_ids = np.empty(ncells if hybrid else 0, np.int32)
    nspikes = nevents = completed = 0
    failure_code, failure_cell, failure_phase = 0, -1, 0
    failed_before = np.full(3, np.nan)
    for j in range(nsel):
        sv[0, j], ss[0, j], sh[0, j] = v[selected[j]], s[selected[j]], h[selected[j]]

    for k in range(nsteps):
        tick, nfired = first_tick + k, 0
        low, high, ilow, ihigh = np.inf, -np.inf, -1, -1
        if hybrid:
            _h_intervals(tick, a, b, coefficient, v, s, h, last, refractory,
                         scratch, interval_status, worker_ids)
        for cell in range(ncells):
            available = tick - last[cell] >= refractory[cell]
            active[cell] = available
            col = selected_column[cell]
            if col >= 0:
                savail[k, col] = available
            old_s, old_h = s[cell], h[cell]
            solver[k, 2] = max(solver[k, 2], old_h)
            solver[k, 3] = max(solver[k, 3], (1. + old_h) * .1 / 20.)
            if available:
                if hybrid:
                    # Commit in source index order. Speculative later-cell
                    # results are ignored after the first original failure.
                    if interval_status[cell] == 1:
                        failure_code, failure_cell, failure_phase = 1, cell, 0
                        failed_before[0], failed_before[1], failed_before[2] = v[cell], old_s, old_h
                        break
                    v[cell], s[cell], h[cell] = scratch[cell, 0], scratch[cell, 1], scratch[cell, 2]
                    work[k, 1] += int(old_h > 0.)
                    work[k, 2] = max(work[k, 2], int(scratch[cell, 5]))
                    solver[k, 0] = max(solver[k, 0], scratch[cell, 4])
                    solver[k, 1] = max(solver[k, 1], scratch[cell, 3])
                else:
                    # Keep the single signed source state and its exact operation order.
                    v[cell] = -52. + (v[cell] + 52.) * a + old_s * coefficient + 0. * (1. - a)
                    s[cell] = old_s * b
                work[k, 0] += 1
                if v[cell] > -45.:
                    last[cell] = tick
                    active[cell] = False
                    fired[nfired] = cell
                    nfired += 1
                    ii, tt = _append_spike(ii, tt, nspikes, cell, tick)
                    nspikes += 1
                    if col >= 0:
                        sfired[k, col] = True
            elif package == 1:
                v[cell] = -52.
                s[cell], h[cell] = old_s * b, old_h * b
            if col >= 0:
                spre[k, col], sactive[k, col] = v[cell], active[cell]
            value = v[cell]
            if not np.isfinite(value):
                nonfinite[k, 0] += 1
            else:
                if value < low:
                    low, ilow = value, cell
                if value > high:
                    high, ihigh = value, cell
                below[k, 0] += int(value < -75. - 1e-10)
            invalid = not (np.isfinite(v[cell]) and np.isfinite(s[cell]) and np.isfinite(h[cell]))
            invalid |= hybrid and (s[cell] < 0. or h[cell] < 0.)
            state_invalid[k, 0] += int(invalid)
            if invalid and failure_cell < 0:
                failure_cell = cell
        if failure_code:
            break
        phase_min[k, 0], phase_max[k, 0] = low, high
        min_index[k, 0], max_index[k, 0] = ilow, ihigh
        progress[k] = 1
        if state_invalid[k, 0]:
            failure_code, failure_phase = 2, 1
            break
        if hybrid and below[k, 0]:
            failure_code, failure_cell, failure_phase = 5, ilow, 1
            break
        destination = (tick + 18) % 19
        offset = pending_count[destination]
        if offset + nfired > pending.shape[1]:
            failure_code, failure_phase = 3, 1
            break
        for j in range(nfired):
            pending[destination, offset + j] = fired[j]
        pending_count[destination] = offset + nfired
        progress[k] = 2
        slot = tick % 19
        for j in range(pending_count[slot]):
            source = pending[slot, j]
            for edge in range(indptr[source], indptr[source + 1]):
                target = targets[edge]
                weight = np.float64(weights[edge])
                sign = 0 if weight < 0. else (2 if weight > 0. else 1)
                if blocked[source]:
                    edge_counts[k, 3, sign] += 1
                    disposition = 2
                else:
                    edge_counts[k, 0, sign] += 1
                    if package == 1 or active[target]:
                        if hybrid and weight < 0.:
                            h[target] += -weight * (1. / 23.)
                        else:
                            s[target] += weight
                        edge_counts[k, 1, sign] += 1
                        disposition = 0
                    else:
                        edge_counts[k, 2, sign] += 1
                        disposition = 1
                if log_events and selected_column[target] >= 0:
                    events = _append_event(events, nevents, tick, source, edge, target, disposition)
                    nevents += 1
        pending_count[slot] = 0
        progress[k] = 3
        for j in range(nin):
            event = uniforms[k, j] < probabilities[j]
            candidate[k, j] = event
            target = inputs[j]
            if event and active[target]:
                v[target] += 68.75
                applied[k, j] = True
        progress[k] = 4

        # One complete scan records actual postexternal state and prospective
        # reset extrema. Prospective reset diagnostics become valid only at phase5.
        low, high, ilow, ihigh = np.inf, -np.inf, -1, -1
        reset_low, reset_high, reset_ilow, reset_ihigh = np.inf, -np.inf, -1, -1
        for cell in range(ncells):
            value = v[cell]
            will_fire = last[cell] == tick
            reset_value = -52. if will_fire else value
            if np.isfinite(value):
                if value < low:
                    low, ilow = value, cell
                if value > high:
                    high, ihigh = value, cell
                below[k, 1] += int(value < -75. - 1e-10)
            else:
                nonfinite[k, 1] += 1
            if np.isfinite(reset_value):
                if reset_value < reset_low:
                    reset_low, reset_ilow = reset_value, cell
                if reset_value > reset_high:
                    reset_high, reset_ihigh = reset_value, cell
                below[k, 2] += int(reset_value < -75. - 1e-10)
            else:
                nonfinite[k, 2] += 1
            invalid = not (np.isfinite(value) and np.isfinite(s[cell]) and np.isfinite(h[cell]))
            invalid |= hybrid and (s[cell] < 0. or h[cell] < 0.)
            state_invalid[k, 1] += int(invalid)
            if invalid and failure_cell < 0:
                failure_cell = cell
        phase_min[k, 1], phase_max[k, 1] = low, high
        min_index[k, 1], max_index[k, 1] = ilow, ihigh
        if state_invalid[k, 1]:
            failure_code, failure_phase = 4, 4
            break
        if hybrid and below[k, 1]:
            failure_code, failure_cell, failure_phase = 5, ilow, 4
            break
        for j in range(nfired):
            cell = fired[j]
            v[cell] = -52.
            if package == 0:
                s[cell], h[cell] = 0., 0.
        phase_min[k, 2], phase_max[k, 2] = reset_low, reset_high
        min_index[k, 2], max_index[k, 2] = reset_ilow, reset_ihigh
        progress[k] = 5
        for j in range(nsel):
            sv[k + 1, j], ss[k + 1, j], sh[k + 1, j] = v[selected[j]], s[selected[j]], h[selected[j]]
        completed += 1
    return (completed, failure_code, failure_cell, failure_phase, failed_before,
            ii[:nspikes], tt[:nspikes], candidate, applied, sv, ss, sh, spre, savail, sfired, sactive,
            phase_min, phase_max, min_index, max_index, nonfinite, below, state_invalid,
            work, solver, edge_counts, progress, events[:nevents])


class FactorialNetwork:
    """Single graph, mutable experimental state; arm and input membership fixed."""

    def __init__(self, neuron_ids, indptr, targets, weights, arm, input_indices, selected_indices, seed=11):
        if arm not in ("C0", "C1", "H0", "H1"):
            raise ValueError("arm must be C0, C1, H0 or H1")
        self.neuron_ids = self._integers(neuron_ids, np.int64, "neuron IDs")
        self.indptr = self._integers(indptr, np.int64, "indptr")
        self.targets = self._integers(targets, np.int32, "targets")
        self.weights = np.ascontiguousarray(weights, dtype=np.float32)
        self.n_neurons, self.n_edges = len(self.neuron_ids), len(self.weights)
        n = self.n_neurons
        if n == 0 or len(np.unique(self.neuron_ids)) != n or n > np.iinfo(np.int32).max:
            raise ValueError("Invalid neuron IDs/count")
        if self.indptr.shape != (n+1,) or self.indptr[0] != 0 or self.indptr[-1] != self.n_edges or (np.diff(self.indptr)<0).any():
            raise ValueError("Invalid CSR pointers")
        if self.targets.shape != self.weights.shape or self.weights.ndim != 1 or not np.isfinite(self.weights).all() or ((self.targets<0)|(self.targets>=n)).any():
            raise ValueError("Invalid CSR targets/weights")
        self.input_indices = self._indices(input_indices)
        self.selected_indices = self._indices(selected_indices)
        self._selected_column = np.full(n, -1, np.int32)
        self._selected_column[self.selected_indices] = np.arange(len(self.selected_indices))
        self.arm, self.seed = arm, int(seed)
        self.v, self.s, self.h = np.full(n, -52.), np.zeros(n), np.zeros(n)
        self.last = np.full(n, -(2**60), np.int64)
        self.refractory = np.full(n, 22, np.int64)
        self.refractory[self.input_indices] = 0
        self.blocked = np.zeros(n, np.bool_)
        self._pending = np.empty((19, n), np.int32)
        self.pending_count = np.zeros(19, np.int64)
        self.tick, self.failed, self.failure = 0, False, None
        self._a, self._b, self._coefficient = coefficients(.1)
        self._graph_sha256 = None
        # Familiar aliases ease parity checks; s is p for H and signed s for C.
        self.voltage_mv, self.synaptic_mv = self.v, self.s
        self.last_spike_tick, self.refractory_ticks, self.ablated = self.last, self.refractory, self.blocked
        self.delay_ticks = 18

    @staticmethod
    def _integers(values, dtype, label):
        raw = np.asarray(values)
        if raw.ndim != 1 or (raw.size and raw.dtype.kind not in "iu"):
            raise ValueError(label + " must be a one-dimensional integer array")
        limits = np.iinfo(dtype)
        if raw.size and ((raw < limits.min).any() or (raw > limits.max).any()):
            raise ValueError(label + " outside dtype range")
        return np.ascontiguousarray(raw, dtype=dtype)

    def _indices(self, values):
        result = self._integers(values, np.int32, "indices")
        if ((result<0)|(result>=self.n_neurons)).any() or len(np.unique(result)) != len(result):
            raise ValueError("Invalid/duplicate neuron indices")
        return result

    @property
    def time_ms(self):
        """Clock of the last coherent completed tick; see failure for partial state."""
        return self.tick * .1

    @property
    def graph_sha256(self):
        if self._graph_sha256 is None:
            digest = hashlib.sha256()
            for array in (self.neuron_ids, self.indptr, self.targets, self.weights):
                digest.update(str(array.shape).encode())
                digest.update(memoryview(array).cast("B"))
            self._graph_sha256 = digest.hexdigest()
        return self._graph_sha256

    def advance(self, uniforms, probabilities, *, log_selected_events=False):
        if self.failed:
            raise RuntimeError("Previous transition failed; preserve partial state and do not continue")
        u = np.ascontiguousarray(uniforms, dtype=np.float64)
        p = np.ascontiguousarray(probabilities, dtype=np.float64)
        if u.ndim != 2 or u.shape[1] != len(self.input_indices) or p.shape != (len(self.input_indices),):
            raise ValueError("Expected uniforms[nsteps,ninputs] and probabilities[ninputs]")
        if not np.isfinite(u).all() or ((u<0)|(u>=1)).any() or not np.isfinite(p).all() or ((p<0)|(p>1)).any():
            raise ValueError("Uniforms must be in [0,1), probabilities in [0,1]")
        if not np.all(self.refractory[self.input_indices] == 0):
            raise ValueError("Input refractory convention was changed")
        expected_refractory = np.full(self.n_neurons, 22, np.int64)
        expected_refractory[self.input_indices] = 0
        if not np.array_equal(self.refractory, expected_refractory):
            raise ValueError("Fixed refractory convention was changed")
        start = self.tick
        values = _run(start,u,p,self.arm.startswith("H"),int(self.arm[1]),self._a,self._b,self._coefficient,
            self.v,self.s,self.h,self.last,self.refractory,self.blocked,self._pending,self.pending_count,
            self.indptr,self.targets,self.weights,self.input_indices,self.selected_indices,self._selected_column,bool(log_selected_events))
        (done,code,cell,phase,before,ii,tt,candidate,applied,sv,ss,sh,spre,savail,sfired,sactive,
         vmin,vmax,imin,imax,nf,below,invalid,work,solver,edges,progress,events) = values
        self.tick += int(done)
        self.failed = bool(code)
        if code:
            self.failure = {"code": int(code), "reason": FAILURES[int(code)], "attempted_tick": self.tick,
                "phase": PROGRESS_PHASES[int(phase)], "phase_code": int(phase), "cell_index": int(cell),
                "state_before_failed_interval": [float(x) if np.isfinite(x) else None for x in before],
                "state_before_nonfinite": (~np.isfinite(before)).tolist(), "last_completed_tick": self.tick,
                "completed_prefix_end_tick": self.tick,
                "last_completed_transition_tick": self.tick - 1 if self.tick else None,
                "coherent_state": False, "note": "Mutable arrays may contain part of attempted_tick; tick/time_ms is only the completed-prefix clock"}
        per_tick = {"phase_min_mv":vmin,"phase_max_mv":vmax,"phase_min_index":imin,"phase_max_index":imax,
            "phase_nonfinite_count":nf,"phase_below_reversal_count":below,"state_invalid_count":invalid,
            "work":work,"solver":solver,"edge_counts":edges,"phase_reached":progress}
        complete_spikes = tt < self.tick
        complete_events = events[:,0] < self.tick
        result = {"status":"failed" if code else "complete", "start_tick":start,"end_tick":self.tick,
            "completed_ticks":int(done),"requested_ticks":len(u),"coherent_state":not bool(code),"failure":self.failure,
            "spike_indices":ii[complete_spikes],"spike_ticks":tt[complete_spikes],
            "candidate":candidate[:done],"applied":applied[:done],
            "selected_v":sv[:done+1],"selected_s":ss[:done+1],"selected_h":sh[:done+1],
            "selected_prethreshold_v":spre[:done],"selected_available":savail[:done],
            "selected_fired":sfired[:done],"selected_delivery_available":sactive[:done],
            "selected_direct_available":sactive[:done],
            "selected_synaptic_available":np.ones_like(sactive[:done]) if self.arm.endswith("1") else sactive[:done],
            "per_tick":{name:value[:done] for name,value in per_tick.items()},
            "selected_events":events[complete_events],"partial":None,
            "schema":{"phases":PHASE_NAMES,"edge_counts":EDGE_COUNT_NAMES,"signs":SIGN_NAMES,
                "work":WORK_NAMES,"solver":SOLVER_NAMES,"event_columns":EVENT_COLUMNS,"dispositions":DISPOSITIONS,
                "selected_delivery_available":"Compatibility alias for selected_direct_available, not package1 synaptic eligibility",
                "selected_synaptic_available":"Target eligibility only; the independent presynaptic outgoing block still applies"}}
        if code:
            result["partial"] = {"spike_indices":ii[~complete_spikes],"spike_ticks":tt[~complete_spikes],
                "selected_events":events[~complete_events],"candidate":candidate[done].copy(),"applied":applied[done].copy(),
                "selected_prethreshold_v":spre[done].copy(),"selected_available":savail[done].copy(),
                "selected_fired":sfired[done].copy(),"selected_delivery_available":sactive[done].copy(),
                "selected_direct_available":sactive[done].copy(),
                "selected_synaptic_available":np.ones_like(sactive[done]) if self.arm.endswith("1") else sactive[done].copy(),
                "diagnostics":{name:value[done].copy() for name,value in per_tick.items()},
                "validity":"Only operations through failure.phase completed; false/NaN values for later or unvisited cells are not negative observations"}
        return result

    def step(self, uniforms, probabilities, *, log_selected_events=False):
        return self.advance(np.asarray(uniforms).reshape(1,-1), probabilities, log_selected_events=log_selected_events)

    def checkpoint(self):
        return {"version":1,"arm":self.arm,"graph_sha256":self.graph_sha256,"seed":self.seed,
            "tick":self.tick,"time_ms":self.time_ms,"coherent_state":not self.failed,"failure":self.failure,
            "parameters":{"dt_ms":.1,"resting_mv":-52.,"reset_mv":-52.,"threshold_mv":-45.,
                "membrane_tau_ms":20.,"synapse_tau_ms":5.,"delay_ticks":18,"refractory_ticks":22,
                "input_refractory_ticks":0,"direct_voltage_increment_mv":68.75,"inhibitory_reversal_mv":-75.},
            "v":self.v.copy(),"s":self.s.copy(),"h":self.h.copy(),
            "last":self.last.copy(),"refractory":self.refractory.copy(),"blocked":self.blocked.copy(),
            "input_indices":self.input_indices.copy(),"selected_indices":self.selected_indices.copy(),
            "pending_count":self.pending_count.copy(),
            "pending":np.concatenate([self._pending[slot,:count] for slot,count in enumerate(self.pending_count)]),
            "rng_ownership":"No RNG in kernel or wrapper; caller must archive supplied uniforms and source RNG boundaries",
            "synaptic_state_meaning":"positive effective-current p in mV" if self.arm.startswith("H") else "canonical signed current-like s in mV"}

    state_dict = checkpoint
