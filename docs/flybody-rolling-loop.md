# Full-neural rolling FlyBody experiment

Status: root source review and recorder self-tests pass. No rolling full-neural plan has yet been frozen and no trial has been run. This document implements steps 4–5 of [the persistent-runtime plan](flybody-persistent-runtime-plan.md); the completed bridge and its matching independent review are required before freezing or execution.

## Proposed experiment

Run three independent 12 s conditions sequentially, each with seed 11, the full retained MaleCNS graph (166,700 neurons; 25,582,938 edges), unchanged Shiu parameters and 2 ms brain/body coupling. The rolling FlyBody task uses its original 0.2 ms physics step, 2 ms actor step and 66-row reference buffer with 65 actor-visible frames. The body and target are never recentered. The food patch remains at `[6, 10]` mm with radius 3 mm. Current odor, sweet-taste and club proprioception encoders remain enabled.

| Condition | Descending-neuron probe | Sensory outgoing transmission | Motor-readout mute intervals |
| --- | --- | --- | --- |
| `locomotor_feedback` | Existing identified pair, 40 Hz excitation events | Enabled | 0.6–1.2, 3.0–3.6 and 9.0–10.6 s |
| `locomotor_sensory_block` | Same pair and rate | Odor, sweet and club source outgoing edges blocked | Same intervals |
| `sensory_only` | None | Enabled | None |

Intervals are half-open; interventions precede zero-based ticks 300/600, 1,500/1,800 and 4,500/5,300. Motor mute changes the decoder readout to rest/zero and preserves neural execution. Sensory blocking retains the real ordered source lists and source-cell dynamics while blocking source outgoing transmission. Recurrent effects and later physical feedback can change actual source spikes and excitation events; identical requested input is checked only while input histories match. The sensory-only condition is a separately labeled engineering trial, not an on-food reproduction.

No walking distance, resumed movement, feeding or navigation outcome is required. No gain fitting, new sensor calibration, neural modification or post-failure replacement trial is allowed. The native physical guards can stop an attempt before 12 s; the partial result remains evidence.

## Frozen references and comparisons

`scripts/check_flybody_rolling_loop.py --plan` refuses an existing plan or result. It first verifies the completed three-case rolling bridge, raw journal hashes and current direct bridge dependencies. It then checks the proposed configuration equals the original locomotor configuration except for explicit rolling reference selection and a null horizon. The plan records the current source revision, source/data hashes, original plan/archive/result identities, original neural parameters, exact sensory/motor identities and both original locomotor journal hashes. Execution verifies these dependencies again and refuses existing results or a colliding raw run directory. Finished source hashes are checked once more.

The original archived locomotor pair supplies the first 1,000 intervals (2 s) for exact comparisons in both longer locomotor trials. Comparison streams one original interval at a time and checks:

- Each encoder's actual local observation and full ordered drive, including zero-rate members and composition order.
- The combined neural input, generator state before/after execution, source masks, all-neuron and downstream ordered spike hashes, spike/edge counts, monitored groups and voltage summaries.
- Native qpos, qvel, qacc, activation, controls, ordered native/canonical actions, actuator identities, body and target poses, contacts, antenna positions, tibia velocities, command, clock, warnings and termination flags.

Rolling bookkeeping and cached post-step reference tails differ by design and are explicitly excluded. The original archive stores spike hashes rather than raw spike arrays: the new lossless arrays must reproduce those hashes exactly, but an unavailable original array cannot be compared directly. The original archive lacks actor-input arrays; the separate rolling bridge tests actual actor-input equality. The sensory-only condition has no matching original locomotor prefix. Later afferent equality between trajectories is not assumed.

## Lossless artifacts and independent checks

Full records remain under ignored `runs/flybody-rolling-loop-<plan hash prefix>/<condition>/`; tracked `validation/flybody-rolling-loop/results.json` holds compact summaries and receipts. The script reuses the original `Capture`, `physical_summary`, native-state inspection and paired-mechanism helpers without editing them.

`events.jsonl.gz` contains UTF-8 JSON lines in one gzip member, flushed after every event. Every completed neural batch is archived before Capture's analysis. Every returned physical state is journaled as `physical_returned` before evaluator assertions. The journal retains full ordered encoder drives/RNG, neural summaries and complete native diagnostics rather than accumulating 6,000 native arrays in tracked JSON. It records actual interventions, failed stages and cleanup errors. Raw and compressed SHA-256 hashes and byte counts are retained.

`spikes.bin.gz` stores actual ordered neuron IDs and absolute spike times. Its decompressed file begins with eight ASCII bytes `FFSPK001`, a little-endian uint32 JSON-header byte count, and that UTF-8 JSON header. The header records the graph/plan hashes and encoding. Each block contains:

| Field | Encoding |
| --- | --- |
| Zero-based coupling tick | Little-endian uint64 |
| Event count `N` | Little-endian uint64 |
| Neural start and end milliseconds | Two little-endian float64 values |
| All `N` body IDs, in returned order | Little-endian signed int64 array |
| All `N` absolute spike times, in the same order | Little-endian float64 array |

Each block header is 32 bytes; each event contributes 16 payload bytes. IDs/times are neither sorted nor rounded. Empty completed batches still have a block. Every batch flushes to the gzip stream and underlying file; offsets refer to the decompressed stream. Per-block hashes use the original Capture convention: uint64 event count, then ordered ID bytes, then ordered time bytes. After closing, an independent decompression pass reads all blocks and checks order, time bounds, counts and hashes against journal receipts. Truncated headers, arrays and compressed streams fail explicitly. A flushed block before a later analysis failure remains available even if the public runner totals exclude that pending coupling step.

The script checks native/neural finiteness, native warnings/termination, actual clock agreement below 1e-9 s, exact rolling buffer dimensions/origin, current physical sensory mappings, native control scaling, neutral stance, mute readout and resource residual below 1e-8. These establish numerical/interface properties, not biological behavior.

## Failure state, resources and images

Before cleanup, each attempt saves a full brain checkpoint, including pending state and RNG, plus the cached native diagnostics, available public snapshot, last cached physical observation, physiology and food/water resources. Snapshot failures are recorded independently. Brain time, actual native time/control tick and latest completed neural interval remain separate. Physiology exposes no independent clock: `host_physiology_t_s` is explicitly null, and the cached observation timestamp is labeled separately. A partial native step can skip the physiology update, so that observation timestamp is not substituted for a physiology clock.

`returned_physical_ticks`/`completed_physical_ticks` count successful `runner.advance` returns; `validated_physical_ticks` counts intervals that also passed all evaluator and prefix checks. A partially failed physical call can advance native time without adding a returned tick. The state checkpoint and journal preserve that distinction instead of rounding it into a completed 2 ms interval.

An initial overview and final overview/Follow image are saved. Each final render is checked for native-state invariance. The Follow camera keeps a fly visible after it travels outside the overview; it does not change the arena, target, command, body pose or scientific endpoint. The source floor is unbounded. This experiment does not introduce arena walls, obstacles or a finite habitat.

The pretrained walking body is a female-derived engineering surrogate controlled by the male connectome plus a learned motor policy. The source policy retains idealized body feedback and its generated current-command preview. Implausible negative Shiu voltages, volatile physiology, uncalibrated sensory rates and missing biological VNC control remain unresolved. Wind neural input, compound-eye neural input, grooming and flight are disabled. A finite 12 s result cannot establish indefinite stability or natural foraging.

## Recorder validation before freezing

`.venv/bin/python scripts/check_flybody_rolling_loop.py --self-test` passed without constructing a simulator. It checks exact ID/time byte roundtrip (including unsorted repeated IDs above float64's exact integer range and signed-zero timestamps), an empty batch, hash receipts, full readback, truncated metadata/block/array/gzip rejection, and fake completed/partial-failure state retention. The fake physiology has no clock attribute; the partial-failure test retains a failed public snapshot, nonfinite native evidence, distinct brain/native/observation times and pending checkpoint arrays.

Plan/result hashes, experiment outcomes and observed limitations will be added only after root review, freezing and execution. No planned behavior is presented here as an observed result.
