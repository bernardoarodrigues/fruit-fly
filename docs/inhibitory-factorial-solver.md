# Isolated inhibitory interval solver

The [helper](../scripts/inhibitory_factorial_solver.py) passed **1,282/1,282 checks** across 125 synthetic cases and eight controls. This validates numerical transitions for a scalar inhibition-only equation. No graph, recorded input history, target threshold/reset protocol, body or runtime default was executed or changed. It is a numerical prerequisite for the prospective [four-arm replay](inhibitory-factorial-design-review.md), not a physiological or promotion result.

The helper integrates an available, event-free interval with positive effective current `p` in mV and inhibitory conductance/leak ratio `h`:

```text
20 dv/dt = −52 − v + p + h(−75 − v)
dp/dt = −p/5; dh/dt = −h/5
```

Times are milliseconds. Positive graph weights will increment `p`; negative weights will increment `h` by `−w/23`. The caller owns that event conversion and all C0/C1/H0/H1 availability, delivery, threshold and reset decisions. The −75 mV reversal is the fixed engineering prior, not a value fitted or established for either target. Positive excitation remains current-like, so there is no universal 0 mV upper bound.

For `h=0`, the helper uses NumPy-computed source coefficients and the exact Shiu voltage expression, including its operation order. The primary C0 replay must still retain the original single signed state and its original update expression in the driver; splitting positive and negative sums would not guarantee bitwise equivalence.

For `h>0`, let `y=v−E_I`, `D=E_L−E_I=23`, and

```text
A(t) = t/20 + h0·5/20·[1−exp(−t/5)].
```

The integrating-factor solution is evaluated in attenuation coordinate `x=A(dt)−A(u)`. With `r=dt−u`, each quadrature node solves the monotone equation

```text
x = r/20 + h_end·5/20·expm1(r/5),  r∈[0,dt].
```

The resulting integral kernel is

```text
exp(−x) · [23 + p_end exp(r/5)] / [1 + h_end exp(r/5)].
```

This change of variable resolves the short endpoint response at high conductance without requiring the ordinary time quadrature to discover a narrow boundary layer. A fixed positive 32-point Gauss–Legendre rule integrates to `min(A(dt), log(23+p0)−log(1e−13))`. The omitted integral is bounded above by `(23+p0)exp(−cutoff)` when truncation occurs; it is zero when the complete interval is integrated. Safeguarded Newton iteration uses `abs(residual)≤1e−13(1+x)` with a limit of 48 iterations. No voltage clamp is applied. Synaptic states receive their exact exponential decay.

The production function is Numba-compatible:

```python
hybrid_step(v, p, h, dt, a, b, coefficient, nodes, weights)
# returns:
# (v_next, p_next, h_next, tail_bound_mv,
#  max_inverse_residual, max_inverse_iterations, cutoff)
```

`coefficients(dt)` computes `a,b,coefficient` using NumPy outside the compiled caller. `NODES32/WEIGHTS32` and `NODES64/WEIGHTS64` are exported. Coefficients must correspond to the supplied interval; the function does not recompute or independently validate that caller contract. All threshold and delayed-event decisions in the upcoming replay remain on its original 0.1 ms macro clock.

The [validation plan](../validation/inhibitory-factorial-solver-plan.json) was frozen before case evaluation. It includes `h=0, 1e−8, 0.1, 3±1e−6, 3, 100, 10,000, 100,000,000`, `p/h=0, 0.1, 1, 100`, initial voltages −75/−52/−45.1 mV, additional nonzero excitation-only inputs, and 0.05/0.025 ms interval cases. The references use independent Brent inversion plus adaptive SciPy quadrature, and a time-domain ODE solver: DOP853 for stiffness at most 10, Radau above it. Separate constant-conductance analytic controls check the coincident-exponent limit near `h=3`; that constant-conductance equation is explicitly different from production's decaying conductance. Event-free subdivision controls do not shift any target threshold or event schedule because those mechanisms are absent from these tests.

The [saved receipt](../validation/inhibitory-factorial-solver-results.json) retains every case, transition, reference, error, inversion diagnostic and check. Maximum absolute differences were:

| Comparison | Maximum difference, mV | Frozen tolerance, mV |
|---|---:|---:|
| Production 32-point versus adaptive quadrature | 2.8564e−12 | 1e−8 |
| Production 32-point versus 64-point | 3.6806e−12 | 1e−8 |
| Independent ODE versus adaptive quadrature | 7.2475e−13 | 2e−8 |

All sampled interval bounds `v≥−75` and `v≤max(v0,−52+p0)` passed at tolerance 1e−10 mV. All `h=0` cases matched the source expression bitwise. Maximum stiffness `(1+h)dt/20` was 500,000.005; inversion required at most three iterations, with maximum residual 1.9185e−13. Maximum reported tail was 1.0000000000000036e−13 mV, within the declared 1.01e−13 gate. The references used 97 DOP853 and 28 Radau cases. Their agreement and quadrature estimates are numerical evidence on this grid, not rigorous global error bounds for arbitrary future inputs.

Frozen SHA-256 receipts:

- Helper: `ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711`.
- Plan: `14df7dad75cec57c86f3608c6ffec842b0cf7e83d707758f2d6220198fe6d687`.
- Results: `7f0a65072d1a0cd7121c7405e7671a3c44013a85af951e0d864bb4617c284e38`.

The commands were `.venv/bin/python scripts/inhibitory_factorial_solver.py --prepare`, followed by the same command without `--prepare`. Existing plans/results refuse overwrite. Preserve these receipts when reproducing in an isolated output location. Recorded-state local errors and complete four-arm event accounting remain work for the replay. Physiological amplitude/timing, stimulus contrasts, seed robustness and a recurrent full-graph evaluation remain explicit [promotion requirements](inhibitory-promotion-gates.md); bounded voltage alone is insufficient.
