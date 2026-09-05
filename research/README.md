# Research overview: from connectome to embodied animal

Snapshot: 2026-09-05. Recommendation: build a **modular, experimentally testable digital fly**, with explicit fidelity limits per subsystem. Use sex-specific brain-and-VNC data, a MuJoCo body, calibrated sensory adapters, and separate physiological dynamics. Grow the model through validated assays rather than assuming that a large wiring diagram supplies the rest of the organism.

> **Implementation update:** the active scope is one male, with a working full-MaleCNS neural/body loop and live viewer. The initial two-body recommendation below is retained as the dated research proposal. Follow [the active single-fly plan](../docs/PLAN.md), [current evidence and remaining gates](../docs/STATUS.md), and [reproduced findings](10-implementation-findings.md) for current work.

## Findings that change the plan

1. **Female connectomes are available.** The 2024 FlyWire paper maps a female brain. The newer [BANC paper](https://www.nature.com/articles/s41586-026-10735-w) maps brain and nerve cord in another female specimen, including abdominal circuitry relevant to reproduction. Use MaleCNS and BANC as distinct anatomical scaffolds. Activating extra neurons in a male network is not a substitute for the female's wiring and physiology.
2. **Anatomical completeness is not functional completeness.** The final provided male paper reports 166,700 neurons, 124.2M retained synaptic links and 25.6M neuron-pair edges; only 40.1% of detected links have both ends attached to proofread neurons. BANC has different coverage and missing sensory regions. These are valuable structural priors, not parameter-complete working nervous systems. See [exact scope and counts](01-connectomes-and-neural-models.md).
3. **Eon's embodiment supplies a practical integration recipe.** The [expanded public-code audit](15-eon-public-code-audit.md) found an additional notebook with explicit P9 walking-context stimulation, leg-taste inputs and stored motor-neuron responses. The [reviewed neural panel](../docs/eon-p9-context-independent-review.md) found context-dependent recruitment and persistent physiological failures. The user cancelled the body integration benchmark. The subsequent [inhibitory factorial](../docs/inhibitory-recurrent-panel-results.md) is complete; current work follows the [staged navigation ladder](../docs/navigation-ladder-plan.md). Exact physical-demo mappings remain unspecified; the original [code audit](07-reference-code-audit.md) records the narrower first pass.
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
| [14 — Obstacle avoidance](14-obstacle-avoidance-evidence.md) | TLA/MDN and tactile/visual candidates; exact male identities and missing physical transduction |
| [15 — Eon public code](15-eon-public-code-audit.md) | Expanded repository inventory, exact neural test protocols and retained author output tables |
| [16 — Eon integration insights](16-eon-integration-insights.md) | What can be reused now; local comparison; locomotor context and sensory entry-level hypotheses |
| [17 — BANC comparative circuits](17-banc-comparative-circuit-insights.md) | Female CNS metadata, exact-type/motor crosswalks, annotation conflicts and limits on physiological inference |
| [18 — Navigation anatomy](18-navigation-ladder-anatomy.md) | Verified route contacts, exact/family and cognate/pooled selections, full DN population, missing angle/mirror registration |
| [19 — Navigation assay evidence](19-navigation-ladder-assay-evidence.md) | Primary still-air/wind/state protocols, hDelta driver corrections, calcium-versus-spike limits and bounded causal interventions |
| [20 — KC–MBON functional calibration](20-kc-mbon-functional-calibration.md) | Direct KC/MBON activity audit, exact-type physiological targets, connectome limits, intervention interpretation and prospective calibration gates |
| [21 — PN–KC physiology](21-pn-kc-physiology-calibration.md) | Source-defined EPSP/EPSC and claw-integration assays, intrinsic time-constant mismatch, preparation and data limits |
| [22 — APL local feedback](22-apl-local-feedback-constraints.md) | Nonspiking evidence, spatial calcium/release/suppression measurements and missing conversion laws |
| [23 — KC contact locations](23-kc-contact-location-availability.md) | Verified local flat-graph schema and public same-version spatial data for a future compartment audit |
| [24 — KC spatial mechanisms](24-kc-spatial-mechanism-constraints.md) | Primary γ-axon muscarinic modulation evidence, electrical/sex-transfer limits, ROI names and public source-data leads |
| [KC waveform comparison](../docs/kc-synaptic-response.md) | Executed five-arm local assay, conditional timing tradeoff, separate somatic constraint and independent mathematical derivation |
| [Fixed Turner reference](../docs/turner-kc-conductance.md) | Executed published conductance equations, approximate intended amplitudes and retained timing/intrinsic differences |
| [KC/APL contact locations](../docs/kc-apl-contact-locations.md) | Exact spatial reconciliation of all modeled KC/APL contacts, raw neuropil distributions and outside-graph records |

## How to interpret the notes

**Evidence** is what the source reports within its assay. **Locally reproduced** means a recorded execution in this workspace. **Proposal/assumption** is a chosen implementation. **Inference/hypothesis** needs testing. No new biological discovery or novelty claim is made here.

The initial research proposal called for a narrow neural replication and persistent backend. Those engineering steps have since been executed and are recorded in the current implementation status. The long-term target remains two sex-specific animals; current development focuses on one male, with major sensory, physiological and behavioral validation gates still open.
