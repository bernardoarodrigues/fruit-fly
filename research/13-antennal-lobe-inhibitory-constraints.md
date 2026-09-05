# Antennal-lobe inhibition: constraints for a declared comparison

Research date: 2026-09-05 UTC. This is a bounded literature audit and proposed assay set. No parameters were fitted, no neural/body simulation ran, and no runtime files changed.

The [exact negative-voltage replay](../docs/negative-voltage-replay.md) makes two mechanisms worth separating: the postsynaptic response to inhibitory input, and the representation of the inhibitory source itself. Its strongest accepted negative source types are `lLN2F_b`/`il3LN6` into cell 67052 (`lLN2T_b`, acetylcholine annotation), and `lLN2P_a`/`lLN2P_b` into cell 13314 (`M_vPNml50`, GABA annotation). These rankings concern the saved event history. They neither establish a biological cause nor identify the receptors expressed by either target.

The existing [ORN→PN lead](../docs/orn-pn-physiology-lead.md) and [scalar depression reference](../docs/synaptic-depression-reference.md) concern excitatory transmission and a separately declared rat-cortex model. They are not inhibitory calibration data. The primary evidence below supports distinct inhibitory mechanisms, but **does not resolve a numerical inhibitory reversal potential, conductance per contact, or inhibitory release/recovery rule for either exact MaleCNS target**.

## Primary evidence and its limits

### Wilson & Laurent 2005: receptor-dependent inhibition

Adult females, 3–10 days old; somatic whole-cell recordings and post hoc morphology, with GH298 labeling an LN subset. Brief GABA application into antennal-lobe neuropil produced hyperpolarization. At 250 μM, picrotoxin blocked **98 ± 3% in LNs (n=6)** versus **46 ± 5% in PNs (n=14)**. CGP54626 (50 μM) blocked **97 ± 2% of the remaining PN response (n=5)**, while LN response amplitude was **101 ± 6% of control (n=5)**. Errors are SEM. These are pharmacological response fractions, not receptor counts or synaptic weight fractions.

The picrotoxin-sensitive component was faster; the CGP-sensitive component was slower. During odor responses, the paper separately evaluated 0–500 ms and 1.5–2.5 s windows. Its internal solution contained 140 mM potassium aspartate and 1 mM KCl. The text says GABA reversal was near chloride equilibrium and refers to supplementary Figure 1; that figure was not recovered here. **No numerical physiological reversal is extracted.** The −55 to −60 mV holding range is not a reversal measurement. Pharmacology does not identify a specific receptor subunit in either MaleCNS cell. [Paper, methods and Figures 2–3](https://pmc.ncbi.nlm.nih.gov/articles/PMC6725763/), [DOI](https://doi.org/10.1523/JNEUROSCI.2070-05.2005).

### Nagel & Wilson 2016: inhibitory buildup is not ORN depression

Adult females, 1–3 days old. Figure 6C–F activates the diverse **NP3056-Gal4, H134R-ChR2** LN population and records from nonexpressing LNs. Presynaptic firing begins rapidly and declines slightly; mean postsynaptic outward current grows slowly (**n=9**, driver-absent controls **n=6**, presynaptic firing **n=5**). This is population stimulation, not a paired unitary connection. The authors propose facilitating release or delayed access of GABA to receptors; the experiment does not distinguish them.

Figure 5's odor-evoked outward currents increase at −40 versus −60 mV. Voltage-clamp internal replaces 140 mM KOH with CsOH and contains 1 mM KCl; this matters when interpreting slow potassium-dependent mechanisms. No exact LN→LN reversal or inhibitory kinetic fit is supplied here.

Crucially, Figure 6A–B's **f=0.75, recovery τ=1566 ms for LNs**, and **f=0.78, τ=893 ms for PNs**, describe **excitatory ORN input** stimulated at 10 Hz. They cannot be imported as GABA-synapse depression parameters. Historical GH298/NP3056/LCCH3 populations are not exact modern MaleCNS types. [Paper, methods and Figures 5–6](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/nagelwilson2016.pdf), [DOI](https://doi.org/10.1523/JNEUROSCI.3887-15.2016).

### Barth-Maron et al. 2023: source mode and compartment matter

Females, 16–72 hours after eclosion; female hemibrain anatomy. **R78F09-Gal4** targets Full `LN2F_b` cells. **R67B06-Gal4** targets Patchy `LN2P_x`, argued to be **LN2P_c**; it does not establish `LN2P_a/b` physiology. Patchy cells show graded, nonspiking signals and compartmentalized tuft calcium; Full cells distribute activity broadly. Optogenetic activation during DC3 PN recordings changes gain and temporal filtering differently for the two populations, consistent with predominantly presynaptic Full and postsynaptic Patchy pathways.

The authors explicitly report a possible genotype-dependent PN off-target problem with Patchy-driver GtACR1, and therefore did not use that silencing experiment. The author-hosted PDF is an article-in-press version with provisional page numbering. Its reduced fitted model is not an independently measured per-contact conductance. [Paper, Figures 2–6 and STAR Methods](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/showpdf.pdf), [published DOI](https://doi.org/10.1016/j.cub.2023.10.041).

### Salman et al. 2026: closer type labels, incomplete exact mapping

The published study provides targeted current-clamp recordings: **VT043679-Gal4 → lLN2F_b**; **R22E10-AD ∩ VT063106-DBD → il3LN6**; **R32F10-Gal4 → approximately 12 of approximately 20 lLN2Ps**. The first two groups spike; the sampled Patchy group does not. Figure 3 reports **17 cells/animals per group**; the methods/caption specify −100 to 350 pA steps without fixed voltage holding or stated synaptic blockade. A later source-image audit found a different current axis, detailed below. These responses do not isolate GABA transfer.

Imaging combines sexes; patch-recording sex composition and ages are unclear. Connectivity analysis principally uses female FlyWire/hemibrain and cites male/female similarity. This does not establish sex-invariant receptors. R32F10 is not mapped to each `a/b/c` subtype or our source IDs. Somatic recording leaves compartmental release unresolved.

The prose and Figure 3D caption disagree about excitability ranking; no slope comparison is adopted. Its GABA connection-sign diagram includes assumptions; its model omits il3LN6. [Published manuscript, Tables 1–2, Figure 3 and methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC13361993/), [DOI](https://doi.org/10.1152/jn.00571.2025), [declared data repository](https://doi.org/10.17605/OSF.IO/PFBEA).

### Root et al. 2008: GABA_B can act on release

Direct optical measurements of ORN-terminal calcium and vesicle release, together with receptor perturbation, support **presynaptic GABA_B inhibition** and differences across olfactory channels. This is distinct from measuring a postsynaptic inhibitory voltage kernel. The paper itself discusses disagreement with contemporary electrophysiological estimates of presynaptic GABA_A involvement. Sex/age and exact driver details were not recovered in this acquisition, so no quantitative or sex-specific parameter transfer is proposed. No exact VM7d or target-cell claim is made. [Primary results/discussion](https://pmc.ncbi.nlm.nih.gov/articles/PMC2539065/), [DOI](https://doi.org/10.1016/j.neuron.2008.07.003).

## Proposed small assay set

These are proposals for separate review and pre-registration, not a frozen run plan. They are ordered so that a numerical property is established before a physiological match is attempted.

| Assay | Concrete comparison and retained readouts | What it can establish; prerequisite |
|---|---|---|
| 1. Inhibitory driving force | Compare the existing voltage-independent signed state with a nonnegative conductance producing inward current `g_I(t) × (E_I − V)`. In a passive isolated cell, evaluate below, at and above the declared reversal; include zero-input and constant-conductance analytical cases. Keep units explicit: existing `g` is effective mV, not nS. | Sign reversal, zero inhibitory current at `V=E_I`, and shunting can be checked without selecting a biological reversal. For passive leak plus nonnegative conductances and no external current, verify the voltage interval bounded by initial voltage and reversal potentials. Use an exact/reference integration check so timestep overshoot cannot masquerade as physiological failure. |
| 2. Fast and slow response components | Preserve the 2005 brief-GABA protocol and compare one component with a separately declared fast-plus-slow model; report normalized response shape, rise/decay, and component-block conditions. Keep direct GABA-pulse measurements separate from odor-evoked network responses. | A phenomenological two-component hypothesis, not an identified receptor complement for the two target cells. Numerical timing/error tolerances require retrieving source traces or digitizing Figure 2 with explicit uncertainty first. The paper's early/late odor windows are not receptor time constants. |
| 3. LN→LN temporal transfer | Compare static output, depressing output, and delayed-buildup alternatives against jointly retained presynaptic firing and postsynaptic current from 2016 Figure 6C–F. Normalize within the assay; retain the driver-absent control. | Whether each mechanism can reproduce the observed direction of buildup under that population stimulus. First obtain numerical traces and specify measurement windows. It cannot uniquely identify release facilitation versus receptor access/network recruitment. ORN depression constants remain excluded. |
| 4. Source signaling and compartment | Keep a declared spiking source and a separately declared graded source as different model classes. A minimal two-glomerulus graded example should expose local output separately from whole-cell output. Record current-response curves and local versus remote release proxies. | A representation check motivated by the two modern papers. No conversion of saved Patchy spikes to biological graded release is identifiable. Establish the driver-to-exact-type mapping before assigning a graded model to MaleCNS `lLN2P_a/b`. |

A presynaptic GABA_B branch, if later added, must change release from the inhibited terminal, with its own receptor state and compartment declaration. Adding the same slow negative current to a PN soma would test a different hypothesis. Receptor-mediated release suppression and activity-dependent vesicle depletion also need separate state variables; a single depression factor cannot identify both.

Only after those stand-alone definitions are frozen should the retained two-target history be used for a **conditional comparison**. Preserve the original ordered source events, masks, delays, graph IDs and baseline replay. Recompute target availability, resets and accepted deliveries under each changed target rule; do not blindly reuse the old acceptance list after the target state diverges. Report all voltage/current trajectories and changed target spikes, including unfavorable outcomes. This still holds source histories fixed, so it cannot predict recurrent network or behavioral consequences. A later recurrent intervention would be a separate experiment.

No parameter should be chosen to bring the observed −300 to −500 model-mV endpoints into a preferred range. Matching the original transfer at one reference voltage could define an **engineering normalization**, but would not turn connectome counts into measured conductances. Neither a lower voltage clamp nor weakening every GABA edge resolves the mechanism questions above.

## Remaining identity and measurement gaps

- Target 67052 is an acetylcholine-annotated LN; old recordings of broad GABAergic LNs do not establish its incoming receptor complement. Target 13314 is a GABA-annotated multiglomerular PN; a generic/uniglomerular PN sample is not its physiological identification. A neuron's outgoing transmitter does not identify its incoming receptors.
- The recorded source-type ranking is not evidence that every anatomical contact was equally functional, that release occurred at every simulated event, or that a soma represents all synaptic compartments.
- Missing quantities include exact-target chloride regulation/reversal, slow-receptor effector and kinetics, capacitance, input resistance, unitary inhibitory amplitude, anatomical-contact-to-functional-release-site mapping, and inhibitory short-term plasticity. The reviewed sources do not establish these for the exact male cells.
- Approximate imaging or somatic correspondence cannot validate sustained model source rates. In particular, evidence that a related Patchy population is nonspiking argues for reviewing the representation, not for silently deleting its recorded spikes or declaring all `a/b` cells identical to that population.

## Acquisition and reproducibility

[The acquisition receipt](../validation/antennal-lobe-inhibitory-source-acquisition.json) records successes, HTTP errors, challenge responses, byte counts and SHA-256 hashes. Complete public HTML copies of Wilson–Laurent 2005 and the published Salman 2026 author manuscript are retained under ignored `data/raw/antennal-lobe-inhibition/`. Plain-text derivatives use Python's standard `HTMLParser`; they are navigation aids, not corrected editions. Direct PDF requests did not yield a valid PDF. The three Wilson-lab papers were readable as web-indexed PDF text, but two figure screenshot fetches timed out; no plot was digitized and no visual numerical estimate is claimed.

The initial Nagel 2016, Salman 2025 preprint and Root 2008 local HTML responses are access challenges, not paper copies. The preprint was superseded for this audit by the acquired 2026 publication. Raw files remain ignored; the small receipt records precisely what is and is not locally reproducible.

The manuscript's code link is [adacks/Salman-et-al](https://github.com/adacks/Salman-et-al). Its public landing page currently lists one file, `processFluorescenceTiffNew.m`; this is not evidence that the physiological model or raw patch traces are included. The precursor's model/data deposit is [Barth-Maron et al., Zenodo 10028674](https://doi.org/10.5281/zenodo.10028674), as listed in its key-resources table. No repository/model code was run; the Zenodo landing page failed to open here. These are acquisition leads, not independently reproduced models.

No institutional paywall was established, and no institutional login is needed for the conclusions above. The unresolved acquisition at that stage was **Wilson–Laurent 2005 supplementary Figure 1**, available via the [journal article's data/supplement page](https://www.jneurosci.org/content/25/40/9069/tab-figures-data). The journal page did not load here; this was an access failure, not proof that it requires payment. The initial literature acquisition did not download Salman’s OSF data. The separate follow-ups below record both subsequent data inspection and recovery of the supplement.

## Follow-up: public data and a physical-current discrepancy

The completed [OSF inventory](../docs/salman-source-inventory.md) traverses 54 public components and lists 258 file entries, with 42.38 GB in provider-reported sizes including repeated files. Its root storage is empty, but the child components are populated. The metadata inventory downloads no data payloads. All inventoried nodes declare CC BY-NC 4.0. The separate [current-clamp audit](../docs/salman-current-clamp-data.md) acquires only the Figure 3d workbook and Prism project, verifies both against provider hashes, and inspects the exact published Figure 3 image.

The workbook has 7 KS, 10 R32 and 7 ABAF sheets, rather than 17 records per group. All 8,434 saved formula caches agree with independent 50-digit recomputation to within 1e−10 workbook units. That arithmetic consistency does not resolve an unexplained duplicated input row, absent units/current labels, preparation identities, or the difference from the published cohort. The audit preserves the source values and makes no correction or exclusion.

The saved Prism regression report and published figure place Keystone/il3LN6 below the two closer Patchy and Full groups, supporting the prose's direction. They do not establish a pairwise equivalence claim. The published figure explicitly labels **−200 through 700 pA in 100 pA increments**, while the methods/caption specify **−100 through 350 pA in 50 pA increments**. Neither axis is selected as correct. Thus the saved slopes cannot currently supply a calibrated current–voltage relationship or resistance. Original current-protocol records and an exported final Prism data table with specimen identities are needed to reconcile these discrepancies.

This is a source-consistency finding, not new Drosophila physiology. It illustrates why an available numerical workbook and reproducible arithmetic are insufficient for biological parameter identification. These data also remain intrinsic/current-clamp responses, distinct from the inhibitory synaptic transfer needed by the two replay targets. No runtime parameters changed.

## Follow-up: the reversal supplement is now recovered

The earlier Wilson–Laurent supplementary Figure 1 access gap is resolved. An unchanged copy of the author's [three-page supplement](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/wilsonlaurent2005supp.pdf) was downloaded through the normal public browser attachment, with no institutional login. The [source audit](../docs/wilson-gaba-reversal-source.md) retains its hash, rendered figure, exact caption interpretation and the earlier HTTP access failures.

The experiment applies GABA to LN somata in whole-cell recordings. With methanesulfonate plus neurobiotin, the caption distinguishes an expected chloride equilibrium of −52 mV from observed GABA reversal nearer −40 mV. Aspartate shifts the response negative, but several open markers denote an unreached reversal: **the true reversal is more negative than the plotted endpoint**. The stated difficulty holding cells below −75 mV is a recording limitation, not a universal reversal measurement. The source's means and open endpoints therefore cannot be treated as fully observed, uncensored physiological values.

These solution-dependent somatic measurements do not identify the native chloride regulation, receptor complement, synaptic compartment or reversal of either exact MaleCNS replay target. No new numerical reversal, Nernst calculation, digitization or fit was adopted. The access problem is closed; the biological mapping remains open.
