# Optional bounded FlyBody runtime

The optional Python 3.12 bridge now runs the pinned Python 3.10 FlyBody policy and native physics in a separate process. It preserves the successful engineering neutral-zero posture hold. It does **not** replace the default NeuroMechFly body, recreate a male VNC, or establish natural food seeking.

The initial backend deliberately stops at **2 simulated seconds**. Advancing beyond that horizon raises an explicit error without moving or resetting the body. The source's finite reference and episode bookkeeping have not yet been replaced by a persistent task. Existing defaults and viewers remain separate from this optional backend.

## Install and watch

The main Python 3.12 environment and processed graph must already be installed as described in the repository README. Create the separate policy environment and materialize only the pinned assets:

```sh
uv venv --python 3.10.21 tmp/flybody-env
uv pip sync --python tmp/flybody-env/bin/python --require-hashes validation/flybody-inference-requirements.lock
.venv/bin/python -m scripts.materialize_flybody_source
.venv/bin/python -m scripts.acquire_flybody_walking
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-probe.json --port 8771 --paused
```

The source materializer verifies all 223 manifest entries (191,050,092 bytes) by size, SHA-256 and Git blob SHA-1. `--from-local /path/to/existing/flybody` copies a previously downloaded matching checkout. Existing differing files fail explicitly. Source and policy assets remain in ignored local storage with their separate license notices.

Open [the local FlyBody viewer](http://127.0.0.1:8771). Resume runs the direct-DN calibration for 2 simulated seconds. At the declared horizon the viewer pauses normally and displays **Trial complete**. Reset starts a fresh paused trial; cameras remain usable at the endpoint. This lifecycle was checked against the actual full graph, with the [saved inspection](../validation/flybody-viewer/inspection.json). The earlier viewer failure when it tried another chunk beyond the horizon is retained in the [initial receipt](../validation/flybody-loop/viewer-initial-limit.json).

The four full-loop trials were executed against runtime source committed at `928e062`. Their frozen plan includes the former viewer source; later viewer lifecycle edits do not retroactively change that experiment. The independent review separately flags one unrecovered pre-run documentation hash, while all declared runtime/configuration/data-receipt hashes match that commit.

## Verified parity

The [predeclared bridge check](../validation/flybody-bridge-plan.json) compared two complete 2 s runs with the frozen native `neutral_zero` stance traces: zero-start and 20 mm/s → hold at 0.6 s → resume at 1.2 s. Both passed with **maximum absolute difference 0** for all 1,001 native qpos, qvel, root pose, actuator length and actuator activation samples, and all 1,000 applied 59-channel action vectors. This includes visual resource sites added to the native arena; they change no collision geometry, inertia, bodies or actuators.

Every trial rendered follow, side and overview views. The worker checked the actual native qpos, qvel, qacc, act, ctrl, sensordata and data.time before and after each render. None changed. Cached observations, snapshots and diagnostics, zero-duration advance, partial-tick rejection, the horizon error, and explicit reset also passed. Reset returned the exact initial qpos and native time zero. Resource conservation residuals stayed within 1e-10.

The [result receipt](../validation/flybody-bridge-validation.json) identifies every trace and frame. Additional comparison of those saved traces found identical per-leg absolute vertical support forces to the native stance traces. These are implementation checks against our prior motor surrogate, **not independent biological validation**. The previously reported gait-frequency and tibia-excursion discrepancies remain; the failed last-target posture variant was not reinstated.

Reproduce with the main environment after source/weights and the isolated inference environment are present:

```sh
.venv/bin/python -m unittest tests.test_flybody_bridge
.venv/bin/python -m scripts.check_flybody_bridge --run
```

The checker refuses changed implementation/source hashes relative to the saved plan. A changed implementation needs a separately recorded review and plan; do not overwrite the old result to hide a failure. The initial development smoke logs also retain the corrected dm-control `visual.global` attribute and camera cleanup API mistakes; neither was a biological/model failure.

## Process and interface

The runner selects `body_backend: "flybody"` explicitly. [The optional config](../configs/male-flybody-probe.json) uses seed 11, 2 ms coupling, direct 40 Hz DNg97 calibration input, actual odor/taste/club feedback, and food centered at (6,10) mm to avoid preempting the locomotor assay with feeding. This configuration is a direct motor assay with physical feedback. The [full-loop record](flybody-loop.md) is maintained separately and must be read for its actual results.

`FlyBodyRuntime(seed, config, log_path=None)` provides `time_s`, `timestep`, `control_timestep_s`, `wind_reference`, `observe`, `advance`, `snapshot`, `diagnostics`, `reset`, `set_stimulus`, `render`, `vision_readouts`, `close`, and context-manager cleanup. Its public physics step is 0.0002 s and policy step is 0.002 s. Each host advance requires complete policy steps. Neural integration remains 0.1 ms; this configuration changes coupling from the default 5 ms to 2 ms explicitly.

The Python 3.12 host owns the existing `PuffField`, finite `ResourcePatch` ledger and `Physiology`. The worker owns TensorFlow, dm-control, the native model, original policy observations, control scaling, source environment stepping and rendering. The worker never imports the FlyGym body module. They communicate over private versioned, length-framed JSON pipes; RGB bytes follow a checked length declaration. No pickle or NumPy ABI is shared. Native/library output is redirected to the run's worker log.

At startup the worker verifies all 223 pinned source/assets and all three SavedModel files against fixed SHA-256 receipts. Source defaults to the durable ignored `data/raw/flybody/source`; the interpreter defaults to `tmp/flybody-env/bin/python`. Python 3.10 and the tested TensorFlow 2.15.1, TFP 0.23.0, dm-control 1.0.27, MuJoCo 3.2.7 and NumPy 1.26.4 versions are required. The saved graph is unchanged. Its documented TFP class-registration compatibility shim is retained. Source is Apache-2.0; the downloaded policy collection is GPL-3.0-or-later. See the acquisition and inference receipts for provenance and packaging boundaries.

The source renders and acts serially on the worker's main thread. A protocol timeout, framing error or EOF makes the transport terminal and terminates the process; a late reply cannot become the next request's state. A framed task error retains the final native state, including a partial-step native time if `env.step` fails. A partial physics interval does not invent a complete 2 ms physiology update. The runner must preserve any resulting brain/body clock difference as a failed run, not silently repair it.

## Commands and reference

The engineering command map is frozen:

```text
L,R = clip(input_left,input_right, -1.2,1.2)
speed_mm_s = 20 × clip((L+R)/2, 0,1)
yaw_rad_s = 2 × clip((R-L)/1.2, -1,1)
```

Only the neural motor decoder's left/right outputs and behavior request enter this map. World locations, food coordinates, odors and distances do not become motor targets. The source's current-only 65-frame preview is rebuilt from the continuously integrated command reference each 2 ms tick. The target is never recentered on the physical body. The 1,100-frame reference preserves original absolute indexing for this bounded trial. The previously audited yaw-reference qvel conversion to rad/s remains explicit.

Walking uses the exact frozen mean policy, clips its canonical output to [-1,1], and scales to the source-native action ranges and ordering. Rest and abstract feeding command all 53 native position channels to zero and all six adhesion channels to one, with the original 10 ms position and 7 ms adhesion filters. Motor ablation therefore mutes the locomotor-policy output while retaining posture actuation. Resume immediately releases the hold and applies the original actor with no additional blend. Shadow policy evaluation during hold is diagnostic and cannot contribute an action.

This map does not implement reverse walking. Low-speed turns and rapidly changing neural commands remain outside the narrow frozen constant-command motor validation and may fail. There is no minimum-speed override or gain fitting. Unsupported grooming, flight, compound vision, empirical wind transfer, and custom world-illumination options are rejected.

## Actual sensory geometry and units

Source positions and velocities use cm and cm/s. The public interface converts them by ×10 to mm and mm/s. Odor sampling then converts antenna positions by ×0.001 to SI meters. Source gravity remains −981 cm/s². Forces are converted from dyne (g·cm/s²) by ×10 to the existing g·mm/s² telemetry convention. There is no physical body rescaling.

Odor is sampled at the actual named left/right antenna **body-frame origins**, not empirically localized receptor positions. The public root pose is the free-joint/attachment origin. The speed used for physiology and telemetry is the native `mjOBJ_BODY` velocity at the thorax **inertial origin**; it is not asserted to equal the derivative of that reported attachment-origin position during rotation. This point distinction should be retained when comparing differentiated tracked trajectories.

Food and water are finite material regions of the original floor, drawn as noncolliding sites. Taste requires an active native tarsal/claw-floor constraint, nonpositive separation, and a physical contact point within the corresponding circular region. A nearby body, geometrically nearby foot, or inactive positive-distance contact cannot taste a patch. The six-key contact maps are ordered LF, LM, LH, RF, RM, RH. Depleted resources no longer emit active taste, while old airborne odor puffs remain in the field.

Host physiology advances once per completed 2 ms step using actual speed/contact. Feeding remains the documented abstraction of stationary tarsal contact plus a feed request; no proboscis or pump is simulated. These normalized reserve and ingestion constants are engineering choices, not measured fly metabolism.

Proprioception supplies real source scalar coxa/femur/tibia coordinates and velocities. Only the verified tibia flexion hinge is aliased to the existing encoder's `tibia_pitch`; the coxa/femur values are named `source_coxa` and `source_femur`. Foot-height telemetry uses the source claw site, distinct from the NMF tarsus5 body origin. Club input uses the existing explicitly configured sensory encoder, not a blanket mapping of all mechanosensors.

Ground contact forces are recalculated on a detached native `MjData` with `mj_forward`, preserving the source actor's original sensor timing. The raw `actuator_force_preceding_stage` is labeled accordingly: dm-control ends at `mj_step1`, so it is not simultaneous with the current actuator length/activation. Signed force vectors and the sum of absolute vertical forces have different meanings and both remain labeled.

Airborne odor advection uses the configured wind. The optional [head-frame airflow observation](flybody-airflow-runtime.md), enabled with `enable_wind: true`, uses verified proximal-antenna geometry and remains independent of neural input or physical force. It is disabled by default. Source perspective eye cameras are not FlyGym ommatidia. Render lighting uses the native FlyBody lights; the light control scales original world diffuse/ambient/specular and headlight coefficients. Snapshot illumination reports `source_native_flybody`, actual coefficients and the relative gain.

## Observer and neural boundary

`observe()` is cached and supplies the existing runner's pose, bilateral odor, taste booleans/maps, physiology, motor state, light and limited proprioceptive fields, plus optional local airflow and disabled grooming/vision status. The neural encoders consume their defined subsets. `snapshot()` separately includes resource inventories, configuration, source provenance, capability flags, illumination and compact physical diagnostics.

`diagnostics()` is an evaluator-only cached copy. It exposes native time/tick, qpos/qvel/qacc/act/ctrl, warnings, canonical and applied native actions, actuator indices/names, current lengths/activation, preceding-stage forces, native root pose, uprightness, actual antenna/claw/joint state, contacts with names/positions/forces/activity, command, reference target and source termination status. These arrays and reference coordinates are **not neural inputs**. Failed-state diagnostics remain available even when no finite observation can be returned.

The source-native renderer still displays its original ghost/reference markers. They are observer aids, not additional physical animals, obstacles or food cues. The first optional viewer must be described as bounded; a paused display at its limit is not an indefinitely running digital animal.

An opt-in [rolling-reference extension](flybody-rolling-runtime.md) passes separate body/RPC comparisons and [three full-neural trials](flybody-rolling-loop.md) through twelve seconds. It uses explicit `reference_mode: "rolling"` and `horizon_s: null`; the bounded configuration and its historical results remain available. Browser operation beyond two seconds, pause/camera/reset and the limits of the sensory-only behavior are recorded separately.
