# Contact-aware γ-KC recurrent diagnostic

This fixed six-trial experiment tests whether excessive recruitment and persistent firing depend on the model's fast positive KC contribution at γ-lobe contacts. It is a branch of experimental H1, not a new default or a biological synaptic ablation. The [primary receptor review](../research/24-kc-spatial-mechanism-constraints.md) motivates the location and postsynaptic population, but supplies no calibrated unitary electrical or GPCR kernel.

## Frozen anatomical scope

Select presynaptic exact class `Kenyon_Cell`, postsynaptic exact class `Kenyon_Cell` with exact type `KCg`, `KCg-d`, `KCg-m`, `KCg-s1`, `KCg-s2`, `KCg-s3` or `KCg-s4`, and literal primary postsynaptic ROI `gL(L)` or `gL(R)`. All KC source subtypes are included because the motivating lateral experiment stimulated a mixed αβ/γ subset; this does not establish each source-to-target receptor assignment. No PED, CA, unspecified ROI, or non-γ target is selected.

The [mask](../validation/kc-gamma-contact-mask-results.json) contains 414,095 selected contacts on 270,710 positive neuron pairs, reaching all 1,557 annotated γ KCs. Of these pairs, 242,204 contain only selected contacts and 28,506 are mixed; 46,992 other contacts on those pairs retain their contribution. The broader 451,534 KC→KC gL contacts include 37,439 contacts onto other KC types and are not all selected. Labels remain structural annotations, not measured receptor or electrical compartment identities.

An independent implementation reads raw body IDs and literal ROI strings from the previously audited contact table and counts body pairs with a Python Counter. It matches every selected pair and contact count from the sparse aggregate route. This is an independent calculation by the same agent, not a separate reviewer or an independent animal.

For a pair with original stored float32 weight cast to float64 `W`, selected count `c` and total count `N`, use `removed = W * (c / N)` in float64, then `retained = W - removed`. Fully selected pairs retain exactly zero. Unaffected weights bypass this calculation and retain their original bytes. This allocates the existing rounded pair weight; it neither installs a gain nor rerounds retained contributions to float32. Actual delivery accounting sums `W - retained`, which can differ from the intermediate `removed` by floating-point subtraction rounding.

## Fixed comparison and timing

Reuse original H1 controls from the completed recurrent panel. Branch exactly at tick 5000 (0.5 s) for constant baseline and ethyl acetate, seeds 11, 12 and 13, ordinals 26, 29, 32, 35, 38 and 41. These are previously examined historical conditions, not held-out animals or blind model selection.

Apply retained weights at delayed arrivals in `[5000,15000)` (0.5–1.5 s). The exact pending source queue crosses the branch boundary. Preserve existing p/h, all other outgoing projections, inhibitory delivery, refractory handling, solver, source uniforms and reset rules. At tick 15000 restore original delivery weights and set the prescribed external input to zero; continue through tick 30000 (3 s). Restoration and input withdrawal coincide, so their individual effects cannot be separated by this design.

Rates at the imposed source boundary remain constant 11 Hz through 1.5 s, or 11 Hz baseline / 149 Hz pulse at 0.5–1.0 s / 11 Hz washout at 1.0–1.5 s, then zero. These describe external candidates, not measured source spike rates; actual spikes remain archived.

## Recording and review

Retain full population spikes, seven-window counts, and checkpoints at 5000, 10000, 15000, 20000, 25000 and 30000. Continuous traces contain the original 48 cells, thirteen γ representatives chosen as the first graph/body ID within each available exact-type/soma-side group, both APLs and ten MBON12–14 cells, deduplicated. Representatives are an anatomical sampling rule, not a population-wide continuous recording. All γ and other KC cells remain covered by spikes and checkpoints.

The original edge counters count accepted graph deliveries, including selected deliveries with zero retained contribution. Sidecar counts split zero-retained and partial-retained deliveries; removed p-weight sums use the original source/CSR order. Selected-event disposition 3 denotes a modified delivery. Full affected arrivals are reconstructible from the complete source spike histories plus initial pending queue and mask; no redundant full affected-event stream is required. p increments and h conductance units must not be subtracted as an E/I balance.

Before launch, require manufactured delivery/state/window/chunk/checkpoint/failure checks and six inactive real-graph probes. Each inactive probe reuses the original selection and must match every original returned field in its historical 50-tick chunk exactly. The worker's online accounting independently reconstructs per-tick affected counts from delayed source emissions, checks removal sums with absolute 1e-9 and relative 1e-11 tolerance, tracks refractory intervals, finite/reversal bounds, input candidates, trace continuity and pending queues. Those tolerances concern summation order, not biological acceptance.

Analyze only after the entire six-trial batch completes. Review all hashes, coverage, source spike histories, queues, per-window counts, selected continuous states, contact-delivery identities, window transitions and per-tick accounting. Independently evaluate every saved global reference interval and the first available interval of each declared reference target in each chunk against adaptive quadrature, independent ODE and order-64 quadrature, using the original panel tolerances and explicit threshold-margin ambiguity reporting.

Compare all seeds together for γ/other KC subtype rates, active fractions, 22-tick ISI occupancy, matched EA-minus-constant contrasts, APL/MBON/navigation readouts, and global off activity. Assess effect sizes against all six saved controls. A changed trajectory after restoring weights need not rejoin the old control because recurrent histories diverge.

Improved dynamics would identify dependence on an implemented term. It would not establish the absence of biological excitation, reproduce mAChR-B modulation, calibrate PN→KC transfer or APL release, fix navigation, or promote H1. Unchanged or worse dynamics are valid results. No further whole-network gain sweep or Eon body integration is included.

## Resource and completion policy

Use four neural integration threads, sequential workers, 50-tick durable chunks, at most one hour per trial / six hours globally, 4 GiB output per trial, 8 GiB worker peak RSS and at least 10 GiB free disk. Preserve failures, partial returned outputs, coherent-state flags and forced-stop evidence. Never automatically restart or resume a failed scientific run.

The existing task heartbeat should check only parent completion and process liveness while work is running, remain quiet on unchanged state, and pause itself before one combined review. A producer `passed` flag means completion and online invariants, not physiological or independent numerical acceptance.
