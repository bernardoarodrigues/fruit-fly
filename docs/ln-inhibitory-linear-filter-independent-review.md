# Independent review of the fixed 5 ms displayed-rate filter

**Pass: 46 checks, with no numerical or interpretation blocker within the declared conditional scope.** The [independent script](../scripts/review_ln_inhibitory_linear_filter.py) directly integrates the pointwise signed window-response kernel at 100-digit precision and checks retained rate corners and interval arithmetic. It imports no producer code, repeats no figure extraction, fits no gain or initial state, and searches no alternative time constant. The [review receipt](../validation/ln-inhibitory-linear-filter-independent-review.json) records inputs, checks and independently calculated values.

The frozen [plan](../validation/ln-inhibitory-linear-filter-plan.json), producer, results, attempt marker, compressed/decoded bounds and source-bin receipts all match their recorded hashes. The plan precedes the single recorded attempt. The reviewed producer is `66ecca05fbb32d63029d78a56216ce7deea68f3eb739f35f5fbb08cadadbfeb7`; plan hash is `5a06f97accebbe83e47c3f1265db680b480cba24e944cad1fa14cf7e999b4b92`. The independent review script is `8e5f65c042a27ee6f654b739ec89b1033379f346d271c6a20875510af995615f`.

## Mathematical sign and initial state

For `tau*x' = −x+G*r`, `tau=0.005 s`, the causal impulse response is `exp(−(t−s)/tau)/tau`. Integrating it over each observation window gives the producer's `H_W(s)` with units inverse seconds. Thus `B=∫(H_late−H_early)r ds` has the formal unit-gain filtered-rate scale; it is not a pA prediction. The separate initial-state coefficient is dimensionless.

Before the early window the signed kernel is a negative exponential. Within that window it is proportional to `exp((s−s*)/tau)−1`, with one zero; after the early endpoint only the positive late-window response remains. The independently located crossing is approximately **0.149999999989694232 s**. Its tiny positive segment before 0.15 s is retained rather than assigning one sign to the whole containing bin.

The equal-width windows are separated by 0.2 s, giving

```text
alpha = A_early * (exp(−0.2/tau) − 1) < 0,
Delta x = alpha*x0 + G*B.
```

Independent calculation gives `alpha ≈ −1.75720567599082436e−23`. It was not rounded to zero. For every finite `x0>=0`, the initial term is nonpositive; choosing zero only maximizes the possible difference mathematically. It is not an observed zero baseline or a fitted initial state. Permitting unrestricted negative initial states would invalidate this exclusion. The finite-history kernel identity `∫K=−alpha` also passes, preserving the tiny constant-input transient and cancellation with its equilibrium initial state. A constant observation offset cancels; an arbitrary input-rate offset must not simply be discarded as if the finite-history filter had no transient.

## Independent numerical enclosure checks

All 547 required bins from −0.197 through +0.35 s match the retained ink input and have complete support. The review checks all **4,376 anchor/ink corners in the 90-digit table**, their rate bounds, every signed contribution, both precision tables' bound agreement and global sums. The affine-fractional rate calibration has a positive denominator throughout the anchor box, so its extrema occur at corners. Negative pre-zero lower bounds remain in 188 bins; none are clipped or used as an exact zero anchor.

The independent calculation integrates **548 sign-constant intervals** using mpmath quadrature of `H_late−H_early`, rather than the producer's analytic bin antiderivatives. Maximum discrepancy in any signed kernel mass is below **4.0e−92**; maximum corner discrepancy is below **5.5e−89**. The single mixed-sign bin contains both masses. For each upper contribution, positive mass multiplies the rate upper bound and negative mass the rate lower bound; lower contributions reverse those pairings.

The reconstructed guarded enclosure, rounded outward to six decimal places, is **[−16.401354, −8.649020]** in the formal unit-gain filtered-rate scale. The retained high-precision upper endpoint is `−8.649020911549906649…`, including the frozen `1e−10` guard. Its numerical sign is far from zero. The producer's normalized quadrature/error arithmetic independently recomputes to a propagated allowance of about `1.5223e−12`, below that guard. This is a strong numerical cross-check, not a machine-certified directed-rounding interval proof.

The positive F current-difference enclosure is retained unchanged. Therefore, for all admitted inputs, every fixed `G>0` and every finite `x0>=0`, this filter's difference is strictly negative and cannot equal the displayed positive F difference. The gain remains unspecified: no fixed pA magnitude follows from the unit-gain bound, and there is no uniform nonzero margin over gains approaching zero.

## Interpretation ceiling

Each bin enclosure already allows the source extraction's ink and calibration uncertainty. Relaxing shared anchors and within-bin structure independently enlarges the possible input family. A negative upper bound over that larger family supports the conditional exclusion; an inconclusive bound would not establish a realizable matching trace. These are graphical sensitivity ranges, not SEM, confidence intervals, individual-cell variation or guaranteed recording-error bounds.

E's five-cell rate cohort and F's nine-cell current cohort are separate recordings. D repeats F's cohort. The E mean has reported 100 ms acausal Hanning smoothing; this calculation treats that displayed mean as input without deconvolution or identifying it with spike timing or transmitter release. Broad female NP3056 LN populations do not identify the male replay cells or their receptor currents.

The result consequently excludes **one direct, fixed-positive-gain, 5 ms mapping of the displayed summaries under the nonnegative-initial-state assumption**. It does not reject a biological receptor, select a longer time constant, estimate conductance or per-spike gain, or rule out recurrent recruitment in a network containing 5 ms synaptic states. No biological or runtime parameter promotion follows.
