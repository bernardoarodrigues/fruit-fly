# FlyBody pretrained walking policy: feasibility audit

Audited 2026-09-04. **Recommendation: test the released walking SavedModel with its original FlyBody body as a separate motor baseline.** It can accept steering derived from our neural readouts without new motor training. The checkpoint, input contract and platform constraints are verified below; superiority to our current CPG is not established by this source audit. No runtime defaults changed. The fixed CPG experiment remains a negative result: [experiment](cpg-calibration-experiment.md).

## What is actually released

The author repository remains at commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`. Its [Figshare v4 collection](https://doi.org/10.25378/janelia.25309105.v4) lists a 6,537,720-byte `trained-fly-policies.zip` containing flight, walking, vision-bumps and vision-trench SavedModels. The ZIP central directory confirms `walking/saved_model.pb` (110,102 bytes), `walking/variables/variables.index` (924 bytes), and `walking/variables/variables.data-00000-of-00001` (4,919,480 bytes). There are no separate pretrained takeoff, landing, courtship, feeding, whole-brain or male-body controllers in this archive.

The walking graph was extracted with exact HTTP ranges and ZIP CRC checks. SHA-256: `49cdb0874021609c1aa5634a3073a394ef55b7ce54b6487c020c8ed2ec37d5d4`. Its own metadata reports TensorFlow **2.8.0**, git build `v2.8.0-rc1-32-g3f878cff5b6`. We inspected the graph, without executing it or initially loading weights. The archive's supplied MD5 is `12934d5a1c60631a710bc2b6d297d3ce`; a full-archive digest is not verified by ranged inspection. The server's multipart ETag must not be substituted for MD5.

Observed variable shapes establish **741 inputs → four 512-unit layers → two 59-unit distribution heads**, 14 float32 tensors and **1,229,430 parameters**. Generic `network_factory.py` defaults to three 256-unit layers; recreating those defaults would silently produce the wrong model. The two head variables have duplicate display names, so any conversion must retain object-node identity and captured-variable order, not make a name-keyed dictionary that overwrites one head. Saved output types are `Independent_ACTTypeSpec` containing `Normal_ACTTypeSpec`, with both location and scale shaped `[batch,59]`. TensorFlow Probability registration is therefore part of loading the original object. Graph operations include ordinary dense, LayerNorm, tanh, ELU and softplus operations; no custom MuJoCo/Reverb operation appears in the inspected operation inventory. That is evidence for a tractable conversion, not a numerical parity test.

Reproduce metadata acquisition with:

```sh
.venv/bin/python -m scripts.audit_flybody_policy
.venv/bin/python -m scripts.audit_flybody_policy --cached
```

The stdlib script uses bounded source/metadata downloads, refuses a server that ignores a Range request, validates the graph hash, and writes [machine-readable evidence](../validation/flybody-policy-audit.json). Its ZIP-tail read incidentally includes a small part of the compressed weight member; it does not decompress or inspect those weights. Cached upstream source/graph bytes remain under ignored `tmp/flybody-policy-audit/`. Asset acquisition and inference, if subsequently executed, receive separate receipts.

## Exact observation and action boundary

Shapes below come from the released SavedModel's concrete function signature. Values are float32 with one leading batch dimension; the table omits that dimension. Source implementations are [body observables](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/fruitfly.py) and [task reference observables](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/base.py).

| Dictionary key, prefixed `walker/` | Shape | Meaning and units |
|---|---:|---|
| `accelerometer` | 3 | Ideal thorax acceleration, cm/s² |
| `actuator_activation` | 59 | Filtered actuator state, in native actuator units |
| `appendages_pos` | 21 | Six claws plus head, flattened body-relative positions, cm |
| `force` | 18 | Six 3D tarsal force sensor readings, dyn |
| `gyro` | 3 | Thorax angular velocity, rad/s |
| `joints_pos` | 85 | Observable hinge positions, rad |
| `joints_vel` | 85 | Corresponding velocities, rad/s |
| `ref_displacement` | 65 × 3 | Desired root positions relative to current body frame, cm |
| `ref_root_quat` | 65 × 4 | Desired orientations relative to current body quaternion |
| `touch` | 6 | Claw touch force, dyn |
| `velocimeter` | 3 | Ideal body-frame linear velocity, cm/s |
| `world_zaxis` | 3 | World vertical expressed in body coordinates, dimensionless |

The non-reference inputs total **286**, and references add **455**, yielding **741**. Use the SavedModel's 741 contract, not the main article's 286-dimensional shorthand. The supplement agrees with the graph. The gravity-direction vector is dimensionless despite the supplement's `cm` label. The sensory inputs are idealized motor-policy feedback; they must not be relabelled as measured receptor firing or injected wholesale into the full male neural graph.

Actions are **59 canonical values**, with class order defined by the source: adhesion first, then head, abdomen, legs in this preset. There are six claw adhesion controls, three head controls, two abdomen controls, and 48 leg controls including coupled tarsal motion. Exact per-actuator names must be read from the compiled `action_spec().name`, never guessed from anatomical order. The [author inference notebook](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/docs/fly-env-examples.ipynb) applies `SinglePrecisionWrapper` and `CanonicalSpecWrapper(clip=True)`, then takes the distribution **mean** through `TestPolicyWrapper`.

For an inference-only implementation, [the author's `canonical2real`](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/task_utils.py) specifies

`native = minimum + 0.5 * (clip(mean, −1, 1) + 1) * (maximum − minimum)`.

Do not pass the 59 means directly as radians or assume compiled MuJoCo actuator order equals policy action order. `FruitFly.apply_action` performs the source's class-to-control permutation. Native position and adhesion controls pass through 10 ms and 7 ms activation filters respectively. [Walking task defaults](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fly_envs.py) use 2 ms control and 0.2 ms physics steps, disable wing actuation, and keep 64 future reference steps. Original geometry is centimetres/grams/seconds, gravity −981; convert **mm/s ÷ 10** at our boundary. Keep dynamics, contacts, filters and action ranges frozen for the first comparison. The present FlyGym FlyBody adapter uses a modified configuration and is not a demonstrated drop-in host for these weights.

## Can neural activity supply the steering?

**Yes, architecturally; this integration is proposed, not yet tested.** The source provides an [inference trajectory loader](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/trajectory_loaders.py) that needs only root `qpos[T,7]` and `qvel[T,6]`, with no measured leg trajectory or training dataset. `walk_imitation(ref_path=None)` uses it automatically. The [synthetic trajectory generator](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/synthetic_trajectories.py) already takes speed and yaw speed. This avoids downloading the 3,019,999,672-byte walking training dataset for a first rollout.

Proposed causal boundary:

1. Our connectome-derived readouts produce a bounded desired forward speed and yaw rate, with explicit engineering calibration.
2. An adapter advances an internal desired planar pose using those present/past commands. It constructs 65 reference poses at 2 ms intervals by holding the **current** command over the 128 ms horizon. Those are intended future poses, not future sensory measurements. Preserve pose continuity; a changing command updates only the unexecuted preview.
3. Feed relative desired poses plus FlyBody's own physical feedback to the frozen policy. Body state may convert coordinate frames and supply motor feedback; external food/landmark positions may not select desired headings or speed. Keep a test that translating food while holding receptor/neural histories fixed cannot alter policy commands.
4. Interpolate/hold the slower neural command at the 500 Hz policy clock; simulate ten physical steps per action. Log command history, internal desired pose, clipping and policy feedback separately from neural observations.

Keep a fixed standing height/pitch reference explicitly labelled as motor-surrogate configuration. A rolling reference buffer and long-duration episode management require a task adapter: the stock loader replaces a whole trajectory before reset, and its default 300-step snippet gives only about 0.47 s of usable control after preview padding. Do not reset the physical body whenever a neural command changes. Also flag a source helper issue: its quaternion-velocity calculation uses `quat2Vel(dquat, dt=1)` after creating `dquat` for a 2 ms step, yielding a per-step rotation rather than rad/s. Actual pose previews remain usable, but derive aligned angular velocity correctly if consuming its `qvel`; the default walking task does not initialize physical qvel from that synthetic value.

The policy contains learned motor intelligence and ideal body feedback. Even successful connectome-driven locomotion remains a **full neural model connected to a learned motor surrogate**, not a claim that all motor output emerged from reconstructed VNC-to-muscle circuitry. The original body and walking training selection are female-derived; a male brain connected to it remains a labelled anatomical surrogate.

## What has been validated biologically upstream?

The paper reports approximately 13,000 training and 3,200 test walking trajectories, from female 150 fps top-view recordings. It compares test-trajectory tracking, stance counts versus speed, and relative swing onset phases; synthetic turns show stride asymmetry, with a reported left/right foreleg asymmetry. Test trajectories are not documented here as held-out animals. Recorded 2D keypoints were lifted using assumed height/pitch and swing arcs, then regularized inverse kinematics. Consequently the policy's tibia ROM is not independently measured 3D joint-angle ground truth. [Paper](https://www.nature.com/articles/s41586-025-09029-4), [Figure 3](https://www.nature.com/articles/s41586-025-09029-4/figures/3).

Numerical caution: the article text reports median position error **0.4 cm** and orientation error **4°**. Its position value exceeds the stated 0.3 cm training termination radius; evaluation can disable that radius. We have not resolved the figure/source-data units or reproduced those errors, so do not silently replace centimetres with millimetres or use this value as an acceptance threshold. No exact author train/test index manifest was found in the inspected source. Their evidence establishes a useful external motor baseline, not a head-to-head victory over our controller. [Paper](https://www.nature.com/articles/s41586-025-09029-4).

## Comparison with our measured deficits

Our [native 800 Hz benchmark](freewalking-benchmark.md) uses a different, pooled mixed-sex running dataset with no per-fly sex assignment. The fixed-CPG trial showed:

| CPG condition | Mean speed, mm/s | Smoothed absolute yaw, °/s | Six-leg tibia ROM MAE, ° |
|---|---:|---:|---:|
| Baseline drive 0.5 | 9.36 | 92.70 | 31.15 |
| Baseline drive 1.0 | 18.41 | 220.82 | 11.87 |
| Full source amplitude + fitted cadence, low command | 10.15 | 141.20 | 8.80 |
| Same candidate, high command | 14.98 | 170.47 | 11.95 |

Those candidate changes increased low-command ROM but worsened low-command reversing yaw and lost high-command speed. Reducing adhesion did not rescue the tradeoff. This motivates a speed-dependent learned trajectory generator; it does not establish that FlyBody will fix the problem. FlyBody changes geometry, stance control, body stabilization and policy simultaneously, so a first comparison is of **two embodiment stacks**, not an isolated causal policy test.

The next experiment should retain these frozen results and use the same requested speeds, yaw signs, filtering and physical-stability diagnostics. Predeclare straight walking at 10/20 mm/s and left/right turns at 20 mm/s, two seeds, a zero-command hold and command withdrawal. Measure median speed, signed and absolute yaw separately, leg-cycle frequency, actual contacts/slip, actuator saturation and tibia ROM. Align FlyBody tibia flexion sign and units using joint axes/FK; raw joint offsets across models are not interchangeable. Score all metrics and failures rather than optimizing one after seeing outcomes. Reuse the already declared per-animal split; label the comparison exploratory because the pooled benchmark has been inspected. Male-specific fidelity cannot be inferred from these data.

## Compatibility and compute

The [repository extra](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/pyproject.toml) pins TF 2.8.0, TFP 0.16.0, Reverb 0.7.0 and NVIDIA cuDNN while leaving `dm_control` unpinned. **Do not install it into our Python 3.12 / NumPy 2 / FlyGym environment.** Live PyPI metadata verifies:

| Route | Evidence / constraint | Recommendation |
|---|---|---|
| Original Linux x86 CPU | TF 2.8.0 and Reverb 0.7.0 have CPython 3.10 Linux x86 wheels; archived model exported with TF 2.8 | Closest numerical reference; pin every resolved dependency and MuJoCo version, because upstream is not fully locked |
| Original extra on native Apple Silicon | `tensorflow==2.8.0` has no arm64 wheel; Reverb 0.7 has only Linux x86 wheels | Not a supported direct install |
| Legacy `tensorflow-macos==2.8.0` | arm64 wheels exist for older Python, but no CPython 3.10 wheel; FlyBody declares Python ≥3.10 | Not an unchanged compatible combination |
| Modern native CPU inference only | TF 2.15.1 has CPython 3.10 macOS arm64 wheel; its NumPy constraint accepts 1.26.4; TFP 0.23 is tested upstream against TF 2.15 | Bounded compatibility trial, not assumed parity; omit Acme/Reverb/Ray/NVIDIA extras and replace only batching/action wrappers exactly |
| NumPy/PyTorch conversion | All graph operations are standard; weights are small | Useful fallback after reference output parity; no invented/retrained weights or approximate architecture |

[TF 2.8 metadata](https://pypi.org/pypi/tensorflow/2.8.0/json), [legacy macOS metadata](https://pypi.org/pypi/tensorflow-macos/2.8.0/json), [Reverb 0.7 metadata](https://pypi.org/pypi/dm-reverb/0.7.0/json), [TF 2.15.1 metadata](https://pypi.org/pypi/tensorflow/2.15.1/json), [TFP 0.23 release](https://github.com/tensorflow/probability/releases/tag/v0.23.0).

Recent [Reverb source-build documentation](https://github.com/google-deepmind/reverb/blob/master/reverb/pip_package/README.md) now mentions Apple Silicon support targeting TF 2.21; that does not make the pinned **0.7.0** wheel compatible. Avoid a broad “Reverb never runs on Macs” claim. The notebook's `TestPolicyWrapper` imports Acme and training classes at module import time; an inference-only wrapper must avoid that transitive chain. Restoring the graph may still fail because its TFP composite-type serialization changed; test it, and report the exact error instead of silently dropping distribution state. [Apple's guidance](https://developer.apple.com/metal/tensorflow-plugin/) notes that small batches can be faster on CPU than GPU, so Metal is unnecessary for this first trial.

The author measured **13.73 ms wall time per 2 ms walking control step** on one Xeon E5-2697 v3 core: policy 4.31 ms, environment 4.49 ms, MuJoCo 4.64 ms. That is approximately 6.865 wall seconds per simulated second, without our brain. It is not a benchmark of this Mac. The first trial needs one CPU process, the ~5 MB walking asset, and an isolated environment; the TF 2.15.1 arm64 wheel alone is 205.7 MB compressed, with further dependency/storage overhead. No training GPU is required for inference. Training from scratch would reintroduce roughly a billion walking simulation steps and distributed CPU/GPU work. [Supplement, Table 5](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-025-09029-4/MediaObjects/41586_2025_9029_MOESM1_ESM.pdf), [paper](https://www.nature.com/articles/s41586-025-09029-4).

## License and execution boundary

The [repository code license](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/LICENSE) is Apache-2.0. The Figshare v4 collection metadata declares **GPL 3.0+**, including the supplied policy archive; the ZIP contains no overriding per-policy license file. Keep the downloaded weights and their provenance distinct from our code and preserve this license when sharing derived assets. The article's CC-BY license does not automatically relicense its separately hosted weights. The independent freewalking dataset still has an unidentified data license; this audit does not redistribute it.

At this audit boundary, inference and physical superiority are **unverified**. The concrete next step is a separate CPU SavedModel load, repeated deterministic finite 59-action check, exact compiled observation/action comparison, and a short original-body synthetic walk. Only after that should we run the fixed comparison and discuss integration. Body sensors, ingestion, grooming, vision, neural inputs and runtime defaults remain unchanged.
