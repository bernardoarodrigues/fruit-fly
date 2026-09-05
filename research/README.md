# Research overview: from connectome to embodied animal

Snapshot: 2026-09-04. Recommendation: build a **modular, experimentally testable digital fly**, with explicit fidelity limits per subsystem. Use sex-specific brain-and-VNC data, a MuJoCo body, calibrated sensory adapters, and separate physiological dynamics. Grow the model through validated assays rather than assuming that a large wiring diagram supplies the rest of the organism.

> **Implementation update:** the active scope is one male, with a working full-MaleCNS neural/body loop and live viewer. The initial two-body recommendation below is retained as the dated research proposal. Follow [the active single-fly plan](../docs/PLAN.md), [current evidence and remaining gates](../docs/STATUS.md), and [reproduced findings](10-implementation-findings.md) for current work.

## Findings that change the plan

1. **Female connectomes are available.** The 2024 FlyWire paper maps a female brain. The newer [BANC paper](https://www.nature.com/articles/s41586-026-10735-w) maps brain and nerve cord in another female specimen, including abdominal circuitry relevant to reproduction. Use MaleCNS and BANC as distinct anatomical scaffolds. Activating extra neurons in a male network is not a substitute for the female's wiring and physiology.
2. **Anatomical completeness is not functional completeness.** The final provided male paper reports 166,700 neurons, 124.2M retained synaptic links and 25.6M neuron-pair edges; only 40.1% of detected links have both ends attached to proofread neurons. BANC has different coverage and missing sensory regions. These are valuable structural priors, not parameter-complete working nervous systems. See [exact scope and counts](01-connectomes-and-neural-models.md).
3. **Existing embodiment still uses substantial controller assumptions.** Eon's technical account and the inspected repository are useful references; they do not supply the requested all-system organism. The original brain model is a replication starting point; its accuracy is scoped to selected experiments. See [code/claims audit](07-reference-code-audit.md).
4. **MuJoCo is the practical initial engine.** Current FlyGym 2.1.0 + NeuroMechFly ran on this Mac. Original FlyBody is the flight reference. The old sensory-rich FlyGym API and current 2.x API differ; the code must be pinned. Neither already supplies sex-specific reproduction or a complete muscle model. See [body audit](02-body-physics-and-software.md).
5. **Food needs several distinct mechanisms.** Airborne identity-bearing plumes, contact taste, ingestion, water/energy/protein balance, gut feedback and learning have separate roles. Reproduction additionally requires courtship/sound/pheromones, receptivity, copulation, transfer/storage and egg production/laying. See [behavior survey](03-behavior-senses-and-reproduction.md).

## Initial research proposal (historical; implementation now focuses on one male)

- **Body/world:** pinned FlyGym/NeuroMechFly in MuJoCo, two bodies in a 50 × 30 mm walking arena; textured floor, food/water, controllable odor and visual stimuli. The larger architecture can expand arena dimensions when assays require it.
- **Neural baseline:** replicate Shiu with compatible FlyWire data; then a persistent sensor-to-brain-to-motor loop. Import MaleCNS and BANC as separately validated configurations, retaining missing-data uncertainty.
- **Sensors:** local bilateral odor time series, contact taste, vision, proprioception; then auditory, pheromonal, thermal, humidity and interoceptive channels.
- **Physiology:** explicit reduced state for hunger, thirst and gut fullness first; later reproductive and sleep/learning dynamics, each tied to evidence.
- **Validation:** neural perturbations, controller-only/rewired controls, held-out conditions, timestep convergence and resource conservation. Success is assay-specific and must be reported that way.

An already-executed prototype is in [../prototype](../prototype/README.md): two articulated bodies, food/water geometry, a simplified odor field sampled at both antennae, and contact-only tarsal taste. It uses fixed locomotion commands, common female-derived anatomy, and uncalibrated receptor parameters. Its successful execution verifies infrastructure, not neural behavior or a complete digital organism.

## Reading map

| Note | Contents |
|---|---|
| [01 — Connectomes and neural models](01-connectomes-and-neural-models.md) | Male/female scope; final-paper corrections; BANC/MaleCNS limitations; data downloads and licensing |
| [02 — Body, physics and software](02-body-physics-and-software.md) | FlyBody vs NeuroMechFly; current API changes; physics/flight/muscles; local execution evidence |
| [03 — Behavior, senses and reproduction](03-behavior-senses-and-reproduction.md) | Broad systems inventory, implementation abstractions, quantitative-data leads, reproductive sequence and validation assays |
| [04 — System architecture](04-system-architecture.md) | World/fields, persistent neural engine, motor interface, two-agent timing, physiological and data boundaries |
| [05 — Roadmap and validation](05-build-roadmap-and-validation.md) | Milestones and exit criteria, causal controls, uncertainty, compute sizing and full-loop benchmarks |
| [06 — Hypotheses and open questions](06-hypotheses-and-open-questions.md) | Falsifiable candidate insights, alternatives and unresolved scientific requirements |
| [07 — Reference code audit](07-reference-code-audit.md) | Pinned Shiu/Eon source inspection; licenses, stimulation/silencing semantics and benchmark interpretation |
| [08 — Bibliography](08-bibliography.md) | Consolidated linked source index; detailed records remain in domain JSON registries |
| [09 — Access and downloads](09-access-and-downloads.md) | Every supplied reference accounted for; open-access alternatives and optional methods requests |
| [10 — Implementation findings](10-implementation-findings.md) | Reproduced data/model issues, negative results and practical consequences; no biological novelty claim |
| [11 — Current mechanism findings](11-current-mechanism-findings.md) | Native-body feedback, rolling references, afferent event semantics and discriminating next tests |
| [12 — Persistent loop and physiological constraints](12-persistent-loop-and-physiological-constraints.md) | Twelve-second results, sensory-only negative endpoint, exact voltage attribution and synaptic/airflow units |
| [13 — Antennal-lobe inhibitory constraints](13-antennal-lobe-inhibitory-constraints.md) | Fast/slow and presynaptic inhibition, spiking versus graded source evidence, exact-type limits and proposed comparisons |

## How to interpret the notes

**Evidence** is what the source reports within its assay. **Locally reproduced** means a recorded execution in this workspace. **Proposal/assumption** is a chosen implementation. **Inference/hypothesis** needs testing. No new biological discovery or novelty claim is made here.

The initial research proposal called for a narrow neural replication and persistent backend. Those engineering steps have since been executed and are recorded in the current implementation status. The long-term target remains two sex-specific animals; current development focuses on one male, with major sensory, physiological and behavioral validation gates still open.
