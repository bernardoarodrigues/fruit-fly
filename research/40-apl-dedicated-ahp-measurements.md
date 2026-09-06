# Complete dedicated APL AHP measurement batch

Completed 2026-09-06 UTC after the [passive measurements](39-apl-passive-measurement-batch.md). All eleven dedicated SK-RNAi/control 2 nA recordings are measured together. The full results support an active recovery constraint for a graded APL candidate, while showing why unsmoothed threshold crossings cannot be adopted as identified kinetics.

## Frozen protocol and complete sample

The [plan](../validation/apl-ahp-measurement-plan.json), SHA-256 `8e837386bfe6c02808dd9d0ace665c5173ffd7817e842860ebe4d29e0eae0d80`, was written before voltage loading. It includes **eleven cells from eleven source fly IDs**, six RNAi controls and five SK-RNAi cells, and **all 65 recorded sweeps**. The source files contain 5–12 sweeps per cell. Repeated sweeps are not independent animals.

Every DAC epoch table commands **2 nA for 750 ms**, with a **60 s sweep interval**. Despite protocol names mentioning “30s,” each sweep contains 600,000 samples at 10 kHz. The pyABF pre-epoch convention gives onset at sample 14,375 (1.4375 s) and offset at sample 21,875 (2.1875 s); both are checked against every sweep's epoch table.

The fixed baseline covers 400–50 ms before onset. Two post-offset windows begin at 5 ms and 20 ms and end at 2.8 s. The measurement retains the most negative voltage, its time, signed deflection, all interpolated 70% and 30% crossings, and weak/incomplete/recrossing flags. An explicit 0.2 mV amplitude floor is a diagnostic convention, not an author exclusion rule. No smoothing, detrending, best-sweep selection or exponential fitting was performed. The same measurement is applied to each original sweep and each cell's all-sweep mean.

## Delivery and numerical checks

The [results](../validation/apl-ahp-measurements.json) retain every sweep and both window variants. Eight files / **42 sweeps** contain a recorded pA channel; all have a pulse-minus-baseline current within the declared ±100 pA tolerance. Their recorded changes range **2,031.504–2,031.740 pA**. Three files / **23 sweeps** have two mV channels and no recorded pA channel, so delivery remains command-only for them. Neither a voltage unit nor an instrument channel name is silently converted to pA.

The [independent review](../validation/apl-ahp-measurement-review.json) recomputes baselines and minima by scalar summation/search and every threshold crossing by a separate scalar loop. **50,248 scalar/status checks pass**, maximum absolute numerical difference **7.11 × 10⁻¹⁵**. Both implementations use pyABF to decode the original data; the binary decoder is not independently reimplemented. The reviewer initially accumulated means at the source float32 precision; correcting the review to explicit float64 accumulation reconciled the mean-trace check without changing the frozen producer or any measurement result.

## Observations and measurement limitations

The all-sweep mean AHP magnitudes have these descriptive ranges:

| Group | Cells | Median magnitude | Range |
|---|---:|---:|---:|
| RNAi control | 6 | 3.464 mV | 2.001–4.816 mV |
| SK RNAi | 5 | 1.219 mV | 0.528–2.278 mV |

The groups overlap. These are descriptive per-cell measurements, not a statistical reanalysis, a new claim about male physiology, or independently blinded confirmation of the study. They preserve the source's qualitative direction under the declared common windows and averaging. The numerical amplitudes need not match the authors' selected cursor/sweep calculations. The eleven source comparisons are retained without altering the windows to improve agreement.

Raw 70%–30% recovery measurements are substantially less stable:

- **62/65 primary-window sweeps** have repeated or reversed threshold crossings.
- One has incomplete recovery in the window, one falls below the amplitude floor, and one has an unambiguous measured interval.
- **All eleven all-sweep mean traces** still have repeated crossings. Averaging has not removed the ambiguity.

A returned first-crossing interval is therefore not an accepted physiological time constant. This is a limitation of the declared threshold measurement on these variable traces, not evidence that the circuit has no measurable dynamics. The complete mean/individual waveforms remain available for a noise-aware fit with separately constrained passive dynamics.

Starting at 20 instead of 5 ms changes none of the eleven mean-trace amplitudes because their minima occur later. This narrow window-start check does not establish robustness to baseline choice, smoothing, recovery-window length or selection of an early versus late trough. In the weakest mean RNAi response (`250522f01c01R`), the global minimum occurs **2.5768 s** after offset, in late fluctuation rather than the early recovery dip seen in stronger cells. Its 0.528 mV magnitude and first interval must not be treated as an unambiguous stimulus-locked AHP.

The article's Figure 4J was visually rechecked: its 30%–70% decay axis is labeled **ms**. The author workbook values are converted to seconds in the comparison receipt using that source evidence. They remain intervals, not exponential tau. The paper PDF is retained at `data/raw/apl-sk-electrophysiology/chen-2026.pdf`; its SHA-256 is recorded in the acquisition receipt.

## Complete visual evidence

The [figure](../validation/apl-ahp-measurements.png) shows all eleven cells, every sweep, each within-cell mean and all eleven amplitude comparisons. It was rendered and visually inspected. Thin traces reveal baseline fluctuation and substantial sweep variation even when the mean recovery is clear. The plot zoom starts 50 ms after offset; measurement windows start at 5/20 ms and are unchanged. No smoothing is used. The archived plot arrays are decimated to 1 ms, while measurement uses full 10 kHz data; array SHA-256 `36e4f15b6716771ca8a9053c33ad8a3910c4770c0a6860d4e3a5c9acba4bd677`, 568,790 bytes.

## Consequence for the next model step

The passive and dedicated AHP batches now provide complementary electrical constraints: a leaky somatic response to a small negative current and a delayed negative response after a strong positive pulse. A graded leak plus slow outward-current candidate can be evaluated against both. As a declared starting approximation, a fast passive relaxation plus a slower negative component can describe the post-offset voltage without pretending that each noisy crossing is a channel time constant. That approximation would still require fitted passive dynamics, repeated-sweep uncertainty, explicit initial state and validation against the RNAi/control contrast; it is not yet a validated SK conductance model.

Next freeze a passive-transient comparison with explicit onset/artifact and fit-window sensitivity, then fit and evaluate complete recovery waveforms using a declared noise/variation treatment and source fly-level partitions. Do not silently smooth until the original threshold metric looks better or promote a kinetic parameter from the current first-crossing outputs. Junction/bridge correction state, soma-to-local-release transfer, natural KC→APL drive and male-specific transfer remain separate uncertainties. No neural runtime, H1 promotion, global E/I gain sweep, decoder/body change or cancelled Eon integration was introduced.
