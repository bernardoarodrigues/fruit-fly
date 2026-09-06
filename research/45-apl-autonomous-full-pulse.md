# Autonomous APL pulse and recovery comparison

Completed 2026-09-06 UTC. The [complete current-response measurements](44-apl-complete-input-response.md) motivated an executable model that develops its outward state during stimulation. This batch implements and tests that requirement. It improves large-signal compression, but **neither fitted candidate reproduces the sustained observed AHP**. Neither advances to the neural runtime.

## Fixed experiment and implementation

The [frozen plan](../validation/apl-full-pulse-plan.json), SHA-256 `68d6694cf830aceef17132ff5444ecf8a5163cf03ccd171bcec5e3781743622f`, retains the previous six calibration and five evaluation flies, all 65 dedicated 2 nA repeats, and all four fixed passive variants. Two junction-correction scenarios and two candidate mechanisms give 16 complete fits and 176 cell predictions. All results were produced before their interpretation. These recordings were previously inspected; evaluation is retrospective transfer, not blind validation.

The new [experimental module](../fruitfly/apl_conductance.py) converts the positive two-pole impedance into a soma leak/capacitance coupled to a nonleaking distal capacitance. This is an equivalent electrical realization, not a claim that the fitted modes identify anatomical compartments. The passive impedance is unchanged. With voltage in mV relative to held baseline, conductance in nS, current in pA, capacitance in pF and time in seconds:

```
Cs/1000 * dVs/dt = I - gL*Vs - gC*(Vs-Vd) - g*(Vs-Erel)
Cd/1000 * dVd/dt = gC*(Vs-Vd)
m = max(Vs,0) / (scale + max(Vs,0))
dh/dt = (1-m-h)/tau_h
dz/dt = (m-z)/tau_z
```

The noninactivating candidate uses `g = gf*m + gs*z`; the inactivating candidate uses `g = gf*m*h + gs*z`. Both start from `Vs=Vd=0, h=1, z=0`. No measured pulse-end voltage or post-pulse outward state is supplied. Activation relative to the held baseline is an explicit phenomenological assumption, not a measured voltage-gating curve or calcium concentration. The fast and slow conductances are descriptive components, not identified channels.

The two models share a fast conductance and activation parameters across flies; slow conductance differs between control and RNAi groups. Positive parameters are fitted in log coordinates using two frozen starts, bounds and a maximum of 80 optimizer evaluations per start. The unused inactivation time constant is excluded from the noninactivating fit. Each calibration cell and each of three windows receives equal weight in absolute-voltage mean squared error: pulse +5 to +750 ms from onset, early recovery +5 to +800 ms from offset, and late recovery +800 to +2800 ms. Equal window weights do **not** equalize physiological amplitudes or measurement noise.

All 65 observed repeats and their order are saved. Baseline is subtracted per sweep and the cell mean baseline conditions the reversal conversion. Predictions average ten 10 kHz samples into the same nonoverlapping 1 ms bins as the data. Source-specific baseline and passive fits remain conditional inputs from evaluation flies.

## Reversal and history assumptions

The source methods specify nominal external 3 mM potassium and internal 140 mM potassium gluconate plus 1 mM KCl. An ideal monovalent Nernst calculation at an **assumed 25 °C** supplies one approximate potassium reversal. The two scenarios subtract either 0 or 15.7 mV from raw baseline before computing its distance to reversal. This retains the unresolved ABF correction convention rather than treating the author's corrected workbook values as proof that every raw trace has already been corrected. Temperature, ionic activities, recording compensation and actual reversal are not independently measured here.

The positive compartment circuit and implicit voltage update preserve the reversal lower bound for these nonnegative injected currents, with nonnegative conductances and initial compartment voltages above reversal. This is not a promise that an arbitrary externally imposed negative current can never drive voltage below reversal. Gate updates preserve `[0,1]`.

Each fitted case is propagated through the remaining zero-input gap to the next source pulse at a 60 s onset interval. The maximum difference between that second pulse and an equilibrium-start pulse is `1.85e-13 mV`. Thus neglecting inter-repeat state accumulation is numerically justified for these fitted candidates and this dedicated protocol. It does not establish the same result for the shorter staircase intervals or natural ongoing drive.

## Complete results

All 32 optimizer starts terminate successfully. Every selected fit drives `tau_z` to its **50 ms lower bound**. Every noninactivating fit also reaches the lower bounds for RNAi slow conductance and activation scale. A converged optimization is therefore not evidence that these parameters are physiologically identified.

Mean evaluation-cell RMSE across the eight fixed variants/scenarios per candidate:

| Window | Fixed passive control (mV) | Noninactivating candidate (mV) | Inactivating candidate (mV) |
|---|---:|---:|---:|
| During pulse | 92.22–92.37 | 10.88–10.93 | 10.05–10.08 |
| Early recovery | 5.71–5.83 | 1.81–1.95 | 1.64–1.72 |
| Late recovery | 0.430 | 0.430 | 0.430 |

The large improvement over passive extrapolation demonstrates useful compression. Inactivation also captures some within-pulse rise, but transfer errors remain large in several flies. The apparent recovery improvement over the passive control is insufficient: the fitted outward state decays rapidly while recorded cell means retain a substantially longer AHP. The late-window equality is mostly a return of all predictions to baseline, not successful recovery modeling. The weak RNAi evaluation cell remains in every comparison.

The [complete figure](../validation/apl-full-pulse.png) was rendered and visually inspected. It shows all eleven cells, every observed repeat, both candidate families across all four passive variants and both correction scenarios, and the passive controls. Recovery panels use a declared −8 to +5 mV display range after the first 50 ms; full traces remain in the [saved arrays](../validation/apl-full-pulse-arrays.npz).

## Numerical review and limits

Three targeted tests pass: exact passive impedance equivalence, continuous-ODE convergence with autonomous recovery, and reversal/gate invariance under a wide range of step sizes. These synthetic checks are supplemented by [independent continuous ODE integration](../validation/apl-full-pulse-review.json) for all 176 fitted predictions, using separate equations and an adaptive DOP853 solver. All 1,056 saved RMSE metrics and all 16 calibration objectives recompute exactly at reported precision. All cases respect the reversal bound in the batch and independent integrations.

The maximum whole-trace numerical RMSE is **0.02696 mV**. However, **three of 176 predictions fail the review's 1 mV maximum absolute-error gate** at the 0.1 ms step; the largest discrepancy is **1.08350 mV**. All half-step RMSE checks show the required convergence, but this does not erase the failed maximum-error gate. The immutable batch and review retain the failures. A finer-step or more accurate implementation needs renewed maximum-error verification before promotion or use in a new fitted comparison. The independent review does not independently optimize the model or decode the ABF files.

## Decision and next discriminating work

Keep the passive circuit realization and executable conductance candidate as experimental infrastructure. **Do not promote either fitted parameter set.** The original conditional-recovery model could reproduce slow recovery only after being supplied an outward state at offset; the autonomous candidate now exposes the missing compatibility between stimulation and recovery under one rule.

The shared activation/decay time constant is a candidate limitation, but the fit does not identify it as the unique cause. Absolute-voltage fitting gives the much larger pulse residuals substantial influence even with equal phase weights; heterogeneous cells, the baseline-relative activation rule and missing processes are additional possibilities. Do not respond by expanding bounds, adding arbitrary per-cell gains or selecting the better-looking voltage plot.

The next bounded comparison should separate recruitment and removal kinetics, retain the current models as controls, and declare acceptance for **each phase** before fitting. Use the existing calibration flies to establish those constraints and preserve the evaluation flies. Test transfer to a different current amplitude/protocol with actual staircase history before considering a natural-input replacement. Address the numerical maximum-error failure at the same time; keep this batch unchanged. No channel identity, SK calcium coupling, male parameters, natural KC→APL input or GABA-release rule is established by this experiment.

The source recordings are from mated female ex vivo preparations, so male and intact-animal transfer remain explicit limitations. H1 remains unpromoted; the Eon embodied integration remains cancelled. No default neural model, decoder, body or viewer process changed.
