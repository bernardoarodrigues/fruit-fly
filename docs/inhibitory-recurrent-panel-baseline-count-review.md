# Independent baseline count and persistence audit

The first completed constant-baseline trial, `01-C0-seed11-constant_baseline` in `runs/20260905T060501089987Z-inhibitory-recurrent-panel`, contains **2,332,500 spikes**. An independent count-only audit passed **2,540 checks on its first execution**. The [script](../scripts/review_inhibitory_recurrent_baseline_counts.py) imports no producer metric, archive or neural code. It reads one packed spike array at a time, applies seven explicit half-open tick masks and accumulates integer counts with NumPy `bincount`. No simulation was run.

All 600 chunk completion records agree with their metadata and terminal-result artifact hashes. Each spike record is exactly 12 bytes: little-endian signed int64 tick followed by signed int32 graph index. The audit verifies packed and component checksums, graph-index bounds, strict tick/index ordering and contiguous 50-tick chunk coverage. The clock is 0.1 ms per tick. All **1,166,900** reconstructed per-neuron/window counters equal both the saved window-count matrix and the final checkpoint count matrix; result and terminal status and coverage end at tick 30,000. This checks counts, not the checkpoint's neural-state equations.

Source and motor identities are joined through the frozen selection and original Or42a plan to the pinned 166,700-neuron ID vector. There are 36 source cells and 166,664 non-source cells. The constant condition requests 11 Hz excitation events in every source column from 0 to 1.5 seconds, then zero through 3 seconds. These are imposed excitation events, not a biological afferent spike-rate clamp.

| Half-open time window (s) | Source spikes | Non-source spikes | Non-source mean rate (Hz/cell) |
|---|---:|---:|---:|
| [0, 0.05) | 30 | 83 | 0.009960 |
| [0.05, 0.5) | 193 | 155,500 | 2.073367 |
| [0.5, 1.0) | 198 | 420,148 | 5.041857 |
| [1.0, 1.5) | 196 | 440,068 | 5.280900 |
| [1.5, 2.0) | 0 | 438,307 | 5.259768 |
| [2.0, 2.5) | 0 | 440,585 | 5.287105 |
| [2.5, 3.0) | 0 | 437,192 | 5.246388 |

Rate means divide counts by the entire fixed cohort size and window duration, including silent cells. The receipt retains exact rational numerators and denominators. The three off-window population rates are exactly **876,614, 881,170 and 874,384 spikes/s**, with 11,827, 11,961 and 11,776 distinct active non-source cells. Requested events, applied events and actual source spikes are all zero in every off window. The last source spike is at tick 14,898 (1.4898 s). Across the full trial, there are 618 candidate events and 617 applied events; this audit counts the masks but does not attribute the rejected event to a neural transition.

| Fixed motor readout | Body IDs | Full-trial spikes | Off counts: early / middle / late |
|---|---|---:|---|
| Forward | 13805, 230783 | 0 | 0 / 0 / 0 |
| Turn left | 10442, 523769 | 0 | 0 / 0 / 0 |
| Turn right | 10360, 10760 | 1 | 0 / 0 / 0 |
| Feeding | 10331, 16949 | 151 | 25 / 29 / 28 |
| Escape | 10001, 10010 | 0 | 0 / 0 / 0 |

All feeding-group spikes come from cell 10331; cell 16949 is silent. Its individual off rates are therefore 50, 58 and 56 Hz, while the two-cell group means are 25, 29 and 28 Hz/cell. The single turn-right spike comes from cell 10760 in the baseline window. These are neural readouts, not observed feeding or body movement; motor groups are subsets of the non-source population.

The observed network activity persists during the complete 1.5-second input-off interval despite source silence: 1,316,084 non-source spikes occur after input stops. The last off-bin count is 1,115 lower than the first (about 0.254%); the middle bin is higher. Thus the three bins show continued activity without monotonic growth, not evidence of return to silence. They do not prove an indefinitely stable attractor, uncontrolled future growth, physiological plausibility, seed robustness or an arm comparison. The complementary active-state review assesses neural transitions separately. Neither result promotes H1.

The immutable [count receipt](../validation/inhibitory-recurrent-panel-baseline-count-review.json) is SHA256 `d135075625ed8a149336a21bd66e8a9e1f2664f7de8aa3901149fe8ecfc02c47`; the script is `55e20663383d849b4755c54927fa99a09cda3291e72c27db00373061112000ef`. The frozen panel plan is `c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5`; the completed trial result is `396731e5684f30e103070b78357157f0f6f7dc813b93748dd6a7e70cb70049cf`. The concatenated packed spike stream is `e82c8762dfdab73a9c9ffa16ddf5c94dfaaa0ff5d354fa6904d6d688ebeeb95e`, and the independently reconstructed count matrix is `3ceb29a230aaa5ef0c42ff6e98ae1aa11a55793cabc3dfb127504ac8ace3c9fd`. The receipt retains exact source/motor IDs, per-cell counts, source and selection hashes, and a digest of the 1,813 verified artifact receipts. Frozen experiment files were unchanged.
