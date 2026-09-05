# Full-graph FlyBody loop assay

**All four full-graph trials completed, and the producer reports all declared gates passing.** The [frozen plan](../validation/flybody-loop/plan.json), [results](../validation/flybody-loop/results.json), [descriptive summaries](../validation/flybody-loop/summary.json), and [archival receipt](../validation/flybody-loop/archival.json) preserve the evidence. An independent saved-data review is in progress. This is an engineering mechanism assay of the optional body, with no parameter tuning or required biological trajectory.

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

The initial live viewer reached the two-second limit with synchronized clocks but treated the planned boundary as a worker error, disabling Reset. That [UI lifecycle defect](../validation/flybody-loop/viewer-initial-limit.json) is retained separately; a subsequent viewer fix will pause at the limit without changing these physical/neural trials.
