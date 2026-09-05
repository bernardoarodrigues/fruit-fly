# Independent review of the saved recurrent performance probe

**No correctness blocker was found in the saved v2 results. All 499 independent checks pass.** C0's complete initial and final canonical arrays match the fresh original-engine reference byte for byte. Its 113 ordered spikes also reproduce the archived original 50 ms prefix. The review [script](../scripts/review_inhibitory_recurrent_performance.py) imports only standard libraries, NumPy and SciPy; it does not import a producer, integrate a network or generate new spikes.

This checks the [frozen v2 plan](../validation/inhibitory-recurrent-performance-plan-v2.json), the [completed producer receipt](../validation/inhibitory-recurrent-performance-v2/results.json), all 126 listed artifact files and all 19 pinned source files. The reviewer records 147 distinct input-file hashes including the plan and producer receipt. The producer's 280 checks are retained as producer evidence; they are not counted again as independent reconstruction. The original pre-graph Numba compilation failure remains preserved with an empty arm list. The review itself succeeded on its first execution, with no failure, correction or rerun.

## Identity, events and saved states

The reviewer recomputes the graph digest from the ordered 166,700 neuron IDs and 25,582,938 CSR edges, verifies the exact 36 input cells and 48 selected cells, and regenerates all 18,000 xorshift uniform draws from seed 11 using independent integer arithmetic. Every arm has the same 30 candidate events, logical RNG boundaries and source ordering. All 30 candidates were actually applied in each arm.

Each arm's complete saved spike history independently reconstructs its final last-spike vector, pending source queues in ring-slot order, refractory availability and selected firing flags. At every delivery tick, the reviewer traverses the source's graph edges in their original order, retaining exact edge indices and float32-to-float64 weight values. This reconstructs all global edge counts by negative/zero/positive weight and accepted/unavailable/blocked disposition. The entire selected event sequence matches by tick, source, edge, target and disposition. These comparisons are against actual saved events, not merely their hashes.

| Arm | Spikes in 50 ms | Visited edges | Accepted edges | Target-unavailable edges | Pending sources at 50 ms |
|---|---:|---:|---:|---:|---:|
| Fresh reference | 113 | 72,031 | 71,802 | 229 | 7 |
| C0 | 113 | 72,031 | 71,802 | 229 | 7 |
| C1 | 2,861 | 916,662 | 916,662 | 0 | 1,053 |
| H0 | 99 | 66,198 | 65,999 | 199 | 2 |
| H1 | 150 | 104,010 | 104,010 | 0 | 3 |

For the 48 selected cells, every stored voltage/synaptic/conductance trace has 501 boundary rows and 500 prethreshold rows, including exact continuity across all ten chunks. Independent synaptic decay, accepted signed-weight updates and reset handling reproduce every selected synaptic/conductance boundary value **bit for bit**. Direct 68.75 mV increments and voltage resets reproduce every selected final-tick voltage exactly. Source refractory values, all-cell available-update counts, selected threshold flags and final valid queues match their independent reconstructions.

The C0/reference complete-state comparison covers voltage, signed synaptic state, zero conductance, last-spike times, refractory values, source block mask, pending counts and pending sources, including shape and dtype. Final state digests are also independently recomputed. Intermediate 5 ms global states were not retained: their matching producer digests are reported as **producer summaries**, not independent intermediate global state parity.

## Independent interval integration

Before computing errors, the review selected **all available intervals of all 48 selected cells in H0 and H1**, with the existing `1e-8 mV` tolerance. No interval was selected or omitted according to its error. All selected intervals were available in these short records, yielding 24,000 checks per hybrid arm.

With milliseconds as the time unit, `y=v+75` and `A(t)=t/20+h0*5/20*(1-exp(-t/5))`, the independent calculation is

\[
y(0.1)=y_0e^{-A(0.1)}+
\int_0^{0.1}e^{A(u)-A(0.1)}\frac{23+p_0e^{-u/5}}{20}\,du.
\]

This is direct time-domain SciPy quadrature, distinct from the producer's attenuation-coordinate Gauss–Legendre solver. The fixed settings are `epsabs=1e-11`, `epsrel=1e-12`, `limit=200`; stable exponential differences avoid subtracting large attenuation values. Each comparison uses that interval's saved initial state. It does not integrate a recurrent trajectory or predict a new spike history.

| Arm | Checked intervals | With positive initial h | Initial h range | Maximum voltage error | Maximum quad error estimate |
|---|---:|---:|---:|---:|---:|
| H0 | 24,000 | 9,589 | 0–14.03925 | 1.4211 × 10⁻¹⁴ mV | 3.2000 × 10⁻¹⁵ mV |
| H1 | 24,000 | 10,227 | 0–14.03925 | 1.4211 × 10⁻¹⁴ mV | 3.8367 × 10⁻¹⁵ mV |

The independent closed-form current-arm interval calculation has zero error on the selected available C0/C1 intervals. No pA/nS conversion, receptor identification, amplitude fit or new parameter selection is made.

## Bounds, coverage and interpretation

All endpoint voltage/synaptic/conductance arrays are independently finite. The hybrid endpoint conductance and positive-current states are nonnegative, and endpoint voltages exceed the declared −75 mV engineering bound. The saved per-tick phase diagnostics are finite, completed and internally consistent; every selected phase value lies within its reported global extrema. When an extremum names a selected cell, its value matches the selected trace. Final all-cell minima/maxima and their indices are independently recomputed. Global intermediate extrema and nonfinite counts remain instrumented telemetry because an all-cell intermediate state cube was not retained.

| Arm | Final all-cell voltage range | Recorded range across three phases/all ticks |
|---|---:|---:|
| C0 | −199.6018 to −45.2372 mV | −213.1957 to +18.2723 mV |
| C1 | −176.0426 to −45.0009 mV | −193.1920 to +18.6247 mV |
| H0 | −70.1997 to −45.1226 mV | −73.0991 to +18.2237 mV |
| H1 | −69.8005 to −45.0267 mV | −72.5924 to +18.4053 mV |

The phase maxima include direct voltage increments before the following tick's threshold check; finiteness does not make them physiological measurements. The hybrid lower bound follows the declared engineering equations and nonnegative states, not a measured reversal potential.

The archived data exercise global target-unavailable rejection in C0/H0 and selected synaptic/reset updates. They do **not** exercise a blocked source, any selected refractory-unavailable interval or an actual same-tick direct-input rejection: all selected spikes belong to zero-refractory input sources. Those empty cases must not be described as positive coverage of the corresponding branches. Kernel synthetic/source tests are separate evidence.

This is one seed, one baseline input and only 50 ms. C1 already has substantially more spikes and a larger pending queue: its last two 5 ms chunks contain 489 and 2,174 spikes. That short-window increase is preserved rather than described as a uniformly quiet result. There is no withdrawal period, stimulus contrast, seed panel or persistent-activity test here. Producer timing and sampled resource limits are checked as recorded metadata, not remeasured performance. No physiological or model-promotion gate is passed, and H1 remains unselected.

## Reproducibility

- [Independent receipt](../validation/inhibitory-recurrent-performance-independent-review.json): SHA-256 `03be066f5559b7cfd769cda92b4ee5a6244b621a5074c5b6714f6620ba66f41a`.
- [Review script](../scripts/review_inhibitory_recurrent_performance.py): SHA-256 `6d21bdc8bddeb626bca466c8fea1442eff9fac76f97c75550ec6df36a454bb12`.
- Frozen producer plan: SHA-256 `b8dce6c73dad3f0502ef5c13cc866257a84dc33f9adf5c7b5dd3b62ac17e6360`.
- Prospective review note before execution: SHA-256 `5394ebaa0597577762a70d62ad04b113e0d4af9d9e4a55744c5fe2e46e39d9be`; this final report replaces its pending status, while the pre-execution hash was sent to the parent before the review ran.

The reviewer refuses to replace an existing receipt. It catches and records exceptions and failing assertions before returning failure; a subsequent corrected review would require a separately preserved first attempt. Producer inputs and results remain unchanged.
