# Actual camera-to-facet geometry

The existing compound-eye renderer now has a reproducible ray-footprint audit.
Three independent random color images agree with the installed FlyGym pipeline
to at most **1.56e-15** in normalized facet output. Fourteen known 3D targets
verify the pixel-center projection and both camera poses. This calibrates the
implemented artificial optics; it does not register MaleCNS columns or measure
biological receptive fields.

## Method

The installed fisheye operation is a deterministic integer pixel lookup. We
encode a unique nonzero 24-bit identifier in every raw RGB pixel, execute that
operation, then decode its destination-to-source lookup. A zero result indicates
black padding. Repeated source pixels retain their repeated weights; invalid
pixels remain in the full facet denominator, reproducing the actual black
padding rather than renormalizing its intensity away.

The separate random-image check combines this lookup with the released facet
mask, channel selection and equal destination-pixel weights. It compares all
721×2 outputs against the original `correct_fisheye` → `raw_image_to_hex_pxls`
pipeline. The unused pale/yellow channel stays zero.

The perspective projection follows [MuJoCo's camera convention](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-camera):
camera x points right, y up, and viewing is along negative z. For height H,
width W, vertical field of view F and raw pixel (row r, column c), we normalize
the vector `((c+0.5-W/2)/f, (H/2-r-0.5)/f, -1)`, with
`f=(H/2)/tan(F/2)`. The script rejects orthographic or explicit sensor-size
cameras. It reads actual camera poses and the body runtime's head-frame basis.

An independent MuJoCo fixture renders a sphere subtending a 6° angular radius
at seven known camera-relative directions for each eye. The two fixtures copy
the actual initial camera poses. Analytic ray/sphere intersection predicts each
silhouette; segmentation rendering supplies the observed mask, free from color
or lighting assumptions. The actual FlyGym pipeline then converts the rendered
mask into facet coverage. No projection parameter is fitted to these images.

## Measured results

| Check or property | Result |
|---|---:|
| Random color-image parity | All 3 pass; maximum error 1.56e-15 |
| Rendered geometric trials | All 14 pass |
| Worst raw silhouette intersection/union | 0.990741 |
| Worst facet coverage RMS error | 0.001366 |
| Facets with any black-padding pixels | 2 of 721 |
| Minimum valid pixel fraction | 0.991379 |
| Unique source pixels per facet | 37–242 |
| Maximum angular distance from each facet's mean ray | 1.996–4.344° |

The predeclared geometric thresholds were raw intersection/union ≥0.97 and
facet RMS ≤0.01. Remaining disagreement includes the renderer's triangulated
sphere silhouette versus an analytic curved surface. These are geometric
engineering checks, not physiological tolerances. Each trial's unrounded
result is retained, including maximum per-facet errors.

Zero-based facets 0 and 15 contain two and one out-of-image pixels respectively.
Both eyes share this lookup and pale mask. Facet angular support varies across
the implemented eye, so a single fixed acceptance angle would discard measured
properties of this renderer. The normalized mean ray is only a summary; the
full lookup is required to reproduce image integration.

At the initial body pose, facet mean azimuths in the forward/left/up head basis
span approximately −11.38° to 138.13° on the left and −137.59° to 12.02° on the
right. Elevations span approximately −73.4° to 73.6°. These describe the current
body cameras and facet centers, not validated male eye coverage. Later body/head
motion requires the current camera transforms; saved world coordinates must
not be reused as fixed sensory directions.

## Reproduce and reuse

```sh
.venv/bin/python scripts/calibrate_retina_rays.py
```

- [Results](../validation/retina-rays/results.json): exact source hashes,
  optical settings, initial camera/head transforms and all geometric checks.
- [Footprints](../validation/retina-rays/ray-footprints.npz): numeric lookup,
  masks, per-facet directions, validity and angular-support summaries; load with
  `allow_pickle=False`.
- [Rendered comparison](../validation/retina-rays/rendered-checks.png): inspected
  analytic and rendered targets plus predicted and measured facet coverage.

The source is the pinned local FlyGym package plus its `vision.yaml` and
`compound_eye.npz` assets; their exact hashes are in the result. No active viewer,
body controller, neural input or source asset is changed by this script.
An [independent review](retina-independent-review.md) reproduced every lookup
index and tested twelve additional peripheral rendered targets. It also found
that incorrectly deduplicating repeated source pixels changes a random-image
facet output by up to 0.05084, confirming why the full weights must be retained.
Segmentation does not test photometry, UV sensitivity, spectral receptor tuning,
adaptation, contrast dynamics, body self-occlusion or physiological acceptance
angles. Those and [anatomical registration](visual-input-mapping.md) remain
separate work.
