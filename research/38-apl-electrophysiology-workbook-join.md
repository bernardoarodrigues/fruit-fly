# APL workbook identities, units and source arithmetic

Completed 2026-09-06 UTC. This follows the [complete archive/header inventory](37-apl-electrophysiology-inventory.md). All five APL workbooks were read without modifying them. The [extraction and join](../validation/apl-sk-workbook-join.json) retains source cell coordinates, values, formulas, cached values, comments, styles, hidden rows/columns and workbook hashes. The [independent review](../validation/apl-sk-workbook-review.json) checks the original XLSX XML and source arithmetic. No ABF voltage response was fitted in this step.

## Complete workbook groups

| Workbook and sheet | Author rows | Exact directory or filename joins | Fly IDs |
|---|---:|---:|---:|
| APL_NS_SD_RS_final.xlsx, intrinsic | 51: NS 20, SD 20, RS 11 | 49 | 50 |
| APL_SKRNAi_final.xlsx, intrinsic | 18: RNAi 7, control 11 | 18 | 17 |
| APL_SKRNAi_final.xlsx, AHP(2nA) | 11: RNAi 5, control 6 | 11 | 11 |

All 80 workbook observation rows are accounted for; **78 join exactly**, covering 169 of 171 APL ABFs. Observation rows are not independent animals: the intrinsic and AHP sheets reuse some cells, and some flies contribute two cells. Preserve the supplied fly ID when partitioning calibration/evaluation or estimating uncertainty. The 2 nA sheet includes `250612f02c01L`, which is absent from the intrinsic sheet; do not invent its intrinsic author measurements.

The NS/SD/RS workbook's numeric recovery entries are **17/18/11**, matching the paper's decay-panel counts. Five remaining entries explicitly say “Not found” or “not found” (three NS, two SD). They remain present rather than becoming zeros or disappearing from the amplitude cohort. Thirteen rows have after-NS8593 amplitude values: **six NS and seven SD**, matching the paired drug-panel counts. The `After NS8593` column N is a heading/separator, not a populated boolean flag; paired values are in O–V.

All eleven 2 nA AHP rows join to dedicated ABFs, with the same five RNAi and six control cells identified by their genotypes and source directories. Their epoch tables command 2,000 pA for 750 ms. The AHP(2nA) sheet nevertheless retains “@1000pA” in its E–G headers. Preserve that source inconsistency and use the actual command tables for protocol assignment.

## Units and correction state

**Resistance:** the NS/SD/RS `intrinsic!G` formulas divide the voltage deflection in F by −0.05; the RNAi workbook uses H and G respectively. For the stated −50 pA step, this is division by −0.05 nA, so the numerical result is **MΩ**, despite the header saying “Gohm.” For example, −6.26043 mV / −0.05 nA = 125.2086 MΩ = 0.1252086 GΩ. Importing the numeric 125.2086 as GΩ would introduce a factor-of-1,000 error. The original workbook remains unchanged; derived interpretation must explicitly carry MΩ.

**Resting voltage:** all 69 intrinsic rows have a formula subtracting **15.7 mV** from the preceding RMP column (NS/SD/RS column E from D; RNAi F from E). The authors' workbook thus distinguishes unadjusted and liquid-junction-adjusted RMP. This establishes the workbook operation, not whether every ABF ADC trace already contains an offset or what online bridge/capacitance compensation was applied. Do not subtract 15.7 mV again from the workbook's adjusted column. Compare raw break-in measurements with the corresponding unadjusted workbook column when checking the ABF correction state. Voltage differences used for resistance are insensitive to a constant junction offset.

**AHP:** retain the signed source deflection. Some post-drug entries are positive; these are not positive AHP magnitudes and must not be transformed with an absolute value. `AHP decay time` and `AHP decay tau (AHP)` are separate columns. The former is the source's 70%–30% interval; the unit and cursor implementation must still be checked against waveform timing before converting values to seconds. Comments on L35/L39/L40 preserve additional numbers without an explicit explanation; do not substitute those comment values for the recorded cells.

The cursor-region sheets preserve short/long/special firing-pattern windows and one dedicated AHP set. They are source cursor values, not a universal template for every sweep. One passive-deflection cell explicitly comments “From long protocol.” Reconstruct exact epoch boundaries and holding intervals per file before choosing measurement windows.

## Identity discrepancies retained

The initial directory-only inspection missed records whose cell and fly folders were reversed. Adding **exact filename-prefix matches within the same experiment folder**, while retaining both types of evidence, resolves these without fuzzy name edits. The initial directory-only extraction/script remain under ignored `tmp/apl-workbook-directory-join`; the final committed join records each matching method.

Two NS/SD/RS rows remain unmatched:

- `intrinsic!B10`: `240201f02c01R`. The deposit has `240201f02c01` files and directory under the same supplied fly ID, without a laterality suffix. This is a plausible identity association, not an exact join; it remains unresolved.
- `intrinsic!B15`: `240219f01c01R`. No matching APL ABF is present in the complete inventory. Its author summary remains available, but no raw trace is assigned to it.

Exact joins can still contain conflicting identity evidence. Examples include workbook/filename `240209f01c01R` under a directory ending L; workbook/directory `240711f02c01L` containing a firing-pattern file ending R; and workbook/directory `241024f01c01R` containing filenames dated `241023`. Other filenames omit digits or insert spaces. These cases require explicit flags in any calibration batch. An exact match to one field does not establish laterality or erase conflicting fields. Do not silently move files or fabricate a correction.

The short filename `241029f01c0L_IC_FP_NS_0001` corresponds to a workbook row with post-NS8593 values, but “NS” alone is not an unambiguous drug label. Preserve the workbook pairing evidence and verify recording order/protocol rather than treating every “NS” filename as drug exposure.

## Repeated nested source vector

The nested workbooks for `240716f01c02R` and `240729f02c01R` contain exactly the same **37 values in raw!B1:B37**. Their normalization baselines differ: the first averages B1:B10 and the second B1:B11. Their file bytes therefore differ, so whole-file hashing alone did not expose the repeated values. No conclusion is drawn about which recording generated that vector. Neither nested summary should be used as an independent physiological target until the raw ABF relationship is established. The third nested workbook contains 50 values and a separate baseline range.

## Verification and next action

A second parser reads the original XLSX ZIP/XML, independently expands the encountered shared formulas, and compares the populated values, formulas and cached values with the extraction. **3,367 checks pass**. Separate arithmetic recomputation verifies **164** RMP-correction, resistance and paired-AHP-difference formulas. No source workbook is saved or recalculated. Source styles and comments are preserved as evidence, without interpreting colors as an undocumented exclusion policy.

Next perform one complete raw protocol/measurement batch, with explicit identity flags and unmeasurable slots. Start with passive voltage differences and command delivery, where a constant junction correction cancels, and establish how break-in and held baselines map to the source workbook. Keep 500 ms firing-pattern and 750 ms dedicated AHP protocols separate; compare all eleven 2 nA cells together. Account for every sweep, acquisition order, recorded-current availability, repeated pulses and weak/non-AHP signals before fitting a graded leak/SK candidate. Preserve fly-level grouping and separate descriptive measurement from parameter calibration and evaluation.

The records remain mated-female ex vivo constraints transferred explicitly to a male simulation. Source consistency checks do not validate male local synaptic release, full-network dynamics or the visible body's behavior. H1 remains unpromoted; no E/I gain sweep, neural runtime change or Eon embodied integration occurred.
