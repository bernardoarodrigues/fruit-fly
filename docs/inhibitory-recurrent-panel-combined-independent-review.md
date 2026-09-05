# Combined panel analysis: independent code and saved-result review

The first independent review passed **3,804 checks**, with no failures or retries. The reviewed aggregate is `bb42919231572491e2adbd4adfa67f53c1ce0b87bdd5a8f229628b0797488d29`; the executed reducer source is `f9d4f63b8a3aca75e5e2c5b832af4fcc50fd3a9b41ce36729ba43075a1548a35`.

The previously identified integrity gap was fixed before the reducer's first execution: selection metadata is checked against the frozen plan, both final-checkpoint files are checked against the frozen trial artifact records, and final counts must have shape `(7, 166700)` and dtype `<i8`. The reducer's actual per-tick keys, phase order, solver-column order, window normalization, factorial coefficients and contrast operand handling agree with the saved schemas. Terminal resource snapshots remain explicitly recorded measurements rather than a new resource census.

This review rehashed all 306 recorded aggregate inputs, checked all 60 trial/audit/result/terminal links and the total of 2,871,695 component checks, and reproduced the 72,000-entry chunk path/hash digest from frozen artifact records. It did not rehash those chunk payloads or repeat their raw-spike audits.

Fresh numerical checks used final checkpoint counts for the four seed-11 ethyl-acetate arms (ordinals 2, 33, 34, 35), covering all 12 cohorts and seven windows. Integer-count order statistics and exact rational interpolation independently reproduced 1,680 rate quantiles; exact rational count rates also reproduced all 420 selected factorial values. Maximum absolute discrepancies were:

| Quantity | Maximum discrepancy (Hz) |
| --- | ---: |
| Mean per-cell rates | 7.11e-15 |
| All-cell rate quantiles | 1.87e-11 |
| Active-cell median rates | 1.43e-14 |
| Factorial effects | 2.85e-14 |

All were below the frozen `1e-10 Hz` tolerance. Quantile checks used exact fractional ranks rather than NumPy's floating-point rank arithmetic. No `numpy.quantile`, `numpy.median`, reducer, model, or producer helper was called by this review.

These checks support the aggregate's numerical consistency within the stated scope. Global extrema remain producer telemetry; the other 56 checkpoint distributions and stimulus contrasts were source-reviewed but not freshly recomputed here. The three technical seeds and three-second duration do not establish biological robustness, measured physiology, long-term stability, or body behavior. This reviewer authored the independent scalar reference helper and executed the separate H1 batch; that prior involvement is disclosed. No H1 promotion follows.

The [receipt](../validation/inhibitory-recurrent-panel-combined-independent-review.json), [frozen review plan](../validation/inhibitory-recurrent-panel-combined-independent-review-plan.json), and [review script](../scripts/review_inhibitory_recurrent_panel_combined.py) retain the exact source pins, selected checkpoint scope, numeric maxima, check categories and examples. No reducer/model rerun or frozen-file edit was performed.
