# Panel input, C0 mapping and metric integration review

This review covers the incoming [panel runner](../scripts/experiment_inhibitory_recurrent_panel.py)'s input schedules, source/cohort identity, C0 original-trial mapping and streaming analysis. Resource/archive/dispatch/failure behavior and numerical reference handling have separate reviewers. The earlier [prospective preflight note](inhibitory-recurrent-panel-preflight-review.md) remains unchanged.

The [pure audit](../scripts/review_inhibitory_recurrent_panel_inputs.py) extracts only the runner's random-stream function, job-order and schedule statements, C0 comparison statements and final analysis block. It never imports the runner or calls `prepare`, `trial`, `run_panel` or a neural constructor. It compares all seeded draws/source mappings to retained inputs and uses manufactured arrays for C0 cursor/window arithmetic and missing-window analysis. No graph simulation occurs.

Source inspection confirms that all rate transitions coincide with 50-tick chunk boundaries, all 36 columns remain present through off periods, and C0 merges the new startup/baseline counts correctly: `(counts[0]+counts[1], counts[2], counts[3])` reproduces the original three windows. Cohort indices are joined from the pinned original IDs, and the streaming helper's explicit chunk bounds and summary APIs match the runner's call sites.

Two analysis integration points were flagged before any panel freeze: completed-count coverage must follow a successfully retained prefix, and clock-complete summaries from correctness/retention/interruption failures must not silently become valid paired outcomes. The runner must retain such raw summaries while excluding them from comparative inputs with explicit reasons. An empty eligible map must report unavailable comparisons rather than call the helper without cohort identity. The source audit includes manufactured checks for these cases.

Status: waiting for the final runner source revision before executing the independent input audit and assembling the aggregate preflight receipt. This note is not source approval, a model run or a physiology/promotion result.
