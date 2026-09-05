# Physical arena smoke example

This runs two **physical NeuroMechFly bodies controlled by a hybrid CPG/reflex walking controller** in a 50 × 30 mm walled MuJoCo arena. It is not a connectome simulation. Both instances currently have the same female-derived geometry; naming one male would not implement male anatomy. There is no feeding, reproduction, or physiological model in this baseline.

## Install and run

Run from the project root, using Python 3.12:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r prototype/requirements.txt
.venv/bin/python prototype/arena_smoke.py --seconds 1 --output prototype/output
```

The exact inspected FlyGym commit is pinned in `requirements.txt`; its API is 2.1.0. Older FlyGym examples using `Fly`, `OdorArena`, and Gymnasium observations belong to the separately packaged `flygym-gymnasium` 1.x and are not drop-in compatible. The basic install has bundled simplified meshes and needs no policy checkpoint or connectome download.

The project-local `.venv` is already installed and both commands were executed with it. `requirements-lock.txt` records the complete resolved environment; use that file in place of `requirements.txt` to reproduce the transitive package versions from this run.

On the current Mac, the already-created test interpreter also works:

```sh
/tmp/fruit-fly-body-smoke-venv/bin/python prototype/arena_smoke.py --seconds 1 --output prototype/output
```

For a server without a display, set `MUJOCO_GL=egl` and `PYOPENGL_PLATFORM=egl` before running, or add `--no-render` to test only physics. These EGL settings were not used or tested on this Mac. Optional NVIDIA Warp dependencies are unnecessary here and do not provide Apple GPU acceleration.

## Verified result

Tested on macOS arm64 with Python 3.12.14, FlyGym 2.1.0 at `38c8ec61034cd59bc5ba0de20688d4a3c0000d60`, MuJoCo 3.9.0, and NumPy 2.5.2. The final walled two-fly run advanced 1 simulated second at 0.1 ms physics steps in **9.54 s wall time**, excluding construction, warmup and rendering. Both flies moved ~13 mm with finite positions and velocities. The earlier 7.60 s measurement preceded the explicit observation-cache synchronization fix and is not the current script's measurement. These are smoke measurements under current machine load, not statistically controlled benchmarks or evidence of biological fidelity.

Outputs: `output/arena.png`, `output/metrics.json`, and `output/thorax_trace.csv`. Rendering was inspected visually. The trace samples thorax position at 100 Hz. The model has 144 velocity degrees of freedom and 96 actuators across both bodies. Ground/wall contact pairs and inter-fly collision masks are enabled; this short run does not validate mating contact or long-term confinement.

## Odor and contact sampling example

```sh
.venv/bin/python prototype/stimulus_smoke.py --seconds 1
.venv/bin/python prototype/stimulus_smoke.py --check-field
```

`stimulus_smoke.py` adds physical food/water markers, samples a Gaussian-puff odor field at both modeled antennae, and detects actual food contacts at tarsal geometry. It records an illustrative saturating/adapting receptor signal and binary contact taste at 1 ms intervals. Locomotion still receives fixed commands: this is sensory instrumentation, not neural foraging, ingestion, or reproduction. Water is a physical/visual marker with no hydration model. Proboscis contact pairs are not enabled in this locomotion preset.

Both scripts refresh MuJoCo's derived position/contact caches before observations; the arena trace records post-step timestamps and the stimulus trace records pre-step timestamps, each relative to the end of warmup.

The field uses SI coordinates, a reflecting floor and open lateral boundaries; its wind is prescribed independently of the arena walls. Odor amount and receptor parameters are arbitrary engineering values, not calibrated Drosophila receptor measurements. Tests check nonnegativity, bilateral symmetry without wind, distance decay and linear scaling with source mass.

The executed one-second trial took **10.29 s wall time** excluding setup/render and produced 2,000 fly-sample rows with finite body states; both flies registered food contact (573 and 537 sample times respectively). Results are `output/stimuli_metrics.json`, `output/stimuli_trace.csv`, and `output/arena-food.png`. This shows functioning geometry/field/sampling plumbing, not biological odor navigation. Timing is a single local smoke measurement.

## Extension interface

`build_simulation(fly_count=2, add_scene=None)` returns `(sim, flies, controllers)`. An optional `add_scene(world)` callback adds environment geometry before model compilation; append additional contact surfaces to `world.ground_geoms`. Geometry uses native MuJoCo `MjSpec` (`world.mjcf_root.worldbody.add_geom(...)`). Configure visual-only food markers with `contype=0, conaffinity=0`; add physical surfaces explicitly when needed.

For every simulation step, compute all flies' observations and actions, call `apply_locomotion_action` for each, then call `sim.step()` **once** for the shared world. `HybridControllerObservation.from_sim(...)` includes a `fly_heading` vector. `thorax_positions(sim, flies)` returns world positions in mm. For realistic odor sampling use the antenna body/site positions, not a hidden vector to the food target. The controller receives two dimensionless left/right drive values. Replacing this command generator with a connectome interface is future work, and its motor decoding must be documented and calibrated.

The FlyGym and MuJoCo source repositories are Apache-2.0; retain applicable upstream license/attribution notices if vendoring assets or code. This prototype imports the installed packages and does not copy meshes into the project.
