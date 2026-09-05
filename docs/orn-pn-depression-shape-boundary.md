# Conditional depression fit: recovery-ceiling check

The imposed 100 s recovery ceiling hid a **small numerical improvement** under the same finite-baseline model. Fitting the nine resolved 20 Hz means in normalized shape coordinates gives `b=0.26112538764204973`, `q=0.8079004712382397`, and development SSE **179.25692182005457** percentage-points squared. One compatible finite inverse was detected in the declared search: `f=0.8082894819335432`, `τ=103.86539120086083 s`.

Development RMSE falls by **0.003059 percentage points**, from 4.465954 to 4.462895. This resolves the narrow search-boundary question. It does not turn the fitted recovery constant into a physiological measurement or establish a globally optimal model.

## Frozen method and numerical evidence

The [plan](../validation/orn-pn-depression-shape-boundary-plan.json) was frozen before this fit. The trigger was the [original calibration](../validation/orn-pn-depression-calibration-results.json) reaching its engineering ceiling; evaluation-curve performance did not select the new search. Only the same nine noninitial 20 Hz raster means enter the unweighted objective:

\[
y_n=b+(1-b)q^n,\qquad b,q\in[0,1],\quad n=1,\ldots,9.
\]

Twenty-five fixed starts all converged, with SSE spanning 179.25692182005457–179.25692182005525. An independent parameterization of the same objective solves the clipped least-squares value of `b` analytically for each fixed `q`, scans 4,001 `q` values, and refines every detected local basin plus the endpoints. Its best SSE differs by only `2.27e−13`. The selected least-squares run stopped on the declared function-tolerance criterion; the finite searches do not constitute a formal global-optimality proof.

For inversion, the unchanged schedule starts fully recovered, emits 28 baseline events at `−4+j/7 s`, then test events at `n/r s` through the half-open 500 ms test window. The first test event is at zero, one seventh of a second after the last baseline event. Define

\[
A_r=\frac{1-e^{-1/(r\tau)}}{1-f e^{-1/(r\tau)}},\quad
q_7=f e^{-1/(7\tau)},\quad
a_0=A_7+(1-A_7)q_7^{28}.
\]

The inverse uses `f=q exp(1/(20τ))`, `τ≥−1/(20 ln q)`, and `b=A20/a0`. The 4,097-point log-time scan covered **0.2343935971 to 10¹² s**, after applying the physical `f≤1` constraint to the frozen engineering range `[10⁻⁶,10¹²] s`. Sampled `b(τ)` was strictly decreasing and had one sign-changing bracket; Brent refinement found the root above. Recovered `b` differs by `−3.33e−16` and recovered `q` is equal at stored precision. This is one detected root in a bounded sampled search; closely spaced or tangent roots outside that evidence are not formally excluded.

An explicit event-by-event recovery/read/decrement loop, including all 28 baseline events, independently agrees with the mapped development curve within `3.33e−16` normalized-amplitude units. It reproduces the development SSE within `2.56e−13`. The model's first-test efficacy is 0.00959443085 relative to its own fully recovered amplitude; this is an internal state, not an absolute current or measured efficacy. Ninety-five manufactured preflight cases had already checked the shape/recurrence identities, limiting parameter values and analytic profile arithmetic before plan creation. The first experimental-data execution passed without a correction or rerun.

## Fixed-parameter evaluation and limits

After the single-root and recurrence gates passed, the mapped parameters were used once at 15 and 50 Hz. No parameter was selected or changed using those curves.

| Curve | Role / resolved means | Original bounded-fit RMSE | Shape-mapped RMSE |
| --- | --- | ---: | ---: |
| 15 Hz | Evaluation / 7 | 12.167649 | 12.388133 |
| 20 Hz | Development / 9 | 4.465954 | 4.462895 |
| 50 Hz | Evaluation / 24 | 21.195403 | 21.171654 |

All RMSE values are percentage points. The mapped curve underestimates the 15 Hz means on average and overestimates the 50 Hz means on average; extending the recovery search does not resolve that discrepancy. Those curves were previously inspected and are not unseen independent-animal tests.

The primary first-amplitude denominator, exact stimulus phase and preprocessing correspondence remain conditional. Shared-cell and normalization dependence, graphical uncertainty and biological SEM are distinct; no weights, confidence intervals or biological acceptance thresholds were introduced. Effective normalized shape and an invertible assumed schedule do not identify physiological release probability, recovery kinetics or absolute gain. Female VM2 is not a male VM7d calibration. There were no neural, graph, body or runtime changes and no additional figure or promotion claim.

## Retained artifacts

[The new script](../scripts/check_orn_pn_depression_shape_boundary.py) and [results](../validation/orn-pn-depression-shape-boundary-results.json) retain every optimizer outcome, inversion bracket and mapping status. [Arrays](../validation/orn-pn-depression-shape-boundary-arrays.npz) retain the complete shape profile and inverse scan; [predictions](../validation/orn-pn-depression-shape-boundary-predictions.csv) retain fixed-parameter development/evaluation values, including the excluded initial means. All original calibration artifacts were hash-checked before and after execution and remain unchanged.

The [independent review](../validation/orn-pn-depression-shape-boundary-independent-review.json) passes 274 checks: 25 saved optimizer endpoints, four retained profile candidates, all 4,001 analytic-profile points, all 4,097 inverse states, and all 43 mapped predictions. It uses a separate high-precision recurrence without rerunning optimizers or root search. Maximum profile SSE discrepancy is `3.64e−12` percentage-points squared and maximum mapped-curve discrepancy is `2.85e−14` percentage points. The [source-history addendum](orn-pn-depression-conditioning-history.md) also confirms that the paper does not establish complete recovery before each conditioning train.

| Artifact | SHA-256 |
| --- | --- |
| Script | `f622c9b6adb01a0908ad395e5e3a385de71c434dba713414deb6988543500334` |
| Plan | `42fc9a1c9d57f2596de8bf98412ddbc9bee5ac8e8ee92ae731e9ab210c80f2f4` |
| Results | `27af79e33d31783b65646b8351a7d14a0f10b6cc74d4a4e06ed9c06fedfe00ac` |
| Arrays | `80e67c18e8cdd2093aa8a385030ab309f68304af94920a5e758017ef50d07ca5` |
| Predictions | `f632197db5bd0aeefce1a25a6b55bb3974ee742f5a8f3ad60d9e3bcc712861a5` |
