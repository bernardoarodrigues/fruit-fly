# Complete APL passive-step measurement batch

Completed 2026-09-06 UTC after [workbook reconciliation](38-apl-electrophysiology-workbook-join.md). This is the first complete raw-voltage measurement batch from the new APL electrophysiology deposit. It establishes a usable somatic passive-response reference for the graded APL candidate; no fitted parameter or neural runtime setting is promoted.

## Fixed scope and methods

The [plan](../validation/apl-passive-measurement-plan.json), SHA-256 `479c50ce938b6eec9b5c5a993adf9521e40232ffc1e0250a6706125a4c0d2917`, was frozen before loading voltage samples. It includes **all 82 APL firing-pattern files and all 26 sweeps per file: 2,132 sweeps**. Source/code hashes and every author row, including unmatched rows, are retained. All results were produced before interpretation.

The header-defined −50 pA passive pulse lasts 500 ms. Its onset is reconstructed from the pre-epoch holding length and preceding epoch duration, and checked against pyABF's sweep epoch table on every sweep. ADC channel 0 must be mV. The baseline is the final 100 ms before onset; the plateau is the final 100 ms before offset. These are declared measurement windows, not a claim to duplicate the authors' cursors. No smoothing, outlier removal, tau fit or choice of a visually favorable sweep was performed.

Resistance from the command is `1000 * delta_mV / -50 pA`, in MΩ. When an ADC channel is labeled pA, a second resistance estimate uses its measured plateau-minus-baseline current. The two estimates remain separate. A 5 pA minimum recorded step and ±5 pA delivery tolerance are declared numerical diagnostics, not physiological exclusion criteria from the paper. No current is inferred from an mV channel.

## Delivery and completeness

The [complete results](../validation/apl-passive-measurements.json) contain every planned file and sweep. All voltage and reconstructed-command arrays were finite. Every command baseline is zero and every passive plateau is −50 pA.

- **77 files / 2,002 sweeps** have a recorded pA channel. All satisfy the declared delivery tolerance. Recorded step differences range from **−54.0833 to −50.0494 pA**, median **−50.7733 pA**.
- **Five files / 130 sweeps** have two mV channels and no pA channel. Their command-based measurement is retained, and their recorded-current estimate is explicitly unavailable.
- Using recorded rather than commanded current reduces the per-file mean resistance by a median **1.47%** among the 77 files. This is an observed command/recorded-channel scale difference; it does not establish the instrument calibration mechanism.

The verified near-50-pA changes also support the passive epoch's timing and current-channel interpretation. They do not prove bridge balance, liquid-junction correction, or absence of electrode artifacts. Constant voltage offsets cancel in this measurement. Held baselines remain held baselines, not resting potentials.

## Source comparison and variation

All-file mean command-based resistances range from **68.14 to 219.92 MΩ**, median **115.39 MΩ**. This mixes source experiments, sleep states and before/after-drug files; it is a descriptive inventory statistic, not a pooled biological parameter estimate. Repeated sweeps, bilateral cells and before/after measurements are not independent animals.

There are **79 author-value comparisons**. Baseline files compare with intrinsic resistance columns; explicit NS8593 files compare with the workbook's post-drug column. Three files have no such comparison: the unmatched suffixless cell, the RNAi cell present only in the 2 nA AHP sheet, and the ambiguous `_FP_NS_` filename. The last file is measured but is not silently assigned an author before/after target.

The difference between our fixed-window all-sweep mean and the author value has median **−3.37 MΩ**, range **−12.56 to +6.13 MΩ**. Median relative difference is **−2.69%**, with maximum absolute relative difference **11.70%**. The source scatter follows the identity line closely, corroborating the corrected MΩ interpretation. It does not show exact reproduction of the original author cursor/sweep calculation. Four comparisons differ by more than 10 MΩ; they are retained and may reflect window, averaging, drift or other acquisition/analysis differences. No cursor was retuned to reduce these residuals.

Within-file sweep ranges can be substantial. Every sweep's baseline, deflection, resistance, current statistics and plateau-half change is saved. The mean response alone must not be used to claim stationary physiology or independent replication. Date/side/name conflicts from the workbook join remain present in the source fields, with exact filename-prefix and directory-match flags. No cell identity is repaired by a good numerical match.

## Independent checks and visual review

A separate [review script](../scripts/review_apl_passive_batch.py) reloads every file, uses integer sample slices and compensated scalar summation (`math.fsum`), and recomputes baseline voltage, voltage difference, command-based resistance, recorded current difference and recorded-current resistance. **10,400 scalar checks pass**, maximum absolute difference **1.42 × 10⁻¹⁴**. The measurement and review share the pyABF binary reader; this is independent arithmetic and window indexing, not an independent ABF decoder.

The [four-panel figure](../validation/apl-passive-measurements.png) was rendered and visually inspected. It includes all 82 mean voltage traces, all 77 available mean recorded-current traces, all 79 source comparisons, and the full within-file resistance ranges. Lines and ranges are descriptive, not confidence intervals. Plot arrays are means across all 26 sweeps decimated to 1 ms; the original 10 kHz samples were used for measurement. The saved trace arrays are 450,484 bytes, SHA-256 `efbd61f26d2d3e4a9f35548d6946a2e9513d56a8520641ca25fb27ed3eb65410`.

## Model consequence and next step

The measured passive responses supply a direct electrical constraint with much stronger temporal resolution than the earlier calcium/dye plots. Their resistance scale is compatible with the source's approximately 120 MΩ description and supports studying a leaky graded APL response. It does not by itself identify a membrane capacitance, natural KC→APL conductance or GABA release law.

Next use a fixed transient comparison that preserves onset artifacts, fit-window sensitivity and within-cell repeated-sweep variation, then analyze all eleven dedicated 2 nA AHP cells together with their recorded commands and repeated-pulse history. Compare active/SK candidates with these separate passive and AHP constraints before recurrent testing. Absolute resting-potential transfer still needs a break-in/correction-state check. The source remains ex vivo mated females; the target remains one male fly. No whole-network gain sweep, H1 promotion, decoder/body change or cancelled Eon integration occurred.
