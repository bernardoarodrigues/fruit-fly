# Independent review of the completed recurrent report

The final [results report](inhibitory-recurrent-panel-results.md) and version 3 figure pass this bounded review. No scientific or numerical reporting blocker remains. The [corrected checker receipt](../validation/inhibitory-recurrent-panel-results-independent-review-v2.json) passes 298 checks against the frozen combined analysis and saved independent reference arrays. No neural model, producer, integrator, fitting procedure or source acquisition ran during this review.

The checks cover all 60 arm/condition/seed identities; arm spike totals and reported voltage/rate ranges; complete zero controls; off-window candidate/applied and source counts; rare target responses; forward/escape silence and feeding totals; first-hop pulse contrasts; factorial effect rows; and the active-cell/quantile and finite-window refractory arithmetic. Independent subtraction of all 75,342 saved H reference rows reproduces the reported maximum production–quadrature errors (H0: 9.947598300641403e−14 mV; H1: 4.263256414560601e−14 mV), maximum ODE–quadrature discrepancy (2.0818902157770935e−12 mV), and the absence of sampled threshold ambiguity. This reduces previously evaluated reference values; it does not rerun their numerical solvers.

The interpretation stays within the evidence. The factorial compares an inhibitory equation and a bundled handling package; it does not separately identify decay, refractory reception or reset retention. Persistent firing is observed through the 1.5-second input-off interval, without claiming indefinite stability or uncontrolled growth. Three numerical seeds support the stated local contrasts, while global ranking and rare target responses remain seed dependent. A finite half-open 0.5-second window can contain 228 spikes at 22-tick spacing, so 456 Hz does not establish a refractory violation. The boundary-source paragraph now separates absence of sustained external input from the untested causal contribution of the isolated boundary spikes.

The retained physiology evidence supports withholding promotion: the engineering −75 mV reversal and rest normalization do not calibrate absolute inhibitory currents or conductances. The earlier 5 ms filter result is conditional on the displayed summary means and their graphical enclosures, not a receptor identification or general rejection of that time constant. Global phase extrema and bound counters here are reduced producer telemetry, not independently reconstructed unsaved all-cell trajectories. Automation state, publication history and broader project completion are outside this review.

Two review corrections are explicit. The [first visual finding](../validation/inhibitory-recurrent-panel-results-review-visual-v2.json) preserves the version 2 figure's artificial closing drop to zero at 3 s. I inspected the corrected version 3 PNG: its endpoints remain open, and the layout has no observed clipping or overlap. The first numerical checker stopped at check 166 because its exact-text matcher omitted the report's explicit plus signs in positive factorial rows. The [first checker receipt](../validation/inhibitory-recurrent-panel-results-independent-review.json) and original script remain unchanged; a [recorded amendment](../validation/inhibitory-recurrent-panel-results-review-amendment.json) fixes only that display matcher and creates separately named outputs. The corrected execution passed on its first attempt. These are review/presentation corrections, not model failures or neural reruns.

Pinned final artifacts (SHA-256):

| Artifact | Hash |
| --- | --- |
| Reviewed results report | `b14d6ff35d8499782183d687d114c707665667d8ce97a97e5e01d70e6daf3407` |
| Frozen combined analysis | `bb42919231572491e2adbd4adfa67f53c1ce0b87bdd5a8f229628b0797488d29` |
| Visually inspected figure v3 | `51dafb184d8a8096d46eea3ca2983ed2491c460a12b300c49704ecd2569dc718` |
| Corrected checker source | `638bd49c3fa2b3a65f2f532cf67d8f9fc05f12499fa1dbaa238414f79d3ab438` |
| Passed review receipt v2 | `96e134c7d5a68ad6f799ba0b5e4ca26c7d4bb8c88e228538f8cbd4f7c5c8dbd9` |

The receipt includes exact hashes for the physiology notes, every saved H review/reference artifact it consumed, and the preserved first failures. H1 and H0 remain experimental; passing this report review is not biological promotion.
