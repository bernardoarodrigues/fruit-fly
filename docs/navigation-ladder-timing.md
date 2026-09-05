# H1 navigation timing diagnostic

The six saved H1 trials confirm sustained VM7d projection-neuron recruitment during the ethyl-acetate pulse and an absence of matched odor contrast in MBON12/13/14 at 25 ms resolution. A separate independent comparison additionally confirms identical entire recorded MBON spike sequences for each matched seed and subgroup. FB5AB has a small, temporally varying contrast. These are post-hoc observations from the same three numerical seeds, not new simulations, biological replicates, or evidence for promoting H1.

[The frozen plan](../validation/navigation-ladder-timing-plan.json) selects constant-baseline and ethyl-acetate trials for seeds 11, 12 and 13, ordinals 26/29/32 and 35/38/41. It selects 55 distinct cells: 36 VM7d ORNs, seven VM7d_adPNs, four MBON12, two MBON13, four MBON14 and two FB5AB. The MBON12_14 group is the union of the three MBON subgroups; its counts must not be added to those subgroups again. Exact indices, body IDs and selectors are pinned to the completed Stage0/anatomy artifacts.

The first reduction passed **36,134 checks**, following four manufactured binning checks before plan creation. The independent reader verified 10,818 files against the immutable final panel manifest, read all 600 packed-spike chunks per trial, checked ordered tick/index records and original component hashes, and matched the selected per-neuron counts to both the final checkpoint and Stage0 in all seven original windows. No producer, neural model, solver or metric helper was imported. This checks the selected spike reduction and publication evidence; it does not repeat the all-neuron state or synaptic-event audit.

## What the finer windows show

Rates below are population spike count divided by cell count and window duration, in per-cell Hz. “Early” is [0.5, 0.6) s and “late” is [0.9, 1.0) s, within the [0.5, 1.0) s odor pulse. The actual emitted spikes are counted, not the declared input-event rate.

| Seed | PN EA early → late | PN EA − constant early → late | FB5AB EA − constant early → late |
| --- | ---: | ---: | ---: |
| 11 | 357.14 → 365.71 | +307.14 → +334.29 | 0 → +25 |
| 12 | 355.71 → 361.43 | +317.14 → +324.29 | +10 → +15 |
| 13 | 364.29 → 378.57 | +334.29 → +334.29 | +15 → +20 |

The 20 individual 25 ms pulse bins give PN EA rates spanning 320.00–388.57 Hz across these seeds, so the high 500 ms mean is not produced by one short onset burst. The late-minus-early PN EA difference is positive in each seed. This is an output-rate description and does not measure single-synapse efficacy or establish the presence or absence of depression.

MBON12, MBON13, MBON14, and their union have **zero EA-minus-constant count difference in every one of the 120 bins**, for each matched seed. The union's pulse rates span 444–468 Hz across 25 ms bins; its early/late rates are 453/456, 456/452, and 452/456 Hz for seeds 11/12/13. The first MBON-union spikes occur at 0.1239, 0.1075 and 0.1214 s in both conditions, before odor onset. This rules out a hidden 25 ms count contrast; matching counts alone does not establish identical sub-bin spike timing.

The [separate independent review](../validation/navigation-ladder-timing-independent-review.json) passed 93 checks, recounting all 39,600 selected per-cell bin values with a scalar loop. Its additional post-hoc comparison found byte-identical complete [0, 3) s `(tick, index)` sequences for all nine seed × MBON12/13/14 pairs. Thus these cells have no recorded spike-output contrast for this stimulus pair and these three seeds. This does not establish a universal loss of odor information, identify a mechanism, or exclude unsaved subthreshold differences. The frozen reducer and results were not amended for this additional comparison.

The seven PN cells cease emitting around withdrawal, while MBON spikes continue to the end of the three-second record:

| Seed | Final PN tick: constant / EA | MBON-union spikes strictly after that tick: constant / EA |
| --- | ---: | ---: |
| 11 | 14888 / 14893 | 6870 / 6868 |
| 12 | 15025 / 15082 | 6804 / 6780 |
| 13 | 15004 / 15004 | 6816 / 6816 |

Withdrawal is tick 15000. The seed-12 ORN cohort has one boundary spike at tick 15000 in each condition; the other two seeds have none in the off interval. The reducer does not reconstruct direct-input delivery or attribute that boundary spike anew. A last mapped-PN spike is not the last possible synaptic arrival or the last input from other cells. Continued MBON emission therefore does not uniquely establish autonomous MBON recurrence or localize the failure to a particular connection.

## Clock, artifact and interpretation boundaries

Bins are half-open integer intervals of 250 ticks (25 ms), from tick 0 through tick 30000. A recorded emission stamp `k` denotes the threshold result after integration in that tick; its post-step state clock is `k+1`. Nominal graph transmission is queued for `k+18` (1.8 ms later), delivered after integration of that later tick when outgoing transmission is permitted. The export contains emitted spikes, not reconstructed edge arrivals. First spikes after a boundary under ongoing baseline are **not evoked latencies**.

[Results](../validation/navigation-ladder-timing-results.json) retain every bin, the seven coarse windows, early/late values, first/last boundary observations and matched contrasts. [The lossless arrays](../validation/navigation-ladder-timing-arrays.npz) retain all 97,356 selected records with structured little-endian `tick:int64, index:int32` fields (12 bytes per record), corresponding body IDs, and per-cell counts. No pooled intervals, significance tests, cross-arm comparison, biological gain claim, or new mechanism are introduced. Coarse PFL3 pulse counts were already zero, so this selection did not search for a hidden PFL3 pulse burst.

| Artifact | SHA-256 |
| --- | --- |
| [Reducer](../scripts/analyze_navigation_ladder_timing.py) | `aa538180d209a00d6fc2299f53c07c2869de8d0d6369c9cd4a8edb606dc30d7b` |
| Plan | `f4b0526e02707aa5299c58412b3b68212d41e5523f63e687e37624adcb20c2ff` |
| Results | `a1ec2e3c79f703d526f9b6682d753cf685efe3835685624dd8d7888aab7b54ca` |
| Arrays | `db0823f3609a529c34d4e2e7426fd82dc7a36eac2e7e8c403b022b6199efb968` |
| Independent review | `2ce57bdc8d637bb11ff76d313d88b4f967504bd95d14e7a7b16e0ea44e7964ab` |
| Original final panel manifest | `c8410ecea4923be0f090daff7e7a14a4ba375e51cfaafd3851d1a040f69bf9e6` |

## Smallest next physiology target

The next concrete local target identified by this timing audit was **female VM2 Figure 8F** from [Kazama & Wilson (2008)](https://doi.org/10.1016/j.neuron.2008.02.030): 7 Hz for four seconds, then 15/20/50 Hz for 500 ms, n=6. The plotted ordinate is “% initial”; subsequent primary-source review did not establish the exact per-cell/per-trial denominator or pooling operation. First-test-event normalization is therefore a comparison assumption, not a recovered experimental operation. The subsequent [bounded figure extraction](orn-pn-depression-digitization.md) preserves graphical coordinates, resolved means/bars and missing values. A comparison with a static null and the [existing scalar depression reference](synaptic-depression-reference.md) must remain conditional on normalization and phase, without an absolute-current gain fit or a whole-network run. No extraction or model comparison is part of the timing reducer itself.

This target is VM2, not a measured male VM7d transfer function. The existing static audit covers DM6/VM2/DL5/DM4; the source's VM7 experiment measures lateral antennal excitation of palp PNs. The scalar reference is already implemented outside the runtime, but its published `f=0.75, recovery τ=300 ms` values come from rat cortex. Per-event depletion and stochastic release remain absent from the neural runtime; ordinary synaptic decay is not a depletion mechanism. [Recovery S8](orn-pn-recovery-digitization.md) is a separate, partly protocol-limited constraint, and its printed 7.5 s fit must not silently become a VM7d parameter or a reused held-out target. These distinctions favor a small local physiology assay over increasing recruitment that the PN spike counts already demonstrate.
