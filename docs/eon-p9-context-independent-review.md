# Independent review of the saved P9-context panel

**The retained-data checks pass: 1,483 checks, all 12 trials and all 606,759 ordered spikes.** This confirms recording consistency and the reported circuit observations. It does not establish physiologically acceptable voltages or justify promoting a model, decoder or runtime default. The review ran no neural simulation and no body assay.

Reviewer independence: this reviewer authored the earlier Eon public-source extraction and performed a source review of the assay, but did not write or run the assay producer. The [review script](../validation/eon-p9-context-independent-review.py) reads saved arrays directly without importing the producer or neural engine. The [review receipt](../validation/eon-p9-context-independent-review.json) retains the checks, reconstructed counts, input comparisons and hashes. The producer plan SHA-256 is `0d7511333583899f05c6ba983b72973c76365251cad25c4ebbb104bc0df52919`.

## What was independently checked

The frozen source and graph-file hashes match. Graph row IDs agree with the metadata, the two P9 inputs are exactly MaleCNS `10783` and `11177` (`DNp09`), and the eleven taste inputs are exactly the planned `LgAG2` cells. They are disjoint from every actual motor readout. Both previously diagnosed negative-voltage target cells are retained among the 25 sampled cells.

All 12 trials have 5,000 neural ticks at 0.1 ms, 500 journal intervals and 501 selected-state samples. Per-cell full-trial counts, every 1 ms group/source count, and every group and per-cell count in the three reported windows agree with the raw ordered spike arrays. Selected initial/final states match the corresponding full checkpoints. Every selected last-spike timestamp was reconstructed at every sample, and all-neuron final last-spike timestamps agree with the complete spike stream.

A separate implementation of the xorshift bit arithmetic, using Python integers, reproduces every saved uniform draw and all 1 ms RNG endpoints. Every condition uses the same 13-cell input order and zero refractory duration for those cells during stepping, including cells at zero configured rate. Initial checkpoints precede that input configuration. Thus the no-event control shares eligibility settings; it is not a claim about an untouched physiological network.

Delayed edge visits independently reconstruct from spike tick plus 18, the outgoing CSR degree and source-output mask. This is a count of visited edges, including zero-weight edges and visits to postsynaptically unavailable cells; it is not a count of accepted synaptic increments. Final pending-ring counts and ordered identities match reconstruction across all 19 slots. Blocked sources remain in the pending queue because the kernel suppresses their outgoing edges only at delivery.

## Circuit findings and intervention limits

- Both forward/oDN1 cells have **zero spikes in [50, 500) ms in every P9-context condition**, in both seeds. This is verified directly from the raw spike stamps, rather than a smoothed readout.
- The P9-output-blocked control has only its P9 source spikes. Every non-P9 final voltage, synaptic state and last-spike timestamp matches the no-event resting control.
- Blocking taste outputs in the combined condition restores **the entire non-taste ordered spike stream**, and all non-taste final voltage, synaptic and last-spike arrays, exactly to P9-only in each seed. This is stronger than agreement of the named motor rates. Taste-cell dynamics themselves remain a separate intervention target.
- Candidate arrival schedules match exactly within each blocked/unblocked pair. In these saved pairs, the inferred applied-event masks also match exactly. The 13-cell source spike stream differs in three of the four pairs, demonstrating why equal external events must not be equated with equal neuronal spiking.

Applied events are reconstructed as candidate arrivals excluding a source's same-tick threshold spike. This follows the inspected engine's ordering and common zero-refractory eligibility. The kernel's applied voltage writes were not independently instrumented, so this is an inference supported by source and retained state, not a separate write-level measurement. The producer's arrival-partition check is algebraic consistency only.

## Voltage and statistical limits

The lowest 1 ms global-minimum journal report is **−474.388875 mV**. Independently reading the full final checkpoints confirms a minimum of **−423.145793 mV**, at cell `67052` in seed 12 combined P9+taste. Thus severe, physiologically implausible hyperpolarization is present in raw retained state, not just a summary label. Finite-number execution passed; physiological acceptability did not. The frozen plan deliberately excludes voltage range as a success gate, so its `passed` flag must not be described as satisfying a biological voltage bound.

Only selected cells have retained intermediate membrane/synaptic state, sampled every 1 ms. Full-network states exist at the endpoints; intermediate global extrema are journal reports. This review cannot reconstruct all interior full-network membrane updates independently from those samples, and the reported minimum need not be the absolute minimum over every 0.1 ms integration tick.

Two random seeds on one male graph and a 500 ms exposure do not support a robust population-level or biological conclusion. The Eon notebook uses a female FlyWire graph, a different sensory/ascending input set, 1 s trials and 30 trials. There was no body, contact-driven input, natural walking, feeding or navigation in this panel. Late oDN1 silence is conditional on this model and protocol; it does not establish absence of an anatomical pathway.

## Preserved reviewer correction

The initial reviewer script mistakenly required forward silence in *all* conditions. That overbroad check failed for seed 12 taste-only: one forward cell spiked at 50.1 ms and the other at 54.8 ms. The source report already limits its claim to P9 contexts, and all such conditions are silent. The original [failed review receipt](../validation/eon-p9-context-independent-review-initial.json) and [initial script](../validation/eon-p9-context-independent-review-initial.py) are preserved. The amended checker narrows the assertion to the actual claim and adds exact non-taste/resting-state checks for the source-block controls. No source experiment, raw result or neural parameter changed.
