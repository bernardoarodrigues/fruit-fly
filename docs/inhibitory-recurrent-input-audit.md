# Retained Or42a inputs for a recurrent comparison

**Pass: 293 checks across all 15 retained trials and 9,694,843 recorded spikes.** The [audit script](../scripts/audit_inhibitory_recurrent_inputs.py) reads saved artifacts and independently reconstructs RNG/event accounting; it imports no neural engine or experiment producer. No neural simulation or larger rolling-loop archive was opened, and no duplicate arrays were written. The [audit receipt](../validation/inhibitory-recurrent-input-audit.json) lists all 65 input hashes, exact populations, schemas, trial paths and prefix checks.

The original [plan](../validation/or42a-summary-plan.json) remains SHA-256 `32a0f8f33d61b532c871a025b975945c7d79530d123b4ee5f7753ea54a0dd41e`. Its source hashes and the earlier independent review's artifact hashes all match. Every `trace.npz` and `samples.jsonl` matches both the original experiment and prior review. Each separate `result.json` equals its complete outer experiment trial record; its byte hash is newly recorded here because prior receipts did not separately pin that file's bytes. The audit script is `ce8ee60f7ea491d8ca14cb237c41a923f552607f1c73f50e7be2c75a84e29929`.

Graph fingerprint `e8d7babaecf923402d32fa1dd7fa687130968ac9ce57fa1b1af80ffea55c82e8` is independently recomputed over the exact 166,700-neuron/25,582,938-edge arrays. All **36 ORN_VM7d inputs**, ordered by numeric body ID, match the plan and metadata: 18 per side, all `MxLbN`. The first hop is the exact **365 non-source cells** reached by their outgoing CSR edges. Inputs, first-hop IDs and graph indices are recorded in the receipt without substituting neighboring types.

The current default decoder matches the frozen five groups and ten cells; optional grooming is absent:

| Group | MaleCNS body IDs |
|---|---|
| Forward, DNg97 | 13805, 230783 |
| Left turn, DNa01/DNa02 | 10442, 523769 |
| Right turn, DNa01/DNa02 | 10360, 10760 |
| Feeding, MN9 | 10331, 16949 |
| Escape, DNp01 | 10001, 10010 |

All per-neuron 500 ms window counts, source subsets, first-hop totals and motor-group totals reconstruct from the complete spike streams. Motor outputs were unrealized diagnostics with false taste gates; no body received them.

## RNG and direct-event semantics

Independent Python integer xorshift64* reconstruction verifies all 540,000 draws per trial, each 1,800-draw/5 ms RNG boundary and every ordered candidate arrival. The audit computes one temporary uniform array per seed outside any neural kernel; all conditions use that same draw sequence with their declared probabilities. Even the zero-rate control consumes all 36 draws per tick.

| Seed | Initial RNG state | State at 50 ms | State at 1,500 ms |
|---:|---:|---:|---:|
| 11 | 3926704849073358691 | 17002731536089512071 | 13581153611792153621 |
| 12 | 9986919024197907781 | 7461862444540912325 | 4493313800868040218 |
| 13 | 1477825346072093981 | 9726742448920413414 | 3214217756490935302 |

Sources have zero refractory interval at every simulated tick under the frozen source: all 36 remain listed, rates are explicit even at zero, each `advance` resets their refractory values to zero before entering the kernel, and the kernel does not change those durations. Complete per-tick refractory/current arrays were not archived, so this is source-backed contract evidence supplemented by the original drive checks.

Zero source refractory does **not** mean a direct event applies on its own firing tick. C0 thresholds first, marks firing sources inactive for the remainder of that tick, processes delayed synapses and direct voltage events, then resets. Every saved applied-arrival flag equals candidate arrival AND no same-tick source spike. These flags are reconstructed from scheduling and spikes, not separately instrumented membrane writes. A new arm must derive its own eligibility from the same candidate stream; it must not reuse C0's applied flags as a spike or voltage clamp.

The audit also reconstructs all delayed edge-visit counts from recorded spikes, exact 18-tick delay, CSR degree and the declared source-output mask. Visits include inactive targets and zero-weight edges; accepted postsynaptic increments are unavailable. Source blocking acts on outgoing delivery, including queued spikes, without suppressing direct excitation, incoming connections or source spikes.

## What the 50 ms probe can establish

Within each seed, `constant_baseline`, `ethyl_acetate` and `isoamyl_acetate` have **bitwise-identical ordered spikes, candidate events, applied flags and identical first ten 5 ms sample records** for `[0,50) ms` (ticks 0–499). All three request 11 Hz there. The unblocked `no_input` condition requests 0 Hz and is excluded from this equality. The blocked EA condition shares candidate arrivals/RNG but is not a recurrent-output equivalence control.

The proposed reference is `runs/20260905T030251528053Z-or42a-summary/seed11-constant_baseline`. Its first 50 ms contains 113 total spikes, 30 source spikes, and 30 candidate/applied direct arrivals. Seven recorded spikes have delivery due at or after tick 500. Their ordered identities/delivery-time hashes and the complete 45–50 ms sample are retained in the audit. The sample at 50 ms reports global voltage extrema **−199.6017809640471 to −45.23717664677575 mV**; finiteness is not physiological plausibility.

Available C0 prefix comparisons are exact spike order/ticks, candidates, applied flags, RNG endpoints, delayed edge work and the ten retained extrema/readout/sample records. Last-spike times and expected pending identities can be reconstructed from the spike history under the inspected queue rules, but there is no archived native prefix queue against which to check them. **There is no complete 50 ms voltage/synaptic checkpoint**, so these old artifacts cannot establish full-state bitwise parity there.

At 1,500 ms, every trial retains full float64 voltage and synaptic arrays, enabling exact endpoint comparison as well as complete spike/event-stream comparison. It still lacks separately archived full last-spike, refractory, mask, current and pending state. The audit verifies finite endpoints and their consistency with the final sample's global/source extrema; it does not reconstruct membrane trajectories.

The prefix is a short baseline workload before the odor-rate change at 500 ms. Its performance cannot by itself establish throughput or numerical behavior under the later stronger drive. Excitation rates remain cross-summary engineering inputs, not clamped afferent firing or physiological current measurements. These artifacts support a separately frozen recurrent test; they do not establish physiology, behavior or a preferred inhibitory model.
