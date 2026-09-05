# Recurrent panel dispatch and failure-contract review

**Pass: 49/49 bounded checks on the first execution; no remaining blocker within this review's scope.** The runner was source-reviewed at SHA256 `597eef47d93f3b57896fa7c38864ea8003153f8e54d1de720f2efc23f2bf2512`. The [fake-process checker](../scripts/check_inhibitory_recurrent_panel_dispatch.py), [frozen test plan](../validation/inhibitory-recurrent-panel-dispatch-plan.json) and [receipt](../validation/inhibitory-recurrent-panel-dispatch-checks.json) exercise parent dispatch and finalization using tiny synthetic reports. No real subprocess, anatomical graph, neuronal transition or reference-solver interval was executed. There was no failed checker attempt or post-result amendment.

The reviewer authored the archive helper and its focused tests, which have a [separate independent review](inhibitory-recurrent-panel-archive-independent-review.md). The reviewer did not author the runner, kernel or metrics module. Metrics/input and numerical-reference review belong to the other independent reviewers; this review focuses on resources, archive publication, process lifecycle, gating and failure retention.

Before source freeze, review findings led the runner author to add prepared-plan hash checks in parent and child, explicit prerequisite-pass checks, authoritative terminal receipts after ordinary results, final parent resource/source/file checks, and validation of actual C0 checkpoint payloads. Parent cleanup now covers any exception with a live child, including a failed active-worker record write. A missing prefix caused by a resource-limited C0 trial has an explicit engineering-status label. The author separately corrected counts-versus-durable-prefix bookkeeping and reference-failure provenance; their final interactions with archival were inspected here.

Source inspection confirms that each trial gets a new `Popen` child. The parent waits for that child before dispatching the next. Worker startup checks the expected prepared-plan digest, the invocation/global-start identity, pinned source/input files and environment. Preparation requires passing prerequisite receipts before creating streams. The parent and worker both enforce all 15 C0 prefix gates before an altered arm. Each gate identifies the seed, condition, tick, plan and expected checkpoint path; `load_archive` validates the checkpoint payloads, completion marker and identity. Trial start records, immutable archives and run start records prevent accidental overwrite or resumption.

The ten fake-process scenarios produced these results:

| Scenario | Fake children launched | Result |
| --- | ---: | --- |
| All trials successful | 60 | Complete, correct fixed order and 15 gates |
| First C0 resource-limited before its prefix | 15 | Missing-prefix resource status; no altered arm |
| First C0 resource-limited after a durable prefix | 60 | Gates allow continuation; panel remains partial |
| First C0 correctness failure | 1 | Failure stops dispatch |
| Child exits without result/terminal | 1 | Failure stops dispatch |
| Global budget exhausted before launch | 0 | Global resource limit |
| Global budget exhausted after final child | 60 | Global resource limit; not complete |
| Parent interrupted with live child | 1 | SIGINT requested, child reaped, no continuation |
| Parent publication fails after launch | 1 | SIGINT requested, child reaped, no continuation |
| C0 payload corrupted with completion marker unchanged | 15 | Validation fails; no altered arm |

All **214 fake worker lifecycles** were reaped, with at most one fake worker live. These are simulated process objects, not observations of OS memory release or actual signal delivery. The real prepared-plan/source guard also rejected changes to tiny synthetic files, and the real prerequisite-only preparation path rejected a failing receipt before stream generation. Child computation, source checking inside dispatch, cohort summaries and disk-free measurements were mocked. Actual archive JSON writes, tiny typed checkpoint loading, parent gate logic, manifest generation and terminal result-hash links were exercised.

Raw fake outputs remain in the ignored [fixture directory](../runs/inhibitory-recurrent-panel-dispatch-fixtures). The receipt hashes all 1,055 files, totalling 1,191,259 bytes. These include the deliberate corrupted checkpoint and failure reports. The synthetic checkpoint identity says `synthetic-no-graph-loaded`; none is evidence that a real C0 prefix passed.

The worker keeps candidate window counts separate until the matching raw chunk has been durably archived. Failure retention distinguishes confirmed neural prefix, raw archive prefix, complete checkpoint boundary and count boundary. Summaries use `counts_end_tick`, which can differ from the latest retained raw chunk after an exception. An uncaught compiled-call or wrapper-return failure marks mutable state incoherent while retaining the pre-call confirmed clock/RNG. Parent analysis excludes correctness, retention and interruption failures from contrast operands. These worker branches were source-inspected; the fake children did not execute them.

Resource checks include current files, logs and temporary evidence. The worker caches closed trial-directory sizes under the exclusive-writer contract, while the parent rescans the full run after child exit/log closure and at finalization. Failure-reserve accounting extends through window counts and result publication. Ordinary result records explicitly defer to `terminal.json`; the parent verifies the worker result hash named there. Final artifact manifests and compact result/terminal links retain the publication chain. A terminal record's own write and last log line remain the final unmeasured operation, as the frozen runner plan explicitly states. Checks between operations allow a single operation to overshoot; these are observation-and-stop limits, not hard process-level quotas.

The source attempts SIGINT and a bounded wait, then termination and finally killing/reaping if required. The fixtures exercised the SIGINT completion path, not timeout escalation, signal races, hardware power loss, an unresponsive kernel, RSS reclamation or complete filesystem failure. Early preflight failure can stop before a worker result exists; the parent treats a missing result/terminal as failure and retains prior files. Archive-level interruption/overwrite behavior has its own frozen tests and independent review.

Frozen test pins:

- Checker: `0f867022029a42904e3738527707fe15e6714d719ba6e658f393e1138002734b`.
- Plan: `86aefcd2077e0f2c9131e81fd4e3911272484511a0f14325912c0bb94683b0bf`.
- Receipt: `81446afa4faaf65905751424bfba0cc3e8a436cb434a832aa7ff08fa1193faec`.

This review clears the tested engineering contracts for the separately frozen panel. It does not establish a real trial's outcome, resource consumption, numerical validity or biological interpretation.
