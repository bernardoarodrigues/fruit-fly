# Independent review of optional FlyBody airflow observation

The saved regression supports the opt-in **proximal-antenna airflow observation** at source revision `6a1577b9c1817d74dd757d04c4a8e494f06deaa4`. The independent [review script](../scripts/review_flybody_airflow_runtime.py) and [receipt](../validation/flybody-airflow-runtime/independent-review.json) contain **69 passing checks**. No blocking findings were identified within this scope. This is an observation and isolation result, not wind-driven behavior or receptor calibration.

The runtime plan SHA-256 is `1c5f1b6946f993fe880ce14a37ca46ffa78d0be51da87cf3e6ff148347db3e7d`. Review uses its retained sources, journals, checkpoints, module proof and source XML. It does not import the producer, fruitfly runtime, FlyBody, MuJoCo or learned actor, construct a simulator, advance physics, or run another neural trial. The source-XML analytical functions come from the earlier independent geometry reviewer; their bytes are included in this receipt.

## Physics, actor and encoder isolation

The new module resolves the five named source bodies and computes a neutral thorax-aligned basis expressed in the head. Sampling reads proximal antenna positions and computes `J(origin) qvel`, then follows the articulated head rotation. Its only native call in `sample` is `mj_jac`. The installed MuJoCo header declares its model and data arguments `const`; its outputs are the caller's Jacobian arrays.

The worker creates the neutral calibration state as a detached copy, and samples each later state on the existing detached diagnostic copy after its forward refresh. The learned actor and native `advance` methods have identical syntax trees before and after the airflow commit. The host adds the result to its cached observation through the existing `local_airflow` function. No force, control, sensory encoder, neural dynamics, resource model or target-generation change is introduced. Frozen neural, sensory, proprioceptive, wind, physiology and rolling-task source hashes match the earlier rolling experiment. The option is explicitly false by default.

The module's zero-step proof contains four probes: rest, root translation, antenna-only rotation, and combined root/head/antenna motion. Review independently reconstructs their positions, velocities and operational rotations from the source XML. The saved before/after bytes agree for the nine named native arrays and cached actor observations, with zero elapsed native time. This byte inventory does not cover every MuJoCo field; the existing worker constructor performs its original initialization before these samples.

The enabled runtime regression supplies **1,001 native states** including the initial state and **1,000 completed 2 ms intervals**. All declared physical fields match the original archived two-second locomotor trial exactly: positions, velocities, accelerations, activations, controls, actions, actuator ordering, body/target poses, contacts, antenna positions, tibia velocities, commands, clocks and termination/warning flags. The original archive lacks actor-input arrays. A separate comparison against the first two seconds of the saved 12 s rolling trial matches all **1,001 actual actor-input hashes**, including initialization.

Each original encoder observation and ordered drive matches, including zero-rate entries and composition order. Combined inputs, RNG states before/after, spike hashes, full per-neuron counts, monitored groups, edge counts, source masks and sampled voltage extrema match for all 1,000 neural intervals. A separately implemented binary reader decodes **1,709,316 actual ordered spikes**, checks their timing and event hashes, and reconstructs the saved per-cell counts. These results support isolation on this fixed path; they do not imply all possible future configurations have been exercised.

## Point, frame and units

The independent calculation uses only saved `qpos`/`qvel`, the pinned `fruitfly.xml` body offsets, fixed quaternions, hinge axes/order and previously saved compiled coordinate addresses. It propagates root and head angular motion analytically, without calling the producer Jacobian routine. All 223 files in the upstream source manifest are rehashed. The XML-derived neutral head transform supplies the basis independently of the runtime's rotation output.

At each saved runtime state, source centimeter positions and centimeter-per-second point velocities are converted to millimeters and millimeters per second. The antenna origins agree with the existing odor sampling points. Subtracting the point velocity from the retained configured ambient flow, `[-2, 0, 0]` mm/s, gives the relative world flow. For row vectors:

```text
relative_head = (ambient_world − antenna_origin_velocity_world) @ head_to_world
source_azimuth = degrees(atan2(relative_head_y, −relative_head_x))
```

The proper rotation uses forward/left/up axes and left/right antenna order. Source azimuth is zero anterior, negative on the left and positive on the right. Near-zero horizontal flow has an undefined azimuth; its representation is null. Vertical flow remains in the full vector. Angular comparisons account for the ±180° wrap.

| Independent comparison across 1,001 states | Maximum absolute error |
| --- | ---: |
| XML-derived proximal origins | 5.33e−15 mm |
| Analytic proximal-origin point velocities | 7.11e−14 mm/s |
| XML-derived operational head rotation | 2.44e−15 |
| Relative head-frame airflow | 1.07e−13 mm/s |
| Horizontal airflow speed | 1.07e−13 mm/s |
| Wind-source azimuth | 2.56e−13 degrees |

The proximal origin is a clear engineering sampling point. Its velocity differs from an antenna's inertial-center velocity and from a distal receptor's velocity. No distal arista or sensillum location, aerodynamic drag, near-body flow, mechanical deflection, receptor axis, or male/female response transfer is established here.

## Hashes, stage clocks and failure evidence

The runtime plan/result identity, source files at the frozen Git revision, data receipts, module plan/result/module identity, prior source-geometry proof, and every raw artifact listed by the producer are checked. The complete closed gzip journal reproduces its compressed/decompressed hash, byte count and record count. It contains 1,000 returned physical records, 1,000 evaluated physical records, 1,000 completed neural records, 1,000 lossless spike receipts, 3,000 encoder records, the retained-state receipt and a final condition-end record. No failure record is present.

The saved final checkpoint's graph, unchanged neural parameters, 20,000 internal ticks, RNG state and voltage extrema match the final completed neural record. Pending spike queues, synaptic state, refractory-related state and previous drive are retained in the original checkpoint. The separately saved state reports 2,000 ms brain time and the actual native time near 2 s. Its unavailable independent physiology clock remains explicitly null. The worker is reaped after cleanup.

The airflow checker wraps native inspection without changing the recorder's underlying capture or retention code. A failed inspection can occur after the real body step; the recorder retains cached native state and a full brain checkpoint before cleanup, rather than replacing the step with a fabricated successful one. This review inspects that source path and the completed run's actual artifacts. It does not claim a newly executed physical fault-injection test. More general transport, allocation or native-library failure coverage remains bounded by the existing runtime tests and earlier recorder review.

## Interpretation boundary

The result supports enabling a read-only airflow observation on this source body. It supplies no wind force, antenna deflection, spike input, learned steering signal or measured female antenna-response transfer. Odor advection remains the pre-existing separate process. The same full male graph, learned female-derived body surrogate, uncalibrated encoder rates and physiological limitations remain in place.

This is one seed and one fixed two-second regression with the existing 0.6–1.2 s motor-readout mute. The proof of unchanged physics/neural output is exact for that saved prefix. It is not a natural navigation result, a general stability proof or evidence that wind already influences behavior.
