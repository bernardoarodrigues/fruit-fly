#!/usr/bin/env python3
"""Focused synthetic checks only; prints evidence, creates no experiment files.

The only graphs are constructed below (six and twelve synthetic cells). No
anatomical graph, saved real checkpoint, producer, or run plan is loaded.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import navigation_mbon_intervention_kernel as intervention

base = intervention.original
Network = intervention.EdgeDeliveryInterventionNetwork


def exact(a, b):
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
    if isinstance(a, dict):
        return isinstance(b, dict) and list(a) == list(b) and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)):
        return type(a) is type(b) and len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and (a == b or isinstance(a, float) and np.isnan(a) and np.isnan(b))


def fixture(recurrent=False):
    if recurrent:
        n = 12
        return (np.arange(100, 100 + n, dtype=np.int64), np.arange(0, (n + 1) * 3, 3, dtype=np.int64),
            np.array([(i + j) % n for i in range(n) for j in (1, 3, 7)], np.int32),
            np.tile(np.array([100., -46., 0.], np.float32), n), np.array([0, 4, 8], np.int32), np.arange(n, dtype=np.int32))
    return (np.arange(100, 106, dtype=np.int64), np.array([0, 3, 4, 5, 6, 6, 6], np.int64),
        np.array([2, 3, 4, 2, 5, 5], np.int32), np.array([-46., 9., 0., -23., 2., 3.], np.float32),
        np.array([0, 1], np.int32), np.arange(6, dtype=np.int32))


def create(module=base, *, recurrent=False, edges=(), window=None):
    ids, ptr, targets, weights, inputs, selected = fixture(recurrent)
    cls = module.FactorialNetwork if module is base else Network
    extra = {} if module is base else dict(suppressed_edge_indices=edges, delivery_window=window)
    return cls(ids, ptr, targets, weights, "H1", inputs, selected, 11, **extra)


def restore(cp, *, recurrent=False, edges=(), window=None):
    ids, ptr, targets, weights, _, _ = fixture(recurrent)
    return Network.from_checkpoint(ids, ptr, targets, weights, cp,
        suppressed_edge_indices=edges, delivery_window=window)


def main():
    started = time.perf_counter()
    checks, observations, failure = {}, {}, None

    def ck(name, condition):
        checks[name] = bool(condition)
        if not checks[name]:
            raise AssertionError(name)

    def same(name, a, b):
        ck(name, exact(a, b))

    def rejects(name, fn, exception=ValueError):
        try:
            fn()
        except exception:
            ck(name, True)
        else:
            ck(name, False)

    def edge_balance(name, output, telemetry):
        e = output["per_tick"]["edge_counts"]
        same(name + "_counts", e[:, 0, :], e[:, 1, :] + e[:, 2, :] + telemetry["counts"])
        recorded = np.zeros_like(telemetry["counts"])
        weights = fixture()[3]
        for tick, source, edge, target, disp in telemetry["events"]:
            sign = 0 if weights[edge] < 0 else 2 if weights[edge] > 0 else 1
            recorded[tick - output["start_tick"], sign] += 1
            ck(name + f"_event_identity_{tick}_{edge}", source == 0 and target == fixture()[2][edge] and disp == 3)
        same(name + "_recorded_event_counts", recorded, telemetry["counts"])

    try:
        base.configure_threads(1)
        derivation = intervention.source_derivation()
        ck("seven_single_replacement_patches", len(derivation["patches"]) == 7 and all(x["replacement_count"] == 1 for x in derivation["patches"]))
        ck("derived_cache_disabled", derivation["derived_numba_cache"] is False)
        ck("original_run_dispatcher_untouched", base._run is not intervention._derived_run)
        u = np.random.default_rng(11).random((120, 3))
        p = np.array([.35, .2, .4])
        for label, edges, window in (("empty", (), None), ("inactive_nonempty", (0, 1, 7), (1000, 1100))):
            a, b = create(recurrent=True), create(intervention, recurrent=True, edges=edges, window=window)
            for net in (a, b):
                net.s[::3] = 20.
                net.h[:] = np.resize(np.array([0., .1, 3., 100.]), 12)
            original = a.advance(u, p, log_selected_events=True, event_indices=[2, 7])
            actual = b.advance(u, p, log_selected_events=True, event_indices=[2, 7])
            same(label + "_every_output_key_dtype_shape_and_byte", original, actual)
            same(label + "_entire_checkpoint", a.checkpoint(), b.checkpoint())
            ck(label + "_no_suppression", not b.last_edge_intervention["counts"].any() and len(b.last_edge_intervention["events"]) == 0)

        # Initial external events at tick0 cause spikes at tick1 and deliveries
        # at tick19. Repeated impulses produce arrivals19,21,23,... naturally.
        u = np.zeros((40, 2))
        p = np.ones(2)
        original = create()
        altered = create(intervention, edges=[0, 2], window=(21, 23))
        original_out = original.advance(u, p, log_selected_events=True)
        altered_out = altered.advance(u, p, log_selected_events=True)
        telemetry = altered.last_edge_intervention
        events = telemetry["events"]
        observations["boundary_suppression_events"] = events.tolist()
        same("exact_inclusive_start_exclusive_end_arrivals", events,
            np.array([[21, 0, 0, 2, 3], [21, 0, 2, 4, 3]], np.int64))
        same("external_candidates_unchanged", original_out["candidate"], altered_out["candidate"])
        same("external_application_unchanged_in_fixture", original_out["applied"], altered_out["applied"])
        same("source_spikes_not_removed", original_out["spike_ticks"][original_out["spike_indices"] == 0], altered_out["spike_ticks"][altered_out["spike_indices"] == 0])
        same("state_exact_before_first_eligible_arrival", original_out["selected_h"][:22], altered_out["selected_h"][:22])
        same("unselected_outgoing_projection_same_s", original_out["selected_s"][:, 3], altered_out["selected_s"][:, 3])
        same("unselected_outgoing_projection_same_v", original_out["selected_v"][:, 3], altered_out["selected_v"][:, 3])
        same("zero_weight_suppression_no_state_change", original_out["selected_h"][:, 4], altered_out["selected_h"][:, 4])
        ck("negative_delivery_removed_exactly", original_out["selected_h"][22, 2] - altered_out["selected_h"][22, 2] == 2.)
        selected_suppressed = altered_out["selected_events"][altered_out["selected_events"][:, 4] == 3]
        same("new_disposition_only_suppressed_events", selected_suppressed, events)
        ck("source_mask_disposition_unchanged", altered_out["schema"]["dispositions"]["source_blocked"] == 2)
        edge_balance("boundary", altered_out, telemetry)

        # Logging choices cannot gate the actual intervention or its sidecar.
        quiet = create(intervention, edges=[0, 2], window=(21, 23))
        quiet_out = quiet.advance(u, p, log_selected_events=False, event_indices=[])
        same("event_logging_does_not_change_checkpoint", altered.checkpoint(), quiet.checkpoint())
        same("suppression_sidecar_independent_of_event_selection", telemetry, quiet.last_edge_intervention)
        ck("ordinary_events_remain_disabled", len(quiet_out["selected_events"]) == 0)

        positive = create(intervention, edges=[1], window=(21, 22))
        positive_out = positive.advance(u, p)
        ck("positive_delivery_removed_exactly", original_out["selected_s"][22, 3] - positive_out["selected_s"][22, 3] == 9.)
        same("positive_suppression_sign", positive.last_edge_intervention["counts"][21], np.array([0, 0, 1], np.int64))

        # An already-blocked source still has its spikes enqueued. It wins the
        # disposition decision and cannot be counted again as edge suppression.
        for module in (base, intervention):
            net = create(module, edges=[0, 2], window=(0, 40))
            net.blocked[0] = True
            out = net.advance(u, p, log_selected_events=True)
            if module is base:
                blocked_out, blocked_cp = out, net.checkpoint()
            else:
                same("source_block_precedence_complete_output", blocked_out, out)
                same("source_block_precedence_checkpoint", blocked_cp, net.checkpoint())
                ck("source_block_not_reclassified_or_double_counted", not net.last_edge_intervention["counts"].any())
                ck("blocked_source_spikes_still_pending", 0 in net.checkpoint()["pending"])

        prefix = create()
        prefix.advance(u[:20], p, log_selected_events=True)
        cp = prefix.checkpoint()
        branch = restore(cp)
        switched = restore(cp, edges=[0, 2], window=(21, 23))
        same("restored_checkpoint_exact", cp, branch.checkpoint())
        same("intervention_restore_keeps_original_full_state", cp, switched.checkpoint())
        ck("restored_arrays_are_not_checkpoint_aliases", not np.shares_memory(cp["v"], branch.v) and not np.shares_memory(cp["pending_count"], branch.pending_count))
        expected_suffix = prefix.advance(u[20:], p, log_selected_events=True)
        same("restored_no_intervention_suffix", expected_suffix, branch.advance(u[20:], p, log_selected_events=True))
        switched.advance(u[20:], p, log_selected_events=True)
        same("restored_pending_preserves_suppressed_arrival_identity", telemetry["events"], switched.last_edge_intervention["events"])
        same("restored_intervention_endpoint", altered.checkpoint(), switched.checkpoint())

        # Package H1 receives synaptic inputs even while the postsynaptic neuron
        # is refractory. Only direct external events use the active mask.
        refractory_cp = copy.deepcopy(cp)
        refractory_cp["last"][2] = 19
        refractory_cp["v"][2] = -52.
        target = restore(refractory_cp, edges=[0], window=(21, 22))
        target_out = target.advance(u[20:24], p, log_selected_events=True)
        ck("H1_refractory_target_not_directly_available", not target_out["selected_direct_available"][:, 2].any())
        ck("H1_refractory_target_synaptically_available", target_out["selected_synaptic_available"][:, 2].all())
        same("H1_refractory_target_suppression", target.last_edge_intervention["events"], np.array([[21, 0, 0, 2, 3]], np.int64))
        ck("H1_other_source_delivery_accepted_during_refractory", ((target_out["selected_events"] == np.array([21, 1, 3, 2, 0])).all(axis=1)).any())

        # Restore at several chunk boundaries, including the suppression window.
        whole = create(intervention, recurrent=True, edges=[0, 1, 7], window=(21, 73))
        chunked = create(intervention, recurrent=True, edges=[0, 1, 7], window=(21, 73))
        ur = np.random.default_rng(11).random((120, 3)); pr = np.array([.35, .2, .4])
        whole_out = whole.advance(ur, pr, log_selected_events=True)
        pieces, sidecars, start = [], [], 0
        for end in (20, 21, 22, 40, 73, 74, 120):
            pieces.append(chunked.advance(ur[start:end], pr, log_selected_events=True))
            sidecars.append(chunked.last_edge_intervention)
            cp_piece = chunked.checkpoint()
            chunked = restore(cp_piece, recurrent=True, edges=[0, 1, 7], window=(21, 73))
            same(f"chunk_restore_{end}_checkpoint", cp_piece, chunked.checkpoint())
            start = end
        same("chunk_restore_final_checkpoint", whole.checkpoint(), chunked.checkpoint())
        for key in ("spike_indices", "spike_ticks", "candidate", "applied", "selected_prethreshold_v", "selected_available",
                    "selected_fired", "selected_delivery_available", "selected_direct_available", "selected_synaptic_available", "selected_events"):
            same("chunk_join_" + key, whole_out[key], np.concatenate([x[key] for x in pieces]))
        for key in ("selected_v", "selected_s", "selected_h"):
            same("chunk_join_" + key, whole_out[key], np.concatenate([pieces[0][key]] + [x[key][1:] for x in pieces[1:]]))
        for key in whole_out["per_tick"]:
            same("chunk_join_per_tick_" + key, whole_out["per_tick"][key], np.concatenate([x["per_tick"][key] for x in pieces]))
        for key in ("counts", "events"):
            same("chunk_join_suppression_" + key, whole.last_edge_intervention[key], np.concatenate([x[key] for x in sidecars]))

        # Invalid restoration is rejected before mutation; failed state cannot
        # be resumed or silently reset. Every case starts from the same object.
        victim = restore(cp)
        before = victim.checkpoint()
        corruptions = {
            "failed": lambda c: c.update(coherent_state=False),
            "failure_record": lambda c: c.update(failure={"code": 1}),
            "graph": lambda c: c.update(graph_sha256="wrong"),
            "clock": lambda c: c.update(time_ms=123.),
            "nonfinite": lambda c: c["v"].__setitem__(0, np.nan),
            "negative_h": lambda c: c["h"].__setitem__(0, -1.),
            "dtype": lambda c: c.update(s=c["s"].astype(np.float32)),
            "future_last": lambda c: c["last"].__setitem__(0, c["tick"]),
            "refractory": lambda c: c["refractory"].__setitem__(0, 22),
            "queue_count": lambda c: c["pending_count"].__setitem__(0, 100),
            "queue_index": lambda c: c["pending"].__setitem__(0, 99),
            "queue_order": lambda c: c["pending"].__setitem__(slice(0, 2), c["pending"][:2][::-1]),
        }
        for name, corrupt in corruptions.items():
            bad = copy.deepcopy(cp); corrupt(bad)
            rejects("reject_restore_" + name, lambda: victim.restore_checkpoint(bad))
            same("reject_restore_" + name + "_nonmutation", before, victim.checkpoint())
        for label, kwargs in (("duplicate_edge", dict(edges=[0, 0], window=(0, 1))),
                              ("out_of_range_edge", dict(edges=[999], window=(0, 1))),
                              ("empty_duration", dict(edges=[0], window=(1, 1))),
                              ("fractional_tick", dict(edges=[0], window=(1.1, 2))),
                              ("missing_window", dict(edges=[0], window=None))):
            rejects("reject_spec_" + label, lambda: create(intervention, **kwargs))

        for label, edges, window in (("inert", (), None), ("derived", (0,), (0, 100))):
            a, b = create(), create(intervention, edges=edges, window=window)
            # This is an explicitly invalid synthetic state, never a real input.
            a.s[3] = np.inf; b.s[3] = np.inf
            expected = a.advance(np.zeros((2, 2)), p, log_selected_events=True)
            failed = b.advance(np.zeros((2, 2)), p, log_selected_events=True)
            same(label + "_failure_output_exact", expected, failed)
            same(label + "_failure_checkpoint_exact", a.checkpoint(), b.checkpoint())
            ck(label + "_failure_is_incoherent", failed["status"] == "failed" and not failed["coherent_state"])
            rejects(label + "_failed_continuation_denied", lambda: b.advance(np.zeros((1, 2)), p), RuntimeError)
            rejects(label + "_failed_restore_denied", lambda: restore(b.checkpoint()))
            ck(label + "_failure_sidecar_partial_retained", b.last_edge_intervention["partial"] is not None)
        ck("frozen_base_hash_still_matches", hashlib.sha256(intervention.BASE_PATH.read_bytes()).hexdigest() == intervention.BASE_SHA256)
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    result = {"passed": failure is None and all(checks.values()), "checks_passed": sum(checks.values()),
        "checks_total": len(checks), "checks": checks, "first_failure": failure,
        "scope": "Six/twelve synthetic cells only; no real graph/checkpoint, no experiment plan/results written",
        "seconds": time.perf_counter() - started, "observations": observations,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), Path(intervention.__file__))},
        "derivation": intervention.source_derivation(),
        "limits": ["Live saved-checkpoint prefix parity and independent MBON audit gate remain required",
            "Synthetic recurrence equality is not a biological efficacy or specificity claim",
            "Caller owns source RNG arrays, intervention specification and durable archival"]}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
