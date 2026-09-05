# Independent review of the fixed FlyBody stance experiment

The frozen traces support the reported engineering result: **`measured_length` and `neutral_zero` pass this grid; `last_target` fails resumption; the unchanged zero-reference policy fails stopping.** No source actuator mapping, latch ordering, preview timing or decision error was found. This is not validation of biological stance or reliability across gait phases.

The reproducible [review script](../scripts/review_flybody_stance.py) and [receipt](../validation/flybody-stance-independent-review.json) preserve the reviewed source, plan, scripts, results, figure and trace hashes. The review used the pinned source commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26` in its isolated MuJoCo 3.2.7 environment. It constructed/reset one source environment at time zero to read compiled parameters, then checked the saved arrays. **No physics trajectory, policy inference, training, parameter fit or runtime integration was performed.** The experiment, its checker and numerical metric helpers were not imported by this review.

```sh
tmp/flybody-env/bin/python -m scripts.review_flybody_stance
```

## Actuators, filtering and command causality

The exact action order is six adhesion controls followed by 53 position controls, mapping to compiled actuator IDs `[53…58, 0…52]`. The position controls comprise **45 joint transmissions and eight fixed tendon transmissions**. Both abdomen tendons sum seven joint angles with coefficients 1. Each of the six `tarsus2` tendons combines four joint angles with coefficients `[1, 0.5, 0.5, 0.5]`. All transmission gears are 1. The receipt records every joint name, `qpos` index and coefficient.

Every saved transmission length, across all 12 traces including the terminated one, agrees **exactly** with an independent reconstruction from saved `qpos` and those compiled coefficients. The source affine law is positive fixed gain times filtered target minus transmission length, with zero velocity-bias coefficient. Capturing actual actuator lengths is therefore the correct coordinate choice for this particular model; a one-angle-per-control shortcut would be wrong for the eight tendon channels. “Measured” here means simulator state, not an empirical fly measurement.

The original model uses Euler integration at 0.2 ms and source `FILTER` activation dynamics: 7 ms time constants for adhesion and 10 ms for position. Ten physics substeps occur per 2 ms action. With the submitted command clamped to the source's compiled native control bounds, the independently computed update is:

```text
a_next = clamp(u) + (a - clamp(u)) × (1 - 0.0002 / tau)^10
```

This agrees with every retained activation transition to **1.78×10⁻¹⁵ native units**. Clamping to the compiled float64 bounds matters at float32 boundary roundoff. No fitted filter or changed gain was needed.

All saved gate arrays match integer action indices: withdrawal at action 300 (0.6 s), resumption at action 600 (1.2 s). Every policy-controlled action matches the original clipped/scaled canonical action exactly. Every engineering gate-off action matches its captured, once-clipped 53-position vector plus six adhesion targets of 1. The failed trial passes these same checks; it was not omitted. All three zero-start hold traces are bitwise identical, as expected from identical zero initial targets and lengths.

Reference positions advance by 0.004 cm per enabled control interval and remain fixed during withdrawal. Source inspection confirms the current-only 65-frame/128 ms preview, preserved target origin and immediate latch release. The full `qpos` prefixes are bitwise identical across variants before withdrawal and between each stop-only/resume pair through the resumption boundary. The later schedule therefore did not affect those earlier physical states.

## Independent metrics and retained failure

The review independently computes planar speeds from unsmoothed position differences and heading from normalized quaternion components. It applies the declared 7.5 ms Gaussian only to heading, with the same reflected window edges. All primary window medians/displacements and decisions agree with the saved report. The figure's 11-sample median speed filter is cosmetic and is clearly labeled; the retained figure was visually inspected.

| Candidate | Stop speed before resume | Resumed speed | Resumed absolute yaw | Result |
|---|---:|---:|---:|---|
| Measured length | 0.003763 mm/s | 20.56898 mm/s | 35.40356°/s | Passes fixed grid |
| Neutral zero | 0.003244 mm/s | 19.70670 mm/s | 29.33528°/s | Passes fixed grid |
| Last target | 0.005945 mm/s | Incomplete | Incomplete | Fails resumption |

The available pre-resumption stop window in the failed trace also passes stopping. Failure remains the correct trial-level result: its final frame is at reconstructed time **1.226 s**, after 613 actions. Its independently reconstructed current reference error is **0.3114005 cm**, beyond the source's 0.3 cm limit. Final linear/angular speeds, **4.96945 cm/s and 24.96240 rad/s**, remain below the corresponding 50 cm/s and 200 rad/s limits. All retained arrays remain finite. This confirms a sufficient termination condition; unrecorded `qacc` prevents excluding another simultaneous source criterion.

## Boundaries and follow-up recommendations

Two reporting details should remain explicit in future diagnostics:

- The original checker skips most per-array checks when a trial carries a failure (`scripts/check_flybody_stance.py:27–29`). This independent review closes that coverage gap for the current failed trace, including action order, latching, activation filtering, finite state and its available stop window. Future checkers should retain these checks before branching on completion.
- Raw `actuator_force` is preceding-force-stage telemetry (`scripts/experiment_flybody_stance.py:126`). dm-control ends a control step with `mj_step1`, making saved transmission lengths current with `qpos`, but it does not recompute actuator forces at that final state. Do not pair this raw force array with poststep activation/length as an instantaneous force-law verification. The detached `mj_forward` used for contact diagnostics does not modify the policy's running state.

Ground geometry ID 0 resolves to `groundplane`; the leg/floor selection and contact-frame vector transformation are consistent with the source. Physical gates recompute correctly from saved aggregates. This review did not independently solve contact forces. The support metric sums **absolute world-vertical** contact forces, including artificial maximum adhesion; it is not net weight balance or physiological force validation. Contact counts also include returned near-contact entries, whereas the support gate requires positive force. The reported four/five supporting legs are sampled support, not a continuous-contact proof.

No native `data.time` series, `qacc` series or failed-run warning history was retained. Clock values are reconstructed from action counts and the verified source steps. The 500 Hz sampled geometry/support and interval displacement speeds do not establish continuous-time extrema. These limits do not change the declared decisions.

The unchanged source dynamics and successful hold/resume traces support a narrowly labeled optional engineering adapter. They do not establish a male body, a neural stance circuit, a natural resting pose, adhesion physiology, or successful transitions at untested gait phases, speeds, headings or surfaces. Preserve the failed last-target candidate and require separately declared tests before broader use.
