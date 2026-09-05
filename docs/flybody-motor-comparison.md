# Frozen FlyBody motor comparison

**The released FlyBody controller improves straight-line heading stability and executes both signed turns, but does not pass the declared overall promotion rule.** Its zero-command and withdrawal windows retain too much local root motion under the fixed ≤1 mm/s criterion. It also retains a substantial joint-excursion mismatch and excessive high-speed cadence. Runtime defaults, the current body, neural graph and sensory encoders are unchanged.

This follows the [source/policy feasibility audit](flybody-policy-feasibility.md) and [successful isolated Apple Silicon inference trial](flybody-inference-trial.md). The comparison uses the exact author SavedModel, all trained tensors, original FlyBody geometry and dynamics, and original action clipping/scaling. It changes no controller gains, weights, contact settings or body dimensions. This is a comparison of two complete motor/body stacks, not an isolated causal comparison of control algorithms or a claim of male anatomy.

## Frozen design and the reporting correction

The [original plan](../validation/flybody-motor-comparison-plan-v0.json) was written before the first physics trial; SHA256 `aa3f77eeebec90a9f0dd850f39130b18566a9597f9fdfb32283356c2dfc67c2e`. There are six command cases × two requested seeds:

| Case | Forward command | Yaw command | Schedule |
|---|---:|---:|---|
| `straight10` | 10 mm/s | 0 | Entire trial |
| `straight20` | 20 mm/s | 0 | Entire trial |
| `left20` | 20 mm/s | +2 rad/s (+114.592°/s) | Entire trial |
| `right20` | 20 mm/s | −2 rad/s (−114.592°/s) | Entire trial |
| `zero` | 0 | 0 | Entire trial |
| `withdraw20` | 20 mm/s, then 0 | 0 | Withdraw exactly at 0.750 s |

Each lasts 1.5 s, with the first 0.3 s excluded from ordinary summaries. The withdrawal stopping window is fixed at 1.0–1.5 s, beginning 250 ms after withdrawal. Seeds are 11 and 12. **Each seed pair produced bitwise-identical physical traces**: this inference preset uses a deterministic mean policy and does not introduce an initial-condition perturbation from those seeds. These are six distinct conditions with repeated executions, not 12 independent stochastic replicates.

The first `straight10`, seed 11 physical rollout completed, but strict JSON serialization rejected a nonfinite contact-force diagnostic. dm-control ends its physics step with `mj_step1`: contact geometry has been refreshed while constraint forces still belong to the prior configuration. Querying those forces against new contact addresses produced invalid diagnostics. The corrected recorder copies the full native `MjData`, calls `mj_forward` on that **detached copy**, and queries its solved contact forces. The original controller's state, observations and dynamics remain untouched. This follows the inspected [dm-control step implementation](https://github.com/google-deepmind/dm_control/blob/1.0.27/dm_control/mujoco/engine.py).

The [amended plan](../validation/flybody-motor-comparison-plan.json), SHA256 `471e8aa00ab1cf8539f9d104d507d1d2c9b7d7af5b91fac582d54b497e210d76`, preserves the original plan hash, failed-report trace hash and exact correction. **No command, acceptance rule or motor parameter changed.** The checker confirms that every nondiagnostic array—poses, joint angles, tip positions, actions, actuator forces, targets and commands—is bitwise identical between the initial and corrected first trial. Original contact-force values are explicitly invalid and excluded.

## Causal command and physics interface

The original source is pinned to [`d015e9bfe441bd90ae431bac24c55cb74bdbce26`](https://github.com/TuragaLab/flybody/tree/d015e9bfe441bd90ae431bac24c55cb74bdbce26). The [manifest](../validation/flybody-source-manifest.json) verifies 223 source/assets files; the [acquisition receipt](../validation/flybody-walking-acquisition.json) pins every downloaded policy file. All execution uses the separate Python 3.10 / TF 2.15.1 / TFP 0.23 / MuJoCo 3.2.7 environment and [hashed dependency lock](../validation/flybody-inference-requirements.lock). The prior trial established deterministic finite actions and NumPy reproduction of the actual mean network to maximum absolute error 8.11×10⁻⁶; this experiment uses the unchanged restored graph.

The body integrates at **0.2 ms** and the policy runs at **2 ms (500 Hz)**. Native length is centimetres: desired mm/s is divided by 10 before making the reference; measured root and claw coordinates are multiplied by 10 for millimetres. Original position/adhesion activation filters remain 10/7 ms. The actor receives the source's 741 float32 inputs and outputs 59 canonical means, clipped to [−1,1], transformed into source action ranges, then permuted into compiled actuator order by the author's `apply_action`.

An 820-frame reference buffer supports the entire 750-step trial plus 64 future steps. At each control tick, only the **current** speed/yaw command is extrapolated over the 128 ms preview. The target root pose advances continuously from the previous target; it is not recentered to the physical body. The two reference observables are refreshed after the new current command arrives; physical observables retain the source Composer behavior. The future zero command is not exposed before t=0.750 s. No physical reset, food coordinate, source leg trajectory, or neural observation appears in this reference builder.

The synthetic source helper computes angular `qvel` as a per-step rotation using `quat2Vel(...,dt=1)`. This experiment supplies the correctly dimensioned planar angular velocity [0,0,yaw_rad_s] in the reference array. It preserves the source pose preview. The default task does not initialize physical velocity from that synthetic `qvel`, and the actor's two reference observations contain pose quantities. This small unit correction is disclosed in the script; it is not a trained-weight or physical-controller modification. [Author synthetic trajectory code](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/synthetic_trajectories.py).

## Comparison basis and decision rules

The biological comparison reuses the existing [native-clock freewalking benchmark](freewalking-benchmark.md), built from native 800 Hz positions and raw tracked leg tips. It does **not** use the mismatched saved `qvel` or `site_xpos` arrays. Its 22 animals are a mixed-sex population, and the acquired HDF5 lacks per-animal sex labels. The source specifically selected well-tracked running, not resting, courtship, feeding or unselected spontaneous behavior. Source model-root positions have already been normalized toward a canonical body; they are not each animal's original metric scale.

The same eight evaluation recording IDs declared in the earlier exploratory CPG split supply the reference. At exact target speeds 10 and 20 mm/s, a ±2.5 mm/s band on each bout's median normalized root speed leaves **four and seven contributing animals**, respectively. Each animal contributes its median of the qualifying bout medians, then animals receive equal weight. This is not the six-animal high-speed band of the earlier CPG plan: that plan used 20.250 mm/s rather than exact 20. The recomputed CPG ROM errors here use the new exact-speed bands consistently. Pooled data had already been inspected before either split; this is not a blinded biological holdout.

Root speed uses native finite differences without smoothing. Heading comes from the quaternion-rotated body +x axis and is smoothed with σ=7.5 ms before differentiation. Cycle timing uses the existing leg-tip speed/Hilbert method and the same 7.5 ms smoothing plus edge/phase quality guards. FlyBody is sampled at 500 Hz, CPG at 200 Hz, experimental data at 800 Hz, so cycle frequencies have different interval quantization. ROM is measured actual tibia max−min within an accepted cycle, not the actuator target. All six compiled FlyBody tibia axes are verified as [1,0,0], matching the source model's local hinge convention. This supports a scalar ROM comparison; it does not make compound joint poses, foot positions or body geometry interchangeable.

The criteria were fixed before trials:

- All trials: finite states, no MuJoCo warnings, upright z≥0.5, root height≥0.5 mm, and ≤1% sampled frames without positive actual leg-floor support.
- Both straight commands: speed error no worse than frozen paired CPG error plus 2 mm/s, and ≥20% reduction of the median absolute yaw rate.
- Across the two straight commands/seeds: six-leg tibia ROM mean absolute reference error no worse than recomputed CPG error plus 5°.
- Both turns: signed yaw median within 25% of ±2 rad/s, speed median within 20% of 20 mm/s.
- Zero and post-withdrawal windows: median planar speed≤1 mm/s and net planar displacement≤0.5 mm.
- All criteria must pass before promotion to an optional runtime adapter is discussed. No automatic integration or biological-validation claim follows from a pass.

These are disclosed engineering decision gates, not statistical significance tests or natural sleep/rest criteria.

## Results

The complete [12-trial result](../validation/flybody-motor-comparison.json), [figure](../validation/flybody-motor-comparison.png), and [trace-validation receipt](../validation/flybody-motor-comparison-validation.json) are retained. Entries below are the identical seed-pair values. Straight CPG comparisons are means of the two frozen seed-specific medians.

| Command | FlyBody median speed | FlyBody median signed yaw | FlyBody median absolute yaw | Outcome |
|---|---:|---:|---:|---|
| Straight 10 mm/s | 10.99 mm/s | +0.88°/s | 23.51°/s | Speed and yaw gates pass |
| Straight 20 mm/s | 19.49 mm/s | −4.02°/s | 37.78°/s | Speed and yaw gates pass |
| Left 20 mm/s, +114.59°/s | 17.41 mm/s | +114.21°/s | 114.21°/s | Signed-turn and speed gates pass |
| Right 20 mm/s, −114.59°/s | 19.09 mm/s | −118.05°/s | 118.05°/s | Signed-turn and speed gates pass |

Frozen CPG absolute yaw medians are **92.70/220.82°/s** at the lower/higher commands. FlyBody reduces them by **74.6%/82.9%**. Its net straight heading rates remain only +1.27/−1.30°/s, consistent with small remaining reversing motion. The source free-running bouts include intentional turns and have conditional absolute yaw medians 43.27/66.03°/s; being below those medians in a deliberately straight command assay does not establish more natural movement.

The larger limitation is the gait:

| Quantity | 10 mm/s reference / FlyBody | 20 mm/s reference / FlyBody |
|---|---:|---:|
| LF cycle frequency | 10.36 / 8.77 Hz | 10.90 / 15.63 Hz |
| LF tibia ROM | 56.00 / 27.21° | 61.90 / 35.02° |
| LM tibia ROM | 35.32 / 15.55° | 32.60 / 12.53° |
| LH tibia ROM | 69.04 / 59.33° | 78.10 / 49.28° |

Both straight commands produce the same median frequency across all six FlyBody legs within each condition. At 20 mm/s, LF cadence is about 43% above the conditional source median, while tibia excursions remain too small. This is compatible with a simulator covering its commanded speed through faster, smaller cycles; it is a descriptive inference, not a demonstrated unique contact-mechanical cause.

Aggregate tibia ROM error is **22.65° for FlyBody versus 21.85° for CPG**, passing the deliberately permissive no-new-large-regression gate but providing **no aggregate ROM improvement**. The lower-command error improves (18.92° versus approximately 31°), while the higher-command error worsens (26.38° versus approximately 12°). The existing source paper's held-out walking evidence uses female top-view 2D tracking with inferred height, not an independently measured 3D joint-ROM target; those source limitations remain relevant. [FlyBody paper](https://www.nature.com/articles/s41586-025-09029-4).

The stopping result is a clear negative result under the declared metric:

| Fixed window | Median / p95 root speed | Net displacement | Gate |
|---|---:|---:|---|
| Zero command, 0.3–1.5 s | **1.692 / 2.121 mm/s** | 0.0176 mm | Speed fails; displacement passes |
| Withdrawal, 1.0–1.5 s | **1.401 / 1.941 mm/s** | 0.1728 mm | Speed fails; displacement passes |

The zero-command body does not steadily walk away: its x/y spans in the analyzed window are only about 0.0193/0.0196 mm, despite accumulated local planar path length 1.962 mm. The withdrawal window has 0.701 mm path length and 0.173 mm net displacement. Thus the failed criterion captures small local physical motion as well as translation. No post hoc smoothing, relaxed threshold, or target reset is used to turn this into a pass. These short physical observations do not establish natural resting or sleep behavior.

### Read-only stopping follow-up

The separately labelled [post hoc diagnostics](../validation/flybody-stopping-diagnostics.json) analyze only the frozen traces; they make no new physics trial and change no decision. Reproduce them with `tmp/flybody-env/bin/python -m scripts.analyze_flybody_stopping`.

In the zero window, **LM, LH, RF, RM and RH have positive floor force at every sampled frame**. LF makes 98 contact onsets and 98 offsets over 1.2 s (81.7 onsets/s), each positive contact spanning only one sampled frame. Its support fraction is 16.3%. That is high-frequency contact chatter at the 500 Hz diagnostic sampling scale, not evidence of an 81.7 Hz walking gait. Actual contact duration between samples is unresolved. Whole-window tibia excursions are only 1.19–2.40° across the six legs.

In the final withdrawal window, **all six legs remain supported with zero contact onsets or offsets**. Tibia angles still adjust by 4.21–11.88° across that 0.5 s window. Before withdrawal (0.3–0.75 s), the gait detector retains approximately 15.15–15.63 Hz cycles, and individual legs have 7–15 contact onsets over 0.45 s. Contact chatter can make contact-onset counts exceed actual gait cycle counts even during ordinary walking, so they must remain distinct metrics.

Applying the Hilbert detector post hoc to the low-amplitude stopping traces yields spurious-looking candidates (0–12 per leg for zero; 0–2 in the final withdrawal window), without corresponding alternating ground-contact cycles for the continuously supported legs. We report those detector candidates, tip spans/speeds and whole-window joint excursions, but **do not call them steps or assign a validated stopping cadence**. The residual-speed failure therefore does not imply that the fly continues a sustained forward walking gait.

The original policy was **not trained only on positive-speed walking**. The primary paper explicitly describes an approximately 0–4 cm/s dataset including “turning and standing still,” and a single network trained on about 13,000 selected trajectories. Zero speed is within that stated intended coverage. However, the article does not provide a separate residual-motion threshold or an evaluation of this exact unannounced 20→0 mm/s command change. We did not download its ~3 GB walking data to count stationary or stopping snippets, so exact training exposure remains unverified. [Primary paper, Walking and Reference walking data](https://www.nature.com/articles/s41586-025-09029-4).

The pinned source exposes `flight_imitation`, `walk_imitation`, `walk_on_ball`, `vision_guided_flight` and a generic `template_task`, but no inspected pretrained standing policy or explicit walking/stance/flight transition controller. The released checkpoint archive contains walking, flight and two visually guided flight policies. Flight and walking are constructed with different disabled body-part/observation/action configurations; some disabling removes joints or actuators before compilation. Those flags are not a validated live takeoff/landing switch. [Source environment factories](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fly_envs.py), [body construction](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/fruitfly.py).

There **is a native position-actuation mechanism from which a joint hold could be built**: non-wing affine actuators apply proportional restoring torque toward their filtered target, with passive joint damping/stiffness retained. The XML's zero-angle geometry supplies the source's neutral standing pose; it is not a demonstrated static mechanical equilibrium. `template_task` exposes a custom `mjcb_control` callback and action modification, and `apply_action` can receive a fixed valid native action vector. No source helper was found that captures the current physical pose, safely transfers all joint/tendon targets and adhesion, then demonstrates stable standing and re-entry. That behavior would require a new explicit controller/transition test. **Canonical zero is not native zero-angle hold** because asymmetric action ranges map it to nonzero midpoints, and it maps adhesion to 0.5. Tendon targets, existing activation state and adhesion choices also prevent blindly copying scalar qpos into the 59-action vector. [Source template task](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/template_task.py), [actuator definitions](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/assets/fruitfly.xml).

This follow-up is feasibility only. No source hold, transition, friction change, policy filter or new controller was implemented or tuned.

## Contacts, clipping and actuator limits

Every trial satisfies the physical gates: minimum upright z **0.991**, minimum root height **1.236 mm**, zero sampled unsupported frames, all retained arrays finite, and zero MuJoCo warnings. This is sampled mechanical stability over short flat-floor trials, not robustness under perturbations or biological ground-reaction validation.

Across analyzed windows, **45.4–51.4%** of all canonical means exceed [−1,1] and receive the author's clipping. Adhesion channels clip on **76.8–92.5%** of samples; position channels on **40.4–48.0%**. Clipping is a material part of the released policy interface, so replacing it with unbounded means would change the controller. These proportions are not evidence that the saved network failed to load.

Only **three compiled position actuators** have explicit force limits, and their observed near-limit fraction is zero. Leg position actuators have no declared force cap in this source preset, so the experiment cannot claim “no leg torque saturation” against a nonexistent limit. The JSON's peak absolute native actuator output mixes adhesion force and hinge torque channels; do not compare that aggregate number to CPG torques or interpret it as a common force unit. Filtered tibia-target versus actual-angle RMS is **7.90–15.37°** across cases, notably greater than the CPG's 1.86–3.02° in its own coordinate/dynamics setup. It is a tracking diagnostic, not proof of muscle force capacity.

The summed absolute vertical leg-floor force averages **4.53–5.73 times body weight**, with source body weight 0.9659 dyne. Artificial claw adhesion is active and the statistic sums contact magnitudes; it is not a net external-force balance or a biological force measurement. Supporting-claw marker speed is also retained per leg, but a claw site is not necessarily the instantaneous contact point. Its nonzero velocity is not by itself a validated slip estimate. Source raw tracking provides no matching force data. We preserve these limitations rather than infer biological stance duty or force from unmatched kinematics.

## Reproduction, compute and recommendation

```sh
# In the already prepared isolated environment; never install into main .venv.
tmp/flybody-env/bin/python -m scripts.compare_flybody_motor --run
tmp/flybody-env/bin/python -m scripts.check_flybody_comparison
tmp/flybody-env/bin/python -m scripts.plot_flybody_comparison
```

`--plan-only` originally wrote the design and refuses an existing plan. The run verifies script and source-summary hashes, frozen source/assets and policy files, then writes incremental reports. All generated physics traces are in ignored `runs/`; the prior [asset/environment instructions](flybody-inference-trial.md) describe reconstruction. No raw experimental trajectories are redistributed. Code is sourced under Apache 2.0; the separately downloaded policy collection declares GPL-3.0+, as retained in its acquisition receipt and local asset notice.

The [checker](../scripts/check_flybody_comparison.py) verifies all 12 unique entries and hashes, 751 physical frames/750 actions per trace, finite arrays, exact canonical-to-native actions, correctly timed current-only commands, continuous integrated target position/yaw, exact zero-reference holding after withdrawal, independently recomputed heading/speed/cycle/ROM summaries, force diagnostics, all decision results and the bitwise no-physics-change diagnostic correction. The [plot script](../scripts/plot_flybody_comparison.py) produces PNG and SVG; the PNG was visually inspected for clipping and legibility.

Timed control integration took **4.73–5.20 wall seconds per 1.5 simulated seconds**, or **0.288–0.317× real time**, on this Mac's CPU. All 12 timed integrations totaled 59.72 s; model construction/import/loading are excluded. Those timings include detached-state contact diagnostics. The previous shorter smoke without these diagnostics achieved approximately 0.33× real time. No training GPU or additional dataset download was needed. These are isolated body/policy measurements, not full-brain closed-loop performance.

**Keep FlyBody as a frozen external motor baseline; do not replace the runtime or promote this adapter yet.** Its lower reversing yaw and command-sensitive cadence justify retaining it for comparison. The declared stopping failure, high-command cadence/ROM mismatch, female-derived geometry, and distinct learned/body dynamics prevent claiming a completed motor improvement. A separate future proposal could test an explicit standing transition and independently measured gait targets, but that would be a new design requiring its own unchanged-parameter validation. This experiment performs no additional search and no full-neural integration.
