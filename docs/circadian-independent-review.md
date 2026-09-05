# Independent review of the isolated circadian model

The reviewed `fruitfly/circadian.py` matches equations 1a–j and the Figure 2/4 parameter captions of Leloup and Goldbeter (1998), DOI [10.1177/074873098128999934](https://doi.org/10.1177/074873098128999934). No concrete implementation defect was found. The local primary PDF and rendered equation/figure pages were inspected; no new web retrieval was performed.

All ten states include their specified linear degradation terms. Reversible phosphorylation, PER–TIM association/dissociation, and nuclear import/export have the correct opposing signs. Totals include one copy of each protein in both complex states, as in equations 2 and 3. Time is in hours; concentrations are **tentatively nM**, and the paper defines them with respect to total cell volume. Its parameter choices are model assumptions, not measured values for the retained male connectome.

Figure 2 defaults match the caption. Figure 4 correctly changes only `vsP=0.8`, `vmP=0.8`, and `k1=1.2` before adding light. The Figure 4 drawing starts with 12 hours of light followed by 12 hours of dark; `vdT` is 4 and 2 nM/hour, respectively. Holding that interval's coefficient through all RK4 stages, including the left-hand limit at an endpoint, correctly avoids mixing coefficients across a discontinuity. An arbitrary internal oscillator phase cannot be recovered from the captions' unspecified initial conditions.

Numerical checks are saved in [the review receipt](../validation/circadian-independent-review.json), including hashes of the reviewed code, tests, and primary PDF:

- A reviewed independent reaction-flux oracle was compared with the implementation over 200 randomized asymmetric parameter/state cases. Maximum absolute derivative disagreement was `5.68e-14`; the protein-total balance residual was `1.17e-13`.
- A separate 48-hour light/dark calculation with lights-on shifted to hour 3 matched piecewise SciPy DOP853 integration within `2.33e-10` tentative nM.
- All 21 implementation-agent tests passed. These cover fourth-order convergence, light boundaries, chunking and checkpoint continuation, reset and exposed-state integrity, invalid input rejection before mutation, and atomic failure for an unsuitable integration step. Public parameter, schedule, step and tick properties are read-only. No concentration clipping hides a numerical failure.

A further numerical observation used the published parameters, the explicitly chosen all-0.1 initial state, a 1,200-hour burn-in, a 0.01-hour integration step and 0.05-hour sampling over 120 hours. It was not fitted to the paper:

| Case | Sampled period | Selected amplitude or phase |
|---|---:|---|
| Figure 2, continuous dark | about 24.15 h | MP maximum 2.564; total PER maximum 5.103; CN maximum 2.045 tentative nM |
| Figure 4, continuous dark | about 25.05 h | Total PER maximum 1.677; total TIM maximum 7.742 tentative nM |
| Figure 4, 12:12 light/dark | 24 h | MP peak ZT 16.25; total PER ZT 19.25; total TIM ZT 21.70; CN ZT 22.25 |

These are sampled maxima and periods, not interpolated estimates. The Figure 4 prose calls the dark period “close to 24 h” and broadly places protein peaks around ZT 19; the calculated TIM peak is later. Preserve the computed values and that textual approximation rather than changing parameters or applying a fitted phase shift. This review verifies a computational clock model only; it provides no neural/body coupling, sleep prediction, male-specific calibration, or independent experimental validation.
