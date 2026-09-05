# FlyMimic muscle models: feasibility for M8

**Useful now as an isolated mechanical substrate; insufficient for calibrated
MaleCNS motor-neuron control.** A released source model compiles locally and
produces causal muscle-to-joint responses. Its control is continuous excitation,
with no released MaleCNS body-ID-to-motor-unit mapping or spike-to-excitation law
in the inspected code. No production body, neural coupling, or policy was
installed or changed.

The referenced [arXiv v2](https://arxiv.org/abs/2509.06426v2) is dated September
2025. The current publication is the [ICLR 2026 conference
paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/222843b731e2c7813291586e2b39fe89-Abstract-Conference.html),
distinct from the authors' 2026 antennal-grooming circuit paper. The published
PDF was downloaded, its text inspected, and methods/Figure 2 on page 4 checked
visually.

## Released assets and actual control interface

Inspected [FlyMimic commit
9ea1131](https://github.com/gizemozd/FlyMimic/tree/9ea1131626cd76f7203b74076ef8f0e9cab30bef),
under Apache-2.0. The complete GitHub tree was obtained without truncation.

| Released item | Verified scope |
|---|---|
| Five muscle MJCF variants, approximately 50 KB each | Each contains **15 left-foreleg muscle actuators and 15 spatial tendons**; 14 hinge coordinates include seven right-foreleg coordinates locked by equality constraints. No free body joint. Passive-property variants alter armature, damping, and stiffness. |
| `best_combined_cvt3_torque.xml` | Seven direct joint actuators for the comparison model. |
| `opensim/best_combined.osim` and `best_combined_full.osim` | Both contain 15 `Millard2012EquilibriumMuscle` objects; “full” does not mean all six legs have optimized muscle actuation. |
| Mesh assets | The audited MJCF references 71 STL files, totaling **13,961,614 bytes**; downloaded and hashed individually. |
| Mocap arrays | Two indexed clips (`0001`, `0002`) with joint/body-state arrays are present in the tree. This audit did not load their trajectories or establish donor identity. |
| `logs/demo_model.zip` | A 10,630,172-byte repository blob is present. It was not downloaded/deserialized or executed. The README also links a Dropbox policy archive; those additional weights were not validated. |

The [muscle task
code](https://github.com/gizemozd/FlyMimic/blob/9ea1131626cd76f7203b74076ef8f0e9cab30bef/flymimic/tasks/fly/mocap_tracking_muscle.py)
uses a 2 ms control step and observes joint/body state, muscle state, and remaining
clip time. Its `play=True` mode directly overwrites joint positions from mocap;
that mode cannot prove muscle causality. The inspected training configuration
requests 30 million steps, while the published experiment describes 15 million;
defaults alone do not reproduce the paper's experiment. Policy commands are not
identified motor-neuron activity.

The README's [OpenSim development/optimization repository
link](https://github.com/gizemozd/neuromechfly-muscles) returned **404**. Thus,
released OpenSim models are available, but the linked original optimization
pipeline was not retrievable. Do not claim complete optimization reproduction.

The installed FlyGym **2.1.0** already exposes an experimental
[`MusculoskeletalFly`](https://neuromechfly.org/api_reference/flygym/compose/fly/musculoskeletal/)
wrapper and bundled muscle MJCF. It switches the body model; it does not overlay
muscles on the existing `BodyRuntime`. Its topology uses different names and
does not provide all existing per-leg sensors/adhesion interfaces. The wrapper
was inspected but not instantiated. The tests below use the pinned original
MJCF directly, without an environment upgrade, RL stack, or wrapper mutation.

## Biological and numerical limits

The paper represents 12 of 19 muscle groups with 15 foreleg MTUs, including fast
tibia flexor/extensor; tibial and trochanter muscles are omitted. It assumes rigid
tendons, zero pennation, and default muscle curves where fly measurements are
missing. Force/velocity and geometry parameters are estimated or optimized against
kinematics. Mid/hind-leg reconstructions were not optimized behaviorally. The
published contact-enabled demonstration drives **only the left foreleg** with
muscles and the other five legs with recorded-trajectory PD control. This is
narrower than the project page's “front legs” wording; use the paper's explicit
Appendix A.8 protocol. [Published paper, §§3.2, 6, A.1, A.4–A.8](https://proceedings.iclr.cc/paper_files/paper/2026/file/222843b731e2c7813291586e2b39fe89-Paper-Conference.pdf).

The underlying Kuan X-ray study used 1–7-day-old adult **female** flies;
Dinges' anatomical study also examined females.
[Kuan et al., Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC8354006/);
[Dinges et al., author PDF](https://kups.ub.uni-koeln.de/25156/1/Blanke%20in%20Dinges%202020.pdf).
The inspected FlyMimic paper/code did not resolve the custom scan and released
mocap clips' sex. This is a composite anatomical/model substrate, not a measured
male musculature or male-specific muscle calibration.

The source MJCF uses gravity `(0,0,-9801)`, mesh scale `1000`, and compiled total
mass **0.002494271478 native mass units**. The OpenSim file labels length `m`
and force `N` yet has fiber lengths around 0.1–0.4 and gravity magnitude 9806.65.
Those metadata do not establish a consistent physical SI conversion. Preserve
the native numbers and audit the original scaling/converter provenance before
reporting newtons, newton-metres, or a biological maximum force. MuJoCo compilation
did not repair those conventions. The model's [actual actuator
entries](https://github.com/gizemozd/FlyMimic/blob/9ea1131626cd76f7203b74076ef8f0e9cab30bef/flymimic/assets/models/best_combined_arm_cvt3.xml#L530)
override the default activation constants with **0.0001/0.0004 seconds** and
control range **[0.0001,1]**.

## Source-native mechanical assay, completed

Run the [audit script](../scripts/audit_muscle_twitch.py) against a checkout or
downloaded asset directory at the pinned commit:

```sh
.venv/bin/python scripts/audit_muscle_twitch.py --source-dir tmp/musculoskeletal-audit/FlyMimic
```

The script rejects a changed source MJCF hash. It initializes the supplied
`default-pose`, retains Euler integration at **0.1 ms**, and compares a baseline
with each of 15 muscles receiving excitation **0.05 during 5–10 ms**, ending at
30 ms. There is no equilibrium burn-in. Every other requested command is zero,
which the source clamps to **0.0001**, so the baseline retains excitation,
passive muscle forces, gravity, and initial transients.

All 15 activation states respond; **14 produce joint-angle differences above
1e−9 rad**. `LFC_sternal_anterior_rotator` has a maximum paired motion of
4.66e−15 rad and force difference 2.09e−11 native units. Its active gain is zero
at the sampled lengths/velocities, but nonzero when queried at the same lengths
with zero velocity. This supports a velocity-dependent model limitation in this
assay, not an absent actuator or biologically inactive muscle.

The transmission Jacobian agrees with a central finite difference of tendon
length to **5.00e−9 native length/rad** (epsilon 1e−7 rad); multiplying it by
actuator force reconstructs generalized actuator force. Before the pulse,
paired joint positions match exactly. All saved states are finite and no MuJoCo
warnings occurred. [Results and all eight integrity checks](../validation/muscle-twitch/results.json);
[full sampled trajectories](../validation/muscle-twitch/traces.npz);
[inspected plot](../validation/muscle-twitch/twitch-audit.png).

The declared timestep diagnostic changes **only the in-memory timestep** for
`LFTibia_flex_93434`, repeating the same physical pulse schedule:

| dt | Peak activation | Peak target force magnitude, native | Maximum joint-angle difference versus 0.025 ms at common times |
|---:|---:|---:|---:|
| 0.1 ms, source default | 0.0998699 | 7.03013 | 0.000710939 rad |
| 0.05 ms, diagnostic | 0.0500000 | 3.60491 | 0.000375898 rad |
| 0.025 ms, diagnostic reference | 0.0500000 | 3.60491 | 0 by definition |

For rising activation, the supplied unsmoothed MuJoCo dynamics use
`da/dt = (u-a)/(tau_act*(0.5+1.5*a))`; falling activation instead uses
`tau_deact/(0.5+1.5*a)`. Control and the activation used in the time-constant
factor are clamped internally. Near rest, the source's effective rising time
constant is about **0.05 ms**, smaller than its **0.1 ms Euler step**. The scalar
formula matches installed MuJoCo exactly on the audited 18 input/state pairs.
[Official documentation](https://mujoco.readthedocs.io/en/3.3.2/modeling.html#muscle-actuators);
[MuJoCo 3.9.0 source](https://github.com/google-deepmind/mujoco/blob/3.9.0/src/engine/engine_util_misc.c).
The original overshoot is retained, and the finest diagnostic is not established
as converged ground truth. Motion similarity alone can conceal a large transient
force error.

## Remaining M8 bridge and next isolated assay

The loaded male annotations offer broad candidates, not an exact fast-motor-unit
crosswalk: `subclass=fl`, `type=Ti flexor MN`, `somaSide=L` selects body IDs
**807165, 809912, 818057, 819384, 909831**; left foreleg `Ti extensor MN` selects
**800636, 815344**. These exact labels do not specify which cells correspond to
the two named fast muscle actuators. Numeric suffixes `93434`/`93932` in source
muscle names must not be treated as MaleCNS body IDs. Neither a shared muscle
name nor summed firing identifies motor-unit recruitment or excitation strength.

The next defensible assay is a **fixed-body tibia flexor/extensor test** after
resolving units, numerical timestep adequacy, and the exact motor-unit crosswalk.
First constrain force–length–velocity and excitation dynamics against an
independent physiological dataset with preparation/sex metadata. Then declare
and calibrate a spike-to-excitation model for those motor units. Compare paired
input-off, source-output-blocked, and muscle-disabled conditions while recording
neural events, excitation, activation, force, moment arms and joint motion.
Use held-out pulse trains and loads. Preserve the current CPG/position-control
baseline for comparison. This can advance M8 without claiming whole-fly muscle
control, natural recruitment, or male physiological fidelity.

## Source receipts

Research copies remain under ignored `tmp/musculoskeletal-audit/`; no source
paper or third-party code was added to the project package. The source receipt
there lists URLs, byte counts, and SHA256 for downloaded code/models/meshes.
The versioned mechanical JSON retains every compiled asset hash and all actual
actuator parameter arrays. Selected small-source SHA256 values:

| Source at pinned FlyMimic commit | SHA256 |
|---|---|
| `LICENSE` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `best_combined_arm_cvt3.xml` | `59d7db31eb756c61661065c16cfbbb1e3400da1a9df8b1f02fe79dc87bd48724` |
| `opensim/best_combined.osim` | `091a173b9cfb26a64228935c6f6ebfc93c26a9425a0b5e5c1bb463c644cb89de` |
| `mocap_tracking_muscle.py` | `aa5e22c5b63052a42b32166c1aaefb725ab14f9ded9bbd31a90d3bdc68db66ac` |
| `pyproject.toml` | `a523a146f84a88f6ff4b4baf8d670f78c822936d28f481f4e78d1824a71c9716` |

Published PDF: 12,490,459 bytes, SHA256
`a136ef38a227eae78ab896846d57a2076734d42412ea9f4ea0e37f525fedd4b8`.
MuJoCo 3.9.0 `engine_util_misc.c`: 58,883 bytes, SHA256
`0e532965c14a8e0f405b5b718e1ce52261819137435e5b3d7c7ff8cf97d60068`.
