# Full-graph FlyBody loop assay

**All four full-graph trials completed, and all declared engineering/mechanism gates passed.** The [frozen plan](../validation/flybody-loop/plan.json), [results](../validation/flybody-loop/results.json), [descriptive summaries](../validation/flybody-loop/summary.json), and [archival receipt](../validation/flybody-loop/archival.json) preserve the evidence. The [independent review](flybody-loop-independent-review.md) reconstructed all 2,500 saved coupling intervals without running another simulation. This is an engineering mechanism assay of the optional body, with no parameter tuning or required biological trajectory.

## Declared experiment

The experiment uses the complete retained MaleCNS graph, unchanged Shiu parameters, seed 11, a 0.1 ms neural step, a 0.2 ms source physics step and **2 ms coupling**. The source pretrained policy and neutral-zero posture hold remain unchanged. The existing odor, named tarsal sweet and FeCO club encoders remain active with their existing explicit gains; there is no visual input or new motor law.

| Condition | Duration | Neural assay | Food region | Outgoing intervention |
|---|---:|---|---|---|
| Locomotor feedback | 2 s | Direct DNg97 40 Hz probe | Center (6,10) mm, radius 3 mm | None |
| Locomotor sensory block | 2 s | Same direct probe | Same | Odor, sweet and club source outputs blocked |
| On-food feedback | 0.5 s | Sensory, no direct DN probe | Center (0,0) mm, radius 3 mm | None |
| On-food sweet block | 0.5 s | Same sensory assay | Same | Sweet-source outputs blocked |

Both locomotor conditions mute the motor readout before tick 300 (0.6 s) and restore it before tick 600 (1.2 s). During that interval the brain and imposed probe remain active, while the body receives its tested engineering neutral posture hold. Rest/feed retain posture actuation; this is not a force-free body. No gait result is assumed after the readout is restored.

The off-path food placement is a pre-plan choice to reduce contact-triggered feeding preemption in the locomotor test. Actual contacts and any sweet events are still recorded, including a zero result. The separate on-food pair exercises the physical tarsal region interface. Odor and club inputs remain active there, so it is **not a taste-only experiment**. Positive ingestion, MN9 changes or locomotion are reported endpoints, not conditions forced by changing gains or control priority.

## Observed results

The complete 166,700-neuron, 25,582,938-edge graph controls the optional body while native contacts, antenna odor samples and tibia velocities return to its existing sensory encoders. The locomotor pair stops during the motor-readout mute and moves again after restoration; those are observed outcomes, not fitted success conditions. Both trials have zero positive sweet input and zero ingestion because no tarsal contact enters the off-path food region.

| Condition | Planar path, mm | Steady muted speed, mm/s | After-restoration speed, mm/s | Full-graph spikes | MN9 spikes | Food ingested, normalized |
|---|---:|---:|---:|---:|---:|---:|
| Locomotor feedback | 17.1923 | 0.002289 | 11.6558 | 1,709,316 | 120 | 0 |
| Locomotor sensory block | 17.3614 | 0.008187 | 13.3849 | 1,648,677 | 104 | 0 |
| On-food feedback | 0.007407 | — | — | 421,545 | 28 | 0.03744 |
| On-food sweet block | 0.007407 | — | — | 426,321 | 28 | 0.03744 |

Path and speeds use unsmoothed planar free-joint-position chords at 2 ms intervals. Steady mute is the median over intervals starting at 0.850–1.198 s and ending at 0.852–1.200 s (`speed[425:600]`, 175 intervals). After restoration uses intervals starting at 1.500–1.998 s and ending at 1.502–2.000 s (`speed[750:1000]`, 250 intervals). These chord speeds differ from the native inertial-center velocity used by physiology. The locomotor feedback and block conditions retain 524,219 and 526,843 neural spikes during the full 0.6–1.2 s mute.

Both pairs first differ in non-sensory spike events at zero-based tick 4, the **8–10 ms neural interval**, while the complete ordered input history and before/after RNG states still match. The locomotor input arrays first diverge at tick 21, the 42–44 ms interval, after the closed loops begin to evolve differently. On-food ordered inputs remain identical through all 250 intervals. This supports transmission of the blocked afferent inputs through the graph; the locomotor intervention combines odor and club sources, so it cannot identify their individual contributions.

**Sweet-output blocking does not change the on-food MN9 total or abstract intake in these trials.** Both conditions request feed for 234 of 250 intervals, first at the interval ending 34 ms; each has 28 MN9 spikes and 0.03744 normalized food intake. Their saved physical trajectories and final images agree. Downstream spike events and overall graph activity differ, so the negative feeding endpoint is not absence of a neural intervention. The experiment does not establish sweet-source necessity, sufficiency, or swallowing. Odor and club inputs are still present.

All retained native arrays are finite, all native warning counters are zero, and all four workers exit cleanly. Maximum neural/body/native clock discrepancy is 1.88×10⁻¹³ s; maximum independently recomputed normalized resource residual is 7.78×10⁻¹⁵. Minimum upright-axis z is 0.972744. These short floor trials do not test obstacle collisions, recovery from falls or sustained behavior. The minimum Shiu voltage is **−516.13 mV** in the locomotor feedback condition, an unresolved physiological failure despite finite arithmetic.

Measured loop wall times are 18.96 and 19.62 s for the two 2 s locomotor trials and 4.83 and 4.99 s for the two 0.5 s on-food trials. Timing starts after construction/reset/initial rendering and stops before final rendering/cleanup; it includes flushed journaling. This is an approximately 0.1× real-time instrumented run, not an isolated performance benchmark.

Eight endpoint frames are saved in [the frame directory](../validation/flybody-loop/frames). The five unique images were visually inspected: the fly remains visible on the floor, the food/water regions render in the intended locations, and the locomotor endpoints move away from the initial position. Initial images match within each pair and the on-food final images match exactly. Still frames are presentation evidence; sampled native state supports the motion/contact measurements.

## Measurements and failure retention

Passive wrappers call each real encoder and `brain.advance` exactly once. The journal retains the actual encoder observations and complete ordered `SparseDrive` indices, neuron IDs, rates, current/weight defaults and refractory declarations. No zero-rate ORNs are dropped or input arrays reordered. Neural records include RNG states, all-neuron counts, ordered ID/spike-time hashes, source/motor counts and hashes, full-batch spike totals, voltage range and finite-state checks.

Each completed coupling tick retains cached native time, `qpos`, `qvel`, `qacc`, activation, controls, canonical/native actions, source contact records, actual antenna positions and tibia velocities. Evaluator checks confirm source action order and scaling, the frozen left/right-to-speed/yaw map, exact neutral hold, native-to-public tibia velocity, SI odor sampling at the actual antenna origins, and tarsal floor-contact membership in the configured material regions. These privileged arrays and world coordinates do not enter the neural encoders or motor map.

Native contacts are the worker's detached-forward diagnostics. The physiology/encoder interface samples them every 2 ms, not every 0.2 ms physics substep. Native acceleration and actuator force retain their source integration-stage semantics; the assay does not infer physiological forces from them. Resource conservation is checked in normalized engineering units.

Every encoder call, neural start, neural completion and physical completion is appended and flushed immediately to a condition JSONL journal. A source failure preserves its returned final native cache, the latest completed neural interval, request and traceback before cleanup. Partial trials stay in the results. The worker is closed/reaped even after failure; there is no fallback body, automatic reset, gain adjustment or discarded trial.

Before each trial, a same-seed reset must reproduce the initial native state. An initial render and `advance(0)` must leave native and neural state unchanged. The run is bounded by the source's explicit 2 s horizon; this does not validate an indefinitely running viewer.

## Interpretation

The source-output intervention blocks transmission at synaptic delivery while leaving the actual sensory encoders and imposed probe in place. It can change downstream activity, body movement and therefore later sensory inputs. **The two closed loops are not required to retain identical afferent input or spikes throughout.** The comparison identifies the first ordered-input difference and the first downstream spike-event difference. A downstream difference during the still-identical input/RNG-history prefix supports transmission of the physical sensory feedback through the graph. Later comparisons carry the changed-feedback caveat.

Condition checks concern completion, synchronized clocks, finite state, warning counters, resource conservation, exact delivered inputs/controls, motor mute and cleanup. The locomotor pair also has an explicit graph-transmission evidence criterion. Its absence would leave that causal observation unresolved even if interface plumbing passes. Intake remains a separate scalar abstraction; this assay cannot establish swallowing, natural food seeking, a male body's biomechanics, endogenous stance control or biological rates.

The current-based transfer's implausible hyperpolarization remains a model limitation. The body is female-derived, and its learned motor policy and fixed hold are engineering surrogates. Four selected short trials cannot establish behavioral realism or broad mechanical robustness.

The following commands created and ran the immutable plan:

```sh
.venv/bin/python scripts/check_flybody_loop.py --plan --config configs/male-flybody-probe.json
.venv/bin/python scripts/check_flybody_loop.py --run
```

The saved plan and source hashes are immutable. Raw journals and deterministic gzip copies are retained under ignored runs, with their exact original/archive paths and hashes in the archival receipt. Do not rerun the plan-creation command over the existing record.

Runtime source is frozen at commit `928e062`; the plan SHA-256 is `6ab6b5f8bbcb4cc3343e97824c182e4c30e9d5d1902d21804cf56eb25f16d403`. The review found one documentation-only discrepancy: the declared hash of `docs/flybody-integration-plan.md` differs from that committed revision. All declared runtime/configuration/data-receipt source hashes match. The review records both document hashes rather than rewriting the frozen plan; see its provenance qualification before reproducing the experiment.

Completed raw directories were relocated without changing their contents by:

```sh
.venv/bin/python scripts/archive_flybody_loop.py
```

That one-shot archiver also preserved the original results, generated deterministic gzip copies, copied endpoint images and calculated the descriptive summaries. Its receipt maps the historical `validation/flybody-loop/<condition>` paths to `runs/flybody-loop-6ab6b5f8bbcb/<condition>`. The raw journals and ignored original results are available locally; the repository retains plans, results, summaries, frames and integrity receipts, so a fresh clone needs those raw artifacts to repeat the saved-journal review. Both plan creation and archival reject overwriting an existing record. The repeatable read-only evidence check is:

```sh
.venv/bin/python scripts/review_flybody_loop.py
```

The initial live viewer reached the two-second limit with synchronized clocks but treated the planned boundary as a worker error, disabling Reset. That [UI lifecycle defect](../validation/flybody-loop/viewer-initial-limit.json) is retained separately; the subsequent [viewer lifecycle fix](../validation/flybody-viewer/inspection.json) now pauses at the limit and preserves working Reset/camera controls, without changing these physical/neural trials.
