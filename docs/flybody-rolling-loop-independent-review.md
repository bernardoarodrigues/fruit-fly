# Independent review of the full neural rolling loop

All three attempts completed the planned **12 seconds** and passed the producer's declared gates. The independent review covers **18,000 completed physical intervals, 31,489,162 ordered spike events, and 11,420,949,975 delayed edge visits**. Both locomotor trials exactly reproduce their declared original 1,000-interval prefixes. The sensory-only trial commands rest throughout, despite substantial network spiking; it supplies no evidence of natural locomotion or food seeking.

The [frozen plan](../validation/flybody-rolling-loop/plan.json) has SHA256 `3e5ca3ca6c91bbd240ff2530d351fd010dc5001e19078e2270a95022449c2498` and source revision `848436f5127d95b36f57f74948c16a7489474cf6`. The [independent reader](../scripts/review_flybody_rolling_loop.py) verifies the [saved result](../validation/flybody-rolling-loop/results.json), closed raw journals, complete binary spike streams, and final brain checkpoints. Its [receipt](../validation/flybody-rolling-loop/independent-review.json) separates record consistency from the experiment's pass/fail status. No neural model, learned actor, or physics simulator is imported or rerun.

| Saved result | Locomotor feedback | Sensory outputs blocked | Sensory only |
|---|---:|---:|---:|
| Completed physical intervals | 6,000 | 6,000 | 6,000 |
| Ordered full-graph spikes | 10,524,467 | 10,441,248 | 10,523,447 |
| Delayed unblocked-source edge visits | 3,813,896,501 | 3,787,758,919 | 3,819,294,555 |
| Walk / rest commands | 4,247 / 1,753 | 4,300 / 1,700 | 0 / 6,000 |
| Planar path, 2 ms chords | 91.0751 mm | 90.2429 mm | 0.015171 mm |
| Sampled voltage extrema | −532.58 / +21.03 mV | −526.62 / +20.15 mV | −527.96 / +20.92 mV |
| Minimum upright-axis z | 0.98373 | 0.97274 | 0.99985 |

There are no feed commands, positive sweet input rates, or abstract food intake in these three off-food trials. The MN9 readout groups nevertheless produce 731, 692, and 708 spikes respectively. Presence of these spikes alone is not a feeding endpoint. Path length is the sum of successive planar pose chords, including the initial pose; it is neither net displacement nor an integral of inertial-center speed.

Across all completed steps, the maximum clock discrepancy is **8.03e−12 s** and the maximum normalized resource-ledger residual is **3.78e−15**. Retained physical arrays are finite, warnings are zero, source termination is false, and all three worker exit receipts are zero. No failed or partial attempt is present in this frozen run. Brain checkpoints end at 12,000 ms; native clocks end at approximately 11.99999999999871 s, consistent with numerical accumulation.

## What is independently checked

The graph fingerprint is recomputed from all four ordered arrays: neuron IDs, outgoing CSR offsets, targets, and signed weights. The graph contains 166,700 neurons and 25,582,938 edges. Frozen tracked sources are read from the declared Git revision; ignored local data must match the plan hashes. Source and motor groups are reconstructed from the annotation table, including bilateral/leg mappings, and checked against every retained group's IDs, types, and indices.

The binary reader checks the `FFSPK001` metadata, graph and plan identity, little-endian block headers, array lengths, offsets, counts, and every original ordered `int64` neuron ID and `float64` timestamp. It requires valid complete gzip trailers and verifies both compressed and uncompressed hashes and byte counts. A missing or truncated tail fails review. It never infers completion from the last readable block of an active file.

Every spike must lie on the 0.1 ms neural grid within its declared 2 ms batch. The native order is checked: time increases, and cells appear in graph-index order within each neural tick, with no duplicate cell event at a tick. Cells outside the current input list also satisfy their 22-tick refractory spacing across batch boundaries. Full and subgroup event hashes and count tables are independently reconstructed. Monitored source/motor counts are subsets of the full stream and are not added to the total a second time.

An independent schedule shifts each source event by the declared 18 neural ticks, excludes sources with blocked outgoing synapses, and sums their CSR outdegrees when delivery occurs. This reproduces batch edge-visit totals across coupling boundaries. These are visited edges, including edges whose target is refractory; they are not counts of successful postsynaptic voltage updates. Blocking acts at source-output delivery and preserves the direct input mechanism and source spike generation.

The reader reconstructs ordered odor/sweet/club encoder outputs from the actual preceding physical observation, including zero-rate listed odor cells and leg-specific tibia/tarsal contact mappings. Motor-probe conditions append the two DNg97 inputs at their configured 40 Hz event rate; sensory-only mode appends none. Available probe IDs in metadata do not mean a probe was applied. Configured Poisson event rates are model input parameters, not measured biological firing rates.

Input-order hashes and RNG state continuity are verified for every interval. Independent integer xorshift transition algebra advances the retained RNG state by exactly twenty draws per listed input index, covering **87,591,780 draw positions**. This includes zero-rate members. The journal does not retain individual Bernoulli realizations or the applied external-event mask, so checking the stream's draw count/state does not independently establish those missing per-event application decisions.

## Body coupling and interventions

Each retained body return supplies the full `qpos`, `qvel`, `qacc`, activation, control, action, contact, antenna, and tibia diagnostic fields at 2 ms intervals. The review independently checks finite arrays, warnings/termination flags, native/control counters, synchronized neural/native/public clocks, the 66-frame storage shapes and current origin, exact neutral hold, action scaling/control order, filtered neural motor decoding, and the speed/yaw command map.

The target is reconstructed by integrating each current command from the preceding target. Its position and yaw are not replaced by the current physical pose. The native clock and source counter remain continuous. This checks the recorded rolling-reference behavior; full actor vectors and every reference-buffer row are not present in this full-neural journal. Their digests and shapes are retained, while actual actor-input parity is established by the separate [bridge review](flybody-rolling-bridge-review.md).

Source contact forces are independently re-summed into leg support and ground-force vectors. Tarsal contact with the declared food/water regions supplies the taste gates. Nutrient and water ledger residuals, capacity bounds, intake increments, and feed/speed/contact requirements are checked. Plume concentrations are retained and their encoder transfer is reproducible, but full puff positions/state are absent; independent spatial plume reconstruction is outside this record.

The locomotor trials mute the motor readout for intervals starting at ticks `[300,600)`, `[1500,1800)`, and `[4500,5300)`: respectively 0.6–1.2, 3.0–3.6, and 9.0–10.6 seconds. Each mute is checked against the recorded intervention and forces rest/zero motor commands while the complete neural stream continues. Window counts use interval start ticks; the final interval ends at the stated upper boundary. The sensory-only trial has neither DN probe drive nor imposed motor mutes.

The three mute windows retain **524,219 / 526,174 / 1,406,633** full-network spikes in the feedback trial and **526,843 / 527,433 / 1,402,890** in the blocked trial. These events remain in the lossless streams even though the delivered motor readout is held at rest.

The two locomotor trials each compare their first 1,000 intervals to the original bounded experiment. The comparison includes every declared native state/action/target field, complete ordered encoder drive, RNG state, neural counts/voltage extrema, and original ordered spike hash. New lossless arrays reproduce those older spike hashes. Rolling bookkeeping and cached post-step reference tails are the explicit exclusions; the original archive had no complete actor-input vectors.

Between the two new locomotor conditions, the first non-sensory ordered spike difference occurs in tick **4**, the **8–10 ms** interval, while the entire input history and RNG assignment still match. The first ordered-input difference occurs at tick **21**, the **42–44 ms** interval. This independently confirms transmission through the collectively blocked sensory source outputs before physical feedback diverges. It does not isolate odor, sweet, or proprioception individually, require later input histories to remain equal, or establish natural navigation.

## State retention and interpretation limits

The final brain checkpoint is independently checked against the retained spike streams: graph identity, time, each neuron's last spike, pending delayed source IDs by ring slot, current, latest drive, input refractory state, blocked mask, RNG state, and full voltage/synaptic finiteness. Final voltage extrema must match the last neural record. Earlier full voltage and synaptic arrays are not retained, so earlier interval finiteness and extrema remain producer assertions, rather than independently reconstructed neuronal trajectories.

On an unsuccessful attempt, completed neural blocks and completed/validated physical intervals must be reported separately. A batch archived before a body failure remains part of the spike evidence without being counted as a completed physical step. The retained native state, cached observation, and brain clock retain their own timestamps. There is no separate elapsed physiology clock, so the reviewer does not assign it the native or brain time.

Reset/render/zero-advance equality and worker cleanup are producer checks with retained receipts, not independent before/after state snapshots or process-history logs. A completed 12-second numerical trial also does not establish indefinite stability. The feedback and sensory-only final follow frames were visually inspected and depict an upright articulated fly; still imagery cannot establish the trajectory or natural behavior.

The full graph is male; the pretrained motor surrogate derives from the female FlyBody preparation. The current odor, sweet, and proprioceptive encoders remain uncalibrated mappings. Neither this coupling nor downstream spike divergence establishes physiological firing/voltage, natural navigation, male-specific mechanics, feeding biology, or reproduction. Large negative sampled voltages must remain visible in the outcome rather than being described as biological validation.

Run the final review only after the producer closes every attempt:

```sh
.venv/bin/python -m scripts.review_flybody_rolling_loop
```

`--available` instead checks only conditions already listed in the producer result with a matching closed condition receipt. It writes an explicitly partial review while other trials are active. Both commands perform read-only analysis of experiment evidence and rewrite only the independent receipt.
