# Independent review of feeding diagnostics

The retained results support a limited circuit-recruitment observation, with
correctly disclosed failure of the original closed-loop equality control. They
support no swallowing claim. No current result discrepancy was found in the
neuron identities, ordered afferents or neural-only replays.

[Reproducible review](../scripts/review_feeding_diagnostics.py) and
[receipt](../validation/feeding-independent-review.json) preserve source SHA-256
hashes, software versions, seeds **11/12**, parameters and results. The review
ran four fresh full-graph neural-only networks, using the saved 100 × 5 ms input
arrays for each seed. It did not rerun any body, modify source experiments,
change model parameters or control a live viewer. All **39** checks passed.

```sh
.venv/bin/python scripts/review_feeding_diagnostics.py
```

## What was independently verified

The current annotation exactly matches the complete saved catalogue: **48
`cb_motor` cells across 18 MN-number types**, plus `GNG588` cells **12617/14321**
with the literal synonym `Shiu 2022: Fdg`. Those two are intrinsic CNS neurons,
not additional motor neurons. An annotation correspondence does not independently
validate physiological identity, muscle targets or functional necessity.

Every retained afferent array can be reconstructed from its saved six-leg
contact state: 51 left then 54 right DM1/DM4 ORNs at zero input rate, followed by
the contacted LgAG2/LgLG4 groups in LF/LM/LH/RF/RM/RH order at 100 Hz. Initially
all six legs contact food, giving 159 listed inputs. Contact and input arrays
first change at **30 ms / 25 ms**, matching the baseline movement records. Muting
motor output therefore does not constitute a matched-input neural intervention.

The monitoring wrappers call the original `advance` once, return its original
batch, and only read/copy afterwards. No RNG is sampled by monitoring. Replays
reuse the saved seed, full graph, parameters and 5 ms chunk boundaries. Listed
zero-rate ORNs must remain: Shiu-style input still consumes one random draw per
listed target per tick and sets its refractory interval to zero. Inactive taste
cells are omitted and recover the default refractory setting. The review checked
every interval's full refractory array and found identical RNG states between
unblocked and Fdg-output-blocked networks at every boundary. This does **not**
require the sensory cells' resulting spikes to remain identical under recurrent
feedback.

Both historical baseline event lists, including neuron IDs and spike times,
match the recaptured baseline hashes. All four reruns exactly reproduce the
saved monitored event hashes, counts, all 100 voltage samples for the 50 cells,
sampled network minima and total-network spike counts. Newly recorded full-graph
event hashes are explicitly marked review-only: the original experiment did not
save full-graph event histories or all internal states for an equivalence claim.

## Findings and bounded recommendations

1. **Future exactness guard:**
   `scripts/check_feeding_afferent_replay.py:64` checks historical input hashes,
   counts and intake, while its field is named `baseline_reproduced_exactly`.
   It does not itself compare historical spike times, graph identity or saved
   neural parameters. The present review verifies these current artifacts, so
   the finding does not invalidate them. Guard these quantities on future runs,
   or name the checked observables explicitly. Also record the full drive
   contract if future encoders use current, custom input weights or a different
   refractory flag; the two recorded arrays suffice for today's defaults.
2. **Minor range wording:** the active conditions include seed 12 with Fdg
   outputs blocked at **−404.4786 mV**. The all-active sampled-minimum range in
   `docs/feeding-motor-expansion.md:88` is approximately **−404 to −437 mV**,
   rather than −408 to −437 mV. This changes no conclusion about the model's
   severe physiological failure.

Under the two frozen input histories, blocking both candidate Fdg cells' outgoing
synapses changes MN9 totals **3→0 / 3→1**. Incoming activity and spikes are not
silenced. Those effects are conditional on this uncalibrated network and its
input histories; no confidence interval, biological necessity or general
motor-program conclusion follows from two sparse-count seeds. No replay body or
intake prediction is present. The actual body lacks proboscis actuation,
mouth-fluid contact, pump dynamics and swallowed-volume measurement, so the
existing normalized intake remains an engineering interface.
