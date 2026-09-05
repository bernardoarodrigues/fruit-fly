# Inhibitory factorial: retained-input audit

**The retained compact inputs are sufficient for the conditional two-target factorial. All 258 checks pass.** The [audit receipt](../validation/inhibitory-factorial-input-audit.json) pins 34 input files and the audit script. This is a read-only data/accounting check: no model was integrated, no parameters changed, and no duplicate event arrays were saved. The original full spike/journal archives were hashed as compressed bytes; their 31,489,162 spikes and journal payloads were not decompressed again.

## Exact identities, weights and ordering

The graph has 166,700 neurons and 25,582,938 directed pairs. Target order is deliberately **[67052, 13314]**, with graph indices **[49930, 3103]**; it must not be replaced by sorted numeric target order. The complete [incoming inventory](../validation/negative-voltage-replay-incoming-edges.csv) contains:

| Target | Type | Incoming edges | Anatomical contacts | Zero-weight edges |
|---|---|---:|---:|---:|
| 67052 | lLN2T_b | 2,260 | 27,830 | 34 |
| 13314 | M_vPNml50 | 435 | 7,247 | 19 |

All 2,695 rows match the original CSR graph, including source/target IDs, indices, annotation types, model signs and contacts. There are 2,595 distinct incoming source neurons and no duplicate source–target pairs. No selected target has a direct self/cross edge into either selected target in this graph. The inventory is target-major, with ascending original graph-edge index within each target. Every `weight_float32_hex` decodes to the exact little-endian graph bytes; the saved decimal value equals that float32 value promoted to float64. Zero-weight edges remain in the inventory and event accounting.

Each condition's `recorded_source_indices` and `recorded_source_spike_ticks` is a same-length, one-dimensional little-endian int32 array. Every index identifies a source in the complete incoming inventory. Ticks are nondecreasing and lie in `[0,120000)`; equal-tick event ordering is preserved, not sorted or deduplicated. The original [independent review](../validation/negative-voltage-replay-independent-review.json) established exact equality with the filtered full source stream. Matching current NPZ and original compressed-archive hashes preserve that proof; this audit does not claim a second raw-archive reconstruction.

## Masks, timing and original delivery accounting

The reconstructed constant source-output mask is empty for feedback and sensory-only. The blocked condition masks the union of **105 odor, 54 sweet and 137 club cells: 296 exact neurons**. The receipt stores their indices/IDs and the full boolean-mask byte hash. Every group identity matches graph annotations, the condition design matches the original frozen plan, and each entire reconstructed mask equals its final checkpoint. Motor readout mutes are separate and do not change these masks. Do not construct the mask from the actual drive-list union, which has 244 or 242 entries.

The original per-interval journals recorded the total blocked count and an all-sensory flag, not a complete membership bitset. Thus constancy relies on the frozen condition design, its fixed group identities, the earlier all-interval verification and the complete final mask. The audit retains that provenance limit. Likewise, absence of either target from **every** actual input list is inherited from the hash-verified original producer/reviewer checks; the current audit separately confirms zero final target current, exclusion from the final drive list and 22-tick refractory settings.

| Condition | Retained source events | Potential edge deliveries | Accepted in C0 | Source blocked | Target unavailable | Beyond horizon |
|---|---:|---:|---:|---:|---:|---:|
| locomotor_feedback | 1,162,471 | 1,225,720 | 1,225,512 | 0 | 8 | 200 |
| locomotor_sensory_block | 1,150,881 | 1,213,516 | 1,208,502 | 4,850 | 0 | 164 |
| sensory_only | 1,168,156 | 1,232,018 | 1,231,820 | 0 | 6 | 192 |

The clock is 0.1 ms, delivery delay 18 ticks, horizon 120,000 ticks, and stored state clock 120,001 samples. Potential deliveries are expanded in source-event order, then target-slot order. Baseline availability is reconstructed **only from saved target spikes**, without evaluating a voltage equation. Ordered accepted tick/edge arrays, every per-edge disposition and all aggregate counts agree exactly with the existing producer and independent review. The small receipt retains all 14 original target-unavailable tick/edge pairs.

Events beyond the horizon are classified pending before any future mask/availability decision. Their relevant source sequence matches each of the final checkpoint's 19 delay-ring slots; there are respectively 187, 157 and 184 pending relevant source events. Source events and edge deliveries differ because some sources contact both targets. Saved endpoint states also match the retained checkpoints byte-for-byte.

## Use in the factorial

Use the raw recorded source arrays and complete edge inventory as inputs. The old accepted arrays are **C0 verification evidence**, not the event list for changed arms: H0/H1/C1 must recompute their own threshold, reset/refractory and acceptance decisions. Preserve source order, float32 weight bytes promoted to float64, fixed masks and future pending events. Recorded source generation stays exogenous; this evidence does not validate a recurrent intervention or physiology.

Reproduce with [the audit script](../scripts/audit_inhibitory_factorial_inputs.py):

```sh
.venv/bin/python scripts/audit_inhibitory_factorial_inputs.py --output /tmp/inhibitory-factorial-input-audit.json
```

The destination must not exist. Failures are retained in the new receipt rather than overwriting earlier evidence. The script imports neither a simulator nor the original replay implementation; its computations are graph joins, hashes and saved-event bookkeeping.
