# DoOR chemical-response evidence audit

DoOR can provide a chemical identity layer and partial receptor-response
evidence. Its consensus is **not a concentration-to-firing-rate encoder**.
This audit acquires small primary tables, preserves their provenance, and
identifies candidate MaleCNS populations. It changes no runtime sensor,
connectome, neural parameter, or behavior.

## Reproduction and frozen sources

From the repository root:

```sh
.venv/bin/python scripts/audit_door.py
# On a fresh checkout with the existing MaleCNS import available:
.venv/bin/python scripts/audit_door.py --download
```

The script verifies all source SHA256s and 48 Git blob hashes before parsing.
It downloads missing files only; an existing mismatched file fails rather than
being overwritten. The frozen set contains 49 files, **2,101,579 bytes** total:

| Source | Pin | Role |
|---|---|---|
| [DoOR.data](https://github.com/ropensci/DoOR.data/tree/db323a496577c4b4a72b5c2fcd1859e07521ffb5) | `db323a496577c4b4a72b5c2fcd1859e07521ffb5`, 2026-07-17, version 2.0.1.9001 | Consensus, chemical IDs, mappings, metadata, 16 selected unmerged study tables |
| [DoOR.functions](https://github.com/ropensci/DoOR.functions/tree/15e415e4d84dfbbba6febefdfd0f2c1ddcf31cd6) | `15e415e4d84dfbbba6febefdfd0f2c1ddcf31cd6` | Read-only normalization/baseline source audit |
| [Benton et al. 2025 Dataset EV1](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs44319-025-00476-8/MediaObjects/44319_2025_476_MOESM2_ESM.xlsx) | 97,614-byte publication supplement; SHA256 in receipt | Updated anatomical identity comparison, kept separate from DoOR |
| Retained MaleCNS v1.0 metadata | Existing `neurons.feather` and manifest hashes | Exact body IDs, type labels, source sides, nerves |

Raw files stay under ignored `data/raw/door`. The current DoOR commit uses
semicolon CSV with R row names, so no R installation or RData parser is needed.
The EV1 reader uses Python ZIP/XML support, selects text identity columns,
preserves 1-based Excel rows, and rejects formulas in those columns. It neither
recalculates nor interprets spreadsheet population estimates.

`validation/door/source-provenance.json` is the frozen acquisition manifest;
`results.json` records numerical checks and hashes of every derived CSV/image.
License and alteration notices are in `validation/door/ATTRIBUTION.md`:
DoOR derivatives CC BY-SA 4.0; Benton and MaleCNS sources CC BY 4.0 separately;
inspected DoOR.functions source GPL-3, not copied into runtime.

## What the numbers mean

The pinned consensus contains **691 rows × 78 responding units**, including the
`SFR` pseudo-stimulus, with **7,379 finite values and 46,519 missing cells**.
These measured file dimensions supersede the older counts in package help and
the 2016 paper. The other 690 entries are database stimuli; this does not mean
all are pure individual odor molecules. All unshifted consensus values lie in
[0,1]. `Or22c`, `Or24a`, `Or67d`, and `pb2A` are entirely missing.

The [2016 methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC4766438/) describe
merging heterogeneous response studies after normalization, followed by scaling
across responding units. The algorithm treats baseline as another stimulus;
calcium studies and studies that subtracted but did not report baseline receive
an SFR of zero. Low-overlap or poor-fit studies can be excluded, so missing or
weak consensus evidence need not mean absence of a strong ligand.

The pinned R implementations make the following distinctions explicit:

| Representation | Interpretation | Permitted use here |
|---|---|---|
| Individual `data/Or42a.csv`, etc. | DoOR's stored values grouped by source study, with source units/processing flags | Preserve exact values and source metadata; these are not individual trials |
| `door_response_matrix_non_normalized` | Merged, within-unit normalized consensus before global weighting | Dimensionless comparison; the filename does **not** mean raw rates |
| `door_response_matrix` | Consensus after global scaling across units | Dimensionless response profile |
| Consensus minus its known SFR entry | Deviation relative to that normalized baseline | Signed dimensionless contrast, never a negative physical firing rate |

`door_norm.R` performs min–max scaling; `global_norm.R` uses relative response
ranges and dataset coverage for cross-unit weights. `back_project.R` requires a
specified template dataset to recover its scale. None supplies a universal Hz
gain or gas-concentration calibration. Our script reads the stored consensus;
it does **not** claim to rerun or reproduce the original nonlinear merge.

Known-SFR subtraction yields **2,374 negative differences**. A missing baseline
remains unknown: all five missing-SFR columns stay NA after subtraction,
including 11 otherwise finite Or22b entries. This deliberately avoids the
upstream `reset_sfr.R` convention that substitutes zero for a missing SFR.
An odor below baseline can suppress a neuron's nonnegative firing rate; it does
not turn its outgoing synapses inhibitory. Preserve transmitter signs.

The unmerged tables still require a source-specific offset audit before use as
rates. For example, Hallem.2006.EN / Or47b stores SFR=47, ethyl acetate=40,
and acetic acid=26, while its metadata says SFR was subtracted in the source
study. These entries are consistent with a restored offset, but this audit did
not verify the import's restoration procedure against the original numeric
publication dataset. **No subtraction or restoration is applied to these raw
study values here.** The original flags and stored SFR remain separate columns.

## Chemical subset and missingness

This fixed illustrative set was selected for food/fermentation relevance,
before inspecting motor outputs. [Fischer et al. 2017](https://elifesciences.org/articles/18855)
provides primary fermentation-mixture context; selection here supplies neither
a complete food bouquet nor emission ratios, additive mixture responses, or
fixed attraction/repulsion labels.

| Audit label | InChIKey | PubChem CID | Consensus coverage / 78 |
|---|---|---:|---:|
| Ethanol | LFQSCWFLJHTTHZ-UHFFFAOYSA-N | 702 | 30 |
| Ethyl acetate | XEKOWRVHYACXOJ-UHFFFAOYSA-N | 8857 | 71 |
| Isoamyl acetate | MLFHJEHSLIIPHL-UHFFFAOYSA-N | 31276 | 55 |
| Acetic acid | QTBSBXVTEAMEQO-UHFFFAOYSA-N | 176 | 47 |
| Acetoin | ROWKJAVDOGWPAT-UHFFFAOYSA-N | 179 | 12 |
| Diacetyl | QSJXEFYPDANLFS-UHFFFAOYSA-N | 650 | 62 |

Source names and CAS numbers are retained; acetoin's identity does not specify
stereochemistry. `chemical-consensus.csv` retains all 468 chemical/unit pairs,
including NA, alongside both consensus forms, baseline, and known-baseline
difference. Its Hz field is intentionally NA. The diagnostic image displays
16 example units, not a complete independent-channel set.

The 16 unmerged tables expose 73 unit/dataset columns. For the six chemicals,
`selected-study-values.csv` retains **438 cells, of which 144 are finite**.
These are DoOR-stored source-study summaries, not trial replicates or a
complete acquisition of every responding unit's raw studies.

## Exact MaleCNS join and its limits

The retained `ORN_*` inventory contains **2,635 neurons in 53 type labels**.
`receptorType` is missing for every one. The joins therefore use exact
glomerulus strings from type names, without inferred suffix aliases or
assumed receptor expression. `male-orn-candidates.csv` preserves every body ID
once; candidate DoOR/EV1 rows are lists, preventing duplicate population counts.

The source `rootSide` counts are **L=883, R=1,343, unknown=409**. These identify
annotated peripheral root sides, not the hemisphere of every axonal terminal.
Unknown-side neurons remain explicit; the audit neither mirrors them nor
assigns them to the smaller side. Recorded asymmetry must not be converted into
an assumed biological receptor-count asymmetry. Nerves are AN=2,451 and
MxLbN=184. Somata/receptor-expression measurements cannot fill these gaps.

DoOR has 62 exact mapping rows covering 48 glomeruli, including the unknown `?`
receptor entry for VA7m. Coexpressed receptors and whole-sensillum recordings
can describe overlapping cells: Or33c, Or85e, and pb2A cannot be summed as three
independent VC1 populations. Pooled `ac1`, `ac2`, `ac3_noOr35a`, and ambiguous
`DL2d/v` labels are not split across cells. Larval-only units stay excluded from
adult candidates. The source duplicate ac3A mapping rows are retained.

| Palpal glomerulus | DoOR unit(s) | L / R / unknown | Nerve annotation |
|---|---|---|---|
| VM7d | Or42a | 18 / 18 / 0 | 36 MxLbN |
| VC2 | Or71a | 14 / 17 / 1 | 32 MxLbN |
| VC1 | Or33c, Or85e, pb2A | 13 / 15 / 1 | 29 MxLbN |
| VA7l | Or46a | 12 / 16 / 1 | 28 MxLbN + 1 AN |
| VM7v | Or59c | 11 / 14 / 0 | 25 MxLbN |
| VA4 | Or85d | 18 / 16 / 0 | 34 MxLbN |

The 185 cells in these six labels include a specific conflict:
**bodyId 125395**, ORN_VA7l, root L, is annotated AN. It is flagged and preserved,
not silently relabeled. Future physical sampling needs separate antennal and
palpal positions; an antenna-only odor sensor cannot stand in for all these
input organs without an explicit surrogate assumption.

The [DoOR maintainers' website](https://neuro.uni-konstanz.de/DoOR/content/DoOR.php)
warns that anatomical updates are missing. The separately acquired
[Benton 2025 EV1](https://doi.org/10.1038/s44319-025-00476-8) supplies newer
identity rows: palpal Or46aA versus antennal Or46aB/VA7m, Ir75b/DL2d versus
Ir75c/DL2v, and revised ab11 and coexpression labels. Parenthesized receptors
denote uncertain functional contribution, not an extra independently active
channel. Its new imaging/electrophysiology used females; the compiled resource
also includes sex-specific literature values. These identities are anatomical
evidence, not response-rate calibration for the MaleCNS donor.

`benton2025-identity-excerpt.csv` and the crosswalk keep this source separate.
The DoOR-only exact join misses DL2d, DL2v, VM6l, VM6m, VM6v; EV1 resolves the
first two label matches, but lists undivided VM6. **No VM6 subdivision is
invented, and no DoOR response is transferred from palpal Or46a to antennal
Or46aB.** New anatomical identities do not create absent chemical measurements.

## Assay provenance problems and smallest next experiment

The source metadata has 42 dataset rows and no sex field. Concentration is
often absent and otherwise usually a nominal liquid dilution, not a measured
concentration at an antenna. Electrophysiology, calcium signals, normalized
fluorescence, and EC50 values must not share one numerical transfer function.
The audit exposes these exact inconsistencies without silently repairing them:

- Raw `Muench.2016.AntGC1/AntGC3` columns do not exactly match metadata rows
  named `Muench.2015.AntGC1/AntGC3`.
- `Silbering.2011.AL` and `.AL_8a` say calcium imaging but list `spikes` as data type.
- `Nissler.2007.EC50` and `.nmr` dataset names disagree with their respective
  normalized-fluorescence/EC50 unit labels and require source review.

The best bounded next step is **one source-native single-odor response replay**,
not a mixture-driven foraging fit. First reconcile Or42a/pb1A baseline and mean
ethyl-acetate response against de Bruyne et al. 1999's original numerical data.
The [primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6782632/) used
Canton-S males aged 2–10 days for its main recordings, 500 ms odor pulses,
500 ms pre-stimulus subtraction, and generally 10^-2 dilution in paraffin oil;
the actual airborne concentration at the preparation was unknown. Its limited
male/female comparison does not establish sex independence for every channel.

Only after that offset check, a declared imposed-rate boundary could replay a
baseline and one 500 ms response into the **36 VM7d cells**, preserving both
18-cell sides and their actual outgoing connectivity. Hold out another
odor's peripheral response for validation; preserve no-input and
source-outgoing-suppression controls. A Poisson timing assumption would remain
an engineering choice: these mean summaries cannot validate adaptation,
latency, spike correlations or detailed trial variability. This audit performs
none of that simulation and chooses no rate/gain from downstream behavior.

A general chemical encoder still needs source-specific dose curves, delivery
and vapor measurements, baseline/solvent reconciliation, temporal responses,
organ-side geometry, receptor-coexpression decisions, and actual mixture
measurements. Missing cells must stay unknown rather than becoming zero.
With the present evidence, the defensible result is a versioned evidence table
and restricted single-odor assay boundary, not a complete olfactory model.
