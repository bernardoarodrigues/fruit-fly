# Independent extended-loop review

The completed three-condition experiment **fails its predeclared resume
locomotor-command gate**, and correctly preserves that failure. All **47
independent review checks pass**: saved-data arithmetic, source/plan/frame
hashes, run-log consistency and every reported gate agree. Review success is
not experiment success or biological validation.

The [review script](../scripts/review_extended_loop.py) runs no physics and
changes no source experiment or live viewer. The
[receipt](../validation/extended-loop/independent-review.json) records hashes,
recomputed gates and input limitations. The original plan was already present
when this independent review began during the first rollout; its hash matches
the completed result and all planned source hashes match. This is a local
predeclared experiment record, not external preregistration.

```sh
.venv/bin/python scripts/review_extended_loop.py
```

| Condition, seed 1 | Sampled planar path (mm) | Lowest sampled upright z after 0.3 s | Declared gates |
|---|---:|---:|---|
| Sensory | 0.0007258103 | 0.99984846 | Pass |
| Continuous direct-DNg97 probe | 5.806320215 | 0.99412645 | Pass |
| Probe, mute, resume | 5.806320215 | 0.99412645 | Resume locomotor-command gate fails |

Each condition retains exactly **200 snapshots at 50 ms intervals**. The source
resolves the four wall names explicitly and uses the actual thorax body's
orientation. Position, requested motor output, spike totals, voltage summaries
and resource residuals agree with all 600 corresponding run-log snapshots.
The largest saved resource residual is **3.85×10⁻¹² normalized units**. No
condition contains sampled wall-contact records or MuJoCo warnings.

## Intervention and failed-gate interpretation

The mute is applied at **5 s before the 5→5.05 s interval**; unmute is applied
at **7 s before 7→7.05 s**. Thus the 7 s endpoint remains muted. The review
checks exact control entries and all logged mute flags. The designated
5.25–7 s window contains **36 endpoint samples** with requested rest and zero
left/right drive. Its median chord speed is **8.2765×10⁻⁶ mm/s**. The brain
produces **1,630,328 spikes** during those intervals, with nonzero activity in
all 36. Motor muting does not silence neurons or remove the direct probe.

After unmuting, **all 60 sampled requested behaviors are `feed`**, with zero
locomotor commands. The existing decoder gives its feeding readout/contact gate
priority over forward drive. Therefore the failed gate is not evidence that the
mute remained enabled. It also cannot be turned into a passing locomotion test
by relabeling feeding or changing the gate after inspection. A future assay
could predeclare a separate movement-resumption setting or a broader motor-
readout-resumption endpoint; the present failure remains.

The neural circuit and body can also alter sensory feedback during an
intervention. These closed-loop runs do not isolate neural effects under matched
afferents. The imposed probe plus existing odor/taste inputs are engineering
conditions, and `feed` denotes the existing abstract intake interface.

## Retained-frame inspection and limits

All **nine source frames** at 5, 7 and 10 s were viewed directly and their hashes
verified. The sensory frames show the fly at its initial location beside the
food patch. Both probe conditions show it at the patch's edge after approach,
consistent with their saved positions and feeding requests. The overview scale
cannot resolve gait, mouth contact or swallowed volume; static frames cannot
prove behavior between samples. Rendering artifacts on patch surfaces are not
treated as contact measurements.

The following limits matter when interpreting or extending this diagnostic:

- `sampled_wall_contacts` counts generated MuJoCo contact records without
  distance, exclusion or force filtering. FlyGym's contact-pair margin is
  **0.001 mm**, so these would be sampled near-contact geometry, not verified
  force-bearing touch or integrated contact impulse.
- The clock gate compares neural time to the body's integer-step-derived time.
  Native `data.time` was not retained separately. Full qpos/qvel and neural
  arrays, thorax matrices and raw contact records were not saved; finite-state
  flags, upright scalar and warning counts remain recorded witnesses rather
  than independently reconstructed full states.
- Path and speed use 50 ms straight-line chords. The 5.25 s endpoint's speed
  covers 5.20–5.25 s. Behavior is the last requested command of each snapshot,
  not continuous time allocation; the arena check covers the thorax's x/y
  point inside outer wall bounds, not every body segment or wall penetration.
- Current-condition upright/contact/finite diagnostics are held in memory until
  that 10 s condition finishes (`check_extended_loop.py:86–94,134–135`). A future
  mid-condition exception would omit them from the result even though run
  telemetry survives. Persist these diagnostics incrementally in a future plan.
- Reported wall duration excludes construction and includes three renders. RSS
  is process-lifetime peak, not a per-condition allocation or leak measurement.

These are **three ten-second engineering trials at one seed**. Finite dynamics,
upright posture and ledger conservation do not repair the known Shiu voltage
pathology or establish natural feeding, swallowing, navigation, biological
necessity or long-term/general robustness.
