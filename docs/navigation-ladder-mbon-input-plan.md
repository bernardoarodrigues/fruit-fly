# Next audit: inputs to saturated MBON12–14

**Prospective saved-data audit; not executed.** Determine which recorded inputs maintain MBON synaptic states during H1 saturation, then decide whether one targeted intervention is justified. No fitting, new simulation, runtime changes or claim of a unique cause is part of this audit.

## Fixed population and evidence

Use all six completed H1 journals in `runs/20260905T060501089987Z-inhibitory-recurrent-panel`: matched constant-baseline / ethyl-acetate ordinals **26/35, 29/38, 32/41**, for seeds **11, 12, 13**. The exact ten-cell population comes from the final anatomy manifest; lists below pair graph indices with body IDs in order.

| Type | Graph indices | Body IDs |
| --- | --- | --- |
| MBON12 | 3477, 3513, 130136, 131044 | 13728, 13768, 519368, 521086 |
| MBON13 | 2550, 127463 | 12726, 514853 |
| MBON14 | 246, 1749, 7264, 8528 | 10267, 11873, 17946, 19366 |

Retain each cell separately. Soma sides are available, root sides are missing, and no mirror pairing is inferred. None of these cells belongs to the panel's 36 externally stimulated cells or 48 cells with continuous selected-state traces. **There is no stored per-tick MBON voltage or directly logged MBON delivery stream.** Full-population states are available at checkpoint boundaries.

Use the seven existing half-open windows, in 0.1 ms ticks: `[0,500)`, `[500,5000)`, `[5000,10000)`, `[10000,15000)`, `[15000,20000)`, `[20000,25000)`, `[25000,30000)`. These separate startup, baseline, the 0.5–1 s pulse, recovery with baseline input, and three input-off windows. Preserve the same windows in constant controls.

## One bounded reduction

1. Freeze an execution plan pinning the reviewer, final anatomy, panel plan (`c7af957e…`), graph manifest/arrays/annotations, six terminal/results and passing independent receipts, selection archive, and chunk/checkpoint completion records. Verify archive hashes, dtypes, shapes and completed clocks before reading. Stream each of the 600 chunks per trial once; retain failure evidence and stop on an inconsistency.
2. Extract incoming CSR edge rows for the ten targets. Retain source/target indices and IDs, source `type`/`class`/`consensus_nt`, declared model sign, integer `contact_counts`, and exact stored float32 weight. Report anatomical edge/contact totals separately from event arrivals. Keep every transmitter category and zero-weight edge; transmitter labels are not receptor-specific physiological signs.
3. Join the **recorded ordered presynaptic spikes**, not Poisson candidates or configured rates, to those edges. A spike at tick `t` visits edges at `t+18`; preserve source order within a tick and CSR edge order. Assign windows by delivery tick, carry arrivals across chunk/window boundaries, and retain deliveries beyond tick 29999 as pending. Input-off does not erase queued or recurrent activity. Check the fixed outgoing masks: H1 accepts unblocked synaptic arrivals even on firing/refractory ticks.
4. For each cell/window and presynaptic cell/class/transmitter, report emitted spikes, visited/accepted/blocked edge arrivals, contacts represented by those arrivals, positive weight increments, and negative increments converted to `h` by `−weight*(1/23)`. Keep zero-weight arrivals explicit. Do not subtract positive effective-current units from dimensionless inhibitory conductance or call contact totals a physiological gain.
5. Reconstruct only the conditional synaptic states: each tick first multiplies `p` and `h` by the frozen `exp(−0.1/5)` coefficient, then adds accepted increments in recorded delivery order. H1 retains both states through reset and decays them during refractoriness. Starting from checkpoint zero, require bitwise agreement with the ten cells' `s`/`h` at **all eight checkpoints**. Independently verify the same totals by source-spike × edge-count joins, the final packed pending queue, and target spike/window counts against checkpoints. Preserve exact target spike times and report the fraction of interspike intervals at the 22-tick refractory limit.

Save a compact incoming-edge table, per-window input summaries, reconstructed `p/h` traces and review receipt. Arithmetic convolution is a second check with a declared tolerance; its regrouped sums need not be bitwise identical. No voltage integration or new spikes are generated. The reconstruction is conditional on the observed recurrent history; it cannot establish what would happen after removing an input or identify the cause of individual threshold crossings.

## One conditional causal test, then stop

Proceed only if the checkpoint gate closes and the **same annotated presynaptic class** supplies the largest summed positive increment to these ten cells over `[5000,15000)` in all six trials, without a tie. Otherwise report ambiguity and do not substitute another intervention.

Freeze that class's exact incoming positive edge rows. The single proposed intervention is to suppress **only those edge deliveries to MBON12–14 during `[5000,15000)`**, with weights, other projections, inhibition, dynamics and external streams unchanged. A separately frozen experiment would run the matched EA/constant pairs for **all three seeds: six intervention runs**, using all six saved controls as references and requiring each pre-intervention prefix to match. Set a quiet completion trigger, then analyze the complete batch together. Compare MBON spike counts, 22-tick interval occupancy and EA-minus-constant pulse contrast; retain all outcomes. Recurrent divergence after intervention is expected. This tests contribution of that pathway in the model, not unique causation or physiological correctness; no automatic follow-up search or promotion follows. **These runs are prospective and have not been launched.**
