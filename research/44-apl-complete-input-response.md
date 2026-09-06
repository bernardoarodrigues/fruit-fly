# Complete APL stimulation-response measurements

Completed 2026-09-06 UTC. This follows the [conditional active-recovery candidate](43-apl-graded-state-and-active-recovery.md). The full drive-response batch establishes two requirements that a stimulation-driven model must satisfy together: strong depolarization is compressed relative to small-signal resistance, yet voltage continues rising during the pulse. Initializing an outward-current state only after the pulse does not address either requirement.

## Frozen complete measurements

The [plan](../validation/apl-input-response-plan.json), SHA-256 `be7515089640f1563e4f062d1d02dcfc68e5f40cd375450f281b07ea7e088a04`, fixes **93 files and 2,197 sweeps**: all 82 firing-pattern files (2,132 sweeps) and all eleven dedicated 2 nA files (65 sweeps). No fit or subset selection occurs. The complete results are produced before interpretation.

For staircase files, DAC0 epoch 3 is reconstructed with its exact per-sweep amplitude increment. Dedicated-pulse files use epoch 1. The observed protocols have 500 ms pulses with 5 or 10 s sweep intervals, or 750 ms dedicated pulses with 60 s intervals. Recording timestamps, sweep order, nominal sweep start times, source identities and all sample windows are retained. The staircase's preceding −50 pA pulse and intervening gap remain part of the raw protocol rather than being erased by a claim of independent steady-state stimulation.

Measurements use the final 100 ms before pulse onset as baseline, the final 100 ms before offset as plateau, and 50–100 ms after onset as the early window. The first-100-ms maximum and a signed post-offset minimum over a common +5 to +600 ms window are also retained. That common post window fits even the shorter recordings; it is not a complete recovery interval. Raw extrema remain noise-sensitive descriptors, not accepted spike/AHP kinetics. No smoothing, voltage correction, current inference from mV channels or rejection of sweeps is performed.

## Delivery and independent arithmetic

All **2,044 sweeps with a recorded pA channel** agree with the commanded plateau-minus-baseline step within the declared tolerance `max(5 pA, 5% of the commanded step)`. **153 sweeps lack a recorded pA channel** and retain command-only measurements. Command timing and levels are checked against the reconstructed waveform. This rules out a large command/delivery discrepancy under the declared checks, not every possible acquisition or compensation error.

The [independent review](../validation/apl-input-response-review.json) reloads every file and recomputes baseline voltage, plateau/early deflections, late-minus-early response, signed post minimum and recorded-current differences using compensated scalar sums/minima. **13,029 checks pass**, with zero numerical difference at the retained precision. Both routes use the same ABF reader. Pulse timing and first-peak indices are retained from the producer rather than independently decoded by the reviewer; that limit is explicit.

## Large-signal compression

Each of the 82 staircase files contains a 1 nA sweep. Its late plateau is compared with the linear extrapolation from that same file's previously measured −50 pA resistance. All 82 ratios are below one:

| Comparison | Records | Observed / small-signal linear prediction: minimum | Median | Maximum |
|---|---:|---:|---:|---:|
| 1 nA staircase plateau | 82 files | 0.423 | 0.575 | 0.844 |
| Mean 2 nA dedicated plateau | 11 matched cells | 0.298 | 0.429 | 0.504 |

The 2 nA comparison uses each cell's matched small-signal recording, with the identity joins preserved. These summaries mix source experiments, genotypes, states and repeated before/after records. They are descriptive constraints, not independent-animal population estimates or new male-specific findings.

The linear residual can be expressed as an equivalent missing current, `I - deltaV/R_small`, for bookkeeping. It must not be labeled measured SK current or attributed to a particular ionic mechanism. Voltage-dependent conductance, active channel recruitment/inactivation, cable effects and acquisition properties are not separated by this calculation. A post-offset phenomenological current amplitude also cannot be compared directly with this residual as if the underlying conductance had a voltage-independent driving force.

## Rising voltage during sustained input

Compression does not mean the voltage simply reaches a lower plateau immediately. At 1 nA, the late plateau exceeds the 50–100 ms mean in **all 82 staircase files**, by **4.910–21.992 mV**, median **11.163 mV**. The eleven dedicated 2 nA cell means likewise rise by **8.411–14.982 mV**, median **11.963 mV**, between these windows.

A candidate that merely clips the passive voltage or appends a post-pulse negative current would miss this within-pulse evolution. The full model must reproduce the current-dependent response shape and subsequent recovery under the same state equations. These measurements do not identify whether the slow rise is caused by inward activation, outward inactivation, distributed membrane charging or a combination. No specific channel identity is inferred from curve shape alone.

The [complete figure](../validation/apl-input-response.png) was rendered and visually reviewed. It shows all 82 I–V curves, all positive-current compression curves (≥200 pA shown to avoid a near-zero ratio display), all early-to-late changes, and every dedicated 2 nA comparison. All lower currents remain in the [full results](../validation/apl-input-response-results.json); the figure's display range is not an exclusion from analysis.

## Consequence for the executable candidate

The existing exact graded-state implementation remains a useful passive-plus-outward-current realization, but its validated scope is conditional recovery. The new data explicitly reject treating the small-signal passive gain as an adequate model of the entire depolarizing phase. The next bounded model comparison should combine a voltage-dependent response/conductance rule with an evolving recovery state, and test complete pulse-plus-recovery waveforms. Keep the existing passive parameters fixed initially and retain a simple control, so improvements are attributable to the new mechanism rather than a compensating gain change.

A reversal-potential-based formulation can address the required inhibitory bound, but its reversal and activation parameters must be declared and supported separately. The source methods retain external 3 mM KCl and an internal solution with 140 mM potassium gluconate plus 1 mM KCl; these are potential constraints for an explicitly approximate ionic calculation, not a direct measurement of APL potassium reversal under the recording conditions. Raw versus junction-corrected voltage, temperature/activity assumptions and online compensation still require care when using absolute voltages. Relative voltage measurements here do not silently resolve those issues.

Preserve source fly partitions, repeated-sweep history, the weak-cell transfer failure and all four passive variants in the next complete comparison. Do not supply the post-pulse state from measured recovery when claiming an autonomous response. Natural KC→APL drive, local GABA release, mated-female ex vivo transfer and recurrent validation remain separate gates. No H1 promotion, global E/I gain sweep, neural runtime/decoder/body default change or cancelled Eon integration occurred.
