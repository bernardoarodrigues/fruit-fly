# Figure 6 inhibitory transfer: one bounded extraction

**The displayed mean outward current rises while the displayed presynaptic population rate falls over the fixed early-to-late windows. Both directions remain resolved after the declared graphical uncertainty.** This supplies a quantitative comparison of the published figure, not a physiological model match, causal transfer kernel or statistical significance test.

The single extraction used Nagel and Wilson (2016), Figure 6 on PDF page 9, printed page 4333. The [separate amendment](../validation/ln-inhibitory-transfer-phase2-plan.json) was frozen before neural path access, SHA-256 `8da8c3f16dbf1cdb2ddf247bb91917e547d0a47694eb15dfa0d4dae634e734d9`. It pins the PDF, previous plan/layout, [design review](ln-inhibitory-transfer-phase2-review.md) and complete extractor. The original PDF SHA-256 remains `3991919a050c83687014e9204f76cc1f48e6dd91949204156a81ab16f294ecfe`. There was no second extraction, segmentation tuning, model fit or simulation.

## Quantities obtained

Times refer to the illustrated light command: baseline `[−0.15,−0.05) s`, early `[0.05,0.15) s`, and late `[0.25,0.35) s`. These are our previously fixed analysis windows, not author-reported averaging windows.

| Published representation | Quantity | Graphical enclosing interval |
|---|---|---:|
| F current mean | Early minus baseline | +2.876 to +3.740 pA |
| F current mean | Late minus baseline | +4.745 to +5.637 pA |
| **F current mean** | **Late minus early** | **+1.489 to +2.292 pA** |
| E rate mean | Plotted early rate | 40.011 to 42.971 spikes/s |
| E rate mean | Plotted late rate | 27.043 to 31.753 spikes/s |
| **E rate mean** | **Late minus early** | **−15.657 to −8.608 spikes/s** |
| D current mean, same cohort | Late minus early, graphical check | +1.172 to +3.271 pA |

Table bounds are rounded outward to three decimals; the [compact CSV](../validation/ln-inhibitory-transfer-phase2-summary.csv) and [numerical receipt](../validation/ln-inhibitory-transfer-phase2-results.json) retain full precision and all changes. D/F intervals overlap for early-minus-baseline, late-minus-baseline and late-minus-early. They were not averaged or counted as separate observations.

F is a wider rendering of D's **same nine-cell postsynaptic current dataset**. E is the mean from **five separately recorded presynaptic cells**, not paired recordings from those nine targets. The seven green vector pieces join into one displayed mean. The source caption states mean ± SEM, but a separate E SEM could not be identified; none was fabricated. The D genetic-control mean was not separated from overlapping raster/vector artwork. Control and gray-envelope geometry remain retained without assigning unsupported mean/uncertainty values.

## What the intervals mean

Each interval encloses the window average of the **attributable mean-line ink**, including the declared uncertainty in graphical anchors and curve representation. They are not SEM, confidence intervals, across-cell variability, or guaranteed bounds on the original recording error.

The extractor retained complete transformed paths and the decoded page content. Cubic paths were subdivided using a maximum 0.001 PDF-point control-to-chord distance, with that allowance added to the enclosing strips. Each 1 ms integration bin covers the entire attributable ink extent across all admitted time-anchor/scale positions. These bins are numerical partitions of the artwork, not recovered acquisition samples. No midpoint centerline, missing-segment interpolation, smoothing or curve fit was introduced.

F's own 200 ms/4 pA bars and D's 1 s/4 pA bars were calibrated independently. Bar endpoints were allowed to vary by half their perpendicular ink thickness. Time-zero ranges use the retained light-command ink edges. E's 20/60 spikes/s tick rectangles define its rate scale; the intermediate 40 tick and endpoint axis extents pass consistency checks. These rules describe graphical sensitivity rather than an experimentally measured timing error.

The method first averages vertical-coordinate enclosures. If the early/late vertical ranges are `[L_e,U_e]` and `[L_l,U_l]`, increasing signal points upward, so the difference uses `[L_e−U_l,U_e−L_l]` divided by the shared positive scale interval. The common vertical origin cancels before this conversion. Baseline cancels from late-minus-early and is not counted twice. This also avoids creating an arbitrary holding-current uncertainty from the page's vertical position.

All **900 required bins** have attributable support: 100 bins in each of three windows for each of F, E and D. Unsupported bins occur only at the full-display boundaries: 2 in F, 9 in E and 59 in D. They remain missing and are outside every required window. Complete source artwork and all bin enclosures remain under ignored `data/raw/ln-inhibitory-transfer/phase2/`.

## Verification and retained presentation failure

The [validation receipt](../validation/ln-inhibitory-transfer-phase2-validation.json) records **53 passing checks**, including hashes, window coverage, an independently recomputed duration-weighted sum, shared-origin difference arithmetic and visual attribution. Synthetic rectangle, cubic-enclosure and signed-interval checks were also performed before source extraction.

A separate [independent review](ln-inhibitory-transfer-phase2-independent-review.md) passes 97 bounded read-only checks of source hashes, calibration, all nine windows, differences and all 12 CSV rows, and confirms the corrected overlay attribution. It does not repeat extraction. Its review preserves the non-sharp graphical uncertainty and the baseline rate interval that straddles zero; that interval must not be clipped or turned into an exact-zero datum for a fit.

The first verification overlay incorrectly placed the source raster on a page beginning at zero. The PDF MediaBox/CropBox is `[9,9,594,792]`; the corresponding pdfplumber box is `[9,−9,594,774]`. A separate [render correction receipt](../validation/ln-inhibitory-transfer-phase2-overlay-corrected-receipt.json) records the fix. The corrected overlay aligns the native F/D black means and E green mean with the source rendering. **Only raster registration changed; source geometry, calibration anchors, extraction and numerical results did not.** The original numerical receipt's pending-visual-review labels are resolved by this later validation receipt, rather than rewritten.

Both overlays are now ignored research copies: [corrected verification view](../data/raw/ln-inhibitory-transfer/phase2/overlay-corrected.png) and [retained original frame error](../data/raw/ln-inhibitory-transfer/phase2/overlay-original-frame-error.png). The [relocation receipt](../validation/ln-inhibitory-transfer-phase2-relocation.json) maps historical output paths in immutable receipts to their current locations with unchanged hashes. Original figure artwork is not a tracked project asset.

## Constraint supplied to later work

These results quantify a **descriptive population timing contrast**: current builds between the fixed windows while mean source firing declines. Current changes have a physical pA scale relative to baseline even though absolute holding current is absent. Neither a conductance conversion nor a per-spike gain follows: Figure 6 holding voltage, local reversal, functional contact gain and paired cell identities remain unknown. The different cohorts must not be divided to estimate a synaptic response per source spike.

The source used female flies aged 1-3 days and broad NP3056 expression with unidentified nonexpressing target LNs. It does not identify the modern male replay targets or their receptors. Reported 100 ms acausal firing-rate smoothing, unspecified current preprocessing and an illustrated rather than measured photon clock prevent a precise causal latency or inhibitory time constant. No model promotion gate has passed merely because this source constraint is now numerical; a compatible observation mapping and separately declared model comparison are still required.

Reproduction code is [the frozen extractor](../scripts/extract_ln_inhibitory_transfer.py) and [the separate frame correction](../scripts/plot_ln_inhibitory_transfer_frame.py). Existing destinations are protected. An exact historical reproduction creates the original incorrect overlay before its separately recorded correction and relocation; do not silently replace this evidence history.
