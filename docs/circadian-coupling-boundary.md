# Circadian coupling: evidence and remaining boundary

**Verdict: the available evidence supports specific anatomical hypotheses and
isolated physiological experiments, but does not yet justify a mechanistic
PER/TIM → MaleCNS → sleep controller.** The reproduced
[Leloup–Goldbeter oscillator](circadian-lg1998.md) remains separate from the
neural and physical simulation. Its author-chosen concentrations and phase are
not measured firing rates, peptide concentrations, or sleep pressure. No runtime
coupling was added for this review.

## Exact cells in the loaded male dataset

Exact `type` equality in `data/processed/malecns_v1/neurons.feather` identifies
this **52-cell named subset**, independently checked against the body IDs in
[the existing catalogue](../data/internal-state-learning-mapping.json).
L/R denotes **soma** side, not the hemisphere of every synaptic compartment.

| MaleCNS annotation | Total | L / R | `consensus_nt` |
|---|---:|---:|---|
| `DN1a` | 4 | 2 / 2 | glutamate |
| `DN1pA` | 8 | 4 / 4 | glutamate |
| `DN1pB` | 4 | 2 / 2 | glutamate |
| `l-LNv` | 8 | 4 / 4 | unclear |
| `s-LNv` | 8 | 4 / 4 | acetylcholine |
| `5thsLNv_LNd6` | 4 | 2 / 2 | acetylcholine |
| `LNd_b` | 4 | 2 / 2 | acetylcholine |
| `LNd_c` | 6 | 3 / 3 | acetylcholine |
| `LPN_a` | 4 | 2 / 2 | acetylcholine |
| `LPN_b` | 2 | 1 / 1 | acetylcholine |

All 52 have null `receptorType`. The loaded table contains no peptide-expression
or transcriptomic columns. Its fast-transmitter consensus cannot establish PDF
absence, receptor identity, peptide release, or a universal postsynaptic sign.
The combined `5thsLNv_LNd6` label does not resolve individual subtypes.

No exact DN2/DN3 clock types were found; this is an annotation boundary, not
evidence that those populations are absent. Reinhard et al. reconstructed 242
clock neurons in **female** FlyWire and anatomically found more than 70 DN3 per
hemisphere in both sexes. They combined anatomy with transcriptomics and receptor
mapping to infer putative paracrine connections. The study supports a much larger
candidate network and communication beyond chemical synapse edges; it does not
supply this male specimen's release or receptor kinetics.
[Reinhard et al., 2024](https://doi.org/10.1038/s41467-024-54694-0).

Audit provenance: processed table SHA256
`d35c2428957c7f18ce4290f02606d2f99b851381dd63edc3f760483f6c70b9a8`;
[MaleCNS v1.0 annotation source](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather)
SHA256 `2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2`.
The catalogue retains exact IDs and the neurotransmitter-source hash.

## Experimentally supported outputs

| Primary evidence | Candidate bridge and unresolved quantity |
|---|---|
| PDF is expressed by the four small and four large LNv per hemisphere. Live-brain cAMP imaging shows PDFR-dependent responses across much of the clock network, with marked cell-group differences; most tested wild-type large LNv lacked a clear response. [Shafer et al., 2008](https://doi.org/10.1016/j.neuron.2008.02.018). | `s-LNv`/`l-LNv` are candidate PDF sources. Do not make PDF a uniform excitatory edge or assume all LNv respond equally. Exact male target receptors, concentration-response curves, and kinetics remain unassigned. |
| PDFR signaling in a restricted DH31-expressing DN1 subset promotes DH31 secretion and waking before dawn. These manipulations dissociate sleep output from free-running rhythmicity. [Kunst et al., 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4255360/). | A PDF → PDFR/DH31-DN1 relay is a concrete candidate. The exact crosswalk to male `DN1pA`/`DN1pB`, downstream DH31 receptor-bearing cells, and quantitative response remain unresolved here. Assigning every DN1 the same sleep effect is unsupported. |
| In male brain explants, compartment-specific neuropeptide-release timing differed from predictions based on somatic electrical or calcium rhythms. The assay used **Dilp2-FAP surrogate cargo**, not a calibrated extracellular PDF concentration measurement. [Klose et al., 2021](https://doi.org/10.1073/pnas.2101818118). | Somatic and terminal release require separate treatment. A single molecular-phase-to-peptide multiplier, or one fixed release amount per spike, is not established by these observations. |

These results motivate a sequence of measured transformations: intracellular
clock state → membrane excitability → compartmental secretion → extracellular
peptide exposure → receptor/second-messenger response → target-cell excitability.
Some secretion mechanisms need not pass through somatic spikes. The current
signed synapse graph and ten-state biochemical oscillator do not specify this
sequence. Chemical-edge count is not a calibrated paracrine weight.

## Light entrainment needs two distinct routes

CRYPTOCHROME and JETLAG support light-dependent TIM degradation; experiments
reconstituted this mechanism and showed impaired resetting in `jet` mutants.
[Koh et al., 2006](https://doi.org/10.1126/science.1124951).
Visual input can also entrain the clock through parallel routes, including when
PDF LNv are silenced or removed in a `cry`-deficient background.
[Li et al., 2018](https://doi.org/10.1038/s41467-018-06506-5).

A physical implementation therefore needs a declared light spectrum and dose,
cell-specific CRY/TIM machinery, and a separately audited retinal/eyelet neural
route. The existing rendered RGB samples do not measure photons reaching clock
cells. The historical model's scheduled TIM degradation change (2 to 4 in its
declared units) reproduces its published LD protocol; it is not a fitted
brightness-to-degradation law. Start with measured phase-response curves and
TIM time courses under defined pulses, then test LD entrainment, release into
darkness, and selective photic-pathway perturbations.

## Sleep requires additional evidence

Foundational experiments distinguish sleep-like quiescence using reduced
responsiveness and homeostatic rebound, including regulation independent of
the circadian clock. [Shaw et al., 2000](https://doi.org/10.1126/science.287.5459.1834);
[Hendricks et al., 2000](https://doi.org/10.1016/S0896-6273(00)80877-6).
The existing [sleep research plan](internal-state-learning-plan.md) names
candidate homeostatic circuits; their state must not be replaced by oscillator
phase or the body's energy reserve.

Before coupling, obtain a defensible male subtype crosswalk for peptide/CRY
expression and receptor-bearing targets, then reproduce one source-to-target
physiology experiment with declared units and held-out perturbations. Record
age, sex, genotype, temperature, preparation, and biological phase. Validate
sleep-like behavior with graded arousal probes, reversibility, deprivation and
recovery at matched circadian phases, while checking motor capability and
feeding/grooming confounds. `rest`, neural silence, a fallen body, or a timed
motor-disable command cannot establish sleep.

Any later multiscale integration must share elapsed biological time explicitly
(one hour equals 3,600 simulated seconds). A computational reduction can be
useful, but needs its own declared approximation and validation; display speed
must not silently accelerate only the oscillator or homeostat. For now, the
justified deliverable is the separate reproduced oscillator plus these exact
candidate cells and prospective assays.
