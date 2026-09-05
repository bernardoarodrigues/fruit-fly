#!/usr/bin/env python3
"""Conditional, experiment-local H1 edge-delivery intervention; no run on import.

Only exact CSR edges can be suppressed, only at delivery ticks in [start, end).
Source-output blocking and postsynaptic eligibility are evaluated first. The
original source-block counters retain their meaning; a separate sidecar records
suppressed deliveries. There is no anatomical selection or RNG in this module.
A caller must independently gate any real intervention and archive its spec.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import sys
import textwrap

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
BASE_PATH = SCRIPTS / "inhibitory_recurrent_panel_kernel.py"
BASE_SHA256 = "fecae2793af7d5b491a9090d0a8d0b712bba727d918c39be14e0e73048dd4eff"
SOLVER_SHA256 = "ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711"
SOURCE_BYTES = BASE_PATH.read_bytes()
if hashlib.sha256(SOURCE_BYTES).hexdigest() != BASE_SHA256:
    raise RuntimeError("Pinned panel source changed; intervention derivation refused")
if hashlib.sha256((SCRIPTS / "inhibitory_factorial_solver.py").read_bytes()).hexdigest() != SOLVER_SHA256:
    raise RuntimeError("Pinned scalar solver changed; intervention derivation refused")
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import inhibitory_recurrent_panel_kernel as original

if Path(original.__file__).resolve() != BASE_PATH:
    raise RuntimeError("Unexpected panel module location")

SOURCE = SOURCE_BYTES.decode("utf-8")
TREE = ast.parse(SOURCE)
DERIVATION = []


def _extract(name, parent=None):
    nodes = TREE.body if parent is None else next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == parent).body
    node = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)
    # Keep the first line's indentation before dedenting class methods. The
    # function's lineno deliberately excludes any decorator.
    return textwrap.dedent("".join(SOURCE.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])).rstrip()


def _replace(source, label, old, new):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Source patch {label!r} expected one anchor, found {count}")
    DERIVATION.append({"label": label, "replacement_count": count, "old": old, "new": new})
    return source.replace(old, new, 1)


_run_source = _extract("_run")
_run_source = _replace(_run_source, "run_arguments",
    "selected_column, log_events, event_mask):",
    "selected_column, log_events, event_mask, edge_suppressed, window_start, window_end):")
_run_source = _replace(_run_source, "separate_telemetry_allocation",
    "edge_counts = np.zeros((nsteps, 4, 3), np.int64)",
    "edge_counts = np.zeros((nsteps, 4, 3), np.int64)\n    suppressed_counts = np.zeros((nsteps, 3), np.int64)\n    suppressed_events = np.empty((128, 5), np.int64)\n    nsuppressed = 0")
_DELIVERY = """                    if hybrid and weight < 0.:
                        h[target] += -weight * (1. / 23.)
                    else:
                        s[target] += weight
                    edge_counts[k, 1, sign] += 1
                    disposition = 0"""
_INTERVENTION = """                    if edge_suppressed[edge] and window_start <= tick < window_end:
                        suppressed_counts[k, sign] += 1
                        disposition = 3
                        suppressed_events = _append_event(suppressed_events, nsuppressed, tick, source, edge, target, disposition)
                        nsuppressed += 1
                    else:
                        if hybrid and weight < 0.:
                            h[target] += -weight * (1. / 23.)
                        else:
                            s[target] += weight
                        edge_counts[k, 1, sign] += 1
                        disposition = 0"""
_run_source = _replace(_run_source, "delivery_only",
    textwrap.indent(_DELIVERY, "    "), textwrap.indent(_INTERVENTION, "    "))
_run_source = _replace(_run_source, "run_return",
    "ref_found, ref_ticks, ref_cells, ref_values,\n            tick_ref_found, tick_ref_ticks, tick_ref_cells, tick_ref_values)",
    "ref_found, ref_ticks, ref_cells, ref_values,\n            tick_ref_found, tick_ref_ticks, tick_ref_cells, tick_ref_values,\n            suppressed_counts, suppressed_events[:nsuppressed])")
# Only the newly derived dispatcher has cache=False. Imported frozen functions
# retain their original compilation settings and are never replaced/modified.
_namespace = dict(vars(original))
_namespace["__name__"] = __name__
_namespace["__file__"] = __file__
exec(compile("@njit(cache=False)\n" + _run_source, __file__, "exec"), _namespace)
_derived_run = _namespace["_run"]

_advance_source = _extract("advance", "FactorialNetwork")
_advance_source = _replace(_advance_source, "advance_call",
    "bool(log_selected_events),event_mask)",
    "bool(log_selected_events),event_mask,self._edge_suppressed,self._window_start,self._window_end)")
_advance_source = _replace(_advance_source, "advance_unpack",
    "rf,rt,ri,rv,tf,ttick,ti,tv) = values",
    "rf,rt,ri,rv,tf,ttick,ti,tv,suppressed_counts,suppressed_events) = values")
_advance_source = _replace(_advance_source, "advance_sidecar",
    "return result",
    """complete_suppressed = suppressed_events[:, 0] < self.tick
self.last_edge_intervention = self._telemetry(
    start, self.tick, len(u), suppressed_counts[:done],
    suppressed_events[complete_suppressed],
    {"counts": suppressed_counts[done].copy(),
     "events": suppressed_events[~complete_suppressed],
     "validity": "Only operations through failure.phase completed"} if code else None)
if len(suppressed_events):
    result["schema"]["dispositions"] = dict(DISPOSITIONS, edge_suppressed=3)
return result""".replace("\n", "\n    "))
exec(compile(_advance_source, __file__, "exec"), _namespace)
_derived_advance = _namespace["advance"]


def source_derivation():
    """Exact source pins, replacement anchors/counts and generated code hashes."""
    return {"base_path": str(BASE_PATH), "base_sha256": BASE_SHA256,
        "solver_sha256": SOLVER_SHA256, "patches": [dict(x) for x in DERIVATION],
        "derived_run_sha256": hashlib.sha256(_run_source.encode()).hexdigest(),
        "derived_advance_sha256": hashlib.sha256(_advance_source.encode()).hexdigest(),
        "derived_numba_cache": False}


class EdgeDeliveryInterventionNetwork(original.FactorialNetwork):
    """H1 only. Exact no-suppression outputs; intervention telemetry is separate.

    Suppression is at delayed arrival, not source spike time; it does not remove
    queued source spikes, block a whole source, change other outgoing edges,
    decay/reset received state, or alter input candidates or RNG consumption.
    Restoring a checkpoint leaves this instance's intervention spec fixed.
    checkpoint() remains the original schema; archive intervention_specification()
    separately. Existing past suppressions cannot be inferred from that schema.
    """

    def __init__(self, neuron_ids, indptr, targets, weights, arm, input_indices,
                 selected_indices, seed=11, *, suppressed_edge_indices=(), delivery_window=None):
        super().__init__(neuron_ids, indptr, targets, weights, arm, input_indices, selected_indices, seed)
        if arm != "H1":
            raise ValueError("This intervention extension supports H1 only")
        edges = self._integers(suppressed_edge_indices, np.int64, "suppressed CSR edge indices").copy()
        if ((edges < 0) | (edges >= self.n_edges)).any() or len(np.unique(edges)) != len(edges):
            raise ValueError("Invalid or duplicate suppressed CSR edge indices")
        if delivery_window is None:
            if len(edges):
                raise ValueError("Nonempty edge suppression requires a delivery window")
            start = end = 0
        else:
            if not isinstance(delivery_window, (tuple, list)) or len(delivery_window) != 2:
                raise ValueError("Expected a half-open (start_tick, end_tick) pair")
            start, end = (self._tick_integer(x, "window tick") for x in delivery_window)
            if end <= start:
                raise ValueError("Delivery window must have positive duration")
        self._edge_suppressed = np.zeros(self.n_edges, np.bool_)
        self._edge_suppressed[edges] = True
        self._edge_suppressed.flags.writeable = False
        edges.flags.writeable = False
        self.suppressed_edge_indices = edges
        self._window_start, self._window_end = start, end
        self.last_edge_intervention = None

    @staticmethod
    def _tick_integer(value, label):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError(label + " must be an integer")
        result = int(value)
        if not 0 <= result <= np.iinfo(np.int64).max - 19:
            raise ValueError(label + " outside safe nonnegative tick range")
        return result

    def intervention_specification(self):
        return {"version": 1, "graph_sha256": self.graph_sha256,
            "suppressed_edge_indices": self.suppressed_edge_indices.copy(),
            "delivery_window_ticks": [self._window_start, self._window_end],
            "enabled": bool(len(self.suppressed_edge_indices)),
            "dt_ms": .1, "selection": "Explicit CSR edge identities only; no anatomical selector",
            "timing": "Absolute delayed-arrival ticks, start inclusive and end exclusive",
            "precedence": "source_blocked, target_unavailable, edge_suppressed, accepted",
            "source_and_queue_semantics": "Outgoing source masks and pending source spike queues remain unchanged",
            "edge_count_identity": "visited_unblocked = accepted + target_unavailable + sidecar suppressed_counts",
            "base_sha256": BASE_SHA256, "solver_sha256": SOLVER_SHA256}

    def _telemetry(self, start, end, requested, counts, events, partial):
        return {"start_tick": start, "end_tick": end, "requested_ticks": requested,
            "counts": counts, "events": events, "partial": partial,
            "schema": {"count_signs": original.SIGN_NAMES,
                "event_columns": original.EVENT_COLUMNS, "edge_suppressed_disposition": 3,
                "counts": "Otherwise eligible delivered edges suppressed by the explicit edge/window condition",
                "events": "All suppressed deliveries, independently of selected event logging"}}

    def advance(self, uniforms, probabilities, *, log_selected_events=False, event_indices=None):
        if self.tick + len(uniforms) > np.iinfo(np.int64).max - 19:
            raise ValueError("Requested advance exceeds safe absolute tick range")
        if len(self.suppressed_edge_indices):
            return _derived_advance(self, uniforms, probabilities,
                log_selected_events=log_selected_events, event_indices=event_indices)
        result = super().advance(uniforms, probabilities,
            log_selected_events=log_selected_events, event_indices=event_indices)
        self.last_edge_intervention = self._telemetry(result["start_tick"], result["end_tick"], result["requested_ticks"],
            np.zeros((result["completed_ticks"], 3), np.int64), np.empty((0, 5), np.int64),
            {"counts": np.zeros(3, np.int64), "events": np.empty((0, 5), np.int64),
             "validity": "Only operations through failure.phase completed"} if result["partial"] is not None else None)
        return result

    def restore_checkpoint(self, checkpoint):
        """Validate an original full coherent H1 checkpoint, then copy exactly.

        Extra caller-owned archive fields are ignored; RNG is intentionally not
        inferred or restored. No mutable field changes before validation passes.
        Packed pending slots preserve their saved slot order and row order.
        Failed/partial checkpoints are never resumed by this API.
        """
        cp = checkpoint
        if not isinstance(cp, dict):
            raise ValueError("Expected a checkpoint dictionary")
        expected = super().checkpoint()
        for key in ("version", "arm", "graph_sha256", "seed", "parameters", "rng_ownership", "synaptic_state_meaning"):
            if cp.get(key) != expected[key]:
                raise ValueError("Checkpoint identity mismatch: " + key)
        if cp.get("coherent_state") is not True or cp.get("failure") is not None:
            raise ValueError("Failed or incoherent checkpoint cannot be restored")
        tick = self._tick_integer(cp.get("tick"), "checkpoint tick")
        if not isinstance(cp.get("time_ms"), (int, float, np.floating)) or cp["time_ms"] != tick * .1:
            raise ValueError("Checkpoint clock mismatch")
        arrays = {}
        specifications = {"v": (np.float64, (self.n_neurons,)), "s": (np.float64, (self.n_neurons,)),
            "h": (np.float64, (self.n_neurons,)), "last": (np.int64, (self.n_neurons,)),
            "refractory": (np.int64, (self.n_neurons,)), "blocked": (np.bool_, (self.n_neurons,)),
            "input_indices": (np.int32, self.input_indices.shape), "selected_indices": (np.int32, self.selected_indices.shape),
            "pending_count": (np.int64, (19,))}
        for key, (dtype, shape) in specifications.items():
            value = cp.get(key)
            if not isinstance(value, np.ndarray) or value.dtype != np.dtype(dtype) or value.shape != shape:
                raise ValueError("Checkpoint array shape/dtype mismatch: " + key)
            arrays[key] = value.copy(order="C")
        for key in ("input_indices", "selected_indices", "refractory"):
            if not np.array_equal(arrays[key], expected[key]):
                raise ValueError("Checkpoint fixed membership/convention mismatch: " + key)
        if not all(np.isfinite(arrays[key]).all() for key in ("v", "s", "h")):
            raise ValueError("Checkpoint contains nonfinite neural state")
        if (arrays["s"] < 0).any() or (arrays["h"] < 0).any() or (arrays["v"] < -75. - 1e-10).any():
            raise ValueError("Checkpoint violates H1 state bounds")
        valid_last = (arrays["last"] == -(2**60)) | ((arrays["last"] >= 0) & (arrays["last"] < tick))
        if not valid_last.all():
            raise ValueError("Checkpoint last-spike tick is neither the original sentinel nor the completed past")
        counts = arrays["pending_count"]
        if ((counts < 0) | (counts > self.n_neurons)).any() or counts[(tick + 18) % 19] != 0:
            raise ValueError("Checkpoint pending counts/empty next-enqueue slot invalid")
        packed = cp.get("pending")
        if not isinstance(packed, np.ndarray) or packed.dtype != np.dtype(np.int32) or packed.shape != (int(counts.sum()),):
            raise ValueError("Checkpoint packed pending shape/dtype mismatch")
        if ((packed < 0) | (packed >= self.n_neurons)).any():
            raise ValueError("Checkpoint pending graph index invalid")
        # Check the frozen kernel's one source-index-ordered firing list per slot.
        offset = 0
        rows = []
        for slot, count in enumerate(counts):
            row = packed[offset:offset + count].copy()
            if len(row) and ((np.diff(row) <= 0).any() or (arrays["last"][row] < tick + (slot - tick) % 19 - 18).any()):
                raise ValueError("Checkpoint pending slot order/history invalid")
            rows.append(row)
            offset += int(count)
        # No operation above this line mutates the network.
        for key, destination in (("v", self.v), ("s", self.s), ("h", self.h), ("last", self.last),
                                 ("refractory", self.refractory), ("blocked", self.blocked)):
            destination[:] = arrays[key]
        self.pending_count[:] = counts
        for slot, row in enumerate(rows):
            self._pending[slot, :len(row)] = row
        self.tick, self.failed, self.failure = tick, False, None
        self.last_edge_intervention = None
        return self

    @classmethod
    def from_checkpoint(cls, neuron_ids, indptr, targets, weights, checkpoint, *,
                        suppressed_edge_indices=(), delivery_window=None):
        """Construct an independent branch from a caller-loaded full checkpoint."""
        instance = cls(neuron_ids, indptr, targets, weights, "H1", checkpoint["input_indices"],
            checkpoint["selected_indices"], checkpoint["seed"],
            suppressed_edge_indices=suppressed_edge_indices, delivery_window=delivery_window)
        return instance.restore_checkpoint(checkpoint)


InterventionNetwork = EdgeDeliveryInterventionNetwork
