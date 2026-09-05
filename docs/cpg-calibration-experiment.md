# Exploratory CPG calibration experiment

**No tested candidate met the predeclared promotion gates. Keep the current runtime unchanged.** All 20 trials were mechanically stable, and preserving excursions improved the ROM endpoint, but the candidates worsened lower-drive yaw and missed the higher desired speed.

This experiment keeps the existing runtime and benchmark frozen. It asks whether preserving the original single-step template's excursions while controlling cadence improves low-drive kinematics, and whether artificial adhesion contributes to the large reversing yaw. It does not retarget the new source joint coordinates directly, fit a neural spike-to-speed law, or establish male-specific movement.

## Predeclared design

The machine-readable [plan](../validation/cpg-calibration-plan.json) was written before any candidate physics trial. SHA256: `1907c3451d29a43bc72a2958559192fd46b40d8bdedf457678aa00f02aad6933`. The script refuses to run if its implementation, the frozen body, or the benchmark changes after that plan. The original [benchmark](freewalking-benchmark.md) and its source arrays are untouched.

An earlier, **unrun** plan draft is preserved as `cpg-calibration-plan-v0-unrun.json`. Before executing any trial, inspection showed that substituting 70 mm/s for the very broad source summary bin 40–100 mm/s would invent a typical observed speed. The final fit excludes bins wider than 10 mm/s. No candidate outcome was seen before this correction or used to choose a new fit.

Animals are sorted by SHA256 of their recording ID. The first 14 are used for the cadence fit; the remaining eight supply conditional reference summaries. Pooled benchmark results were already inspected before making this split, so it is **exploratory**, not a blinded biological holdout.

The training fit uses the left foreleg's median frequency in fixed speed bins, requiring ≥3 cycles per bin and width ≤10 mm/s. Weighted least squares gives each contributing animal equal total weight:

```text
f_Hz = 4.5411193 + 0.2729633 × desired_speed_mm_s
```

Cadence is clipped to the training fit-point frequency range, 5.882–14.815 Hz. Desired speed is `drive × 20.2498107 mm/s`, where 20.2498107 is the training animals' median normalized root speed. This drive-to-desired-speed relationship is an engineering command convention. It is not measured descending-neuron physiology. The fit approximates each compact speed bin by its midpoint; that approximation and the body-normalized source units remain limitations.

The grid has **five variants × two drives (0.5, 1.0) × two seeds (11, 12) = 20 trials**. Each lasts 1.5 s with a fixed 0.3 s startup exclusion. All use the same enlarged clear arena, initial pose, position gains, force bounds, joint springs/damping, CPG coupling, retraction/stumble reflexes, and phase-dependent adhesion timing. Only the stated instance-level quantities differ:

| Variant | Template excursion magnitude | Cadence | Adhesion gain | Purpose |
|---|---|---|---:|---|
| `baseline` | Existing drive magnitude | Existing 12 Hz | 40 | Frozen baseline |
| `full_excursion` | 1.0 | 12 Hz | 40 | Mechanistic control; ineligible for promotion because forward drive is ignored |
| `cadence` | 1.0 | Training speed–frequency fit | 40 | Candidate |
| `cadence_adhesion10` | 1.0 | Same fit | 10 | Candidate with quarter-strength artificial adhesion |
| `cadence_adhesion0` | 1.0 | Same fit | 0 | Diagnostic candidate without artificial adhesion |

The original `PreprogrammedSteps` data are single-leg trajectories extracted from FlyGym v1 walking recordings, exposed by the installed controller in current anatomical coordinates. “Preserve excursions” means keep those existing template excursions, not assert that new mixed-sex joint traces have been numerically retargeted. The original formula is `neutral + magnitude × (template(phase) − neutral)`; current drive directly changes `magnitude`. The turning wrapper keeps the intrinsic cadence at 12 Hz apart from direction reversal. These code facts explain why lower forward drive shrinks all excursions while leaving cycle timing largely unchanged.

Adhesion 10 and 0 are quarter/zero perturbations of the current gain 40. They are not experimentally measured pad parameters, and zero artificial adhesion does not mean a real fly has no adhesion. No friction, collision pair, floor, actuator-force, or contact-solver changes are hidden in these comparisons.

## Decision rule, frozen before trials

The primary endpoint is mean absolute tibia ROM error across six legs, both drives and seeds, compared with equal-animal reference medians from evaluation bouts whose median normalized speed lies within ±2.5 mm/s of the desired speed. The bands have four and six evaluation animals, respectively. A candidate must reduce that error by **at least 20%** against the paired baseline.

Every candidate trial must also remain finite, keep thorax height ≥0.5 mm and upright-axis z≥0.5, show no MuJoCo warnings, and have no more than 1% of sampled frames without positive support from any leg. At each drive, its mean desired-speed absolute error must not exceed baseline by more than 2 mm/s; its mean absolute heading-motion median must not exceed `1.2 × baseline + 10°/s`. Each source reference band must include at least three animals. These are engineering decision gates, not statistical significance thresholds.

Cadence, speed, actual tibia ROM, heading motion, net heading rate, ground force, uprightness, actuator force, tracking error, and reflex correction are all recorded, but are not collapsed into an optimized omnibus score. Passing would support discussing an **optional** controller; it would not authorize changing defaults or claim biological validation. No additional parameter search will be added after seeing this grid.

## Execution

```sh
# Already written and preserved; refuses silent overwrite.
.venv/bin/python scripts/calibrate_cpg_experiment.py --plan-only

# Executes the exact saved plan, verifies the frozen input hashes.
.venv/bin/python scripts/calibrate_cpg_experiment.py --run
```

The experiment changes only freshly created objects in its own process. Runtime source files remain unchanged. Its simulated trajectories may be stored under ignored `runs/` for post-analysis; these are generated simulator outputs, not redistributed experimental source arrays. The complete [results](../validation/cpg-calibration-experiment.json), [plot](../validation/cpg-calibration-experiment.png), and [validation receipt](../validation/cpg-calibration-validation.json) are saved.


## Results of all 20 declared trials

Values below are means of the two seed-specific medians or error summaries. Lower/higher commands correspond to desired speeds 10.125/20.250 mm/s. ROM error averages all six tibia joints against the conditional evaluation references.

| Variant | Speed, low / high command (mm/s) | Absolute heading motion, low / high (°/s) | Tibia ROM error, low / high (°) |
|---|---:|---:|---:|
| Frozen baseline | 9.36 / 18.41 | 92.70 / 220.82 | 31.15 / 11.87 |
| Full excursion, 12 Hz | 18.41 / 18.41 | 220.82 / 220.82 | 8.30 / 11.87 |
| Fitted cadence, adhesion 40 | 10.15 / 14.98 | 141.20 / 170.47 | 8.80 / 11.95 |
| Fitted cadence, adhesion 10 | 10.56 / 14.74 | 141.29 / 174.29 | 8.81 / 12.06 |
| Fitted cadence, adhesion 0 | 10.57 / 14.15 | 139.58 / 183.94 | 11.35 / 14.97 |

The fitted cadence commands are **7.305 Hz** at drive 0.5 and **10.069 Hz** at drive 1.0. Measured cycles are sampled at 200 Hz, so frequency estimates have the interval quantization already described in the benchmark. Every trial retained at least seven complete detected cycles in every leg.

Preserving excursions with fitted cadence reduced the aggregate ROM error by **51.8%**, satisfying the primary improvement threshold. The quarter-adhesion variant reduced it by 51.5%, and zero adhesion by 38.8%. Nevertheless, every candidate failed both the lower-command heading guard and higher-command speed guard. The low-command heading ceiling was about 121.24°/s, while candidates produced 139.58–141.29°/s. At the high command, candidates' speed errors were approximately 5.27–6.10 mm/s, compared with 1.84 mm/s for baseline; the allowed baseline-plus-2 ceiling was 3.84 mm/s. The control that ignores forward drive is ineligible by design and also fails its lower-command speed and yaw guards.

**Mechanical stability passed in all trials:** no nonfinite states, no MuJoCo warnings, no sampled loss of support, minimum thorax height 0.798 mm, and minimum upright-axis z 0.990. These are numerical/mechanical checks, not physiological validation. Peak position-actuator force was only 8.294 native units against the frozen ±65 limit; tibia tracking RMS was about 1.86–3.02°. The main excursion mismatch is therefore not explained by actuator-force saturation in this grid.

## What this identifies

1. **Amplitude scaling is responsible for much of the low-drive excursion loss.** At unchanged 12 Hz, replacing magnitude 0.5 with magnitude 1 changes speed from 9.36 to 18.41 mm/s and reduces low-command ROM error from 31.15 to 8.30°. This is a within-simulator intervention, not a claim that a real descending neuron controls one universal amplitude scalar.

2. **Cadence alone cannot supply the source's faster progression per cycle.** Preserving the current template and changing cadence reaches 10.15 mm/s at the lower desired 10.125 mm/s, but only 14.98 mm/s at the higher desired 20.250 mm/s. For orientation, dividing speed by commanded cadence gives about 1.39/1.49 mm of simulated progression per cycle. The engineering targets combined with the source frequency fit require about 1.39/2.01 mm. This calculation is an inference from the declared fit and measured simulator speed, not a directly observed foot-stride measurement. It suggests that the higher-speed trajectory requires changes in foot progression/excursion and possibly geometry, not only faster or slower playback of this fixed template.

3. **Artificial adhesion strongly changes ground forces but does not remove the yaw problem.** At fitted cadence, reducing gain 40→10→0 changes mean summed vertical ground force from roughly 136.4→41.6→10.0 native units. Body weight is 10.05 in the same units. Lower-command absolute yaw stays near 140°/s; higher-command yaw increases from 170.5 to 183.9°/s at zero adhesion. Thus this perturbation does not support attributing the reversing yaw chiefly to the adhesion gain alone. Gait geometry, tripod timing, contact mechanics and body inertia remain possible contributors that this grid does not distinguish.

All gain-40 and gain-10 trials had zero sampled reflex corrections; zero-adhesion trials had small maximum corrections, below 0.83. That further limits any explanation based on large stumble/retraction interventions in the normal-gain cases. Large ground reaction forces under artificial adhesion are not measured biological force targets and were not used as a fitted endpoint.

## Recommendation and limits

Do **not** promote any of these candidates or alter the default controller. No new production controller module was added. The isolated callback exists only inside the experiment script and defines positive forward commands; it has no validated stop, reverse, or turning behavior.

A bounded next kinematic milestone would retarget a source-supported progression/excursion change across speed, using recorded markers and explicit joint-axis conversion, before changing the neural decoder. The current mixed-sex source model and the female-derived NMF body have different geometry and joint conventions, so simply scaling every angle by a common factor would not establish that mapping. Separately, inspect the source of repeated body yaw with phase-resolved geometry/contact diagnostics; the present adhesion perturbation is already a useful negative result.

The evaluation has only two simulator initial-condition seeds, constant forward commands, a clear flat arena, and 1.2 s analyzed windows. It does not test neural rate fluctuations, obstacles, feeding, transitions, or unilateral steering. The biological comparison uses four/six source animals in the conditional speed bands, after pooled source data had already been reviewed. There is no claim of blinded generalization, male-specific calibration, complete gait fidelity, or behavioral control by the connectome.

The [checker](../scripts/check_cpg_calibration.py) verified all 20 unique grid entries, all 301-frame generated trace hashes and finite arrays, at least one cycle for every leg, unchanged body/controller/benchmark hashes, and exact reproduction of the earlier two unit-drive baseline speeds and all six tibia ROM values (absolute tolerance 1e−10). Reproduce that receipt with:

```sh
.venv/bin/python -m scripts.check_cpg_calibration
```

No additional candidates were searched after inspecting these outcomes. The original benchmark script/results, runtime body, neural simulator, and sensory decoder were not edited by this experiment.
