# Single-male implementation status

Evidence snapshot: 2026-09-04 Pacific / 2026-09-05 UTC. This follows [PLAN.md](PLAN.md). Full-graph execution, numerical correctness and biological fidelity are distinct results.

| Gate | Current evidence | Remaining work |
|---|---|---|
| M0 Repository/provenance | Private GitHub repository and initial push; source/processed checksums; dependency records | Continue versioning milestones |
| M1 Physical fly | Articulated MuJoCo body, actual contacts, arena, finite food/water, deterministic reset; controller parity | Female-derived body; measured male morphology work ongoing |
| M2 Sensors | Bilateral odor; leg-specific sweet input; optional 137-cell FeCO club proxy; actual compound-eye samples; local antenna airflow and verified female wind measurements | Wind-to-neuron and spatial/graded visual mappings; water/labellar/pharyngeal inputs; sex transfer, hook/claw tuning and receptor calibration |
| M3 Neural replication | Independent numerical tests; exact full Shiu630 spike replay for 100 and 1,000 ms; 90 sugar/MN9 trials | Published biological effect-size comparison and further circuits |
| M4 Full male graph | 166,700 neurons; 25,582,938 directed pairs; 124,177,617 contacts; 217 isolated selected neurons retained | Receptor-specific signs and physiological strengths remain assumptions |
| M5 Neural/body loop | Continuous full graph; DNg97 stimulation moves body; motor-readout mute suppresses movement while spikes continue; clock/reset/chunk checks | Sensory-driven calibrated movement, circuit interventions, shuffled outputs, coupling sensitivity |
| M6 Foraging/homeostasis | Actual tarsal sugar→full graph→feeding assay; removing taste, blocking sweet synaptic output or muting readout stops intake; separate nutrient/water conservation | Odor approach remains a negative result; ingestion abstracts proboscis mechanics |
| M7 Repertoire | Rest/walk/feed; optional neural-gated measured grooming template with contact and mute/withdrawal controls | Natural sensory grooming, visual escape, sleep/circadian state, learning, male cue/song assays |
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

The [conductance extension](conductance-model.md) is now implemented and independently checked. Its 17-condition sensitivity screen preserved voltage bounds but showed strong gain dependence and continued recurrent activity after odor input stopped. Neither bounded voltage nor that persistence demonstrates validated behavior or memory. The fixed exponential reference remains the default for this optional backend; a recorded Padé option and matched-event timestep comparisons expose the speed/accuracy tradeoff.

The [taste contact assay](../validation/taste-contact/results.json) ran 0.5 s with odor disabled and actual feet on food. Sweet input produced 0.009432 normalized intake units. No taste input, motor-readout mute, and blocked sweet-sensor outgoing synapses each produced zero intake; the blocked sensory cells still fired. This tests a neural feeding interface with abstract tarsal ingestion, not mouth/pump mechanics.

The [wind dataset](wind-calibration.md) was downloaded by the user, checksum-verified and selectively extracted. All 17 paired female antennal response means are retained, with derived fits and leave-one-fly-out error. [Airflow geometry](airflow-geometry.md) uses actual antenna velocities and a retained head-geometry frame; it detects out-of-domain empirical estimates. A MuJoCo-fused head-body lookup was caught and corrected before the reference assay; antenna body IDs used by existing odor sensing were valid. Wind-to-neural transduction remains uncalibrated, with important [cell-identity, nonspiking and peptide-signaling limits](wind-neural-mapping.md).

A [broad ORN recruitment diagnostic](odor-recruitment.md) also failed to restore reliable motor readouts. The [held-out DN decoder test](dn-decodability.md) failed sensory-contrast generalization. Neither result was used to install a steering policy. The independent [slow navigation-circuit reproduction](navigation-memory-model-audit.md) matches a pinned author's model at two parameter points, but is not integrated as validated MaleCNS memory.

An [executed multisensory motor probe](../validation/multisensory-smoke.json) includes actual compound-eye samples and leg-velocity-driven club input. Eye-image brightness responds to illumination changes, and reset restores the initial samples. Zero lighting leaves the renderer's fixed background radiance; it is not total darkness. The viewer reports elapsed simulation/wall time including rendering and pacing and labels both the assay and currently unmapped visual pathway.

The [full-graph grooming assay](grooming-loop.md) completes one measured traversal under direct left-DN stimulation, with 0.408 s of physical antennal contact and 2.151° joint tracking RMS. No-input and motor-mute controls produce no playback or contact; withdrawal cancels playback and tonic input does not loop it. The female-derived trajectory, rigid antennae, engineering motor adapter and unphysiological Shiu dynamics remain explicit limitations.

The [free-running data audit](freewalking-data-alignment.md) discovered that native 800 Hz poses and stored interpolated velocities share array lengths but refer to different times. Independent reconstruction confirms the mismatch in all 372 bouts. Per-fly sex and exact absolute source-frame origins are not resolved. Aligned derivatives and mixed-sex labels are required before this dataset can support motor calibration.

Latest complete suite: **107 tests passed, 26 subtests passed**, with 22 Brian2 dependency deprecation warnings. Further experimental modules remain subject to their own validation.

## Compute and next gates

Active neural-only benchmarks took about 2.4–3.5 wall seconds per simulated second; full-loop checks about 5.9–7.6, excluding graph construction and renderer setup. Current RAM is sufficient. More CPU capacity can help parameter/seed sweeps. A GPU does not automatically accelerate the present Numba CPU implementation; hardware recommendations should follow a measured accelerated backend.

Next: calibrate wind sensing from measured antennal mechanics, audit its exact male sensory pathways, and evaluate combined wind/odor input. The optional bounded-conductance model, leg-specific sweet input, compound-eye sampling and club movement proxy now exist; receptor calibration, graded visual transmission and a reliable sensory-to-motor transformation remain unresolved. Expand grooming and internal-state mechanisms with independent published assays while preserving these limits. The paired-animal stage remains deferred.
