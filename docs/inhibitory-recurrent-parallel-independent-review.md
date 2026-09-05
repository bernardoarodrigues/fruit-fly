# Independent review of the parallel recurrent implementation

**Pass: 176 checks; no remaining blocker to the separately frozen 50 ms matched performance probe.** This review inspected the narrow parallel-source diff and the proposed probe, and independently checked the saved synthetic arrays. It did not import or execute either kernel, rerun the producer, load the anatomical graph, or measure performance. The reviewer authored earlier input/source/data reviews, but neither recurrent kernel nor these producers.

The reproducible [review script](../scripts/review_inhibitory_recurrent_parallel.py) writes [the independent receipt](../validation/inhibitory-recurrent-parallel-independent-review.json). Its first execution passed; there was no failed review attempt or checker amendment. It refuses to overwrite the receipt. All inspected inputs were rehashed after review. The underlying [producer receipt](../validation/inhibitory-recurrent-parallel-checks.json) reports 103/103 checks and pins its pre-execution plan, sources, raw arrays, metadata and compiler report.

The parallel H loop reads native arrays and writes disjoint per-cell scratch rows, status bytes and worker IDs. The unchanged scalar helper is called without fastmath. The original serial loop then commits in ascending cell order, including threshold decisions and reductions. A failed interval stops that commit scan at the original first failing cell; speculative results for later cells are discarded. Refractory handling, direct input, delayed CSR delivery, source blocking and reset retain their order. All original class methods and other existing functions apart from `_run` are structurally unchanged by an independent AST comparison; the `_run` diff was read directly.

The saved [NPZ](../validation/inhibitory-recurrent-parallel-arrays.npz) and [metadata](../validation/inhibitory-recurrent-parallel-arrays.json) account for all **2,737 arrays**, including **1,358 paired array leaves** across **68 recursively compared objects**. Every paired array matches in dtype, shape and raw bytes; saved scalar values and JSON schema match. Coverage includes all four arms, whole and unevenly chunked runs, all output/checkpoint fields, changed source blocks, one versus four threads, and eight intentional failure cases. JSON archival normalizes tuples/lists and NumPy scalar types: exact original Python container types are supported by the producer's direct comparison, not independently recoverable from these JSON files.

Beyond pair equality, the review independently reconstructed eligibility from the saved own-cell spike history and fixed refractory durations, strict threshold decisions, candidate/applied masks, spike ordering, every delivered CSR event at its 18-tick delay, signed edge counts, final pending queues, reset values and whole/chunk concatenation. All 128 cells are selected in this bounded fixture, making those reconstructions possible without another neural run.

| Synthetic arm | Spikes in 300 ticks | Delivered edges | Pending source spikes at tick 300 |
| --- | ---: | ---: | ---: |
| C0 | 1,307 | 6,055 | 96 |
| C1 | 3,507 | 16,415 | 224 |
| H0 | 615 | 2,890 | 37 |
| H1 | 1,420 | 6,705 | 79 |

These are artificial fixture counts, with deliberately large positive weights and varied initial H state, not observations about MaleCNS or biology. Each H package's four corruption fixtures fails at the retained tick-5 attempted transition while reporting tick 5 as the completed-prefix boundary and transition 4 as the last completed transition. They retain the same first failure, prefix, partial output and native arrays as serial. In the multiple-invalid case, cell 1's earlier threshold crossing is retained, cell 5 fails first, and the later invalid cell 90 remains uncommitted. Continuation denial is supported by source and the producer receipt; this reviewer did not re-execute it.

The detached scratch evidence preserves all five native arrays byte for byte, including the injected NaN. It records 126 successful cells, one failure and one unavailable cell whose scratch row remains unwritten. Worker IDs 0–3 and the retained optimized `prange` compiler listing establish actual four-worker participation for that fixture. A Numba thread mask is runtime state, set explicitly by the caller. Extra scratch is 61 bytes per cell, allocated once per `advance` and reused each tick; integer inversion counts remain exactly representable in float64. Per-tick barriers, scratch traffic and serial commits can reduce the benefit. Failure work counters count committed operations rather than later speculative computation. No full-graph speed or exhaustive concurrency guarantee follows from the synthetic result.

The proposed [performance probe](../scripts/probe_inhibitory_recurrent_parallel.py) reuses the saved serial uniform stream, probabilities, input/selection arrays and logical RNG boundaries. Every arm starts afresh and executes ten 5 ms chunks. It requires byte equality for every numeric chunk array and final canonical array, plus each stored full-state digest. This checks numeric outputs, not all JSON metadata fields. Intermediate global arrays were not retained by serial, so their hashes remain producer summaries; final full arrays and selected intermediate arrays are available directly. The source keeps C arms serial, starts with explicit four-thread configuration and a separate tiny warmup, and compares against earlier serial timings. Those timings are sequential observations, not simultaneous paired measurements or confidence intervals.

One issue was corrected **before freezing or running this new probe**: an uncaught exception during the compiled call or wrapper return could leave mutable `net.tick` advanced. The failure record now retains `confirmed_prefix_end_tick` and its matching pre-call RNG boundary separately, marks the state incoherent, identifies mutable tick as unconfirmed, and prohibits resumption. This path was source-reviewed, not fault-injected in the new probe. The earlier frozen serial probe has the former ambiguity only under that uncaught-return scenario; its successful retained results are unaffected and were left unchanged.

The 600-second, 2-GiB-output and 8-GiB-peak-RSS limits are checked between operations. A single chunk, load or archival operation can overshoot; preflight hashing and final rehash/report work sit outside the execution budget. Abrupt process termination or severe allocation failure can prevent diagnostic archival. A failed numeric or resource gate must remain a failure, without parameter revision or continuing the scientific panel.

Reviewed SHA256 pins:

- Parallel kernel: `1d787238144c74df46512bd266bbaefb7fbf50caebd67c87343f292406cd23c6`.
- Serial kernel: `52892eabb7124dfe6140f7c0cbc4d9047301978c6706053e3230d72280ec2b0f`.
- Synthetic producer: `8fa0c9bc6ec5db9196c60ce3b4231e8d1a7d055a934d9b1dddf2554a4ca60951`.
- Synthetic plan: `a0df93152521b691de5bb9e3f2f63e967ac520f3b64c9bdd2fda28ff81c82268`.
- Synthetic receipt: `9c968800bf79edace82542566f525b407c801b1ab6077232a7b8e295cc0159a8`.
- Proposed performance probe, including the confirmed-prefix correction: `0827e7d55168e0844450512d70885607953d67145c7306b00f6e60442c7f106e`.

This establishes agreement on the retained implementation fixtures. The full-graph probe remains a separate test, and even a successful 50 ms baseline would not establish long-run stability, stimulus contrasts, physiology or a reason to promote H1.
