# Retained failure state in the viewer

A body failure can occur after the neural interval completes but before the physical interval completes. The viewer now distinguishes its last completed telemetry and last image from the cached failure diagnostics. It does not advance, render, resume or restart a failed simulation to obtain this information.

`SimulationRunner.failure_diagnostics()` returns an independent copy of the existing, JSON-safe failure receipt. The same record is written to the run's `failures.jsonl`. It contains the neural clock, pending action/spike bookkeeping and cached native body state when available. Nonfinite values become `null`; they are not replaced by plausible measurements. A reset clears the cached record but preserves the journal.

On an exception, the viewer publishes this record separately as `failure_diagnostics`. Ordinary telemetry is explicitly marked `last_completed_advance` (or unavailable before initialization). Each actual image publication retains its own simulation time and receipt wall time. Error publication no longer resets the apparent age of the preceding image. The browser labels that image as the last frame and displays completed-telemetry, image, neural-failure and physical-failure times separately when available.

The terminal error remains visible and controls remain disabled. This change does not weaken a physical guard, recover a failed trial, imply synchronized failure clocks, or claim that the last image depicts the failed state. Errors outside the runner's recorded body/final-snapshot paths may have no cached failure record; that absence remains explicit in the API.

Focused validation: **15 tests and 23 subtests pass** across `tests/test_viewer.py` and `tests/test_simulation.py`. A deliberately nonbiological IPC fixture completes through 0.020 s, then fails with a 0.030 s neural clock and a 0.025 s partial physical clock. The receiver retains all three times, the earlier image and its age, JSON-safe nonfinite diagnostics, and a terminal worker. Attempting to render its failed state would fail the test. Separate checks verify failure-receipt copy isolation, cleanup, and clearing on reset; the existing full-graph reset/chunk comparison still passes.

```sh
.venv/bin/python -m pytest tests/test_viewer.py tests/test_simulation.py -q
```

These are viewer/runner correctness checks. The fixture is not physical wall-contact evidence or a biological simulation. Actual habitat trial and UI receipts are recorded separately.

The subsequent [actual habitat viewer check](flybody-habitat-viewer.md) now confirms this behavior during source wall-contact termination: the last image is at 0.750 s, completed telemetry at 0.760 s, and both recorded failure clocks at 0.768 s. The worker exits and the UI retains the earlier frame with disabled controls. This separate controller-only experiment makes no avoidance claim.
