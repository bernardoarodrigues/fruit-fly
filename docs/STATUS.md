# Single-male implementation status

Evidence snapshot: 2026-09-04 Pacific / 2026-09-05 UTC. This follows [PLAN.md](PLAN.md). Full-graph execution, numerical correctness and biological fidelity are distinct results.

| Gate | Current evidence | Remaining work |
|---|---|---|
| M0 Repository/provenance | Private GitHub repository and initial push; source/processed checksums; dependency records | Continue versioning milestones |
| M1 Physical fly | Articulated MuJoCo body, actual contacts, arena, finite food/water, deterministic reset; controller parity | Female-derived body; measured male morphology work ongoing |
| M2 Sensors | Bilateral advected odor and adaptation, actual tarsal contact, physical proprioception, source-verified taste identities | Finish taste/vision/proprioceptive neural adapters and calibration |
| M3 Neural replication | Independent numerical tests; exact full Shiu630 spike replay for 100 and 1,000 ms; 90 sugar/MN9 trials | Published biological effect-size comparison and further circuits |
| M4 Full male graph | 166,700 neurons; 25,582,938 directed pairs; 124,177,617 contacts; 217 isolated selected neurons retained | Receptor-specific signs and physiological strengths remain assumptions |
| M5 Neural/body loop | Continuous full graph; DNg97 stimulation moves body; motor-readout mute suppresses movement while spikes continue; clock/reset/chunk checks | Sensory-driven calibrated movement, circuit interventions, shuffled outputs, coupling sensitivity |
| M6 Foraging/homeostasis | Contact/feed request/stationary gates; food depletion, crop assimilation, separate water balance; conservation | Odor approach remains a negative result; ingestion abstracts proboscis mechanics |
| M7 Repertoire | Reduced rest/walk/feed modes | Grooming, visual escape, sleep/circadian state, learning, male cue/song assays |
| M8 Motor mechanism | Full retained VNC participates in neural graph; frozen CPG/reflex body adapter | Motor-neuron-to-actuator calibration and refinement |
| M9 Watch/control/record | Actual full-graph viewer inspected; pause/reset/camera/motor mute verified; assay and body caveats visible | Extend display with validated modules |
| M10 Robustness/performance | Focused tests, exact replay, active full-graph benchmark, real loop controls | Longer/held-out behavior runs; voltage plausibility; compute assessment after calibration |

## Executed loop controls

All conditions used the actual male graph, seed 1, 0.1 ms neural/physics steps and 5 ms coupling, for one simulated second. [Results and frames](../validation/closed-loop/results.json) are retained.

| Condition | Horizontal displacement | Evolution + telemetry wall time |
|---|---:|---:|
| Environmental odor | 0.000723 mm | 5.90 s |
| Odor + direct DNg97 40 Hz stimulation | 5.441 mm | 7.63 s |
| Same stimulation, motor readout muted | 0.000723 mm | 5.99 s |

Clocks remained synchronized, arrays finite, and resource residuals below 1e-8 normalized units. Muting affected only the motor interface. This establishes decoder dependence in a direct stimulation assay, not natural sensory-to-walking behavior.

**Finite values are insufficient physiological validation.** The [motor audit](motor-calibration.md) found mean walking-neuron potentials down to roughly −164 mV after transferring current-based Shiu parameters/sign rules to MaleCNS. Positive graph paths exist; excessive inhibition suppresses the readouts. This is a calibration failure. A conductance-based alternative is being investigated while preserving the replicated original model.

## Compute and next gates

Active neural-only benchmarks took about 2.4–3.5 wall seconds per simulated second; full-loop checks about 5.9–7.6, excluding graph construction and renderer setup. Current RAM is sufficient. More CPU capacity can help parameter/seed sweeps. A GPU does not automatically accelerate the present Numba CPU implementation; hardware recommendations should follow a measured accelerated backend.

Next: compare bounded conductance dynamics; connect exact leg-specific appetitive taste; add compound-eye sensing and proprioceptive adapters with supported anatomical mappings; calibrate motor circuits before held-out food-search assays. Then expand the behavioral repertoire and motor mechanism, assessing flight/lifespan separately. The paired-animal stage remains deferred.
