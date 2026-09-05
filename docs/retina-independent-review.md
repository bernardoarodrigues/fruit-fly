# Independent review of the implemented retinal ray footprints

The independent audit found no numerical or geometry defect in the reviewed
calibration. This is a verification of the **implemented artificial optics**;
it does not establish MaleCNS anatomical registration, biological acceptance
angles, or physiological phototransduction.

Run from the repository root with the existing research/morphology dependencies:

```sh
.venv/bin/python scripts/review_retina_rays.py
```

The [review script](../scripts/review_retina_rays.py) writes only its
[JSON receipt](../validation/retina-rays/independent-review.json). It reads
the original calibration script, results, footprint archive, and plot, and
checks their hashes before and after execution. It does not import the original
calibration's numerical functions or alter its artifacts. A fresh, temporary
`BodyRuntime` verifies camera poses without touching live viewers.

The receipt records NumPy, MuJoCo and FlyGym versions, reviewed artifact hashes,
review-script and relevant dependency hashes, seed **419**, all thresholds,
per-camera matrices' checks, and each rendered target's measurements. All
**14 named checks passed** in the saved run.

| Independent check | Saved result | Acceptance tolerance |
|---|---:|---:|
| All 230,400 source-pixel indices from a separate translation of the installed fisheye equations | 0 mismatches | Exact |
| Separately reduced, duplicate-weighted facet mean rays | Maximum component error 2.22e−16 | ≤1e−12 |
| Maximum angular support radius per facet | Maximum error 4.91e−13 degrees | ≤1e−9 degrees |
| Valid destination-pixel fraction per facet | Exact | ≤1e−12 |
| Seeded random RGB → facet readings | Maximum error 1.67e−15 | ≤1e−12 |
| White-field → facet readings | Maximum error 5.66e−15 | ≤1e−12 |
| Fresh camera world positions and world/head rotations | Exact match | ≤1e−12 in model mm or matrix components |
| Twelve additional rendered sphere targets | Worst Jaccard 0.999459 | ≥0.97 |

The source-index oracle retains upstream integer **truncation toward zero**.
Facet reduction retains repeated source pixels and divides by all destination
pixels, including invalid samples, which remain black. Of 721 facets, **700**
repeat at least one source pixel. One-based facets **1** and **16** contain
respectively **2/232** and **1/232** invalid destination samples. A deliberately
incorrect uniform average over unique valid pixels differs by up to **0.050844**
in normalized readout. That comparator also discards invalid-sample attenuation;
it is a diagnostic of the lossy replacement, not a controlled isolation of
duplicate weighting alone.

The extra targets use both saved camera poses at camera-relative
azimuth/elevation pairs `(74,0)`, `(-74,0)`, `(0,73)`, `(0,-73)`, `(60,40)`, and
`(-60,-40)` degrees. Each sphere is 20 model mm away with radius
`20 sin(6°)` model mm. Expected silhouettes use a **world-space ray/sphere
quadratic discriminant**, independently of the calibration's angular
dot-product threshold. Rendering uses segmentation, 128 slices/stacks, and
disabled multisampling. The 0.97 Jaccard tolerance matches the original audit;
these are numerical audit tolerances, not fitted biological parameters.

The saved original plot was visually inspected: overlays agree, readout curves
are legible, and the biological-registration limitation is visible. The audit
does not validate radiometry, self-occlusion, or all articulated poses. Initial
L/R names and outward optical directions agree with current FlyGym conventions;
future body poses still require their current camera/head transforms. Retain
the full lookup and finite facet support when using this artifact.
