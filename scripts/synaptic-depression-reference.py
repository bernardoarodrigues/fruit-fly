#!/usr/bin/env python3
"""Abbott 1997 scalar efficacy reference; fixed-source fly-protocol predictions.

Standalone research only: no fruitfly imports, graph, fitting, or integration.
Run --prepare before --run. Existing plan/results are never overwritten.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "validation/synaptic-depression-reference"
FACTOR = .75
RECOVERY_S = .3
KERNEL_S = .002
TOLERANCE = 1e-12
RATES = (7, 15, 20, 50, 100, 200)


def output(suffix):
    return Path(str(PREFIX) + suffix)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(8*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def write_json(p, obj):
    p.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def inputs():
    return [Path(__file__).resolve(), ROOT / "fruitfly/neural.py", ROOT / "fruitfly/data.py",
            ROOT / "validation/orn-pn-transfer-depression-proposal.json",
            ROOT / "validation/orn-pn-transfer-plan.json",
            ROOT / "validation/orn-pn-transfer-results.json",
            ROOT / "data/raw/orn-pn-physiology/kazama-wilson-2008.pdf",
            ROOT / "data/raw/orn-pn-physiology/kazama-wilson-2008-supplement.pdf",
            ROOT / "tmp/pdfs/orn-pn-transfer/abbott-1997.pdf"]


def prepare():
    if output("-plan.json").exists():
        raise FileExistsError("Preserve the frozen plan")
    plan = {
        "schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_paths": {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in inputs()},
        "primary_reference": {"doi": "10.1126/science.275.5297.221", "url": "https://huguenardlab.stanford.edu/220/varela1997a.pdf", "location": "Printed p223 notes6,7,10; PDF page5 visually checked", "organism": "rat cortex"},
        "fixed_parameters": {"per_event_retention_factor": FACTOR, "recovery_tau_seconds": RECOVERY_S, "normalized_response_kernel_tau_seconds": KERNEL_S},
        "equations": {"between_events": "tau*da/dt=1-a", "event": "amplitude=a_before; then a_after=f*a_before", "periodic_steady_state": "A=(1-exp(-1/(r*tau)))/(1-f*exp(-1/(r*tau)))", "finite_train": "a_n=A+(a_0-A)*(f*exp(-1/(r*tau)))**n, with first event index n=0", "normalized_observation": "h(t)=sum_k a_k*exp(-(t-t_k)/kernel_tau) for t>=t_k; scale arbitrary, no pA or male voltage mapping"},
        "numeric_checks": {"absolute_tolerance": TOLERANCE, "periodic_rates_hz": RATES, "pulses_each": 256, "checks": ["Exact finite and asymptotic regular-train amplitudes", "Read-before-decrement event order", "Continuous exponential recovery", "State bounds, finite values, monotonic train depression", "Same-time events and rejected backward event cause expected state behavior", "Read-only recovery queries do not create depression", "Declared f=1 null control only, not a prediction parameter", "Independent direct-sum response versus event-driven response", "Independent integrated convolution versus interval-by-interval integration"]},
        "fly_scope": "Female VM2 published stimulation protocols, evaluated with unchanged rat-source reference parameters as predictions only; no data digitization, measurement fitting or match assertion",
        "train_protocol": {"baseline": "28 spikes at -4+j/7 seconds, j=0..27; recovered before first spike", "test": "j/r seconds for j>=0 and j/r<.5", "test_rates_hz": [15, 20, 50, 100, 200], "phase": "Test first event at0; no event at.5; explicit simulation convention, not documented exact experimental pulse phase", "time_representation": "Retain Fraction numerator/denominator in event CSV; evaluate float64 seconds without timestep quantization", "amplitude_normalization": "Divide by first test-train event amplitude", "waveform_sample_grid": "-.2 to.7s inclusive,0.0001s grid, right-continuous after coincident events; grid does not drive scalar dynamics"},
        "charge_prediction": {"rates_hz": [20, 50, 100, 200], "window_seconds": [.1, .5], "normalization": "Same-window100Hz integral", "primary": "Analytic integral of test-event responses only, unit peak per fully recovered event; no empirical baseline subtraction inferred", "sensitivity": "Also include exact residual baseline response from all preceding events", "scope": "These four displayed Fig9B frequencies only; no unextracted Fig9C/D point locations claimed"},
        "recovery_prediction": {"high_frequency": "50Hz range endpoint and displayed200Hz, .5s train. Each under fully recovered initial condition and under7Hz/4s baseline, both explicit scenarios. Read-only isolated test-probe amplitudes at0..2s after nominal train end,1ms grid; not sequential probing and not measured probe times.", "pause": "After28 regular7Hz events, report isolated probe efficacy0..30s after last event,10ms grid. Time origin is after last event, not an inferred author pause convention; normalize to fully recovered amplitude1. Baseline duration/history and normalization are scenario choices.", "claim_limit": "Missing experimental history/probe times are not resolved by these conventions; no reproduction of measured S8B/D curves claimed and no use of measured7.5s as model parameter"},
        "not_in_scope": ["Any fitted value", "Absolute physiological current/voltage/charge prediction", "Full brain or body", "Runtime integration", "Male or female biological validation", "Stochastic quantal variance", "Any reproduction of Abbott full spiking network"],
        "provenance_limit": "Same author as earlier isolated ORN-PN audit; internal independent formulas are not a separate external replication"
    }
    write_json(output("-plan.json"), plan)
    print("Frozen plan sha256=" + sha(output("-plan.json")))


@dataclass
class Efficacy:
    """Exact event-based recurrence. Time is seconds, a and f dimensionless."""
    time_s: float
    a: float = 1.
    factor: float = FACTOR
    recovery_s: float = RECOVERY_S

    def __post_init__(self):
        if not (math.isfinite(self.time_s) and 0 <= self.a <= 1 and
                0 <= self.factor <= 1 and math.isfinite(self.recovery_s) and self.recovery_s > 0):
            raise ValueError("Invalid scalar reference state/parameters")

    def peek(self, time_s):
        delta = float(time_s)-self.time_s
        if not math.isfinite(delta) or delta < 0:
            raise ValueError("Time must be finite and nondecreasing")
        return self.a + (1-self.a) * (-math.expm1(-delta/self.recovery_s))

    def event(self, time_s):
        before = self.peek(time_s)
        self.time_s = float(time_s)
        self.a = self.factor*before
        return before, self.a


def periodic_formula(rate, n, initial=1.):
    decay = np.exp(-1/(rate*RECOVERY_S))
    steady = (1-decay)/(1-FACTOR*decay)
    return steady+(initial-steady)*(FACTOR*decay)**np.asarray(n), float(steady)


def baseline_times():
    return [Fraction(-4)+Fraction(j, 7) for j in range(28)]


def test_times(rate):
    return [Fraction(j, rate) for j in range(math.ceil(rate/2)) if Fraction(j, rate) < Fraction(1, 2)]


def train(times):
    state = Efficacy(float(times[0]))
    values = []
    for t in times:
        pre, post = state.event(float(t))
        values.append((pre, post))
    return np.asarray(values), state


def sampled_event_response(times, amps, samples):
    """Independent streaming construction of the linear observation proxy."""
    cursor, g, last = 0, 0., min(float(times[0]), float(samples[0]))
    values = []
    for sample in samples:
        while cursor < len(times) and times[cursor] <= sample:
            g *= math.exp(-(times[cursor]-last)/KERNEL_S)
            last = times[cursor]
            g += amps[cursor]
            cursor += 1
        values.append(g*math.exp(-(sample-last)/KERNEL_S))
    return np.asarray(values)


def direct_response(times, amps, samples):
    result = np.zeros(len(samples))
    for t, a in zip(times, amps):
        mask = samples >= t
        result[mask] += a*np.exp(-(samples[mask]-t)/KERNEL_S)
    return result


def integrated_events(times, amps, lo, hi):
    """Streaming interval integral; includes any prior response tail."""
    g, last, total = 0., min(float(times[0]), lo), 0.
    for time, amplitude in zip(times, amps):
        if time >= hi:
            break
        if time > lo:
            start = max(last, lo)
            g_start = g*math.exp(-(start-last)/KERNEL_S)
            total += g_start*KERNEL_S*(-math.expm1(-(time-start)/KERNEL_S))
        g *= math.exp(-(time-last)/KERNEL_S)
        g += amplitude
        last = time
    start = max(last, lo)
    total += g*math.exp(-(start-last)/KERNEL_S)*KERNEL_S*(-math.expm1(-(hi-start)/KERNEL_S))
    return total


def direct_integral(times, amps, lo, hi):
    return sum(a*KERNEL_S*(math.exp(-(max(t, lo)-t)/KERNEL_S)-math.exp(-(hi-t)/KERNEL_S))
               for t, a in zip(times, amps) if t < hi)


def run():
    if output("-results.json").exists():
        raise FileExistsError("Preserve executed results")
    plan = json.loads(output("-plan.json").read_text())
    for name, record in plan["source_paths"].items():
        assert sha(ROOT / name) == record["sha256"], name
    assert plan["fixed_parameters"] == {"per_event_retention_factor": FACTOR, "recovery_tau_seconds": RECOVERY_S, "normalized_response_kernel_tau_seconds": KERNEL_S}
    checks, arrays, events = [], {}, []
    def check(name, condition, **details):
        checks.append({"name": name, "pass": bool(condition), **details})
    def close(name, actual, expected):
        error = float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
        check(name, error <= TOLERANCE, max_absolute_error=error)

    periodic = []
    for rate in RATES:
        times = [Fraction(j, rate) for j in range(256)]
        values, state = train(times)
        expected, steady = periodic_formula(rate, np.arange(256))
        close(f"periodic_{rate}:finite_train", values[:, 0], expected)
        close(f"periodic_{rate}:steady_state", values[-1, 0], steady)
        close(f"periodic_{rate}:event_order", values[:, 1], FACTOR*values[:, 0])
        check(f"periodic_{rate}:bounds_finite_monotonic", np.isfinite(values).all() and (values>=0).all() and (values<=1).all() and (np.diff(values[:, 0])<=TOLERANCE).all())
        periodic.append({"rate_hz": rate, "pulses": len(values), "initial_amplitude": float(values[0, 0]), "last_amplitude": float(values[-1, 0]), "analytic_steady_state": steady})
        arrays[f"periodic_{rate}_times_s"] = np.asarray([float(t) for t in times])
        arrays[f"periodic_{rate}_pre_post"] = values
    state = Efficacy(0)
    close("first_event_recovered_amplitude", state.event(0), [1, FACTOR])
    close("same_time_second_event_order", state.event(0), [FACTOR, FACTOR**2])
    before = (state.time_s, state.a)
    try:
        state.event(-.1)
    except ValueError:
        rejected = True
    else:
        rejected = False
    check("backward_event_rejected_without_mutation", rejected and before == (state.time_s, state.a))
    pauses = np.asarray([0., .001, .05, .3, 1., 2., 7.5, 30.])
    close("analytic_pause_recovery", [state.peek(t) for t in pauses], 1-(1-state.a)*np.exp(-pauses/RECOVERY_S))
    check("read_only_queries_do_not_mutate_or_depress", before == (state.time_s, state.a))
    recovered = Efficacy(0)
    close("no_events_preserve_recovered_efficacy", [recovered.peek(t) for t in pauses], np.ones(len(pauses)))
    null = Efficacy(0, factor=1.)
    close("explicit_static_null_control", [null.event(float(t))[0] for t in pauses], np.ones(len(pauses)))

    # Only these declared known train frequencies generate fly-protocol predictions.
    samples = np.asarray([float(Fraction(j, 10000)) for j in range(-2000, 7001)])
    arrays["train_response_sample_times_s"] = samples
    trains, charge_rows = [], []
    for rate in (15, 20, 50, 100, 200):
        fractions = baseline_times()+test_times(rate)
        values, state = train(fractions)
        times = np.asarray([float(t) for t in fractions])
        amplitudes = values[:, 0]
        test_mask = np.arange(len(times)) >= 28
        normalized = amplitudes[test_mask]/amplitudes[test_mask][0]
        # Closed finite test-train solution takes its first efficacy from the
        # baseline's independently derived 29th would-be 7Hz event.
        initial = float(periodic_formula(7, 28)[0])
        expected, _ = periodic_formula(rate, np.arange(test_mask.sum()), initial)
        close(f"fly_train_{rate}:independent_full_train_amplitudes", amplitudes[test_mask], expected)
        response = sampled_event_response(times, amplitudes, samples)
        direct = direct_response(times, amplitudes, samples)
        close(f"fly_train_{rate}:independent_response_convolution", response, direct)
        check(f"fly_train_{rate}:no_event_quantization", np.array_equal(times, np.asarray([float(f) for f in fractions])))
        check(f"fly_train_{rate}:declared_event_counts", int(test_mask.sum()) == math.ceil(rate/2) and len(times)-int(test_mask.sum()) == 28)
        for i, t in enumerate(fractions):
            events.append({"protocol": f"baseline7_then_{rate}", "phase": "test" if i>=28 else "baseline", "event_index": i,
                           "time_seconds": float(t), "time_numerator": t.numerator, "time_denominator": t.denominator,
                           "a_pre": values[i, 0], "a_post": values[i, 1],
                           "relative_to_first_test": values[i, 0]/amplitudes[28] if i>=28 else None})
        arrays[f"train_{rate}_times_s"] = times
        arrays[f"train_{rate}_pre_post"] = values
        arrays[f"train_{rate}_normalized_test_amplitude"] = normalized
        arrays[f"train_{rate}_normalized_response"] = response
        trains.append({"test_rate_hz": rate, "test_events": int(test_mask.sum()), "first_test_amplitude": float(amplitudes[28]),
                       "last_test_time_s": float(times[-1]), "last_test_amplitude": float(amplitudes[-1]),
                       "last_over_first_test_amplitude": float(normalized[-1]),
                       "status": "fixed_rat_source_model_prediction_not_a_fit_or_measured_fly_value"})
        if rate in (20, 50, 100, 200):
            for window in (.1, .5):
                only = direct_integral(times[test_mask], amplitudes[test_mask], 0, window)
                full = direct_integral(times, amplitudes, 0, window)
                close(f"charge_{rate}_{window}:independent_test_only_integral", integrated_events(times[test_mask], amplitudes[test_mask], 0, window), only)
                close(f"charge_{rate}_{window}:independent_full_history_integral", integrated_events(times, amplitudes, 0, window), full)
                charge_rows.append({"rate_hz": rate, "window_s": window, "test_only_unit_amplitude_seconds": only,
                                    "with_baseline_tail_unit_amplitude_seconds": full,
                                    "baseline_tail_difference": full-only})
    for row in charge_rows:
        denominator = next(x["test_only_unit_amplitude_seconds"] for x in charge_rows if x["rate_hz"]==100 and x["window_s"]==row["window_s"])
        row["normalized_to_same_window_100hz"] = row["test_only_unit_amplitude_seconds"]/denominator

    recoveries = []
    for rate in (50, 200):
        for baseline in (False, True):
            fractions = (baseline_times() if baseline else [])+test_times(rate)
            values, state = train(fractions)
            anchor = .5
            grid = np.asarray([float(Fraction(j, 1000)) for j in range(2001)])
            initial = state.peek(anchor)
            probe = np.asarray([state.peek(anchor+t) for t in grid])
            close(f"post_train_{rate}_baseline{baseline}:recovery", probe, 1-(1-initial)*np.exp(-grid/RECOVERY_S))
            recovered_fraction = (probe-initial)/(1-initial)
            close(f"post_train_{rate}_baseline{baseline}:normalized_deficit_recovery", recovered_fraction, 1-np.exp(-grid/RECOVERY_S))
            key = f"recovery_{rate}_baseline{int(baseline)}"
            arrays[key+"_time_after_nominal_train_end_s"] = grid
            arrays[key+"_probe_amplitude"] = probe
            arrays[key+"_fraction_of_deficit_recovered"] = recovered_fraction
            arrays[key+"_event_times_s"] = np.asarray([float(t) for t in fractions])
            arrays[key+"_event_pre_post"] = values
            recoveries.append({"name": key, "baseline": "7Hz4s" if baseline else "fully_recovered", "test_hz": rate,
                               "last_event_time_s": state.time_s, "anchor_nominal_train_end_s": anchor,
                               "amplitude_at_anchor": initial, "probe_amplitude_after_300ms": float(probe[300]),
                               "probe_amplitude_after_1s": float(probe[1000]), "probe_amplitude_after_2s": float(probe[2000]),
                               "probe_convention": "Independent single probes queried without depressing state; grid is not a measured experimental schedule"})
    fractions = baseline_times()
    values, state = train(fractions)
    anchor = state.time_s
    grid = np.asarray([float(Fraction(j, 100)) for j in range(3001)])
    probe = np.asarray([state.peek(anchor+t) for t in grid])
    initial = state.a
    close("7hz_pause_recovery", probe, 1-(1-initial)*np.exp(-grid/RECOVERY_S))
    close("7hz_pause_fraction_of_deficit_recovered", (probe-initial)/(1-initial), 1-np.exp(-grid/RECOVERY_S))
    arrays["pause7_time_since_last_baseline_event_s"] = grid
    arrays["pause7_probe_amplitude"] = probe
    arrays["pause7_fraction_of_deficit_recovered"] = (probe-initial)/(1-initial)
    recoveries.append({"name": "pause7", "baseline_events": len(fractions), "anchor_last_event_s": anchor,
                       "amplitude_immediately_after_last_event": initial, "probe_amplitude_after_300ms": float(probe[30]),
                       "probe_amplitude_after_1s": float(probe[100]), "probe_amplitude_after_7p5s": float(probe[750]),
                       "scope": "Scenario normalized to fully recovered amplitude1; not the unresolved author recovery-ratio convention"})

    check("all_saved_arrays_finite", all(np.isfinite(a).all() for a in arrays.values()))
    pd.DataFrame(events).to_csv(output("-events.csv"), index=False)
    pd.DataFrame(charge_rows).to_csv(output("-charge-predictions.csv"), index=False)
    np.savez_compressed(output("-arrays.npz"), **arrays)
    check("frozen_input_and_runtime_bytes_unchanged", all(sha(ROOT/name)==record["sha256"] for name, record in plan["source_paths"].items()))
    result = {"schema": 1, "finished_utc": datetime.now(timezone.utc).isoformat(), "plan_sha256": sha(output("-plan.json")),
              "passed": all(c["pass"] for c in checks), "checks": checks,
              "fixed_parameters": plan["fixed_parameters"], "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
              "periodic_reference": periodic, "train_predictions": trains, "charge_predictions": charge_rows, "recovery_predictions": recoveries,
              "prediction_status": "Fixed rat-source scalar model under declared fly-protocol timing scenarios; no comparison with digitized or raw fly data",
              "model_fitted": False, "runtime_integrated": False, "brain_simulated": False,
              "uniform_recovery_property": {"time_to_recover_fraction_1_minus_exp_minus1_s": RECOVERY_S, "time_to_recover_99percent_of_current_deficit_s": -RECOVERY_S*math.log(.01), "scope": "Analytic consequence of a single recovery state, not a fitted fly measurement"},
              "artifacts": {str(output(s).relative_to(ROOT)): {"bytes": output(s).stat().st_size, "sha256": sha(output(s))} for s in ("-events.csv", "-charge-predictions.csv", "-arrays.npz")}}
    write_json(output("-results.json"), result)
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "periodic": periodic, "train_predictions": trains,
                      "charge_predictions": charge_rows, "recovery_predictions": recoveries}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--run", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else run()
