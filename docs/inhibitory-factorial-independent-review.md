# Independent review of the inhibitory factorial

**Pass within the fixed-source, two-cell numerical scope: 565 checks, all 12 saved traces. No candidate is promoted.** The review independently verifies the event and reset bookkeeping and the reported factorial arithmetic. It does not validate the changed equation against fly physiology or test recurrent consequences.

The review was completed on 2026-09-05 using [this independent checker](../scripts/review_inhibitory_factorial.py) and retained in [the machine-readable receipt](../validation/inhibitory-factorial-independent-review.json). It imports neither the factorial producer nor its interval solver and executes no full network or two-cell replay. Every conditional transition starts from its own saved preceding state; reconstructed states never become subsequent inputs.

The reviewer previously authored the original negative-voltage replay and source-reviewed the factorial driver, but did not author the factorial producer or interval solver. Original-replay parity is consequently a cross-artifact identity check, not an independent biological replication. The new event reconstruction, vectorized local transition checks and direct time-domain reference integration were written independently for this review.

## Frozen evidence and coverage

The [executed plan](../validation/inhibitory-factorial-plan.json) has SHA-256 `add6680e275f4540a3f21ff2d9422313a918fc63ca29bc5dbc59b4501cb1e9fc`. The producer is `05342f151a45a18235824c931633f627a6d9211b07b9fd37ae2bc0c4733ebbcb`; the executed [results](../validation/inhibitory-factorial/results.json) hash is `877190eb44dc35d85ff5a4117988da358078f473ba129c76c2e80c1ed15b1d12`. The independent checker hash is `6728cdf190422221ceedf95413c718c47f857898eb170de9a8231a0c175bca84`. All pinned producer inputs and output artifacts match their retained hashes; all 69 review inputs remain unchanged at review completion.

Coverage includes 2,880,000 target intervals across 12 traces, each with 120,001 saved states for each of the two cells. All 3,671,254 potential edge deliveries across the three source histories were reconstructed in original source-event order, including zero-weight edges and delayed deliveries beyond the horizon. The four arms account for 14,685,016 event dispositions in total. Array names/order, shapes, dtypes, finiteness, completion markers and outer/individual report consistency pass.

The incoming inventory contains exactly 2,695 unique source–target pairs and matches the complete incoming join in the retained graph. The checker verifies CSR source ownership, target indices/IDs, exact float32 weight bytes, contact counts and source model signs. Each expanded event links to the correct original source event and has exactly 18 ticks of delay. Fixed source masks agree with the original condition design and complete final checkpoint. Original target current is zero and refractory duration is 22 ticks; absence from direct input lists also relies on the earlier frozen journal/input audits. The mask's constancy throughout each original run is not newly established from per-interval full masks: those are absent here.

## Local state and event semantics

For every target/tick/arm, the checker reconstructs last-spike timestamps from that arm's own saved spikes, derives availability, checks strict `v_pre > −45 mV`, derives delivery eligibility and verifies the post-threshold reset. Availability is evaluated before thresholding; delayed input arrives after thresholding; reset follows delivery. Package 0 rejects unavailable/firing-tick arrivals and clears synapses at firing. Package 1 accepts every unblocked in-horizon arrival, decays during refractoriness and retains state through firing. It still holds refractory voltage at reset.

All C0 and C1 active voltage transitions agree bit for bit with the analytic current equation using each saved preceding state. All arms' synaptic transitions also agree bit for bit: decay/hold, source-ordered addition, signed jump accounting, and clear/retain behavior. H negative deliveries use the exact recorded weight converted as `−w × (1/23)`; positive input remains current-like. The H zero-inhibition branch matches the C expression bit for bit. All H states retain nonnegative synaptic variables and the chosen lower voltage bound; interval upper-bound arithmetic and inactive diagnostics pass.

Every event classification is independently reconstructed with precedence pending → blocked → unavailable → accepted. Every per-edge count and every positive/negative accepted increment matches exactly. Source histories remain exogenous, including any recorded target self/cross sources; altered target spikes never replace them.

| History | Accepted, package 0 | Accepted, package 1 | Source blocked | Unavailable, package 0/1 | Pending |
|---|---:|---:|---:|---:|---:|
| Locomotor feedback | 1,225,512 | 1,225,520 | 0 | 8 / 0 | 200 |
| Locomotor sensory block | 1,208,502 | 1,208,502 | 4,850 | 0 / 0 | 164 |
| Sensory only | 1,231,820 | 1,231,826 | 0 | 6 / 0 | 192 |

C0 matches every original voltage and signed-state sample, emitted spike, accepted jump and ordered accepted tick/edge pair bit for bit. Its final voltage, synaptic state, last-spike times and all per-edge dispositions match the retained original checkpoint/replay. The producer source places all three C0 gates before altered recorded arms; execution chronology is a source/producer record statement, not inferred from the state arrays alone.

## H numerical evidence and its limits

All 1,488 retained reference selections match the frozen rule exactly, and each recorded reference identifies the actual preceding state and pre-threshold result. The independent checker evaluates those event-free intervals using direct time-domain integrating-factor quadrature. With `y=v+75` and `A(t)=t/20+(h₀/4)(1−exp(−t/5))`, it evaluates

```text
y(Δ) = exp(−A(Δ)) y(0)
       + ∫₀^Δ exp(A(t)−A(Δ)) [23+p₀ exp(−t/5)]/20 dt,
Δ = 0.1 ms.
```

This uses no attenuation inversion or production Gauss–Legendre nodes. Its maximum difference from retained production voltage is **1.4211 × 10⁻¹⁴ mV**, with maximum quadrature error estimate **5.3353 × 10⁻¹⁴ mV**. These checks sample H voltage integration; they do not independently recompute all H voltage intervals.

All stored per-interval 32/64 differences, inversion residuals/iteration counts, cutoff/tail quantities, and selected reference/subdivision comparisons meet the frozen bounds. Maximum retained 32/64 difference in the recorded trials is **1.4211 × 10⁻¹⁴ mV**. Reference input identities and error arithmetic are checked directly; diagnostic summaries match the raw diagnostic arrays. Raw 64-point outputs, inverse iterates and subdivided endpoints are not retained, so the checker cannot independently reconstruct those internal calculations merely from the stored absolute errors. This limitation does not apply to the separately computed time-domain reference above.

## Controls and retained reviewer failure

All four saved 64-tick mixed controls pass independent event/state reconstruction. Their first spike is tick 19, immediately after the tick-18 large excitatory delivery. Availability at ticks 19/20/40/41 is exactly true/false/false/true. Package 0 fires only at tick 19; package 1 fires at 19, 41 and 63. Blocked target 1 remains at rest. The H controls additionally pass independent time-domain integration for all 107 and 86 available target intervals respectively, with maximum discrepancy **1.8759 × 10⁻¹² mV**, below the frozen 10⁻⁸ mV tolerance.

The **expected invalid synthetic control is separate from the finite recorded trials**. An infinite weight delivered at tick 18 leaves the failing input state at tick 19. The archive retains 19 completed macro ticks, 20 state rows, failure marker `[19, 0]`, one accepted event and 24 unprocessed events. It does not call those remaining events pending, and it contains no partial failing step. That nonfinite input is deliberate; no recorded-source trial failed. Process termination/allocation failures are outside the source's prefix-retention guarantee.

The producer reports 40 control checks. Eight checks—four no-input cases, two excitation-only equalities and two moderate single-impulse comparisons—have no separately archived raw trajectories. Their booleans are retained and their implementation was source-reviewed; this review does not claim independently to have reproduced those unarchived runs.

The first independent checker attempt stopped after 73 passing checks because it read the prior input audit's status key as `pass` instead of `passed`. No trial arrays had yet been checked and no producer/data mutation occurred. Its [initial script](../validation/inhibitory-factorial-independent-review-initial.py) and [error receipt](../validation/inhibitory-factorial-independent-review-initial.json) are retained. Correcting that reviewer schema lookup allowed the complete 565-check review to pass; this was a reviewer operational error, not a failed model gate.

## Interpretation

Every cell/window summary and all 24 factorial contrast records are independently reconstructed from the raw traces. Across all four arms, cell 67052 has no spikes; cell 13314 has one spike at 14.0 ms in feedback, none in the sensory-blocked history, and one at 11.7 ms in sensory-only. Thus all spike-count contrasts are zero and no arm restores sustained activity.

C0/C1 retain extreme negative minima, reaching −536.739 mV. The H equations keep both cells above their predeclared −75 mV bound. For feedback cell 13314, H0/H1 minima are −62.708/−65.960 mV, an H1−H0 difference of −3.251 mV; sensory-only gives −63.078/−66.325 mV. The second factor combines decay, acceptance and reset retention, so these traces cannot isolate their separate contributions or establish H1 as preferable.

These are three conditional histories from **one original seed**, selected for two severe endpoint cells. They are not three independent replicates, an unbiased population sample, a new recurrent-network result or a physiological fit. The engineering lower-bound correction passes; physiological amplitude/timing and generalization remain unresolved. There is no basis here to promote H1, alter production defaults or claim behavioral recovery.
