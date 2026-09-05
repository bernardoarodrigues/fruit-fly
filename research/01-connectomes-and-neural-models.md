# Connectomes and neural models for a male and female digital fly

Research checked on 2026-09-04 (America/Los_Angeles). This document separates measured anatomy, computational predictions, engineering proposals, and unresolved questions. It uses the supplied final Cell PDF when its numbers conflict with older web descriptions. No biological discovery is claimed.

## The central correction

A female connectome is already available. FlyWire reconstructed an adult female brain in 2024. The female BANC dataset now connects brain and ventral nerve cord (VNC) within one specimen. MaleCNS provides a male brain and VNC within one specimen. These make sex-specific simulation possible without inventing a female by changing activation in a male network. Neither resource is a complete, functional, whole-organism model. [FlyWire paper](https://www.nature.com/articles/s41586-024-07558-y), [BANC paper](https://www.nature.com/articles/s41586-026-10735-w), [MaleCNS final paper](https://doi.org/10.1016/j.cell.2026.08.015).

## Which anatomical resource means what

| Resource | Sex and specimen scope | Status relevant to this project | Proposed use |
| --- | --- | --- | --- |
| FlyWire/FAFB v783 | One adult female; brain, including optic lobes; no VNC | 139,255 reconstructed neurons; 54.5 million retained chemical synaptic links in the 2024 paper | Replicate published brain simulations; reference female vision and cell types |
| MaleCNS v1.0 | One adult male; brain, VNC and neck connective | Published Cell September 3, 2026; 166,700 neurons | Main male structural scaffold |
| BANC v888 | A different adult female; connected brain and VNC | Published Nature June 8, 2026; limitations below | Main female structural scaffold and female abdominal circuits |
| MANC v1.2.1 | Another male; VNC only | Densely reconstructed; about 23,000 neurons; no brain | Motor-circuit reference and independent validation |
| FANC | Another female; VNC only | Partial/sparse reconstruction and targeted proofreading | Independent female premotor and ascending/descending circuit evidence |
| Hemibrain v1.2.1 | Another adult female; partial central brain | Older, smaller brain reconstruction | Third specimen for selected cell-type comparisons |

The male optic-lobe release and MaleCNS extend the **same specimen**, so they are not independent animal replicates. FlyWire brain plus FANC cord would be a cross-animal composite, not a measured intact female CNS. [MaleCNS supplied PDF, Results], [MANC project](https://www.janelia.org/project-team/flyem/manc-connectome), [FANC code and description](https://github.com/htem/FANC_auto_recon), [2025 neck-connective comparison](https://www.nature.com/articles/s41586-025-08925-z).

## MaleCNS: final paper facts and limitations

The supplied `drosophila-2026.pdf` is the final Cell article, DOI **10.1016/j.cell.2026.08.015**, pages 5504–5526 and supplementary methods. Its extracted text is in `tmp/pdfs/drosophila-2026.txt`. Prefer these final-paper numbers over the preprint and web abstracts:

| Quantity | Final Cell value | Meaning |
| --- | ---: | --- |
| Identified, proofread and annotated neurons | 166,700 | Includes sensory axons |
| Neurons with retained synapses | 166,483 | 217 identified neurons have no retained synapses |
| Cell types | 11,710 | Final paper's classification |
| Retained synaptic connections | 124.2 million | Links with both ends on proofread neurons |
| Directed neuron-pair edges | 25.6 million | Multiple synapses can contribute to one edge |
| Presynaptic completion | 94% | Detected presynapses assigned to proofread neurons |
| Postsynaptic completion | 42% | Detected postsynapses assigned to proofread neurons |
| Both-ended completion | 40.1% | Fraction of detected synaptic connections whose two neurons are traced |
| Cross-dataset cell-type matches | 97.9% of neurons | A match to FlyWire, hemibrain and/or MANC |

The initial detector found 46 million presynaptic sites and 312 million postsynaptic sites. These are not interchangeable with 124.2 million retained synaptic links or 25.6 million neuron-pair edges. Polyadic synapses and incomplete attachment explain why multiple counting conventions coexist. Detection precision/recall is reported as 0.82/0.81; proofreading a neuron does not establish that every synapse on it is correct or attached. [Final paper, PDF pp. 3–5, 26–29](https://doi.org/10.1016/j.cell.2026.08.015).

The final sex-comparison inventory is **8,069 isomorphic, 138 dimorphic, 289 male-specific and 71 female-specific cell types**. This is principally a male-CNS versus female-FlyWire **brain** comparison. The authors explicitly say that female VNC comparisons require further proofreading, joint typing and quantification of variation. Some annotations are qualified as *potentially* dimorphic or sex-specific; those confidence qualifiers must survive ingestion. [Final paper, PDF pp. 2, 5–6, 18, 30–31](https://doi.org/10.1016/j.cell.2026.08.015).

Sex-related differences include cell presence, branching and connectivity, with additional sex-dependent physiology beyond the wiring. Morphologically similar neurons can acquire different partners. Consequently, a shared network with only a sex-dependent bias is not an evidence-based substitute for the two measured networks. A common cell-type ontology and shared software are appropriate; shared anatomical parameters must remain hypotheses. The paper warns that n=2 brains prevents formal analysis of some cell-number differences, and that missing homologues can reflect divergence or annotation uncertainty. [Final paper, PDF pp. 5–6, 18, 30–31](https://doi.org/10.1016/j.cell.2026.08.015).

Sensory reconstruction needs individual audits. MaleCNS reports 2,635 olfactory receptor neurons in 53 types and 91 thermo/hygrosensory neurons in 8 types; approximately 70% of those receptor neurons were completely reconstructed, and some bilateral axons remain disconnected fragments. Root-side and soma-side annotations have different meanings. Blindly counting bodies as neurons or merging fragmented afferents by name can create false lateral asymmetries. [Final paper, PDF pp. 36–37](https://doi.org/10.1016/j.cell.2026.08.015).

## BANC: what is present, and what “whole CNS” leaves out

The final paper reports **155,916 proofread or roughly proofread neurons**, and separately 171,512 identified objects including fragments, glia and trachea. Detected-link attachment is 74% presynaptic, 23% postsynaptic and 18% at both ends. BANC lacks lamina and ocellar structures, with roughly 9,390 associated cells absent and several visual neurons truncated. Antennal damage compromises some Johnston's-organ reconstructions. Its full female abdominal neuromere is particularly relevant to reproduction. The selected specimen showed marked turning handedness, so it is not a population-average fly. These are structural data with predicted synapses and transmitters. [BANC final paper, Fig. 1 and Methods](https://www.nature.com/articles/s41586-026-10735-w).

Final analyses use materialization **v888, April 17, 2026** and synapse model v2; the preprint used v626. Materialization, annotation snapshot and synapse-detector version are separate axes. The paper also makes v3 synapses available. The final repository is [Harvard Dataverse 7WTH1N](https://doi.org/10.7910/DVN/7WTH1N); the earlier 8TFGGB deposit is superseded. [BANC data availability](https://www.nature.com/articles/s41586-026-10735-w).

The current [BANC GitHub README](https://github.com/htem/BANC-project) advertises approximately 188,000 neurons/199 million predicted synapses. That headline is **not** the final paper's 155,916 proofread/roughly-proofread inventory. Do not silently substitute it. Investigate the inclusion criteria and version before reporting an updated count. The repository says its code and Dataverse data are CC BY 4.0, while bundled code archives may have separate licenses.

## Cross-source discrepancies worth retaining

These are reproducibility findings, not new biological findings:

1. **MaleCNS counts have drifted.** Google's publication abstract still describes 166,691 neurons, 11,691 types and earlier dimorphism counts; the local final article gives the values above. Record exact source versions. [Google abstract](https://research.google/pubs/sexual-dimorphism-in-the-complete-connectome-of-the-drosophila-male-central-nervous-system/).
2. **Lamina contradiction.** The BANC article says MaleCNS also lacks lamina. The later final MaleCNS paper explicitly describes lamina-specific synapse-detector training and some unreconstructed R1–R6 cells at volume boundaries. Therefore, do not generalize BANC's missing-lamina statement to current MaleCNS. Use MaleCNS's own final anatomy and inspect its regions. Ocellar coverage remains a targeted verification item, rather than inferred from the contradictory sentence. [MaleCNS final Methods, PDF pp. 26–29](https://doi.org/10.1016/j.cell.2026.08.015).
3. **A versioned folder can contain mutable objects.** The BANC `banc_888_meta.feather` object had an August 21, 2026 modification date when checked, after materialization and publication dates. Pin checksum and object generation or archived deposit, not just `888`.
4. **Catalogues may lag.** Codex FAQ advertised MCNS v0.9 while the official MaleCNS download page offered v1.0. BANC's Codex release date also differs from its CAVE materialization date. [Codex FAQ](https://codex.flywire.ai/faq), [MaleCNS downloads](https://male-cns.janelia.org/download/).
5. **Small documentation defects matter.** BANC's data-location index lists a neurotransmitter filename without `_v2`, returning HTTP 404. Public bucket inventory identified the valid `_v2.csv` file. [Authors' data index](https://github.com/htem/BANC-project/blob/main/manuscript/print/banc_data_locations.md).

## What to download first

Bulk tables are sufficient for initial point-neuron simulation. Full electron-microscopy volumes, meshes and skeletons are unnecessary until a morphology or boundary problem requires them.

**MaleCNS v1.0:** the official page supplies separate neuron annotations, neurotransmitter probabilities and segment-pair weights in Feather format, plus per-synapse geometry and skeletons. The full weight table includes fragments and non-neuronal segments, so filter endpoints against the selected neuron inventory before simulation. NeuPrint API access requires a free account/token; the bulk GCS files below responded without login. Dataset license: CC BY 4.0. [Download documentation](https://male-cns.janelia.org/download/).

| Direct file (read-only HTTP check) | Bytes observed | Check result |
| --- | ---: | --- |
| [Male neuron annotations](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather) | 14,483,314 | HTTP 200 |
| [Male segment-pair weights](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather) | 1,051,241,946 | HTTP 200 |
| [BANC v888 metadata](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/banc_888_meta.feather) | 57,503,026 | HTTP 200 |
| [BANC v2 neuron-pair edges](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/banc_888_edgelist_simple_v2.feather) | 305,250,378 | HTTP 200 |
| [BANC v3 neuron-pair edges](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/banc_888_edgelist_simple_v3.feather) | 359,161,658 | HTTP 200 |
| [BANC neurotransmitter predictions, corrected filename](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/banc_888_neurotransmitter_prediction_v2.csv) | 21,107,592 | Listed by public GCS object API |

These checks prove public file availability, not successful import or simulation. Hashes/ETags and last-modified dates from these checks are recorded in `sources-connectomes.json`. GCS ETags are not a substitute for locally computed SHA-256.

The [BANC data-location index](https://github.com/htem/BANC-project/blob/main/manuscript/print/banc_data_locations.md) distinguishes v2 edges using postsynaptic detection-size threshold ≥5 from v3 edges using ≥10. These are not “at least 5 or 10 synapses per neuron pair.” Treat each preprocessing rule as a named field.

**FlyWire:** [Zenodo 10676866](https://zenodo.org/records/10676866) supplies v783 proofread neuron IDs (about 1.1 MB), per-pair/per-neuropil connections (about 852 MB), and a larger all-synapse table (about 9.5 GB). The latter contains orphan endpoints. Sum across neuropils only when deliberately collapsing region-specific connectivity. Cleft score 50 is a detector filter, distinct from an edge-weight threshold. The Zenodo API reports CC BY 4.0.

For contemporary crosswalks, use tagged [flywire_annotations](https://github.com/flyconnectome/flywire_annotations) releases. Tag 2.1.0 corresponds to the 2024 papers; 3.1.0 includes updates associated with the peer-reviewed MaleCNS work. The same v783 segmentation can therefore have different annotation releases. The authors warn that Codex's mixed annotations may diverge from their systematic repository annotations. Retain the repository commit and annotation release with every simulation.

FANC code is GPL-3.0 in [FANC_auto_recon](https://github.com/htem/FANC_auto_recon). That code license is not by itself a dataset license. Verify each FANC data product's terms before redistribution. MANC data are CC BY according to its [official project page](https://www.janelia.org/project-team/flyem/manc-connectome).

## What the existing whole-brain model establishes

Shiu et al. (2024) implemented a Brian2 leaky integrate-and-fire model constrained by connectivity and predicted transmitter identity, and validated selected feeding/grooming predictions experimentally. Its baseline is zero firing; weights scale with synaptic counts. It omits non-spiking neurons, gap junctions, internal state, long-range peptides and realistic receptor diversity. The paper treats GABA/glutamate as inhibitory and several monoamines as excitatory simplifications. Thus it supports circuit-hypothesis testing, not claims that every fly behavior is already reproduced. Reported accuracy is 91% across 164 tested predictions, or 84% after excluding the large optogenetic set dominated by negative responses; neither number is a whole-animal benchmark. [Shiu et al., Nature](https://www.nature.com/articles/s41586-024-07763-9), [public code](https://github.com/philshiu/Drosophila_brain_model).

**Engineering inference:** implement this as a frozen replication backend before adapting it to new datasets. Importing MaleCNS or BANC weights is a new model configuration requiring recalibration: detector thresholds, synapse capture, afferent completeness and neurotransmitter predictors differ. A global gain copied from FlyWire cannot be assumed portable. Receptor identity, neuromuscular effects and cotransmission must be handled separately; a universal “glutamate is inhibitory” switch is unsuitable as a biological axiom.

## Proposed neural architecture

This is a proposed engineering design, not an experimentally validated full-fly model.

1. **One immutable anatomy manifest per specimen.** Record dataset/materialization, annotation commit, synapse version, downloads, checksums, selected neuron IDs, filtering rules, coordinate units and crosswalk provenance.
2. **A sparse graph, with per-neuron state.** Start with a point-neuron backend reproducing Shiu. Support per-cell-class electrical parameters later. Use separate channels for fast excitation, inhibition and slow modulatory effects. Keep anatomical counts distinct from fitted functional weights.
3. **Explicit sensory boundaries.** Convert world stimulus into receptor-level activity at documented afferents. Every injected input should carry modality, cell type, side, calibration and measured-versus-modelled status. Where anatomy is missing, use a declared surrogate sensor module; do not silently wire a missing retinal circuit.
4. **Explicit motor boundaries.** Descending neurons project to VNC circuitry; they are not muscle actuators. Maintain separate options for a calibrated motor policy, a reduced VNC model and an anatomically constrained VNC. Record which option controlled each behavior.
5. **Bidirectional coupling.** Body contact, joint state and inertial cues return through afferent models. Brain output alone cannot establish closed-loop plausibility.
6. **Slow physiology.** Energy, hydration, sleep/circadian drive, reproductive state and hormones need state variables with causal input to the neural model and causal consequences of feeding/mating. Those variables are model assumptions until validated.
7. **Controlled perturbations and ensembles.** Lesions, input changes, transmitter alternatives, uncertain edges and parameter sweeps should be first-class experiments. Preserve uncertainty rather than collapsing all unknown neurons into excitation.

A common cell-type vocabulary can map both sexes without forcing one-to-one neuron correspondence. Represent mappings as relations with confidence and provenance, including one-to-many and unresolved mappings. Use `mancType`, `flywireType` and `hemibrainType` crosswalks provided by MaleCNS; root IDs remain dataset-specific. [Final Cell PDF pp. 4–5](https://doi.org/10.1016/j.cell.2026.08.015).

## Compute implications for the current 24 GiB machine

The following are derived storage estimates, **not runtime benchmarks**. A dense float32 matrix for 166,700 neurons needs about 111.2 GB (103.5 GiB). A sparse 25.6-million-edge representation with one int32 target and float32 weight per edge needs about 204.8 MB before row pointers, delays, state, indexes and library overhead. Storing every anatomical synapse separately is far more expensive than aggregating equivalent neuron-pair connections.

Therefore use sparse, memory-conscious preprocessing and benchmark a single fly before two flies, visual rendering and learning. Avoid dense all-to-all tensors, all-neuron voltage traces at every submillisecond step, and loading multiple full synapse tables together. Decimate observability independently from numerical integration. Capacity to store a graph does not imply the CPU can simulate it in real time.

## Candidate insights and falsifiable experiments

These are research hypotheses derived from the evidence, not established discoveries or verified novel ideas.

| Hypothesis | Experiment | What would disconfirm it |
| --- | --- | --- |
| Closed-loop sensory feedback improves transfer from recorded locomotion to altered surfaces | Compare matched motor controllers with feedback intact versus removed, using held-out friction and obstacle conditions | No reproducible improvement after matching controller capacity and tuning |
| A small number of dimorphic circuits can strongly alter social action selection without rewriting shared locomotion | Exchange mapped candidate cell-type subcircuits between the two anatomical scaffolds while preserving all other parameters | Effects disappear under uncertainty/parameter ensembles or can be explained solely by body differences |
| Dataset-specific missing inputs can dominate apparent sex differences | Compare matched tasks with complete and deliberately masked afferent sets | Sex differences persist unchanged after coverage and sensory-drive matching |
| Updating synapse detection can change circuit conclusions more than adding neuronal complexity | Run identical behavioral predictions on BANC v2 versus v3; compare to parameter/biophysical-model changes | Predictions remain stable across detector versions but change systematically with neuron dynamics |
| Published brain-to-cord modules may reduce the dimension of calibration | Fit small module-level gains versus unrestricted neuron-level parameters under held-out perturbations | Lower-dimensional calibration loses predictive validity despite equal data and evaluation |

Novelty would require a dedicated literature search and actual experimental/simulation results. A successful rendered scene or a courtship state machine is not evidence that a neural connectome generated the behavior.

## Access blockers and remaining evidence

- Supplied Cell and FlyWire PDFs cover their core papers; institutional login is not needed for those supplied files.
- BioRxiv v2 and Cell HTML returned HTTP 403 through the research browser. That is an access-tool failure, not proof of a subscription requirement. The final Cell paper is marked open access in the supplied PDF.
- Nature BANC HTML was readable via ordinary Python HTTPS despite a browser-tool redirect failure. Its public paper and data should not require an institutional login.
- Dataverse page/API were blocked from this environment; public GCS download URLs worked. Preserve the DOI and use an archive when available for frozen provenance.
- Before implementing female vision or acoustic courtship, audit the exact missing/truncated afferents. Before making sex-comparison claims, quantify sample and reconstruction differences. Before claiming reproduction, distinguish neural choice, successful mechanical mating and biochemical/developmental simulation.

Core bibliography and check outcomes are in `sources-connectomes.json`.
