# Ten-second full-graph loop and retained restart failure

Three fixed ten-second assays complete with finite states, conserved resources,
upright bodies and no MuJoCo warnings. **The overall declared experiment fails**:
unmuting does not resume locomotion because the fly requests feeding at the food
patch. The mute itself is released correctly. This is useful evidence about the
existing behavioral priority rule, not a passing locomotor-restart test or
validated natural foraging.

The [plan](../validation/extended-loop/plan.json) was saved before the first
rollout. The [script](../scripts/check_extended_loop.py),
[results](../validation/extended-loop/results.json), nine actual rendered frames,
and an [independent review](extended-loop-independent-review.md) preserve the
outcomes. No model parameter, body geometry, decoder or acceptance rule was
changed after viewing the result. All conditions use seed 1, the complete
166,700-neuron / 25,582,938-edge graph, Shiu dynamics at 0.1 ms, body steps at
0.1 ms, and 5 ms sensorimotor coupling. The source/graph hashes are retained.

## Fixed conditions and observations

The current default bilateral odor and tarsal taste pathways remain enabled.
Vision, wind-reference fitting and the optional club proxy are not introduced.
The motor probe imposes 40 Hz input events on DNg97; the physical food location
is unchanged and is not supplied to a steering policy.

| Condition | Protocol | Sampled planar path | Sampled requests | Normalized intake |
|---|---|---:|---|---:|
| Sensory | Default environmental input | 0.000726 mm | 200 rest | 0 |
| Motor probe | Direct DNg97 throughout | 5.80632 mm | 20 walk, 180 feed | 0.658236 |
| Probe, mute, resume | Same probe; mute at 5 s, unmute at 7 s | 5.80632 mm | 20 walk, 40 rest, 140 feed | 0.556480 |

There are 200 endpoint samples per condition, one every 50 ms. The probe first
appears in feed mode at the 1.05 s sample, after reaching the food edge. The last
three seconds of the resumed condition request feed, with zero left/right
locomotor commands. The two probe conditions have identical sampled physical
paths: feed and muted rest both use the same posture actuator rule here, while
only feed permits abstract intake. This equality is specific to this position
and assay; it does not imply sensory feedback is generally invariant to motor
muting, as the earlier [feeding audit](feeding-motor-expansion.md) demonstrates.

The muted analysis includes endpoints from 5.25 through 7.0 s: 36 samples,
covering 50 ms intervals ending there. Its median chord speed is
8.28×10⁻⁶ mm/s, every request is rest with zero locomotor commands, and the
recorded neural intervals contain 1,630,328 spikes. Unmuting is recorded before
the 7.0→7.05 s interval. The motor decoder's existing MN9/contact feeding rule
then takes priority over walking. The failed `resume_locomotor_command` gate is
retained rather than relabeled as a success.

## What passed, and what was not tested

All sampled states are finite. Minimum settled thorax upright-z is 0.9941 across
the moving conditions. Maximum resource-balance residual is 3.85×10⁻¹²
normalized units. All three native warning counters remain zero, and each body
stays inside the configured wall bounds at sampled times. There are **no sampled
wall near-contact records**, so this run supplies no wall-collision robustness
evidence. The continuous probe exceeds the declared 1 mm path gate.

The neural clock agrees with BodyRuntime's tick-derived clock. This assay does
not save the native floating-point `data.time` at each observation, nor the
complete physical/neural arrays. Finiteness and upright/contact flags were read
from the live objects; the recorded flags cannot independently reconstruct those
arrays. Core numerical and timestep tests remain separate evidence. Sampling
cannot exclude short between-sample excursions. Chord path length at 20 Hz is
not an unsampled path integral or a high-frequency speed measurement.

Wall counts include generated contact records within the explicit pair margin;
they are not force-bearing contact tests or integrated impulses. No extra force
claim is drawn from them. The script writes a condition's diagnostic samples
after that condition completes; if an exception occurs earlier, its ordinary
run telemetry survives, but unsaved diagnostic flags would be missing.

Finite Shiu dynamics are still physiologically implausible: sampled minima reach
roughly −485 mV. The body remains female-derived and its CPG/reflex motor adapter
is a surrogate. Intake is tarsal, stationary, MN9-gated normalized bookkeeping;
no proboscis/pump mechanics, swallowing or energetic calibration is implied.
One selected seed and ten seconds do not establish long-term robustness,
natural rest/sleep, odor-guided navigation or a complete organism.

## Independent check, reproduction and compute

The [review script](../scripts/review_extended_loop.py) performs no new physics.
Its [47 passing checks](../validation/extended-loop/independent-review.json)
recompute every saved decision and motion summary, compare the snapshots and
interventions with run telemetry, and verify all nine image hashes. Passing the
review means the **failed experimental outcome is faithfully reproduced**.

```sh
# From the source version recorded by the fixed plan:
.venv/bin/python scripts/check_extended_loop.py
# Expected nonzero exit for the preserved restart gate.
.venv/bin/python scripts/review_extended_loop.py
```

The experiment refuses changed source hashes. Reproduce its historical source
revision rather than editing the plan to admit a changed model. Ignored graph
data and recorded run telemetry must be available at their manifest paths.

Each ten-second integration took 66.4–73.1 wall seconds, including telemetry and
three overview renders, excluding construction. Concurrent research processes
were active, so this is an observed run cost rather than an isolated throughput
benchmark. Peak process RSS reached 1.103 GB; it is the cumulative process high
water mark on macOS, not the size of an individual neural network or total
system memory. No extra hardware was needed for this bounded test.

The next restart experiment should explicitly isolate locomotion from the
feeding-priority state and challenge actual wall contacts. It must be a newly
declared experiment with the original failed result retained, not a change to
this experiment's threshold or recorded conditions.
