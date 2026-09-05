# Panel metric helper and prospective preflight review

The pure [metric helper](../scripts/inhibitory_recurrent_panel_metrics.py) passes **36 manufactured checks** on its first test execution. The [receipt](../validation/inhibitory-recurrent-panel-metrics-checks.json) pins its source. Tests cover half-open boundaries, streaming accumulation, the unequal baseline/pulse durations, all requested contrast directions, three separate seeds, missing trials and partial off periods. They are arithmetic/record fixtures, not neural simulations or biological tests.

The incoming panel runner was not yet present when this note was written. This is its **preflight/audit design**, not source approval or permission to freeze/run. The [execution contract](inhibitory-recurrent-execution-plan-review.md) remains prospective. No frozen input, runtime or parameter was changed.

## Minimal streaming API

```python
cohorts = build_cohorts(neuron_ids, old_plan)
counts = np.zeros((7, len(neuron_ids)), dtype=np.int64)
# For each complete, contiguous, durably identified chunk:
accumulate_chunk(counts, indices, ticks, start_tick=start, end_tick=end)
summary = summarize_counts(counts, completed_tick, cohorts)
# After available trials close:
contrasts = paired_contrasts({(seed, arm, condition): summary, ...})
```

`accumulate_chunk` modifies counts in place without retaining spikes. It validates within-chunk tick/index order, uniqueness and range; the runner owns cross-chunk contiguity and exactly-once accumulation. Save the array separately as **`observed_window_counts[7,N]`**, in graph order. Do not feed uncommitted partial-tick spikes into completed-prefix counts.

`summarize_counts` returns ordinary JSON with `completed_tick`, seven `window_complete` flags, `complete_window_count`, cohort membership hashes and `cohort_metrics[name][window]`. Each row has explicit `observed_spikes`, nominal/observed durations and complete/partial/unobserved status. `spike_count`, population Hz, mean per-cell Hz, recruited cells and active fraction are **null** for an incomplete window. Complete zero-event windows retain real zero values. A count beyond available ticks is rejected under the exact one-spike/cell/tick record contract, not a biological activity limit.

`build_cohorts` preserves old-plan source/first-hop/motor order, checks 36 source indices, 365 first-hop nonsource IDs and both fixed targets, and returns all/source/nonsource/first-hop/combined-target/individual-target/motor cohorts. A read-only join to the actual neuron-ID file succeeded: 166,700 cells, 36 sources, 166,664 nonsources, 365 first-hop cells, targets 67052 and 13314, and five two-cell motor groups. The parent manifest must pin graph IDs and the original plan bytes. Shared group names/population sizes alone are insufficient: paired analysis also verifies ordered membership hashes.

`paired_contrasts` uses complete mean-cell-rate windows only. It returns within-trial pulse-minus-baseline, pulse-minus-matched-constant, ethyl-minus-isoamyl, unblocked-minus-blocked, H0−C0, H1−C1 and their interaction, plus off-bin changes/control excesses. Every operand and missing reason is retained. It normalizes 0.45 s baseline and 0.5 s pulse separately and never averages simulation seeds into biological replicates. Off-bin strict increase is descriptive direction only, with null when incomplete. The small-stream `summarize_trial` convenience wrapper exists, but is unnecessary for the panel.

## Runner preflight before any panel freeze

Use fake clock/resource providers and manufactured chunk outputs to test orchestration without a graph run:

- Verify the complete 60-job order and exactly 15 passing C0 prefix receipts before altered-arm dispatch. Exercise a C0 mismatch, a C0 resource stop before 1.5 s, and a resource stop after a passing prefix. Only the latter may preserve that prefix gate; none may be silently retried or counted as a complete trial.
- Verify all five rate schedules at boundary ticks 4,999/5,000, 9,999/10,000 and 14,999/15,000; all 36 source columns and RNG draws continue through zero-rate/off periods. The blocked condition changes only its fixed source-output mask. A recurrent synaptic permission must not bypass the direct event firing-tick rejection rule.
- Exercise before/after-chunk wall, RSS, per-trial/global output, free-space and terminal-checkpoint checks. Retain overshoot and the protected failure reserve explicitly. Trial resource exhaustion may continue another fresh trial; a global cap or correctness/retention failure stops dispatch. Fresh worker exit, not garbage-collection hope, must establish resource release.
- Publish a normal chunk, then inject archive failure before completion publication. Metrics and C0 gates must never claim the uncommitted chunk as durable. Preserve actual current state, attempted phase, last completed prefix, last durable chunk and last complete checkpoint independently; no failure path advances or resets the failed network.
- Reconstruct counts from published spike archives and compare the streaming accumulator. A prefix ending at each exact window boundary and halfway through pulse/off must produce the appropriate complete flags and null unavailable contrasts. Include double-consumption and missing-chunk fixtures in the runner's continuity checks.
- Verify complete boundary checkpoints, selected `n+1` traces and per-tick `n` records. Numerical-reference rows must retain exact preceding states and exclude uncommitted failed ticks; `found=False`/undefined log-ratio fields are missing reference data, not model-state nonfiniteness. Test no-events and blocked-source consistency checks separately: source firing is permitted in the latter, nonsource firing/accepted source-output writes are not.

The prior resource proposal remains coherent: 3,600 s/4 GiB/8 GiB RSS per trial, 86,400 s/64 GiB globally, a 512 MiB failure reserve and 10 GiB free-space floor. Root may accept or amend these engineering limits before freezing; no change to scientific conditions follows from the numbers. Serial short-prefix cost cannot guarantee completion, especially with C1 growth. Metric processing does not require concatenating up to hundreds of millions of retained spikes.

After a runner exists, independently inspect its actual dispatch, archive/metric ordering, C0 comparison, budget and failure paths against these cases. Passing helper tests alone is insufficient runner approval. No H1 selection, physiological threshold or recurrent outcome is claimed here.

Pins: helper SHA-256 `d4cec767d98b7996522a288cf5d78f9180a09227e8a46fe2fb55b454186f9b26`; metric-test receipt SHA-256 `bb81bf2cfc9a5bf31696bea76a280362014f7b74f16b87981a713e86e56247dc`.
