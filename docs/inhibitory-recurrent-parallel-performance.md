# Matched four-thread recurrent probe

**All 1,242 execution checks pass, including exact equality of every retained numerical chunk array and complete final canonical arrays against the serial probe.** The [frozen plan](../validation/inhibitory-recurrent-parallel-performance-plan.json) has SHA-256 `1ca89512d2e651329a13493469e5aa8e0d2f79e30bf850de004489fc142853d3`; the [results](../validation/inhibitory-recurrent-parallel-performance/results.json) have SHA-256 `0bc69e23b06a1f0265f9609c31f4cc3c5aa98080d3cff95b8d21f33f2c8340f9`.

The [parallel implementation](inhibitory-recurrent-parallel.md) precomputes independent H interval results with four Numba workers, then commits them in the original serial neuron order. Thresholds, source-ordered spike queues, synaptic edge order, direct inputs and failure ordering remain unchanged. No floating-point approximation or fast-math option is introduced. C0/C1 use the same serial path. The [103 synthetic checks](../validation/inhibitory-recurrent-parallel-checks.json), with raw comparison arrays retained, precede a [176-check independent source/artifact review](inhibitory-recurrent-parallel-independent-review.md).

The matched full-graph probe runs C0, C1, H0 and H1 for 50 ms each, seed 11, 11 Hz on the same 36 sources. It reuses the [serial probe's](inhibitory-recurrent-performance.md) exact uniform values, probabilities, selection and RNG boundaries. No source is blocked and no body runs. The configured Numba workqueue uses four threads; earlier synthetic worker-ID evidence confirms all four workers execute intervals.

| Arm | Serial kernel time (s) | Four-thread implementation (s) | Observed serial/new time ratio |
|---|---:|---:|---:|
| C0 | 0.9723 | 0.7925 | 1.23 |
| C1 | 0.8472 | 0.7796 | 1.09 |
| H0 | 3.0122 | 1.7465 | 1.72 |
| H1 | 3.5074 | 2.1216 | 1.65 |

These are separate single runs of the same protocol, not a repeated timing study. C0/C1 also run faster despite having no parallel integration; system/cache/timing variation therefore affects the ratios. H1's final 5 ms chunk takes 0.309 s here versus 0.738 s previously. This supports using the exact parallel path for the planned experiment, but not a precise forecast for stronger or longer recurrent activity.

The complete probe took 6.72 s. The last budget check recorded about 3.48 MB output and 486 MB peak process RSS; all resource limits held. Each H advance allocates 61 bytes of scratch per cell, reused across its ticks. Parallel workers can evaluate cells beyond the first failing serial index, but those speculative values do not mutate native state or become completed telemetry. Thread count is explicitly configured by the caller rather than changed on import.

Raw chunks retain all spikes, candidate/applied masks, selected states and ordered events, and per-tick global phase diagnostics. Final checkpoint comparisons include voltage, synaptic state, last spikes, refractory/source masks and valid pending queues. Intermediate full-state digests agree, but the serial run did not retain all intermediate global arrays; those digests remain producer summaries. The independent serial saved-data review already checks 48,000 selected H intervals with a separate time-domain integral.

The [independent saved-file comparison](inhibitory-recurrent-parallel-performance-independent-review.md) passes **1,859 checks** on its first attempt. It compares all 1,080 numeric array pairs across 40 chunks and eight initial/final checkpoints—59,483,960 uncompressed bytes on each side—and verifies all 77 source pins and 96 new artifact hashes. The new chunk metadata omits the serial runner's explanatory RNG note; the numerical streams and all other compared metadata agree. No model or producer was rerun for this review.

The reviewed runner records a separately confirmed pre-call clock/RNG boundary if an uncaught exception prevents a completed return. This avoids treating an already advanced mutable wrapper clock as a confirmed prefix. No exception or numerical mismatch occurred in the executed matched probe.

No neural model or production/body default is promoted. The next scientific test remains the three-seed, five-condition recurrent panel with stimulus withdrawal and all four factorial controls. The short baseline probe cannot establish physiological response amplitudes/timing, meaningful odor contrasts, seed robustness, or absence of uncontrolled persistent activity.
