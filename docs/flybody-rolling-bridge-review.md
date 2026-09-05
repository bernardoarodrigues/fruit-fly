# Independent review of the rolling FlyBody bridge journals

The three completed body/RPC trials preserve their saved standalone references exactly. **138 case checks pass across 8,003 recorded samples and 8,000 control intervals**, including the 12-second rolling stop/resume trial. This review imports no runtime code and executes no simulation.

The reviewer authored the earlier standalone rolling task and reference experiment, but did not author the new runtime integration or its primary comparison checker. This is an independent review of the bridge integration against those references, not an independent biological replication. The standalone references previously received a separate [independent review](flybody-persistent-independent-review.md).

Evidence is saved in [the review script](../scripts/review_flybody_rolling_bridge.py) and [review receipt](../validation/flybody-rolling-bridge/independent-review.json). The [bridge plan](../validation/flybody-rolling-bridge/plan.json) SHA256 is `22ac32806f690bf7f6f864023470574bff321d212233e1164484e5ed55174604`. The reviewer verifies that plan's current source hashes, reference NPZ hashes, result identity, and actual journal hashes before assessing samples.

| Trial | Recorded samples | Control intervals | Last native time | Maximum reported resource residual |
|---|---:|---:|---:|---:|
| Bounded 2-second parity | 1,001 | 1,000 | approximately 2 s | 1.9984e−15 |
| Rolling 2-second parity | 1,001 | 1,000 | approximately 2 s | 1.9984e−15 |
| Rolling stop/resume | 6,001 | 6,000 | approximately 12 s | 3.3307e−15 |

## Actual actor input and physical parity

The standalone NPZ files retain all 741 float32 actor-input values per sample. The bridge worker hashes the actual float32 observation arrays before placing those same arrays into the TensorFlow input dictionary. The reviewer reconstructs SHA256 from every saved reference row using explicit little-endian float32 bytes. All **5,930,223 reference values** are covered by matching per-sample bridge digests, including the three reset-time evaluations. Metadata retains the same 12 observation keys in the same order and the same dimensions, with 65×3 displacement and 65×4 quaternion reference observations.

The journals retain the bridge's digest, not a second copy of its raw actor arrays. Thus the evidence is equality of cryptographic digests computed at the inspected boundary, rather than direct comparison of two independently stored input arrays. Full reference buffers are likewise not transmitted. Per-tick buffer shapes and origins are directly checked; the 65 rows used by the actor are covered by the matching actor digest and saved standalone input.

The reviewer compares the serialized bridge `qpos`, `qvel`, `qacc`, activations, controls, native and mean actions, continuously integrated target, native time, root pose, linear/angular velocity, and upright z component against the saved reference. It restores each reference dtype and compares IEEE bytes, preserving distinctions such as the sign of zero. Every comparison passes.

Every sample also preserves action names and actuator IDs. Command gates match the reference schedules; on commands remain 20 mm/s with zero yaw. Each target advances by exactly 0.004 cm per enabled 2 ms interval and stays fixed while resting. No target recentering or native-time reset appears between sample 0 and the trial endpoint.

## Clocks, buffers, forces, and resources

Bounded samples report 1,100×7 pose and 1,100×6 velocity reference arrays. Rolling samples report 66×7 and 66×6. Source control counters match recorded tick numbers at every interval. Rolling buffer origin is zero at reset and `tick−1` after each completed step, matching the source's post-step observation update. Bounded mode reports no rolling origin.

Native time agrees with tick×2 ms within **8.033e−12 s** at worst. Metadata preserves the 0.2 ms native physics clock, 2 ms control/physiology clock, and source gravity of −981 cm/s². The host's `time_s` accessor reads native time; this is not a comparison between independently maintained host and physics clocks. No neural simulation or brain/body timing claim follows from this body/RPC experiment.

Native arrays are finite, source termination flags remain false, and all MuJoCo warning counters are zero. Unlike the standalone reference NPZ, bridge journals retain all 59 native actuator forces from the preceding force stage and refreshed world-space leg/floor contact forces. The reviewer checks **588,775 individual force values** for finiteness. It independently reconstructs each leg's summed absolute vertical support and world ground-force vector from **38,866 contact rows**, including the native-dyne to `g mm/s²` factor of ten. Those aggregate values match exactly.

This establishes current-journal force finiteness and internal aggregation. It does not establish force parity with the standalone reference, whose raw forces were not saved. Native actuator forces and refreshed contact forces represent different calculation stages; they are not treated as a same-stage external force-balance experiment.

The resource patches retain their initial inventories in every sample. The schedules contain walking/resting, with no feed commands. Every recorded nutrient/water balance residual is finite and below the declared 1e−8 threshold, and the reviewer recomputes the reported maxima exactly. However, the journal does not store the complete energy, hydration, crop, spent-energy, and lost-water ledgers. The reviewer can verify patch inventories and the recorded residuals but cannot independently reconstruct the full conservation equation from all actual stored components. These resources use uncalibrated normalized engineering units.

## Render, reset, and failure evidence

Each successful journal has exactly one initial event, its expected sequence of samples, and one explicit reset event. The reset's complete native state equals the initial native state, including actor digest, reference metadata, and zero native clock. This reset occurs after the trial endpoint, not as a persistence mechanism within the trajectory.

The primary checker calls zero-duration advance and three camera renders before recording the initial event and asserts exact native state equality. It saves no camera image or per-render before/after record. The completed, source-hashed checker therefore provides evidence that those assertions executed; this review does not independently establish rendered image quality. Host physiology after reset is not separately journaled.

The bounded overrun test is also implemented as a primary checker assertion: an additional advance must raise `RuntimeError` and leave native state unchanged. Its exception is not retained as a separate journal event. Source inspection confirms the explicit 2-second bounded guard; this saved-data review adds no new runtime failure injection, and does not convert an unrecorded exception into stronger evidence.

The earlier [initial-checker attempt](../validation/flybody-rolling-bridge-initial-checker/results.json) remains an operational failure. Its first two trials passed. During the third trial, a manual interrupt arrived while the checker repeatedly decompressed an immutable NPZ array. The retained exception is `KeyboardInterrupt`, with `_decompressor.decompress` in the traceback. There are **2,179 recorded samples but only 2,178 completed comparisons**: a sample is journaled before its checks finish. The last recorded tick is 2,178 at native time `4.356000000000344` seconds; its raw native state is finite, has no warning, and is not source-terminated. This was not a physical guard failure.

The amended checker loads each immutable reference array once, preserves commands and gates, and reruns all three trials under a new frozen plan. The completed revised journals support the result stated here; the interrupted case is neither silently counted as complete nor replaced in its original receipt.

## Reproduction

With the existing saved journals and standalone NPZ files present, run:

```sh
.venv/bin/python scripts/review_flybody_rolling_bridge.py
```

This reads the saved artifacts and current source hashes only. It neither imports the native runtime nor starts a worker. Use the revision that freezes this bridge experiment when reproducing after subsequent runtime changes. The passing result establishes the selected body/RPC regression scope; long full-brain feedback, broader command transitions, and browser interaction require their own evidence.
