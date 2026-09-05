# H0 batch independent audit

All **12 remaining H0 trials passed**, totaling **707,807 checks**, in one saved-data batch after the full 60-trial panel had terminated. The batch covered ordinals 25, 28, 31, 34, 37, 40, 43, 46, 49, 52, 55 and 58: three seeds for baseline, ethyl acetate, isoamyl acetate and ethyl acetate with source outputs blocked. Each missing review was invoked exactly once; no review failed or was retried. No model was executed and no frozen source was changed. The earlier three H0 no-input reviews remain in the [six-control summary](../validation/inhibitory-recurrent-panel-H-noinput-audit-summary.json).

The [batch index](../validation/inhibitory-recurrent-panel-H0-batch-audit.json) records every receipt hash, check count, numerical result and source pin. Its SHA-256 is `34f23c98caa84f050c5f9cd8b67fd49738c85bf292ed55b85b5855de214a5129`; the [batch log](../validation/inhibitory-recurrent-panel-H0-batch-audit.log) retains commands and complete reader output. All start/end hashes match, including the frozen reader `80a68d09ed3d028a7bc193ab5471c270bf6576018c7cd04dab6852a500d64237`. The 12 readers took 69.0 seconds in total.

The independent integrations checked **32,199 retained reference rows**, representing **26,727 distinct input tuples when counted separately within each trial**. All 26,727 independent time-domain references selected DOP853 under the frozen stiffness rule; none required Radau. There were **zero threshold-margin ambiguities** in these sampled intervals.

| Numerical quantity | Maximum observed | Frozen gate |
|---|---:|---:|
| Production versus independent adaptive quadrature | `9.948e-14 mV` | `1e-8 mV` |
| Production versus independent 64-node quadrature | `9.948e-14 mV` | `1e-8 mV` |
| Independent ODE versus adaptive quadrature | `1.613e-12 mV` | `2e-8 mV` |
| Independent quadrature error estimate | `5.216e-14 mV` | `1e-9 mV` |

Across the retained reference inputs, the largest `h` was `72.38446357828832`, corresponding to interval-start stiffness `(1+h) × 0.1/20 = 0.3669223179`. The lowest production endpoint among these reference rows was `−73.01711722481812 mV`; this is a sampled-reference minimum, not a reconstructed full-network minimum. All selected lower-bound checks and saved global phase-counter checks passed. All three source-output-blocked trials retained only rest-state reference tuples with `h=0`, despite their imposed source spikes; they provide no nonzero-conductance numerical test.

The reader independently verified all saved 48-cell synaptic/conductance traces, strict threshold/direct-input/reset arithmetic, delayed selected-target events, source masks, spike/count consistency, refractory history and pending queues. Its [method and preflight](inhibitory-recurrent-panel-H-saved-data-audit.md) define the evidence boundary: independent H interval integration is limited to the predetermined saved reference intervals. Global reference candidates dominate the retained selected population, but their optimality over unselected cells cannot be established without unsaved all-cell interval states. The lower-bound result combines every selected step with producer-reported global counters; it is not an independent reconstruction of all global voltage trajectories. Global accepted/unavailable edge counts remain a checked partition, with exact reconstruction limited to selected dispositions and all delivery visits.

These findings establish numerical consistency within that saved-data scope. They do not establish electrophysiological amplitude or timing, adequate stimulus discrimination, biological interpretation of activity after input ends, natural behavior, or eligibility to promote an altered neural model. Comparisons across arms belong to the full-panel analysis.
