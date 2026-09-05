# Independent review: viewer failure-state clocks

Reviewed commit `986790d41272b0850d778dc01513fb95e52b395e`. **No correctness blocker found within this change's scope.** The [review receipt](../validation/viewer-failure-independent-review.json) records source hashes, commands, results and limitations. Runtime files were not edited.

The worker retains the last successfully returned telemetry separately from cached failure diagnostics. Its exception handler calls neither `advance` nor `render`; it publishes no new image or image clock. The receiver therefore preserves the previous image, sequence and simulation timestamp. Image age uses the last image's receiver wall-clock timestamp, so an error-only packet does not make the image appear fresh. This is time since server receipt, not image capture time or an independent physical clock.

The retained runner receipt is JSON-safe and returned by deep copy. It is cached before journal writing, and reset clears the cache. The error packet is normalized before cleanup, so a subsequent cleanup failure cannot overwrite that already published record. Existing cleanup still attempts a final snapshot and closes resources; it does not render or advance physics. Errors outside recorded runner paths may have no diagnostic record. That absence remains explicit.

Validation:

- `tests/test_viewer.py` and `tests/test_simulation.py`: **15 tests and 23 subtests passed** in 5.86 s, including the existing full-graph reset/chunking test. No extra full-graph experiment was run.
- An independent transport fixture separates all four clocks: image **0.010 s**, completed telemetry **0.020 s**, partial physical failure **0.025 s**, neural failure **0.030 s**. Exactly one render occurred, before failure; the final operations were cached-diagnostic retrieval and cleanup. Nonfinite cached position became `null`.
- Runner `advance`, `snapshot`, `render` and coupling-validation methods are AST-identical to the parent commit. Neural and sensor/decoder source bytes are unchanged. `node --check fruitfly/web/app.js` passes.

The focused tests also verify terminal errors, rejected post-error controls, no automatic restart, retained images, copy isolation and reset behavior. Browser source review confirms distinct clock labels and unavailable-number formatting. Actual browser rendering and a physical habitat failure were not exercised here. The independent clock fixture is deliberately nonbiological: it verifies transport and reporting, not dynamics, contact physics or biological validity.
