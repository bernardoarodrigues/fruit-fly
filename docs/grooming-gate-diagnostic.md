# Full-graph grooming gate positive control

The fixed **40 Hz direct probe supplies a continuous gate long enough for
250 ms entry plus 500 ms playback in both tested seeds**. This is a neural
scheduling check; it does not establish successful body playback or spontaneous
sensory-driven grooming. No gains, thresholds or default settings were changed.

## Protocol and exact runtime correspondence

`scripts/check_grooming_gate.py` runs the complete retained MaleCNS graph with
the baseline Shiu LIF dynamics for 1.25 seconds, at each prespecified direct
input rate 0, 40 and 100 Hz, using seeds 11 and 12. The probe targets the exact
left group selected by the runtime: DNg62 body ID **13624** and DNge078 body ID
**14537**. The graph and source-code hashes, parameters, selected input IDs,
spike times and 5 ms state/readout samples are saved in
[validation/grooming-gate.json](../validation/grooming-gate.json).

The actual `SensoryEncoder` supplies **105** zero-rate ORNs, ordered 51 left
then 54 right, followed by the two probe indices. There are 106 DM1/DM4 cells
before the side selection; the unassigned-side cell is excluded by the runtime.
This check uses the encoder directly instead of manually constructing a
106-cell group. Taste and proprioceptive input are absent, matching the probe
configuration. Zero-rate entries remain in the input vector: the Shiu engine
consumes a random draw per listed input per timestep, and applies its declared
refractory override to listed direct-input targets even when their rate is zero.
Omitting these entries would change both random-number assignment and that
override.

The actual `MotorDecoder` averages the two cells' spike counts over each 5 ms
interval and updates its 50 ms exponential rate filter. Grooming is requested
when the filtered mean is strictly greater than 10 Hz. There is no hysteresis
in this check. The same compile-then-reset sequence used by `SimulationRunner`
precedes every trial. Output recording is restricted to decoder neurons;
propagation and network spike counts still cover the entire graph.

## Results

Spike counts are actual neuronal outputs during 1.25 seconds, not input events.
Late metrics exclude the first 100 ms. Gate intervals refer to held body-action
time: the preceding 5 ms neural update supplies each action, as in the runner.

| Input Hz | Seed | DNg62 / DNge078 spikes | Gate fraction after 100 ms | Longest gap after 100 ms | Longest uninterrupted gate | Minimum late filtered rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 11 | 0 / 0 | 0% | 1150 ms | 0 ms | 0 Hz |
| 0 | 12 | 0 / 0 | 0% | 1150 ms | 0 ms | 0 Hz |
| 40 | 11 | 252 / 185 | 100% | 0 ms | 1230 ms | 59.41 Hz |
| 40 | 12 | 234 / 183 | 100% | 0 ms | 1245 ms | 39.88 Hz |
| 100 | 11 | 335 / 244 | 100% | 0 ms | 1240 ms | 127.20 Hz |
| 100 | 12 | 329 / 255 | 100% | 0 ms | 1250 ms | 171.88 Hz |

At 40 Hz, the seed-11 gate lasts from 20 to 1250 ms, and the seed-12 gate from
5 to 1250 ms. Neither trial contains a gate withdrawal after its first onset.
Both therefore meet the uninterrupted 750 ms scheduling requirement. The two
seeds establish these specific outcomes; they do not guarantee persistence for
every seed or any later stimulus history.

## Voltage and interpretation limits

At 40 Hz, DNg62 outputs 201.6 / 187.2 Hz and DNge078 148.0 / 146.4 Hz for seeds
11 / 12. Input Poisson rate does not impose that same neuronal output rate:
network recurrence and the Shiu direct-voltage/refractory semantics contribute.
The probe is an explicit intervention, not a peripheral sensory stimulus.

| Input / seed | Network sampled minimum | DNg62 sampled minimum / final | DNge078 sampled minimum / final |
|---|---:|---:|---:|
| 0 / both | −52.00 mV | −52.00 / −52.00 mV | −52.00 / −52.00 mV |
| 40 / 11 | −477.08 mV | −79.76 / −52.00 mV | −70.95 / −48.51 mV |
| 40 / 12 | −484.52 mV | −90.12 / −49.70 mV | −76.79 / −54.97 mV |
| 100 / 11 | −463.38 mV | −71.79 / −46.11 mV | −58.59 / −53.33 mV |
| 100 / 12 | −479.99 mV | −63.63 / −47.69 mV | −58.46 / −51.86 mV |

All states remained finite, but the extreme network hyperpolarization is
physiologically implausible and consistent with the documented limitations of
transferring the current-based Shiu parameters to this male graph. Voltages were
sampled at 5 ms coupling boundaries; these are sampled extrema, not guaranteed
extrema across every 0.1 ms integration step. The JSON also retains each probe
cell's mean voltage, all sampled voltages and exact spike timestamps.

No body physics was run here. A successful motor-template trial still requires
entry, grounded posture, valid playback and completion to be checked by the body
assay. The result supports using the existing 40 Hz setting for that bounded
positive control without claiming biological calibration or changing its value.

Reproduce from the repository root:

```sh
.venv/bin/python scripts/check_grooming_gate.py
```
