# Displayed-rate 5 ms filter: conditional direction result

**A fixed-positive-gain first-order 5 ms filter of the admitted plotted E rates cannot produce F's positive late-minus-early current difference, for any finite nonnegative initial filter state.** This is a conditional result about a direct mapping of separately recorded displayed means. It does not reject a biological inhibitory receptor, identify its kinetics, or rule out a recurrent network containing 5 ms synaptic states.

The [prospective design](ln-inhibitory-linear-filter-design.md) was reviewed before implementation. The [execution plan](../validation/ln-inhibitory-linear-filter-plan.json) was frozen before real-bin evaluation, SHA-256 `5a06f97accebbe83e47c3f1265db680b480cba24e944cad1fa14cf7e999b4b92`; the [script](../scripts/check_ln_inhibitory_linear_filter.py) hash is `66ecca05fbb32d63029d78a56216ce7deea68f3eb739f35f5fbb08cadadbfeb7`. One recorded evaluation completed without failure or amendment. The two precision levels were part of that frozen evaluation, not separate tuned attempts.

## Result and units

The declared equation is `tau*x' = -x + G*r(t)`, with `tau=0.005 s`, fixed `G>0`, and unknown `x(t0)=x0>=0`. Start time is the first supported E boundary, `t0=−0.197 s`. The unchanged comparison windows are early `[0.05,0.15) s` and late `[0.25,0.35) s`; the original baseline `[−0.15,−0.05) s` remains part of the input history and is not assigned an exact zero.

The signed window difference is

\[
\Delta x=\alpha x_0+G B[r],\qquad
\alpha=A_{\rm early}(e^{-0.2/\tau}-1)<0.
\]

| Quantity | Retained result |
|---|---:|
| Input-driven contribution `B`, lower bound | −16.4013534634486 |
| Input-driven contribution `B`, upper bound | −8.64902091164991 |
| Fixed absolute numerical guard | 0.0000000001 |
| Guarded upper bound | −8.64902091154991 |
| Initial-state coefficient `alpha` | approximately −1.75720567599082 × 10⁻²³ |
| Source F late-minus-early graphical current interval | +1.48903484341238 to +2.29178451593021 pA |

`B` is expressed in the **formal unit-gain filtered-rate scale**, inherited from the plotted spikes/s input. It is not a predicted pA current or a conductance. No value of `G` was selected, estimated or used to fit amplitude. Table values are display rounding; [results](../validation/ln-inhibitory-linear-filter-results.json) preserve 60- and 90-digit decimal strings, including both guarded bounds.

Since the guarded upper bound remains strictly negative, `G*B` is negative for every `G>0`. The unknown initial-state term is nonpositive, so it cannot reverse that direction. Setting `x0=0` maximizes the possible difference algebraically; it is **not an observational assumption of zero baseline**. The small coefficient was retained rather than discarded, because an arbitrarily large allowed initial state can still have a substantial negative effect. An unrestricted negative initial state would invalidate this exclusion. A constant observation offset cancels between windows.

## Input and numerical evidence

All **547 required 1 ms bins** from −0.197 through +0.35 s have source support. The full displayed E record has 600 bins; its nine unsupported edge bins were neither filled nor extrapolated. Each required bin retains all eight combinations of its ink endpoints and the E 20/60-tick anchor endpoints: **4,376 corners per precision**. Negative lower rate bounds near the displayed baseline remain unchanged. No centerline, clipped rate trace, new segmentation or constant-within-bin source trace was created.

The kernel is integrated with its sign retained. Positive kernel mass multiplies the upper rate bound for an upper response bound; negative mass multiplies the lower rate bound. The bin containing the kernel's crossing, at approximately `0.149999999989694 s`, is split at that crossing. The independently relaxed bin/anchor ranges enlarge the input family; they support a conservative exclusion rather than a uniquely reconstructed source curve.

All **16 top-level checks pass**, including nine manufactured checks at each precision. Those cover zero input, unknown nonnegative initial state, constant-input equilibrium and its small zero-state transient, signed enclosures and four impulse locations. These are numerical fixtures, not biological trials.

The 60/90-digit calculations differ by at most **3.54 × 10⁻⁵⁸** across checked bounds, coefficients and bin quantities. **548 sign-constant interval integrals** were independently checked with SciPy quadrature. Each integral was normalized by its width and endpoint kernel scale before comparison, so tiny coefficients were not accepted merely through a loose absolute tolerance. Maximum normalized disagreement was **2.23 × 10⁻¹⁶**, and the maximum quadrature error estimate was **1.12 × 10⁻¹⁴**. Propagating these checks using the largest admitted rate gives an allowance below **1.53 × 10⁻¹²**, smaller than the frozen `1e−10` guard. These are numerical checks, separate from graphical or biological uncertainty.

The [compressed bounds archive](../validation/ln-inhibitory-linear-filter-bounds.json.gz) preserves all bin corners, signed masses, contributions at both precision levels, coverage and normalized quadrature records. Its compressed SHA-256 is `6ee2adea5ddad8ee56d9047d410bcd028acca74e5f365fed503978f8a37abfa6`; the numerical receipt also pins the decoded bytes. The [attempt marker](../validation/ln-inhibitory-linear-filter-attempt.json) records the state before checking/evaluating inputs; its historical `real_E_bins_evaluated_yet=false` is superseded by the completed results, not rewritten.

## Interpretation ceiling

The [figure extraction](ln-inhibitory-transfer-phase2.md) supplies **graphical ink/anchor enclosures**, not SEM, confidence intervals or bounds on recording error. F's nine-cell postsynaptic current cohort differs from E's five-cell presynaptic cohort. They are not paired measurements. D repeats F's current data and was not counted again.

E's plotted rate is reported with 100 ms acausal Hanning smoothing; current preprocessing is incompletely specified. This test treats that displayed curve as its mathematical input without deconvolution or equating it with transmitter release. Broad NP3056 experiments in young female flies do not identify the modern male targets or their incoming receptors. Population recruitment, release mechanisms, observation filtering and compartmental effects remain outside the declared direct filter.

Accordingly, this result supplies a **conditional descriptive incompatibility** for one fixed filter and one fixed sign comparison. It is not biological receptor rejection, an estimate of a longer time constant, a per-spike gain, a pA/nS conversion, or a full-network model verdict. No new source was acquired, no gain or initial state was fitted, no alternative kernel was searched, and no neural/body simulation ran.
