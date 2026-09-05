# Live local viewer

Run from the project root with the project Python environment:

```sh
.venv/bin/python -m fruitfly.viewer --port 8765 --open
```

Open http://127.0.0.1:8765. The HTTP server is local only. Ctrl+C stops both the
server and simulation worker. `--paused` loads an initial frame without advancing
time. `--config path/to/config.json` passes a JSON object to the simulation.

The arena shows real JPEG frames rendered by MuJoCo. It is not a prerecorded clip
or a browser approximation of the body. Browser reloads reconnect to the same
worker. Pause, resume, reset, three camera views, food odor intensity, ambient
light, and the model's motor readout mute are available. The mute does not silence
neurons: spikes continue to be simulated. Its target is displayed from runtime
telemetry. The assay banner distinguishes sensory stimulation, direct DN motor
calibration, and a controller-only baseline. The female-derived body morphology
surrogate is disclosed beside the male circuit label. Space pauses/resumes;
1, 2, and 3 select arena, follow, and side cameras when a form control is not
focused. Controls are ordinary keyboard-accessible HTML elements.

The speed selector is a target simulation/wall-time ratio; `Maximum` removes
pacing. Actual speed is measured between running frame updates, including
rendering and pacing overhead. The runtime's compute-only ratio remains in raw
telemetry. Paused time is excluded; two running frames establish an interval. A
computer unable to reach the target runs as fast as it can. Pausing and camera
changes do not advance simulated time. Reset reconstructs state through the
runner's reset command. Stimulus sliders synchronize to the runtime's reported
gains after controls, reset and browser reload; the runtime defines how those
gains change sensory input. Reserve percentages use the runtime's capacities;
when capacities are unavailable the viewer shows raw units instead.
The neural panel reports model voltage minimum, mean and maximum. A separate
sensory panel shows optional compound-eye sample timing/intensity and FeCO club
input rates, explicitly distinguishing rendered eye samples from an implemented
neural vision pathway.
The wind readout shows source azimuth and relative horizontal air speed at the
left and right antennae. An optional measured female reference shows predicted
steady arista deflections only when the runtime's domain gates pass; otherwise
it shows unavailable with the exclusion reason. Its caption explicitly states
that the neural pathway is unmapped. There are no wind controls in this viewer.

## Runtime API

`fruitfly.simulation.SimulationRunner` is created inside a spawned subprocess:

```python
runner = SimulationRunner(config: dict)
telemetry = runner.advance(sim_seconds: float)  # 0 returns state without stepping
rgb = runner.render(camera: str)               # H × W × 3 uint8 NumPy array
runner.control(command: dict)                  # optional updated telemetry dict
runner.close()
```

Cameras: `overview`, `follow`, `side`. Runtime commands:

```json
{"type": "reset"}
{"type": "stimulus", "name": "odor", "value": 1.0}
{"type": "stimulus", "name": "light", "value": 1.0}
{"type": "ablation", "enabled": true}
```

Odor/light values are in `[0, 2]`. Zero odor gain stops new source emission;
previous airborne puffs and baseline receptor activity can remain. The viewer implements
`pause`, `camera`, and `speed` itself. It steps in small quanta (default 0.01
simulated seconds, aligned to whole `runner.coupling_s` intervals when provided),
checks commands between quanta, and renders up to eight
frames per wall-clock second. Frame/update queues have fixed capacity and drop
old frames, so rendering cannot accumulate unlimited queued video. A single slow
simulation quantum still delays a control; its duration depends on model size and
available compute. The HTTP server stays responsive independently.

Optional viewer configuration:

```json
{"viewer": {"paused": false, "camera": "follow", "speed": 1.0,
            "step_seconds": 0.01, "fps": 8}}
```

Settings are validated before worker startup: FPS 1–30, requested step 0.001–0.05
seconds, and speed 0.05–10 or zero for maximum. Invalid settings fail with a
specific error. The effective step can be larger than the requested step when
one coupling interval is larger.

Telemetry keys are optional and absent values display as unknown:

```text
t_s, realtime_factor, behavior
pose: {position_mm: [x, y, z], heading}
physiology: {energy, hydration, crop, capacities?: {energy, hydration, crop}}
stimuli: {odor, light}                           # source gain controls
senses: {odor: [left, right], taste_food, taste_water, club_event_rates_hz?}
vision: {enabled, sample_t_s, shape, mean_by_eye}
wind: {relative_velocity_head_mm_s, source_azimuth_deg, horizontal_speed_mm_s,
       antenna_reference?: {estimated_steady_arista_deflection_deg, excluded_because}}
wind_reference?: {nominal_speed_mm_s, speed_tolerance_fraction,
                  elevation_tolerance_deg, ...provenance}
neural: {neurons, edges, active_neurons, spikes, output_rates,
         voltage_mv?: {minimum, maximum, mean},
         ablated, backend, ablation_target?, ablation_description?}
assay, status, warnings, provenance?
```

Neural activity history is sampled per rendered update, not a complete spike
recording. Warnings and optional provenance come directly from the simulation.
The UI distinguishes loading, paused, running, stopped, and worker error states.
An exception displays its type/message in the browser and full traceback in the
server terminal. A crashed worker does not restart or reset an experiment silently.

## HTTP endpoints

- `GET /api/state`: worker status, telemetry, frame sequence, age, camera and speed.
- `GET /api/frame`: latest JPEG, or HTTP 204 before the first render.
- `POST /api/control`: JSON command, HTTP 202 once queued (not yet applied).

The control endpoint validates command shapes and rejects requests from a foreign
browser origin. All endpoints also restrict the Host header to the loopback
viewer address, preventing an external hostname from masquerading as the local
origin through DNS rebinding. No simulation data is sent to an external service.

## Verification boundary

`tests/test_viewer.py` uses a deliberately labeled fake runner to check worker
lifecycle, control delivery, frame generation, bounded state publication, HTTP
validation, and visible error propagation. These tests do not validate fly biology
or real MuJoCo rendering. A real-runtime browser check is separately required for
the integrated simulation.

The wind integration was inspected with the real full-graph conductance runner
in a separate paused viewer on port 8767 using `configs/male-wind-reference.json`.
The rendered dashboard showed left/right source azimuth 0.0°, relative flow
596.0 mm/s, steady reference angles −8.05°/−8.24°, and the female-reference and
unmapped-pathway caveats. The existing running port-8766 experiment was not reset
or controlled by that check.
