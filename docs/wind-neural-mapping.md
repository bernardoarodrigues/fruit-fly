# Wind-pathway annotation and physiology audit

The MaleCNS graph contains anatomically identified JO-C/E afferents and candidate
central wind pathways, but the present model is not a validated wind circuit.
This audit records exact source annotations and connections; it applies no
sensory mapping or transmitter override.

## Exact male inventory

Source: pinned MaleCNS v1.0 annotations and retained raw contacts, downloaded
from the [Janelia MaleCNS release](https://www.janelia.org/project-team/flyem/male-cns-connectome).
`scripts/audit_wind_annotations.py` reproduces
`validation/wind-annotation-audit.json`, including per-cell IDs, root side,
subclass, transmitter predictions, synonyms, graph weights and direct contacts.

There are **672 JO cells**, 348 left and 324 right, all entering via `AN`.
Use `rootSide` for these afferents, whose somata are not in the imaged brain.
Use `somaSide` for the central candidates below. Do not infer side from array
position or assign all bilateral populations equal sizes.

| Anatomical selection | Exact types | Left / right |
|---|---|---:|
| JO-C | JO-CA1, JO-CA2, JO-CL, JO-CM | 46 / 22 |
| JO-E | JO-ED1, JO-ED2_a, JO-ED2_b, JO-ED2_c, JO-EV1–6 | 157 / 110 |
| JO-F | JO-FD1, JO-FD2, JO-FV | 42 / 36 |
| Putative APN2 | SAD003, SAD004 | 8 / 8 |
| Putative APN3 | SAD077 | 5 / 4 |
| Putative WPN | LHPV6q1 | 1 / 1 |
| Putative WL-L | LAL138 | 1 / 1 |

JO-C/E cells in these selections have consensus ACh. All selected JO-E cells
carry subclass `wind_gravity`; JO-C has 53 `wind_gravity`, eight `auditory`, and
seven null subclass entries. CA1/CA2 account for mixed functional annotation.
Several A/B types also contain mixed auditory/wind labels, and JO-F contains
both grooming and wind/gravity entries. A broad subclass filter therefore cannot
substitute for an audited sensory population. The 102 `JO-unclear` cells are
strongly asymmetric (7 left, 95 right), so missing subtype assignments must not
be mistaken for established sex or laterality differences in tuning.

Hampel, Eichler et al. explicitly renamed the historical **aJO** population as
**JO-F**. It is not a synonym for wind-sensitive JO-C/E. Their anatomical study
also distinguishes multiple JO subtypes without assigning each a unique
wind-response function. No supported **bJO** alias was found in MaleCNS metadata,
the inspected Shiu/Eon notebooks, or the primary-source search. It remains
unresolved and is not silently equated with JO-B.
[Hampel, Eichler et al., eLife 2020](https://elifesciences.org/articles/59976)

## Central-cell crosswalk is putative

There are no literal APN2/APN3/WPN/aJO/bJO labels in the inspected MaleCNS type,
synonym or cross-dataset name fields. Hulse et al.'s Figure 9 supplies the
**putative morphological crosswalk** used above: APN2→SAD003/SAD004,
APN3→SAD077, WPN→LHPV6q1 and WL-L→LAL138. Matching male type annotations makes
these useful candidates; it does not prove identity with every recorded cell.
[Hulse et al., eLife 2021, Figure 9](https://elifesciences.org/articles/66039/figures)

Suver's driver labeled two WPNs per hemisphere; the male LHPV6q1 annotation has
one. Male LHPV6q1 also has 33 left→right and 62 right→left raw contacts, whereas
the recorded WPN pairs showed no detectable functional contralateral coupling.
Anatomical contacts and functional coupling are different observations, and
sex, preparation or crosswalk uncertainty may matter. These differences prevent
an unqualified one-to-one validation claim.

Selected direct raw contact totals, with no pair-strength threshold:

| Source → target, ipsilateral | Left | Right |
|---|---:|---:|
| JO-C → putative APN2 | 207 | 37 |
| JO-E → putative APN2 | 4,612 | 1,617 |
| JO-C → putative APN3 | 28 | 18 |
| JO-E → putative APN3 | 3,739 | 1,539 |
| Putative APN2 → putative WPN | 22 | 25 |
| Putative APN3 → putative WPN | 0 | 0 |
| Putative APN3 → putative APN2 | 408 | 395 |

These counts establish anatomy, not measured physiological strength. SAD003 and
SAD004 are consensus ACh; SAD077 is glutamatergic, treated as inhibitory by the
declared global model rule; LAL138 is GABAergic. Zero direct APN3→WPN contacts
does not exclude indirect effects.

## WPN output: retained anatomy, missing physiological mechanism

The exact male LHPV6q1 cells are **10347 left** and **11477 right**. They retain
1,554 / 1,467 outgoing neuron pairs and 15,704 / 15,876 contacts respectively.
Every outgoing model weight is zero because `consensus_nt=unclear`. The raw
classifier's serotonin predictions (.662 / .701 confidence) do not supersede
that curated consensus. Their source synonyms explicitly include
`Wu 2024: FMRFa-WED` and `Cachero 2010: pSP-e`.

Wu et al. identify LHPV6q1 as FMRFa-WED using morphology and peptide evidence.
In their protein-feeding circuit, FMRFamide acts on FMRFaR in DA-WED neurons,
through PKC53E and ORK1, to hyperpolarize those hunger neurons. Activity and
feeding effects depend on sex and mating state: male, virgin-female and
mated-female conditions were compared. This supports a peptide/receptor-specific
mechanism, not a universal fast sign for every LHPV6q1 contact. The study does
not calibrate fast WPN output during wind stimulation. Its primary
[electrophysiology data](https://zenodo.org/records/12701489) are available
separately from the Suver wind dataset.
[Wu et al., Cell 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11437785/)

The zero weights unambiguously make output from the **modeled candidate** cells
nonfunctional. They do not by themselves prove the cause of absent wind behavior:
wind input has not yet been calibrated, other routes exist, APN2 physiology is
misrepresented, and the WPN identity correspondence is tentative. No transmitter
or backend rule was changed by this audit.

## Graded APN2 evidence and assay limits

Suver et al. used adult females, generally 2–7 days old, with tethered
electrophysiology and four-second directional wind stimuli. APN2 showed graded
nonspiking responses with little adaptation, whereas APN3 and WPN produced small
spikes; WPN baseline firing averaged 8.4 Hz. Reported average APN2, APN3 and WPN
voltages were −22.0, −26.4 and −22.3 mV **before** an estimated −13 mV liquid
junction correction. WPN's cholinergic blockade experiment tests its required
input transmission, not its own outgoing transmitter. The APN2→WPN activation
effect was transient depolarization followed by hyperpolarization, so it does
not provide a simple static release-to-voltage calibration.
[Suver et al., Neuron 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6533146/)

The April 2026 Nunn et al. **preprint** studies females aged 2–10 days, with
left-hemisphere APN2 recordings during quiescence, flight and antennal movement.
It reports mean APN2 voltage around −34 mV including junction correction and
identifies 14 FAFB female candidates. Those are not exact male body IDs.
The proposed tonic ACh influence is consistent with graded signaling, but
the paper does not measure an APN2 voltage-to-release transfer curve. Its
statement about effects of approximately 2 mV changes cites other arthropod
interneurons and must not be promoted into an APN2-specific calibration.
[Nunn et al., preprint, DOI 10.64898/2026.04.16.718965](https://pmc.ncbi.nlm.nih.gov/articles/PMC13131640/)

## Constrained next implementation proposal

An optional mixed model could designate only explicitly listed putative APN2
cells as graded, retain their incoming conductances and real outgoing contacts,
and remove spike threshold/reset/refractory behavior for that subset. A
nonnegative voltage-dependent release signal needs a tonic baseline so that
hyperpolarization can reduce release. Baseline voltage, release offset, slope,
saturation, time constant and per-contact conversion must remain declared
parameters unless independently measured. Delayed release, membrane state and
all parameters must survive checkpoints.

The appropriate first assay compares candidate APN2 **voltage changes** and
timing against held-out female recordings, with the identity and sex transfer
explicit. It must not overwrite candidate voltage with the target response and
then claim prediction, inject a known wind angle into WPN/DN cells, or enable
unknown WPN transmitter weights to force propagation. Numerical bounds and
graded causality can be tested before biological adequacy. A qualitative model
mechanism is supportable; quantitative APN2 release calibration remains open.
