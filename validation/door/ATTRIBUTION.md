# DoOR evidence and anatomical crosswalk attribution

The DoOR-derived CSV tables, diagnostic image, and DoOR portions of the combined
crosswalks/results in this directory are released under **Creative Commons
Attribution-ShareAlike 4.0 International**:
https://creativecommons.org/licenses/by-sa/4.0/ .

Source: **DoOR.data**, Daniel Münch, C. Giovanni Galizia, Shouwen Ma, Martin
Strauch, and Anja Nissler; version 2.0.1.9001, commit
`db323a496577c4b4a72b5c2fcd1859e07521ffb5`:
https://github.com/ropensci/DoOR.data/tree/db323a496577c4b4a72b5c2fcd1859e07521ffb5 .
Its DESCRIPTION declares CC BY-SA 4.0. See Münch and Galizia (2016),
https://doi.org/10.1038/srep21841 , and the original studies individually
identified in `study-metadata.csv` and `selected-study-values.csv`.

Changes made here: parsing semicolon CSVs, selecting six chemicals and sixteen
study tables, retaining missingness, subtracting known consensus SFR values,
counting coverage, and joining exact glomerulus labels to MaleCNS metadata.
The crosswalk is an inference with documented exclusions, not a source-authored
cell assignment. Original study numbers are retained without unit conversion.
No endorsement by the source authors is implied.

**Separate Benton source:** `benton2025-identity-excerpt.csv` is a column subset
of Dataset EV1, Benton, Mermet, Jang, Endo, Cruchet and Menuz (2025),
*An integrated anatomical, functional and evolutionary view of the Drosophila
olfactory system*, https://doi.org/10.1038/s44319-025-00476-8 . This publication
and its supplementary dataset are under **CC BY 4.0**:
https://creativecommons.org/licenses/by/4.0/ . We extracted 65 identity rows
with their original Excel row coordinates; source parentheses, separators and
missing cells remain intact. This excerpt is not relicensed as DoOR data.

**Separate MaleCNS source:** body identifiers, labels, sides, nerve annotations,
and counts derive from MaleCNS v1.0, Berg et al., *Cell* (2026),
https://doi.org/10.1016/j.cell.2026.08.015 , under **CC BY 4.0**. The frozen
primary annotation URL and hashes are in `source-provenance.json`.
Combined DoOR/Benton/MaleCNS crosswalk tables are distributed as CC BY-SA 4.0
adaptations, retaining each source's attribution above.

**Code inspected only:** DoOR.functions commit
`15e415e4d84dfbbba6febefdfd0f2c1ddcf31cd6`, GPL-3 per DESCRIPTION:
https://github.com/ropensci/DoOR.functions/tree/15e415e4d84dfbbba6febefdfd0f2c1ddcf31cd6 .
The pinned R files remain in ignored `data/raw/door/functions` for source audit;
no function implementation is copied into project runtime or the audit script.

`source-provenance.json` records exact URLs, byte counts, SHA256s, and Git blob
hashes. `scripts/audit_door.py --download` retrieves only those frozen files.
No project-wide code license is currently declared. This data notice does not
grant a license for unrelated project code or assets.
