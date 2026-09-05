# Independent review of FlyBody airflow geometry

The saved evidence supports a **proximal-antenna airflow geometry proxy** with the stated forward/left/up and wind-source conventions. An independent reconstruction from the pinned source XML reproduces the antenna-origin positions, point velocities, head rotations, and local airflow in all four probes. This is a geometry result; it establishes neither a distal receptor frame nor mechanical or neural wind calibration.

The [review script](../scripts/review_flybody_airflow.py) and [receipt](../validation/flybody-airflow-independent-review.json) contain **248 passing checks**, including all **223** files in the upstream source manifest. Review used saved JSON/NPZ arrays, source inspection, and NumPy rigid-body algebra. It did not import the producer, fruitfly runtime, learned policy, FlyBody, or MuJoCo, construct a simulator, or run physics or neural steps.

## Provenance and reconstruction

The [amended plan](../validation/flybody-airflow-plan.json), [producer result](../validation/flybody-airflow-geometry.json), producer script, and saved geometry form a matching hash chain. Both cached modules match their exact Git bytes at `f433f4f`; the upstream files match commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`. The review does not substitute later working-tree worker changes for those frozen files. The receipt hashes the evidence files, image, source manifest, retained failure, local MuJoCo header, and reviewer itself.

The independent calculation reads body offsets, normalized fixed quaternions, hinge order, joint axes, and inherited parameters from `fruitfly.xml`. It checks the nine head/antenna hinge definitions against the saved compiled joint table, including zero anchors and reference angles. Saved compiled addresses select the coordinates in each full 116-element `qpos` and 114-element `qvel` vector. Source XML then supplies the kinematic transforms; it does not reuse the producer's Jacobian function.

For the free root, world angular velocity is root rotation times the locally represented angular `qvel`. The head origin follows the root's rigid motion. Each head hinge contributes its current world axis times its angular rate before applying the next rotation. Each antenna origin follows the articulated head at its source body offset. Its own three hinges share that origin, so their rotations contribute no origin translation. This analytically reproduces the saved Jacobian velocities.

| Comparison across four probes, two antennae | Maximum absolute error |
|---|---:|
| XML-derived origin versus saved native origin | 2.78e−17 cm |
| Analytic origin velocity versus native Jacobian velocity | 5.55e−17 cm/s |
| XML-derived versus saved operational head rotation | 3.33e−16 |
| Saved finite-difference velocity versus analytic velocity | 2.97e−10 cm/s |
| Inertial-center correction versus origin Jacobian | 1.67e−16 cm/s |
| Analytic local airflow versus saved local airflow | 4.89e−15 mm/s |
| Independent rotation/boost invariance | 3.55e−15 mm/s |
| Producer's saved original/transformed flow difference | 7.11e−15 mm/s |

The four probes are rest, root translation, antenna-only rotation, and combined root/head/antenna motion. The finite-difference values cover all three planned intervals, `1e−5`, `1e−6`, and `1e−7` seconds, and satisfy the frozen `2e−8 cm/s` tolerance. Native time remains zero in each saved probe. The producer source makes detached copies, uses `mj_integratePos`/`mj_forward` for geometry, and contains no physics-advance call. Its worker constructor performs its original initialization; the audit reports zero applied policy/body steps.

## Frames, point choice, and units

The NPZ mesh counts, means, minima, and maxima reproduce the reported landmarks. The head-minus-abdomen offset points dominantly forward, left-minus-right antenna origin points dominantly left, and the ocelli/rostrum separation establishes dorsal sign. The raw head frame is rotated relative to these axes. The constant calibration is the neutral thorax basis expressed in the head; the articulated operational rotation is `R = H B`. Orthogonality, positive determinant, and neutral alignment pass independently.

The review visually inspected the [two-panel mesh figure](../validation/flybody-airflow-geometry.png). Its millimeter labels, dorsal/side projections, red origin markers, blue inertial-center markers, and separation lines are legible and consistent with the saved geometry. Mesh vertex means establish sign here; they are not physical mass centers or measured receptor axes.

The correct sampling-point velocity is `J(origin) qvel`. The body linear output of `mj_objectVelocity` is evaluated at the inertial center, requiring

```text
v_origin = v_center + omega_world × (origin − center)
```

The source reconstruction also propagates each antenna's rigid inertial-center offset and angular velocity through all probes. Those local offsets are inferred from the saved neutral compiled centers, so this verifies rigid-body propagation without independently recompiling the mesh mass model. The maximum center/origin velocity discrepancy is **0.8943 mm/s**. Under antenna-only rotation, origin velocities are zero, while the left/right centers move at approximately **0.6872/0.4476 mm/s**.

The source model's velocity is converted from cm/s to mm/s by multiplying by ten before subtraction. With row vectors, the verified observation is

```text
relative_head = (air_world_mm_s − origin_velocity_world_mm_s) @ R
source_azimuth = degrees(atan2(relative_head_y, −relative_head_x))
```

All six saved source directions from −90° through 180° reproduce their expected angles. Zero is anterior, −90° is left, and +90° is right. These are source directions: the air velocity points oppositely. Zero horizontal flow yields a null azimuth, including when vertical flow is present. The independent reconstruction applies the producer's common arbitrary rotation, translation, and velocity boost to the full root/head/antenna kinematics and wind. Its transformed local vectors agree with the saved transformed vectors.

## Retained hash failure and verifier limits

The [original failed result](../validation/flybody-airflow-hash-v0-result.json), [original plan](../validation/flybody-airflow-hash-v0-plan.json), and [original script](../validation/flybody-airflow-hash-v0-script.py) remain present with matching hashes. The original passed 40/41 checks; only its broad data-array hash comparison failed. Its broad model comparison, collected physical state/clock, and cached observations passed. Original and amended **geometry hashes, complete probe values, sign probes, and landmark values are identical**, and their numerical plan parameters are unchanged.

The amended receipt enumerates 25 excluded owning data arrays: twenty are empty, and five nonempty fields are `dof_island`, `dof_islandind`, `efc_island`, `island_dofind`, and `island_efcind`. These five are documented in the installed MuJoCo 3.2.7 header as outputs of `mj_island`; the saved configuration has island discovery disabled, `enableflags=0`, and `nisland=0`. The receipt records owning storage, `base=None`, and differing addresses from repeated getters for these five without reading their contents. This supports excluding these allocations from a comparison of live native data in this configuration.

Two limitations remain explicit:

- The claim that the original differing fields were specifically `efc_island` and `island_efcind` comes from the author's later tool observation. The versioned original receipt retains the broad mismatch, not a field-level diff.
- The amendment also excludes **134 owning model fields** without retaining their names and shapes. Their complete classification cannot be independently established from these artifacts. The original broad model comparison passing is supporting producer evidence, not a replacement inventory.

The amended native-view checks cover 119 data and 246 model arrays. Their per-field before/after hashes and complete live arrays were not retained, so this review cannot independently replay the no-mutation comparison. That conclusion rests on producer checks and inspection of detached-copy code. The ownership filter must not be generalized into a claim that every owning getter is irrelevant or that every form of MuJoCo state was hashed.

Likewise, native plus/minus positions and full Jacobians are absent; only the resulting finite-difference velocities are saved. Transformed native `qpos`, `qvel`, and Jacobians are also absent. The independent source kinematics strongly corroborate the retained numerical values, but do not reproduce native API internals from a complete raw native-state journal.

## Claim boundary

Source construction with `use_antennae=False` removes the antenna actuators and direct antenna joint observations while retaining the six passive hinges. The reviewed source parameters are zero stiffness and damping 0.0003; this review supplies no empirical justification for their wind response. Head actuation remains in the source policy.

Sampling at the body origin is a clear engineering choice with a clear limitation: that point is the proximal pivot, not a distal arista or olfactory sensillum. Future distal sensing needs a justified local point and its own Jacobian. The signs resolved here do not calibrate an exact receptor axis, aerodynamic drag, near-body flow, mechanical deflection, wind-speed response, male/female transfer, or neural input gain. The audit leaves the observation disabled and does not assess later runtime changes.

Reproduce only this saved-evidence review with:

```sh
.venv/bin/python -m scripts.review_flybody_airflow
```

The command rewrites the independent receipt and performs no simulation. The existing source checkout, frozen Git revision/cache, evidence files, and recorded local MuJoCo header must remain available.
