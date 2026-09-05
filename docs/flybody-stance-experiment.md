# Source-native engineering posture holds

**Holding measured actuator positions or commanding the source neutral pose passes this fixed stop/resume experiment. Holding the last commanded targets fails on resumption.** No runtime adapter was promoted, and no neural controller, learned weight, body parameter or source gain changed.

This is a bounded follow-up to the [unchanged policy comparison](flybody-motor-comparison.md). That policy still fails its original stopping criteria. The new positive result applies to an explicitly added **engineering posture hold**, using the author's native actuators. It is not evidence of biological stance control or a correction to the earlier failed result.

## Actuator audit before trials

The [initialization-only audit](../validation/flybody-stance-actuator-audit.json) was saved before the plan and before any hold trial. It verifies the actual compiled model against the pinned author source and exact action-spec order. All 53 non-adhesion controls use fixed positive gain and affine position bias:

```text
actuator output = gain × (filtered native target − actuator transmission length)
```

The bias velocity coefficient is zero; passive joint damping and stiffness remain present. Source gains are 0.1, 0.4 or 0.8, depending on actuator. Forty-five channels actuate joints and eight actuate fixed tendons: two abdomen channels and six `tarsus2` channels. Their measured target must therefore be `physics.data.actuator_length` in source action order, rather than a guessed correspondence to individual `qpos` columns. Every native position range admits zero. At the source reset, all 53 native position controls and their measured transmission lengths are exactly zero.

The [source actuator definitions](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/assets/fruitfly.xml) and [action-order conversion](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/fruitfly.py) establish this interface. The [audit script](../scripts/audit_flybody_stance_actuators.py) reproduced the saved audit byte for byte after the experiment. Gain/bias/transmission checks also run before every trial.

This source already has position actuators, but it does not supply the tested transition adapter below. The original paper includes standing still in its walking data; it does not establish that these hand-designed holds are neural or biological mechanisms. [Primary FlyBody paper](https://www.nature.com/articles/s41586-025-09029-4).

## Predeclared grid

The [plan](../validation/flybody-stance-plan.json), SHA256 `0708e313180371593699c54d7ed3f8c898406b1743ee5a9e492891cdd53b92c7`, was written before any trial and remains unchanged. It freezes the source audit, implementation, old comparison, metrics code, policy assets, source manifest and dependency lock.

There are four variants × three 2 s assays = **12 trials**. Seed 11 is used once per condition. Previous seeds 11 and 12 produced identical deterministic mean-policy physics, so this experiment does not treat repeated seed labels as independent initial conditions.

| Variant | Gate off: native position targets | Gate off: six adhesion targets |
|---|---|---|
| `policy_zero` | Unchanged learned policy, given zero-speed reference | Unchanged learned policy |
| `last_target` | Latch the last applied native target vector | Fixed native 1 |
| `measured_length` | Latch actual actuator transmission lengths | Fixed native 1 |
| `neutral_zero` | All 53 native position targets zero | Fixed native 1 |

The three holds clip their captured target once to the source native control bounds and retain that diagnostic. At zero-start, the last target and measured length are both zero, making all three hold variants structurally identical controls. This expected identity is not three independent demonstrations of different standing mechanisms.

Native adhesion 1 is the source's maximum command, with original gain 0.985, 7 ms filter and friction retained. Applying it to all six claws is a declared engineering choice. It does not imply every claw contacts the ground, and it is not a measured neural adhesion law. No gain, filter time, damping, stiffness, contact solver or actuator force limit was fitted or changed.

| Assay | Motor gate | Stop metric window | Resume metric window |
|---|---|---|---|
| `zero_start` | Off for 0–2 s | 0.3–2 s | — |
| `walk_stop` | On 0–0.6 s, then off | 0.85–2 s | — |
| `walk_stop_resume` | On 0–0.6 s, off 0.6–1.2 s, then on | 0.85–1.2 s | 1.5–2 s |

The desired on-speed is always 20 mm/s, yaw zero. Gate off suppresses locomotor-policy output **while retaining posture actuation** in the three engineering variants; it is not a force-free body. The frozen policy is evaluated in the background for diagnostics, but its proposed action has no effect during a hold. The `policy_zero` baseline instead keeps the actor controlling posture under a zero-speed reference.

At resumption, the hold latch is released and the exact original clipped/scaled mean-policy action takes over immediately. No transition blend, target recentering, physical reset, body-position clamp or velocity clamp is used. The only body writes after ordinary source initialization are native actuator commands passed through the original environment. The original 0.2 ms physics step, 2 ms control step, 10 ms position filter, 7 ms adhesion filter and body sensors remain unchanged.

An 1,100-frame root-reference buffer supports the full trial and 64-step future context. At each policy tick, the current gate/speed is extrapolated over the same 128 ms preview. Off/on edges are never exposed early; the integrated target pose remains continuous. There are no food coordinates, source leg recordings or new environmental observations in this adapter.

## Fixed criteria

The original physical and stopping criteria are preserved: after the initial 0.3 s, all states must remain finite, warnings must remain zero, upright z must stay ≥0.5, root height ≥0.5 mm, and no more than 1% of sampled frames may lack positive leg-floor support. Every declared stop window requires **median unsmoothed root speed≤1 mm/s and net planar displacement≤0.5 mm**.

Resumption additionally requires median speed 16–24 mm/s in its fixed window and median absolute yaw≤55.333°/s. The yaw ceiling was declared as `1.2 × frozen FlyBody straight20 yaw + 10°/s`. It is an engineering guard against a large new heading disturbance, not a biological threshold. The body must also satisfy the physical gates through the transition. Any source early termination fails the trial. Hold actions must exactly match the captured/clipped position targets and fixed adhesion during every gate-off step.

A variant passes only if all its assays, stop windows, physical gates, motor-mute checks and resume checks pass. The unchanged policy is a control, not a candidate. Passing supports review of an optional adapter; it does not cause automatic runtime integration.

## Outcomes

The [full result](../validation/flybody-stance-experiment.json), [validation receipt](../validation/flybody-stance-validation.json) and [figure](../validation/flybody-stance-experiment.png) preserve every trial, including the terminated one.

| Variant | Zero-start speed | After-walk stop speed | Resumed speed | Resumed absolute yaw | Declared result |
|---|---:|---:|---:|---:|---|
| Original policy zero | 1.696 mm/s | 1.874 mm/s | 19.90 mm/s | 35.45°/s | Fails stopping |
| Last targets | 0.000212 mm/s | 0.003541 mm/s | Terminated | — | Fails resumption |
| Measured length | 0.000212 mm/s | 0.003307 mm/s | 20.57 mm/s | 35.40°/s | Passes this grid |
| Neutral zero | 0.000212 mm/s | 0.003197 mm/s | 19.71 mm/s | 29.34°/s | Passes this grid |

Values are median instantaneous root speeds in the declared windows. The after-walk stop column uses `walk_stop` at 0.85–2 s. In the shorter stop window before resumption, measured-length and neutral-zero medians are similarly small: 0.003763 and 0.003244 mm/s. Their p95 speeds are 0.010953 and 0.003452 mm/s. Neither success depends on changing the speed smoothing rule.

The zero-start holds have net displacement **0.000310 mm**. In `walk_stop`, measured-length/neutral-zero net displacements are **0.000485/0.003697 mm**; before resumption they are 0.000454/0.001145 mm. These are generated simulator coordinates, not experimentally measured resolution or biological immobility.

All 11 completed trials have finite retained states, zero MuJoCo warnings and no sampled loss of all leg support. Across successful candidates, the lowest upright z is **0.9852**, and the lowest root height is **1.2786 mm**. The last-target-only stop also passes the broad physical gate but rests in a visibly more tilted posture, with minimum upright z 0.7801. The failure on resumption is retained separately and is not counted as a warning-free completed trial.

The source neutral hold returns the body toward zero-angle geometry. The measured-length hold captures the current actual posture, which differs materially from the actor's position targets: at the tested stop edge, the largest target change is about 3.007 native units, including head/tendon coordinates. This is a commanded equilibrium change filtered by the original actuator dynamics, not a teleport of a joint or body. The last-target capture changes only one boundary value by 1.19×10⁻⁷ native units because of float32 range-rounding; that correction is recorded, not a fitted parameter.

### Contacts and retained gait limitations

All six legs support the zero-start hold. After walking, measured-length hold has continuous support from **LF, LH, RM and RH**, while LM and RF remain off the floor. Neutral-zero hold has **five** continuously supported legs, with RH off the floor. There are **zero sampled contact onsets/offsets** in these fixed stop windows. Thus the quiet result is a static engineering posture with four or five supporting legs, not a demonstrated natural six-legged resting pose.

The unchanged zero-reference policy still shows its previously identified contact chatter/local motion. Its new zero-start window has five continuously supported legs plus 138 brief LF contact onsets over 1.7 s. After walking, five legs remain supported, with LF off the floor. The different posture is source-policy behavior at this particular withdrawal phase; no stance-foot selection was imposed on it.

On resumption, measured-length and neutral-zero LF cycle frequencies are **15.39/15.63 Hz**, with LF tibia ROM **34.80/34.69°**. Those preserve the earlier high-cadence/small-excursion limitation relative to the mixed-sex freewalking reference near 20 mm/s (about 10.90 Hz and 61.90°). Solving this specific stopping criterion does not solve the gait mismatch. The resumed contacts and cycle summaries are retained for all six legs.

The zero-start hold's mean summed absolute vertical leg-floor force is **7.12 times body weight**, consistent with the added maximum adhesion commands. Successful walking/hold/resume trials average approximately 4.79–5.82 times weight over their analyzed windows. These contact magnitudes include artificial adhesion and are not biological force-validation targets. The experiment changes both position-target selection and adhesion commands during holds, so it does not isolate policy action variability from adhesion variability as the cause of the original residual motion.

### Preserved last-target failure

The last-target resume case terminates after **613 control steps, at 1.226 s**, shortly after the gate reopens. The retained [post hoc failure diagnostic](../validation/flybody-stance-failure-diagnostic.json) reconstructs the source's current target from the continuous preview. Its root-reference error is **0.31140 cm (3.114 mm)**, exceeding the source's **0.3 cm** termination distance. The final root linear/angular speeds, 4.969 cm/s and 24.962 rad/s, remain below the separate source limits 50 cm/s and 200 rad/s. Final upright z is 0.6878. The arrays remain finite.

Reference-distance failure is sufficient to explain the termination. `qacc` was not retained, so the diagnostic does not exclude another simultaneous source threshold. The short trajectory is preserved; it was not extended by disabling termination, resetting the target or altering gains. [Source termination implementation](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/walk_imitation.py), [source constants](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/constants.py).

This negative result distinguishes a latched commanded target from a latched measured position. The original actor's target can differ substantially from the current actuated position, and maintaining it can allow the body to settle into a posture from which the frozen actor does not recover in this assay. It does not establish that every last-target hold must fail, or that the successful choices work at all gait phases.

## Verification and recommendation

The [checker](../scripts/check_flybody_stance.py) verifies all 12 unique grid entries and retained hashes, then checks 1,001 physical frames and 1,000 actions in each complete trial, exact gate times, continuous reference integration, the original action transform whenever the policy is active, exact latched hold actions whenever muted, and reproduction of primary window metrics and decisions. Its detailed per-trial loop skips the shorter failed trace after preserving it; the independent review below closes that gap.

It also provides stronger causality checks: the new control's original physical prefixes match the earlier frozen comparison **bitwise**; all variants have identical physical prefixes before the stop edge; and each stop-only and stop/resume pair remains bitwise identical until the resume edge at 1.2 s. The differing future schedule therefore did not leak into the policy preview. The source gain audit was independently reproduced byte for byte. The PNG figure was inspected; its displayed 11-sample median speed filter is explicitly cosmetic and never used in the gates.

A separate [independent review](flybody-stance-independent-review.md) verifies commands, latches, filtered actuator state and all 53 joint/tendon coordinate reconstructions across **all 12 traces, including the failed partial trajectory**. It reconstructs the source Euler activation filter with compiled control clipping to maximum error 1.78×10⁻¹⁵. Its [receipt](../validation/flybody-stance-independent-review.json) leaves every decision unchanged. Raw `actuator_force` in the trace belongs to the preceding force stage, whereas recorded post-step actuator lengths/activation are current; do not combine those arrays as simultaneous torque/position measurements. The separate contact diagnostic uses a detached `mj_forward` and is current-state force evidence. No physics was rerun for that review.

```sh
# Initializes the source model only; no hold rollout.
tmp/flybody-env/bin/python -m scripts.audit_flybody_stance_actuators

# Existing plan is immutable; --plan-only refuses overwrite.
tmp/flybody-env/bin/python -m scripts.experiment_flybody_stance --run
tmp/flybody-env/bin/python -m scripts.check_flybody_stance
tmp/flybody-env/bin/python -m scripts.plot_flybody_stance
```

Timed integration totals **78.20 wall seconds for 23.226 simulated seconds**, including shadow-policy inference and detached-state force diagnostics, excluding environment construction/imports. The same isolated CPU environment and frozen asset licenses from the [inference trial](flybody-inference-trial.md) apply. No raw source behavioral recordings were redistributed.

**Retain measured-length and neutral-zero holds as reviewed experiment candidates, without automatic promotion.** They demonstrate that this source body and its unchanged gains can produce a quiet physical posture and resume the original walking policy at the tested stop phase. The last-target candidate fails and should not be promoted from this result.

The scope is one forward speed, one flat surface, one deterministic initial state and one stop phase (0.6 s). It does not establish reliable stops throughout the gait cycle, turning-to-stop transitions, slopes, perturbations, sensory-triggered decisions, full-neural timing or male anatomy. Any optional integration should preserve the explicit locomotor-policy mute/posture-hold distinction and retain these constraints; no such runtime integration occurred in this experiment.
