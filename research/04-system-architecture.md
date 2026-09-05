# Proposed embodied Drosophila architecture

Research snapshot: 2026-09-04, America/Los_Angeles. This document is an engineering proposal, not an experimentally validated model. Source-specific evidence is in the adjacent research notes. Parameters below are starting values for convergence and calibration experiments, not measured biological constants.

## Scientific target

Build two autonomous adult *Drosophila melanogaster*, each with its own persistent nervous-system and physiological state, in one physical arena. Their behavior should arise from the sensory–neural–motor feedback loop wherever a validated neural mechanism exists. Every remaining fitted or procedural controller must be identifiable in recordings and experiment manifests.

“Fully digital” is achievable. “Complete biological equivalence across every behavior” is not an established deliverable from current data. Separate structural coverage, neural predictive accuracy, motor fidelity, behavioral generalization, and physiological coverage; never combine them into one fidelity percentage.

## Component boundaries

```text
Shared physical world: MuJoCo bodies, surfaces, food patches, water, obstacles
Shared fields: odor chemicals, wind, light, temperature, humidity, local sound
                         |
          sample at each animal's actual sensor positions
                         v
Sensory encoders: receptor-specific responses, adaptation, noise, latency
                         |
                         v
One persistent neural engine PER FLY: brain + VNC where supported
          ^              |                        ^
          |      motor/descending activity         |
          |              v                        |
  proprioception    neural-to-actuator mapping   physiological modulation
          |              |                        |
          +----- articulated body ----------- metabolism/reproductive state
                         |
                physical consequences in world
```

The environment never passes a food target coordinate, a mate's identity, shortest path, distance-to-reward, or a desired behavioral label into a biological-policy channel. Evaluation software may read these quantities. Training a low-level movement controller can use privileged information, but freeze and label that controller before testing brain-dependent behavior.

### World

Start with an approximately 40 × 40 × 10 mm enclosed arena, two separated adults, an appetitive yeast/sugar patch, water, an alternative substrate for oviposition, one obstacle, a textured floor, controlled illumination, and adjustable wind. These dimensions are an engineering choice for short walking assays; validate boundary effects against larger arenas. Flight needs a separately calibrated, larger arena and aerodynamic model.

Keep visual appearance, chemical composition, and nutritional content independent. A banana-colored object need not emit odor; an invisible odor source need not contain calories. This permits cue-conflict experiments. Food stores finite carbohydrate, protein, water, volume, and chemical emission state. Ingestion changes both patch inventory and fly reserves, with explicit units and mass-balance checks.

Use consistent SI units in external interfaces. Body libraries may use mm–mg–s conventions; convert coordinates, inertia, forces, gravity, and sensory geometry explicitly at one boundary. A mesh rescale alone is not a physically consistent rescale.

### Chemical fields and transduction

Use a vector of concentrations `c_k(x,y,z,t)`, one component per represented volatile; do not reduce every source to “food attraction.” Initial model: an analytically normalized diffusion plume or Gaussian puffs advected by wind. More demanding experiments can use a finite-volume advection–diffusion solver:

`∂c_k/∂t + ∇·(u c_k) = ∇·(D_k ∇c_k) + q_k - λ_k c_k`.

Specify no-flux/absorbing/outflow walls and source rates. Use nonnegative, conservative numerical updates and verify mass budgets. Molecular diffusivity, turbulent effective diffusivity, release rate, and receptor sensitivity are distinct parameters. A smooth static distance gradient is useful for debugging but inadequate evidence for biological plume tracking.

Sample separately at both moving antennae. Transform the ambient flow into the fly's head frame. Preserve encounter onset, offset, intermittency, bilateral differences, and stimulus history. An illustrative encoder is `r_j = clip(r0_j + f_j(c, adaptation), 0, rmax_j)`; use measured receptor responses where available, with uncertainty on concentration transfer across assays. DoOR normalized responses are useful priors, not universal Hz-per-concentration calibration. Transduction must represent inhibitory odor responses and mixtures where supported, rather than simply summing all positive affinities.

Taste is sampled only at appropriate contacting legs/proboscis. Cuticular contact pheromones require contact/proximity rules justified by the chemical; volatile pheromones can enter a field. Never let taste provide long-range food coordinates. Apply geometry-based occlusion and per-sensor delays to vision. Courtship sound needs direction, near-field particle-motion treatment appropriate to antennal sensing, and waveform/time resolution beyond rendered video frames; a simple far-field audio loudness law is only an approximation.

### Neural engine

Use the Shiu Brian2 model as a replication baseline for its specific published activation experiments. Treat the male CNS and BANC as separate model imports. Preserve neuron ID namespaces, materialization/release, cell type, confidence, transmitter probabilities, completeness, and specimen identity. Mapping corresponding cell types across datasets does not make their individual neuron IDs interchangeable.

Begin with sparse point-neuron dynamics where justified; refine critical circuits with cell-type parameters, graded transmission, receptor-dependent signs, compartmental dynamics, electrical coupling, and neuromodulation as evidence permits. EM contact count is a structural prior on weight, not a measured conductance. “All neurons spike with the same parameters” is a declared approximation; many visual neurons use graded signals. Do not insert a separately simulated visual pathway into an already active identical pathway without an explicit replacement boundary.

An import should retain raw contact multiplicity and a separately derived neuron-pair weight. Store a transform manifest including thresholds, excluded neurons/edges, sign assumptions, weight normalization, delay assumptions, and zero-degree cells. Do not silently remove weak synapses or compensate missing contacts with a universal gain. Distinguish no annotated connection from verified absence.

Required persistent state: membrane/synaptic variables, refractory state, delayed events, receptor adaptation, and random-generator state; also plasticity and neuromodulatory states when those mechanisms are enabled. The Shiu replication baseline has fixed weights. The short-step API should resemble `advance(duration, sensory_drive, modulation) -> timestamped_outputs`; it must preserve state across calls. Rebuilding the brain at each frame invalidates recurrent dynamics and memory.

### Motor interface and its evidence level

Maintain two explicit modes:

1. **Practical baseline:** population activity of identified descending neurons supplies bounded speed/turn/posture commands to a frozen locomotor controller. Log that controller's full state. It establishes a testable loop but is not full VNC motor generation.
2. **Mechanistic extension:** descending activity, VNC interneurons, proprioception, and motor-neuron activity drive calibrated muscles/actuators. Introduce this circuit by circuit and compare with the practical baseline.

Low-level coordination must not secretly choose where food or mates are. A neuron-to-behavior dictionary can test a published manipulation, but alone cannot establish natural action selection. Use population readouts, competing outputs, causal ablations, and input/output latency tests. Avoid an executive state machine that decides “court now” while merely animating neural activity.

### Internal state and reproduction

Track energy, protein balance, hydration, gut/crop fullness, arousal, circadian phase, sleep pressure, mating status, egg maturation, stored sperm, and relevant modulatory variables. Choose reduced physiological equations and link each variable to specific sensory/neural parameters only when supported. Keep hunger distinct from thirst, mating experience distinct from sperm storage, and egg availability distinct from fertilization.

Male and female agents need their own connectome, body parameterization, sensory tuning, and reproductive physiology. A female-like mesh with a changed color is not a validated male body. Courtship, copulation, sperm transfer, sperm storage, sex-peptide effects, fertilization, and oviposition are separate events with observable preconditions and state transitions. Genital mechanics can initially be an explicitly abstracted contact process. Do not claim that eggs or offspring emerge from the neural graph alone.

Eggs can initially be persistent objects with parent IDs and resource-dependent survival. Egg → larva → pupa → adult is a separate developmental model. Adult connectomes cannot be interpolated backward through metamorphosis. A genetics module would need explicit inheritance and development rules; recombining adult synaptic matrices has no established biological interpretation.

## Scheduling and two-agent causality

Use one physical world clock and integer multiples/substeps. A candidate starting schedule is neural integration at 0.1 ms, body integration at the body's validated step (often 0.1 ms for these models), sensory/motor exchange at 1 ms, and lower-frequency display. Calibrate field and physiological integration independently. Faster auditory/flight processes may require tighter steps. Run a convergence study; no single timestep is automatically correct.

At a communication boundary: (1) sample both agents from the same world time, (2) advance both nervous systems for the interval, (3) deliver both timestamped motor commands, (4) integrate the shared world, (5) record contacts/ingestion/events. Define whether input is held constant or interpolated between boundaries. Avoid giving the second agent information from a future state caused by the first agent's update. Distinct random streams belong to each animal and each stochastic subsystem.

The 15 ms coupling in the Eon description is a reference configuration, not a biological timestep requirement. Persistent delayed events and muscle state must survive every exchange. Offline simulation can be slower than real time without changing simulated physics or scaling neural time.

## Data and observability

Each run saves: resolved configuration; software commits; body asset hashes/licenses; connectome release/filters; neuron ID map; source registry revision; seeds; timestep/solver settings; hardware; wall-time breakdown; initial states; sampled observations; motor commands; world trajectory; food/resource transactions; event log; and selected neural recordings.

Record all neurons only in bounded experiments. Long runs should use selected spike streams, population summaries, rotating buffers, and event-triggered full traces. Rendering and file writing must have separate timing from simulation. Compute `wall_seconds / simulated_seconds` for the complete loop, not just the neural kernel.

## Proposed module layout

```text
fruitfly/
  data/        # release-aware import, validation, cell-type crosswalks
  neural/      # persistent backends, synapse rules, state checkpoints
  senses/      # geometry to receptor drive, measured calibration tables
  body/        # MuJoCo adapters, unit conversion, muscles/controllers
  world/       # shared arena, fields, food, water, contacts
  physiology/  # reserves, endocrine approximations, reproductive state
  experiments/ # interventions, replay, blinded held-out assays
  recording/   # provenance, trajectories, spikes, analysis exports
```

This is the intended architecture, not a statement that these modules have been implemented. The separately labeled prototype checks a small subset of body/world feasibility.

## Evidence anchors

- [Provided female connectome paper](../drosophila-2024.pdf), especially scope and chemical-synapse limitations.
- [Provided male CNS paper](../drosophila-2026.pdf), especially Fig. 1 and “Limitations of the study.”
- [Shiu et al. model](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446845/) and [source code](https://github.com/philshiu/Drosophila_brain_model).
- [Eon's technical description](https://eon.systems/updates/embodied-brain-emulation).
- [Brian2 state continuity documentation](https://brian2.readthedocs.io/en/stable/user/running.html).
- Additional body and sensory evidence is linked in [body notes](02-body-physics-and-software.md) and [behavior notes](03-behavior-senses-and-reproduction.md).
