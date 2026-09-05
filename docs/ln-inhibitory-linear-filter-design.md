# Prospective 5 ms filter direction test

**The retained figure can support a bounded, conditional direction test without a gain fit or an exact-zero baseline assumption.** The unknown nonnegative initial filter state contributes negatively to late-minus-early output. Therefore a negative upper bound on the input-driven contribution would exclude a positive difference for every positive fixed gain and every allowed initial state. No filter, convolution, input-driven bound or model comparison has been evaluated for this note; root review and a frozen execution plan come first.

The question is deliberately narrow: can a first-order 5 ms filter applied to the **displayed E population-rate curve** produce the positive late-minus-early direction of the **displayed F current curve**? It does not ask whether a biological inhibitory receptor has a 5 ms time constant, or whether a whole-network model with a 5 ms synaptic state could produce the figure.

## Inputs and fixed scope

Use the [existing extraction](ln-inhibitory-transfer-phase2.md), its [frozen amendment](../validation/ln-inhibitory-transfer-phase2-plan.json), [results/calibration](../validation/ln-inhibitory-transfer-phase2-results.json), and the full E entries in ignored [ink-bins.json](../data/raw/ln-inhibitory-transfer/phase2/ink-bins.json). The latter is 880,365 bytes, SHA-256 `0f0403a2251c609299313ef5dcf490071d7f0b60df9d0c2d6d3350bbaa632580`.

The saved E support is contiguous from **−0.197 to +0.394 s**, with no internal unsupported bins. Set `t0 = −0.197 s`, the first supported bin boundary. This covers all input times needed through the last comparison-window endpoint, +0.35 s. Earlier history is represented by the unknown initial state; do not pad the unsupported display edge or assume an unrecorded pre-stimulus rate.

Keep the original windows: baseline `[−0.15,−0.05) s`, early `[0.05,0.15) s`, and late `[0.25,0.35) s`. The baseline is retained as context and an input interval, not assigned an exact zero. The primary endpoint is late-minus-early. F's already extracted graphical interval for that difference is strictly positive, approximately +1.489 to +2.292 pA; only its **sign** is used here. D repeats the same current dataset and adds no replicate.

For each supported 1 ms bin, convert its saved full vertical ink enclosure into a rate enclosure using the retained E 20/60-tick anchor rectangles. Evaluate all corners of those anchor/ink intervals under the same affine calibration formula. Keep every resulting negative lower endpoint: the published baseline enclosure straddles zero and must not be clipped or replaced with zero. Do not use a midpoint trace or only the three window means. Independent per-bin enclosures deliberately enlarge the set allowed by common anchors and a smooth drawn curve. This makes an exclusion conservative, but an inconclusive bound is not a realizable positive-response witness.

## Equation and the unknown initial state

Declare the mathematical candidate as

\[
\tau\dot x(t)=-x(t)+G r(t),\qquad
\tau=0.005\ {\rm s},\quad G>0,\quad x(t_0)=x_0\ge0.
\]

`r(t)` is the plotted rate under the graphical enclosures, not recovered presynaptic spikes. `x` is an outward-response filter coordinate with unspecified scale. A constant additive observation offset cancels between windows. No value or physical conductance interpretation is assigned to `G`.

For a window `W=[a,b)` of width `T`, define its mean filter output and the initial-state coefficient

\[
A_W=\frac{\tau}{T}\left[e^{-(a-t_0)/\tau}-e^{-(b-t_0)/\tau}\right].
\]

The window-averaged impulse weight is

\[
H_W(s)=\begin{cases}
\big[e^{-(a-s)/\tau}-e^{-(b-s)/\tau}\big]/T,&t_0\le s<a,\\
\big[1-e^{-(b-s)/\tau}\big]/T,&a\le s<b,\\
0,&s\ge b.
\end{cases}
\]

Thus, writing `K(s)=H_late(s)−H_early(s)`,

\[
\Delta x=(A_{\rm late}-A_{\rm early})x_0+G B[r],
\qquad B[r]=\int_{t_0}^{0.35}K(s)r(s)\,ds.
\]

Both windows have width 0.1 s and are shifted by 0.2 s. Consequently

\[
\alpha=A_{\rm late}-A_{\rm early}
=A_{\rm early}\big(e^{-0.2/\tau}-1\big)<0.
\]

For every allowed input and fixed positive gain, maximizing the difference over `x0>=0` therefore gives `x0=0`. This is an extremal mathematical argument, **not a claim that the recorded baseline or initial state was zero**. The coefficient may be tiny but must not be rounded away: an unbounded unknown initial state can still have a finite or arbitrarily negative effect. If negative initial states were allowed without a bound, this argument would fail; the proposed conclusion explicitly depends on nonnegativity.

## Bound the entire input family, without constructing a trace

Let `[l_i,u_i]` enclose `r(s)` throughout bin `i`, and define

\[
k_i^+=\int_i\max(K(s),0)\,ds,\qquad
k_i^-=\int_i\min(K(s),0)\,ds.
\]

Then conservative bounds are

\[
B_{\rm lo}=\sum_i(k_i^+l_i+k_i^-u_i),\qquad
B_{\rm hi}=\sum_i(k_i^+u_i+k_i^-l_i).
\]

These use the entire bin enclosures, including the onset and inter-window history. Comparing rate-window means alone is insufficient because a causal filter also depends on earlier input. The bins are integration partitions, not a piecewise-constant reconstruction of biological rate.

Use analytical exponential integrals and split at the window endpoints and any sign change of `K`. There is one sign change immediately before the early-window end:

\[
s_* = b_e-\tau\log\!\left[1+
e^{-(a_l-b_e)/\tau}\big(1-e^{-(b_l-a_l)/\tau}\big)\right].
\]

Here `b_e=0.15`, `a_l=0.25`, and `b_l=0.35 s`; `K` is negative before this crossing and positive afterward until the last endpoint. Evaluate the crossing with `log1p` and the exponential differences with stable formulas/high precision. Do not assign one sign to the entire bin containing the crossing or evaluate the kernel only at bin centers.

The finite-history identity `∫K(s)ds = −alpha` is a useful check. A constant input with its corresponding equilibrium initial state must give zero window difference; a zero-initialized constant input has a small nonzero transient. These checks prevent accidentally cancelling a rate offset or imposing an exact baseline. Other numerical checks should cover signed interval arithmetic, an impulse with known window weights, zero input with arbitrary nonnegative initial state, and two independent precision levels for the scalar exponential integrals. Freeze a numerical enclosure guard before evaluating the saved rate bounds; keep it separate from graphical uncertainty.

## Prospective decision and retained limits

After root review, freeze one script/plan with source hashes, `tau`, `t0`, windows, bin-to-rate conversion, kernel integrals, precision/guard, and failure handling. Report `B_lo/B_hi` in the formal unit-gain filtered-rate scale, the exact initial-state coefficient expression/sign, coverage and numerical checks. Do not report a pA prediction, choose `G`, or fit a current/rate ratio.

- If the guarded upper bound is **strictly negative**, then `alpha*x0 + G*B` is negative for every `G>0`, `x0>=0` and input admitted by the conservative envelopes. This is incompatible with F's positive displayed difference under this declared filter/observation interpretation.
- If the upper bound is zero or positive within the numerical guard, report **not excluded by these bounds**. Do not label it a match or infer an admissible underlying curve from independently relaxed bins. Stop this bounded test rather than tighten segmentation, choose another time constant or fit an initial state/gain.
- Missing coverage, inconsistent calibration or failed numerical enclosure checks yields **unresolved** with the exact failure retained. No new source acquisition is needed for the present design.

This is a conditional descriptive-filter comparison across different cell cohorts: E contains five ChR-positive cells and F nine other ChR-negative cells, from broad NP3056 experiments in young females. Their means are not paired circuit input/output. E has reported 100 ms acausal Hanning smoothing; its SEM is unavailable as separate artwork, current preprocessing is incompletely specified, and light timing is illustrated rather than measured. Treat the smoothed displayed rate as the mathematical input, without deconvolution or equating it to transmitter release. A mismatch would not reject a biological receptor, determine a release mechanism, identify the modern male targets, or rule out recurrent recruitment. It would only reject this direct, fixed-positive-gain 5 ms mapping of the displayed summaries under the stated initial-state assumption.

Status: mathematical design only. No filtering, bound evaluation, gain inference or model comparison has been performed.
