# KC reporter inhibition across timesteps

2026-09-05 UTC. This completes one fixed scalar numerical batch after the [author-code audit](27-kc-reporter-data-and-author-model-audit.md). It supplies an isolated reference for future local model work. It does not fit experimental data, run a neural network, or install an electrical mechanism.

## Result and interpretation

All **45 declared cases and 362 checks pass**. The largest difference among direct discrete recurrence, its independently summed affine-map solution, an exact continuous embedding, refined stepping, and an adaptive DOP853 solution is **6.751 × 10⁻¹³ arbitrary state units**, below the frozen absolute tolerance of 10⁻⁹. The [plan](../validation/kc-reporter-inhibition-reference-plan.json), [results](../validation/kc-reporter-inhibition-reference-results.json), [reference implementation](../scripts/kc_reporter_inhibition_reference.py), and [batch checker](../scripts/check_kc_reporter_inhibition_reference.py) are retained.

The author recurrence applies modulation to old inhibitory memory as well as new drive. At the **initial, unfitted** author parameters `tauinh=1.5 s`, sigmoid inflection 0.5 and slope factor 0.03, a fixed calcium proxy of 0.5 gives modulation m=0.5. Its inhibitory equilibrium per unit drive is 0.0217391 at 30 Hz but 0.0000666622 with a naive 0.1 ms substitution: about **326 times smaller**. Its effective memory-decay time changes from 46.58 ms to 0.1443 ms. These are mathematical consequences under fixed inputs, not measured receptor kinetics or fitted effect sizes.

This sharpens the previous finding: the parameter called `tauinh` is not by itself the actual memory time constant when the entire memory state is gated every step. A visually plausible calcium fit at one integration rate cannot establish compatibility with the faster CNS engine.

## Reference construction

For constant modulation m and lateral drive D, the audited equation is

`I_next = q*I + b`, where `q=m*(1-h/tau)` and `b=m*h*D/tau`.

Here h is the **fixed reference step**. For `0<m<=1` and `0<h<tau`, a scalar continuous embedding can reproduce this affine map exactly at every reference boundary:

`dI/dt = k*(I_equilibrium-I)`, with `k=-log(q)/h` and `I_equilibrium=b/(1-q)`.

Its exact held-input solution can then be advanced at smaller intervals without changing the reference map. The implementation uses `log1p`/`expm1` to retain accuracy near weak decay. This is an explicit mathematical embedding of the existing discrete model; it is **not** evidence that the receptor follows this differential equation.

At m=0, the source recurrence erases arbitrary memory in one step. No finite-rate scalar continuous embedding implements that instantaneous deletion. The reference rejects that embedding request explicitly, while separately checking that the discrete source step returns zero. Likewise, `h>=tau` lies outside the declared positive-map embedding domain and is rejected. These domain limits must remain visible if a later fit explores the author's broad parameter bounds.

The batch holds C/m and D constant. It tests three tau values (0.05, 0.2 and 1.5 s), five modulation values (0.001, 0.1, 0.5, 0.9 and 1), and three initial-state/drive pairs. Each runs 30 reference intervals at 1/30 s, with subdivisions 2, 10 and 333. The ODE reference independently forms the affine-map coefficients and uses rtol 10⁻¹¹ and atol 10⁻¹³. The 333 subdivision is h/333, not exactly 0.1 ms; the separate naive-step illustration evaluates exactly 0.1 ms analytically. All outcomes were reduced together after the complete scalar batch.

No claim is made about varying-input convergence, nonlinear coupled calcium/adaptation dynamics, clipped calcium, noise, whole-population dynamics or physiology. Those require their own explicit comparison if this reference is used later. The author modules were not executed. The original source files are hash-pinned in the plan.

## Source-data access and next work

The exact primary-cohort join for the four-column author export remains unresolved. The [acquisition follow-up receipt](../validation/kc-reporter-source-access.json) preserves these distinct outcomes:

- Europe PMC's documented supplementary-files endpoint returns XML saying this manuscript is not in its open-access set; it supplies no ZIP.
- Two OA utility endpoint attempts return HTML error pages, not usable package metadata.
- The primary PMC article is readable in Chrome, but clicking its Data S1 workbook link gives `ERR_BLOCKED_BY_CLIENT`.
- The [publisher article](https://www.sciencedirect.com/science/article/pii/S0960982222014518) requires a human CAPTCHA in Chrome. The page is retained for user handoff; no CAPTCHA was solved or bypassed.

The required file is Data S1, `NIHMS1837499-supplement-1.xlsx`, linked from the [primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC9613607/). Table S1 would additionally resolve statistical metadata. An institutional paywall has not been established. A human-verification request was sent while this independent numerical work continued.

Next, when source access is available, match the exported WT/KD curves against the original workbook using all samples and explicit sheet/column identities; recover normalization, cohort, time and error conventions before selecting calibration/evaluation data. The graded APL and electrical observation mappings remain open and can be researched independently of this access gap. No candidate is promoted. The full single-male plan remains active, with the Eon body benchmark cancelled and no new whole-network E/I sweep.
