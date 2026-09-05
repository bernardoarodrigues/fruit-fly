# Independent review of the full-graph FlyBody loop

**All 2,500 saved coupling intervals pass the independent journal calculations.** No neural simulation, policy inference or physics run was repeated. [The review script](../scripts/review_flybody_loop.py) imports NumPy/Pandas and standard-library tools only; it does not import the producer's metric helpers or any `fruitfly` runtime. Its [machine-readable receipt](../validation/flybody-loop/independent-review.json) records hashes, quantities checked and limits.

## Provenance qualification

The run's plan SHA-256 is `6ab6b5f8bbcb4cc3343e97824c182e4c30e9d5d1902d21804cf56eb25f16d403`. The reviewer resolves tracked source paths at frozen commit `928e062`, which permits later viewer work without silently substituting it into the experiment. Ignored data manifests are checked locally. All declared runtime, configuration and data-receipt hashes match. The producer's results also record unchanged source hashes immediately after execution.

One declared documentation hash does **not** match commit `928e062`: `docs/flybody-integration-plan.md` is declared as `71a0cbb5dfc965331ca4788c385e1ba14d401e75a06faa1d6dd4ee3b7a636968`, while the committed document is `b9ac20ebe92116537ef3741493abe471c015b5eeda1433f0083b3d1637be5bf6`. This prevents claiming that every declared file is preserved by that commit alone. The receipt explicitly reports `all_declared_sources_match_revision: false`, separately from `passed_saved_journal_checks: true`. Neither the frozen plan nor original trial results were changed to remove this discrepancy. The original pre-run document contents have not been recovered; an exact reconstruction is unavailable. The separate immutable assay plan still retains its declared methods, interventions and gates.

All archived original file hashes match the relocation receipt. Each gzip file decompresses to the original journal hash. The original pre-archive results and all eight copied endpoint images also match their recorded hashes. The journal totals are 7,007 records per locomotor trial and 1,753 per on-food trial. Local raw artifacts live under `runs/flybody-loop-6ab6b5f8bbcb`; the archival path mapping resolves historical execution paths inside byte-preserved manifests. A clone without these ignored raw artifacts cannot independently repeat this calculation from summary JSON alone.

## What was independently checked

- Exact sequence of one observation, three ordered encoder calls, one neural start/completion and one physical completion per tick; precisely 1,000/1,000/250/250 ticks and the two scheduled motor-mute transitions per locomotor trial.
- Source indices and IDs against the saved MaleCNS neuron table, including bilateral ORN DM1/DM4, all six named leg taste/club groups, descending motor groups and MN9. The recorded graph dimensions are consistent with 166,700 retained IDs and 25,582,938 target entries.
- Ordered drive hashes, index uniqueness, ID/rate correspondence, unchanged refractory declaration and default current/weight fields. Independent reconstruction of odor occupancy/adaptation/hunger gain, tarsal contact rates and native tibia-speed club rates gives **zero rate error**. The complete brain input is exactly odor, sweet, club, then the 40 Hz DN probe only in the locomotor pair; zero-rate ORNs stay listed.
- The input observation uses the preceding native body pose/tibia velocities and active tarsal floor contacts in the actual food/water regions. State flow is causal across coupling ticks. This checks the two-way physical interface, not just matching final endpoints.
- Unique per-neuron spike-count rows sum exactly to each full batch. Every source/motor group's counts match the corresponding subset of the all-neuron counts. Full-graph cumulative telemetry equals the sum of batches; overlapping summaries are never added as additional graph events. The motor rate filter independently reconstructs with **zero error**, and its rest/feed/walk outputs agree with the commands.
- Every native action has the source's action ordering. Enabled policy actions equal the source float32 clipping/scaling map exactly; rest/feed/mute actions equal six adhesion values of 1 followed by 53 neutral position targets of 0. Speed/yaw commands agree with the frozen left/right decoder. No posture hold is described as a force-free body.
- All retained physical arrays are finite, warning counters are zero, native/brain/host times match each completed 2 ms tick, and normalized resource ledgers balance. Recorded food increments occur only in feed mode with actual tarsal food contact and the native speed at or below 1 mm/s; they do not exceed the declared per-tick intake cap. All workers exit with code 0.
- Every neural interval and physical check summary agrees with its raw journal event. Path, displacement, exact speed slices, total/group/muted spikes, behavior counts, feed onset, ingestion, minimum upright/voltage, maximum acceleration, clock discrepancy and resource residual agree with the descriptive summaries.

Maximum clock discrepancy is 1.8763×10⁻¹³ s and maximum resource residual is 7.7716×10⁻¹⁵ normalized units. All checked encoder and filtered motor rates are bit-for-bit numerically equal to their independently reconstructed values. This is arithmetic/interface consistency; it does not make the selected biological gains correct.

## Causal comparison and retained negative endpoint

The locomotor source-output block covers **296 sensory cells**; the on-food sweet-only block covers **54**. Source review confirms that the neuronal mask is checked at synaptic delivery. It does not disable a source cell's own thresholding, spontaneous/recurrent spikes or supplied Poisson drive. The producer asserts the complete expected mask every tick; the journal itself retains the count and named groups, not the full boolean mask. Thus full-mask identity is producer evidence supported by the code, not independently reconstructable from counts alone.

Both pairs first differ in the saved non-sensory spike-event hash at zero-based tick 4 (8–10 ms). Their current and prior ordered drive hashes and before/after RNG states agree at that point. Locomotor inputs first differ at tick 21 (42–44 ms); on-food inputs never differ over the 250 saved intervals. The full history match, not merely equality of the current input vector, supports the intervention comparison. Later locomotor differences include altered bodily feedback. The collective locomotor block cannot isolate odor versus club transmission.

The sweet block changes downstream events, but **both on-food trials retain 28 MN9 spikes, 234 feed intervals and 0.03744 normalized intake**. Their physical paths and final frames are identical. This is a negative differential feeding endpoint. It does not establish that sweet input is unnecessary in real flies: odor and club input remain active, neuronal gains/dynamics are provisional, and this is one short seed. Sensory-source spike totals themselves may differ because recurrent input changes even when the imposed sensory drives are identical.

## Evidence limits

Ordered spike times/IDs are saved as hashes plus per-neuron counts, not full ordered timestamp arrays. The review can compare recorded hash equality and independently check counts, but cannot regenerate those spike-event hashes. Complete voltage and synaptic arrays are likewise not journaled, so their finite flags are producer assertions. The recorded minimum −516.13 mV is physiologically implausible and remains a model defect.

Native antenna positions and their sampled concentrations are saved, and source inspection confirms mm-to-m conversion and pure `PuffField.sample` lookup. Puff birth/state arrays are not saved in the journals, so the independent review cannot reconstruct the spatial plume values from these artifacts alone. The producer performed that additional pure query during the run. Reset, render and zero-duration equality are also producer assertions with only the resulting initial state retained; they were not re-executed here.

The five unique endpoint images were visually inspected and all eight image hashes were verified. The fly and material-region markers render correctly and motion changes the locomotor endpoint. Still images do not establish gait quality, continuous contact occupancy or stability between samples. Contacts are observed at 2 ms intervals even though native physics steps at 0.2 ms. Source acceleration/force snapshots retain their native integration-stage semantics.

These trials do not validate a natural male body, food seeking, endogenous stance, swallowing, reproduction, biological voltage/rates, long-run robustness or an indefinitely running viewer. The initial viewer's two-second boundary error is a separate retained UI defect, not a failure of the completed four assay conditions. A later [actual-browser inspection](../validation/flybody-viewer/inspection.json) verifies the fix.

To repeat the review with local archived raw artifacts:

```sh
.venv/bin/python scripts/review_flybody_loop.py
```
