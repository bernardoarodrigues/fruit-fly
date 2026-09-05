# Or42a / pb1A primary-assay boundary

The original paper supports a spontaneous rate and an ethyl-acetate response,
but **DoOR's exact restoration of the original baseline remains unverified**.
We can specify a transparent experiment using published summary numbers. We
cannot label it an exact reproduction of the original trial data or a
concentration-to-rate calibration. This audit runs no neural/body simulation
and changes no runtime input.

## Direct evidence and the offset question

[de Bruyne, Clyne and Carlson (1999)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6782632/)
used Canton-S males, age 2–10 days. Their 500 ms pulse response subtracts the
preceding 500 ms rate; the usual stimulus was a 10^-2 liquid dilution in
paraffin oil. Airborne concentration was unmeasured. Figures 5 and 6 summarize
different sample sizes, so their statistics must stay separate.

| Quantity | Primary result | Location / evidence |
|---|---:|---|
| pb1A spontaneous rate | 11 ± 1 spikes/s, SD; n=17 | Figure 6 numeric label and caption |
| pb1A ethyl-acetate rate change | +138 ± 32 spikes/s, SD; n=13 | Explicit Results text; Figure 5 |
| pb1A isoamyl-acetate rate change | Approximately +46.7 spikes/s; SD approximately 12.5; n=13 | Figure 5 raster estimate, **not an original numerical table** |

Or42a → pb1A → VM7d is the later DoOR/anatomical crosswalk, not a receptor
identification made by the 1999 paper; see the [existing audit](door-odor-audit.md).

The pinned `Bruyne.1999.WT` column in
[DoOR Or42a](https://github.com/ropensci/DoOR.data/blob/db323a496577c4b4a72b5c2fcd1859e07521ffb5/data/Or42a.csv)
contains SFR=11, ethyl acetate=147.647, isoamyl acetate=58.469, and solvent=18.583.
Its metadata marks source SFR subtraction and no solvent subtraction, and says
the data were updated from original data for DoOR 2.0.

| Comparison with primary Figure 5 | Ethyl acetate | Isoamyl acetate |
|---|---:|---:|
| DoOR stored value | 147.647 | 58.469 |
| Stored minus DoOR SFR | 136.647 | 47.469 |
| Primary delta reference | 138, explicit text | 46.679, raster estimate |
| Residual if SFR was restored | −1.353 | +0.790 |

These numbers are consistent with restoration. They **do not prove its exact
arithmetic or identify the original averaging cohort**. In particular,
147.647 is neither the published delta of 138 nor 138+11=149. We do not silently
round away that difference, call SFR=11 an individually matched baseline, or
add 11 a second time to the stored DoOR response. The solvent's candidate
delta, 18.583−11=7.583, also remains separate from spontaneous activity.

The current 18 finite entries exactly match the
[2015 reintroduction commit](https://github.com/ropensci/DoOR.data/commit/7c24180d0202fc0dc5f81191c1093f11e9987467).
That commit restores already processed summary columns; it supplies no
pre-import trial table or transformation script. The inspected pinned tree
has no de Bruyne original trial directory. The current generic
[`import_new_data.R`](https://github.com/ropensci/DoOR.functions/blob/15e415e4d84dfbbba6febefdfd0f2c1ddcf31cd6/R/import_new_data.R)
rounds/imports supplied values and has no explicit spontaneous-rate restoration
operation. This is not proof about a historical manual preprocessing step.
The [DoOR 2.0 methods](https://www.nature.com/articles/srep21841) describe SFR
handling in the consensus and author-supplied updates, but do not resolve this
specific column's original per-trial offset.

## Held-out odor and reproducible extraction

Isoamyl acetate is a second chemical with an inspectable primary Figure 5
response. Its chemical key is `MLFHJEHSLIIPHL-UHFFFAOYSA-N`, CID 31276; DoOR calls
it isopentyl acetate. Reserve this response from any future ethyl-acetate
parameter selection. A fixed lookup replay of its imposed rate would test
transport/boundary behavior; it would **not** be held-out prediction by a
chemical-response model, since no such model was fitted here.

The extraction uses the unscaled 786×1199 Figure 5 JPEG. We visually inspected
it in the browser, then selected black vertical edges using luminance below
80/255 in fixed row windows. Five tick midpoints map pixels to Hz by a linear
fit. The ethyl-acetate mean/SD reconstructed this way agree within 1 Hz with
the explicit text, providing a useful independent check of scale and bar
identity. Isoamyl acetate's mean spans **45.26–48.08 Hz** when every chosen
tick and bar endpoint is perturbed by ±1.5 pixels. This is a digitization
sensitivity range, not a confidence interval, measurement SD, or evidence that
systematic printing/rounding error is absent. The SD estimate has additional
cap-reading uncertainty and is not used as a precise distribution parameter.

```sh
.venv/bin/python scripts/audit_or42a_primary.py
```

The script verifies 11 source-file hashes, all 18 historical/current values,
bar-edge evidence, the explicit-text check, and the exact 36-cell MaleCNS join.
`validation/or42a-primary/results.json` keeps the unresolved offset check
**false**. It is not converted into a passing experimental result. The source
manifest preserves image dimensions, manual coordinates, methods, URLs, bytes,
and SHA256s; the generated CSVs retain study, figure, chemical and error-type
distinctions. The local paper copy is the full PMC HTML under
`data/raw/or42a-primary/PMC6782632.html`. The linked PDF returned an HTML
challenge, and the publisher PDF returned 403, so no PDF acquisition is claimed.
Images were retained locally for numerical provenance, not redistributed.

## Proposed bounded experiment, requiring review before execution

The least ambiguous first boundary is an explicitly named **primary-summary
rate replay**: 11 Hz spontaneous, 149 Hz total during ethyl acetate, and about
57.7 Hz during isoamyl acetate. The totals combine the Figure 6 baseline with
Figure 5 deltas. They are engineering combinations of different summary
cohorts, not reported matched-cohort total firing rates. A stricter exact-data
reproduction must remain pending the original trial/mean table and baseline
preprocessing record.

1. Freeze the 36 `ORN_VM7d` body IDs in `male-vm7d-population.csv`, ordered by
   numeric body ID. They are exactly 18 left/18 right and all MxLbN. Stimulate
   both palpal sides uniformly as a declared laboratory boundary; do not sample
   this receptor from the existing antenna-only odor positions.
2. Use fresh initial states for each condition: no imposed input, constant
   baseline, baseline→ethyl acetate→baseline, baseline→isoamyl acetate→baseline,
   and the ethyl-acetate condition with all selected source outgoing delivery
   suppressed. Suggested windows are 0–0.5/0.5–1.0/1.0–1.5 s. The final window
   is an imposed return to baseline, not a validated biological recovery curve.
   Independent trials avoid pretending this is the paper's repeated-odor
   protocol. Fix three RNG seeds before running; seeds are simulation draws,
   not independent animal replicates.
3. Declare what is imposed. The current `PoissonDrive` is an external excitation
   event stream, not a source-spike clamp. Recurrent effects and membrane
   integration can make actual VM7d spike counts differ from its nominal Hz.
   Count requested events, actual source spikes, outgoing deliveries and
   downstream responses separately. Do not certify the published afferent
   rate merely because the configured drive number matches it. Exact
   presynaptic spike replay would need a separately reviewed boundary.
4. Keep the same ordered input list, including zero rates, across controls;
   preserve existing model timing/refractory semantics. Outgoing suppression
   must retain the sources and imposed events while blocking their delayed
   output. Do not alter transmitter signs, synapse strengths, or motor thresholds.
5. Predeclare numerical/timing/identity checks. Report neural propagation and
   known voltage failures independently of walking/feeding outcomes. No motor
   outcome may select an odor rate, fill missing channels, establish attraction,
   or promote a complete chemical encoder.

This would move toward an empirically bounded olfactory input while preserving
the remaining tasks: original offset reconciliation, airborne dose calibration,
adaptation and timing, palp geometry, other receptor classes, and mixtures.
