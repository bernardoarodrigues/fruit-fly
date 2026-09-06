# APL recruitment versus removal: frozen comparison

Status: running, 2026-09-06. No fit results have been interpreted. This follows the rejected [autonomous full-pulse candidates](45-apl-autonomous-full-pulse.md).

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

Three targeted tests pass: exact nesting of shared kinetics, convergence to an independently integrated continuous ODE on the same observation clock, and voltage/gate bounds with zero-input relaxation. These tests do not replace the pending review of actual fitted predictions. That review will check every prediction against continuous ODE integration and a 25 microsecond step, using maximum error ≤1 mV, RMSE ≤0.2 mV and the declared refinement criterion.

Each fitted case also propagates through the remaining 60 s source inter-pulse interval and a second pulse. This tests the reset approximation for this protocol; shorter staircase history remains a separate required transfer test.

## Execution and follow-up

The first launch failed at the repeat-history call with a duplicate `dt` argument. No complete result or partial fit interpretation was produced. Its frozen plan, script and failure receipt are preserved as `validation/apl-recruitment-aborted-*`. The call signatures were corrected without changing experimental methods and the plan was refrozen before relaunch.

The active producer is `.venv/bin/python scripts/compare_apl_recruitment.py`; its process identity and expected outputs are recorded in `validation/apl-recruitment-launch.json`. Wait for all results before interpretation. Then run:

```
PYTHONPATH=. .venv/bin/python scripts/review_apl_recruitment.py
.venv/bin/python scripts/plot_apl_recruitment.py
```

Verify the complete 16-fit/176-case result, original pins and arrays hashes before analysis. Preserve all failed phase or numerical checks and optimizer-start disagreements. Visually inspect the complete figure; update this note and the project status with findings, then commit and push the reviewed artifacts. A better fit or a passing local screen does not authorize runtime promotion: different-amplitude/protocol transfer, natural KC input, GABA release, male transfer and recurrent validation remain open. Do not modify H1, decoder or body defaults or revive Eon integration.
