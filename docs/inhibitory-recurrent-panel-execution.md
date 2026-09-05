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

The [plan](../validation/inhibitory-recurrent-panel-plan.json) was prepared on 2026-09-05 UTC after all seven preflight components passed (666 checks, including the separately independent archive review). Its SHA-256 is `c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5`. Input archives and the prepared manifest are under `runs/20260905T060501089987Z-inhibitory-recurrent-panel`. The source/input/environment recheck passes. No full-panel trial has run at this snapshot; the source and plan are being committed before execution.
