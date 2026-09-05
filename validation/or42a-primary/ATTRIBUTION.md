# Source and alteration notice

`door-study-comparison.csv` and the DoOR-derived fields in `results.json` are
adaptations of **DoOR.data**, Daniel Münch, C. Giovanni Galizia, Shouwen Ma,
Martin Strauch, and Anja Nissler, under **CC BY-SA 4.0**:
https://creativecommons.org/licenses/by-sa/4.0/ . They are distributed under
the same license. The current and historical commits, source URLs and hashes
are in `source-provenance.json`. Alterations: selecting one study column,
comparing versions and showing a explicitly conditional baseline subtraction.
No endorsement by the source authors is implied.

Primary numeric evidence: de Bruyne M, Clyne PJ, Carlson JR (1999),
*Odor Coding in a Model Olfactory Organ: The Drosophila Maxillary Palp*,
J Neurosci 19:4520–4532. https://doi.org/10.1523/JNEUROSCI.19-11-04520.1999 .
Copyright 1999 Society for Neuroscience. The paper HTML and figure images
remain ignored local research copies; no license to redistribute those
original files is asserted. `figure5-estimates.csv` records our approximate
numeric raster measurements and their uncertainty, not original trial data.

`male-vm7d-population.csv` contains MaleCNS v1.0 body IDs and annotations,
CC BY 4.0, Berg et al., Cell (2026),
https://doi.org/10.1016/j.cell.2026.08.015 . Extraction: exact `ORN_VM7d` type
selection and numeric body-ID sorting; source side and nerve strings retained.
The imported metadata's hash is recorded. Anatomical receptor assignment
limitations remain in `docs/door-odor-audit.md`.

DoOR.functions GPL-3 code was inspected only and remains in the ignored source
cache. No source function implementation is copied into project code. This
notice grants no license for unrelated repository files.
