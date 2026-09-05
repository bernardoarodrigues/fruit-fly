# Single-body physical and physiological runtime

`fruitfly.body.BodyRuntime` keeps one articulated fly, its MuJoCo world, the published walking controller, its odor history and its physiological reserves alive across calls. This is the physical interface for intended **male CNS** experiments. Its `body_profile` is explicitly **female-derived NeuroMechFly morphology surrogate**. The mesh, mass distribution, abdomen and sensory geometry have not been validated as male anatomy. Both NeuroMechFly and the alternative FlyBody published specimens are female; no measured male rescaling ratio has been substituted. See [the body source audit](../research/02-body-physics-and-software.md) for the pinned sources.

```python
from fruitfly.body import BodyConfig, BodyRuntime

with BodyRuntime(seed=7, config=BodyConfig()) as body:
    obs = body.advance(0.01, drive_left=0.8, drive_right=1.0)
    obs = body.advance(0.01, behavior="feed")
    rgb = body.render("follow")    # uint8 RGB array, also overview or side
    evaluation = body.snapshot() # privileged world/provenance state
```

`advance` requires an integer number of physics steps and returns current observations. The default physics timestep is **0.0001 s**, preserved from the pinned model. Finer steps can be selected for convergence studies; coarser steps are rejected. Coupling steps belong to the caller and do not reset gait, fields or physiology. Physics is not sped up by enlarging the timestep.

`reset(seed)` resets physics, gait state, fields, stimuli and all resources. A declared 0.05 s physical settling period precedes simulated time zero. `close()` releases the renderer and simulation. The class is a context manager. Rendering is optional and lazy; the process/thread that owns rendering should also own the simulation, or serialize access.

## World and motor boundary

The default arena is 40 × 40 mm, bounded by 3 mm high physical walls. It contains a low cylindrical food substrate at `(6,0)` mm, water at `(5,7)` mm, and a physical landmark/obstacle. The arena has no roof, flight solver or wing controller. Bodies, walls and patches use explicit FlyGym collision pairs. Position/time units are millimetres/seconds (`gravity=-9810` in the pinned globals); native compiled body mass sums to `0.00102431`, corresponding to approximately 1.02431 mg when the asset's mass unit is grams. Contact-force vectors remain in the model's native units (g·mm/s²), not newtons. This code converts millimetres to metres only at the chemical-field boundary.

The low-level motor controller is the pinned FlyGym `HybridTurningController`: six CPGs, recorded step patterns, and stumble/retraction corrections. It is a **procedural motor surrogate**, not a reconstruction of the male VNC. It sees thorax height, leg height, local ground force and heading; it receives no food coordinates. Its two drive inputs are finite values clamped to `[-1.2,1.2]`, an engineering limit, not a measured descending-neuron range. Root neural code must document its own population decoder and causal controls.

`walk` advances the CPG/reflex controller. `rest` and `feed` smoothly return position actuators to the reference standing pose with a 20 ms engineering interpolation constant, turn on stance adhesion, and hold. This does not freeze, teleport or externally brake the body. Gait phase is retained while standing. `feed` additionally requests the physiological ingestion gate described below. Flight commands remain unavailable. Grooming is rejected by the default composition; `BodyConfig(enable_grooming=True)` enables a separately qualified measured female motor template with head actuation and foreleg–antenna contacts. It traverses one 0.5 s recording with 0.25 s entry/exit blends, supports withdrawal, and does not repeat under a tonic request. See [grooming-replay.md](grooming-replay.md) for phases, diagnostics, source conversion, and rigid-antenna limitations.

Compiled body, actuator and contact identifiers are cached. Every physics step ends with `mj_forward` before reading updated position/contact caches. Cached ground-force accumulation is checked against FlyGym's original `HybridControllerObservation.from_sim`; contact frames and sign convention are preserved. This avoids reconstructing body-name orders and geometry membership tables 10,000 times per simulated second.

## Observations and external stimuli

`observe()` returns JSON-compatible values:

| Key | Meaning |
|---|---|
| `t_s` | Integer-tick physical time |
| `antenna_odor` | Left/right concentration at actual funiculus body origins, arbitrary chemical mass/m³ |
| `taste_food`, `taste_water` | Nondepleted substrate touching a tarsal geom, with contact distance ≤0 |
| `food_contact_by_leg`, `water_contact_by_leg` | Separate local-contact booleans keyed LF, LM, LH, RF, RM, RH |
| `light_intensity` | Uniform environmental illumination gain; a generic photoreceptor proxy, not compound-eye vision |
| `proprioception` | Speed (mm/s), yaw rate and body-frame angular velocity (rad/s), six tarsal heights, six aggregate actual leg-support force vectors, and measured coxa/femur/tibia pitch angles and angular velocities |
| `pose` | Self thorax position and heading for the observer; root must explicitly select its neural inputs |
| `physiology` | Reserves, cumulative transfers and hunger/thirst proxies |
| `motor` | Last clamped drive and requested motor mode |
| `vision` | Enabled state, sample timestamp, array shape and two eye means; full retina arrays remain outside telemetry |

Food coordinates, patch inventory, source identity and distances are **not** in `observe()`. `snapshot()` deliberately includes privileged configuration/resources for visualization, evaluation and provenance and must never be supplied wholesale to the biological policy. Body proprioception is read from mechanics, not inferred from commanded motion.

`set_stimulus("odor", gain)` changes **future emissions**, preserving puffs already in the air. Instantaneous sensory ablation must instead remove receptor input at the neural boundary. `set_stimulus("light", gain)` changes a uniform light sensor and renderer illumination. Both gains accept finite values in `[0,10]`; render brightness saturates at 1 while the scalar light input can exceed 1. This is a declared convenience stimulus, not a calibrated photometry or retinal model.

The odor model emits Gaussian puffs at 10 Hz, advects them with constant horizontal wind, uses 2×10⁻⁶ m²/s effective diffusion and 1 mm initial width, and adds mirrored puffs for a reflecting floor. The 3 s initialization prehistory, arbitrary unit mass and 8 s retention horizon are explicit engineering choices. Lateral boundaries are open even though the physical chamber has walls: this first field does not solve wall flow or turbulence. Retired arbitrary airborne mass is logged. Resource depletion scales future emission; airborne chemical tracer mass is independent of nutritional units. Actual source chemistry, receptor specificity, mixture interactions and measured parameters belong in the sensory calibration layer.

Optional **compound-eye sensing** is enabled with `BodyConfig(enable_vision=True)`. `fly.add_vision()` is called before compilation and `sim.get_ommatidia_readouts()` samples the actual two eye cameras at a fixed 50 Hz by default, including a time-zero frame. Body position, occlusion and visible scene geometry enter these images; the overview camera is not used for sensing. `body.vision_readouts()` returns a copy of the cached `(2,721,2)` array (left/right eyes × ommatidia × yellow/pale channels). Calling `observe()` or reading the cache does not trigger extra rendering or move time. Each eye's unused pigment channel follows upstream's zero convention. The upstream retina and camera placement remain female-derived and their mapping to the male visual graph is a separate calibration problem. The independent `light_intensity` convenience scalar does not substitute for this visual pipeline.

Leg support and locomotor stumble detection use separate caches. Support includes all leg segments, particularly distal tarsi that normally carry load; the controller's published stumbling subset remains tibia/tarsus1/tarsus2. These mechanical signals still need an explicit receptor encoder before they become male sensory-neuron stimulation.

## Feeding and resource conservation

`fruitfly.physiology` uses **normalized engineering resource units**. Default rates are inspectable in `PhysiologyConfig`; none is claimed to measure Drosophila physiology. Nutrients transfer 1:1:

`food patch → crop → energy → cumulative energy spent`

Water transfers `water patch → hydration → cumulative water lost`. Finite inventories cannot become negative; capacities cap crop, energy and hydration. Each snapshot reports both conservation residuals, expected to remain numerically zero. Energy and water expenditure depend on elapsed time and physically measured travel speed.

Ingestion requires all three conditions: a `feed` command, tarsal contact with the relevant nondepleted patch, and horizontal thorax speed ≤1 mm/s. The stationary threshold is an engineering parameter. Food and water gates are separate, and a nearby patch produces no taste or intake. This explicitly abstracts proboscis extension, mouth contact, pumping and gut physiology; it does **not** show actual mouth ingestion. Zero energy/hydration disables walking and ingestion in this reduced viability model. Circadian state, sleep, long-term starvation tolerance, protein metabolism, sex-specific endocrine signals and reproductive physiology are absent.

## Verification performed

`python -m unittest tests.test_physiology -v` verifies resource conservation through depletion; crop and hydration capacity; all ingestion gates; invalid inputs; actual MuJoCo food-contact transfer; absence of remote transfer; exact reset and split-step replay for a fixed seed; cached forces against upstream; distal-tarsal support; drive limits; timestep validation; plume symmetry; delayed plume disappearance after emission stops; and optional compound-eye shape, finiteness and fixed sampling timestamps.

A local Apple arm64 smoke run used 0.2 simulated s of walking and 0.2 s of standing. Walking advanced the thorax approximately 1.84 mm in x and 0.54 mm in y, took about 0.79 wall s excluding setup/render, and remained finite. After standing, speed was about 0.00068 mm/s. A separate physical-contact feed run ingested 0.016 normalized units over 0.2 s, with conservation residual below 6×10⁻¹⁵. Following, side and overview cameras use real MuJoCo rendering; the following image was visually inspected. These are engineering checks, not biological validation or long-duration stability evidence.

Remaining body milestones include measured male morphology/segment inertias, male motor-controller validation, calibrated visual and mechanical receptor-to-neuron mappings and sound, actual proboscis kinematics, biologically validated grooming beyond the optional female template, flight/takeoff/landing, and VNC-to-muscle control. A running male graph does not establish those missing body mechanisms.
