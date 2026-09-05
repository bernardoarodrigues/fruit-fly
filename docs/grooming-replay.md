# Measured grooming replay: implementation and evidence

The optional grooming body now executes one measured 0.5 s female trajectory through MuJoCo position actuators, with four supporting legs and explicit foreleg–antenna collisions. It supplies a **motor template**, not a learned motor controller or a validated reproduction of natural grooming. The default walking body is unchanged.

## What was acquired and mapped

The source is the author-selected `unilateral_left` container in Özdil et al.'s [public CC0 dataset](https://doi.org/10.7910/DVN/N8ITTG), linked by the [2026 primary article](https://doi.org/10.1038/s41467-026-72152-x). It contains 51 contiguous 100 Hz samples, source frames 4939–4989 (49.39–49.89 s), from a tethered female. [The acquisition and biological audit](grooming-model-audit.md) records exact source checksums, versions, licenses, recording metadata, and limitations. [The numeric provenance](../data/grooming/provenance.json) pins the current NPZ SHA256.

The 21 acquired angle channels remain unchanged in the data. The adapter uses only 14 foreleg channels and head roll/pitch. It holds head yaw at the neutral pose and leaves antennae rigid. Measured antennal angles are preserved for future validation but are not falsely treated as active motor outputs. No right-grooming example was invented by mirroring the left recording.

The numeric conversion is explicit in `fruitfly/grooming.py:source_joint_map`:

| Source | Current FlyGym mapping | Convention |
|---|---|---|
| `ThC` yaw/pitch/roll | thorax → foreleg coxa | Source global axes x/y/z, ordered yaw/pitch/roll |
| `CTr` pitch/roll | coxa → trochanter/femur | Source axes y/z |
| `FTi` pitch | trochanter/femur → tibia | Source y axis |
| `TiTa` pitch | tibia → tarsus1 | Source y axis |
| Right foreleg yaw/roll | Corresponding right joint | Negate: current FlyGym reverses these hinge axes |
| Head roll | `c_thorax-c_head-yaw` | Source physical x is called generic “yaw” in this FlyGym anatomy convention |
| Head pitch | `c_thorax-c_head-pitch` | Positive sign retained |

The [author SeqIKPy kinematic chain](https://github.com/NeLy-EPFL/sequential-inverse-kinematics/blob/f7f1dc9b09ce89c4f54b2005722d62f887623a7b/seqikpy/kinematic_chain.py), [head-angle implementation](https://github.com/NeLy-EPFL/sequential-inverse-kinematics/blob/f7f1dc9b09ce89c4f54b2005722d62f887623a7b/seqikpy/head_inverse_kinematics.py), and [body template](https://github.com/NeLy-EPFL/sequential-inverse-kinematics/blob/f7f1dc9b09ce89c4f54b2005722d62f887623a7b/seqikpy/body_config.py) corroborate these conventions. This is a pinned current author-code audit; the exact SeqIKPy commit used when preprocessing the 2025 source dataset is not established. FlyGym's pinned `add_joints` implementation defines the right-side sign reversal. Its current geometry is not identical to the source template.

Forward kinematics provide an independent check: replay the converted joint positions without running dynamics, then compare recorded femur/tibia/tarsus marker coordinates relative to each coxa. No rotation, scale, angle offset, or segment length was fitted. Across 306 marker samples:

| Conversion | RMS Euclidean marker error | Maximum error |
|---|---:|---:|
| Documented axis/sign mapping | 0.05763 mm | 0.09364 mm |
| Negative control without right-axis reversal | 0.34314 mm | 0.97090 mm |

The difference supports the foreleg sign/order conversion. It does not calibrate the head or antennae, and the nonzero residual remains material relative to these small structures. For example, the source template's foreleg coxa/tibia lengths are about 0.400/0.540 mm; the current target rig is about 0.365/0.518 mm.

A source integrity guard rejects any required channel jumping more than 30 degrees per 10 ms sample, and angles outside the generic IK domain ±180 degrees. The 30-degree threshold is an **engineering rejection rule**, not an experimentally measured velocity limit. No samples are silently clipped, smoothed, or repaired. The selected example's largest mapped jump is 15.056 degrees. The longer Figure 1C and bilateral snippets fail this rule and are currently rejected; they remain available as unmodified research data.

## Physics and the standalone diagnostic

Run:

```sh
.venv/bin/python scripts/replay_grooming.py
```

This writes a [numerical receipt](../validation/grooming-replay-diagnostic.json), [tracking plot](../validation/grooming-replay-diagnostic.png), [midpoint image](../validation/grooming-replay-diagnostic-frame.png), and [video](../validation/grooming-replay-diagnostic.mp4). The video displays the single 0.5 s traversal at one quarter speed; it does not loop the trajectory. This harness stops after the measured endpoint, whereas `BodyRuntime` also executes a smooth exit.

The frozen diagnostic uses MuJoCo 3.9.0, FlyGym 2.1.0, timestep 0.0001 s, Newton solver with 100 iterations and 5 no-slip iterations, gravity −9810 mm/s², position gain 45, actuator force limit ±65 native units, leg spring/damping 0.05/0.06, passive distal tarsal spring/damping 7.5/0.01, and adhesion gain 40. These values are inherited engineering settings for this body; they are not recovered grooming-paper parameters. Four supporting legs retain the preprogrammed standing pose, and foreleg adhesion is off. The 72 explicit self-contact pairs connect six foreleg segments (tibia and tarsus1–5) to each pedicel, funiculus, and arista on both sides. Antennal contacts use FlyGym's default contact parameters.

The standalone replay settles for 0.25 s, enters over 0.25 s using cubic smoothstep, then linearly interpolates the source samples at the physics timestep. Its measured-interval diagnostics were:

| Quantity | Result |
|---|---:|
| Joint tracking RMS / maximum | 2.182° / 10.712° |
| Thorax height range | 0.92314–0.93009 mm |
| Net displacement | (0.00299, −0.00084, −0.00695) mm |
| Mean normal support, LM/LH/RM/RH | 44.77 / 40.35 / 44.91 / 40.03 native g·mm/s² |
| Finite state throughout | Yes |

The support forces are strongly affected by the artificial adhesion gain; they are not measured fly forces. Contacts are read from actual MuJoCo constraints with positive normal force, including the solver's compliant contact margin, and are never inferred from the source's behavior name. Both left and right antennal structures receive contact in this diagnostic despite the `unilateral_left` container label. Target selectivity is therefore **not validated**. The rigid antennae, geometry differences, missing passive parameters, and possible head-angle approximation matter for that conclusion.

The published paper instead used passive antennal spring/damper joints, behavior-specific rest poses, a different MuJoCo/FARMS setup, and restricted contact scope. A pinned runnable FARMS configuration sufficient to reproduce it was not recovered. The implementation here must not be described as a replication of the paper's biomechanics or contact forces.

## Optional runtime API and gate semantics

```python
from fruitfly.body import BodyConfig, BodyRuntime

with BodyRuntime(config=BodyConfig(enable_grooming=True)) as body:
    observed = body.advance(1.1, behavior="groom")
    assert observed["grooming"]["completed_count"] == 1
    assert observed["grooming"]["state"] == "held"
    assert observed["motor"]["mode"] == "rest"
```

`grooming_trace_path` defaults to `data/grooming/unilateral_left.npz`; relative paths resolve against the repository/package parent. Loading verifies its numeric-file hash against adjacent provenance. Optional composition adds two head position actuators and 72 contact pairs. The walking controller still sees exactly 42 leg actuators in its original order, separately from the head. Default composition remains 42 position actuators plus six adhesion actuators; optional composition has 44 plus six. Body sex/provenance labels remain the female-derived surrogate.

The reusable `GroomingPlayback` has only a boolean gate and current actuator targets as control inputs. It has no food coordinates, odor gradients, neural IDs, or behavior-selection policy. `BodyRuntime.advance(..., behavior="groom")` supplies the gate; root-level neural selection is a separate assay/decoder.

| Phase | Meaning |
|---|---|
| `disabled` | Optional composition absent; a grooming request raises an error |
| `ready` | Standing/other requested behavior; a new rising gate can start |
| `entering` | 0.25 s smoothstep from current targets to the source start |
| `playing` | One 0.5 s source-time traversal |
| `exiting` | 0.25 s smoothstep from current/endpoint targets to standing |
| `held` | Request remains high after exit; standing, disarmed, no repetition |

Withdrawal during entry/play increments `cancelled_count`, initiates exit from the current targets without a discontinuity, and prevents completion. `completed_count` increments only after the measured traversal reaches its endpoint. Reasserting a gate during exit does not queue another playback. A new rising request after withdrawal/exit is necessary for another traversal. Reset clears gate state and diagnostics. The engineering blend durations are not behavioral timescales inferred from the recording.

`observation["grooming"]` exposes `enabled`, `state`, `armed`, `requested`, `actual_active`, `source_time_s`, `source_duration_s`, `completed_count`, `cancelled_count`, and a `fidelity` string array. `motor.mode` reports `groom` only during entry/play/exit and `rest` in the held phase, avoiding a false appearance of continued grooming after the source ends. Source time is null in ready/held.

Contact telemetry includes instantaneous `contact_count` (distinct active geometry pairs), `contact_by_pair` (positive normal force), cumulative `contact_s` (time with any such force), and `contact_s_by_pair`. Cumulative time includes entry and exit as well as the measured interval; per-pair durations may overlap and must not be summed as total elapsed contact time. Tracking reports sample count, RMS and maximum absolute degrees, accumulated only during measured playback. `snapshot.grooming_reference` retains source metadata/checksum and frozen control settings. These diagnostics expose actual physics without routing privileged source or arena coordinates to the neural engine.

In an optional-body gate-only test after 0.1 s standing, one request produced 0.408 s cumulative contact, 2.151° RMS/10.707° maximum tracking error, and exactly 5,000 measured physics samples. Standing without a request produced no foreleg–antenna contact. These are direct-gate body checks, not a claim that connectome activity naturally generates grooming. Root-level spike-triggered and readout-mute interventions are recorded separately.

Focused validation:

```sh
.venv/bin/python -m pytest tests/test_grooming.py tests/test_physiology.py -q
```

Tests exercise source hash/IK rejection, recorded-marker conversion against a sign-error control, no tonic repetition, withdrawal and rearming, actual contact forces, supporting legs and finite state, reset, resumed walking, actuator-order separation, and existing default body/physiology/contact/vision behavior. No empirical grooming force, fatigue, dust-removal, antennal elasticity, or male kinematics claim follows from these tests.
