# Independent review of the Figure 6 graphical extraction

**No blocking numerical or interpretation issue found.** On 2026-09-05 I source-reviewed the extractor, independently checked saved calibration/bin/summary arithmetic and receipts with 97 bounded read-only checks (all passed), and inspected the corrected overlay. No extraction, flattening, model run or fit was repeated. I did not author the executed extraction.

The [phase-2 plan](../validation/ln-inhibitory-transfer-phase2-plan.json) hash is `8da8c3f16dbf1cdb2ddf247bb91917e547d0a47694eb15dfa0d4dae634e734d9`; it precedes extraction. Its [extractor](../scripts/extract_ln_inhibitory_transfer.py) remains `428a1aa227f4a907d14626aa6b9064c0dc437a0a7cfc42fcf225be4996416174`, and the source PDF remains `3991919a050c83687014e9204f76cc1f48e6dd91949204156a81ab16f294ecfe`. Source/plan inputs, numerical artifacts, summary CSV and overlay receipts match their recorded sizes/hashes, resolving moved images through the [relocation receipt](../validation/ln-inhibitory-transfer-phase2-relocation.json).

Calibration is dimensionally consistent. D uses its own 1 s and 4 pA bars; F uses 200 ms and 4 pA bars. E shares F's expanded time axis and derives rate scale from its 20/60 spikes/s tick ink, with the 40 tick providing a separate check. Coordinates increase downward, so an upward deflection gives positive outward-current change. The scale intervals preserve finite endpoint/tick thickness. They represent an explicit graphical uncertainty convention, not measured instrument calibration errors.

All nine required windows contain 100 supported 1 ms bins. These are display integration partitions, not acquisition samples. Independent duration-weighted calculations agree with the saved means within `2e-12` PDF points. The source uses an arithmetic mean because these fixed windows align exactly to equal-width bins; floating representation of their widths does not materially change the result.

For each change, the calculation first subtracts y-coordinate enclosures and then divides by one shared positive scale interval. This cancels the common vertical origin. Late-minus-early does not reuse or double-count baseline uncertainty. Per-bin unions over admissible time anchors/scales, followed by interval subtraction, can combine extremes that are not jointly attainable under a single calibration. This makes the result potentially wider; it is a conservative enclosure conditional on the stated ink/anchor model, not a sharp uncertainty interval or a guaranteed bound on the original recording. E's absolute plotted-rate calculation keeps its 20/60 anchors together in the affine calibration.

All 12 CSV rows reproduce the saved quantities, units and cohort labels. The main directional results are:

| Displayed change | Graphical interval |
|---|---:|
| F late minus early outward current | +1.489 to +2.292 pA |
| D late minus early outward current | +1.172 to +3.271 pA |
| E late minus early rate | −15.657 to −8.608 spikes/s |
| E plotted baseline rate | −0.953 to +0.831 spikes/s |

Displayed bounds are rounded outward to three decimals; the saved CSV retains full precision.

The first three intervals resolve the displayed directions under the declared graphical rule. This is not biological statistical significance. The baseline interval straddles zero: its negative lower endpoint reflects graphical location/calibration uncertainty, not negative physical firing. It should remain unclipped and must not become an exact zero anchor for a future fit.

D and F show the same nine-cell current cohort. Their three corresponding change intervals overlap; this is graphical consistency, not replication, and they must not be pooled as 18 cells. E is a separate five-cell rate cohort, with seven artwork pieces representing one mean. Neither a current/rate ratio nor per-spike gain is identified. The E SEM, negative-control mean, absolute holding current and conductance remain unavailable. The graphical intervals are not substitutes for SEM, individual cells, confidence intervals or likelihoods. PSTH smoothing and unknown current preprocessing still prevent a precise causal latency or time-constant inference.

The corrected overlay visibly aligns the selected F/D black traces and E green union with the source rendering. The initial raster-frame error is separately retained; only image registration changed, and all numerical geometry hashes remain unchanged. The frozen results' `pending overlay inspection` field and the design review's “unperformed” statement record their earlier stages; the subsequent [53-check validation](../validation/ln-inhibitory-transfer-phase2-validation.json), corrected-overlay and relocation receipts supply the later attribution status. They should be read together without rewriting the frozen artifacts.

This supports retaining the extracted graphical constraints for a separately declared observation-model comparison. It does not identify male replay-target physiology, contact conductance, receptors, or a preferred inhibitory handling package.
