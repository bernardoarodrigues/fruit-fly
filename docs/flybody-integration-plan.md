# Proposed optional full-neural FlyBody integration

**Use a Python 3.12 body adapter plus a separate Python 3.10 physics/policy worker. Keep the current body and viewers as defaults.** Start with a bounded 2 s full-MaleCNS calibration run that sends real physical odor/contact/proprioceptive feedback into the graph and reads actual descending output back into the body. Do not begin by substituting recorded trajectories or fitting a new neural gain.

This records the pre-implementation proposal. The bounded worker/bridge is now implemented and checked against native traces; see [implementation and parity results](flybody-bridge.md) and the separate [full-loop record](flybody-loop.md). It follows the [frozen motor comparison](flybody-motor-comparison.md) and [neutral-zero stance experiment](flybody-stance-experiment.md). The latter passes the declared stop/resume criteria at one tested gait phase; it does not establish robustness under arbitrary neural fluctuations. Exact inspected runtime hashes are saved in the [interface audit](../validation/flybody-integration-interface-audit.json), so later changes to these files are visible.

## Why a separate worker

The main simulator uses Python 3.12 and NumPy 2, while the verified policy uses Python 3.10.21, NumPy 1.26.4, TensorFlow 2.15.1, TFP 0.23, dm-control 1.0.27 and MuJoCo 3.2.7. Installing the original training extra or mixing these environments would invalidate the verified dependency boundary. The [isolated inference environment](flybody-inference-trial.md) already works on this Apple Silicon CPU. It requires no training GPU or new large data download.

Launch the pinned interpreter with `subprocess.Popen` from the main simulation process, using argument arrays and private stdin/stdout pipes. Avoid Python pickle or multiprocessing queues across interpreter/NumPy versions. Use request IDs, a versioned JSON schema and explicit length-prefixed binary RGB payloads. Redirect library logs to stderr/the run log, reserving stdout for the protocol. One serial worker loop owns MuJoCo, TensorFlow and its GL context.

The existing viewer already spawns a Python 3.12 process that owns `SimulationRunner`. A subprocess can be launched from that worker without changing the desktop server, JPEG transport or command queue. Do not launch another multiprocessing child from the daemon viewer worker. The bridge must close pipes and reap its subprocess; worker EOF and an explicit close request must release resources. A timeout or worker exit stops the optional run with its error, rather than silently switching to CPG or replaying stale state.

## Smallest code boundary

Proposed new modules are `fruitfly/flybody_worker.py` and `fruitfly/flybody_bridge.py`, plus an optional config and a closed-loop validation script. The runner needs one explicit backend factory/selection branch and an additional control-clock check. No change to the current `BodyRuntime` controller or source defaults is needed.

The bridge can reuse `PuffField` from the already imported main-process body module, and `Physiology`/`ResourcePatch` from the existing pure bookkeeping module. **The Python 3.10 worker must not import `fruitfly.body`**, which imports FlyGym. This keeps shared odor/physiology equations in the main environment without duplicating or refactoring them for the first integration. The worker owns physical state and original actor observations; the main bridge owns the resource ledger and scalar sensory abstractions.

The existing `BodyConfig` is not reusable as-is: it enforces ≤0.1 ms physics and the exact NMF profile label. Add an explicit FlyBody configuration instead, with fixed 0.2 ms physics, 2 ms control and a female-derived FlyBody profile. Shared world dimensions remain in mm at the public boundary. Use a top-level opt-in such as `body_backend: "flybody"`; absent that key, the existing NMF path remains byte-for-byte unchanged. Unknown/unsupported optional settings should fail before allocating the worker.

## Exact runner contract

`SimulationRunner` currently needs the following body interface; it does not require access to FlyGym internals:

| Member | Required behavior |
|---|---|
| `time_s` | Cached completed physical time; equal to brain time after every coupling interval |
| `timestep` | Source physics step, 0.0002 s |
| `control_timestep_s` | New optional capability, 0.002 s; runner validates coupling against it |
| `wind_reference` | `None` initially; existing runner only checks whether a reference exists |
| `observe()` | Return the most recent complete physical/sensory observation without stepping or extra IPC |
| `advance(duration_s, left, right, behavior)` | Send validated commands, advance exact source control ticks, update host field/physiology, cache returned state |
| `snapshot()` | Return observation plus observer-only config/resources/ledger/stimuli/physics/backend provenance |
| `reset(seed=...)` | Reset worker and host state together; reset target/hold/odor/resources and cached time |
| `set_stimulus(name,value)` | Preserve existing odor/light controls; light renderer writes happen in the owning worker |
| `render("follow"/"overview"/"side")` | Return uint8 RGB of the requested view, without changing simulation time |
| `close()` | Idempotent process/pipe/renderer cleanup |

`observe()` must preserve the runner's required keys: `t_s`, `pose`, `physiology`, `motor`, `antenna_odor`, `taste_food`, `taste_water`, six-key `food_contact_by_leg`/`water_contact_by_leg`, `light_intensity`, `proprioception`, `wind`, `vision`, and disabled `grooming` telemetry. `snapshot()` must provide `config`, `wind_reference`, `resources`, `resource_balance`, and `stimuli`. Additional `backend`, `capabilities`, policy/worker hashes, clock and provenance fields should be exposed through the manifest/snapshot, without pretending the body has NMF-specific `.fly`, `.controller` or actuator IDs.

The bridge should cache each complete advance reply, so the runner's repeated `observe()` and `snapshot()` calls do not cause extra IPC or change sensor timing. Native arrays are decoded into finite typed data, never accepted as arbitrary executable objects. `advance(0)` and rendering must leave all clocks, body state, resource totals and neural state unchanged.

## Clock and command semantics

The original actor acts every **2 ms**, with ten **0.2 ms** physics steps inside the source `env.step()`. The runner's current 5 ms coupling interval is 25 physics steps but **2.5 actor steps**, and cannot be silently rounded. For the first optional config use **coupling_s=0.002**: one complete actor step per neural coupling interval, and 20 unchanged 0.1 ms neural steps. Existing 5 ms default configs remain NMF-only. Larger optional intervals may later be allowed only as integer multiples of 2 ms, with explicit sample/hold semantics.

Changing the coupling schedule changes receptor/readout update timing and potentially RNG assignment. It is not a change to the neural integration step, but old 5 ms neural trajectories must not be claimed as exact baselines. Record both clocks and the new coupling choice in the manifest. Validate chunk invariance at the same 2 ms coupling schedule rather than comparing unlike schedules.

For the first adapter, reuse the existing neural `MotorDecoder` and interpret its finite left/right outputs through one declared engineering map:

```text
forward_fraction = clip((left + right) / 2, 0, 1)
turn_fraction    = clip((right - left) / 1.2, -1, 1)
speed_mm_s       = 20 × forward_fraction
yaw_rad_s        = 2 × turn_fraction
```

This range comes from the fixed 10/20 mm/s and ±2 rad/s motor comparisons, not a measured descending-neuron law. The mapping must be recorded and frozen before integration trials. Existing left/right clipping can prevent exact recovery of the internal decoder's forward/turn scalars at saturation; report that limitation. No food/world coordinate or desired destination enters this map. Low-speed turns and continuously varying neural commands remain unvalidated and may fail; do not add a hidden minimum walking speed or fit gains to suppress that failure.

`walk` while alive uses the exact original graph mean, canonical clipping, native action scaling and source actuator order. `rest`, motor-readout ablation, and `feed` use **neutral-zero hold: all 53 native position targets zero and six native adhesion targets one**, retaining the original filters. This is the tested engineering posture hold; no extra interpolation, root clamp or target recentering is added. `feed` only enables the existing contact/stationarity ingestion abstraction. It does not actuate a proboscis or pump. `groom` and flight are unsupported initially and must not silently become walking.

Motor-readout ablation is explicitly a locomotor-policy output mute with posture actuation retained. Brain dynamics may continue, and its changing proposed motor readout must not reach the actor while muted. On release, the original policy resumes with a reference starting at the continuously integrated target, as in the stance experiment.

The first validation can stay below 8 s with a sufficiently long reference buffer and the original 10 s source task. Before advertising an indefinitely running optional viewer, implement and separately verify a rolling-reference inference task that preserves the original observation values and speed/acceleration/distance termination guards, while removing only finite-recording end bookkeeping. The current source uses absolute indices, a trajectory end and an environment time limit; silently resetting the physical body at the end would break the experiment. That persistent-task extension is not required to answer the first 2 s full-loop test, and should not be disguised as already implemented.

## Physical world, contacts and units

Keep the original floor and physical body unchanged for the first loop. Resource patches can be **surface-material regions of that floor**, represented by noncolliding colored markers for observers. A taste event requires an actual penetrating/contacting tarsal floor contact whose contact point lies within the configured food/water region. Region membership alone, a nearby foot, or the body origin is insufficient. This preserves source floor mechanics and avoids coincident colliding floor/patch surfaces. The region coordinates remain confined to the physics/sensory adapter and evaluator; only named contact booleans reach the neural encoder.

The tarsal geom inventory must be compiled from exact source names, with LF/LM/LH/RF/RM/RH ordering. Exclude non-tarsal leg, head, body and inactive contacts. Compute contact forces on a detached native `MjData` after `mj_forward`, as in the verified experiment; retain original actor sensor timing. The source raw post-step `actuator_force` is a preceding-stage value and must not be used as if it were simultaneous with current actuator lengths/activation. [Independent timing review](flybody-stance-independent-review.md).

| Quantity | Source worker units | Main body boundary |
|---|---|---|
| Root, antenna, contact and claw positions | cm | ×10 → mm; ×0.01 → m for `PuffField` |
| Root/antenna translational velocity | cm/s | ×10 → mm/s |
| World geometry, patch radii, camera distances | Public mm | ÷10 → cm before source MJCF construction |
| Joint angles / angular velocities | rad / rad/s | Unchanged |
| Gravity | −981 cm/s² | Leave native physics unchanged; equivalent −9810 mm/s² |
| Ground force | dyne = g·cm/s² | ×10 → existing g·mm/s² telemetry; label units |
| Resource quantities | Normalized engineering units | Existing ledger unchanged |
| Light RGB coefficients/directions | Dimensionless | No scale conversion; positions still ÷10 |

Both antenna positions must come from actual `antenna_left`/`antenna_right` bodies, with an explicit left/right order. Evaluate the existing SI puff field at those positions; preserve source depletion, old airborne puffs and odor adaptation semantics. The neural encoder receives only those concentrations and its existing hunger modifier.

Actual tibia angular velocities can drive the existing opt-in FeCO club encoder under `joint_velocities_rad_s["tibia_pitch"]`, in the six-leg order. The compiled FlyBody hinge axis [1,0,0] has already been checked against the benchmark's flexion coordinate; this interface alias must be documented. Compound coxa/femur names should carry source conventions, not silently masquerade as NMF coordinates. Claw-site height and NMF tarsus5-body-origin height also differ; label the chosen sensor site.

Ground reaction vectors should use the correctly signed force on each leg, transformed from contact to world coordinates, then unit converted. They remain observer/proprioceptive telemetry; no blanket force-to-mechanosensory mapping is introduced.

The host can advance the existing physiology at the returned **2 ms physical sampling cadence** using actual speed, tarsal contact and requested feed mode, then advance the odor field to the exact returned time. This is coarser contact sampling than the current NMF 0.1 ms bookkeeping and must be explicit; ledger conservation still applies. For this first bridge, coupling is exactly one returned policy tick, so the host can inhibit the next command immediately if reserves are exhausted. A finer contact-occupancy integral would require a separately verified source substep observer, not silently interpolated contact.

For airflow, return actual antenna point velocities and an audited head anatomical frame to the host's existing `local_airflow`. The FlyBody head axes differ from its thorax and from the NMF head transform; derive and verify that basis from the source head/antenna geometry before enabling it. Do not transfer the existing NMF mesh correction by name. The empirical antenna reference can remain disabled initially; its explicit sex-transfer and domain gates must be retained if later added.

## Rendering and current viewer compatibility

Source cameras include `walker/track1`, `track2`, `track3`, `side` and separate eye cameras. Use dm-control's `MovableCamera`/`Camera.render` on the worker's main thread for `follow`, `overview` and `side`, with public mm distances converted to cm. Size the offscreen framebuffer before compilation. Transfer RGB bytes to the bridge; the existing viewer can continue encoding JPEG and publishing its bounded latest-frame channel.

Rendering should never call `env.step()`, advance the odor field or alter the policy input schedule. Viewer pause, reset, camera selection, speed pacing and motor-readout ablation remain the existing commands. Starting this optional process must not stop or change any already running default viewer.

The source walking policy does not consume image input. Its two perspective eye cameras are **not** the pinned FlyGym ommatidial yellow/pale array. For the first integration report `vision.enabled=false`, disabled grooming, and explicit native-vision limitations; do not fabricate an ommatidial shape. New world-light configuration currently targets a newer MuJoCo `MjSpec` API, while the source worker uses dm-control MJCF and MuJoCo 3.2.7. Keep the original visual setup for the first parity/loop trial, and reject unported illumination/vision options rather than silently dropping them. A later world-light translation can preserve numerical RGB/direction settings and convert positions, but needs its own renderer API and camera-independence check.

## Smallest first integration test proposal

Before full-brain trials, perform an **RPC parity check** with the original bare floor and fixed commands. Reproduce the successful neutral-zero stop/resume trace under the same 2 ms source schedule. Require identical action mapping, hold semantics, unit conversion, clock and source hashes; compare physical arrays against the frozen standalone trace at tight documented numerical tolerance. Check rendering leaves state/time unchanged and that invalid partial policy ticks are rejected. No neural gain is fitted during this step.

Then use a single frozen 2 s optional config:

- Full retained MaleCNS graph, original Shiu parameters, seed 11, 2 ms coupling.
- Existing `motor_probe` assay: direct 40 Hz input to identified DNg97 cells, with **real physical sensory feedback still enabled**. This is a neural motor calibration assay, not spontaneous food seeking.
- Existing odor encoder, tarsal taste groups, and explicit existing club parameters (`max_rate_hz=30`, `half_speed_rad_s=5`). Record the exact input IDs/rates/order; do not tune them after seeing the result.
- Source initial root position (0,0,1.278 mm), zero heading, flat arena with observer-only food/water regions. For example retain food center (6,0) mm, radius 3 mm and the existing finite resource amounts. This placement is a declared assay setup; it never becomes a motor destination.
- Gate off through existing motor-readout ablation at 0.6 s and back on at 1.2 s, matching the tested stop/resume timing. Keep the neural probe and brain active during that intervention.

The critical evidence is the complete causal chain: actual MuJoCo antenna/foot/joint state → receptor/club/taste input events in the full graph → real DNg97/steering/MN9 readouts → bounded speed/yaw or neutral hold → new physical state. Record actual commanded velocities and contacts. Do not infer that receptor input controls natural navigation merely because all modules exchange values.

A second paired 2 s trial should block the outgoing synapses of the enabled sensory groups through the existing `synaptic_output` mechanism while retaining those physical observations, input events and direct motor probe. This tests whether physical afferent feedback actually reaches downstream graph activity. The HTTP viewer currently whitelists only its grooming-specific synaptic control, so this calibration can use `SimulationRunner.control` directly without expanding public viewer controls. Record any downstream difference and any unchanged readouts honestly; direct DNg97 stimulation may dominate behavior.

Required receipts: matching body/brain time after every tick; finite brain/body states; source-neutral hold during motor mute; traceable actual sensory event delivery; unchanged full graph identity and typed neuron groups; output-mute causality; graph-level sensory block delivery; finite resource conservation; no hidden source coordinates in neural/motor inputs; frame/pause/reset lifecycle checks; and preserved physical/controller failures. Baseline body tests and existing viewer smoke checks must remain passing. A natural odor-only run can then be reported separately, including no movement if that is what the unchanged graph produces.

Do not require a particular biological trajectory or quietly adjust the map if a rapidly varying full-neural command breaks the surrogate. The successful stance experiment has one stop phase and a constant 20 mm/s command; this integration test is explicitly new evidence. Only after these receipts and the persistent-reference extension are reviewed should an optional long-running viewer be described as supported.
