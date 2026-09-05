# Isolated multiview acquisition of the female optical template

The new sampler acquires all **852 retained right-eye optical axes** through six MuJoCo views. It follows the current head frame and actual right-eye camera origin. No source axis is replaced by a nearest existing facet, and no MaleCNS cell identity, neural input, spectral sensitivity or release gain is assigned. Body, viewer and neural defaults are unchanged. The current body has **no independent world lights**: after suppressing camera-attached illumination, non-emissive surfaces become black. This valid dark signal is retained separately from missing support; a lit synthetic scene verifies the RGB acquisition.

This addresses the acquisition gap in [the previous coverage audit](visual-template-coverage.md): only 783 axes were inside the original raw right-camera frustum and 704 hit pixels used by the existing facet sampler. The multiview experiment returns 852 finite RGB samples. This is angular coverage of an explicitly declared optical surrogate, not evidence of a reconstructed male retina.

## Source and coordinate contract

The source is Zhao et al., [*Eye structure shapes neuron function in Drosophila motion vision*](https://doi.org/10.1038/s41586-025-09276-5), using the [author repository](https://github.com/reiserlab/eyemap_T4/tree/99d2a43123db636cedb55af9ff31a59657e7d17e) pinned at `99d2a43123db636cedb55af9ff31a59657e7d17e`. The coherent 852 directions were reconstructed from female microCT sample 20240701. They estimate lens-to-cone optical geometry; they are not measured acceptance functions or physiological receptive fields. [The extraction and registration audit](visual-retinotopy-feasibility.md) records the source arrays, exact matched-subset parity and why the older standalone 786-row lattice was rejected.

The input CSV is [zhao-female-right-eye-directions.csv](../validation/visual-retinotopy/zhao-female-right-eye-directions.csv), SHA256 `7ac32cfeee41236f6b4c76ffbb3f60c5559f6af81426a94cb8768e6a4f93d194`. Its axes use **x forward, y left, z dorsal**. The author's inside-out plotting reflection is absent. Rows retain the original right-lens indices 1..852; Python arrays, cube face indices and raw image indices are zero-based. The diagnostic verifies the CSV against its extraction receipt before use. Embedded source data and derived geometry retain the author repository's provenance; no author implementation code is vendored into the runtime module.

The optical-template and body specimens differ. Identifying their canonical head bases is an explicit female-to-female body-optics surrogate assumption, without a fitted rotation or anatomy correspondence. All six views share the body's current right-eye camera origin; individual lens origins and near-field parallax are absent. The directions therefore describe a far-field angular surrogate. Objects near the shared origin can still be rendered, but this is not specimen-accurate compound-eye parallax.

## Acquisition and API

Implementation: [fruitfly/multiview.py](../fruitfly/multiview.py). `CubeEyeSampler` owns its renderer and changes only its private `MjvScene` cameras and headlight contribution. It never changes model camera definitions, advances physics, or modifies `qpos`/`qvel`. It uses the installed MuJoCo 3.9.0 `Renderer.update_scene`/`render` implementation and `MjvGLCamera` API. The geometry is rendered once into a scene, then acquired through six colocated monocular camera orientations in that same state.

```python
from fruitfly.multiview import CubeEyeSampler, eye_pose_from_body

# directions_head: verified 852x3 source CSV vectors, in original row order.
# body: an existing vision-enabled BodyRuntime with current forward kinematics.
with CubeEyeSampler(body.model, directions_head) as sampler:
    pose = eye_pose_from_body(body, side="R")  # reread at every acquisition
    rgb = sampler.sample(body.data, pose)     # 852x3, floating display RGB
    valid = sampler.mapping.valid            # 852 rows; never silently drop one
```

`eye_pose_from_body` reads the compiled camera position and current head-geometry rotation multiplied by BodyRuntime's neutral anatomical basis. It intentionally depends on those audited body fields. A caller must complete forward kinematics and avoid concurrent physics advancement while rendering. A generic caller can instead supply `EyePose(origin_world, head_to_world)` in the model's length units; the body adapter uses millimetres.

Each face has a **90° core at 256×256 pixels**, with one guard pixel on each edge:258×258 rendered pixels, FOV approximately 90.446°. Face order is `+x,-x,+y,-y,+z,-z`; the largest positive dot product selects a face, with that order breaking ties. Camera right is `forward × up`. Pixel centres are at column+0.5,row+0.5, with rows increasing downward. The guard pixels keep all four bilinear neighbours inside a real image even at exact face edges and corners.

The output is an approximation to a **point-direction query**, obtained by bilinearly interpolating four finite raw pixels. It is not an infinitesimal sample or a biological acceptance kernel. Both pixel-centre rays and the corners of their four pixel cells are retained in [cube-support.npz](../validation/multiview-eye/cube-support.npz). The maximum source-to-support offset across this template is 0.5945° for pixel centres and 0.9091° for pixel-cell corners. Weighted pixel-centre mean direction error is at most 0.0002814°. The small mean error does not imply negligible finite support or physiological optical fidelity.

Finite unit axes have weights summing to 1 without missing-support renormalization. A malformed row remains present with `valid=False`, face/pixel indices−1, zero weights and a NaN output; no malformed rows occur in the verified852-axis source. Array consumers must use the validity mask. Black RGB is a valid renderer value and must not be mistaken for padding. There is no selected pixel padding for a valid unit direction.

MuJoCo's model near/far clipping conventions are retained. Visibility matches FlyGym's eye convention: hide marker group 1 and selected body-segment group 2, retain the default settings of the other groups. The actual visibility vector is `[1,0,0,0,0,0]`; other group 0 body parts remain occluders. Hidden body surfaces or clipping can omit biologically relevant occlusion. The headlight is the one deliberate isolated lighting distinction: its private-scene contribution is zeroed while world lights remain intact. Otherwise the overridden GL views would inherit an unrelated free-camera headlight or illuminate the world differently at each cube face. The model's headlight settings and existing camera pipeline are unchanged. The actual body records zero model world lights and 329/437 fully black source samples in its two tested poses. Floor/resource/leg detail requires an explicit world illumination source in a future integration; this experiment adds no hidden lamp to the body.

RGB is MuJoCo display RGB on the original 0–255 scale, with floating interpolation roundoff. It includes renderer lighting, surfaces, textures and rasterization; no photon calibration, fly spectral channels, adaptation or phototransduction is supplied. Cube overlap removes undefined sampling support, but high-frequency textures or geometry exactly on a seam can retain raster-resolution differences. The reported tests establish computational geometry and a limited RGB lighting check, not biological radiometry.

## Executed validation

Run:

```sh
.venv/bin/python -m pytest -q tests/test_multiview.py
.venv/bin/python scripts/validate_multiview_eye.py
```

Nine focused tests passed. They cover whole-sphere random directions and exact corners, invalid-row retention, coordinate-field continuity, rotation validation, target rendering, current visibility groups and private headlight suppression. An independent agent reviewed the projection/frame/guard logic without finding a defect.

The diagnostic's nine checks pass; exact values, pose matrices, source hashes and target positions are in [results.json](../validation/multiview-eye/results.json). It preserves [per-source sampling and RGB](../validation/multiview-eye/female-right-ray-sampling.csv) and the [rendered figure](../validation/multiview-eye/diagnostic.png).

| Check | Retained result |
|---|---|
| Source axes and nonmissing four-pixel support |852/852; all finite RGB in both body poses |
| Six core-face source counts |251,28,0,320,170,83 |
| Known 4° sphere, 19 axes×2 independent poses |38/38 pass; worst analytic/rendered silhouette Jaccard0.996337 |
| Cube seam smooth-coordinate field |All 8 seams/corners below 1e−5 component error and transition range |
| RGB across a flat wall at the +x/+y seam |Identical `[163,77,20]` on three axis samples crossing the face tie |
| World-light negative control |Removing the fixture's world light gives `[0,0,0]` while its deliberately large model headlight remains configured |
| Light identification |World light id 0, direction, ambient and diffuse retained; only the headlight flag's private light contribution zeroed |
| Actual movable body head |Joint offsets yaw +25°/pitch −15° produce 29.093° head-frame change and 0.11609 mm eye-origin movement |
| Optical read does not mutate physics/cameras |`qpos`, `qvel`, model camera position/quaternion unchanged |

The body head offsets are imposed fixture poses followed by `mj_forward`, not a motor or behavior reproduction. The target fixture uses translated/rotated camera poses and an independent analytic sphere silhouette. The current two actual-body acquisitions took about 37 ms and 22 ms for six faces on this machine; these are two observations, not a throughput guarantee. The figure was visually inspected for orientation, the dark surfaces caused by missing world illumination, and complete source-row display.

The experiment makes full optical-template acquisition feasible with the current renderer. Biological male retinotopic registration, physiological acceptance and photoreceptor-to-brain transfer remain separate unresolved tasks. No default retinal change or neural injection is included here.
