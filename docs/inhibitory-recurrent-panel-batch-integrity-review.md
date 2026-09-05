# Completed-panel C1 batch and final integrity review

The missing C1 saved-data reviews and the separate final-integrity audit both passed on their first executions. No producer, input, frozen reader or run artifact was changed, and no neural simulation was started. No commit was made.

The [C1 batch index](../validation/inhibitory-recurrent-panel-c1-batch-index.json) records **15 passed C1 reviews, 564,360 component checks and 66,637,628 archived spikes**. Exactly the requested missing ordinals 27, 30, 33, 36, 39, 42, 45, 48, 51, 54 and 57 were executed, sequentially, using the frozen independent active reader after authoritative completion. Existing ordinals 15, 18, 21 and 24 were reused unchanged. The [batch script](../scripts/review_inhibitory_recurrent_c1_batch.py) refuses to overwrite its first index and stops on a failed reader.

These C1 reviews verify pinned artifacts, ordered spikes, source input/RNG masks, own-history refractory and delayed queues, selected-48 voltage/synaptic transitions, ordered selected-edge events, checkpoint counts and all fixed cohort metrics. They do not independently reconstruct every intermediate global voltage or every global accepted/unavailable edge disposition. Passing these engineering and numerical checks does not establish physiological accuracy, long-term stability or promotion.

The [final-integrity receipt](../validation/inhibitory-recurrent-panel-final-integrity.json) records **478,154 passing checks** from a separate [standard-library audit](../scripts/review_inhibitory_recurrent_panel_final_integrity.py). Its scope was:

- Verify the authoritative parent terminal → results → artifact-manifest links and the exact published copies in `validation/`.
- Confirm all **60 unique trials** in the declared 4-arm × 5-condition × 3-seed design, in frozen plan order, with complete child terminal/result status, consistent identities and clocks, and **420 complete windows**. Parent summaries exactly match their pinned child summaries.
- Stream SHA256 and verify size for **all 109,952 manifest-listed files**, totaling **4,406,666,281 bytes**: 73,348 JSON files, 36,544 NPZ files and 60 logs. The only run files outside that manifest are the three final publication files, which are linked separately and also hashed.
- Verify every trial-result artifact reference against the observed manifest records, all expected checkpoints, exactly 600 chunk markers per trial, and the payload links of all **36,544 completion markers**.
- Verify all **61 frozen source receipts**, plus the linked 15 C0 prefix-gate declarations. This pass links the existing C0 gate evidence; it does not replay its numerical checks.

Each unique file was hashed at most once within the integrity execution; later link checks reused that observed record. Including source files, publication copies and the audit script, the pass hashed 110,008 distinct files and 4,714,270,919 bytes. Hashes establish retained bytes and reference consistency. They do not validate neural equations, recompute spike metrics or contrasts, or guarantee protection from later filesystem changes. Array decoding and metadata/payload transaction reconstruction remain the responsibility of the independent C/H readers.

The earlier optional first-stimulus summary failure is preserved unchanged at [its original receipt](../validation/inhibitory-recurrent-panel-c1-first-stimulus-summary.json), SHA256 `7f5aea66fec2237923b3d54c43f3eb30818b8ee708899f214001cb20039efc01`. Its `KeyError: 'phase_min'` was a failed optional summary extraction; it was neither corrected nor rerun in this batch. The completed trial-24 independent review remains passing, and this batch does not use that failed summary as evidence.

| Artifact | SHA256 |
|---|---|
| C1 batch index | `d78ab98dc1483dbf89e2e512318879afa82c2047d71d581904bd483cb61d523b` |
| C1 batch script | `2b79b7bcf496478a1271fdd53c0042af23fd3901ec960785a58f9ac57ac5cab0` |
| Final-integrity receipt | `1e96c6f2946d3b1055be3fb3e1925fdf3f44c688ff87505469bc428a4b3c983e` |
| Final-integrity script | `3435f184615adb74c6433afceab60b5797c02c69e86e442c3723a548178b4651` |
| Frozen active reader | `2329e31a90bfaae48372a36ce3ccd03146bdec785dff9c511737c10bead81226` |
| Parent terminal | `59b2a948dc6c641ac38d7e1ecb5707656a7fbd724a4bd453ffed981e6605049a` |
| Parent results | `021bbc028ceec91611d97010fec48deae7940eb3b155649ba279a7ccf5f1916c` |
| Parent artifact manifest | `c8410ecea4923be0f090daff7e7a14a4ba375e51cfaafd3851d1a040f69bf9e6` |

Individual review/result/terminal identities and hashes are retained in the C1 index. Exact source receipts, per-trial publication links, categorized checks and the digest of all observed file records are retained in the final-integrity receipt. Scientific interpretation and the cross-arm aggregate remain separate work.
