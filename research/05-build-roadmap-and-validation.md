# Build roadmap and validation contract

Snapshot: 2026-09-04. Proposed work, ordered by evidence dependencies. Calendar estimates would be misleading before benchmarking and data import; use the exit conditions below.

## Milestones

| Stage | Deliverable | Exit condition | What it does not establish |
|---|---|---|---|
| 0. Freeze evidence | Versioned papers, source registry, hashes, licenses, assay scope | Every imported data product has specimen/release/units/filter provenance | Physiological completeness |
| 1. Physical arena | Two articulated adults, terrain, contacts, food/water geometry, externally controllable stimuli | Deterministic replay; stable contacts; movement comparable to reference controller; two bodies coexist | Neural control or true sexual body dimorphism |
| 2. Sensory pipeline | Bilateral odor, contact taste, vision, proprioception, auditory stimulus interface | Calibration/unit tests; receptor-specific inputs; no hidden target coordinates | Natural sensory tuning without calibration |
| 3. Neural replication | Original Shiu circuit trials using the original compatible data and parameters | Reproduce selected published response comparisons and quantify stochastic uncertainty | Whole-behavior fidelity or body integration |
| 4. Persistent loop | One neural model drives a physical fly, then two independent models share a world | Continuity of delayed events; converged coupling step; behavior changes under relevant neural ablation | Full VNC/muscle control |
| 5. Sex-specific CNS | MaleCNS and BANC imports with explicit incomplete regions and crosswalks | Count/ID/filter integrity and declared sign rules verified; sensory-to-motor circuit tests; results robust to plausible missing-edge models | Population-wide male/female differences from two specimens |
| 6. Foraging and feeding | Odor navigation, contact taste, ingestion and depletion, energy/water state | Held-out plume/food layouts; intake balance; hunger/thirst perturbations; neural dependence | Complete digestion or lifetime metabolism |
| 7. Social/reproductive assays | Courtship sequence, song response, receptivity, abstract copulation/transfer, storage, oviposition | Multimodal and state-dependent behavior matches assay data; explicit physiological state transitions | Anatomically resolved fertilization or a developmental digital twin |
| 8. Mechanistic expansion | Replace selected low-level controllers with VNC–motor–muscle circuits | Improvement on neural and kinematic holdouts, lesion specificity, no loss of stability | Universal fly behavior |
| 9. Lifespan/flight | Calibrated flight, sleep, long-term learning, development modules where useful | Separate validated assays for each; transparent change in fidelity | Exhaustive reproduction of all biology |

Stage 1 can be interactive. Neural replication and long experiments can initially run offline. Make sex-specific brain-and-VNC imports available early as a parallel data track without skipping the known-model replication reference.

## Experiments that distinguish a neural model from a convincing animation

1. **Brain ablation:** run the same initial world with intact neural model, zeroed neural outputs, time-shuffled outputs, and a locomotion-only controller. Relevant sensory-guided decisions should depend on neural output; basic gait may persist in a controller-based baseline.
2. **Structural controls:** compare the actual graph with degree/sign-preserving rewired graphs and a matched-capacity fitted controller. Preserve stimulation and parameter search budgets across conditions. A behavior replicated equally well without the original structure is weak evidence for the connectome's causal contribution.
3. **Sensory dissociation:** move odor independently of visible food; place nonnutritive sweet substrate and odorless nutrients; remove unilateral/bilateral odor; swap flow direction. Use identical evaluation rules across conditions.
4. **Closed-loop necessity:** compare live sensory feedback with a replay of a previous fly's sensory input. Shared stimulus statistics do not imply the same behavior when the animal's actions no longer affect input.
5. **Internal-state interventions:** alter hunger or hydration while holding the world fixed. Demand correct dissociation of water seeking, sugar response, protein preference, and locomotor changes where measured.
6. **Courtship factors:** vary sex, maturity, virgin/mated status, song, volatile/contact pheromones, visual motion, and recent experience independently. A generic “mate nearby” trigger will fail these tests.
7. **Reproduction bookkeeping:** ingestion, energy cost, sperm transfer/storage/use, egg production/laying, and parent identity must reconcile. A new egg requires the modeled conditions; a fertilized egg is distinct from a viable offspring.
8. **Timing and numerics:** halve neural, coupling, and body steps independently; compare neural response distributions, contact stability, trajectories, and event timing. Save simulation time and wall time separately.

The Eon technical account explicitly describes a sparse motor interface and missing validation; it motivates these controls but does not itself establish their outcomes. [Source](https://eon.systems/updates/embodied-brain-emulation)

## Validation data and statistics

Match species, strain, sex, age, hunger preparation, temperature, light cycle, substrate, and tethered versus freely moving preparation. Use measured distributions of speed, gait phase, turn rate, approach/return trajectories, proboscis extension, food intake, courtship bouts, song structure, mating latency, and egg placement, not hand-selected successful videos.

Hold out entire experimental conditions and source animals, not adjacent frames from a fitted trajectory. Define each primary endpoint and acceptable error before tuning. Report biological sample sizes separately from simulation seeds; 1,000 stochastic replicas of one connectome are not 1,000 independently mapped animals. Use uncertainty intervals and parameter sensitivity. Cross-sex comparison must account for recording/reconstruction differences and individual variation.

Do not use a published “91%” result as a global target. Shiu et al. report 91% consistency over 164 empirically tested predictions in the paper's experimental scope; that does not measure all fly behavior or accuracy of every neuron. [Paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446845/)

## Compute plan

Observed local hardware: Apple arm64, 24 GiB physical RAM. This is an environment observation, not the user's declared total compute budget. Start with CPU body/world smoke tests and reduced neural calibration. NVIDIA CUDA packages cannot be assumed to accelerate this Mac; Eon's current PyTorch device selection chooses CUDA when available and CPU otherwise, with no MPS path in the audited runner. [Pinned runner](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/run_pytorch.py)

Use an NVIDIA workstation/cloud GPU only after profiling demonstrates a need and the user supplies or approves that resource. Do not promise real-time two-CNS operation from a neural-only benchmark. Measure compilation, data load, neural steps, field solve, body steps, sensor rendering, device transfers, recording, and end-to-end latency independently.

Memory sizing example, calculated here: male CNS has about 25.6M aggregated neuron-pair edges in the provided final paper. CSR with float32 weights and int32 column indices uses approximately `8E + 4(N+1)` bytes, roughly 205 MB decimal for the matrix alone. This excludes duplicate tables, transmitter probabilities, delays, event queues, device copies, parameter arrays, and library overhead. With 64-bit indices it is about 309 MB. It is not a total RAM estimate.

Dense float32 weights for 166,700 neurons would require about 111 GB decimal. Avoid a dense matrix. At a hypothetical mean of 10 spikes/s across 166,700 neurons, 12 bytes per stored spike gives about 20 MB/s, or 72 GB/hour, before metadata and file overhead. This illustrative calculation is a logging warning, not an observed firing rate.

A time-stepped sparse update over 25.6M edges at 0.1 ms can visit roughly 256 billion edges per simulated second if it scans every edge each step. Event-driven computation has a different load profile; measure actual sparsity/activity, and preserve correct delays and synapse semantics. Two different connectomes need independent topology/state; batching two trials of one graph is not equivalent.

## Required checkpoint before claiming the requested system exists

- Two sex-specific, versioned neural imports are actually running, with documented sensory omissions.
- Movement and decisions respond causally to neural perturbations.
- Food scent/taste, ingestion, and internal reserves form a working loop.
- Courtship/reproductive outputs are identified as mechanistic, fitted, or procedural.
- The common world handles two bodies, fields, contact, and resource competition.
- Every claimed behavior has a reproducible assay and validation result.

The current research package is the basis for this program. A successful arena smoke test satisfies only a portion of Stage 1.
