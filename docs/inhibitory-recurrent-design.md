# Prospective recurrent inhibitory comparison

**Design only: no recurrent kernel was implemented or network run.** This proposal was drafted without reading the new conditional factorial's outcomes and does not select H1. The [promotion gates](inhibitory-promotion-gates.md) remain in force. The four-arm conditional replay is frozen separately under plan SHA-256 `add6680e275f4540a3f21ff2d9422313a918fc63ca29bc5dbc59b4501cb1e9fc`; its eventual numerical results do not by themselves establish recurrent behavior or physiology. No body benchmark is proposed.

The bounded question is whether changing inhibitory voltage dependence, synapse handling, or their interaction preserves reproducible stimulus responses while avoiding the original voltage pathology and introducing no unacceptable activity persistence or collapse. This requires newly generated recurrent spikes in each arm. Replaying the old network's source spikes cannot answer it.

## Arms and a fixed 60-trial panel

Retain the complete existing MaleCNS graph, signed float32 weights promoted on use, 0.1 ms macro clock, −52 mV rest/reset, −45 mV strict threshold, 20/5 ms time constants, 18-tick delay, and existing seed initialization. No gain, sign, receptor-mixture or depression search is included.

| Arm | Voltage equation | Synaptic handling package |
|---|---|---|
| C0 | Original single signed current-like state | Freeze while unavailable; reject unavailable/firing-tick synaptic arrivals; reset synaptic state on spike |
| C1 | Same single signed current-like state | Always decay; accept unblocked synaptic arrivals while refractory and on firing tick; retain state on spike |
| H0 | Positive current plus inhibitory `h(E_I−v)`, `E_I=−75` | Original freeze/reject/reset package |
| H1 | Same hybrid equation | Always-decay/accept/retain package |

For H arms, positive weights increment `p` unchanged and negative weights increment `h` by `−w/23`. This matches the inhibitory driving term at rest and remains an engineering normalization. All three changes in each handling package stay explicitly bundled. Analyze H0−C0, H1−C1 and `(H1−C1)−(H0−C0)`; H1−C0 alone cannot isolate inhibition.

Use seeds **11, 12 and 13** and the five existing [Or42a conditions](or42a-summary-experiment.md), giving four arms × five conditions × three seeds = **60 trials**. Each trial lasts **3.0 seconds**, with 600 diagnostic intervals of 5 ms and 30,000 neural ticks. The original first 1.5 seconds remain unchanged; append 1.5 seconds of external input off.

| Condition | 0–0.5 s | 0.5–1.0 s | 1.0–1.5 s | 1.5–3.0 s |
|---|---:|---:|---:|---:|
| No imposed events | 0 | 0 | 0 | 0 |
| Constant baseline, then off | 11 | 11 | 11 | 0 |
| Ethyl-acetate profile | 11 | 149 | 11 | 0 |
| Isoamyl-acetate profile | 11 | 57.67908699377742 | 11 | 0 |
| Ethyl-acetate profile; source outputs blocked | 11 | 149 | 11 | 0 |

Values are independent external excitation-event rates per input cell in Hz. The same ordered **36 exact VM7d IDs** from [the frozen Or42a plan](../validation/or42a-summary-plan.json), 18 per side, are present at every tick, including no-events and off periods. All listed sources retain zero refractory duration; other cells retain 22 ticks. Do not add the runtime's zero-rate general odor list, taste cells, P9, proprioception or background current. Baseline and chemical-profile values combine different published summary cohorts; they are not concentration-calibrated odors or a held-out receptor-model prediction.

Generate one immutable 30,000 × 36 uniform array per seed with the existing RNG algorithm and retain its exact start/end state. Each arm and condition consumes the same ordered draws; only the frozen rate schedule changes the candidate event mask. Retain per-condition candidate masks and actual per-arm direct-event acceptance. Sharing a random stream pairs the perturbation; it does not force identical source spikes after recurrent activity diverges. No-events and input-off keep the draw/eligibility convention, with zero event probability.

## Keep direct input semantics separate from the factorial

At each tick, integrate eligible voltages using previous synaptic states; test `v > −45`; record spikes at the original tick stamp; enqueue every newly generated source identity for delivery 18 ticks later. Visit queued edges in the original source/CSR order and evaluate the fixed source-output mask at delivery. Apply direct **68.75 mV voltage increments after threshold** with the original source availability test, including rejection on a source's firing tick. Reset after delivery.

C1/H1's permission to accept *recurrent synaptic-state* arrivals during refractoriness must **not** change the direct voltage-event rule. Direct stimulation is identical in definition across all four arms. Reusing `ConductanceDrive` would change input amplitude units and event semantics and is excluded. In package 1, reset affects voltage only; in package 0 it clears the synaptic state(s). All targets, including the 36 stimulated cells, generate their own new recurrent spikes. Neither the two earlier target cells nor any previously recorded cell has its output clamped to a history.

H's lower bound applies because initial/reset voltages are above −75, `p,h` are nonnegative and external voltage increments are positive. Preserve post-external voltage as well as pre-threshold extrema: positive events can exceed threshold after that tick's threshold phase. There is no universal 0 mV upper bound, and no voltage clamp is allowed.

## Isolated implementation and performance decision

Implement a standalone experiment-local Numba kernel/wrapper, importing the frozen [hybrid interval helper](inhibitory-factorial-solver.md) where appropriate. Do not change `fruitfly/neural.py`, `conductance.py`, config defaults, decoder gains, viewers or saved plans. Keep C0's single signed state and exact NumPy coefficients/operation order. Retain array dtypes, graph order, queue behavior and checkpoint metadata. Use bounded storage and sequential trials rather than a new general simulation framework.

**Measure performance before freezing/executing the full panel.** Its 180 neural seconds may be expensive: exact 32-point quadrature is invoked for available neurons with nonzero `h`, potentially billions of intervals. The earlier current-only run time is not a prediction of hybrid throughput.

The proposed separately frozen performance probe has two parts: (1) the same fixed scalar state grid tiled into arrays, including `h=0`, moderate and high conductance, to measure fast-path versus quadrature cost; and (2) a fixed 50 ms baseline-input prefix for each of the four arms, seed 11, in disposable full-graph states. Record compilation separately from warmed execution, peak memory, saved-byte rate, graph size, cell updates, fraction of hybrid evaluations, inversion iterations, edge visits and spike counts. These short prefixes are execution measurements, not activity or physiology results. A quiet prefix underestimates later recurrent load; use the tiled nonzero-h measurements to bracket that uncertainty.

Before that probe, freeze a host-specific wall-time and storage budget in its plan. Its bounded measurements should determine whether all 60 trials fit. If not, retain the measurement and optimize the isolated implementation under parity/reference checks or pause before the panel. Do not silently drop C1/H0, choose the cheapest seed, shorten only an unfavorable trial or replace 32-point quadrature with a new approximation. Any revised numerical method or panel requires its own plan before outcomes are generated. Performance probes are not reused as scientific trials.

## Evidence sufficient for a saved-data review

Freeze script/helper/environment/graph hashes, the exact 36 inputs, first-hop and output populations, all conditions, source masks, seeds, duration, window definitions, storage schema and numerical tolerances before running. The 365 original directly targeted nonsource cells remain a structural cohort; no response-dependent selection is allowed. Keep existing motor groups as raw neural readouts; no decoder action or body is needed.

Retain:

- Every network spike as ordered integer tick/index records; per-neuron window counts; complete initial, phase-boundary and terminal checkpoints, including all synaptic states, last spikes, refractory values, queue counts/order and RNG. Flush progress and checkpoint any failure without resetting or replacing the trial.
- The shared uniforms, held rates, candidate masks, direct applied/rejected masks, actual source spikes, complete fixed outgoing block mask and its hashes. Instrument direct-event decisions in the isolated kernel rather than mislabeling inferred events as observed writes.
- Every-tick pre-threshold and post-external/reset global extrema, nonfinite flags and counts of bound violations; explicit extrema identities and their preceding states. Per-5 ms voltage distributions, firing counts, active-cell fractions and `h`/stiffness summaries are sampled statistics, separately labeled.
- Per-tick selected state/availability/firing traces for 67052 and 13314; per-1 ms source/motor-state samples. Complete spike streams reconstruct other cells' refractory schedules. It is unnecessary to save a prohibitively large all-neuron/all-tick voltage cube, but do not imply one was retained.
- Exact visited/accepted/target-unavailable/source-blocked edge counts by interval and sign, with zero-weight edges accounted for. Save ordered edge IDs and dispositions for the two selected targets and predeclared audit intervals. The full spike stream, immutable graph and source mask permit independent reconstruction of visited edges and target-eligibility decisions; a visit is not an accepted write. Preserve pending sources without deciding an unobserved future delivery.

For C0, compare each first 1.5-second prefix against its matching saved original Or42a trial: all ordered spikes, candidate/applied events, RNG, window counts and available endpoint voltage/synaptic state must agree bitwise. The new current-kernel instrumentation must not alter arithmetic. H1/C1 no-input trials should remain at reset with zero synaptic states/spikes under these deterministic initial conditions; this is a model consistency control, not a requirement that biological flies have no spontaneous activity. The source-output-block condition should have no nonsource spikes from reset and no source-edge delivery, while stimulated source cells continue their own activity.

For H numerical checks, reuse the helper's validated 32/64-point and adaptive-quadrature/time-domain references. Before the panel, select local transitions by fixed rules: regular times for both target cells, largest `h`, largest stiffness, smallest absolute threshold margin, largest positive-state/current ratio and every encountered bound/nonfinite failure, with deterministic tick/index tie-breaking. Save the exact preceding state and phase for each selected transition. Production/reference differences use the helper's 1e−8 mV gate, independent ODE/quad comparison 2e−8 mV, and the lower bound 1e−10 mV. A threshold margin comparable to numerical error must be reported as unresolved timing robustness; a valid lower bound does not establish correct spike timing. Additional reference work may inspect retained states, without silently rerunning or replacing primary outcomes.

## Contrasts, recovery and promotion limits

Report `[0,0.05)` startup and `[0.05,0.5)` baseline separately, then the original pulse `[0.5,1.0)` and baseline-recovery `[1.0,1.5)` windows. Divide input-off into `[1.5,2.0)`, `[2.0,2.5)` and `[2.5,3.0)`. Preserve raw 5 ms trajectories so transient peaks and ongoing growth are not hidden by means. Rate equals count divided by the declared population size and window duration; include individual-cell distributions and silent fractions.

For each seed and arm, report pulse-minus-matched-baseline and ethyl-minus-isoamyl contrasts for source, first-hop, target, nonsource and motor groups. Then report the factorial contrasts within the same seed and condition. Do not average away an opposite-sign seed or call three simulation seeds independent animals. The blocked condition tests propagation, not identical afferent firing. There is no preregistered claim that total downstream firing must increase with input strength.

Report post-pulse and off-period persistence against the same arm/seed's constant-baseline-then-off and no-events controls: cell recruitment, sustained rate, changes across consecutive off bins, high-rate tails and distance from baseline distributions. Rising activity across all off bins, near-refractory saturation or lost stimulus contrast are explicit engineering warning patterns. Their absence is not a physiological pass. No arbitrary spike-count ceiling or zero-tail rule is asserted to be biology; any future binary engineering acceptability threshold must be declared before results, separately from measured physiological targets. A 3-second outcome supports only that horizon.

Promotion requires numerical accuracy, meaningful reproducible contrasts, acceptable recurrent behavior under the declared engineering scope, and physiological amplitude/timing agreement at the level the data actually support. The current Or42a profile is an excitation-event engineering stimulus. It cannot validate LN→LN inhibitory transfer, per-contact nS/pA, receptor identity or absolute amplitude in either exact target. The [Nagel–Wilson temporal-transfer source](ln-inhibitory-transfer-source.md) and other physiology in the promotion gates require separate compatible observation models and retained uncertainty. No bounded plot, quieter network, disappearance of extreme negative voltages or preferred H1 result supplies those missing tests.
