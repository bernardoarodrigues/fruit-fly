# Positive passive modes: complete comparison

Completed 2026-09-06 UTC. This follows the [window-sensitive single-exponential comparison](41-apl-passive-transient-comparison.md). A constrained positive fast/slow response predicts current switch-off more accurately than a single-component control in almost every file. It can now serve as the **conditional passive basis for the next local active-recovery comparison**, while retaining all window variants. It is not promoted to the neural runtime or assigned to specific channels/compartments.

## Model and fixed comparison

The [plan](../validation/apl-passive-modes-plan.json), SHA-256 `4216d1c2d7760e26f24c44ed32eb1c7279b895d6b4796f9318a2e846042594c3`, fixes all 82 source mean traces, four onset windows and both model families: **656 fits**, with 328 paired comparisons. The same 1–50, 5–50, 1–100 and 5–100 ms windows are retained. Neither offset error nor a favorable fitted trace chooses a window or parameter bound. Offset traces were seen in earlier work, so this is diagnostic conditional prediction, not blind evaluation.

For one relaxation time τ, the unit-current-step response is `1 - exp(-t/τ)`. Each basis is divided by its **exact sampled mean** on the source plateau window (0.4–0.5 s, 1,000 samples at 10 kHz). A positive mixture with plateau fraction α in [0,1] therefore shares the measured held baseline and late plateau amplitude by construction:

`V_on(t) = V_base + deltaV * [alpha * h_fast(t) + (1-alpha) * h_slow(t)]`.

The one-component control uses the same conditioning. This differs from the previous free-asymptote/free-amplitude descriptive exponential, making the present comparison between like endpoint assumptions. The measured late plateau is not silently treated as an infinite-time steady state.

For the 500 ms pulse, the unnormalized offset response of each component is `(1-exp(-0.5/τ))*exp(-t_off/τ)`. The same sampled-plateau divisor and mixture weights are applied. No parameters are fit to the switch-off data. Offset scoring remains 5–100 ms, normalized by the measured passive step, with mV errors also retained.

Alpha is the **fraction of late-plateau response**, not a channel conductance or directly the steady-state resistance fraction. The implementation records the corresponding steady-state weight and gain factor separately. All taus remain within the declared 0.5–200 ms bounds. Two-mode fitting profiles alpha, searches the ordered 25-point-per-axis log-tau grid, refines four separated candidates, and includes the single-mode solution as a boundary candidate.

## Complete results

| Onset window | Median offset error, single mode | Median offset error, two modes | Files with lower two-mode offset error | Two-mode tau-bound cases |
|---|---:|---:|---:|---:|
| 1–50 ms | 6.43% | 2.26% | 80/82 | 0 |
| 5–50 ms | 5.92% | 2.12% | 81/82 | 1 |
| 1–100 ms | 6.43% | 1.86% | 80/82 | 0 |
| 5–100 ms | 5.91% | 1.74% | 81/82 | 2 |

Percentages are RMSE divided by the measured passive voltage step. These are descriptive file medians across heterogeneous experiments, states and before/after-drug records. They do not treat files or repeated sweeps as independent animals. All failures to improve are retained. The improvement is on a separately scored portion of the trace, rather than merely the onset objective where the extra component is guaranteed to be at least as flexible.

Component values remain sensitive to the fitting window:

| Window | Median fast tau | Median slow tau | Median fast plateau fraction |
|---|---:|---:|---:|
| 1–50 ms | 1.538 ms | 23.378 ms | 0.646 |
| 5–50 ms | 2.524 ms | 27.467 ms | 0.687 |
| 1–100 ms | 1.868 ms | 30.061 ms | 0.673 |
| 5–100 ms | 3.064 ms | 40.041 ms | 0.727 |

None of the 328 two-mode fits has a near-zero/near-one mixture or effectively coincident taus under the declared diagnostic thresholds. This does **not** establish unique biological identifiability. The fast component may include electrode/access or acquisition effects; the slow component may aggregate cable or active properties. Three window/file cases reach a tau bound and remain flagged. Do not select one row of this table as a global male APL parameter set.

## Independent checks and reproducibility

The [kernel module](../scripts/apl_passive_kernels.py) has two focused numerical tests. One checks the sampled plateau normalization and full finite-pulse response against an independently integrated two-state ODE. The other recovers a constructed positive mixture from onset only and predicts its offset response. Both pass. Their constructed values are test inputs, not selected fly parameters.

The [independent review](../validation/apl-passive-modes-review.json) fits every one of the **328 two-mode cases** using direct three-parameter nonlinear least squares from three fixed starts, with explicitly averaged sample-by-sample plateau factors. This differs from the producer's profiled weight, geometric-series normalization, grid and simplex refinement. The maximum difference in normalized fitting MSE is **2.36 × 10⁻¹⁵**. All **1,312** recomputed objective/prediction checks pass for both model families. Agreement verifies the numerical objective, not uniqueness of component parameters or source biological validity.

The [full results](../validation/apl-passive-modes-results.json) retain all parameters, boundary/degeneracy flags, optimizer outcomes, onset errors and offset errors. They reference the unchanged full-resolution mean-voltage arrays from the previous batch. The [figure](../validation/apl-passive-modes.png) was rendered and visually inspected; it shows every paired error, every component pair, all per-file window sensitivity and all 82 residual traces for an explicitly labeled display window. The display choice is not a model-selection decision.

## Next active-response step

This closes the initial passive model-family comparison. Carry the matched cell's four passive variants into a complete 2 nA active-recovery comparison, keeping passive parameters fixed and recording unavailable/conflicting cell identities. Establish a time-domain realization with exact state updates so that the response to a finite current pulse is reproducible and stable under timestep subdivision. Then compare a declared slow outward-current component with a passive-only control against the full AHP waveforms, preserving source fly grouping and repeated-sweep variation. Do not add further passive modes simply to chase small residuals.

A successful local active-response candidate still needs source-compatible input history, uncertainty across cells, natural synaptic drive/release mapping, recurrent stability and the original physiological promotion checks. These are ex vivo mated-female somatic recordings used as explicit transfer constraints for the one-male simulation. No H1 promotion, global E/I gain sweep, neural runtime/decoder/body default change or cancelled Eon integration occurred.
