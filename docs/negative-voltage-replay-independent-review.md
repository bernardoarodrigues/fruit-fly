# Independent review of the negative-voltage replay

The saved two-cell reconstruction passes **381 independent checks**. Every one of **720,000 target-state transitions** has bitwise agreement for both voltage and synaptic state with the pinned update rule evaluated from the preceding saved state. All six pairs of final voltage/synaptic values match the original full-network checkpoints bit-for-bit. Recorded target spike stamps, last-spike ticks, and each relevant pending-ring slot also match exactly. No numerical inconsistency was found within this frozen scope.

The [review script](../scripts/review_negative_voltage_replay.py) reads the original recordings and saved replay arrays. It neither imports nor executes the producer, neural simulator, learned policy, or physics. It does not run a free-running two-cell recurrence: each transition check starts from that transition's preceding saved state. The [machine-readable receipt](../validation/negative-voltage-replay-independent-review.json) preserves the checks, source hashes, counts, numerical differences, and limitations.

The reviewed [producer plan](../validation/negative-voltage-replay-plan.json) has SHA-256 `5e474e043a4c302a4694ac7b0e87db0bfce6f9de1d4a4213ae484e27399914a1`. Its 31 pinned inputs match, including the executed producer, neural/data source, original full-loop plan/results/review, graph files, and three original recordings/checkpoints. The ten result-listed artifacts and plot-receipt hashes also match. No historical Git fallback was needed: all pinned inputs still matched their working-tree files. The source baseline recorded by the plan is `97dc2a65d3b43e7d0039d5e97dff26b0e253e0ad`.

The complete incoming-edge join was reconstructed from the outgoing CSR graph. It contains 2,260 edges / 27,830 contacts for 67052 (`lLN2T_b`) and 435 edges / 7,247 contacts for 13314 (`M_vPNml50`). Each source-target pair is unique, which validates the producer's one-edge-per-pair lookup. All inventory columns match the graph and annotations, including silent sources, untyped labels, 53 zero-weight edges, source transmitter signs, contact counts, float32 weight bytes, and the retained `contacts × float32(0.275) × sign` rule. A target's own transmitter annotation does not determine its incoming signs.

All **31,489,162 original ordered spikes** were read through valid gzip endings and checked against uncompressed hashes, block hashes, framing, graph IDs, ordering, 0.1 ms stamps, and 2 ms block clocks. Of these, 3,481,508 events came from sources with an incoming edge to at least one selected target. A source can connect to both targets, producing the larger delivery count below.

| Condition | Potential target deliveries | Accepted | Source blocked | Target unavailable | Beyond 12 s |
|---|---:|---:|---:|---:|---:|
| Locomotor feedback | 1,225,720 | 1,225,512 | 0 | 8 | 200 |
| Sensory outputs blocked | 1,213,516 | 1,208,502 | 4,850 | 0 | 164 |
| Sensory only | 1,232,018 | 1,231,820 | 0 | 6 | 192 |
| Total | **3,671,254** | **3,665,834** | **4,850** | **14** | **556** |

Every original event is classified exactly once for each connected target edge. The review reconstructs the accepted delivery stream in original source order, including the 18-tick delay, and matches the saved accepted tick/edge-row arrays exactly. Events awaiting delivery at the endpoint remain pending regardless of their source's block status. The pending check compares relevant presynaptic identities separately within all 19 ring slots; it does not duplicate a source that connects to both targets.

All 18,000 actual input lists exclude both selected targets, even as zero-rate members. Their recorded current is null and the final checkpoint contains zero target current and 22-tick refractory intervals. The blocked condition declares 296 sensory source cells; recorded counts and all-sensory flags agree throughout, and the final complete mask matches. Motor readout muting is separate from this source-output mask.

Source inspection confirms the pinned Shiu-style kernel's ordering: integrate available voltage and decay synaptic state, test strict `v > −45`, make newly fired targets unavailable, deliver delayed unblocked source events, then reset both states on a spike. Both states freeze during the refractory interval. The reviewer derives availability from original recorded target spike stamps and verifies that the threshold calculation from saved preceding states predicts those exact stamps. It then adds accepted weights to the saved preceding synaptic state in event order and checks every resulting state bit-for-bit. Thus observed spikes are used to audit eligibility, while independently checked threshold decisions establish consistency with them.

Cell 67052 never spikes. Cell 13314 spikes at tick 140 (14.0 ms) in feedback and tick 117 (11.7 ms) in sensory-only; it does not spike in the blocked condition. Its eight and six unavailable deliveries respectively are retained, not silently accepted. All per-tick signed increments, per-edge counts, cumulative sums, last-100-ms / last-second windows, source-type aggregates, top-ten ordering, and result cell-summary fields match. The reported inhibitory magnitude shares of 83.17% and 92.93% in sensory-only also match their saved type/edge tables.

Endpoint attribution was checked with the discrete impulse response, independently of the producer's continuous-exponential expression. Let `a = exp(−0.1/20)`, `b = exp(−0.1/5)`, `c = (5/15)(a−b)`, and `n = 119999−delivery_tick`. An accepted post-reset jump contributes `w bⁿ` to final synaptic state and `w c(aⁿ−bⁿ)/(a−b)` to final voltage minus rest. Summing these powers by edge and target differs from the saved contributions or final states by at most **9.6634×10⁻¹³ model mV**, below the frozen 10⁻⁹ tolerance. No accepted event falls within the final refractory interval; events before the last reset are excluded. This is conditional accounting under fixed acceptance and source history, not the effect of silencing a source.

The [producer report](negative-voltage-replay.md) and [plot](../validation/negative-voltage-replay-voltages.png) were inspected. The plot has readable axes, condition labels, model units, and an explicit absence of physiological calibration. Its source reads saved arrays only. The lowest reconstructed value, **−536.7385192 model mV**, occurs for 67052 at the 4,444.9 ms state sample in feedback. This 0.1 ms target reconstruction is distinct from the original full-network minimum **−532.5811 mV**, which was retained only at 2 ms sampling intervals.

The original full-network recordings do not contain interior per-target voltage/synaptic arrays at every 0.1 ms step. Interior agreement here is with the pinned equations and saved reconstruction; direct original-state comparison is possible at the endpoint. Likewise, the original initial journal corroborates uniform resting voltage and no spikes but does not serialize a full initial synaptic array: zero synaptic state and reset bookkeeping are established by the pinned reset source. Per-interval full source masks were not serialized; their membership is grounded in the fixed design/runtime, recorded aggregate flags/counts, and final full checkpoint.

Recorded self/cross target source spikes remain external replay inputs. No recurrent source generation or perturbation response was recomputed. Cumulative signed jumps are effective synaptic-state increments, not instantaneous voltage, electrical charge, or conductance. The pinned signed-state equations have no inhibitory reversal potential, so their numerical consistency does not validate the extreme negative voltages as electrophysiology or identify a justified gain adjustment. There was no fitting, parameter change, or full-network/body rerun.

To reproduce this saved-data review in a checkout without its generated review receipt:

```sh
.venv/bin/python scripts/review_negative_voltage_replay.py
```

The script refuses to overwrite an existing review receipt. The original producer's 58 passing checks are retained separately from these 381 independent checks.
