# KC axonal contacts do not specify a somatic EPSP mechanism

**Conclusion.** The anatomy does not justify interpreting every cholinergic KC→KC contact as an ordinary fast somatic EPSP. Adult experiments establish a functional, mAChR-B-dependent interaction between KC axons that suppresses local calcium, acetylcholine release and dopamine-driven cAMP. They do not measure a unitary KC→KC current, voltage response, spike-transfer curve or per-contact time constant. This supports testing dependence on the *implemented fast positive contribution* while retaining the anatomical contacts; it does not support deleting the biological connections, reversing every edge's sign, or assigning invented GPCR kinetics.

This bounded review covers three primary papers and an official anatomical glossary. The new MaleCNS contact totals belong to the separate [spatial audit](../docs/kc-apl-contact-locations.md); they were not recomputed here. Source bytes, exact protocols, access failures and limitations are pinned in [the receipt](../validation/kc-spatial-mechanism-source-review.json). No figure values were digitized and no model was run.

## Direct adult KC→KC evidence

[Manoim et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9613607/) reanalyzed Hemibrain v1.2.1, finding predominantly axonal, within-subtype KC connectivity. Their receptor reporters labeled αβ and γ strongly, α′β′ weakly. **Tagged receptor overexpression**, rather than endogenous protein localization at each contact, placed mAChR-B in lobes and somata with no calyx label (Figure 1). The physiological effects were clearest in γ axons; expression in αβ alone did not establish the same effect there.

| Experiment | Actual intervention and observable | Main boundary |
|---|---|---|
| Figures 3–4, S3 | mAChR-B knockdown/overexpression; odor-evoked GCaMP6f in γ axons versus calyx; knockdown also increases ACh3.0 responses, except OCT OFF | Local calcium and release modulation; no somatic voltage or spike measurement |
| Figure 5 | MB247-driven cAMPr; 2 s local ACh puff, 1 mM alone or 0.5 mM with 5 mM dopamine; 1 μM TTX; knockdown removes cAMP suppression | Application concentrations, not synaptic cleft concentrations or input spike rates |
| Figure 6 | Activate a sparse αβ/γ subset; measure odor responses in CsChrimson-negative γ regions; suppression disappears with mAChR-B knockdown | Demonstrates lateral modulation; autoreceptor action is still possible |

General age was 7–10 days; optogenetic preparation instead specifies collection at day 3 plus 3–4 days on retinal. Sex was not stated in the retained methods. Imaging was 30 Hz in an exposed, perfused brain in an intact mounted fly. Figure 6 paired a 5 s odor with 625 nm, 33 Hz illumination; **33 Hz is a light pulse frequency**, not a measured KC firing rate. The two reporters' calcium/cAMP kinetics and these sampling rates do not resolve a millisecond synaptic kernel. Driver/cohort/sample details are retained in the receipt.

## What cholinergic transmission and voltage dependence add

[Barnstedt et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4819445/) establishes KC ChAT/VAChT expression and cholinergic excitation of **MBONs**, including nicotinic antagonist and receptor-knockdown evidence. This is not a receptor assignment to KC→KC synapses. In explant brains aged 1–7 days, local ACh at MB lobes did not produce a detectable KC calcium transient (main-text account of Figure S3F). That experiment was acquired at 12 Hz; physiological sex was not specified in the retained main methods. Its negative calcium result cannot exclude small, inhibitory or calcium-independent electrical effects. The supplement request returned an HTML challenge, so its exact negative-assay concentration, pulse duration and n are left unresolved here. The main text confirms the ACh result; the 2022 paper's broader ACh/**nicotine** attribution is not independently verified for KC axons in this review.

[Manoim Wolkovitz et al. 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC12948350/) clarifies why a constant negative voltage increment is also premature. In **Xenopus oocytes**, mAChR-B coupled to coexpressed GIRK gave ACh EC50 values of 516 nM at −80 mV and 1,470 nM at +40 mV (Figure 3; normalized dose-response means ± SEM). These are receptor-reporter currents, not native KC potassium conductance. In adult γ KCs, R71G10-driven G-Flamp1 showed that odor activation weakened the ACh suppression of dopamine-evoked cAMP (Figure 6; n = 5, 30 Hz imaging). This experiment compared odor present/absent; it did **not** clamp or directly record two KC membrane voltages. Adults were generally 7–10 days; mixed sexes were specified for behavior, not for this imaging cohort. The 2 s ACh/DA puff and reporter trace do not identify a per-spike GPCR impulse response.

## Anatomical names and mapping limits

The Janelia-hosted [Hemibrain glossary, physical page 5](https://www.janelia.org/sites/default/files/Project%20Teams/Fly%20EM/1.1%20191004_HemibrainDataset.pdf) explicitly expands `CA` as calyx, `gL` as γ lobe, `aL`/`bL` as α/β lobes, `a'L`/`b'L` as α′/β′ lobes, and `PED` as pedunculus. The page was rendered and visually checked. This older document contains draft placeholders elsewhere: it supports the names, **not identity of Hemibrain and MaleCNS ROI masks**. The retained [MaleCNS download documentation](https://male-cns.janelia.org/download/) establishes the partner table's primary postsynaptic neuropil labeling. A named neuropil is not a measured electrical compartment, claw identity, receptor map, or local-to-soma transfer function. PED should remain explicit rather than silently pooled with a lobe assay.

## A defensible diagnostic and its limits

A controlled comparison may remove only the current model's fast positive KC→KC contribution assigned to a declared set of lobe contacts. The question is whether the model's excessive recruitment or persistence depends on that representation. Specify the literal ROIs and how mixed-ROI neuron pairs are handled; preserve calyx contributions and keep PED separate unless explicitly included. The strongest direct mechanism evidence concerns γ axons. Extending the diagnostic to every lobe is a broader engineering comparison, not an experimentally established pan-KC receptor intervention.

Improvement would demonstrate model dependence on those implemented terms. It would not establish physiological absence of excitation, identify mAChR-B kinetics, prove a unique cause of the network phenotype, or calibrate PN→KC gain, APL, thresholds or learning. Unchanged or worse behavior would also remain informative. Retain the graph contacts and label their receptor/dynamics assignment unresolved.

## Reusable source data

The 2022 article's availability prose says data/code are available on request, **but its supplement links public Data S1**: [raw-data XLSX, reported 22.6 MB](https://pmc.ncbi.nlm.nih.gov/articles/instance/9613607/bin/NIHMS1837499-supplement-1.xlsx), and [Table S1, reported 28.7 KB](https://pmc.ncbi.nlm.nih.gov/articles/instance/9613607/bin/NIHMS1837499-supplement-Table_S1.xlsx). These links were identified, not downloaded or inspected; usable sheet content and time axes remain unverified. No institutional access is needed for the retained full article HTML.

The 2026 article identifies [ScienceDB](https://doi.org/10.57760/sciencedb.34257), [Zenodo](https://doi.org/10.5281/zenodo.18045004) and [author model code](https://github.com/nawrotlab/KC_KC_lateral_interactions). These are preserved leads, not inspected datasets or validated models. The paper's model includes separate dendritic/axonal calcium variables and fitted neuromodulation; it is not a native KC electrophysiological kernel to copy into the current point-cell graph.
