# Reference code and claims audit

Read-only source inspection on 2026-09-04. No whole-brain runner was executed in this audit. Source observations below are narrower than a formal correctness review. Repositories were inspected in temporary directories; stable links pin the revisions.

## Shiu original model

- Repository: [philshiu/Drosophila_brain_model](https://github.com/philshiu/Drosophila_brain_model/tree/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960), commit `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`.
- License: MIT as declared by its root license.
- [model.py](https://github.com/philshiu/Drosophila_brain_model/blob/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/model.py) builds a Brian2 neuron group and sparse synapses from precomputed connectivity tables. Synaptic contact/sign values are multiplied by a global weight parameter.
- Inspected default parameters: resting/reset potential −52 mV; threshold −45 mV; membrane time constant 20 ms; synaptic decay 5 ms; refractory period 2.2 ms; synaptic delay 1.8 ms; per-contact weight scale 0.275 mV. These describe this model configuration, not a measurement of every fly neuron.
- Experimental stimulation is Poisson activation, with special handling of refractory state for directly stimulated neurons. It is not a calibrated olfactory/gustatory receptor model.
- The repository includes both legacy v630 and v783 data filenames. Published replication must explicitly select the matching release and figure conditions.

**Integration decision:** retain this as the known-model reference and reproduce selected experiments before converting its machinery into a persistent sensor-driven service. Do not interpret successful execution as validation of all neural activity.

**Semantic detail to check:** the current README describes silencing connections to and from neurons, while inspected `silence()` zeros outgoing weights (`i` matches the silenced index). A future adapter must define its intervention precisely and test against the published experimental intent. This is a source discrepancy, not a local reproduced failure. Similarly, code labels for synapse models are less authoritative than their actual differential equations and reset behavior.

## Eon fly-brain

- Repository: [eonsystemspbc/fly-brain](https://github.com/eonsystemspbc/fly-brain/tree/a3db62f9436074e485c0278290c2164ed6150808), commit `a3db62f9436074e485c0278290c2164ed6150808`.
- Root license: GPL-2.0-or-later; retained original Shiu materials have their own MIT notice. Plan dependency/distribution strategy with these actual licenses, rather than assuming the fork inherits only MIT.
- [main.py](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/main.py) dispatches neural benchmarks; framework runners include Brian2 CPU, Brian2CUDA, PyTorch, NEST GPU, GeNN, and separately configured Brian2GeNN.
- [README](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/README.md) specifies v783 input, backend comparison tools, spike exports, and setup/simulation timing. Its default command launches a broad multi-backend suite, so it is not an appropriate first smoke command on this Mac.
- Inspected PyTorch runner chooses CUDA when available and otherwise CPU. Apple MPS is not selected. Its 0.1 ms step, Euler-style updates, delay queue, and refractory behavior need parity tests against the reference equations; equal parameter labels do not guarantee identical dynamics.
- The exposed entrypoint is a neural benchmarking application. The inspected code does not provide the complete embodied demo with body, food world, sensory encoders, and reproductive physiology. We must implement or separately obtain the missing integration.

**Integration decision:** useful performance/reference material, but evaluate each backend for persistent short-step input/output, state continuity, statistical parity, and license fit before adopting it. Numerical agreement with Brian2 is implementation agreement, not biological ground truth.

## Eon's demonstration claims

The [March 10 technical account](https://eon.systems/updates/embodied-brain-emulation) describes NeuroMechFly, a Shiu-derived LIF network, and a separate visual model. A few descending/motor readouts drive existing movement controllers, with hand-chosen interface mappings and 15 ms exchange intervals. It says visual inputs did not substantially affect demonstrated behavior, escape was not implemented in the body, and internal state, learning, and hormonal changes were largely absent. The authors do not present a complete downstream motor hierarchy or comprehensive biological validation. Therefore this is a useful integration reference, not evidence that the requested full organism already exists. The supplied X link returned HTTP 403; its video/post was not independently inspected.

## Count and benchmark interpretation

Do not interchange physical synaptic contacts, presynaptic sites, postsynaptic links, or aggregated neuron-pair edges. The Eon README's approximate “5M synapses,” the FlyWire paper's roughly 50M synaptic links, and the final male paper's 25.6M graph edges/124.2M links are not interchangeable quantities. The Eon value was not independently recounted in this audit; inspect imported tables and transformations before assigning its exact meaning.

For replication, retain a separate neuron table including isolated nodes. An adjacency matrix alone can discard biologically identified neurons without connections in that filtered export.

Record full-loop runtime separately from backend kernel time. Repeated trials of one fixed graph, accelerated batches, sparse activity regimes, disabled spike recording, and human-visible real-time interaction are different workloads.

## Additional model approaches

- [Lappalainen et al., 2024](https://www.nature.com/articles/s41586-024-07939-3): connectome-constrained visual-network fitting is a useful example of combining structure with functional/task constraints. It does not turn an unparameterized whole CNS into a validated all-purpose controller.
- [FlyGM preprint](https://arxiv.org/abs/2602.17997): learns locomotion policies using a connectome-shaped directed graph and compares alternative graphs. Treat it as a learned-control research alternative, not evidence that adult neural biophysics or reproduction has been recovered. Full reproduction/code audit was not performed here.
- [Effectome paper](https://www.nature.com/articles/s41586-024-07982-0): structural connectivity can be a prior for estimating causal functional effects. This supports calibrating perturbation responses rather than treating an anatomical edge as a fully known physiological influence.

## Local artifact verification

The two supplied papers remain unchanged. Their titles, DOI metadata, page counts, sizes, and SHA-256 hashes are saved in [provided-papers.json](provided-papers.json). Text was extracted for searching; the female paper's opening page and the male paper's opening/figure pages were rendered for visual inspection. The male paper's figure confirms the distinction between proofread-neuron counts and synaptic completion; extracting text alone can lose that distinction.

Physics execution evidence is in [prototype/output/metrics.json](../prototype/output/metrics.json), separate from these source-only neural observations.
