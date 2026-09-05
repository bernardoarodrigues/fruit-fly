# Fixed Turner 2008 KC conductance reference

2026-09-05. The complete three-arm local assay passed **58/58 numerical checks on its first execution**. The printed conductance settings produce EPSPs close to the authors' intended amplitudes, but do not reproduce all reported mean rise times. This establishes a numerical reference for the published equations; it does not establish physiological calibration or replace the current neural model.

The [frozen plan](../validation/turner-kc-conductance-plan.json), [results](../validation/turner-kc-conductance-results.json), [arrays](../validation/turner-kc-conductance-arrays.npz), [completion receipt](../validation/turner-kc-conductance-completion.json) and [standalone script](../scripts/assay_turner_kc_conductance.py) retain the first execution. No parameter was fitted, no network ran, and no source defaults changed. The separate [independent review](../validation/turner-kc-conductance-independent-review.json) subsequently passed **204/204 checks on its first execution**, using independently written scalar Radau integration with the analytic gate and no producer import. It checked all nine sampled trajectories, all readouts, density-current algebra, zero-event semantics and source/terminal pins; maximum voltage discrepancy was 1.76×10⁻¹² mV. This is numerical validation, not physiological acceptance.

## Fixed equations and units

Parameters are transcribed from [Turner, Bazhenov & Laurent 2008](https://pubmed.ncbi.nlm.nih.gov/18094099/), pp.735–736 of the [retained public author PDF](../data/raw/pn-kc-physiology/turner2008-author.pdf). The source audit and caveats remain in [research 21](../research/21-pn-kc-physiology-calibration.md) and the [mathematical candidate review](pn-kc-waveform-candidate-review.md).

With milliseconds, millivolts and baseline-relative voltage `u = V − EL`:

\[
\dot O=\alpha(1-O)T-\beta O,
\qquad
\dot u=-\frac{g_L+\bar g O}{C_m}u+
\frac{\bar g O}{C_m}(E_{syn}-E_L).
\]

- `Cm = 1 μF/cm²`, `gL = 0.089 mS/cm²`, `EL = −57.8 mV`, `Esyn = 0 mV`.
- `α = 2.5` and `β = 0.4` in the source's millisecond convention. The transmitter concentration unit is unspecified; `T = 0.5` is not relabeled mM.
- One transmitter pulse: `T = 0.5` on `[0,0.3)` ms, then zero; initial `O = u = 0`.
- Event arms use `gbar = 0.05` and `0.04 mS/cm²`; the zero-event arm uses `0.05` with `T = 0` throughout.
- Native voltage starts at `EL = −57.8 mV`. A **separate ideal clamp at −60 mV** supplies the normalized synaptic-current kinetics; it excludes leak current.

Numerically, `mS/μF = ms⁻¹` and `mS × mV = μA`; there is **no extra factor of 1,000** in the equations above. Outward synaptic current density is `gbar O (V−Esyn)`, negative for this excitatory input. The table reports its inward magnitude at the separate clamp. Unknown membrane area prevents conversion to total pA, capacitance, or nS per graph contact.

The event clock starts at prescribed synaptic activation, not at odor onset or a measured presynaptic spike. There is no threshold, reset, refractory mechanism, APL or recording-filter model in this subthreshold reference. Consequently, it supplies no spiking or recruitment result.

## Whole-batch results

| Readout | gbar 0.05 | gbar 0.04 | Source comparison |
|---|---:|---:|---|
| EPSP peak above −57.8 mV | 1.457080 mV | 1.169314 mV | Author-intended 1.4 / 1.2 mV; observed spontaneous-event mean 1.4 ± 0.8 mV, median 1.2 |
| EPSP 10–90% rise | 2.644138 ms | 2.648093 ms | Reported 2.1 ± 0.5 ms |
| EPSP peak time from prescribed event | 4.950671 ms | 4.955591 ms | No matched scalar source target; not an evoked latency |
| EPSP theoretical late-tail constant | 11.235955 ms | 11.235955 ms | Source falling-phase fitted constant 11.5 ± 5.3 ms; fitting window unspecified |
| EPSP peak-to-first-1/e fall | 14.039454 ms | 14.037925 ms | Additional predeclared model metric, not the paper's exponential fit |
| Normalized clamp EPSC 10–90% rise | 0.238238 ms | 0.238238 ms | Reported 0.9 ± 0.4 ms |
| Clamp EPSC late-tail and peak-to-1/e | 2.500000 ms | 2.500000 ms | Source fitted constant 2.8 ± 1.2 ms; exact gate tail here |
| Clamp inward synaptic-current peak density | 0.887339 μA/cm² | 0.709871 μA/cm² | No absolute EPSC amplitude target recovered from source Fig.3D |

The zero-event arm remains exactly at baseline with zero gate and synaptic current at all saved samples. Its normalized rise/decay and peak-time metrics are **null**, not zero-time responses.

The amplitude discrepancies from the authors' intended values are +0.057080 and −0.030686 mV. The EPSP rises exceed the reported mean by +0.544138 and +0.548093 ms; the clamp rise is 0.661762 ms below its reported mean. No adjustment followed these findings. Source dispersions are preserved as reported and are not used as statistical acceptance intervals; these are heterogeneous, small event/cell cohorts, not exact observations of one canonical KC.

The transmitter-gate calculation explains the short clamp rise directly: while the transmitter is present, `O = (αT/(αT+β)) × [1−exp(−(αT+β)t)]`; after 0.3 ms it decays with `1/β = 2.5 ms`. The gate reaches its peak at the cutoff. Matching the EPSP's approximate amplitude does not fix that normalized current waveform.

## Numerical evidence and decay limits

The producer solves the **coupled gate and voltage ODEs** using DOP853, splitting the integration at 0.3 ms. Maximum step sizes 0.2, 0.1 and 0.05 ms were frozen, with the last as primary; all three sampled trajectories are retained at 0.01 ms spacing through 200 ms. Continuous peaks and crossings come from dense-output root solves, not nearest output samples.

Independent within-producer verification uses the exact piecewise gate and its analytic integral in an integrating-factor quadrature for voltage. The quadrature is split at the pulse cutoff. It checks 194 time points per event arm and 190 for the zero-event control, including prespecified early/boundary/late anchors and every measured voltage peak/rising crossing/1/e point.

- Maximum ODE versus independent voltage-quadrature difference: **3.10×10⁻¹⁵ mV** (limit 10⁻⁸ mV).
- Maximum reported quadrature error estimate: **9.77×10⁻¹³ mV** (limit 10⁻⁹ mV).
- Maximum voltage difference across the frozen step-size comparisons: **1.73×10⁻¹² mV** (limit 10⁻⁸ mV).
- Exact-gate agreement, pulse-boundary continuity, current-density algebra, finite states, physical bounds and zero-event checks all passed.
- At 200 ms the largest residual depolarization is **5.42×10⁻⁸ mV**, reached by continuous decay, without clearing state.

Numerical accuracy is much tighter than the source's measurement precision, so extra displayed digits identify reproducible calculations rather than biological certainty.

The voltage decay is curved near its peak. For gbar 0.05, the instantaneous log-slope time constant is about 35.21, 13.59, 11.65, 11.25 and 11.236 ms at 1, 5, 10, 20 and 40 ms after the peak. Its asymptotic constant, its 14.04 ms peak-to-1/e duration and a finite-window exponential fit are different quantities. **No exponential fit was performed here**, and the source's unknown fit window was not guessed or selected after seeing the result.

The printed `Cm/gL` ratio is **11.235955 ms**. The separately reported **>200 ms somatic current-injection membrane constant is therefore not reproduced**. Nor can total somatic resistance >10 GΩ be tested without area. This is the authors' effective synaptic point-cell approximation, not a full intrinsic-KC model. Absolute contact strengths, male VM7d specificity, APL calibration and spiking behavior remain unresolved.

## Reproducibility pins

| Artifact | SHA-256 |
|---|---|
| Producer | `7a19cfff32c999d7865f5d6f1d11016d3a590180fabf0057de618bb5807e3843` |
| Plan, frozen before execution | `7fe5d98a2717f0499e7677093f227d3754eec42891d216363b1e8655b066c845` |
| Results | `4d28d85529adbd88909e4f4b8d7aa6c655b5b4650dea75b45807e65e539b60d2` |
| Arrays | `64c916e9e5f634e2ca7be6cd6ae5b7b5882a82d6cefb4d8b7cf4eafd01e32ed4` |
| Primary PDF | `b91b357db8110c073e7f3e6ee0e1132cac466c722f6b97997dfe89e755f7618d` |

The plan also pins the extracted primary text, earlier source review and environment. The started/completion receipts preserve the execution links; results name each array, shape and dtype. Arrays are small local-model trajectories, not evidence of a neural-network rerun. Exclusive output creation prevents overwriting the completed attempt.
