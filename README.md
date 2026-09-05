# Embodied digital Drosophila

A research simulator coupling the **166,700-neuron male CNS** to one articulated MuJoCo fly. Current scope: one male; a second fly and paired reproduction are deferred. Research, source audits, negative results and hypotheses are retained here.

**Working:** full retained MaleCNS import, persistent sparse spiking engine, physical body with bilateral odor/contact sensing and finite resources, a live browser viewer, and neural-to-motor positive/negative controls. **Not yet validated:** odor-guided foraging, a biologically calibrated male neural model, male articulated morphology, or the full behavioral repertoire. The body and gait controller are declared NeuroMechFly/CPG surrogates. See [current evidence](docs/STATUS.md) and the [single-fly plan](docs/PLAN.md).

## Install and watch

Python 3.12 and uv were used on Apple Silicon. From the repository root:

```sh
uv venv --python 3.12
uv pip install -e '.[test]'
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

## Validate and investigate

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_loop.py
```

Runs write configuration, graph hash, exact input/output IDs, dependency versions, telemetry, interventions and final state to `runs/`. Fixed coupling boundaries preserve behavior across browser update chunks. Missing graph data and invalid timing fail explicitly.

- [Neural engine](docs/neural-engine.md), [original Shiu replication](docs/replication.md), [male motor diagnosis](docs/motor-calibration.md)
- [Body and units](docs/body-runtime.md), [sensory mapping evidence](docs/sensory-mapping-evidence.md), [viewer](docs/viewer.md)
- [Full-loop checks](validation/closed-loop/results.json), [neural benchmark](validation/neural-benchmark.json), [Shiu results](validation/shiu/results.json)
- [Research overview](research/README.md), [architecture](research/04-system-architecture.md), [broader roadmap](research/05-build-roadmap-and-validation.md), [hypotheses](research/06-hypotheses-and-open-questions.md), [paper access](research/09-access-and-downloads.md)

The supplied PDFs remain unchanged; [metadata and hashes](research/provided-papers.json) identify them. The [earlier two-body prototype](prototype/README.md) remains as historical scaffolding. See [third-party attribution](THIRD_PARTY.md).
