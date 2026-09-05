# Salman current-clamp source-data audit

The accessible data clarify the **direction of the Figure 3D discrepancy**, but do not yet provide a verified physiological calibration. The published plot and the saved Prism report show Keystone/il3LN6 lower than the two closer R32/Patchy and ABAF/Full groups, agreeing with the results prose rather than the caption's group comparison. Separately, **the figure's current axis differs by a factor of two from the methods/caption**. The Excel workbook is an incomplete cohort relative to the published sample count and contains an unexplained duplicated row. No correction, exclusion, regression fit or neural-model run was performed.

## Acquired source versions

The [OSF Figure 3d node](https://osf.io/sutz6/) exposes the original [Current Clamp analysis.xlsx](https://osf.io/sutz6/files/osfstorage/68d98abe626328f871d4e8fd) and [ALL CC pre DRUGS.pzf](https://osf.io/sutz6/files/osfstorage/68d98abe6282872a49d4eb0d). Both downloaded payloads match OSF's size, SHA-256 and MD5 exactly. Both are version 1, uploaded 2025-09-28. The workbook's internal created/modified dates are 2023-10-19 / 2024-02-01; these are metadata, not proof of when experiments occurred. The article was published in 2026, so repository placement alone does not establish final-publication identity.

| Original | Bytes | SHA-256 |
|---|---:|---|
| Current Clamp analysis.xlsx | 274,638 | `5e5fd1c48d372369ffdd5f269170d7ac612eedab39bf68233f9f59191cc96fb0` |
| ALL CC pre DRUGS.pzf | 381,637 | `55639979681a5a844cff00f24dd386bc99a3fcca5e54f90137741e158ce5d671` |

Files remain unchanged under ignored `data/raw/salman-current-clamp/`. The [acquisition receipt](../validation/salman-current-clamp-acquisition.json) copies the relevant file metadata from the root inventory's preserved incomplete version, so the audit does not depend on a subsequently replaced inventory. No RAR archive was downloaded.

## Workbook structure and formula verification

There are **24 visible sheets: 7 KS, 10 R32 and 7 ABAF**, with 24,912 nonempty cells. No cell text headers, units, native Excel tables, charts, comments or external workbook links were found; numeric formats are `General`. The sheet names supply preparation/cell labels, not globally unique specimen IDs or full metadata. In particular, `Prep 5 Cell 1 R32` / `Prep5 cell 2 R32` and the two `Prep 7` cells cannot automatically be treated as independent animals. Sex, age, exact patch-driver genotype and modern subtype are not encoded.

Across the sheets, columns B:K and N:W each contain ten numeric series over rows 1–31. A and M contain two different ascending numeric coordinates; their units are absent. L contains the row-wise mean of B:K. The formulas in X:AG subtract paired first-block values from second-block values, and X32:AG32 average each resulting series across 31 rows. Thus `N1 KS!X32` is `AVERAGE(X1:X31)`, where `X1=N1−B1`. Calling the two blocks baseline and stimulated voltage is a plausible interpretation, not a labeled workbook fact. The 31 rows are not a verified count of independent specimens.

The [read-only extraction](../validation/salman-current-clamp-extract.py) preserves the literal XLSX XML values, formulas, shared-formula attributes and saved formula caches in a compressed ignored audit file. A 50-digit Decimal calculation recomputes every formula from literal numeric inputs, including summary precedents. **All 8,434 caches are present and agree within 1e−10 workbook units; maximum absolute difference is 2.94e−14 or less.** There are no literal error cells or missing numeric values within B1:K31 / N1:W31. This validates arithmetic, not the provenance or correctness of the input values. Extra first-block rows on `Prep 7 KS` are preserved; its summary still averages rows 1–31.

The [240-cell summary CSV](../validation/salman-current-clamp-summary-values.csv) retains exact sheet/cell/formula locators and column ordinals. Current and unit fields remain empty because the workbook provides neither. The [results JSON](../validation/salman-current-clamp-results.json) records every sheet, descriptive means and missingness. It does not assign current steps or fit slopes.

One concrete anomaly is retained: **`Prep R32!B31:K31` exactly equals `Prep 4 R32!B31:K31`**. The largest preceding change is `Prep R32!G30→G31`, from −85.6781005859375 to −49.6368370056152, a difference of 36.0412635803223 in unlabelled workbook units. These values enter `Prep R32!X32:AG32`. This could reflect an export, selection or copy issue, but the source does not identify its cause. No value was replaced, no row removed, and no "corrected" result produced.

## Prism report and published figure

PZF is a binary project file. This audit only extracts readable report strings with byte offsets; it does not claim to decode its full data table, identities, current vector or statistical settings. Four retained copies of each group report agree. The [extraction JSON](../validation/salman-current-clamp-prism-text.json) preserves these strings and locations:

| PZF group label | Saved slope | Saved slope SE | Saved slope 95% CI | Saved equation |
|---|---:|---:|---|---|
| Keystone LNs | 0.02176 | 0.001279 | 0.01924–0.02429 | `Y = 0.02176*X + 0.1204` |
| R32 LNs | 0.03983 | 0.002090 | 0.03570–0.04396 | `Y = 0.03983*X + 0.01478` |
| ABAF LNs | 0.03754 | 0.002096 | 0.03341–0.04168 | `Y = 0.03754*X + 1.033` |

Its axis strings label input pA and output change mV. The saved global equal-slope report gives **F=27.93, DFn=2, DFd=504, P<0.0001**. This is an existing software report, not a new statistical analysis. No recovered pairwise comparison establishes that R32 and ABAF are equivalent; similarity of estimates or overlapping intervals does not prove equality. Degrees of freedom alone do not verify the underlying animals or correspondence to workbook sheets.

The exact [published Figure 3 image](https://cdn.ncbi.nlm.nih.gov/pmc/blobs/742a/13361993/7af553fdf374/nihms-2184600-f0004.jpg), linked from the acquired [PMC manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC13361993/), was saved with a hash and visually inspected. Panel D shows the gold il3LN6 curve below the closer green lLN2F_b and blue lLN2P curves, supporting the prose's direction. **Its x-axis explicitly labels −200, −100, 0, 100, 200, 300, 400, 500, 600, 700 pA**, whereas the methods and caption describe **−100 to 350 pA in 50 pA steps**. No point or error bar was digitized. The current discrepancy remains unresolved, and source slopes must not be converted into a calibrated resistance or assigned to a neural model.

The published figure reports 17 cells from 17 animals per group; the workbook supplies only 7/10/7 sheets. The PZF may contain additional records, but its table has not been decoded and no exact record join has been established. Consequently the data support a likely caption-label problem, while the exact published cohort, pairwise inference and physical current scale remain unverified.

## Next bounded evidence needed

Request an exported Prism data table and analysis settings, with specimen identifiers and its actual current vector; reconcile them with the original acquisition protocol and final Figure 3D. Clarify the duplicated R32 row and whether the workbook is a subset or an earlier analysis. Only then would slope/amplitude comparisons be quantitatively interpretable. Separate confirmation remains necessary for patch-recording sex/age and the R32 driver-to-`lLN2P_a/b/c` mapping. These files are current-clamp responses, not inhibitory synaptic transfer measurements or receptor-reversal assays.

Reproduction uses the bundled Python runtime with `openpyxl` for read-only analysis:

```sh
/Users/bernardo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 validation/salman-current-clamp-extract.py
```

The script refuses to overwrite outputs; use a clean copy with the original hash-verified sources and invoke its canonical absolute path. A clean-copy extraction reproduced all four outputs byte for byte, and a second invocation verified the overwrite refusal. The [validation receipt](../validation/salman-current-clamp-validation.json) also preserves an initial macOS `/var` versus `/private/var` temporary-path receipt failure, resolved by invoking the canonical path without changing the extractor or evidence. Artifact Tool separately inspected the workbook and representative ranges without exporting or modifying it; its inspector and output are retained with hashes in the acquisition receipt. Its inferred "table" summaries are not native Excel table objects. No original workbook edits, RAR downloads, parameters, runtime changes or simulations are part of this audit.
