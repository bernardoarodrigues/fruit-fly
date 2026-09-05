# APL spatial data and fixed prediction comparison

Completed 2026-09-05 UTC. The previous [APL source review](22-apl-local-feedback-constraints.md) identified spatial constraints but did not reduce the workbooks. This step extracts their numerical observations and compares **all three stimulus sites and all six available author prediction variants together**. It runs no new neural simulation, changes no parameter, and does not resolve the separate γ-KC supplement access gap.

## Data and verification

Primary source: [Amin et al., Localized inhibition in the Drosophila mushroom body](https://elifesciences.org/articles/56954), DOI `10.7554/eLife.56954`. The original Fig. 7 and Fig. 8 workbooks and archival article XML were already available, with hashes verified before and after this analysis. No additional download or workbook save/export occurred.

The [fixed reduction plan](../validation/apl-spatial-reference-plan.json) pins source files, source columns, the three author spread lengths (25, 50, 75 µm), and descriptive metrics before calculation. It is an analysis of already-inspected published results, not a blind holdout, a new fit, or a new simulation.

The [results](../validation/apl-spatial-reference-results.json) verify **7,550 numeric cells** directly against their OOXML encodings and independently recalculate **74 formula caches**. This covers both Fig. 7 sheets and the Hstim, Vstim and Cstim sheets in Fig. 8. The Fig. 8 KC-to-KC inhibition matrix and Voronoi-index sheets are outside this reduction. All required prediction/observation missing-value patterns agree. Source hashes are unchanged. The read library warns about an unsupported extension; this has no write consequence because the source workbooks were never saved.

The [extracted data](../validation/apl-spatial-reference-data.json) retain **5,640 Fig. 7 values** with source sheet, exact cell, literal panel, branch/region and observation slot. Missing entries are not imputed. Slot numbers identify workbook positions, not individual flies or independently identified neurons. Unlabeled negative-control bottom regions retain ordinal positions rather than invented region names. The literal sheet `Fig 7-supp1` remains unchanged despite the source-caption mismatch recorded previously.

Fig. 8 supplies 54 path entries per stimulus: 26 calyx-to-horizontal and 28 calyx-to-vertical entries at 10 µm intervals. The first 19 entries, 0–180 µm, repeat the same shared path. Their observations, dye values and all six predictions are exactly equal. The primary score counts this shared prefix once, yielding **35 distinct segments per stimulus**. A separate 54-entry score preserves the uncorrected path weighting for comparison. These counts are spatial bins, not biological sample sizes. The source profiles are normalized; no amplitude scaling, baseline fit, denoising or re-normalization was applied.

## Fixed spatial-profile results

RMSE on the 35 distinct segments, in the source's normalized reporter/model units:

| Published model | Stimulation | 25 µm | 50 µm | 75 µm |
|---|---|---:|---:|---:|
| Connectome skeleton | Horizontal lobe | 0.2190 | **0.1349** | 0.1605 |
| Connectome skeleton | Vertical lobe | 0.1535 | **0.1317** | 0.1334 |
| Connectome skeleton | Calyx | 0.2224 | 0.1702 | **0.1354** |
| Straight backbone | Horizontal lobe | 0.1951 | **0.1184** | 0.1399 |
| Straight backbone | Vertical lobe | **0.0702** | 0.0990 | 0.1938 |
| Straight backbone | Calyx | 0.2091 | **0.1984** | 0.2303 |

Bold means smallest error among these three exported predictions under this declared metric; it is not parameter promotion. Site-level ordering is unchanged with both path copies included. Equal-site pooled RMSE is 0.2008/0.1466/0.1436 for the connectome model and 0.1700/0.1451/0.1916 for the backbone model at 25/50/75 µm respectively. Thus this particular unweighted normalized-profile score slightly favors 75 µm over 50 µm overall for the connectome export, while the paper's qualitative overall assessment favors approximately 50 µm. This does **not** establish a contradiction or a new biological estimate: the criterion, weighting, normalization, source rounding and finite tested lengths matter. No statistical significance is inferred from correlated bins, and no arbitrary fitting criterion is attributed to the authors.

The [figure](../validation/apl-spatial-reference-figure.png) displays the entire exported profile comparison. Main limitations are visible: none of the simple curves reproduces the calyx-stimulation secondary shoulder well, and representation changes can alter the apparent preferred spread. A single anatomical length cannot by itself specify reporter dynamics or feedback strength.

## Calcium localization and downstream inhibition are different observations

The [descriptive Fig. 7 summary](../validation/apl-spatial-reference-summary.json) calculates means and SEM across retained observation slots for the bottom panels. Illustrative means, in their **separate published normalization scales**, are:

| Stimulation | APL calcium: C / H / V | KC inhibitory effect: C / H / V |
|---|---|---|
| Horizontal lobe | 0.036 / 0.724 / 0.514 | −0.142 / −0.482 / −0.271 |
| Vertical lobe | 0.014 / 0.003 / 0.703 | −0.172 / −0.376 / −0.447 |
| Calyx | 0.686 / 0.015 / 0.003 | +0.223 / −0.328 / −0.288 |

C/H/V mean calyx/horizontal/vertical readout region. The APL panels are A1/B1/C1; the KC inhibitory-effect panels are A4/B4/C4. Slot counts are 10/10/6 for APL and 10/10/9 for KC readouts. The source reports fewer flies than neurons in these cohorts; SEM across slots is not a fly-cluster uncertainty estimate. These are different reporter cohorts and different normalizations. Ratios between the two columns would not estimate release efficacy, conductance or a calcium-to-voltage law.

The observation that downstream KC inhibition can accompany little visible APL calcium does not prove distant local GABA release. The paper specifically discusses inhibition below calcium detectability and how local inhibition of KC input/spiking can suppress calcium elsewhere in KC axons. For calyx ATP stimulation, it also identifies **leaky P2X2 expression** as a confound: control animals show excitation without APL-targeted expression. A positive calyx calcium effect alongside lower axonal calcium is therefore not a direct contradiction in membrane voltage, and must not be fitted by assigning a positive GABA current. The negative-control source values are retained for this reason.

## Consequences for the simulator

This source comparison supports spatially distributed APL feedback with **distinct input, membrane, reporter and output stages**. It does not support making one whole-cell spike counter stand for all local release sites, or setting GABA output to zero where GCaMP is small. Equally, the data do not identify an absolute voltage-to-release law, local capacitance, receptor reversal, or the physical input imposed on each APL segment.

The next useful local model comparison must preserve the source stimulus footprint and observation pipeline, and test localization across stimulus sites before a recurrent full-network trial. It should include the source anatomical and simple-backbone representations as declared references, retain calyx P2X2 leak controls, and score APL calcium and KC response separately. Match the source's regional/time normalization before evaluating either signal. A static spatial attenuation fit alone cannot establish stable recurrent inhibition.

For MaleCNS transfer, original APL neurite path geometry is still required: ROI membership or Euclidean separation cannot silently substitute for distance along its neurites. The existing male contact-location join supplies input/output locations but does not yet identify that path operator or membrane dynamics. These are actionable prerequisites for the graded APL mechanism, independent of the pending γ reporter download. H1 remains unpromoted, Eon body integration remains cancelled, and no global gain sweep is introduced.

Reproduction: run [analyze_apl_spatial_reference.py](../scripts/analyze_apl_spatial_reference.py) with the bundled spreadsheet Python environment after restoring the pinned sources, then [plot_apl_spatial_reference.py](../scripts/plot_apl_spatial_reference.py) with the project environment. Both preserve existing output files. The initial figure's overlapping y-axis labels were corrected and the final six-panel image was visually inspected; initial image and unchanged summary remain under ignored `tmp/apl-spatial-reference/`.
