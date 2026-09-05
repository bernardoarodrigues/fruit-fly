# Camera facets to MaleCNS visual cells: registration boundary

The camera can be calibrated, the male column identities can be checked, and a published female optical template can be extracted. **An exact male column-to-viewing-direction registration is not yet established.** No visual direction was assigned to a MaleCNS neuron and no runtime input or weight was changed in this audit.

## Firm anatomical link in the retained male graph

Nern et al. (2025), [*Connectome-driven neural inventory of a complete visual system*](https://www.nature.com/articles/s41586-025-08746-0), describes the right optic lobe of a male; the lamina is incomplete. Its released columns are anatomical assignments, not recorded receptive fields. The accompanying [source repository](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/tree/dbafc73124b5c96e96429cdf2a89d067cae841bc) is pinned at `dbafc73124b5c96e96429cdf2a89d067cae841bc` and its configuration names `optic-lobe:v1.1`.

The small [official column CSV](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/dbafc73124b5c96e96429cdf2a89d067cae841bc/results/exchange/ME_assigned_columns.csv) contains 13,267 cells in 892 unique columns. Every body ID, cell type, side and hex pair agrees with the corresponding retained MaleCNS metadata. All are right-side cells. This directly verifies reuse of those right-side column identities; it does not verify the left columns or any optical angle. The [registration audit](../scripts/audit_visual_registration.py) reproduces this join and records source hashes in [its receipt](../validation/visual-retinotopy/registration-boundary.json).

The spreadsheet `params/ME_columnar-cells_location.xlsx` describes these as manual visual assignments by Kit D. Longden. The [coordinate documentation](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/dbafc73124b5c96e96429cdf2a89d067cae841bc/docs/coordinate-systems.md) sets an arbitrary positive hex origin, places the p/q origin at `[hex1,hex2]=[18,19]`, and describes H as approximately aligned with the perceived horizon. Its rendered diagram labels `hex1→q` and `hex2→p`. These are grid conventions, not degrees.

The [column-pin implementation](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/dbafc73124b5c96e96429cdf2a89d067cae841bc/src/utils/ROI_columns.py) constructs internal neuropil trajectories from assigned cells' synapses, principal components, ROI boundaries, smoothing and interpolation. The `[x,y,z]` pin coordinates and normalized depth are **not optical ray directions**. Cached ME pins are available as a roughly 2.93 MB pickle or an 8.10 MB CSV; no large pin reconstruction or unsafe pickle loading was needed here. Recomputing them is unnecessary for the current registration question.

The existing [R1–R6 connectivity audit](../scripts/audit_visual_columns.py) infers 1,064/1,112 left photoreceptors across 286 columns and 2,053/2,265 right photoreceptors across 486 columns by same-side L1/L2 consensus. It is a useful target-cartridge inference, not proof of a photoreceptor's lens of origin. Neural superposition pools photoreceptors from different ommatidia that sample the same direction into one cartridge; see the primary study [*The Developmental Rules of Neural Superposition in Drosophila*](https://pmc.ncbi.nlm.nih.gov/articles/PMC4646663/). A future input assigned by target cartridge must retain that interpretation. Seven or eight photoreceptors can occur near the equator; counts above six alone do not establish an annotation error.

## A real optical bridge, with a different sex and specimen

Zhao et al. (2025), [*Eye structure shapes neuron function in Drosophila motion vision*](https://pmc.ncbi.nlm.nih.gov/articles/PMC12488493/), estimates viewing directions from whole-head micro-CT and maps them to female FAFB medulla columns using the eye equator and lattice landmarks. The micro-CT specimens were 6–7-day-old females; this is not a scan of the MaleCNS donor. It is nevertheless a substantially better optical surrogate than uniform angles on an invented hex grid.

The [author repository](https://github.com/reiserlab/eyemap_T4/tree/99d2a43123db636cedb55af9ff31a59657e7d17e) is pinned at `99d2a43123db636cedb55af9ff31a59657e7d17e`. The saved `20240701` scan contains 1,709 lenses: 857 left and 852 right. The main [registration code](https://github.com/reiserlab/eyemap_T4/blob/99d2a43123db636cedb55af9ff31a59657e7d17e/proc_eyemap.R) selects the right eye and pairs 778 of its lenses with 778 of 779 FAFB Mi1 array entries by their lattice coordinates. Those identifiers are **one-based R array indices**, not MaleCNS body IDs.

[The extraction script](../scripts/extract_zhao_eye_template.py) reads the small saved RData objects without executing author R code. It produces [852 female right-eye direction rows](../validation/visual-retinotopy/zhao-female-right-eye-directions.csv) and a [provenance/check receipt](../validation/visual-retinotopy/zhao-extraction.json). Every one of the 778 matched rows has exactly the same optical direction in the full micro-CT artifact and the embedded EM map, and every paired p/q coordinate agrees. The unit-vector normalization error is at most `2.22e-16`.

Important source details:

- [The optical processing code](https://github.com/reiserlab/eyemap_T4/blob/99d2a43123db636cedb55af9ff31a59657e7d17e/proc_uCT.R) matches annotated lens and photoreceptor-tip positions by a minimum-cost assignment, estimates a head basis from equator landmarks and both eyes, smooths positions and directions locally, and normalizes the lens-minus-tip vectors. These are geometric estimates processed by the authors, not directly recorded neural receptive fields, lens surface normals, or empirically measured acceptance kernels.
- The saved Cartesian convention is x forward, y left, z dorsal. The derived CSV uses `atan2(y,x)` for azimuth, positive to the left, and `asin(z)` for elevation. The plotting functions intentionally negate y for an inside-out view; importing a plotted azimuth without accounting for this would mirror the registration.
- The coherent map embeds an **852-row** `lens_ixy`; the separately released `data/lens_ixy.RData` has **786 rows** and must not be substituted. `utp_lens_rot` contains sphere-projected lens positions, not viewing directions. The `*_aux` objects contain 39 generated boundary-support points and are excluded.
- Nine upper-equator markers lie on `p+q=0`; ten lower markers lie on `p+q=-1`. In this template, grid origin `[0,0]` is right lens index 395 and points to approximately azimuth −53.568°, elevation +5.329°. A grid equator or central origin must not simply be assigned elevation 0° or azimuth ±90°.

The extracted raw files are kept under `data/raw/visual-retinotopy/zhao2025/`. Reproduction requires no complete R installation:

```sh
uv pip install --target /tmp/fruitfly-retinotopy-deps --no-deps rdata==1.1.0 xarray==2026.7.0
.venv/bin/python scripts/extract_zhao_eye_template.py --rdata-path /tmp/fruitfly-retinotopy-deps
.venv/bin/python scripts/audit_visual_registration.py
```

The existing environment supplies NumPy, pandas and SciPy. No project dependencies were changed. The author repositories declare GPL-3.0; retain their provenance and licensing when redistributing source-derived data. This audit does not vendor their implementation into the runtime.

## Why no male angular assignment was selected

The Nern diagram displays +p toward the upper left and +q toward the upper right. Zhao's plotted hex basis uses the opposite display arrangement. A drawing reflection does not prove an anatomical reflection. More fundamentally, the retrieved tables do not provide an exact homologous central-meridian column and upper-versus-lower equator correspondence between the male grid and the female optical specimen. Anatomical equator evidence is stronger than centring two outlines, but it must be attached to exact rows and anterior/posterior orientation before selecting a transform.

The audit receipt enumerates the 12 symmetries of a hex lattice without ranking them. If a shared positive vertical diagonal is imposed, only identity and p/q exchange remain; that conditional constraint still leaves reflection and origin unresolved. Translations `(k,-k)` preserve an equator row, and confusing its two bordering rows adds a one-row phase ambiguity. Different cell counts and local lattice defects also mean that a single rigid lattice transform is only a candidate model. None was chosen by overlap count, visual appearance or useful neural output. Left-eye registration would require its own evidence rather than an automatic mirror of the male right map.

## Smallest next registration experiment

First use the extracted female optical template as a **declared body-optics surrogate only**: in an isolated, fixed-head scene, render achromatic targets along a few published template directions spanning front, dorsal and posterior regions, and compare observed facet responses with predictions from the calibrated camera-ray footprints. Keep all 852 template directions and report those outside camera support; do not force them bijectively onto 721 camera facets. This gives a testable template-to-camera transform and interpolation boundary while keeping male neurons unassigned.

Before transferring a seven-column patch to MaleCNS, obtain a documented male upper/lower equator row plus one homologous anterior/central-meridian landmark, and verify that they select a unique orientation and translation. Then test that same predeclared transform on additional withheld anatomical landmarks. If the landmarks leave alternatives, retain an unregistered result. This is an anatomical holdout, not a fit to steering or task success.

The camera-side prerequisite is already practical: installed FlyGym `38c8ec61034cd59bc5ba0de20688d4a3c0000d60` uses a deterministic destination-to-source pixel lookup and facet averages. An independent encoded-pixel check found exact agreement at every destination pixel; only three pixels in two facets were out of bounds. Root's [camera calibration](../scripts/calibrate_retina_rays.py) independently checks rendered silhouettes and stores [its artifacts](../validation/retina-rays/). Its 721 facets have one active yellow/pale channel apiece, using the same mask in both eyes; these are renderer channels rather than measured Rh1/R7/R8 spectral responses. A future retinotopic map will still need a separately justified graded photoreceptor transfer and release model.

The audit consulted small primary code/data files and cached primary-paper text. Direct publisher/PMC follow-up pages were intermittently unavailable; one Europe PMC full-text request timed out. No wind retrieval was retried. Exact numerical and identity claims above come from the locally inspected pinned files, with source URLs and hashes retained in the receipts.
