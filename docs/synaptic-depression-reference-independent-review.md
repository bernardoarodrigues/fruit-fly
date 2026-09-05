# Independent review of the scalar depression reference

The standalone reference is numerically consistent with its declared scalar equations and fixed source parameters. **219 independent checks pass** across **56 arrays containing 93,739 values**, all **333 exact-fraction event rows**, the area table, and the source/artifact hash chains. The largest discrepancy from independent 80-digit closed-form expectations is **5.00e−15**, below the frozen `1e−12` tolerance.

The fly-protocol curves remain **unfitted model predictions**. No fly measurements, uncertainty estimates, fit residuals, or biological match criteria were evaluated. This review does not promote the reference to the male neural model or runtime.

The [review script](../scripts/review_synaptic_depression_reference.py) and [receipt](../validation/synaptic-depression-reference-independent-review.json) use saved evidence and independent algebra. They do not import or rerun the [producer](../scripts/synaptic-depression-reference.py), fit parameters, load a connectome, or simulate a brain or body. The producer's original 79 checks remain separate from this independent pass.

## Primary-source correspondence

The retained Abbott PDF's printed page 223 was inspected visually and through text extraction. Note 4 identifies rat primary visual cortex; note 6 specifies `f = 0.75` and recovery `τ = 300 ms`; notes 7 and 10 state the exponential recovery, multiplicative depression, and regular-train steady amplitude. These parameter values came from the source paper's own Figure 1B fit. “Unfitted” here means no new fit to fly data, not that the rat paper never estimated parameters. [Abbott et al., 1997, notes 4, 6, 7, 10](https://huguenardlab.stanford.edu/220/varela1997a.pdf)

The verified scalar rules are

```text
between events:  τ da/dt = 1 − a
event response:  amplitude = a_before
after event:    a_after = f × a_before
```

Recovery uses seconds: 300 ms becomes `0.3 s`. For periodic spacing `Δ = 1/r`, `d = exp(−Δ/τ)`, and `q = fd`, the fixed point is `A = (1−d)/(1−q)`. The independent finite-train expression is `a_n = A + (a_0−A)q^n`, with the first event at index zero. These expressions, evaluated with 80-digit Decimal arithmetic, reproduce all six 256-event trains at 7, 15, 20, 50, 100, and 200 Hz, including their bounds, decreasing amplitudes, and pre/post event ordering.

The separate **2 ms conductance decay** is present in Abbott note 10. The producer deliberately uses it in a linear summed kernel observation, `h(t) = Σ a_k exp[−(t−t_k)/0.002]`, rather than reproducing the paper's conductance-driven integrate-and-fire network. That additional observation convention is explicit and appropriate for a numerical reference. It supplies neither an absolute current in pA nor a mapping to the male simulator's effective-mV synaptic state.

The source methods also retain same-time events and reject backward times before assigning state. Algebra gives successive same-time amplitudes `1, 0.75`, with post-event states `0.75, 0.5625`. Recovery queries contain no state assignment. The producer's boundary, null-control, and query tests retain pass/error summaries but not their full before/after scalar traces. This review corroborates them through source ordering and algebra without describing them as independently replayed raw state histories.

## Timing and normalization

Kazama and Wilson's Figure 8D–F, Figure 9B–D, methods, and supplement Figure S8 were inspected. The main experiment used adult female flies; the relevant unitary recordings are from VM2 PNs. Figure 8F labels 15, 20, and 50 Hz. Figure 9B labels 20, 50, 100, and 200 Hz, with first-100/500-ms charge normalized to 100 Hz in C/D. The 7 Hz, 4 s baseline and 500 ms test duration are explicitly stated. [Kazama & Wilson, 2008](https://doi.org/10.1016/j.neuron.2008.02.030)

The exact simulation phase is declared rather than recovered from the paper: 28 baseline events at `−4 + j/7 s`, followed by test events `j/r` in `[0, 0.5)`. The independent reader checks each numerator, denominator, float conversion, event index, phase, and pre/post efficacy in the CSV against these rational times. The 0.1 ms waveform grid affects observation sampling only.

The common first-test efficacy is **0.7092785406656722**. It is the finite baseline's next would-be 7 Hz event, not the asymptotic value substituted by assumption. The last/first test ratios are **0.711674, 0.599591, 0.304889, 0.168330, and 0.088810** at 15, 20, 50, 100, and 200 Hz respectively. Their last events occur at 466.667, 450, 480, 490, and 495 ms; there is no event at 500 ms.

All five saved waveforms agree with an independently assembled matrix of causal exponential kernels and closed-form event amplitudes. A naming caveat should remain visible to future users: arrays ending in **`normalized_response` use unit peak per fully recovered event**. They are not divided by the first test amplitude. The separate `normalized_test_amplitude` arrays do use that first-test denominator.

Area predictions independently agree with analytic finite-window kernel integrals, including partial response tails at the upper boundary. Each ratio uses the **100 Hz integral from the same window**, not a shared denominator across windows. The independent 100/500-ms ratios at 20, 50, 100, and 200 Hz reproduce the saved table.

The baseline contribution is mathematically positive: approximately **1.35149e−34 arbitrary amplitude-seconds** per window. Adding it to an area around `1e−3`–`1e−2` produces the same float64 value, explaining the saved zero full-minus-test differences. Zero at that precision is not proof that the kernel has no prior tail, nor that experimental baseline subtraction is irrelevant. The existing producer documentation already describes this rounding limit.

## Recovery and claim boundary

Each saved recovery trace agrees with the same 80-digit exponential law. For post-train scenarios, the anchor is nominal test end at **500 ms**, after 20 ms of recovery at 50 Hz or 5 ms at 200 Hz. For the 7 Hz pause scenario, the anchor is immediately after the **last baseline event**, at `−1/7 s`; its starting state is therefore the post-event value **0.5319589056278012**. Independent queries are isolated potential probes and do not repeatedly depress the state.

All scenarios recover the fraction `1−exp(−t/0.3)` of their starting deficit, reaching 99% in **1.3815510558 s**. This is an imposed one-state property, not evidence for a measured recovery mechanism. Figure S8 distinguishes post-train recovery from recovery after a pause in 7 Hz stimulation; its caption explicitly reports a **7.5 s** pause-recovery time constant. The fixed `0.3 s` model cannot be presented as validation of that empirical timescale. Exact stimulus/probe history and the paper's recovery-ratio conventions remain unresolved here, and no quantitative residual or curve fit is claimed. [Kazama & Wilson supplement, Figure S8](https://kazamalab.riken.jp/pdf/Neuron_Kazama%26Wilson_2008_supplement.pdf)

The [prediction figure](../validation/synaptic-depression-reference-predictions.png) was visually inspected. Its model-only label, fixed parameters, normalization axes, and common-recovery annotation are legible; no measured fly points or error bars are overlaid. The figure/plot-source receipts match. The panel shapes are predictions to evaluate later, not biological pass criteria.

The reference omits stochastic release, receptor dynamics, presynaptic inhibition, morphology, and sex-specific physiology. Neither `1−f` nor event count establishes vesicular release probability or release-site count. Matching scalar algebra does not justify applying these parameters to male ORN→PN edges, other glomeruli, or the full graph. No source or runtime file was changed by this review.

Reproduce the saved-evidence review with:

```sh
.venv/bin/python -m scripts.review_synaptic_depression_reference
```

The command rewrites only the independent receipt. Primary PDFs and all frozen inputs must remain available for their hash checks.
