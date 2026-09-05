# Independent saved-data review of the matched parallel probe

**Pass: 1,859 checks, with no mismatch or remaining review blocker.** The [review script](../scripts/review_inhibitory_recurrent_parallel_performance.py) compared the retained parallel probe against serial-v2 without importing a producer, executing a model, or collecting another timing measurement. The reviewer also authored the earlier parallel source/synthetic review, but neither kernel nor probe producer. Its first execution passed without a failed attempt or checker amendment; the [receipt](../validation/inhibitory-recurrent-parallel-performance-independent-review.json) retains all checks and input hashes.

The [frozen plan](../validation/inhibitory-recurrent-parallel-performance-plan.json) is SHA256 `1ca89512d2e651329a13493469e5aa8e0d2f79e30bf850de004489fc142853d3`. The [completed producer result](../validation/inhibitory-recurrent-parallel-performance/results.json), SHA256 `0bc69e23b06a1f0265f9609c31f4cc3c5aa98080d3cff95b8d21f33f2c8340f9`, reports 1,242 passing checks and no errors. All **77 pinned sources**, **96 parallel artifacts**, and the corresponding serial metadata files match their manifests. All inspected inputs were rehashed after review.

Across C0, C1, H0 and H1, all **1,080 numeric array pairs** match exactly in dtype, shape and bytes: 40 complete 5 ms chunk archives and eight initial/final checkpoint archives, totalling 59,483,960 uncompressed array bytes per side. This includes ordered spikes, candidate/applied masks, selected states and eligibility, event records, diagnostics, full endpoint voltage/synaptic state, refractory clocks, source masks and pending queues. Initial and final metadata also match exactly. Parallel chunk metadata omits only serial's explanatory `logical_rng_note`; every remaining field and schema value is identical.

Each arm reaches tick 500, or 50 ms, with the retained seed-11 uniform stream and matching logical RNG boundaries. Every chunk's completion, spike count and recorded state digest agrees with serial. The review independently regenerated all four final state digests from retained full arrays. Intermediate all-cell digests remain producer summaries because those full intermediate arrays were not archived; selected intermediate arrays and global diagnostic arrays are available and compared directly. This review does not repeat the prior independent serial numerical analysis.

Timing sums and the reported arithmetic ratios are correct:

| Arm | Earlier serial timed calls, s | New module timed calls, s | Observed earlier/new ratio | Spikes |
| --- | ---: | ---: | ---: | ---: |
| C0 | 0.972303 | 0.792535 | 1.227 | 113 |
| C1 | 0.847198 | 0.779610 | 1.087 | 2,861 |
| H0 | 3.012198 | 1.746516 | 1.725 | 99 |
| H1 | 3.507445 | 2.121584 | 1.653 | 150 |

These are sums of timed `advance` calls, including their wrappers and excluding subsequent hashing/archive work. Construction and the 0.161938 s warmup were reported separately. Both C arms also ran faster despite retaining their serial neural path. This demonstrates why the noncontemporaneous single-run observations cannot isolate a robust gain from threading, yield uncertainty intervals, or forecast the longer stimulus panel. No extra repeat or timing normalization was introduced after seeing these outcomes.

The full-graph producer records a successful four-thread-mask check and the `workqueue` layer. Actual worker IDs were retained only by the separately reviewed synthetic fixture; there is no new per-tick worker-ID trace for the anatomical graph. Reported execution wall time was 6.613421 s, with 6.723175 s through final hashing/report preparation. The last resource measurement recorded 486,359,040 bytes peak RSS and 3,481,912 output bytes, within the frozen limits. These historical measurements are producer evidence. They were taken between operations; they are not independently measured maxima here, and the output count excludes the final result write.

The result establishes exact saved-output agreement on one 50 ms constant-baseline run per arm. It does not establish later inhibitory workload, long-run stability, stimulus or seed robustness, physiology, or a reason to promote H1. The original engine, serial and parallel kernels, input streams, parameters and existing artifacts were left unchanged.
