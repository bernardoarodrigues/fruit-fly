# Derived hypotheses and unresolved questions

These are proposed tests derived from the reviewed evidence, not discoveries. Novelty has not been established by an exhaustive literature search. A positive simulation result prioritizes an experiment; it does not prove a biological mechanism.

| ID | Proposed hypothesis | Derivation | Discriminating test | Main alternative explanation |
|---|---|---|---|---|
| H1 | Behavioral differences between two imported CNS models may initially reflect missing-input and completeness differences more than sex-specific circuitry | MaleCNS and BANC differ in proofread coverage and missing sensory regions; the Cell paper warns about cross-dataset interpretation | Compare within-sex reconstruction perturbations, completeness-matched graphs, common-input subcircuits, and swapped sex-specific modules | Real sexual dimorphism, unknown parameter differences, specimen variability |
| H2 | A calibrated sensor/motor boundary can improve held-out behavior more than increasing neuron-model detail everywhere | Connectomes constrain topology, while stimulus-to-neuron and neuron-to-force mappings remain poorly measured | Equal-compute/equal-fitting-budget comparison of uniform model refinement versus boundary calibration; hold out perturbations | Boundary fitting may merely compensate errors deeper in the network |
| H3 | A broader descending population improves robustness to obstacles and sensory conflict over a few command readouts | Descending control is distributed and population-based; sparse interfaces omit many outputs | Hold body/controller constant; compare sparse and broader biologically identified readouts; test lesions and unseen terrain | More fitted parameters or a better low-level controller, rather than biological organization |
| H4 | Odor-navigation performance depends on central memory and encounter history in ways a static gradient follower cannot reproduce | Bilateral motion cues and newer plume-edge directional-memory assays emphasize different information | Static gradient, moving/intermittent plume, unilateral cue, central-complex perturbation, and odor-free return trials | The chosen sensory encoding may favor one navigation strategy; tethered assay may not generalize |
| H5 | Reproductive state should alter the same sensory circuit's gain or routing, producing context-dependent decisions without an external behavior selector | Courtship/receptivity and post-mating state involve modulatory pathways, not just geometry | Freeze environment and sensory stimuli; manipulate modeled reproductive modulation and corresponding neural pathways | A procedural state variable may prescribe the outcome instead of explaining it |
| H6 | Apparent behavioral rhythms can be artifacts of brain–body exchange intervals | The reference Eon loop uses 15 ms exchanges, while neural/body integration can be much finer | Sweep coupling intervals with matched neural/body integrators; inspect gait, turn, and neural spectra | True circuit or controller oscillations, aliasing only in recording |
| H7 | Closed-loop control can expose import errors invisible to open-loop firing-rate comparison | A sign error or identity mismatch can still yield aggregate spiking but destabilize sensorimotor feedback | Verify known sensory–DN pathways, then compare open-loop neural parity with closed-loop trajectory/perturbation fidelity | Body mismatch or poor actuator calibration rather than graph import |

Evidence: [connectome notes](01-connectomes-and-neural-models.md), [body notes](02-body-physics-and-software.md), [behavior and recent navigation papers](03-behavior-senses-and-reproduction.md), [Eon account](https://eon.systems/updates/embodied-brain-emulation), and the [provided Cell paper](../drosophila-2026.pdf).

## Questions that must remain explicit

1. Which untraced fragments and absent peripheral neurons matter for each selected assay? Can their uncertainty be marginalized rather than hidden in fitted gains?
2. Which transmitter predictions imply excitatory/inhibitory/slow modulation in each receptor context? Where are co-transmission and electrical synapses essential?
3. Which neural parameters can be identified from published recordings, and which remain non-identifiable even when behavior fits?
4. How should sensory physiology from one sex, age, strain, or preparation transfer to the two connectome specimens?
5. What does replacing the VNC with a trained controller remove from the explanation of proprioception, gait, and social motor sequences?
6. Which body parameters distinguish males and females beyond overall scale, and what data constrain genital/ovipositor mechanics?
7. Can the fly learn a genuinely held-out odor association through a documented plasticity mechanism, rather than an external reward-to-action update?
8. What reduced physiological model is sufficient for meaningful feeding, satiety, mating, and egg laying over the intended experiment duration?
9. How much biological variation can be inferred with so few reconstructed individuals? How should reconstruction uncertainty be separated from individual variation?
10. Are project claims about “emulation” tied to defined experiments, or simply to the presence of a connectome matrix?

## Knowledge ledger convention

Future notes should use one of: **observed in source**, **reproduced locally**, **engineering assumption**, **inference**, **hypothesis**, **unresolved**, or **contradicted/superseded**. Record source version, assay, confidence, alternative explanations, and the experiment that would change the conclusion. Preserve superseded results with a reason rather than quietly rewriting history.
