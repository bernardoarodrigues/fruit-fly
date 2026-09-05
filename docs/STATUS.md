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
| M10 Robustness/performance | Focused tests, exact replay, active full-graph benchmark, three 10-second full-loop runs | Held-out/perturbed behavior; locomotor restart isolated from feeding; wall contacts; voltage plausibility |

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

The subsequent [feeding-motor audit](feeding-motor-expansion.md) records all 48 annotated proboscis motor cells plus two Fdg candidates. The existing taste assay recruits only part of the oral program. A presumed equality of afferents under motor muting failed because movement changes foot contacts; the failed result is retained. Recorded-input replay reproduces both baselines exactly and isolates a candidate Fdg contribution to MN9 recruitment. No swallowing or new intake model is claimed.

The [wind dataset](wind-calibration.md) was downloaded by the user, checksum-verified and selectively extracted. All 17 paired female antennal response means are retained, with derived fits and leave-one-fly-out error. [Airflow geometry](airflow-geometry.md) uses actual antenna velocities and a retained head-geometry frame; it detects out-of-domain empirical estimates. A MuJoCo-fused head-body lookup was caught and corrected before the reference assay; antenna body IDs used by existing odor sensing were valid. Wind-to-neural transduction remains uncalibrated, with important [cell-identity, nonspiking and peptide-signaling limits](wind-neural-mapping.md).

A [broad ORN recruitment diagnostic](odor-recruitment.md) also failed to restore reliable motor readouts. The [held-out DN decoder test](dn-decodability.md) failed sensory-contrast generalization. Neither result was used to install a steering policy. The independent [slow navigation-circuit reproduction](navigation-memory-model-audit.md) matches a pinned author's model at two parameter points, but is not integrated as validated MaleCNS memory.

An [executed multisensory motor probe](../validation/multisensory-smoke.json) includes actual compound-eye samples and leg-velocity-driven club input. Eye-image brightness responds to illumination changes, and reset restores the initial samples. Zero lighting leaves the renderer's fixed background radiance; it is not total darkness. The viewer reports elapsed simulation/wall time including rendering and pacing and labels both the assay and currently unmapped visual pathway.

The [full-graph grooming assay](grooming-loop.md) completes one measured traversal under direct left-DN stimulation, with 0.408 s of physical antennal contact and 2.151° joint tracking RMS. No-input and motor-mute controls produce no playback or contact; withdrawal cancels playback and tonic input does not loop it. The female-derived trajectory, rigid antennae, engineering motor adapter and unphysiological Shiu dynamics remain explicit limitations.

The subsequent [JO-F sensory activation assay](grooming-sensory-loop.md) reaches the same body interface without direct DN stimulation. All 18 two-seed checks pass. Sensory-output blocking preserves the exact stimulated source spike trains and eliminates all downstream spikes and playback. Both sides' grooming DNs respond, and the inputs are imposed events with an uncertain crosswalk to experimental drivers. This is a causal model demonstration, not calibrated natural touch or side-selective grooming.

The [free-running data audit](freewalking-data-alignment.md) discovered that native 800 Hz poses and stored interpolated velocities share array lengths but refer to different times. Independent reconstruction confirms the mismatch in all 372 bouts. Per-fly sex and exact absolute source-frame origins are not resolved. Aligned derivatives and mixed-sex labels are required before this dataset can support motor calibration.

The [mixed graded/spiking backend](graded-model.md) now supports exact nonspiking cell populations without removing their graph edges. Independent equation/delay/checkpoint checks and a full-graph 16-candidate APN2 smoke assay pass. Release parameters remain explicit hypotheses; no wind physiology fit or body/viewer integration is claimed.

The [walking benchmark](freewalking-benchmark.md) now derives aligned kinematics from 372 bouts and compares the actual physical controller and neural motor probe. It identifies fixed cadence, undersized excursions and reversing body yaw as separate calibration targets, while preserving the source's mixed-sex and curated-running limits. The subsequent [20-trial CPG experiment](cpg-calibration-experiment.md) reduced excursion error but failed its combined speed/yaw promotion gates. No candidate changed the runtime defaults.

The [visual-column audit](visual-input-mapping.md) found released downstream column labels and tentative connectivity-based R1–R6 assignments, with incomplete and unequal eye coverage. [Camera ray footprints](retina-ray-calibration.md) now reproduce the actual pixel pipeline and pass fourteen independently rendered geometric checks. Camera-to-anatomy registration and graded phototransduction remain unresolved; no visual neural adapter was installed. The [wind transduction review](wind-transduction-boundary.md) likewise separates measured deflections/voltages from the unidentified peripheral rate and release laws.

An isolated [PER/TIM oscillator reproduction](circadian-lg1998.md) matches the published 24.135-hour model period and entrains under its specified light/dark forcing. [Independent equation and numerical review](circadian-independent-review.md) agrees. Biological-hour units and tentative concentration units are explicit. It is not coupled to the fly's neural/physical clock, light sensor, or sleep.

The released [FlyBody walking policy](flybody-inference-trial.md) loads in a separately pinned Apple Silicon CPU environment with verified observation/action dimensions and an independently checked mean network. Its [fixed six-condition comparison](flybody-motor-comparison.md) reduces straight reversing yaw by 75–83% and follows both commanded turns, but fails the declared zero-command and withdrawal speed gates. Repeated seeds produce identical physics, and aggregate joint-ROM error does not improve. This is a comparison of complete motor/body stacks. No runtime replacement is promoted.

The [anatomical visual audit](visual-retinotopy-feasibility.md) exactly joins 13,267 released right-side visual cells to the retained male graph and extracts 852 geometric optical directions from a female micro-CT template. Their male registration remains unresolved. The [camera-coverage study](visual-template-coverage.md) finds 69 template axes outside the current right camera and another 79 inside its aperture but absent from the pixel resampling. No nearest-facet substitution or visual neural drive was installed.

The isolated [six-view sampler](multiview-eye.md) now acquires all 852 axes from the actual moving eye origin/head frame, with 38 geometric target checks and a world-light/RGB seam control. Its four-pixel interpolation is a numerical point-query approximation, not an ommatidial acceptance kernel. The existing arena has no world lamps, so disabling camera-attached illumination leaves its non-emissive surfaces dark; that result is recorded explicitly. No visual neural mapping or default camera change is installed.

The [FlyMimic muscle audit](musculoskeletal-feasibility.md) compiles the source-native 15-MTU left-foreleg model and verifies its mechanical responses. Its fast activation time constants produce numerical overshoot at the source Euler timestep. Force units and exact male motor-unit identities remain unresolved; this does not replace the six-leg body. An [independent feeding review](feeding-independent-review.md) verifies the stored identities, input histories and four neural-only replays, preserving the original failed feedback-equality control.

An isolated [proboscis geometry audit](proboscis-mechanics.md) verifies source mesh transforms and a two-pitch diagnostic Jacobian. The source has no NeuroMechFly oral-motion limits, extension trajectory or identified mouth aperture; generic hinge defaults and an arbitrary distal mesh vertex cannot supply them. No physical swallowing claim or runtime oral controller was added.

Latest complete suite: **168 tests passed, 37 subtests passed**, with 22 Brian2 dependency deprecation warnings. Further experimental modules remain subject to their own validation.

The [ten-second loop experiment](extended-loop.md) completes three full-graph conditions with finite, upright bodies and conserved resources. It retains one failed gate: after releasing motor mute, the fly requests feeding at the food patch rather than locomotion. Its [47-check independent review](extended-loop-independent-review.md) confirms that outcome and the actual mute release. No sampled wall interactions occur, and the current-based voltage failure remains. This is bounded engineering robustness evidence, not a completed natural-behavior milestone.

The [fixed posture-hold experiment](flybody-stance-experiment.md) now passes stopping and restart with source-native measured-length and neutral-zero position targets plus maximum adhesion. The last-commanded-target candidate fails on resumption, and the original policy still fails its stopping criterion. An [independent review](flybody-stance-independent-review.md) reconstructs all twelve traces, actuator transmissions and filters. This supports a bounded optional engineering adapter; it does not resolve the measured gait mismatch or establish neural stance control.

[Optional world illumination](world-illumination.md) adds a fixed scene lamp without changing sampled physical states at 21 times across 1,000 steps. Thirteen diagnostic checks and the live viewer light/reset inspection pass. The former unilluminated multiview result remains the record for the legacy configuration; visual-to-neural mapping remains open.

The [DoOR odor audit](door-odor-audit.md) now records chemical identities, missing and signed baseline-relative consensus evidence, selected source-study values, and candidate joins to all 2,635 named male ORNs. Updated olfactory identity data expose ambiguities and one palpal-label/nerve conflict. No dimensionless score is used as a firing rate, no missing response is filled with zero, and no new odor-driven behavior is claimed.

The [optional native FlyBody bridge](flybody-bridge.md) reproduces two original 2 s motor traces exactly. Four [actual full-graph trials](flybody-loop.md) complete with synchronized clocks, finite states and conserved resources. Their [independent journal review](flybody-loop-independent-review.md) checks all 2,500 ticks. Sensory-output blocking changes downstream activity under initially identical input, but blocking sweet output in the on-food pair leaves MN9 counts and intake unchanged. One frozen pre-run documentation digest is unrecovered; runtime, configuration and data-receipt hashes match the recorded source revision. The optional viewer now pauses normally at 2 s with working Reset and camera controls. Longer rolling-reference operation remains a separate experiment.

The [primary Or42a audit](or42a-primary-assay.md) distinguishes a measured male spontaneous rate from baseline-subtracted odor responses and separately identifies all 36 male VM7d sensory cells. Exact original DoOR offset preprocessing remains unresolved. Any proposed numerical rate replay must distinguish imposed excitation events from actual source spikes and must not treat liquid dilution as airborne concentration.

## Compute and next gates

Active neural-only benchmarks took about 2.4–3.5 wall seconds per simulated second; full-loop checks about 5.9–7.6, excluding graph construction and renderer setup. Current RAM is sufficient. More CPU capacity can help parameter/seed sweeps. A GPU does not automatically accelerate the present Numba CPU implementation; hardware recommendations should follow a measured accelerated backend.

Next: verify rolling-reference FlyBody operation beyond the source recording horizon, then repeat full-neural controls over longer intervals. In parallel, quantify how measured olfactory response summaries relate to actual simulated afferent spikes and continue wind transduction and male visual-registration work. The optional bounded-conductance model, leg-specific sweet input, compound-eye sampling and club movement proxy now exist; receptor calibration, graded visual transmission and a reliable sensory-to-motor transformation remain unresolved. Expand grooming and internal-state mechanisms with independent published assays while preserving these limits. The paired-animal stage remains deferred.
