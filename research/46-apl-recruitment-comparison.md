# APL recruitment versus removal: frozen comparison

Status: complete, 2026-09-06. All 16 fits and 176 predictions were produced before interpretation; the complete figure has been visually reviewed. This follows the rejected [autonomous full-pulse candidates](45-apl-autonomous-full-pulse.md).

## What changes and what is controlled

The new experimental module `fruitfly/apl_recruitment.py` retains the fixed positive passive circuit and fast inactivation. Its slow state is

```
m = max(Vs,0)/(scale + max(Vs,0))
dz/dt = m*(1-z)/tau_on - (1-m)*z/tau_off
```

When the two time constants are equal, this exactly reduces to the previous `(m-z)/tau` law. Unequal times change both the rate and the voltage-dependent equilibrium of this state. Consequently, a better fit would not by itself identify a biological activation or removal process, and conductance amplitude can remain confounded with gating occupancy.

The same six calibration and five evaluation flies, all 65 repeats, all four passive variants and both voltage-correction scenarios are retained. Shared and separate kinetics are refitted under the same objective, producing 16 fits and 176 candidate predictions with passive controls. Two fixed optimizer starts are retained; these are not stochastic biological seeds or a recurrent robustness test.

Each calibration cell and each of three response phases gets equal weight after amplitude normalization. Each phase scale is the RMS of the six calibration cell-mean responses, with a 1 mV floor. This is explicitly **not an estimated noise model**. It prevents the large depolarizing response from dominating the much smaller recovery simply because it has larger voltage units. Both kinetics candidates use these exact same scales, so their comparison does not confound the kinetics change with a change of objective.

The [frozen plan](../validation/apl-recruitment-plan.json), SHA-256 `238478f24d6a8733a2ebb94e87c91b316c7e6ee80a96030b0318bc7f2d4816f4`, contains source hashes, bounds, starts, phase scales and acceptance criteria. Normalized phase RMSE cutoffs are 0.25 during the pulse, 0.5 during early recovery and 1.0 during late recovery. At least four of five evaluation flies must pass all three. These are declared engineering screening criteria, not published physiological tolerances. Source waveforms have already been inspected, so this remains retrospective conditional transfer.

## Numerical change

The original first-order module and its failed numerical checks remain unchanged. The new integrator predicts a midpoint state, then applies exact constant-conductance compartment voltage evolution and exact frozen-activation gate evolution using that midpoint. Positive conductances and gates preserve the reversal bound under the stated nonnegative current injections. Initial voltage and gates remain equilibrium states; no measured post-pulse state is inserted.

Integration uses 50 microsecond steps. Observations always use the original 10 kHz sample times, averaging ten samples into 1 ms bins. Halving the integration step therefore leaves the observation clock unchanged. This corrects a limitation of the previous refinement comparison, which averaged a different set of within-bin times at each step size.

Three targeted tests pass: exact nesting of shared kinetics, convergence to an independently integrated continuous ODE on the same observation clock, and voltage/gate bounds with zero-input relaxation. These tests are supplemented by independent reviews of every fitted prediction against continuous ODE integration and a 25 microsecond step, using maximum error ≤1 mV, RMSE ≤0.2 mV and the unchanged declared refinement criterion. The reference-precision issue found during that review is recorded below.

Each fitted case also propagates through the remaining 60 s source inter-pulse interval and a second pulse. This tests the reset approximation for this protocol; shorter staircase history remains a separate required transfer test.

## Execution and follow-up

The first launch failed at the repeat-history call with a duplicate `dt` argument. No complete result or partial fit interpretation was produced. Its frozen plan, script and failure receipt are preserved as `validation/apl-recruitment-aborted-*`. The call signatures were corrected without changing experimental methods and the plan was refrozen before relaunch.

The producer completed all 16 fits and 176 predictions. Its process identity is retained in `validation/apl-recruitment-launch.json`; it is now terminal. The completion heartbeat is paused. Frozen source/script pins, result counts and arrays hashes were verified before analysis. The complete [figure](../validation/apl-recruitment.png) shows all eleven cells, all repeats and all model variants; no best-looking case was selected.

## Complete findings

The fixed calibration-only amplitude scales were **62.673 mV** during the pulse, **2.377 mV** in early recovery and **1.000 mV** in late recovery. With the phase-scaled objective, **even shared kinetics now produces a slow recovery**: fitted shared time constants are approximately 0.714–0.799 s, instead of the 0.050 s lower-bound solutions from the absolute-voltage objective. Therefore, reproducing that qualitative slow response does not require separate recruitment/removal time constants. Numerical error is far too small to explain this change in the fitted waveform, though the integrator also changed between experiments.

Across all four passive variants and both correction scenarios:

| Evaluation metric | Shared kinetics | Separate kinetics |
|---|---:|---:|
| Mean-cell pulse RMSE | 8.51–9.73 mV | 8.74–9.92 mV |
| Mean-cell early-recovery RMSE | 0.872–0.926 mV | 0.854–0.914 mV |
| Mean-cell late-recovery RMSE | 0.296–0.298 mV | 0.296–0.297 mV |
| Evaluation flies passing all phase criteria | 3/5 in all eight cases | 4/5 in four cases; 3/5 in four cases |

Separate kinetics lowers the calibration objective by only **0.51–0.99%** relative to the nested shared-kinetics candidate. Its early-recovery improvement comes with a slightly worse mean pulse error. Every separate-kinetics fit reaches the **10 ms recruitment lower bound**; six of eight also approach the activation-scale upper bound. Four shared-kinetics fits approach that same scale bound. These observations constrain identifiability and do not support a claim that recruitment kinetics or channel density have been measured.

The weak RNAi evaluation cell `250522f01c01R` fails the pulse criterion in every model variant. Shared kinetics also fails its early-recovery criterion. Control evaluation cell `250612f03c01R` fails early recovery in all shared-kinetics cases and four separate-kinetics cases. Thus the extra mechanism's pass/fail advantage depends on the passive-window variant; it is not robust across the retained uncertainty family.

All sixteen selected fits report optimizer convergence. **31 of 32 starts** converge; the second start for fit 13 reaches the 100-evaluation cap and is retained as a failed optimizer attempt. The maximum relative objective difference between starts is about `7.75e-6`. That agreement is evidence about this deterministic optimizer, not stochastic biological-seed robustness or proof of a unique parameter solution.

Every candidate respects the compartment reversal bound. The maximum second-pulse difference after propagating the actual 60 s interval is **6.68e-13 mV**, supporting negligible inter-repeat memory for these fitted dedicated-pulse cases only.

## Numerical diagnosis without changing the acceptance criteria

The [first full independent review](../validation/apl-recruitment-review.json) recomputes all 1,056 phase RMSE values and sixteen objectives. Its absolute errors are small: maximum whole-trace RMSE `3.23e-5 mV` and maximum absolute difference `0.001359 mV`. All absolute-error gates pass. However, nineteen cases fail the declared step-halving ratio criterion.

A separately [frozen diagnosis](../validation/apl-recruitment-refinement-plan.json) includes all nineteen failures plus the maximum-error and first-passing reference cases, deduplicated to twenty cases. It tightens DOP853 tolerances from relative `2e-9` / absolute `2e-10` to `2e-12` / `2e-13` and checks 50, 25, 12.5 and 6.25 microsecond steps on the identical original observation clock. No parameters, scientific criteria or fitted outputs change.

The [diagnostic results](../validation/apl-recruitment-refinement.json) identify reference-error contamination: tightening the reference shifts its waveform by up to `4.93e-6 mV` RMS, comparable to the integrator errors in the flagged cases. **All nineteen original failures satisfy the original ratio criterion against the tighter reference.** Across the diagnostic panel, maximum RMSE falls from `3.23e-5` to `7.79e-6`, `1.91e-6` and `4.74e-7 mV` as the step is halved. Final error ratios are 0.2478–0.2503, consistent with second-order convergence. This resolves a reference-precision problem rather than relaxing a failed criterion. Both the original failed review and the diagnostic evidence remain immutable.

The [complete tighter-reference review](../validation/apl-recruitment-tight-review.json) then repeats the unchanged numerical and phase checks for **all 176 predictions**. Every numerical gate passes; maximum absolute error is **0.001359 mV**, maximum RMSE is **0.00003233 mV**, and all 1,056 phase metrics and sixteen objectives agree. This broader repeat was necessary because the original reference precision was insufficient for a subset of cases. It does not change the failed physiological phase screens or identify a biological mechanism.

## Decision

Neither family is promoted to the neural runtime. The useful advance is an autonomous, bounded electrical model that can produce compression, within-pulse rise and slow recovery simultaneously, with an explicit assessment of where transfer fails. The results also show that objective scaling materially matters when fitting responses whose amplitudes differ by orders of magnitude; adding state variables should not be the automatic response to a poorly balanced objective.

The next discriminating experiment is **different-current/protocol transfer without refitting**, retaining both families and all uncertainty variants. Use the matched staircase recordings with their preceding negative test pulse and actual inter-sweep history. Do not keep adding mechanisms or adjusting phase thresholds to make this 2 nA batch pass. Natural KC input, GABA release, male transfer and recurrent validation remain separate requirements. No H1, decoder, body or viewer changes were made, and Eon integration remains cancelled.
