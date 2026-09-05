# Wilson–Laurent 2005: recovered GABA reversal supplement

**Supplementary Figure 1 is recovered and visually inspected.** It supports a strong dependence of somatic GABA reversal on recording solution, with censored measurements in the aspartate conditions. It does not establish one physiological reversal for the MaleCNS neurons in this project. This resolves the source-access gap recorded in [research13](../research/13-antennal-lobe-inhibitory-constraints.md), without changing that earlier audit or selecting a model parameter.

The [author's publication page](https://wilson.hms.harvard.edu/publications/role-gabaergic-inhibition-shaping-odor-evoked-spatiotemporal-patterns) links the [three-page supplement](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/wilsonlaurent2005supp.pdf). Normal Chrome attachment download succeeded without login or CAPTCHA after direct HTTP requests returned access-denied HTML. The original is retained under ignored `data/raw/wilson-gaba-reversal/wilsonlaurent2005supp.pdf`: **176,169 bytes; SHA-256 `867ac68c88000b9b2ba44a46fb692636e84b993b495c5f6c5c34149cd1d26833`**. Its internal creation/modification dates are 2005-10-06 / 2006-02-18; these are file metadata, not a documented correction history. No identity comparison with a journal-hosted supplement was possible. The [acquisition receipt](../validation/wilson-gaba-reversal-acquisition.json) retains successes, errors, methods, derivatives and hashes. No institutional download is currently needed.

## What Figure 1 actually measures

The experiment applies GABA to **LN somata** during whole-cell recording and compares GABA response reversal with each cell's spike threshold. It is not a measurement at an identified LN→LN or LN→PN synapse.

| Internal solution group | Figure n | Supported interpretation |
|---|---:|---|
| Potassium methanesulfonate + 0.5% neurobiotin | 5 | Caption's expected chloride equilibrium is −52 mV; observed GABA reversal is described as nearer −40 mV. These are different quantities. |
| Potassium methanesulfonate without neurobiotin | 16 | GABA reversal remains depolarized despite nominal intracellular chloride being zero. |
| Potassium aspartate | 5 | GABA reversal shifts negative; several open symbols report a limit, not a reached reversal. |
| Potassium aspartate + 0.5% biocytin hydrazide | 5 | Addition does not change the authors' conclusion; this group also includes open limits. |

An open symbol is the most negative stable voltage reached while still above that cell's reversal: **`E_GABA < V_open`**. The caption describes instability below approximately −75 mV; that is an experimental holding limitation, not a universal voltage cutoff or a measured reversal for every cell. No point, mean or error bar was digitized. In particular, the black summary bars must not silently turn censored endpoints into fully observed physiological means. The supplement supplies no numerical table or censoring-aware mean calculation. [Supplement, Figure 1](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/wilsonlaurent2005supp.pdf).

## Protocol and identity boundaries

The [main methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6725763/) describe in vivo recordings from adult females 3–10 days after eclosion, one cell per fly. LNs were distinguished by their large spikes and usually checked by a post hoc fill. The reversal panel gives no modern subtype or per-cell genotype/identity; the paper's GH298 anatomical labeling must not be assumed to identify these recorded cells.

The standard internal contains 140 mM potassium aspartate, 10 mM HEPES, 1 mM KCl, 4 mM MgATP, 0.5 mM Na3GTP and 1 mM EGTA, pH 7.3, 265 mOsm; biocytin hydrazide was usually added. The general iontophoresis protocol uses 250 mM GABA at pH 4.3, 4–7 ms ejection at 1000 nA every 20 s, with 0–5 nA backing current. Figure 1 specifies somatic delivery; this must remain distinct from the paper's neuropil applications. The supplement does not separately restate all pulse settings or supply a full methanesulfonate recipe.

The main recording range of −55 to −60 mV, maintained with 0–30 pA hyperpolarizing current, is not a reversal measurement. Neither the recovered supplement nor the main methods specifies the reversal-search voltage sequence, liquid-junction correction, recording temperature, or per-cell response-versus-voltage data. Figure 1 does not declare selective receptor isolation. Those omissions prevent reconstruction of a precise corrected chloride or receptor-specific reversal from these files alone.

## Constraint for a later declared comparison

Treat this as a **solution- and compartment-dependent response assay with censored bounds**. A later assay could distinguish a response crossing from an unreached reversal and keep spike threshold, holding voltage, expected chloride equilibrium and measured GABA reversal in separate fields. Do not substitute −52, −40 or −75 mV into the full neural simulation as an experimentally identified native reversal.

Supplementary Figure 2 compares PN odor responses across solutions and offers soma-local effects or shunting as explanations for preserved responses. These are the authors' interpretations, not direct compartmental chloride measurements. Thus Figure 1 cannot establish dendritic chloride, a GABA_A/GABA_B receptor complement, or a receptor mapping for `lLN2T_b`, `M_vPNml50`, `lLN2F_b`, `il3LN6` or any Patchy subtype. The old LN/PN categories do not resolve those joins.

The [structured notes](../validation/wilson-gaba-reversal-notes.json) preserve numerical statement types and unknowns. PDF pages 1–2 were rendered with Poppler and visually compared with extracted text. No fit, new Nernst calculation, parameter change, neural run or point digitization was performed.
