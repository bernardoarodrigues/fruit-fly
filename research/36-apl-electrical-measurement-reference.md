# Electrical measurement functions prepared during acquisition

Completed 2026-09-05 UTC. The [Chen electrophysiology archive](35-apl-direct-electrophysiology-source.md) remains in acquisition. This step implements and checks the mathematical measurement functions needed after the complete archive is verified. It does not inspect partial recordings or establish biological parameters.

## Explicit measurement boundary

[apl_ephys_measurements.py](../scripts/apl_ephys_measurements.py) accepts times in seconds, voltage in mV and recorded current in pA. It requires callers to specify analysis windows and quality floors. It does not infer channel identity, liquid-junction correction, bridge compensation, genotype, cell identity, holding offsets, stimulus epochs or cohort membership. Those must be established from the complete recording inventory before application.

Windows are half-open `[start, stop)` and must lie inside a finite, strictly increasing record. Malformed arrays, overlapping baseline/response windows and insufficient samples are rejected rather than silently clipped. Numerical floors are required arguments; the illustrative values in tests are not scientific exclusion criteria for the forthcoming archive.

### Passive resistance

The function computes the mean plateau-minus-baseline voltage and current differences. Resistance is `1000 * delta_mV / delta_pA` in **MΩ**. The holding current cancels through the difference. The reported held baseline is deliberately not named resting potential, because Chen measures resting potential separately immediately after break-in.

Absent or insufficient current steps return an explicit unmeasurable result. Negative/nonpositive resistance is retained and flagged, rather than made positive by an absolute-value operation. Baseline voltage variation and plateau-current variation are also returned for later quality assessment.

### Passive transient

The descriptive fit is `V_inf + B exp(-(t - onset)/tau)` within a caller-declared transient window. For each positive time constant, linear least squares solves the two voltage coefficients. A logarithmic grid brackets interior minima for bounded refinement, with both supplied limits included as candidates.

The result retains the asymptote, extrapolated onset voltage, residual error, linear-design rank/conditioning and whether the optimum lies on a bound. A flat or insufficient-span voltage trace returns no time constant. These numerical diagnostics do not establish physiological identifiability or a valid cable capacitance. Instrument filtering, electrode artifacts, active currents and window choice still require examination in the actual data.

### Afterhyperpolarization recovery

The function measures the most negative voltage in a declared post-offset window relative to a declared preceding baseline. It preserves both the signed voltage deflection and positive AHP magnitude. Below the explicitly supplied amplitude floor, it returns no recovery interval.

For a detectable AHP, it retains every interpolated downward and upward crossing of 70% and 30% of peak magnitude after the trough. The first ordered recovery interval is reported with an ambiguity flag when either threshold is crossed repeatedly. Missing crossings retain an incomplete-window status. No smoothing or forced exponential is inserted.

Chen's cross-condition observation is a **70%-to-30% recovery interval**, not an exponential time constant. For a constructed single exponential, the interval equals `tau * log(7/3)`. Real AHP waveforms need not obey that relation. The code therefore returns the observed interval without automatically converting it into a kinetic parameter.

## Verification

All **six focused tests** pass. The [reference receipt](../validation/apl-ephys-measurement-reference.json) pins the implementation and tests and records the command.

The tests recover 120 MΩ from a constructed −50 pA /−6 mV step despite a nonzero holding current, and recover a constructed 10 ms exponential with known onset/asymptote. Three separate AHP decay examples verify the analytic 70%-to-30% interval. Other cases check absent input, flat voltage, weak AHP, incomplete recovery, repeated crossings and invalid time windows. The waveforms are unfiltered mathematical examples; **none of their parameter values is selected for the fly model**.

These functions are ready to support a fixed complete recording analysis after acquisition. Before fitting the source data, establish file-to-cell grouping, actual current commands, correction state, valid windows and source-compatible quality rules. In particular, resolve the source's +1 nA versus +2 nA panel protocols and retain low-amplitude normal-sleep AHP records explicitly. Cohort comparisons and parameter fitting remain pending; no partial-recording analysis, neural experiment or runtime change occurred.
