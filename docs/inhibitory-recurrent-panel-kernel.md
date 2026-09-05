# Panel event logging and numerical reference selection

The isolated [panel kernel](../scripts/inhibitory_recurrent_panel_kernel.py) passes **284/284 bounded synthetic checks** against the frozen parallel implementation. Existing spike, trace, clock, diagnostic and checkpoint arrays match byte for byte in the tested fixtures. This stage adds evidence collection; it does not change graph weights, cell dynamics, inputs or production defaults. No anatomical graph or body was executed by its checker.

`FactorialNetwork` has the same constructor and checkpoint format. `advance` and `step` add the keyword `event_indices=None`. With `None`, logging uses the fixed `selected_indices`, as before. An explicit list must be a unique valid subset of those selected cells; an empty list logs no edges. `log_selected_events` still controls whether logging is enabled. The list affects only edge records and may change at chunk boundaries. All selected traces, including the panel's 48-cell population, continue at every tick. The returned schema records `event_graph_indices` for that call.

H arms additionally return `reference_intervals`, describing only available event-free intervals before threshold/reset. Three rankings are retained per `advance`: largest input conductance `h` (also the largest stiffness at fixed timestep/tau), smallest absolute prethreshold distance from −45 mV, and largest `log(p)-log(h)` for `h>0`. For the last ranking, `p=0` remains eligible with score negative infinity; `h=0` is excluded. No `p/h` division is performed. Strict comparisons and the serial tick/cell scan preserve the earliest tick and then the lowest graph index for ties. These rankings cover every cell, including cells outside the selected trace population.

The result contains `found[3]`, `ticks[3]`, `graph_indices[3]` and `values[3,12]`. Missing records have `found=False`, index/tick −1 and NaN values. `schema.reference_names` defines row order; `schema.reference_columns` defines the following columns:

| Column | Meaning |
|---|---|
| `before_v_mv`, `before_p_mv`, `before_h` | Exact interval input state |
| `dt_ms` | Fixed 0.1 ms interval |
| `prethreshold_v_mv` | Solver output before threshold, delivery or reset |
| `threshold_margin_mv` | `abs(prethreshold_v_mv + 45)` |
| `stiffness` | `(1 + h) × 0.1 / 20` |
| `tail_bound_mv`, `inverse_residual`, `inverse_iterations`, `cutoff` | Unchanged scalar helper's diagnostics |
| `log_p_over_h` | Ratio ranking score; NaN for `h=0`, negative infinity for eligible `p=0` |

Candidates are collected when the original serial commit scan accepts an H solver result. A separate merge occurs only after the entire macro tick finishes. Thus completed references never include a failed tick. On failure, `reference_intervals.partial` holds the same four arrays for successfully integrated intervals reached in the attempted tick, with explicit incomplete-state scope. Speculatively computed later-cell intervals are excluded after an earlier cell failure. Existing failure-before-state and partial outputs remain intact. C arms return no found H references. The two named target intervals at the first eligible tick remain reconstructible from their ordinary selected traces and availability masks; they are not duplicated here.

The numerical interval calculation still uses the frozen 32-point helper and the same four-thread `prange` implementation. Callers explicitly set `configure_threads(4)` and record `parallel_runtime_info()`. Additional storage is one boolean event mask per cell and two tiny three-record reference tables with flags/indices, under 1 KiB total for the latter. These tables are reused across ticks. Reference comparisons and logarithms add serial collection work; full-panel execution cost has not been established by this synthetic test.

The [plan](../validation/inhibitory-recurrent-panel-kernel-plan.json) was frozen before evaluation. Its 64-cell graph exercises all four arms with 48 fixed traces, full/two-cell/empty event logging, changing event selection across chunks, and exact old-output/checkpoint comparisons. A separately retained 64-cell trace oracle reconstructs reference winners, including winners outside the usual 48 cells. Domain fixtures cover ties, ineligible cells, `h=0`, `p=0` and ratios larger than float64 can directly represent. Deliberately corrupted synthetic failures check both completed-prefix reference retention and exclusion of later speculative intervals. They are failure tests, not biological conditions.

The [284-check receipt](../validation/inhibitory-recurrent-panel-kernel-checks.json) pins [raw arrays](../validation/inhibitory-recurrent-panel-kernel-arrays.npz) and [their metadata](../validation/inhibitory-recurrent-panel-kernel-arrays.json). State and solver fields compare byte for byte. Independently computed Python log scores are checked separately, allowing less than `1e-12` absolute error where finite; ranking identities must match exactly. The [checker](../scripts/check_inhibitory_recurrent_panel_kernel.py) runs with `.venv/bin/python scripts/check_inhibitory_recurrent_panel_kernel.py` and refuses to overwrite its frozen attempt.

SHA256 pins are `fecae2793af7d5b491a9090d0a8d0b712bba727d918c39be14e0e73048dd4eff` for the kernel, `8f12730a6610252d4398ba6c4fb2aca4ee18e5b01897e721952ed1c5fa9ce813` for the checker, `1fca71b2ccac20568553dcd160bc109b730d6fea1fa6b99a09976c5b683b0aca` for the plan, and `6cd10b15b36fa867a8f5212a760c6e3ad15f488ff5b8572b4d62719e1be659c6` for the receipt. All pinned sources remained unchanged after the checks. These results validate collection behavior on bounded fixtures; the separately frozen recurrent panel and physiological promotion requirements remain outstanding.
