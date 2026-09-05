# BANC: comparative circuit evidence for the male model

Checked 2026-09-05 UTC (4 September Pacific time). This was a read-only primary-source and metadata audit. No graph weights, neural dynamics, runtime defaults or body configuration changed, and no neural or physical simulation ran. The inhibitory factorial remains the primary experiment; the embodied P9 benchmark remains cancelled.

**A female connectome exists.** BANC connects an adult female brain and ventral nerve cord, complementing the earlier female FAFB brain and female FANC nerve-cord resources. The BANC paper, *Distributed control circuits across a brain-and-cord connectome*, was published online on 8 June 2026. Its print analyses use materialization v888, dated 17 April 2026; the preprint used v626. The paper describes local sensory–effector loops coordinated by ascending and descending pathways, with putative walking, steering, grooming, feeding and other modules. Its sample is one behaviorally screened female, so it does not establish a typical female's circuit or physiology. Lamina and ocellar structures are missing. These facts correct the original no-female-connectome premise while preserving incompleteness and individual-variation limits. [Primary paper](https://www.nature.com/articles/s41586-026-10735-w), [publication record](https://pubmed.ncbi.nlm.nih.gov/42259917/).

The public Codex landing page labels BANC v888 as female CNS, with 158,262 neurons and 3,037,361 connections. The official repository describes a broader reconstruction with approximately 188,000 neurons and 199 million predicted synapses. These are different populations/products, not interchangeable graph sizes. Our retained MaleCNS graph has 166,700 neurons and 25,582,938 directed stored edges. A cross-dataset comparison must reconcile inclusion, synapse-detection version, edge threshold, autapse policy and proofreading before comparing densities. [Codex dataset listing](https://codex.flywire.ai/?dataset=banc), [official repository](https://github.com/htem/BANC-project), [static Dataverse deposit](https://doi.org/10.7910/DVN/7WTH1N).

## Direct metadata findings

I downloaded only the official metadata snapshot and small documentation files, not connectivity matrices or model code. The source is `htem/BANC-project` commit `e31a2e26b9937dca72e5ca1c1960df6454d76114`, file `data/meta/banc_888_meta_20260521.parquet`, 66,586,415 bytes, SHA-256 `4dde2e6503e59a79e1e8f46e32687de09e8b595e5bd48f7353829fb713c9761a`. Unchanged downloads are retained under ignored `data/raw/banc-comparison/`, with URLs, byte counts and hashes in the [compact evidence receipt](../validation/banc-comparative-circuit-evidence.json). The snapshot has 188,508 rows and 165 columns. Findings below are direct queries of those bytes, with the parent's separate live-UI observation explicitly attributed below. [Pinned metadata](https://github.com/htem/BANC-project/blob/e31a2e26b9937dca72e5ca1c1960df6454d76114/data/meta/banc_888_meta_20260521.parquet).

Exact primary `cell_type` matches give five `lLN2T_b` and four `M_vPNml50` cells, all marked proofread in this snapshot. The former are antennal-lobe local neurons; the latter are multiglomerular antennal-lobe projection neurons. The `M_vPNml50` name should not be interpreted as a visual projection-neuron identity.

| Type | BANC v888 ID | Side | Curated male match in metadata |
|---|---|---|---|
| lLN2T_b | 720575941568333102 | left | absent |
| lLN2T_b | 720575941599261340 | left | absent |
| lLN2T_b | 720575941597223025 | right | absent |
| lLN2T_b | 720575941628446521 | left | 14243 |
| lLN2T_b | 720575941439824402 | right | absent |
| M_vPNml50 | 720575941535774986 | left | absent |
| M_vPNml50 | 720575941459316383 | left | 13951 |
| M_vPNml50 | 720575941415798417 | right | absent |
| M_vPNml50 | 720575941483766458 | right | 13832 |

Neither exact male target **67052 nor 13314** appears anywhere in `malecns_match` or `malecns_nblast_match`. This means this snapshot does not supply an explicit counterpart for either target; it does not show that a counterpart is biologically absent. The currently retained male table contains four `lLN2T_b` and four `M_vPNml50` cells. The five-versus-four count is not, by itself, evidence of sexual dimorphism.

The parent agent independently inspected the live BANC UI on 5 September UTC. A [structured `cell_type == lLN2T_b` search](https://codex.flywire.ai/app/search?dataset=banc&filter_string=cell_type+%3D%3D+lLN2T_b) returned the same five IDs. Free-text search returned six: the extra `720575941643413093` is primarily `lLN2P_c` but retains a historical `lLN2T_b` community label. The parent also observed GABAergic community text on AL.10/AL.13 despite curated acetylcholine. This UI evidence is attributed to the parent's tool transcript; this author did not independently view it, and the receipt does not contain a separate screenshot. It reinforces exact structured cohort selection and preservation of annotation provenance, rather than a biological sign change.

Useful inhibitory source types from the [saved replay](../docs/negative-voltage-replay.md) also exist: exact primary-type counts are `lLN2F_b=4`, `il3LN6=2`, `lLN2P_a=7`, and `lLN2P_b=9`. Alias searches yield different counts: one currently `lLN2T_b` row retains `lLN2F_b` among other labels. Several Patchy cells have automatic male candidates named `auto:lLN2T_a/e`. Therefore, preserve primary type, aliases, match status and morphology separately; a string match must not overwrite our current identities.

The official cross-dataset documentation identifies these male matches as **MaleCNS v0.9**, whereas our retained graph is v1.0. NBLAST scores are candidate morphology evidence, not confidence probabilities or guaranteed cell equivalence. Current v1 IDs/types and anatomical side/nerve/hemilineage need checking before joining. [MaleCNS matching documentation](https://github.com/htem/BANC-project/blob/e31a2e26b9937dca72e5ca1c1960df6454d76114/manuscript/print/dataverse/documentation/banc_malecns_v0.9_nblast.md).

## Inhibitory semantics: the immediate useful constraint

The metadata separates classifier prediction, its score, literature-curated transmitter and the final transmitter annotation. Two concrete disagreements matter:

- `lLN2T_b` BANC `720575941568333102`: predicted GABA, score 0.8827; literature-curated and final labels acetylcholine.
- `il3LN6` BANC `720575941478599454`: predicted acetylcholine, score 0.4893; literature-curated and final labels GABA.

All five listed `lLN2T_b` cells have literature-curated acetylcholine labels, and all four `M_vPNml50` cells have literature-curated GABA labels. These annotations agree at type level with the current male target labels, while exposing classifier disagreement. A literature-curated label is not an electrophysiological measurement from that EM specimen. The target's own transmitter describes its output; it does not determine its incoming receptors, inhibitory reversal or conductance. [Metadata field definitions and provenance](https://github.com/htem/BANC-project/blob/e31a2e26b9937dca72e5ca1c1960df6454d76114/manuscript/print/dataverse/documentation/banc_888_meta.md).

BANC's published all-to-all **influence** product also cannot calibrate our inhibitory kernel. Its documented computation uses `signed=FALSE`, retains edges with at least five synapses, normalizes by target input, rescales the matrix's largest real eigenvalue to 0.99, and solves a steady-state response to unit input. Thus this product answers an anatomical propagation question with an unsigned linear model; its values are neither inhibitory postsynaptic amplitudes nor time constants, spike rates or natural stimulus gains. [Exact influence computation](https://github.com/htem/BANC-project/blob/e31a2e26b9937dca72e5ca1c1960df6454d76114/manuscript/print/dataverse/documentation/influence_all_to_all.md).

**Bounded hypothesis:** after the factorial, compare the two target-type cohorts' source-type input fractions and bilateral motifs under matched edge/filter rules. Agreement would support retaining an anatomical motif across specimens. Disagreement would motivate a typing/proofreading audit before a sex-specific mechanism. Neither outcome selects −75 mV, 5 ms decay, a release probability, or a refractory handling package. Those remain subject to the [physiological promotion gates](../docs/inhibitory-promotion-gates.md) and the existing [inhibitory literature audit](13-antennal-lobe-inhibitory-constraints.md).

## Sight, walking, steering and grooming

The snapshot provides explicit curated male matches for the existing readout/context types:

| Type | BANC left → male | BANC right → male |
|---|---|---|
| DNp09/P9 | 720575941566493282 → 10783 | 720575941433155799 → 11177 |
| DNa01 | 720575941535862506 → 10442 | 720575941432123640 → 10760 |
| DNa02 | 720575941510475536 → 523769 | 720575941456897005 → 10360 |
| DNg97/oDN1 | 720575941519464046 → 13805 | 720575941572713886 → 230783 |

These make a small comparative anatomical panel possible without selecting a new motor mapping. They do not establish the existing decoder's numerical gains. In particular, BANC's `cell_function` field labels both P9 cells `halting`, while primary activation experiments identify DNp09 as a walking command-like neuron and show recruitment of downstream DNa02/DNb02. Treat this as a metadata-to-literature discrepancy to reconcile, not permission to invert P9's simulated effect. [Primary descending-network study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11186778/).

Targeted electrophysiology identifies DNa02 with high-gain steering and DNa01 with low-gain steering; this is a more appropriate source of temporal response constraints than a connectivity cluster label. It does not automatically validate pooling them equally in our decoder. [Primary steering study](https://elifesciences.org/articles/102230). MANC circuit analysis further predicts distinct ipsilateral/contralateral routes through premotor interneurons, including GABAergic IN19A003/IN08A006 downstream of DNa02. This suggests comparing named premotor routes rather than inferring a turn from a DN's anatomical side alone. [Primary MANC circuit analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC13384506/).

For vision, a specific BANC hypothesis is leg proprioceptor → AN09B011 → mALC5 feedback, potentially suppressing ventral visual responses during walking. It is a connectivity-supported hypothesis, not a measured visual response gain. A useful later structural audit would identify the corresponding male route and missing peripheral coverage before introducing a renderer-to-neuron encoder. For grooming, the BANC metadata documentation explicitly warns that antennal-nerve dissection damage underrepresents Johnston's-organ and nearby neurons. Exact `JO-FD1`, `JO-FD2` and `JO-FV` labels are absent from this snapshot, while broader `JO-F` and `JO-FVA` primary types have 184 and seven rows. This is not evidence that female flies lack the male subgroups. [BANC paper](https://www.nature.com/articles/s41586-026-10735-w), [dataset damage notes](https://github.com/htem/BANC-project/blob/e31a2e26b9937dca72e5ca1c1960df6454d76114/manuscript/print/dataverse/documentation/banc_888_meta.md).

Primary head-grooming work provides a separate somatotopic bristle-mechanosensory circuit hypothesis; that population is distinct from Johnston's-organ afferents. It should not silently replace the current JO-F sensory probe. [Primary mechanosensory grooming study](https://doi.org/10.7554/eLife.108044.2). Likewise, primary halting experiments distinguish GABAergic inhibition of walking commands from an excitatory VNC brake. Inhibition of movement and inhibitory neurotransmission are different claims. [Primary context-specific halting study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446846/).

## Reproducibility and remaining boundaries

The broad download is metadata, not a ready-to-run female model. Two observed schema hazards reinforce that distinction: 11,858 rows have `banc_888_id != root_id`, and 278 have `banc_888_id != root_888`, despite general documentation describing those identifiers as synonyms. The inspected Parquet stores proofreading flags as booleans, unlike the documentation's description of string flags in Feather. Keep every versioned identifier and validate actual dtypes; do not silently join connectivity using a newer root identifier. The nine target-type rows above have matching identifiers, but the left DNg97 example already has a different current `root_id`.

The direct checks can be reproduced against the pinned public Parquet with pandas: exact equality on `cell_type` for the listed counts, equality on `malecns_match` and `malecns_nblast_match` for the two target IDs, and direct column comparisons for versioned-root mismatches. IDs must remain strings or 64-bit integers, never floats. No morphology alignment, edge-density comparison, receptor measurement or model fitting was performed here.

The companion *Uncovering Sex Differences in the Drosophila Ventral Nerve Cord Through Connectome Alignment* is useful for cross-specimen type matching and candidate sexual differences, but explicitly retains a need for molecular and functional confirmation. It concerns VNC alignment and cannot resolve the two antennal-lobe targets' physiology by itself. [Primary manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC13307954/), [DOI](https://doi.org/10.64898/2026.06.14.732053).

The public metadata and repository documentation were acquired successfully. Several direct Nature/eLife/PMC web opens returned redirects, 403 responses or browser challenges; the primary indexed article text and public source artifacts supported the limited statements above. No institutional paywall was established and no new figure was digitized. The next active numerical work remains the frozen inhibitory factorial, with no BANC-driven parameter changes or replacement of its recorded source histories.
