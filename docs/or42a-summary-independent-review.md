# Independent review of Or42a summary excitation

**All 15 saved trials pass the independent event and accounting checks.** The reviewer checked all 4,500 five-millisecond samples and all **9,694,843 recorded network spikes** without rerunning a neural model. The propagation result remains accompanied by a physiological failure: sampled global voltage reaches **−503.0719 mV**, and the configured inputs are excitation events rather than clamped afferent firing.

The [review script](../scripts/review_or42a_summary.py) uses standard-library tools, NumPy and Pandas. It imports neither the experiment nor `fruitfly.neural`, Numba or any simulator. Its [receipt](../validation/or42a-summary-independent-review.json) records source/artifact hashes, every raw file hash, per-trial counts and comparison results. Pure Python integer arithmetic independently reconstructs the RNG stream; this is an audit of saved inputs, not a new neural trial.

## Identity and preserved design

The frozen plan hash is `32a0f8f33d61b532c871a025b975945c7d79530d123b4ee5f7753ea54a0dd41e`; the experiment report hash is `09f8a0135d80b8ecffbc3ffe733fbcb8becba28617d7d2c1b784d073c156dada`. All declared experiment/engine/data/motor/source-result hashes match. The reviewer verified each processed graph-array file and independently recalculated the graph fingerprint, recovering `e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8` for 166,700 neurons and 25,582,938 directed connection entries.

All 36 selected cells are exactly `ORN_VM7d` in the retained MaleCNS table, in ascending numeric body-ID order: 18 left, 18 right, all with `MxLbN` entry nerves. Every trace retains the same ordered IDs and graph indices. The 365 unique directly targeted non-source cells were independently reconstructed from the outgoing CSR rows. Existing motor-group IDs were also checked against the annotated types and side selections. These are anatomical subsets; belonging to the direct-target subset does not demonstrate a functional response or an accepted synaptic update.

The five conditions and their 0–500, 500–1000 and 1000–1500 ms input windows match the plan for seeds 11, 12 and 13. All trials have 300 samples, reach 1500 ms, retain the original Shiu parameters and contain no reported execution exception. Individual trial reports match the combined report. Both raw artifact sizes/hashes and all 45 rows of the compact window CSV agree with the report. The environment receipt's report/table hashes also match; its recorded package versions are historical execution provenance, not a fresh environment benchmark.

## Input events and RNG

The nominal per-source rates are 0 Hz for the listed zero-input control, 11 Hz at baseline, 149 Hz for the ethyl-acetate middle window, and 57.67908699377742 Hz for the isoamyl-acetate middle window. The latter two totals combine the published 11 Hz firing baseline with response increases from different summary cohorts. They are engineering combinations; no matched-cohort total rate, chemical concentration function or held-out prediction is established. The provenance and original firing summaries remain in [the primary assay audit](or42a-primary-assay.md).

Inside this numerical model, each listed source gets a Bernoulli voltage-arrival opportunity per 0.1 ms tick, with probability `configured_rate × 0.0001` and the existing 68.75 mV increment. All 36 sources remain listed even at zero rate, preserving the same draw count and zero-refractory declaration. The review independently implements the xorshift64* recurrence with explicit 64-bit integer wrapping. It verifies the SeedSequence-derived initial state, every 1,800-draw five-millisecond boundary, the final state after 540,000 draws per trial and the **complete ordered requested-event lists**.

Across all trials there are 24,822 requested arrivals. Of these, 266 occur on ticks where that same source has already fired, leaving 24,556 reconstructed applied direct-voltage events. The source neurons generate **24,564 actual spikes**. Those quantities are not interchangeable.

The reviewer reconstructs the applied mask from the complete source-spike tick list and the inspected kernel order: source refractory time is zero, but a neuron that fires is marked inactive for the remainder of that tick, before Poisson input is applied. This supports the saved applied mask exactly. It is a reconstruction from source scheduling and spikes, not a separately instrumented membrane-write counter. Events and spikes can straddle summary boundaries, and incoming recurrent activity remains possible.

For ethyl acetate in the middle window, the independently verified requested/applied/source-spike counts are:

| Seed | Requested events | Applied voltage events | Actual VM7d spikes |
|---|---:|---:|---:|
| 11 | 2,703 | 2,666 | 2,669 |
| 12 | 2,647 | 2,609 | 2,615 |
| 13 | 2,747 | 2,700 | 2,701 |

The blocked condition has the identical requested-event list within each seed, while its middle-window source spike counts are 2,666, 2,608 and 2,699. Actual source spike lists differ between blocked and unblocked conditions in every seed. Equal external input therefore does not imply equal afferent firing once recurrent delivery changes.

## Complete spikes and delayed edge visits

All network events have valid graph indices and integer ticks in `[0, 15000)`. The reviewer checks chronological order and strictly ascending graph indices within a tick, ruling out duplicate same-cell/same-tick records. Extracting source events from those complete lists reproduces the saved source tick/ID lists and both source-event hashes. Full per-neuron window counts, bilateral source counts, first-hop counts, motor-group counts, whole-network totals and every five-millisecond count agree independently.

Each presynaptic spike's potential delivery tick is its recorded tick plus 18, corresponding to the unchanged 1.8 ms delay. The reviewer assigns the source outdegree to that delivery's five-millisecond interval only when delivery occurs before the experiment ends and the source is not blocked. This reconstructs all **3,556,785,698 edge visits** exactly, interval by interval, including cross-window deliveries. There are 14,367 recorded spikes whose delivery time is at or beyond the final boundary; they are excluded from completed edge-visit totals.

An edge visit is an iteration over a directed connection entry, not a unique connection, synaptic contact, transmitted current or accepted postsynaptic update. The kernel counts it even when a target is inactive, and zero-weight entries remain traversable. **Accepted postsynaptic increments are unavailable** and are left null in the results. The reviewer does not infer them from aggregate traversal counts.

The source-output intervention passes only the 36 VM7d indices to the existing ablation API. Source code confirms that the mask acts at synaptic delivery, preserving the source cells, their incoming connections and direct excitation. Every blocked trace contains only source spikes and zero edge visits or downstream spikes. The full boolean mask itself is not saved; exact intervention identity is supported by source inspection and the observed event/visit accounting rather than by an independently retained mask array.

## Paired conditions, motor transients and voltage

Within each seed, the constant-baseline, ethyl-acetate and isoamyl-acetate trials have identical complete network spike lists during their common first 500 ms. The reviewer verifies those entire prefixes, not only matching source totals. All five conditions also have equal RNG draw counts and final states per seed. The three no-input controls contain no requested events or spikes and end with every voltage exactly −52 mV and synaptic state zero.

The motor-rate filters and unrealized commands were independently reconstructed from the complete spike lists. Across 4,500 samples, there are **4,374 rest and 126 walk commands**; all 1,500 middle-window commands are rest. Each of the nine unblocked trials has one initial right-turn-group spike and a 14-sample, 70 ms filtered `walk` transient, with no forward-group spike. The common baseline spike prefix explains its repetition. Taste gates are synthetic false values, and no command reaches a body. This is not observed turning, locomotion, feeding or attraction.

Both full final voltage and synaptic arrays are finite in every trace. Final source/global extrema match the last sample exactly. All intermediate sample flags are true and the source/global extrema are internally ordered and reproduce the window summaries. However, complete intermediate arrays were not retained: finiteness at earlier boundaries remains the producer's observation. The recorded range over five-millisecond boundary samples is **−503.0719218109295 to +19.576391333576808 mV**. It is not a continuous-time range or a biological success criterion. Excitatory voltage writes occur after threshold evaluation, so a positive boundary value does not itself imply an omitted same-tick spike.

## Interpretation and reproduction limits

This evidence establishes execution and propagation for the specified numerical excitation experiment. Baseline input already recruits extensive downstream activity; larger ethyl-acetate excitation does not increase total downstream spikes in every seed. Neither total count nor a transient decoder label identifies a biological odor representation, and the extreme voltage pathology remains unresolved. Three simulation seeds do not provide independent animal cohorts.

The applied-event mask, refractory/current/input-list contract and complete source-output mask depend partly on inspected code and producer assertions. Recorded integer ticks support exact ordering and grid accounting; original floating millisecond batch arrays are not retained separately. Complete raw force/body evidence is irrelevant here because no physical model is instantiated. There is no plume, receptor concentration transfer, adaptation fit, biological recovery model or locomotor assay in this experiment.

The read-only review can be repeated with:

```sh
.venv/bin/python scripts/review_or42a_summary.py
```

It requires the existing processed graph and all raw `trace.npz`/`samples.jsonl` artifacts under `runs/20260905T030251528053Z-or42a-summary`. Those local ignored artifacts are not replaced by the compact repository summaries. No original trial, frozen plan, input rate or neural parameter was changed during this review.
