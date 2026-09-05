# First real worker: resource and publication audit

**Pass.** One bounded audit of `00-C0-seed11-no_input` verifies completion, process handoff, file integrity and final resource accounting. The [saved-file checker](../scripts/review_inhibitory_recurrent_panel_first_worker.py) passed **4,291 checks** on its first execution; a separate [parent-admission snapshot](../validation/inhibitory-recurrent-panel-first-worker-parent-admission.json) passed four checks. No worker was launched, no neuronal transition was replayed, and no live run file was modified. Other trial outcomes were not audited.

The worker belongs to [the frozen panel plan](../validation/inhibitory-recurrent-panel-plan.json), SHA256 `c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5`, in `runs/20260905T060501089987Z-inhibitory-recurrent-panel`. Its authoritative [terminal receipt](../runs/20260905T060501089987Z-inhibitory-recurrent-panel/00-C0-seed11-no_input/terminal.json) reports **complete**, with all neural, durable archive, checkpoint and count boundaries at tick 30,000, or 3 seconds.

| Measure | First worker |
| --- | ---: |
| Reported wall time through terminal preparation | 68.468804750 s |
| Reported peak RSS | 768,114,688 bytes |
| Independently counted final directory bytes | 25,161,920 bytes |
| Closed directory files | 1,833 |
| Verified archive records | 1,827, including 609 completion markers |

These values are within the frozen per-trial limits. Wall time and peak RSS are the actual worker's measurements, not independently reconstructed historical maxima. A read-only `ps` sample at approximately 49 seconds independently showed PID 1747, parent PID 1743, and RSS 610,960 KiB; the original tool output remains in the task transcript. This one no-input worker gives no forecast for later inhibitory workloads.

The [PID observations](../validation/inhibitory-recurrent-panel-first-worker-observations.json) first found worker 1747 present, then found it absent at **06:06:55.847506 UTC** while the active-worker record still named it. The next worker, PID 2826, was recorded at **06:06:55.967558 UTC** and wrote its own start record at **06:06:56.547015 UTC**. Together with the inspected parent's wait-before-dispatch order, this supports the actual sequential handoff. It is a 20 ms polling observation, not continuous OS tracing.

Publication and byte accounting agree exactly:

```text
24,695,335  bytes at the ordinary result's last measurement
   465,809  bytes in result.json
25,161,144  bytes measured by the authoritative terminal receipt
       669  bytes in terminal.json
       107  bytes in the final worker log line
25,161,920  bytes in the closed worker directory
```

The unexplained residual is **zero**. The first worker's global-versus-trial byte offset also reconstructs exactly to 26,173,415 bytes from pinned root-level streams/selection, manifest/start files and the saved first active-record contents under the inspected JSON formatting. This reconstruction excludes parent progress, which is written after the child exits. It is a serialization-based reconstruction of the former root directory state, not a retained filesystem snapshot at that instant.

Every reported archive file hash and completion-to-payload link verifies, with no lock, temporary or failure-publication artifact left in the first worker directory. The terminal points to result SHA256 `5861d94fb6cb8d7e54c9782a9dd67cdd28dea7f9ad3115700aaf7f8fe183ee11`; the terminal itself is SHA256 `7be602f698c9925a55d3eb420243fe8e090c4d77237b59908c7f96220fac809c`. The parent snapshot records those same hashes, authoritative complete status and tick-30,000 count/raw boundaries. Its source progress file is mutable, so the saved admission includes its hash at capture and only the first trial's entry.

The [audit receipt](../validation/inhibitory-recurrent-panel-first-worker-audit.json) retains the checks and all inspected closed-file hashes. This verifies the first worker's engineering evidence; it is not an independent neuronal trajectory review, a panel-wide resource conclusion or a biological result.
