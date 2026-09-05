# Male specimen morphology source and first derivation

Research and measurements: 2026-09-04. A real male whole-animal scan has been acquired and processed. It is **not yet a rigged male body** and does not replace the clearly labeled female-derived NeuroMechFly walking surrogate.

[Blackie, Gaspar et al., *The sex of organ geometry*, Nature 2024](https://www.nature.com/articles/s41586-024-07463-4) provides sex-specific whole-animal microCT, gut traces and organ segmentations. Its [versioned source archive](https://doi.org/10.25418/crick.25598859.v1) is CC BY 4.0. The archived datasheet identifies scan `M1E.nii.gz` as specimen **M5H, Male, OregonR**. Existing OBJs represent internal organs; none was mistaken for external cuticle. The paper reports scanner sampling near 2.49–2.95 µm.

## Selective acquisition and provenance

The full ZIP is 147,866,131,515 bytes. HTTP ranges were verified and only selected members were extracted. `fruitfly.morphology.RangeReader` refuses a response that fails to honor an exact byte range, and rejects accidental reads exceeding 8 MiB. Python's ZIP reader validates each complete member's CRC; local SHA-256 checksums are saved. The provider's whole-archive MD5 is `2e68cf081c5e83f85c66c8978a807b1f`; the entire archive was not downloaded, so that global checksum is **provider-reported**, not independently verified.

| Member | Extracted bytes | SHA-256 |
|---|---:|---|
| OregonR/OregonR_datasheet.csv | 9,877 | `577fe1b99607bc41cff2577e5706229901ec662dd1438adb405b2190896d4645` |
| OregonR/Processed_microCT_scans/M1E.nii.gz | 68,794,547 | `cc347682b12ce4f10930253e9605f78bad20378903a1f49a61fbea5616d10246` |
| OregonR/Centrelines/M5H.swc | 51,074 | `4443580ff2e415ce3959a91a57ffea8bec6bb0a5ddd4ca8db59cfe75793eb69e` |

The archived README and one additional specimen's gut trace/mesh were also inspected for calibration. All six acquired members and their CRC/SHA values are recorded in `data/raw/morphology/provenance.json`; bulk source data are excluded from Git. M1T's organ mesh is a different specimen and is not mixed into the M5H anatomy.

## Recovered spatial calibration

The NIfTI header encodes **1 mm isotropic voxels** for a 707 × 707 × 1,075 volume. That would make the fly hundreds of millimetres long. Headers from two other male scans show the same problem; these exports cannot be used directly as physical calibration.

The matched M5H gut trace preserves coordinates on an exact **0.002951345** lattice. Every coordinate divided by that value is an integer to a maximum error of 1.14×10⁻¹³ voxels. Interpreting these coordinates as millimetres gives **2.951345 µm/voxel**, consistent with the paper's rounded 2.95 µm acquisition scale. This is a cross-file calibration inference, explicitly recorded in the analysis manifest; it is not an assertion that the NIfTI header was correct or a general rule for SWC units.

Registration provides an independent check: after mapping those trace coordinates into voxel indices, 97.2% of the gut trace lies inside the default extracted body-tissue region. Mirroring the y coordinates reduces this to 25.7%. This supports the paired-file alignment and unit interpretation. It does not establish cuticle accuracy or remove uncertainty due to fixation and segmentation.

## Derived artifact and sensitivity

The analysis downsamples by three, applies an Otsu threshold (65 in the stored 8-bit intensities), closes with a two-voxel sphere, fills cavities, opens with a three-voxel sphere and retains the largest connected tissue region. It repeats the operation at thresholds 45 and 85. These are declared image-processing choices, not biological constants.

| Threshold | Principal long extent | Envelope volume | Gut trace inside |
|---:|---:|---:|---:|
| 45 | 2.275 mm | 0.914 mm³ | 100.0% |
| 65, Otsu | 2.254 mm | 0.517 mm³ | 97.2% |
| 85 | 1.980 mm | 0.309 mm³ | 86.2% |

The generated `data/derived/morphology/male-M5H-tissue-envelope.obj` has 224,828 vertices and 449,920 faces; its SHA-256 is `ae058e524d740543f85ab45afdb1ef6fc53923f8500f9518981020b92795878b`. The corresponding `analysis.json` preserves the full parameters, source identity, calibration inference and measurements. `male-envelope-sensitivity.png` overlays the three masks on the same CT projection and was visually inspected.

In a separate compiled NMF reference measurement, the world-space mesh vertices of head, thorax and abdomen have a principal long extent of **2.760 mm** (axis-aligned extent 2.753 × 0.989 × 1.073 mm). The male stained-tissue envelope and that female external body mesh have different segmentation definitions and postures. Their lengths cannot justify a female-to-male scaling ratio.

Visual inspection shows fixed legs and wings folded against the body; low thresholds retain some appendages, while high thresholds lose parts of the head and abdomen. Volume changes almost threefold across this small threshold sweep. Consequently `body_physics_ready` remains false. The OBJ is a research artifact for segmentation refinement; it lacks named body segments, cuticle boundaries, joints, mass distributions and inertias. No body asset or control parameter was silently rescaled.

## Reproduce

Optional analysis dependencies used here: nibabel 5.4.2 and scikit-image 0.26.0. The downloader itself uses the standard library.

```bash
.venv/bin/python -m fruitfly.morphology \
  --member BlackieGasparEtAl2024-sourceData/README.rtf \
  --member BlackieGasparEtAl2024-sourceData/OregonR/OregonR_datasheet.csv \
  --member BlackieGasparEtAl2024-sourceData/OregonR/Processed_microCT_scans/M1E.nii.gz \
  --member BlackieGasparEtAl2024-sourceData/OregonR/Centrelines/M5H.swc

.venv/bin/python -m fruitfly.morphology \
  --analyze-scan data/raw/morphology/OregonR/Processed_microCT_scans/M1E.nii.gz \
  --trace data/raw/morphology/OregonR/Centrelines/M5H.swc \
  --output data/derived/morphology

.venv/bin/python -m unittest tests.test_morphology -v
```

The next useful anatomy step is segmentation of head, thorax and abdominal cuticle with retained scanner coordinates, followed by measured segment dimensions and a separate inertia model. This dataset makes male-derived geometry feasible without inventing a sex scale factor. It does not make a full male musculoskeletal model available automatically. The recovered calibration and segmentation sensitivity are engineering findings from this project, not new biological discoveries.
