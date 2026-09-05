# Independent scalar references for the recurrent audit

The [new reference implementation](../scripts/inhibitory_panel_reference_audit.py) passes all 125 previously frozen scalar cases on its first validation execution: 1,125 case checks and four unchanged-source/input checks. Its [plan](../validation/inhibitory-panel-reference-audit-plan.json) and [results](../validation/inhibitory-panel-reference-audit-results.json) retain every case and comparison. It imports neither the producer solver nor a neural kernel, and runs no graph, spikes, resets, fit or new parameter sweep. Original conventions were inspected and pinned; this is an independent numerical implementation of the same hypothesis.

The fixed interval equations, with time in milliseconds, are

```text
dv/dt = (-52 - v + p - h*(v + 75)) / 20
dp/dt = -p / 5
dh/dt = -h / 5
```

Here v and p are in mV and h is dimensionless. Setting y = v + 75 gives a positive-forcing linear equation. For a backward fractional lag q, attenuation is x(q) = dt*q/20 + h(dt)*expm1(dt*q/5)/4. The implementation independently inverts this strictly increasing expression with Brent's method. Adaptive quadrature and separately generated 64-point Legendre quadrature integrate the transformed expression. The omitted tail is bounded by (23 + p(0))*exp(-cutoff). There is no clipping of voltage and no special call to the producer's zero-conductance branch.

The third method integrates the original three state variables in time, using DOP853 or Radau according to the frozen stiffness boundary. Radau uses an independently written analytic 3-by-3 Jacobian. Thus the two integral methods share a coordinate and inversion, while the ODE follows a separate path. The reported quadrature estimate includes its tail bound; it does not certify every floating-point or inversion error.

| Comparison across the saved 125 cases | Maximum absolute difference |
| --- | ---: |
| Saved production voltage vs independent adaptive quadrature | 2.86e-12 mV |
| Saved production voltage vs independent order-64 quadrature | 3.81e-12 mV |
| Independent ODE vs independent adaptive quadrature | 4.06e-12 mV |

All comparisons satisfy the previously frozen tolerances. Ninety-seven cases use DOP853 and 28 use Radau. The largest reported quadrature estimate is 1.13e-12 mV. These results cover only the declared scalar fixture; the actual recurrent H trials still require their own saved-state comparisons. Physiological amplitude/timing, useful stimulus contrasts, seed robustness and network persistence remain separate gates.

The `evaluate(v, p, h, dt)` API returns independent quadrature/order-64/ODE values and diagnostics. A `ReferenceAuditError` retains exact inputs, the failed method, preceding method outputs and the exception. Callers own archival and interruption handling; identical saved input tuples may share a cached numerical evaluation, while every row's provenance and comparison remain checked.

Frozen source SHA-256: `2a20ac9ed6b5dfd312b7f7aeb83028920c403f8972374213d731fcafddbea743`. Plan SHA-256: `78a2215b0efc56be3db93188abe75f2308e6eb75964e2153c9c311b4e402a8a2`. Results SHA-256: `4985dac16fe3192c6e703cafa3aaf42ab4251c75a5952baef8b65aeb950abafd`.
