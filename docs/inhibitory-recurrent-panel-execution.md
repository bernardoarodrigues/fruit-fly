# Full recurrent inhibitory panel

The panel tests the four fixed C0/C1/H0/H1 arms in fresh full MaleCNS networks. It preserves the [scientific design](inhibitory-recurrent-design.md) and the [execution contract](inhibitory-recurrent-execution-plan-review.md): three seeds, five input conditions, and three simulated seconds per trial. All fifteen C0 controls run before any altered arm. Their first 1.5 seconds must reproduce the saved original-model experiment, including ordered spikes, applied inputs, RNG progression, counts and endpoint voltage/synaptic state.

This is an isolated neural experiment. The user cancelled the embodied Eon integration benchmark. Physiology remains a separate unresolved promotion gate; passing numerical bounds or obtaining more spikes cannot select H1.

## Implementation and preflight

The [runner](../scripts/experiment_inhibitory_recurrent_panel.py) creates one fresh process per trial. The [kernel](inhibitory-recurrent-panel-kernel.md) retains the exact four-thread interval calculation and ordered event commitment. It adds selected-event recording and global numerical-reference selection without changing dynamics. The [archive format](inhibitory-recurrent-panel-archive.md) publishes checksummed typed arrays and a completion marker, and has a separate [independent decoder review](inhibitory-recurrent-panel-archive-independent-review.md). Streaming metrics preserve partial windows as unavailable for rate contrasts.

Preflight evidence covers 284 kernel checks, 45 archive checks, 84 independent archive checks, 36 metric fixtures, 30 numerical-reference checks, 138 independent input checks and 49 dispatch checks. These checks include manufactured data and source inspection; they do not constitute a completed network panel or a biological validation. The aggregate receipt and exact-source pins must pass before the runner can prepare a plan.

## Resources and retained evidence

Each trial uses four integration threads and a fresh worker. Ordinary limits are 3,600 wall seconds, 4 GiB output and 8 GiB peak RSS per worker; the panel has 86,400 seconds and 64 GiB output, a 512 MiB failure-retention reserve, and a 10 GiB free-space floor. Limits are checked between operations, so one operation can overshoot. Final terminal receipts carry the authoritative status after normal output publication. Their own bytes and the last log line are the disclosed final unmeasured operation.

Bulk input streams, every completed 5 ms chunk, selected traces, numerical-reference inputs/results, boundary checkpoints and partial-failure evidence remain under the frozen ignored `runs/` directory. Git retains the plan, source, review receipts and compact outcome documents. Neither a resource limit nor a failed numerical interval is permission to restart, replace or silently omit that trial. Correctness or retention failure halts the panel. A resource-limited C0 trial can authorize altered arms only if its original 1.5-second prefix was already durably verified.

## Execution record

The [plan](../validation/inhibitory-recurrent-panel-plan.json) was prepared on 2026-09-05 UTC after all seven preflight components passed (666 checks, including the separately independent archive review). Its SHA-256 is `c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5`. Input archives and the prepared manifest are under `runs/20260905T060501089987Z-inhibitory-recurrent-panel`. The source/input/environment recheck passes. The source and plan were committed and pushed as `91b6820` before execution. The parent began at 2026-09-05 06:05:46 UTC.

### First seed controls: saved progress snapshot

All five C0/seed-11 controls completed three seconds and passed their exact original 1.5-second prefix gates. The [immutable progress snapshot](../validation/inhibitory-recurrent-panel-first-seed-snapshot.json) pins their result and terminal receipts. This is an intermediate result: the parent is continuing the remaining C0 seeds, and altered arms still require all fifteen gates.

| C0 condition, seed 11 | Saved spikes over 3 s | Original prefix |
| --- | ---: | --- |
| No input | 0 | Exact |
| Constant baseline, then withdrawal | 2,332,500 | Exact |
| Ethyl acetate, then withdrawal | 2,323,760 | Exact |
| Isoamyl acetate, then withdrawal | 2,341,629 | Exact |
| Ethyl acetate, source outputs blocked | 3,085 | Exact |

The [quiet-control audit](inhibitory-recurrent-panel-saved-data-audit.md) passes 35,811 checks, and the [active-state audit](inhibitory-recurrent-panel-baseline-independent-review.md) passes 38,229 for the baseline trial. The latter reconstructs every selected voltage/synaptic transition, 344,181 selected delayed edge records and the complete spike-derived checkpoint histories. A separate [count audit](inhibitory-recurrent-panel-baseline-count-review.md) confirms every neuron/window counter. The [first-worker audit](inhibitory-recurrent-panel-first-worker-audit.md) separately verifies process handoff, terminal hashes and exact output accounting. These certify their stated saved-data scopes, not the entire unfinished panel.

The first baseline trial reveals **persistent C0 activity after source withdrawal**. Its 36 sensory cells produce no events or spikes in the three off bins, while the other 166,664 cells produce 438,307 / 440,585 / 437,192 spikes. That is 5.259768 / 5.287105 / 5.246388 spikes per cell per second, averaged over the entire nonsource population. The bins do not increase monotonically; the late count is 0.254% below the early count. This establishes activity through the observed three seconds, not indefinite stability or uncontrolled growth. The forward pair stays silent. Feeding readout 10331 remains active, but no body or ingestion ran in this experiment.

A further **provisional seed-11 C0 comparison** uses the producer summaries pinned in the snapshot. The first-hop population rises from 57.3151 Hz in the ethyl trial's own baseline to 127.6548 Hz during its pulse. The matched constant-input control is already at 121.8301 Hz during that same time window: the matched odor effect is +5.8247 Hz, much smaller than the +70.3397 Hz within-trial change. Thus startup recruitment substantially contributes to the apparent response in this model. The full paired-seed analysis and independent active-odor audit remain pending. Whole-network mean activity, first-hop responses, exact targets and motor outputs must remain separate measures.

No H0 or H1 result is available in this snapshot. All model defaults and the cancelled embodied Eon benchmark remain unchanged.
