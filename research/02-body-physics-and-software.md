# Body, physics, and software audit

Research date: 2026-09-04 (America/Los_Angeles). Primary papers, official documentation, and current source code were checked. “Documented” means upstream claims or code inspection; “tested” means actually executed on this machine. The accompanying `sources-body.json` records versions, links and download metadata.

## Recommendation

Use **MuJoCo with FlyGym 2.1.0 and the NeuroMechFly body** for the first walking, sensory, two-animal arena. Keep a separate, pinned **original FlyBody** reference environment for flight and its published trained controllers. Evaluate FlyGym's experimental FlyBody adapter after the baseline is stable; it could later unify the body interface. This is an engineering choice based on the present APIs and the successful local smoke run, not a claim that one body is biologically complete.

Neither stack supplies reproduction, full digestive physiology, endocrine regulation, all sensory transduction, or a fully connected nervous system. A walking controller is a replaceable surrogate for motor circuits. It cannot be presented as a reconstructed ventral nerve cord (VNC).

## Exact audited versions

| Project | Inspected commit | Current role |
|---|---|---|
| TuragaLab/flybody | `d015e9bfe441bd90ae431bac24c55cb74bdbce26` | Published whole-body walking/flight model; separate TensorFlow policy stack |
| NeLy-EPFL/flygym | `38c8ec61034cd59bc5ba0de20688d4a3c0000d60` | Version 2.1.0; native MuJoCo `MjSpec`; local CPU smoke tested |
| NeLy-EPFL/flygym-gymnasium | `d285260a1c8a7b3494150cd1590f2c9fe4b5e06b` | Legacy 1.3.2 API; rich existing sensory examples; code inspected, not installed |

The NeuroMechFly **v2 scientific model** published in 2024 and **FlyGym 2.x software API** introduced in 2026 are different version concepts. Current FlyGym dropped Gymnasium compatibility; 2.1.0 additionally replaced `dm_control.mjcf` with MuJoCo's native `MjSpec`. Old `Fly`, `OdorArena`, observation dictionaries and examples do not import unchanged. Legacy imports now use `flygym_gymnasium`. The changelog dates 2.0.0 to April 2, 2026; the README says March, so prefer pinned code over an ambiguous month. [B03, B04, B05]

## What each model provides

### Original FlyBody

The Nature paper builds a **female** from confocal microscopy, with 67 body segments and 102 internal degrees of freedom. It demonstrates learned walking, flight, and vision-guided flight. Grooming is illustrated through inverse kinematics, which does not establish autonomous grooming control. Its low-level learned controllers are functional analogues of motor circuitry, not reconstructions of that circuitry. Wing actuation and aerodynamic forces are phenomenological; the rigid-body model does not explicitly reproduce wing flexibility, wake vortices, or turbulence. The authors caution that position/torque actuator commands should not be interpreted directly as biological muscle signals. [B01]

Independent XML inspection counted **67 bodies, 102 hinge joints, one free joint, 78 actuators, and 15 explicitly declared sensors** in the complete asset. The asset includes articulated rostrum/haustellum and left/right mouth structures named `labrum`, plus mouth adhesion actuators. Those names are software identifiers; feeding success is not implied. No named genital/ovipositor system was found in the inspected asset. Simulation sensors include accelerometer, gyro, velocimeter, force and touch types; joint state access provides additional observations. [B02]

Walking task defaults are 0.2 ms physics and 2 ms control steps; flight defaults are 0.05 ms physics and 0.2 ms control steps. The bare XML instead defaults to 0.1 ms. Task presets can freeze joints; do not quote the full body's degree count as the active policy dimension. Original FlyBody uses centimetres, grams and seconds; gravity is −981 cm/s². [B06]

### NeuroMechFly / current FlyGym

NeuroMechFly's geometry is also female-derived, originating in micro-CT imaging. The 2024 paper demonstrated sensory-guided walking, path integration, head stabilization, complex odor plume tracking, and following another fly through a connectome-constrained visual model. These demonstrations do not constitute a whole-brain simulation, courtship or reproduction. [B07]

Current `flygym.Simulation` offers a shared CPU world with multiple named flies; API methods read body positions, joint state and contact forces. `make_locomotion_fly` configures a legs-only body and position actuators. `HybridTurningController` uses CPGs, recorded step patterns, and stumble/retraction corrections; two left/right drive values provide steering. Our two-fly model had 144 velocity degrees of freedom and 96 actuators. **Default fly geometry has contact masks disabled** and ground collisions are added as explicit pairs: merely adding two flies does not guarantee inter-fly contact. The prototype adds distinct collision masks and explicit floor/wall contacts. [B08, B09]

Current CPU vision exists: `fly.add_vision()`, `sim.get_raw_vision(...)`, and `sim.get_ommatidia_readouts(...)`. The latter returns left/right eye readings with yellow/pale channels. Vision in the GPU backend remains deferred according to the changelog. No olfaction module was found in the inspected 2.1.0 Python package. This is a bounded source audit, not a claim that olfaction could never be added. [B04, B10]

The experimental FlyBody adapter shares the composition interface and supports wing/abdomen joints and tendons, but is explicitly labelled incomplete. Its supplied walking tutorial uses 42 position-actuated leg degrees of freedom and disables adhesion because it produces rearing. The adapter converts the original centimetre geometry to millimetres, including rotational parameter scaling. It should not be assumed to reproduce the original trained-policy flight setup. [B11, B12]

FlyGym also now wraps **FlyMimic**, but this is an experimental **left-front-leg-only** muscle system: 15 Hill-type muscles and 15 spatial tendons. It swaps in a different model, rather than furnishing a complete muscle layer for all six legs. Its GPU helper probes backend support. This is a promising calibration/validation route, not evidence that all motor neurons can already drive a complete musculoskeletal animal. [B13, B14]

## Coverage and required extensions

| Function | Available foundation | Missing work / claim limit |
|---|---|---|
| Walking, turning, standing | NMF hybrid controller; FlyBody learned controllers | Validate speed, gait, slip, load and perturbation responses; document motor decoder |
| Climbing/adhesion | Contact and adhesion actuators | Active adhesion is an abstraction; tune stance/swing release and test walls/ceilings |
| Flight | Original FlyBody wing mechanics + trained policies | Takeoff/landing transitions, turbulent wake, and simultaneous walking/flight are separate integration work |
| Grooming | Articulated bodies, reachable poses, contact | Sensory hair/dust field, action selection and a tested autonomous motor controller |
| Feeding | Mouth geometry; FlyBody mouth actuators | Taste/contact gating, proboscis sequence, pumping/ingestion, food depletion and gut model |
| Courtship song | Wings and body geometry | Separate unilateral song motor patterns and a calibrated acoustic stimulus model |
| Mating/egg laying | Generic collision engine and articulated abdomen | Male genital/female ovipositor geometry, alignment, force limits, mating state, sperm/egg physiology |
| Full life cycle | No demonstrated integrated implementation found | Eggs/larvae/pupae require different anatomy and developmental models |

This table separates software foundations from proposed work. It is not a literature proof that every listed missing component is unknown in isolation.

For male/female embodiment, start with a labelled common body only for engineering tests. Then create morphology profiles with measured sex/strain/age size distributions, segment inertias, abdomen shape, reproductive structures, and sensory differences where documented. Recompute masses/inertias after changing geometry and revalidate controls. Merely rescaling a female mesh or changing a label does not establish a male digital twin. Keep morphology provenance independent of connectome provenance.

## Environment and sensory implementation

A **50 × 30 × 4 mm** walking chamber with two food patches, one non-food visual landmark, a textured floor and adjustable air flow is enough for initial experiments. The prototype implements its floor and four walls; food and biological stimuli belong in the next layer. This geometry is a proposed experimental arena, not a reconstruction of a specific published assay. A separate taller chamber is needed to validate free flight.

Represent each chemical as a nonnegative concentration field `C[k, x, y, z, t]`. Sample at antennae and palps in world coordinates, then apply receptor tuning, adaptation, saturation, latency and noise in a sensory adapter. Taste should depend on local contact at legs/proboscis, rather than airborne “food smell.” Never give the neural controller hidden food coordinates unless explicitly running an oracle baseline. Source identity and observer visualizations stay outside the animal's observation.

The legacy `OdorArena` supports multiple sources and odor dimensions, sampling four locations (two antennae/two palps). Its default inverse-square profile is a simple field, not a validated solution of odor transport. The legacy plume arena samples separately simulated HDF5 fields, with defaults of 0.5 mm grid spacing and 200 Hz time sampling. These are useful implementation precedents that can be ported without adopting the old simulator API. [B15, B16]

Proposed progression: begin with a bounded analytic Gaussian field to test interfaces; then use advection–diffusion with source flux, diffusivity, decay and physically stated boundaries; finally replay or generate intermittent plumes. Preserve plume time series so all model variants see identical stimuli. For contact pheromones, use a surface field and contact geometry rather than treating all chemicals as long-range airborne signals.

MuJoCo's fluid model computes phenomenological forces on moving objects. It does **not** evolve an air or odor grid; it therefore does not automatically generate food scent, wing-produced sound, or the odor plume carried by a wing wake. MuJoCo documents both inertia and ellipsoid approximations and recommends implicit integrators for velocity-dependent fluid forces. Retain published settings for reproduction runs and compare any changed integrator using a timestep convergence check. [B17]

## Installation and compute

**Smallest path verified here:** Python 3.12, base FlyGym 2.1.0, MuJoCo 3.9.0; no `warp`, RL or TensorFlow extra. Commands and pinned commit are in `prototype/README.md` and `prototype/requirements.txt`. The virtual environment at `/tmp/fruit-fly-body-smoke-venv` occupied ~448 MB after install; the shallow FlyGym clone ~15 MB and bundled assets ~4.1 MB. These are observed disk sizes on this machine, not general requirements.

Original FlyBody's base package requires Python ≥3.10 and pins NumPy 1.26.4. Its optional learning stack pins TensorFlow 2.8.0, TensorFlow Probability 0.16.0, Reverb 0.7.0, protobuf 3.20 and CUDA/cuDNN-related packages; README instructions use Python 3.10 and CUDA 11.8. The core body and the original learned-policy runtime are therefore different installation tasks. We cloned and inspected original FlyBody but did not claim its TensorFlow policy stack works on this arm64 Mac. Prefer a separate Linux environment for reference policy reproduction or perform a deliberately validated policy conversion. [B18]

FlyGym 2.1.0 requires Python 3.12–3.14, NumPy 2.x, MuJoCo 3.9.x. NVIDIA Warp/MJWarp is optional; it does not give this Mac Apple GPU acceleration. Legacy 1.3.2 instead requires Python 3.10–3.12, MuJoCo 3.2.7 and dm-control 1.0.27. Use separate environments; do not solve this by mixing incompatible versions in one interpreter. [B03, B05]

**Measured initial local smoke:** two walking bodies, 1 simulated second, 10,000 shared-world physics steps, 7.60 seconds wall time for controller+physics (~0.132× real time), excluding setup/warmup/render. Both moved roughly 13 mm; positions and velocities remained finite. A PNG was rendered successfully and visually inspected. This is not a long-duration, two-body contact, brain or biological behavior benchmark.

**Follow-up integration check:** independent review found that MuJoCo's derived contact/position caches needed explicit refresh before timestamped observations. The final scripts add `mj_forward()` synchronization. Re-executed from the project-local pinned environment, the body trial took 9.54 wall seconds and the body+stimulus trial 10.29 wall seconds per simulated second. Current results and traces are in `prototype/output/`; initial benchmark metadata in the source registry are retained as historical measurements. The stimulus example also labels taste as tarsal-only because this locomotion preset lacks proboscis–food collision pairs.

Upstream FlyGym advertises approximately 10× CPU and 300× GPU improvements over its previous implementation. Those are workload-specific upstream claims. GPU throughput summed over many independent worlds is not the latency of one world containing two interacting flies. Current source's GPU benchmark varies the world batch count and computes summed steps per second. Do not promise real-time brains from that number. [B19]

Proposed benchmark matrix: 1 vs 2 flies; 1/16/128 parallel worlds where applicable; no controller vs surrogate controller vs full neural model; vision off/100/200 Hz; odor off/analytic/plume; rendering off/30/60 FPS; walking vs flight. Record physics time, neural time, data transfers, sensory encoding, rendering, peak RAM/VRAM, contacts, solver warnings, and simulated time/wall time separately. Warm up compilation, repeat at least five runs, report median and p95. Include a shared two-fly contact case and a hard geometry case. Start with one-step/two-step-size agreement before relaxing precision or solver iterations. MJWarp has feature and memory limitations to check explicitly; GPU state transfers can dominate small workloads. [B20]

## Assets, licenses, download budget

Repository license files for FlyBody, FlyGym and MuJoCo declare Apache-2.0. However, **FlyBody's Figshare supplementary collection v4 declares GPL 3.0+**, including the listed trained-policy archives. Keep code, geometry, trained weights, behavioral recordings, and neural datasets as separate provenance/license entries. Do not label the entire assembled project Apache merely because the core simulator is Apache. The original repositories and external asset collections may provide different license grants; preserve the actual source used. [B21, B22]

Figshare API metadata retrieved live (compressed sizes; not downloaded):

| File | Bytes | Approx. decimal size |
|---|---:|---:|
| Trained fly policies | 6,537,720 | 6.54 MB |
| Flight imitation dataset | 12,880,076 | 12.88 MB |
| Walking imitation dataset | 3,019,999,672 | 3.02 GB |
| Flight controller reuse checkpoints | 31,979,537 | 31.98 MB |
| Confocal stacks | 1,243,490,469 | 1.24 GB |
| Grooming poses | 314,449 | 0.31 MB |

The current FlyGym package bundles simplified NMF meshes and downloads optional full-resolution meshes from EPFL's public S3-compatible endpoint. A live object listing reported ~14.03 MB NMF fullsize, ~140.21 MB FlyBody fullsize, and ~13.96 MB musculoskeletal meshes. Cache path can be set with `FLYGYM_ASSET_CACHE_DIR`. Its downloader checks object metadata/ETags; a reproducible project should additionally freeze its own asset manifest and SHA-256 hashes. The smoke run uses bundled simplified meshes and did not require these optional downloads. [B23]

## Derived insights and research hypotheses

1. **The interface is likely the first scientific bottleneck.** Two physical bodies already run on this Mac. Accurate receptor-to-neuron input and neural-output-to-muscle coupling remain substantial work even if a brain graph is available. This is a synthesis of the audit, not a measured neuroscience finding.
2. **Use two complementary motor baselines.** Compare identical sensory/brain models with a learned FlyBody decoder and a rule/CPG NMF decoder. If behavior changes mainly with decoder choice, attribute the result to embodiment assumptions instead of the connectome alone.
3. **Ablate source-location leakage.** Compare receptor-only control against an explicitly marked oracle. If only the oracle reaches food, the observation/learning problem remains unsolved even when the video looks convincing.
4. **Sex differences require separable interventions.** Swap morphology, neural population identity, circuit parameters and internal reproductive state independently. Any apparent sex-specific effect should survive checks that it is not simply a body-size or controller mismatch.
5. **Full flight + odor requires two environment models.** MuJoCo's wing force approximation and an odor transport model can be coupled, but adding the former does not automatically solve the latter. Initially document one-way coupling and omit wake effects rather than implying them.

These are proposed tests and implementation conclusions. They are not novel biological discoveries until tested against independent experiments.

## Sources

Reference IDs resolve to direct primary URLs and commit-specific code paths in `sources-body.json`.

- **B01:** [Vaxenburg et al., Nature 2025](https://www.nature.com/articles/s41586-025-09029-4).
- **B02:** [Original FlyBody complete XML](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/fruitfly/assets/fruitfly.xml).
- **B03:** [FlyGym 2.1.0 dependency definition](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/pyproject.toml).
- **B04:** [FlyGym changelog](https://neuromechfly.org/changelog/).
- **B05:** [Legacy API dependency definition](https://github.com/NeLy-EPFL/flygym-gymnasium/blob/d285260a1c8a7b3494150cd1590f2c9fe4b5e06b/pyproject.toml).
- **B06:** [Original FlyBody task constants](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/constants.py).
- **B07:** [Wang-Chen et al., Nature Methods 2024](https://www.nature.com/articles/s41592-024-02497-y); [author-hosted PDF](https://gizemozd.github.io/assets/pdf/2024_neuromechflyv2.pdf).
- **B08:** [Current world composition](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym/compose/world/base_world.py).
- **B09:** [Current locomotion helpers](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym_demo/complex_terrain/common.py).
- **B10:** [CPU simulation and vision methods](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym/simulation.py).
- **B11:** [Experimental FlyBody adapter](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym/compose/fly/flybody.py).
- **B12:** [Current FlyBody walking tutorial](https://neuromechfly.org/tutorials/5b_using_flybody_model/).
- **B13:** [Musculoskeletal adapter scope](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym/compose/fly/musculoskeletal.py).
- **B14:** [Özdil et al., FlyMimic preprint](https://arxiv.org/abs/2509.06426).
- **B15:** [Legacy simple odor arena](https://github.com/NeLy-EPFL/flygym-gymnasium/blob/d285260a1c8a7b3494150cd1590f2c9fe4b5e06b/flygym_gymnasium/arena/sensory_environment.py).
- **B16:** [Legacy odor plume arena](https://github.com/NeLy-EPFL/flygym-gymnasium/blob/d285260a1c8a7b3494150cd1590f2c9fe4b5e06b/flygym_gymnasium/examples/olfaction/plume_tracking_arena.py).
- **B17:** [MuJoCo fluid-force documentation](https://mujoco.readthedocs.io/en/stable/computation/fluid.html).
- **B18:** [Original FlyBody dependencies](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/pyproject.toml); [installation](https://github.com/TuragaLab/flybody).
- **B19:** [FlyGym project overview](https://neuromechfly.org/); [batch benchmark code](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym_demo/benchmark/time_gpu_simulation.py).
- **B20:** [MuJoCo Warp documentation](https://mujoco.readthedocs.io/en/stable/mjwarp/index.html).
- **B21:** [FlyBody license](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/LICENSE), [FlyGym license](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/LICENSE), [MuJoCo license](https://github.com/google-deepmind/mujoco/blob/main/LICENSE).
- **B22:** [FlyBody dataset v4 DOI](https://doi.org/10.25378/janelia.25309105.v4); [Figshare API](https://api.figshare.com/v2/articles/25309105).
- **B23:** [Versioned asset downloader](https://github.com/NeLy-EPFL/flygym/blob/38c8ec61034cd59bc5ba0de20688d4a3c0000d60/src/flygym/utils/assets_lazy_loading.py).
