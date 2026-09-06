# Complete passive-transient comparison

Completed 2026-09-06 UTC. The [passive amplitude/delivery batch](39-apl-passive-measurement-batch.md) and [dedicated AHP measurements](40-apl-dedicated-ahp-measurements.md) are now complemented by a complete single-exponential transient comparison. The result constrains the next model choice: a fitted tail time constant is strongly dependent on the window and does not transfer cleanly to switch-off recovery.

## Frozen fits and conditional prediction

The [plan](../validation/apl-passive-transient-plan.json), SHA-256 `ea0395403d19aaa879b56201ba029fb0b950c25195ca1fa8089cce7e13bd44bd`, fixes **82 files, 2,132 individual-sweep fits and 328 mean-trace fits**. All results were completed before analysis. All original sweeps and source identities are retained; no source workbook value or favorable trace chooses a fitting window.

The descriptive onset model is `V_inf + B exp(-t/tau)`, where t is time from the −50 pA step onset. Tau is bounded at 0.5–200 ms, with a declared 0.2 mV observed-span floor. The primary window is 5–100 ms after onset. Every within-file mean is also fit over 1–50, 5–50 and 1–100 ms. Original 10 kHz values are used without smoothing or downsampling. The linear coefficients and tau are fit together by profiled least squares. Neither V_inf nor the extrapolated onset is forced to the earlier measured plateau/baseline.

For conditional switch-off prediction, tau is kept fixed from the onset fit. The predicted voltage is `V_base + deltaV exp(-t_off/tau)`, using the independently measured pre-step held baseline and late passive plateau-minus-baseline difference from the previous batch. Predictions are scored over 5–100 ms after switch-off. No recovery value optimizes tau or either endpoint. This is an explicit **within-record conditional prediction**; the endpoints themselves come from the record, and the records have been seen previously. It is not a blind animal holdout. The fitted onset curve is also scored over the later 100–400 ms plateau interval.

## Complete results

Every requested fit completed. None of the 328 mean fits reaches a tau bound. **221 of the 2,132 individual-sweep fits reach the 200 ms upper bound**; none reaches 0.5 ms. These bound results remain visible and are not treated as physiological estimates or silently replaced with the mean-trace fit.

| Onset fit window | Median mean-trace tau | Tau range across files | Median onset RMSE | Median conditional offset RMSE | Median offset error / passive step |
|---|---:|---:|---:|---:|---:|
| 1–50 ms | 9.134 ms | 4.939–13.568 ms | 0.0897 mV | 0.3751 mV | 6.95% |
| 5–50 ms | 13.736 ms | 6.551–20.910 ms | 0.0300 mV | 0.5399 mV | 9.91% |
| 1–100 ms | 12.922 ms | 5.611–18.686 ms | 0.1035 mV | 0.4999 mV | 9.24% |
| 5–100 ms, primary | 18.360 ms | 7.219–29.782 ms | 0.0523 mV | 0.7286 mV | 13.30% |

These inventory medians mix experiment/genotype, sleep states and before/after-drug files. They summarize the fixed numerical comparison, not an independent-sample population estimate. The maximum ratio between the four fitted mean-trace taus for one file is **4.107**. Fitting later portions can produce a small onset-window residual while giving a poorer conditional recovery prediction. The primary offset error ranges from 4.73% to 23.78% of the measured passive step; these are measured discrepancies, not an invented accept/reject standard.

The [full results](../validation/apl-passive-transient-results.json) retain every fit's coefficients, extrapolated onset, asymptote, residual, numerical rank/conditioning and bounds. All individual-sweep fits remain separate. Late-plateau and switch-off scores are saved for each mean fit. The original recording intervals, artifact and bridge-compensation uncertainties are unchanged.

## Independent verification

The [review](../validation/apl-passive-transient-review.json) independently optimizes **all 328 mean fits** with a centered-regression coefficient calculation and a separate scalar optimization over the full log-tau interval, including both bounds. This differs from the producer's least-squares matrix solve and grid-plus-local-refinement route. Their maximum absolute MSE difference is **2.29 × 10⁻¹⁶**; maximum relative tau disagreement is **6.17 × 10⁻⁸**. All **984 residual/optimization/prediction checks pass**. The 2,132 single-sweep optimizations are not all independently repeated; they retain the tested reference fitter's diagnostics, and that verification limit is explicit.

The [figure](../validation/apl-passive-transients.png) was rendered and visually checked. It includes every file's window dependence, all 328 onset-versus-offset error pairs, the complete single-sweep tau distribution with its upper-bound pileup, and all 82 normalized offset traces/predictions. The normalization uses each file's measured passive step only. The saved full-resolution mean traces occupy 1,011,188 bytes, SHA-256 `3a2568148a74a963c9a86a154eccc2e143a5e7b0e182e32cc99f01a96f30ca34`.

## Interpretation and next model comparison

The electrical responses show a fast change plus slower relaxation that a freely fitted single exponential summarizes differently depending on which portion is used. A tail fit with an unconstrained extrapolated onset can absorb unmodeled fast behavior into its amplitude. Its tau should not then be called the membrane time constant or used to infer capacitance from the measured resistance. Electrode/access effects, cable modes, active currents and acquisition filtering are possible contributors; this comparison does not distinguish them.

A useful next candidate is a **positive sum of fast and slow passive relaxation components**, constrained to share the measured voltage endpoints and predict both onset and the finite-pulse switch-off response. This can test whether a compact linear response captures the observed shape more consistently before introducing an active outward-current component for AHP. Fit only declared onset windows and evaluate switch-off without retuning against it; report single-component controls and sensitivity/boundary degeneracy. Additional components are a proposed observational model, not a claim that each fitted component is an anatomical compartment or a specific ion channel.

After that comparison, use the separate 2 nA AHP waveforms, explicit repeated-sweep variation and fly-level partitions to evaluate a slow active recovery candidate. Do not select a 9 ms or 18 ms global value merely because a particular fit window gives an attractive curve. Absolute correction state, soma-to-local-release transfer, natural synaptic conductance and mated-female-to-male transfer remain separate. No H1 promotion, recurrent network run, global E/I gain sweep, decoder/body change or cancelled Eon integration occurred.
