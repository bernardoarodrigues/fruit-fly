# FlyBody walking: isolated Apple Silicon inference trial

The released walking policy **loads and drives the original FlyBody on this arm64 Mac**, using a separate CPU environment. The saved graph and all trained tensors are unchanged. This is a 0.5 s compatibility/physics smoke, not a biological benchmark or a replacement of the current body. See the earlier [feasibility audit](flybody-policy-feasibility.md) and the separate [predeclared trial plan](../validation/flybody-inference-plan.json).

## What was executed

Python 3.10.21, TensorFlow 2.15.1, TensorFlow Probability 0.23.0, dm-control 1.0.27, MuJoCo 3.2.7 and NumPy 1.26.4 run in ignored `tmp/flybody-env`. All 88 resolved packages and distribution hashes are frozen in [requirements](../validation/flybody-inference-requirements.lock). No Acme, Reverb, Ray, CUDA or Metal package was needed. TensorFlow has no visible GPU and uses one intra-op and one inter-op CPU thread. The environment occupies approximately 1.6 GB locally; its dependency installation took about two minutes, excluding initial package import/cache startup. The main `.venv` and runtime dependencies are unchanged.

Only the three walking SavedModel members were acquired: 4,640,367 bytes of compressed archive ranges. Their SHA-256 and ZIP CRC checks are in the [acquisition receipt](../validation/flybody-walking-acquisition.json). No training dataset was downloaded. All 223 files under the pre-existing FlyBody package, plus its license and project definition, were verified against Git object hashes at commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`; local SHA-256 values are in the [source manifest](../validation/flybody-source-manifest.json). These include existing body assets; this trial did not reacquire their 191 MB of source/package data.

## Exact compatibility repair

An ordinary `tf.saved_model.load()` failed because the archive names its distribution TypeSpec as `tensorflow_probability.python.distributions.independent.Independent_ACTTypeSpec`, which TFP 0.23 does not register under that name by default. Explicitly importing the distribution classes did not resolve it. The preserved [initial error](../validation/flybody-inference-initial-load.json) records that failure.

The public TFP decorator restores the old registration for the **same** `Independent` class:

```python
tfp.experimental.auto_composite_tensor(tfp.distributions.Independent)
_ = tfp.distributions.Normal
policy = tf.saved_model.load("data/raw/flybody/walking")
```

TFP's deserializer supports the archive's version-3 composite state. This shim changes an in-process Python type registration; it does not rewrite the SavedModel, replace functions, drop trained variables, or approximate the network. The restored output contains the original location and scale tensors, and we take the deterministic mean as in the author's wrapper. It is still a newer TensorFlow runtime: numerical equivalence to a TF 2.8 execution has **not** been tested.

All 12 compiled observation keys and their shapes match the actual SavedModel (741 scalars). Body observations are explicitly cast from float64 to batched float32, reproducing the author's single-precision wrapper. All 59 action names and bounds were read from the compiled source body. Means undergo the author's canonical clipping and range transformation with float32 bounds, then the original `apply_action` permutation and actuator dynamics. Neither neural data nor food coordinates enter this isolated constant-command experiment.

## Results

[Full result and contract](../validation/flybody-inference-probe.json) includes the exact action order, ranges, source/plan/script hashes, initial distribution, timings and trace hash.

- Ten repeated calls on the identical physical observation produced **identical mean actions**; initial means and positive standard deviations were finite.
- A separate NumPy implementation of the deterministic mean used all the actual checkpoint tensors, preserved duplicate-name head identities, and read LayerNorm epsilon from the actual graph. Across 250 recorded physical observations, maximum absolute NumPy-versus-SavedModel error was **8.106 × 10⁻⁶**, RMS **1.191 × 10⁻⁶**, passing the predeclared 10⁻⁵ tolerance. TF batch-versus-single-step roundoff was 6.914 × 10⁻⁶. This verifies the arithmetic path under TF 2.15.1, not an independent TF 2.8 reference.
- A 20 mm/s straight command ran for **0.5 simulated seconds**: forward displacement **10.261 mm**, mean planar speed **21.086 mm/s**, median **19.263 mm/s**. Minimum root height was **1.294 mm** and minimum body-up dot world-up was **0.9928**.
- The body had **3–6 actual floor contacts** at every sampled control step, finite positions/velocities and **zero MuJoCo warnings**.
- **50.7% of canonical action scalars exceeded ±1** before the author's clipping, with maximum absolute mean about 6.0. This is reported rather than hidden. It does not imply native actuator-force saturation; that requires separate force/range telemetry.
- The first timed rollout took **1.56 wall seconds / 0.5 simulated seconds** (~0.32× real time), including policy, physics and telemetry but excluding model build/load. Subsequent repeated timing is in the JSON. This does not include the male neural graph, rendering or sensory chemistry.

The stored trace is generated simulation output in ignored `runs/flybody-inference-probe/trace.npz`. It includes physical poses, qpos, actions, observations and contacts. No source behavioral recording is redistributed. The final report uses full quaternion heading geometry; a preliminary reporting-only calculation was corrected and the identical physical smoke repeated.

## Reproduce in the isolated environment

With the existing pinned source checkout available:

```sh
uv venv --python 3.10.21 tmp/flybody-env
uv pip sync --python tmp/flybody-env/bin/python --require-hashes validation/flybody-inference-requirements.lock
.venv/bin/python -m scripts.acquire_flybody_walking
tmp/flybody-env/bin/python -m scripts.probe_flybody_inference --repo /tmp/fruit-fly-research-flybody
```

The probe verifies every source/asset hash before execution, fails on mismatched input shapes, nonfinite actions/state, unexpected early termination, parity failure or MuJoCo warnings, and saves failure details. Use a fresh ignored environment for the setup commands; do not repurpose the project's primary environment.

The remaining decision is empirical: run the already described fixed straight/turn/rest/withdrawal comparison against our frozen CPG and mixed-sex running benchmark. The short smoke provides no reliable cadence/ROM distribution, long-duration drift test, command-withdrawal result or male-specific fidelity evidence. The policy remains a learned motor surrogate with idealized feedback and female-derived body/training data. Its separately hosted asset license remains **GPL 3.0+**, distinct from the **Apache-2.0** source-code license.
