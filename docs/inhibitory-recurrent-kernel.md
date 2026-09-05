# Experiment-local recurrent factorial kernel

The [kernel/wrapper](../scripts/inhibitory_recurrent_kernel.py) implements C0, C1, H0 and H1 in an isolated module. It does not modify the production neural models, weights, defaults, decoder, viewer or body. Each arm generates new recurrent spikes on the supplied graph. No full connectome was loaded or run while implementing this module; the separately frozen performance probe determines its practicality before a larger panel.

The [bounded synthetic checker](../scripts/check_inhibitory_recurrent_kernel.py) passed **143/143 checks** on a six-cell recurrent graph with positive, negative and zero-weight edges. It compares C0's complete spike stream, voltage, canonical signed synaptic state, last-spike/refractory arrays and packed pending queue against the unchanged `LIFNetwork`. It also checks all-arm chunk invariance, exact phase extrema and identities, event-disposition counts, direct-event rejection, output blocking at delayed delivery, positive-only C/H equality, no-input controls and explicit partial failure. These are implementation checks, not biological validation. The [durable receipt](../validation/inhibitory-recurrent-kernel-checks.json) retains every check and source hash; synthetic time-series arrays were not archived separately. Its SHA-256 is `86134f8c541f7a71cb19e15b6fdf8223b2571a2ef6bc6d615b8c73186edf1370`.

## API and state

```python
from inhibitory_recurrent_kernel import FactorialNetwork

net = FactorialNetwork(
    neuron_ids, indptr, targets, weights, arm,
    input_indices, selected_indices, seed=11,
)
result = net.advance(uniforms, probabilities, log_selected_events=True)
# uniforms: [nsteps, ninputs]; probabilities: [ninputs], held for this call
# one step: net.step(uniforms_for_one_tick, probabilities)
checkpoint = net.checkpoint()  # state_dict() is an alias
```

Input and selected indices preserve the caller's exact order. IDs/indices are integers and unique; graph targets, shapes, float32 weights, supplied uniforms and probabilities are validated. Input indices have zero refractory duration from construction, while all other cells have 22 ticks. This initial configuration is explicit and differs from an unconfigured `LIFNetwork` checkpoint before its first drive. No input membership or refractory-duration change is supported during the run.

`v`, `s`, `h`, `last`, `refractory` and `blocked` are public mutable state arrays. For C arms, `s` is the canonical signed effective-current state and `h` stays zero. For H arms, `s` is nonnegative positive-current state `p` and `h` is nonnegative inhibitory conductance/leak ratio. Graph arrays are shared and must remain immutable. The caller may change entries in the boolean `blocked` array at an explicit boundary; the mask is consulted at delivery, including for already queued sources.

The wrapper generates no random numbers. `seed` is provenance metadata only: the caller must construct, retain and verify the uniform stream and its source RNG boundaries. There is no hidden input, spontaneous noise, current drive, body feedback or neuronal output clamp.

The fixed macro step is 0.1 ms. C0/C1 use NumPy-computed source coefficients and the original single-state expression, including `+0.*(1-a)`. H0/H1 call the unchanged [32-point interval solver](inhibitory-factorial-solver.md). Negative weights convert by `−float64(weight_float32)*(1/23)`; positive weights remain effective-current increments. There is no voltage clamp.

Thresholding is strict `v > −45` and precedes delayed graph delivery and direct external voltage increments. Direct inputs remain 68.75 mV voltage events in every arm, rejected on a source's firing tick even under package 1. Package 1 accepts recurrent synaptic-state arrivals during refractoriness and on firing ticks, decays synapses throughout, and resets only voltage. Package 0 freezes/rejects/resets the synaptic states. All new spikes enter the 19-slot delay ring; the source-output mask is evaluated after 18 ticks.

## Returned evidence

The result includes `status`, `start_tick`, exclusive `end_tick`, `completed_ticks`, `requested_ticks`, `coherent_state`, `failure` and `partial`. Complete-prefix arrays are:

- `spike_indices`, `spike_ticks`: ordered complete network spike stream.
- `candidate`, `applied`: directly instrumented external-event masks, shape `[completed_ticks,ninputs]`.
- `selected_v/s/h`: initial and post-reset selected states, shape `[completed_ticks+1,nselected]`.
- `selected_prethreshold_v`, `selected_available`, `selected_fired`: selected voltage before delivery, integration eligibility before threshold and actual threshold firing, one row per completed tick.
- `selected_direct_available`: native active mask after threshold, governing direct voltage events. `selected_synaptic_available`: actual target eligibility for graph deliveries, all true in package 1. Presynaptic blocking remains independent. The older `selected_delivery_available` key is explicitly a compatibility alias for the **direct** mask and must not be treated as package-1 synaptic eligibility.
- `selected_events`: optional ordered rows `(tick,source_index,edge_index,target_index,disposition)` for edges landing on selected cells. Dispositions are 0 accepted, 1 target-unavailable, 2 source-blocked. Pending events are retained in checkpoints instead of assigned future outcomes.

`per_tick` contains:

| Field | Shape per call | Meaning |
|---|---|---|
| `phase_min_mv`, `phase_max_mv` | ticks × 3 | Pre-threshold, post-external, post-reset voltage extrema |
| `phase_min_index`, `phase_max_index` | ticks × 3 | Exact graph-index identities; lowest index breaks ties |
| `phase_nonfinite_count` | ticks × 3 | Nonfinite voltages by phase |
| `phase_below_reversal_count` | ticks × 3 | Voltages below −75−1e−10 mV; diagnostic for C, failure for H |
| `state_invalid_count` | ticks × 2 | Nonfinite state or negative H-state counts after integration and delivery |
| `work` | ticks × 3 | Available cell updates, nonzero-h quadrature calls, maximum inverse iterations |
| `solver` | ticks × 4 | Maximum inverse residual, tail bound, pre-integration h and `(1+h)·0.1/20` |
| `edge_counts` | ticks × 4 × 3 | Dispositions by negative/zero/positive weight |
| `phase_reached` | ticks | 5 for every completed tick; partial progress is recorded separately |

The four edge-count rows are `visited_unblocked`, `accepted`, `target_unavailable`, `source_blocked`. Hence `visited_unblocked = accepted + target_unavailable`, matching the original kernel's visit meaning. Total potential visits additionally include source-blocked edges. Zero-weight edges are visited/classified once; they are not silently discarded. Counting blocked edges adds instrumentation work even though the original kernel skips their CSR traversal. Selected-event logging can also add cost, so the performance receipt must identify its setting.

Post-reset extrema are calculated during the complete post-external scan using the known firing mask and become valid only after reset succeeds. The synthetic checks compare them against the actual selected-all-cells post-reset matrix. All phase telemetry is for actual completed ticks, not 5 ms-only samples. This module does not retain a full all-neuron/all-tick state cube or the prior state of every global extremum; a later reference-selection scheme must explicitly retain the additional states it needs.

## Checkpoint and failure contract

Checkpoints contain full copies of `v`, `s`, `h`, `last`, `refractory`, `blocked`, input/selected indices and `pending_count`, plus packed **valid** `pending` source indices in slot order. Uninitialized queue capacity is never serialized. Metadata includes arm, parameters, seed, graph hash, tick, time, state meanings, caller RNG ownership and coherence/failure information.

On a numerical/solver failure, the wrapper returns completed-prefix output rather than reporting the partially processed tick as complete. `tick`, `time_ms` and `completed_prefix_end_tick` denote the exclusive completed-prefix boundary; `attempted_tick` identifies the unfinished next transition. The older `last_completed_tick` is an alias for that boundary. `last_completed_transition_tick` is the last processed tick index (boundary minus one), or null when none completed. Mutable state can already include integration, threshold, queue or delivery effects from that transition, and `coherent_state` is false. `partial` retains its partial spike/event records, masks and phase diagnostics with an explicit validity warning. Unvisited or later-phase false/NaN entries are not evidence of zero events. Numerical metadata represents nonfinite before-state values as null with separate flags; checkpoint arrays preserve the actual values.

Continuation after failure is prohibited. There is no automatic rollback, retry, reset, amplitude adjustment or replacement trial. Validation errors in supplied arrays occur before mutation. Host termination, memory exhaustion or external interruption are not guaranteed to return a structured kernel failure; the runner still needs periodic archival and an interruption receipt. Production array inputs are trusted after construction, so deliberately corrupting CSR/pending structures is outside this interface's supported operations.

The synthetic command is `.venv/bin/python scripts/check_inhibitory_recurrent_kernel.py`. Its JSON lists every check and source hash; it loads no anatomical dataset. Successful small-graph parity and the scalar solver checks do not establish full-graph performance, physiological response amplitude/timing, seed robustness or acceptable recurrent persistence. Those remain separate [planned comparisons](inhibitory-recurrent-design.md) and [promotion gates](inhibitory-promotion-gates.md).
