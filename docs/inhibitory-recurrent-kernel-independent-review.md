# Independent source review of the recurrent kernel

**No remaining source blocker for the separately frozen performance probe.** This review inspected the final kernel, original `LIFNetwork`, interval solver interface, six-cell checker and its retained receipt. It did not run a network, replay, kernel or synthetic checker. The [independent receipt](../validation/inhibitory-recurrent-kernel-independent-review.json) separates manual source findings, hash checks and the author's **143 reported synthetic checks**. Those control time-series arrays were not retained, so their numerical outcomes were not independently reconstructed here.

Reviewed kernel SHA-256: `52892eabb7124dfe6140f7c0cbc4d9047301978c6706053e3230d72280ec2b0f`. The [author's control receipt](../validation/inhibitory-recurrent-kernel-checks.json) is `86134f8c541f7a71cb19e15b6fdf8223b2571a2ef6bc6d615b8c73186edf1370`, and pins both the matching checker and unchanged scalar solver/original engine.

## C0 and package semantics

C0 preserves the original signed-current expression and operation order, strict threshold, ascending cell spike order, source-identity delay queue, 18-tick delivery, original edge order, direct-event slot and subsequent voltage/synapse reset. Its scope is the fixed source parameters, no direct current and the listed input membership. Inputs have zero refractory duration, other cells 22 ticks. Initial input refractory values are configured in the new constructor; the original engine sets them at its first drive, so an unconfigured original checkpoint is not the correct initial refractory reference.

The supplied uniform stream is external to the wrapper. `seed` is metadata, not a hidden RNG. Every arm derives candidates from that stream and held probabilities. Direct 68.75 mV voltage events retain the original same-tick firing rejection even in package 1. Recurrent synaptic arrivals use the arm's own threshold/availability state: package 0 freezes/rejects/clears, package 1 always decays and receives unblocked synaptic arrivals and retains synaptic state at reset. A presynaptic block is checked at delivery, including already queued spikes. It does not suppress source firing or incoming/direct input.

For H, positive current and inhibitory ratio decay separately through the unchanged interval helper. Only negative graph weights become `−float64(weight_float32)*(1/23)` increments to h. There is no clamp or global 0 mV upper bound. The recurrent kernel's helper usage matches the earlier conditional replay equations, but the new recurrent histories will differ; that source correspondence is not empirical replay equivalence.

The author checks C0 original-state/spike/queue equality and all-arm chunk parity on six cells. Those assertions use `np.array_equal`, not explicit shape/dtype/byte comparison. The full-graph C0 gate should retain stronger byte equality where old raw reference arrays exist. The input audit explains why full voltage/synaptic parity is available at 1,500 ms but not from the old 50 ms prefix alone.

## Telemetry and failure retention

Global edge rows satisfy visited-unblocked = accepted + target-unavailable; blocked edges are counted separately, including zero-weight edges. Optional event logs cover only edges landing on selected postsynaptic cells. Counting blocked edges adds work that the original engine skipped; selected logging adds more, so timings must name the configuration.

Phase extrema use all cells with lowest-index tie breaking. The pre-threshold voltage is preserved before delivery/reset; post-external and post-reset phases are distinct. Post-reset extrema are calculated prospectively from the firing mask during the post-external scan, then exposed as completed-phase data only after reset succeeds. On a partial failure, phase progress determines validity; later-phase counters or placeholders must not be interpreted as completed observations. Nonfinite counts concern voltage, while invalid-state counters also cover synaptic values and negative H states. C voltages below −75 mV are diagnostic; H violations terminate. The solver/work counters report available updates, actual nonzero-h quadrature calls and extrema of local solver diagnostics; they do not constitute a new numerical reference comparison.

Handled solver/state/queue/bound failures preserve completed-prefix output and separately retain the attempted tick's partial records. Full checkpoint arrays may already include integration, spike, queue or delivery changes from that tick and are explicitly marked incoherent. No rollback is implied. Continuation is denied. Allocation failures, termination or an uncaught exception may bypass that structured return and remain runner-level interruption cases.

Two source-review findings were corrected before the final hash:

1. The old `selected_delivery_available` field represented the native active mask, which differs from package-1 synaptic eligibility. The result now exposes `selected_direct_available` and `selected_synaptic_available`; the older field is explicitly documented as the direct-mask alias. The new masks are included in the reported synthetic checks.
2. `last_completed_tick` denoted an exclusive boundary rather than a last processed index. The result now adds `completed_prefix_end_tick` and `last_completed_transition_tick`; the latter is boundary minus one or null. `attempted_tick` equals the exclusive boundary. Existing prefix slicing correctly retains spikes/events strictly below it.

The author exercises one H interval failure with an injected NaN, retained earlier prefix and continuation denial, plus invalid external-array rejection before mutation. Other failure phases, queue capacity, memory interruption and all possible chunk/parameter combinations are source-reviewed paths, not independently executed coverage in this review. The checker tests selected-voltage chunk traces and final state/queue equality; it does not establish every telemetry array's chunk invariance from independently retained raw arrays.

The implementation is suitable to enter the frozen bounded probe with these limits. Successful tiny-graph checks do not establish full-graph performance, physiological amplitude/timing, seed robustness or a preferred inhibitory package. Production sources were not edited by this review.
