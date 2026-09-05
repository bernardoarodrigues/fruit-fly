# Prospective execution contract for the 60-trial recurrent panel

**Proposal only: no panel plan is frozen and no simulation was run for this review.** The [scientific design](inhibitory-recurrent-design.md) can be made executable with the ordering, budgets and archive contract below. Its opening “no recurrent kernel” statement is now historical: the [serial performance review](inhibitory-recurrent-performance-independent-review.md) passes 499 checks. That evidence supports implementation checks, not model promotion. Keep every existing arm, condition, seed, stimulus value, gain and timing unchanged.

## Fixed panel and ordering

Run 60 fresh states: C0/C1/H0/H1 × the five conditions × seeds 11/12/13, each for 3 s at 0.1 ms. Use the exact ordered 36 VM7d sources, 18 per side, and the original full graph/weights. Preserve C/H equations, −75 mV engineering reversal, negative increment `−w/23`, positive weights, 20/5 ms time constants, threshold/reset, delay, refractory packages and direct 68.75 mV event rule. No input source is removed during zero-rate periods.

| Condition | 0–0.5 s | 0.5–1 s | 1–1.5 s | 1.5–3 s |
|---|---:|---:|---:|---:|
| No events | 0 | 0 | 0 | 0 |
| Constant baseline | 11 | 11 | 11 | 0 |
| Ethyl-acetate profile | 11 | 149 | 11 | 0 |
| Isoamyl-acetate profile | 11 | 57.67908699377742 | 11 | 0 |
| Ethyl-acetate profile, source outputs blocked | 11 | 149 | 11 | 0 |

Rates are excitation events/s/source, not afferent spike clamps or calibrated concentrations. Preserve all 30,000 × 36 draws per seed, including off periods; share uniforms across conditions/arms, never actual spikes or applied-event masks.

1. Run all **15 C0 trials first**, seed-major 11/12/13 and condition order as in the table. At exactly 1.5 s, compare each prefix to its matching original trial before advancing its off period: ordered spikes, candidate/applied events, RNG, per-cell window counts and available final voltage/signed-synaptic arrays. Combine startup/baseline counts to reconstruct the original first 0.5 s window. Reconstruct last/pending values from spikes separately; the old trial does not contain a complete original checkpoint. Retain all comparison outcomes, including failures.
2. A durable gate receipt must contain **15 passing C0 prefixes** before any altered arm starts. Any C0 parity failure or resource stop before 1.5 s prevents unlocking altered arms. A C0 resource stop after a passing prefix leaves that trial's off period incomplete but does not invalidate the other prefix gates.
3. After that gate, run condition-major, then seed 11/12/13, then C1/H0/H1 for each pair. This fixed interleaving avoids spending the entire altered-arm budget on one arm first. Use one fresh worker/state at a time. Never reorder according to firing, runtime or an attractive outcome.

Pin the executable implementation and thread count before the panel. Serial timings below are the measured basis; the four-thread implementation has only separate synthetic evidence at this review's cutoff. A different selected implementation needs its already planned matched full-graph parity/performance result before it enters the frozen panel, without changing panel conditions.

## Engineering budgets and partial completion

Propose **3,600 s wall time, 4 GiB ordinary output and 8 GiB peak worker RSS per trial**; **86,400 s wall time and 64 GiB ordinary output globally**. These are host resource limits, not physiological thresholds. Global time includes preflight, compilation, trial construction, archives and summaries; trial time includes construction through its terminal archive. Record components separately.

Reserve a further **512 MiB**, excluded from ordinary-output limits, for the one active trial's failure checkpoint/receipt; require at least **10 GiB filesystem free space** at startup and every durable chunk boundary. Current read-only filesystem evidence showed about 256 GiB available; this is not reserved space and must be checked again at execution. An output-size check is on actual bytes, including temporary files. Sample wall/RSS/storage checks before and after each 5 ms chunk and checkpoint; one operation can overshoot. Do not call these hard real-time caps.

A resource-only stop may continue to the next predeclared fresh trial if global limits/free-space checks pass, the worker has exited and released memory, all inputs still match and, when dispatching an altered arm, the 15-prefix gate is satisfied. Mark the stopped trial **resource-limited/incomplete**, retain its last valid prefix and never resume or replace it. A global cap stops dispatch. A parity, numerical, source-hash, archive-schema or failed-retention check stops the panel for review; do not silently continue past a correctness failure. Interrupted or missing windows are unavailable data, not zero responses. Paired contrasts require both complete windows; incomplete factorial contrasts remain unavailable even if other arms finish.

No biological spike ceiling or activity-triggered early stop is introduced. Exact refractory violations, nonfinite/invalid state and the declared hybrid lower-bound violation are numerical failures. High activity or growth without such a failure is retained descriptively until the ordinary engineering budget or 3 s endpoint.

Preserve the deterministic controls: all no-events arms remain at rest with zero synaptic states/spikes; source-output-block arms have no nonsource spikes or accepted source-output writes, while source stimulation/firing and blocked edge visits remain possible. These are consistency checks for this declared initial state and input scheme, not claims about biological spontaneous activity.

## Durable evidence contract

Create an exclusive run directory and immutable manifest before execution. Pin source/environment/graph/plan hashes, complete input IDs, cohort IDs and overlaps, the fixed source block masks, RNG streams, schedules, windows, ordering, budgets and tolerances. Include the 365 structurally selected first-hop nonsource cells and existing motor groups without response-based selection.

Publish one archive per completed **5 ms/50-tick** chunk. Write to a temporary path, close/flush and fsync, compute hashes, rename atomically, then publish its completion record; retain temporary/incomplete artifacts after failure. Store ordered spikes losslessly as explicit little-endian `(int64 tick, int32 graph_index)` records, 12 bytes/event without padding, with version/count/checksum headers. Keep indices and ticks exact when compressed. Save candidate/applied masks, logical RNG boundaries and counts, every-tick three-phase extrema/IDs/finite/bound diagnostics, sign-resolved edge dispositions and work/solver summaries. Retain the existing 48 selected cells' boundary `v/s/h` and prethreshold/availability/firing traces at every tick; their first and last rows must match adjacent chunks/checkpoints.

Keep all ordered events into the two target cells. For the remaining selected cells, keep events in fixed audit ranges `[0,.05)`, `[.5,.55)`, `[1.5,1.55)` and `[2.95,3)` s. Store original edge indices/dispositions; source order, CSR order and float32 weight provenance must be recoverable. All spikes, graph, masks and refractory packages permit independent global delivery reconstruction; an edge visit is not an accepted write.

Save complete initial and boundary checkpoints at **0, .05, .5, 1, 1.5, 2, 2.5 and 3 s**, with full voltage/synaptic states, last spikes, refractory/mask arrays, valid pending counts/order, completed tick and RNG position. Save per-neuron counts for all seven analysis windows and sampled 5 ms distributions/recruitment summaries. Do not imply an all-cell intermediate state cube exists.

On a caught failure, save actual mutable state and any returned partial spike/event/phase arrays before cleanup. Distinguish `last_durable_chunk_end_tick`, `last_complete_checkpoint_tick`, `completed_prefix_tick` and `attempted_tick/phase`. An in-progress exception can leave arrays incoherent even when a completed-prefix clock exists; do not label those arrays as a completed checkpoint or render/advance them. A hard kill may leave only the previously durable evidence; report that limitation rather than inventing a failure checkpoint.

For H interval references, predeclare both targets at each 5 ms start plus, within each chunk, available intervals with largest `h`, largest stiffness, smallest absolute prethreshold threshold margin, and largest `p/h` for `h>0`; ties use earliest tick then smallest graph index. Retain exact preceding state and phase, deduplicate identical selections, and include every numerical failure. Undefined `p/h` at zero `h` is not given an artificial denominator. Preserve existing 1e−8 mV production/adaptive-quad, 2e−8 mV independent ODE comparison and 1e−10 mV bound tolerances. Report threshold margins comparable to numerical error as unresolved timing robustness. These required preceding-state records must exist in the panel runner's archive schema before freeze; current global extrema alone cannot reconstruct them.

## Cost evidence and its limits

Measured serial kernel times come from seed-11 baseline **50 ms** records; compilation, archiving and startup are separate. Multiplying by 60 is only a constant-workload scale calculation:

| Arm | Measured 50 ms kernel time | ×60 for one 3 s trial |
|---|---:|---:|
| C0 | 0.9723 s | 58.34 s |
| C1 | 0.8472 s | 50.83 s |
| H0 | 3.0122 s | 180.73 s |
| H1 | 3.5074 s | 210.45 s |

Multiplying again by 15 gives **7,505 s (125 min)** for all 60 trials, excluding expanded archives and startup. It is not a completion forecast: H0/H1 used quadrature on only about 3.3%/3.8% of possible cell-ticks, and C1's last two chunks already contain 489 then 2,174 spikes. Each full trial has 5.001 billion potential cell updates. Applying the separate mixed scalar grid's 1.843 million intervals/s to all of them gives about **2,713 s/trial** before graph/event/telemetry cost—another workload scenario, not a guaranteed upper bound.

The measured compressed chunk sizes, 0.465–0.557 MB per 50 ms for the four arms, scale to **1.87 GB across the panel** only if compressibility/workload stay unchanged. Shared float64 uniforms require 25.92 MB total; seven int64 per-cell count windows require 9.34 MB/trial. Eight full checkpoints add roughly 55–60 MB/trial before compression, depending on pending queues. Retained spike volume can dominate: the mathematical refractory schedule permits up to 228,409,696 records in a 3 s trial, or 2.74 GB at 12 bytes/record. This is a storage bound under model timing, not expected biology. Archives must stream rather than accumulate all spikes/events in RAM. The proposed budgets allow useful completion but do not promise every high-activity trial will fit.

## Analysis and interpretation

Keep the original windows `[0,.05)`, `[.05,.5)`, `[.5,1)`, `[1,1.5)`, then all **1.5 s of input off** as `[1.5,2)`, `[2,2.5)`, `[2.5,3)`. Report exact counts, rates with explicit population/time denominators, individual-cell distributions, silent/recruited fractions and the raw 5 ms trajectory. Separate source, first-hop, two targets, nonsource and motor populations; groups may overlap but cannot be silently summed as independent cells.

For each seed/arm, report pulse minus that trial's baseline **and** pulse-window difference against its matched constant-baseline condition; report ethyl minus isoamyl and unblocked minus blocked conditions in the same window. Then report H0−C0, H1−C1 and their interaction within each seed/condition. Retain candidate/applied/source-spike differences so an input rate is not mistaken for a delivered spike dose. A “meaningful contrast” here means an explicit effect size and direction reproducible across the three paired simulation seeds, with sign reversals/near-zero effects shown; it has no invented universal amplitude or significance cutoff.

For off periods, report excess rate/recruitment relative to matched baseline-then-off and no-events controls, consecutive-bin changes, late-minus-early off difference and high-rate tails. Preserve increasing activity, loss of contrast or approach to the model's refractory firing scale as descriptive warnings; neither their presence nor absence supplies physiological acceptance. There is no withdrawal persistence result for a truncated off period and no conclusion beyond 3 s. Numerical/engineering completion, stimulus descriptions and physiology/promotion are separate outputs. **This panel alone cannot promote H1 or establish physiological inhibitory amplitude/timing.**

Measured evidence: [producer result](../validation/inhibitory-recurrent-performance-v2/results.json), SHA-256 `d9a8269b2e24538bb652367c3ac11bcf4c8a5f33b91d4c0f75377fb8b28dac82`; [independent receipt](../validation/inhibitory-recurrent-performance-independent-review.json), SHA-256 `03be066f5559b7cfd769cda92b4ee5a6244b621a5074c5b6714f6620ba66f41a`. This note changes no frozen artifact or runtime.
