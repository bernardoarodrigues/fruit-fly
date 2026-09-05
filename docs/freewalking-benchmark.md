# Native-clock mixed-sex locomotion benchmark

The acquired file now provides a reproducible **mixed-sex, curated-running reference**, with quantities aggregated by animal. Its first comparison suggests that the current physical CPG can produce approximately the source's running speed, but the direct-DNg97 probe drives smaller joint excursions and lower speed. No neural gain, body geometry, or motor parameter was tuned to these data.

The [benchmark script](../scripts/benchmark_freewalking.py), [complete derived summaries](../validation/freewalking-benchmark.json), and [comparison plot](../validation/freewalking-benchmark.png) retain the methods and results. The HDF5 remains in ignored `data/raw/`; no raw or retargeted source trajectory arrays were exported. The data's explicit redistribution license remains unidentified.

## Scope and source selection

The source is *Whole-body 3D kinematics of freely behaving Drosophila*, [preprint DOI 10.64898/2026.05.03.722293](https://doi.org/10.64898/2026.05.03.722293), with [author code](https://github.com/elliottabe/3d_tracking_dataset/tree/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f) pinned to `d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f`. HDF5 SHA256: `369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e`. The paper reports 13 males and 9 females; the inspected per-recording metadata does not identify which animal has which sex.

There are **372 bouts, 22 recording animals, and 168.114 seconds** between valid native position endpoints. The study selected upright, well-tracked running away from interfering walls, with scutellum forward speed above 5 mm/s and at least two complete cycles for every leg. These data do not estimate spontaneous behavior prevalence, resting time, slow walking, female/male differences, or all possible gaits. [Primary paper, behavioral segmentation and running analysis](https://doi.org/10.64898/2026.05.03.722293)

The separate [alignment audit](freewalking-data-alignment.md) establishes why the saved `qvel` and `site_xpos` arrays must not be paired with native `qpos` by row number. This benchmark uses neither of those arrays. The one-frame mismatch with attached CSV ranges still prevents assigning an exact original-video frame to each exported sample.

## Aligned quantities and uncertainty

For each native `qpos` sequence with N samples, relative time is `arange(N)/800`. Translation and scalar-joint velocities use forward differences, yielding **N−1 valid intervals**, located at `(arange(N−1)+0.5)/800`. No fabricated final velocity is appended.

Root positions are in the source model's centimetres and are multiplied by **10 to obtain millimetres**. The model positions have already been scaled toward a canonical body. Raw `orig_keypoints` instead require **0.1 to obtain millimetres** and retain the tracked animal's scale before that normalization. Raw scutellum speed and normalized model-root speed are reported separately; their difference also includes the distinct tracked/root reference points. The source's per-bout size transform is not fully preserved, so a ratio between them is not a recovered body-scale calibration.

The free-root quaternion is `w,x,y,z`. Quaternion rotations are normalized by SciPy after checking a norm error below 0.001; the largest observed source error is only 7.52×10⁻⁶. Angular velocity comes from the shortest rotation-vector logarithm between neighboring rotations, in both world and body frames. The implementation never differentiates four quaternion components as if they were independent angles. Analytic tests include alternating equivalent quaternion signs and a heading crossing ±π.

The thorax's forward axis is +x, as supported by the named model's head/body placement. Planar heading comes from that axis projected into the world XY plane. A planar heading is rejected when its projection is nearly vertical. Reported absolute heading rate uses Gaussian smoothing of unwrapped heading with **σ=6 native frames (7.5 ms)** before differentiation, with unsmoothed and σ=3/12 alternatives retained. This is heading motion, including gait-coupled yaw and tracking jitter; it is not automatically a deliberate turning command.

All 93 qpos columns are verified against the pinned XML joint sequence. Scalar joint velocities are derived from those exact columns and radians, without arbitrary unwrapping of limited hinges. The report preserves per-animal and per-bout absolute-velocity distributions for coxa/femur/tibia joints. Whole-bout maximum scalar-angle changes are retained as integrity diagnostics; the largest is 34.19° per native interval. Nothing in the primary population summaries is silently clipped or repaired.

## Step timing and joint excursions

For each of six legs, speed is derived from its **native raw tracked tip** in world coordinates, on the same N−1 interval grid. Following the primary paper's method, the speed is Gaussian-smoothed with σ=6 frames, mean-subtracted, and transformed with a Hilbert transform. Upward phase crossings at −π/2 define swing-onset cycle boundaries. [Primary paper, swing/stance Methods](https://doi.org/10.64898/2026.05.03.722293), [author running notebook](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/notebooks/Scutellum_Height_Running.ipynb)

This implementation additionally excludes the first/last **4σ** regions and rejects candidate cycles with more than π/4 accumulated reverse phase. Those are disclosed engineering quality guards, not parameters fitted to obtain a target frequency. It retains **6,565 complete leg cycles** and rejects 111 internal candidates for phase reversal, in addition to boundary truncation. Counts by leg are LF 1,100; LM 1,098; LH 1,067; RF 1,083; RM 1,124; RH 1,093. A synthetic positive speed-pulse signal recovers the known 10 Hz cycle rate.

For each accepted cycle, frequency is `800/(end−start)` and a named joint's range of motion (ROM) is `max−min` over the corresponding native frames, converted to degrees. This is an independent benchmark adaptation, **not an exact reproduction of the paper's saved analysis**, which also used processed/model site outputs. It does not infer stance forces from tracking.

Per-animal summaries pool that animal's valid intervals or cycles. The population comparison then gives **equal weight to each animal's median**, so an animal with many long bouts does not become dozens of independent animals. No confidence interval or population-wide sex effect is claimed.

| Quantity | Median across animal medians | Interquartile range across animals |
|---|---:|---:|
| Model-normalized root speed | 20.17 mm/s | 15.86–22.07 mm/s |
| Raw scutellum speed | 16.44 mm/s | 13.21–17.79 mm/s |
| Absolute heading rate, σ=7.5 ms | 76.71°/s | 55.16–87.52°/s |
| LF cycle frequency | 10.96 Hz | 9.43–12.12 Hz |
| LF tibia ROM | 63.74° | 61.28–69.87° |

The median normalized speed changes little across smoothing sensitivities: 20.17 mm/s unsmoothed, 20.19 at σ=3 frames, 20.25 at σ=6, and 19.89 at σ=12. Absolute heading rate is much more sensitive: **144.58, 90.89, 76.71, and 61.16°/s**, respectively. Fast orientation fluctuations must therefore not be overinterpreted as intentional steering.

Across the six legs, animal-median cycle frequencies are 10.89–11.43 Hz. Tibia ROM differs substantially by leg pair: front approximately 61–64°, middle 34–35°, and hind 79–80°. The result file also records within-animal Spearman frequency–speed associations and frequency distributions in fixed speed bins. For LF, the median within-animal Spearman coefficient is **0.772** (IQR 0.690–0.879; 21 animals with at least six accepted cycles and varying frequency). This gives a concrete adaptation target that a constant 12 Hz oscillator does not express. These are descriptive associations, not a fitted causal motor law.

## Current simulator comparison

The script compares seeds 11 and 12 for two conditions, without modifying runtime implementation:

- CPG-only: constant left/right drive 1.0, independent of the neural engine.
- Direct DNg97 probe: full retained male graph, current-based LIF, 40 Hz input to each DNg97 cell, existing rate-to-motor decoder, odor and taste input disabled.

Each run lasts 1.5 s; the first 0.3 s is excluded by a declared fixed startup rule. The arena is enlarged to 40 mm half-size and resource patches moved off the path to isolate locomotion from wall/resource collisions. Root kinematics and actual distal-leg body positions are sampled at 200 Hz, which is an exact multiple of the 0.1 ms physics step and 5 ms coupling interval. Step smoothing uses the same **7.5 ms physical time**, not six 200 Hz samples. Simulated tibia ROM uses the actual joint positions, not actuator targets. Neural runs retain their standard manifests and telemetry in ignored `runs/`.

| Condition | Speed median, seeds 11 / 12 | LF frequency | LF tibia ROM, seeds 11 / 12 |
|---|---:|---:|---:|
| Mixed-sex source reference | 20.17 mm/s across animals | 10.96 Hz across animals | 63.74° across animals |
| CPG drive 1.0 | 18.55 / 18.27 mm/s | ≈12 Hz | 54.28 / 54.23° |
| Direct DNg97 40 Hz input | 9.16 / 7.33 mm/s | ≈12 Hz | 33.71 / 32.51° |

The simulated cycle estimator is quantized by its 200 Hz sampling: 200/17=11.765 Hz and 200/16=12.5 Hz bracket the underlying 12 Hz oscillator. This should not be mistaken for a precisely measured biological 11.765 Hz oscillator.

The DNg97 probe's filtered output averages **21.8/16.6 Hz**, with mean decoder drives **0.515/0.407**, and the selected walking state occupies 91.7%/93.8% of the post-startup window. The decoder divides the forward readout by 40 Hz and clips the result; drive primarily scales the CPG's excursion while its intrinsic frequency remains 12 Hz. The lower probe speed and ROM are therefore consistent with that declared engineering mapping. They do not establish that a natural fly's DNg97 spikes should be multiplied by a particular correction factor.

Middle/hind excursions also differ. The unit-drive CPG produces roughly 23° middle and 61–62° hind tibia ROM, compared with source references around 34–35° and 79–80°. Direct DNg97 produces roughly 11–14° and 31–37°. Cross-model tibia ROM is a useful single-hinge amplitude diagnostic, but current and source models differ in geometry and reference frames; compound coxa/femur coordinates are not interchangeable actuator targets.

The CPG's absolute heading motion is roughly **218–224°/s** after 7.5 ms smoothing, greater than the source reference. The same CPG windows have net heading rates of only **−2.09/+4.38°/s**, demonstrating that much of the large absolute heading motion reverses direction instead of accumulating as a turn. This is consistent with periodic body yaw under the gait, but the benchmark does not establish its contact-mechanical cause. It is a concrete reason to inspect gait-coupled body motion before fitting steering gains. The direct-DNg97 condition gives 72–91°/s while also moving more slowly. A lower aggregate heading-motion statistic alone does not establish better biological movement. Source animals have a median absolute per-bout net heading rate of 59.34°/s across animal medians; they are not following the simulator’s deliberately straight bilateral command. That assay difference prevents treating a match to source turn statistics as proof of calibrated steering.

The comparisons suggest bounded next calibration work: test source-supported frequency/excursion relationships on held-out animals, inspect CPG yaw oscillation and contact/adhesion sensitivity, and fit any spike-to-drive relation against an appropriate neural/behavioral experiment. Simply increasing the DNg97 gain until one speed matches would leave the fixed-frequency, leg-excursion, coordinate and behavioral-selection issues unresolved.

## Identified examples and reproducibility

Three source **identifiers only** are retained for later review. They were selected around the 10th/50th/90th speed quantiles among 164 candidates lasting ≥0.4 s, with two retained cycles per leg, scalar jumps below 30°/sample and root orientation steps below 10°/sample. These broad engineering guards do not filter the population summaries.

| Bout | Recording ID | Native duration | Median normalized speed |
|---|---|---:|---:|
| `bout_344` | `session7/2025_10_13_12_33_18` | 1.39125 s | 12.04 mm/s |
| `bout_249` | `session6/2025_10_12_15_06_46` | 1.46375 s | 19.16 mm/s |
| `bout_323` | `session5/2025_10_11_10_29_50` | 0.47750 s | 25.19 mm/s |

None has an established individual sex label or verified absolute source-frame mapping. No source arrays are copied into tracked output files.

```sh
# Download the public HDF5 first if not already present.
.venv/bin/python scripts/acquire_freewalking.py

# Source summaries; downloads the pinned small XML if it is absent.
.venv/bin/python scripts/benchmark_freewalking.py

# Also run independent CPG and full-graph DNg97 comparisons (new run directories).
.venv/bin/python scripts/benchmark_freewalking.py --include-simulation

# Analytic quaternion and known-cycle-frequency checks.
.venv/bin/python -m pytest tests/test_locomotion_metrics.py -q
```

The XML SHA256 is `52dda79c9df22872fda0a37009f478515cc6398562a3988c79f11347e2c7f633`; its exact joint order, local axes, source URL, script hash, dependency versions, and body-code hash are retained in the report. The source HDF5 and model XML hashes are verified before analysis. Raw values remain unchanged.
