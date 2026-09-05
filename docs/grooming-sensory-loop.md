# Imposed JO-F activation coupled to the body

This optional assay tests whether imposed activity in an audited antennal
sensory population reaches the full graph's grooming readout and gates the
existing recorded motor template. It does not convert physical touch, dust, wind,
or antenna deflection into neural input, and does not validate natural grooming.

Use `configs/male-grooming-sensory-probe.json`. The input is fixed at 100 independent
Poisson events per second per selected cell, with unchanged Shiu parameters,
5 ms coupling, and the existing 50 ms motor filter and strict >10 Hz threshold.
These are declared engineering choices, not fitted sensory firing rates.

The exact source union is `JO-FD1`, `JO-FD2`, and `JO-FV`, selected from left
`AN` entries. Its 42 body IDs and ascending graph-index order are checked against
the audited list in `fruitfly/simulation.py`. The actual 105 zero-rate odor input
indices come first (51 left, then 54 right), followed by the 42 JO-F cells. This
preserves the neural audit's RNG draw order. Taste and proprioceptive input
adapters must be disabled and both odor baseline and increment must be zero.
No descending neurons receive external events. Run manifests retain all 147
ordered input IDs, probe rate, graph provenance, code hashes, and body settings.

The [neural route audit](grooming-sensory-route.md) provides the primary-source
crosswalk and exact annotations. Hampel's older aJO terminology maps to JO-F, but
the correspondence between older F subgroups and male FD1/FD2/FV remains putative.
The anatomical union includes two FD2 cells annotated `wind_gravity`. Experimental
drivers additionally label a sparse JO-EVP population, which is not included
here. The adequate natural JO-F stimulus remains unresolved. Left inputs also
activate right grooming DNs in the neural audit; selecting a left readout and
left recording does not establish biological laterality.

The body uses the female-derived NeuroMechFly morphology and the measured female
motion template already documented in [grooming-loop.md](grooming-loop.md).
Antennae remain rigid, actuation and adhesion are engineering approximations,
and the motion plays once per sustained request. The Shiu baseline retains large
input voltage jumps, disabled refractory periods for all listed input cells
(including zero-rate ORNs), and implausible hyperpolarization elsewhere in this
male graph. No parameters are tuned to make this assay succeed.

## Reproducible controls

```sh
.venv/bin/python scripts/validate_grooming_sensory_loop.py
```

The fixed protocol runs seeds 11 and 12 for 1.4 simulated seconds each under four
conditions: zero input, 100 Hz JO-F input, 100 Hz with motor readout muted, and
100 Hz with JO-F outgoing synapses blocked. The latter uses:

```python
runner.control({"type": "synaptic_output", "group": "grooming_sensory", "blocked": True})
```

This intervention preserves incoming connections, input events, and source
spikes, and is retained across reset. The validation records chronological
source spike-train hashes, per-cell source counts, left DN counts, every 5 ms
body/gate observation, final states, and manifest hashes. It checks brain/body
clock agreement, finite states, and resource conservation. The paired hashes
compare exact source spike times, not only firing-rate averages.

Results are saved under `validation/grooming-sensory-loop/`; raw experiment logs
and manifests remain in their recorded `runs/` directories. Failure retains the
evidence and exits without changing rates, thresholds, or other parameters.

## Observed result

All 18 prespecified causal checks passed across the two seeds. At 100 Hz input,
each body completed one playback, then stood in the `held` phase without
repeating under the tonic request. All three control conditions had no playback
and zero foreleg/antenna contact time.

| Seed | JO-F source spikes | Left DNg62 / DNge078 spikes | Contact time | Sampled minimum voltage |
|---|---:|---:|---:|---:|
| 11 | 5,871 | 116 / 104 | 0.4082 s | −483.97 mV |
| 12 | 5,840 | 140 / 120 | 0.4085 s | −477.73 mV |

Motor muting preserved the exact source spike trains and left-DN counts.
Blocking JO-F outgoing synapses preserved the exact source spike trains and
eliminated every downstream spike. Zero-input trials were silent. These results
support a causal route in this specified computational model and its selected
motion adapter; the voltage extrema preclude claiming calibrated neuronal
physiology. Extrema were sampled every 5 ms, not continuously.

The real rendered phases are saved in
`validation/grooming-sensory-loop/sensory-frames.png`. The full evidence is in
`validation/grooming-sensory-loop/results.json`, including both seeds, controls,
ordered source identities, spike-train digests, and all timing checks.
