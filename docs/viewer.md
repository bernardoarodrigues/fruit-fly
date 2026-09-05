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
pacing. Actual speed is measured by the simulation and shown separately. A
computer unable to reach the target runs as fast as it can. Pausing and camera
changes do not advance simulated time. Reset reconstructs state through the
runner's reset command. Stimulus sliders report requested values; the underlying
runtime defines how those values change sensory input.

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

Odor/light values are in `[0, 2]`; zero disables the input. The viewer implements
`pause`, `camera`, and `speed` itself. It steps in small quanta (default 0.01
simulated seconds), checks commands between quanta, and renders up to eight
frames per wall-clock second. Frame/update queues have fixed capacity and drop
old frames, so rendering cannot accumulate unlimited queued video. A single slow
simulation quantum still delays a control; its duration depends on model size and
available compute. The HTTP server stays responsive independently.

Optional viewer configuration:

```json
{"viewer": {"paused": false, "camera": "follow", "speed": 1.0,
            "step_seconds": 0.01, "fps": 8}}
```

Telemetry keys are optional and absent values display as unknown:

```text
t_s, realtime_factor, behavior
pose: {position_mm: [x, y, z], heading}
physiology: {energy, hydration, crop}             # normalized [0, 1]
senses: {odor: [left, right], taste_food, taste_water}
neural: {neurons, edges, active_neurons, spikes, output_rates,
         ablated, backend, ablation_description?}
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
browser origin. No simulation data is sent to an external service.

## Verification boundary

`tests/test_viewer.py` uses a deliberately labeled fake runner to check worker
lifecycle, control delivery, frame generation, bounded state publication, HTTP
validation, and visible error propagation. These tests do not validate fly biology
or real MuJoCo rendering. A real-runtime browser check is separately required for
the integrated simulation.
