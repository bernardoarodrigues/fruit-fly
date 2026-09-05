# Embodied digital Drosophila

A research simulator coupling the **166,700-neuron male CNS** to one articulated MuJoCo fly. Current scope: one male; a second fly and paired reproduction are deferred. Research, source audits, negative results and hypotheses are retained here.

**Working:** full retained MaleCNS import, persistent sparse spiking engine, physical body with bilateral odor/contact sensing and finite resources, a live browser viewer, and neural-to-motor positive/negative controls. **Not yet validated:** odor-guided foraging, a biologically calibrated male neural model, male articulated morphology, or the full behavioral repertoire. The default body uses a declared NeuroMechFly/CPG surrogate. An optional FlyBody body and learned motor policy now run the same full male graph through three reviewed 12-second trials with lossless spike records. See [current evidence](docs/STATUS.md) and the [single-fly plan](docs/PLAN.md).

## Install and watch

Python 3.12 and uv were used on Apple Silicon. From the repository root:

```sh
uv venv --python 3.12
uv sync --extra test
.venv/bin/python -m fruitfly.data build
.venv/bin/python -m fruitfly.data verify
.venv/bin/python -m fruitfly.viewer --config configs/male-sensory.json --port 8765
```

Open [the local viewer](http://127.0.0.1:8765). It shows actual current simulation frames, neural counts, sensory readings and resource state, with pause/reset, three cameras, odor/light controls and a motor-readout mute. The server binds to loopback.

The data command downloads about **1.11 GB** from the authors' public release, verifies pinned SHA-256 checksums, and builds 25,582,938 directed neuron-pair edges representing 124,177,617 contacts. All selected neurons, including 217 isolated neurons, remain present. Raw/processed data are ignored by Git; the [provenance manifest](data/malecns-manifest.json) is tracked. Transmitter-to-sign and contact-to-weight rules are explicitly recorded assumptions.

The sensory assay currently rests: transferred Shiu dynamics over-suppress the walking readouts. This is a calibration failure, not evidence that the biological fly would remain still. A separately labeled **direct DNg97 stimulation** assay demonstrates motor coupling:

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-motor-calibration.json --port 8766
```

That assay is motor calibration, not emergent foraging. Light currently changes the physical scene; validated visual-to-neural mapping remains pending.

`configs/male-multisensory-probe.json` additionally enables actual 50 Hz compound-eye images and an optional leg-specific FeCO club input proxy. `configs/male-taste-contact.json` starts on food to inspect the validated tarsal taste/feeding interface. `configs/male-conductance-sensory.json` selects the separately tested, experimental conductance model. Its bounded voltages do not yet establish calibrated navigation.

`configs/male-wind-reference.json` adds relative airflow at both antennae and a domain-limited empirical deflection reference from verified female wind measurements. It is not a wind-to-neuron adapter. The separate viewer can be launched on port 8767. Research acquisition/analysis tools use `uv sync --extra test --extra morphology --extra research` with the committed lockfile.

`configs/male-grooming-probe.json` directly stimulates two identified left descending neurons, which gate one measured female grooming trajectory through the physical body. Launch it on port 8768 and use Reset to replay. The [four-condition check](docs/grooming-loop.md) verifies neural gating, actual contacts, cancellation and no tonic repetition. This is an optional motor calibration assay; natural sensory-driven grooming remains unvalidated.

`configs/male-grooming-sensory-probe.json` instead stimulates 42 audited JO-F antennal sensory cells. The [two-seed body assay](docs/grooming-sensory-loop.md) passes 18 controls, including unchanged sensory spike trains with all downstream activity and movement abolished by blocking sensory outputs. Launch on port 8769. Inputs are imposed neural events; physical touch transduction and natural grooming are not yet calibrated.

`configs/male-world-illumination-probe.json` enables a fixed arena lamp with camera headlights disabled. Launch it on port 8770. The [lighting checks](docs/world-illumination.md) cover sampled physics invariance, shadows, eye responses and the live light/reset controls. Renderer brightness remains an engineering stimulus, with neural vision mapping pending.

The optional [FlyBody runtime](docs/flybody-bridge.md) uses a separately pinned Python 3.10 environment and its original pretrained walking policy. After its one-time [setup](docs/flybody-bridge.md#install-and-watch), launch:

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-probe.json --port 8771 --paused
```

Open [the bounded FlyBody viewer](http://127.0.0.1:8771), then Resume. This direct-neuron calibration trial runs for **2 simulated seconds**, displays **Trial complete**, and keeps Reset and camera controls available. Four [full-graph trials](docs/flybody-loop.md) verify physical sensory feedback and motor coupling.

For the reviewed rolling controller with optional local antenna airflow, launch:

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-rolling-airflow-probe.json --port 8773 --paused
```

Open [the rolling FlyBody viewer](http://127.0.0.1:8773) and Resume. [Three 12-second neural trials](docs/flybody-rolling-loop.md) retain every ordered spike and repeated stop/resume controls. The sensory-only trial remained at rest; none contacted food. The rolling reference removes the artificial two-second limit while retaining physical termination guards. Airflow reports motion-relative velocity at proximal antenna origins; it supplies no wind-driven neural input. These remain engineering trials with an unbounded source floor and an uncalibrated neural model.

For a small [physical habitat](docs/flybody-habitat.md) with food and water regions, launch:

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-rolling-habitat.json --port 8774 --paused
```

Open [the 30 × 24 mm habitat](http://127.0.0.1:8774). This sensory assay currently rests; the new walls do not supply an avoidance behavior. A separately labeled straight-command trial contacts a wall and stops at 0.768 s under the original physical guard. [Actual browser checks](docs/flybody-habitat-viewer.md) verify pause/reset and distinguish the last image from the failed state. The enclosure is open above its 6 mm walls, and odor advection has no wall-flow model.

The [independent scene review](docs/flybody-habitat-scene-independent-review.md) checks the final render correction, retained physical/controller states and saved UI evidence, while preserving the earlier failed outcomes.

## Validate and investigate

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_loop.py
.venv/bin/python scripts/validate_taste.py
```

Runs write configuration, graph hash, exact input/output IDs, dependency versions, telemetry, interventions and final state to `runs/`. Fixed coupling boundaries preserve behavior across browser update chunks. Missing graph data and invalid timing fail explicitly.

- [Neural engine](docs/neural-engine.md), [original Shiu replication](docs/replication.md), [male motor diagnosis](docs/motor-calibration.md)
- [Body and units](docs/body-runtime.md), [sensory mapping evidence](docs/sensory-mapping-evidence.md), [viewer](docs/viewer.md)
- [Conductance dynamics](docs/conductance-model.md), [proprioceptive mapping](docs/proprioception-mapping.md), [navigation calibration](docs/navigation-calibration.md), [internal state and learning](docs/internal-state-learning-plan.md)
- [Experimental nonspiking/graded transmission](docs/graded-model.md), with independent equation checks and an unchanged full-graph assay
- [Measured wind calibration](docs/wind-calibration.md), [wind neural targets](docs/suver-neural-calibration.md), [slow-circuit reproduction](docs/navigation-memory-model-audit.md), [measured grooming and free behavior](docs/grooming-model-audit.md)
- [Grooming neural/body controls](docs/grooming-loop.md), [measured joint replay](docs/grooming-replay.md), [free-running dataset timing and units](docs/freewalking-data-alignment.md)
- [Measured walking comparison](docs/freewalking-benchmark.md), [implementation findings and open implications](research/10-implementation-findings.md)
- [CPG calibration: no candidate promoted](docs/cpg-calibration-experiment.md), [visual column/mapping audit](docs/visual-input-mapping.md), [wind transduction limits](docs/wind-transduction-boundary.md)
- [Isolated circadian model reproduction](docs/circadian-lg1998.md), [independent numerical review](docs/circadian-independent-review.md)
- [Calibrated camera ray footprints](docs/retina-ray-calibration.md), [circadian coupling limits](docs/circadian-coupling-boundary.md)
- [FlyBody policy compatibility trial](docs/flybody-inference-trial.md), [physical feeding and circuit-replay audit](docs/feeding-motor-expansion.md)
- [Independent feeding review](docs/feeding-independent-review.md), [muscle mechanics and timestep audit](docs/musculoskeletal-feasibility.md), [unresolved muscle identifiers](docs/muscle-identifier-boundary.md)
- [Male column/female optics registration boundary](docs/visual-retinotopy-feasibility.md), [measured-template camera coverage](docs/visual-template-coverage.md)
- [Fixed FlyBody comparison and stopping failure](docs/flybody-motor-comparison.md)
- [Engineering posture holds and restart experiment](docs/flybody-stance-experiment.md), [independent actuator/trace review](docs/flybody-stance-independent-review.md)
- [Optional fixed arena illumination](docs/world-illumination.md)
- [Native FlyBody bridge and parity](docs/flybody-bridge.md), [four full-graph trials](docs/flybody-loop.md), [independent saved-journal review](docs/flybody-loop-independent-review.md)
- [Twelve-second rolling neural loop](docs/flybody-rolling-loop.md), [motion and voltage outcomes](docs/flybody-rolling-loop-outcomes.md), [independent spike/state review](docs/flybody-rolling-loop-independent-review.md), [optional FlyBody airflow](docs/flybody-airflow-runtime.md)
- [Isolated olfactory synaptic transfer](docs/orn-pn-transfer-audit.md), [independent matrix-exponential review](docs/orn-pn-transfer-independent-review.md)
- [Published scalar synaptic-depression reference](docs/synaptic-depression-reference.md), [independent high-precision review](docs/synaptic-depression-reference-independent-review.md); fixed-source predictions, no biological fit or neural integration
- [Recorded-input reconstruction of extreme-voltage cells](docs/negative-voltage-replay.md), with exact endpoint states and signed incoming-edge accounting; [381-check independent review](docs/negative-voltage-replay-independent-review.md)
- [Executed inhibitory factorial](docs/inhibitory-factorial.md): bounded hybrid voltages, unchanged two-cell spike trains, no model promotion; [recurrent comparison design](docs/inhibitory-recurrent-design.md)
- [Reviewed Eon P9/taste neural panel](docs/eon-p9-context-independent-review.md); body benchmark cancelled. [BANC comparative circuit audit](research/17-banc-comparative-circuit-insights.md) preserves female CNS matches and annotation uncertainty
- [Published VM2 recovery curves as numerical data](docs/orn-pn-recovery-digitization.md), with separate protocols and graph-extraction limits; [inhibitory physiology and source signaling](research/13-antennal-lobe-inhibitory-constraints.md)
- [Quantified inhibitory current/rate timing contrast](docs/ln-inhibitory-transfer-phase2.md), with conservative graphical intervals, separate cohorts and no physiological fit
- [Public inhibitory-source data inventory](docs/salman-source-inventory.md), [current-clamp workbook and published-current discrepancy](docs/salman-current-clamp-data.md); exact arithmetic does not resolve missing specimen/current metadata
- [Recovered GABA-reversal supplement](docs/wilson-gaba-reversal-source.md); recording-solution effects and unreached reversals remain distinct from exact-cell physiological parameters
- [Viewer failure-state reporting](docs/viewer-failure-reporting.md), with [independent clock and cleanup review](docs/viewer-failure-independent-review.md)
- [Chemical odor responses, baseline/missingness and receptor identity audit](docs/door-odor-audit.md), [primary Or42a response and unresolved baseline offset](docs/or42a-primary-assay.md), [executed excitation assay](docs/or42a-summary-experiment.md)
- [Source proboscis geometry and missing motion/contact data](docs/proboscis-mechanics.md)
- [Full optical-template sampling through six views](docs/multiview-eye.md), including moving-head, cube-seam and lighting checks
- [Ten-second full-brain runs and feeding/restart interaction](docs/extended-loop.md), [independent saved-data review](docs/extended-loop-independent-review.md)
- [Full-loop checks](validation/closed-loop/results.json), [neural benchmark](validation/neural-benchmark.json), [Shiu results](validation/shiu/results.json)
- [Research overview](research/README.md), [architecture](research/04-system-architecture.md), [broader roadmap](research/05-build-roadmap-and-validation.md), [hypotheses](research/06-hypotheses-and-open-questions.md), [paper access](research/09-access-and-downloads.md)

The supplied PDFs remain unchanged; [metadata and hashes](research/provided-papers.json) identify them. The [earlier two-body prototype](prototype/README.md) remains as historical scaffolding. See [third-party attribution](THIRD_PARTY.md).
