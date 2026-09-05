# C0 independent audit aggregate

All **15 C0 trials** in the frozen panel passed independent saved-data review: **571,017 component checks** across 9,000 archived chunks and 21,546,618 spikes. The existing quiet ordinal-0 and active ordinal-1 receipts were reused. Ordinals 2–14 were reviewed sequentially, once each, only after their authoritative terminal records reported completion. No failure occurred; no receipt, frozen reader or experiment file was overwritten, and no neural simulation was run by this review.

The [aggregate receipt](../validation/inhibitory-recurrent-panel-c0-audit-summary.json) passed **297 checks on its first execution**. Its [aggregation script](../scripts/summarize_inhibitory_recurrent_c0_audits.py) verifies each review's source, plan, result and terminal hashes before using its certified counts. The independent readers reconstructed the per-neuron window counts and checked the result's cohort metrics; aggregation uses those exact pinned operands without recounting the full spike streams. The original 1.5-second C0 spike, input/RNG, count and endpoint gates are included in the independent trial reviews.

The seven half-open windows are `[0,.05)`, `[.05,.5)`, `[.5,1)`, `[1,1.5)`, `[1.5,2)`, `[2,2.5)` and `[2.5,3)` seconds. Every operand is complete. Missing or unsuccessful evidence would fail aggregation, rather than become zero. Rates divide integer counts by the duration and entire fixed cohort size; paired baseline-to-pulse differences account for the unequal 0.45- and 0.5-second durations.

## Verified withdrawal counts

These are counts for the **166,664 non-source cells**, after imposed input rates become zero at 1.5 seconds:

| Seed | Condition | [1.5,2) | [2,2.5) | [2.5,3) |
|---|---|---:|---:|---:|
| 11 | Constant baseline | 438,307 | 440,585 | 437,192 |
| 11 | Ethyl acetate | 438,959 | 437,914 | 436,267 |
| 11 | Isoamyl acetate | 438,311 | 440,217 | 440,468 |
| 12 | Constant baseline | 437,857 | 437,073 | 438,527 |
| 12 | Ethyl acetate | 443,964 | 441,727 | 446,069 |
| 12 | Isoamyl acetate | 437,929 | 438,090 | 437,397 |
| 13 | Constant baseline | 437,282 | 438,495 | 436,832 |
| 13 | Ethyl acetate | 440,440 | 437,057 | 438,690 |
| 13 | Isoamyl acetate | 438,114 | 437,300 | 440,708 |

All three no-input trials are completely silent. All three ethyl-acetate trials with source outputs blocked have exactly zero non-source spikes in every window. Their source cells still receive the specified excitation events. These complete-zero controls are retained as observations.

The nine unblocked driven trials retain substantial non-source activity throughout the measured 1.5-second withdrawal interval. Off-bin direction varies: these observations do not establish indefinite persistence, a stable attractor, future uncontrolled growth or physiological plausibility. Fixed forward-group counts are zero in every trial/window; nonzero feeding-group counts are neural readouts, not observed feeding or movement.

## Source spikes at the cutoff

Off-period requested/applied input masks are verified against the frozen zero-rate schedule by the independent reader. Actual source spikes need separate wording. Every seed11 and seed13 trial has zero off-source spikes. The four driven seed12 trials each have **one source spike at tick 15,000**, followed by no further source spikes; the no-input trial has none.

For all four events, the retained neighboring chunks identify body ID **167295**, graph index **112198**, source column **24**. At tick 14,999, its input candidate is applied and the source does not fire. Its post-external voltage is exactly the prethreshold voltage plus 68.75 mV. At tick 15,000, the prethreshold voltage is above −45 mV, the source fires, then resets to −52 mV. The first off chunk has zero candidates and zero applied events. The receipt retains the exact voltages and synaptic-state scalars for each condition and verifies that these first-off-chunk spikes account for the entire off-source count. This is evidence for last-pre-off direct input followed by next-tick thresholding; it is not an assumed delayed synaptic arrival.

## Descriptive stimulus differences

For the non-source population, paired pulse-rate differences are:

| Seed | EA minus constant (Hz/cell) | IA minus constant (Hz/cell) | EA minus IA (Hz/cell) |
|---|---:|---:|---:|
| 11 | −0.073801 | +0.072721 | −0.146522 |
| 12 | +0.120638 | +0.078277 | +0.042361 |
| 13 | +0.039517 | +0.031513 | +0.008004 |

EA-minus-constant and EA-minus-IA change sign across the three seeds. The constant-baseline condition itself increases from baseline to pulse by 2.968490, 2.473860 and 1.888758 Hz/cell, so that temporal increase is not uniquely attributable to an odor-rate increase. The receipt preserves each condition's own baseline-to-pulse difference, constant-adjusted differences, EA/IA and unblocked/blocked contrasts, and all three withdrawal bins for all 12 fixed cohorts. These are paired descriptive arithmetic, without significance tests, fitted gain or physiological acceptance thresholds.

The reader checks selected-48 voltage/synaptic algebra at every tick, raw-spike history and checkpoints, ordered selected events and full-graph delivery-visit totals. It does not independently reconstruct every intermediate global voltage or every global accepted/unavailable event disposition. This aggregate covers C0 only and makes no altered-arm or H1-promotion claim.

Aggregate SHA256: `0942b7b1ba57a33391488aa36eb069f514e394a4295cd3b6a99b8e43f9394256`. Aggregation script: `6058bfa8e0e456f73db4fe87c41db6e22c080505ef3ec4fdef2058eb74a88a86`. Frozen active reader: `2329e31a90bfaae48372a36ce3ccd03146bdec785dff9c511737c10bead81226`; shared independent reader: `1e2d91757813372de3fa3d5df100690ab7ac6d3805fe7f7035e3ebc5f6424da8`. Frozen plan: `c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5`. Individual receipt and source hashes are retained inside the aggregate.
