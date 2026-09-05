# Native FlyBody habitat

The optional `body.habitat` configuration adds four collidable MuJoCo box walls around a 30 × 24 mm interior. The walls are 6 mm high and 1 mm thick; the enclosure has an open top. Dimensions and center are configurable in millimeters. Native FlyBody lengths use centimeters, so the conversion is mm / 10. The compiled wall friction, solver reference and impedance equal the source floor values.

The original infinite collision plane remains under the enclosure. Its visible extent and XY center match the outside wall footprint. This preserves the walking surface while providing finite physical walls; it does not guarantee indefinite containment. The source body remains female-derived, with its original pretrained walking policy, native actuators, gains, clocks and physical termination rules.

Food is a radius-3 mm planar region at (6, 0) mm; water is radius 2 mm at (5, 7) mm in the example config. These regions must fit inside the walls. Their visible disc footprints use those same centers and radii. They are not added collision bodies or volumes. Existing active tarsal-floor-contact tests control ingestion, and wall contacts are stored separately. The odor puff field still uses unbounded uniform advection; there is no wall-flow or odor-boundary coupling.

Use [the sensory habitat viewer configuration](../configs/male-flybody-rolling-habitat.json) with the existing viewer. It selects rolling references with an explicit null horizon and an overview camera. It does not inject a motor probe or add steering. The default `habitat: null` retains the old environment and cameras. Follow and side views remain body-centered; overview frames the enclosure. Reset explicitly rebuilds the same habitat and clears an existing native failure.

## Native evidence

The design was frozen before runtime edits, followed by an execution plan before trials. Commit `fd19b56` freezes the executed environment implementation and receipts. The [original receipt](../validation/flybody-habitat-results.json) contains **64 passing checks out of 65**, and preserves a failed detached-probe force gate. The controller trial itself also terminates physically; neither failure is reclassified as successful wall avoidance.

| Check | Saved outcome |
| --- | --- |
| Default vs pre-habitat frozen worker | Every saved native state field and all 741 actual float32 actor values exactly match for reset plus 1,000 control intervals, 2 seconds |
| Habitat vs rolling source floor before contact | Exact state and actor parity for reset plus 250 intervals, 0.5 seconds; no wall contacts in this prefix |
| Straight 20 mm/s, zero-yaw wall approach | First actual positive-x wall contact at 0.666 s; 35 sampled endpoints with active nonzero wall forces |
| Physical termination | Tick 384, 0.768 s: reference error 0.304047895 cm exceeds the unchanged 0.3 cm threshold |
| Other endpoint guards | Speed 8.22149 cm/s, angular speed 54.82369 rad/s, qacc norm 60,481.9; below the respective 50, 200 and 1e14 limits |
| Root containment | Inside the inner XY rectangle at every saved wall-trial sample; final root (12.8833, 1.71358) mm |
| Soft-contact evidence | Most negative sampled wall distance −0.0420185 mm; largest per-contact force norm 6.03116 dyne |
| Numerical state | Sampled arrays and forces finite; warning counters zero; failure latch prevents subsequent advance |
| Reset and cameras | Exact initial state and actor restored; three camera renders preserve the nine named native arrays, cached observations, actor hash and native time |
| Offset geometry | Separate zero-step (1, −1) mm center case confirms wall, visible floor, overview and resource alignment |

These are control-endpoint diagnostics every 2 ms, not a recording of every 0.2 ms physics substep. The root-containment check is not full mesh containment, and soft penetration is explicitly retained. Journals include preceding-stage actuator forces and detached-forward endpoint floor/wall forces. Wall records retain native geom IDs, contact frame, local force/torque, world force, world position and signed distance. This permits independent force-transform checks.

## Detached contact probes and preserved failures

Initial translated-root probes placed parts of the fly deeply across the finite wall. In the positive-x case, penetration reached 1.543 mm across a 1 mm thick wall, with contacts on multiple faces. Its summed inward-axis force check failed. That probe is not evidence of a physical trajectory or a force-sign bug.

The separately planned [shallow-contact addendum](../validation/flybody-habitat-shallow-contact-results.json) bisected the first contact boundary on detached native-data copies and translated a further 0.01 mm. It passes **29 of 31 checks**. All four walls produce shallow active contacts, inward normals and exactly reconstructible force transforms, with no live native state mutation. Two total horizontal-force checks at the y walls remain failed.

The [saved-data decomposition](../validation/flybody-habitat-contact-decomposition.json) explains those two failures. Initial lateral claw contact occurs at the lower wall edge. Positive normal force gives an inward horizontal component, but the opposing tangential component is larger; the total horizontal force points slightly outward. An unconditional total-force-axis gate was too broad for this corner contact. The decomposition changes no result or threshold, and no additional contact trials were run to obtain a preferred outcome.

The independently authored [review](../validation/flybody-habitat-independent-review.json) checks source and retained evidence without new native simulation. Its review pass means that the evidence and its limits are consistent; it does not turn either failed force gate or the controller termination into success.

## Display correction

The original food marker showed severe jagged depth artifacts in the saved overview and live viewer. A first correction used dm-control's camera `scene_callback` after native scene update, moving only rendered resource markers upward by 0.05 mm and setting reference-ghost/trajectory display alpha to zero. Native `MjModel`, `MjData`, compiled site positions/radii, task reference state and sensing remained unchanged. The lift is a display offset, not food height. The native initial site center remains 0.001 mm above the floor with a 0.001 mm visual half-thickness; the derived display center becomes 0.051 mm.

The [v1 visual receipt](../validation/flybody-habitat-visual-results.json) passes **26 of 27 checks**. All four paused renders (overview, follow, side and repeated overview) preserve the entire serialized compiled model byte-for-byte, nine explicit native arrays, actual actor hash, cached observations and native clock. Reset plus 100 control intervals after rendering exactly match all prior saved native state fields and all 741 actual float32 actor values. The overview shows smooth resource discs, but subsequent close-view inspection revealed residual dotted reference-site shadows/reflections. The earlier broad no-dots claim was incorrect. This alpha-only version and its flaw are retained at commit `ef6e230`.

The remaining visual check requires pixel identity between the default worker camera and a separately constructed source camera. It failed and remains failed. A separately planned [zero-step diagnostic](../validation/flybody-habitat-render-diagnostic-results.json) retains five images: the first differs from each later image by three pixels, with a maximum channel difference of one. The same difference occurs on repeat renders by the worker's own camera. Poses and all saved scene-geometry fields are exact; compiled model bytes and native state remain unchanged. This establishes a small repeated-render variation in the test, without establishing its graphics-driver cause. No image tolerance was substituted into the original check.

The final [scene-removal addendum](../validation/flybody-habitat-scene-results.json) passes **26 of 26 checks**. It removes reference-ghost geoms and trajectory sites from the disposable `MjvScene`, including its reflection and shadow passes, while retaining the resource-marker lift. Surviving scene geoms are copied field-for-field; only the specified marker Z and compact display segmentation indices change. The entire compiled model, paused native state/actor/cached observations/time remain exact. All 101 native and actual-actor samples again match the original wall-trial prefix. No reference IDs remain in any of the four retained scenes.

Inspection of final overview, follow and side images confirms smooth discs and removal of the dotted reference artifacts. The source floor reflectance of 0.2 remains, so a reflection of the actual fly is visible below the surface; it is not a second animal or a retained target ghost. The [visual inspection receipt](../validation/flybody-habitat-scene-visual-inspection.json) identifies the exact images.

The [actual browser inspection](flybody-habitat-viewer.md) additionally checks all three final views at commit `62129a3`, after a separately retained full-graph pause/reset and wall-failure demonstration at `ef6e230`. Port 8774 is left in the final sensory habitat, paused at t=0. The source sensory assay remains at rest.

The original screenshots, physical trial, both failed aggregate-force gates, failed exact-pixel gate and v1 shadow flaw remain retained. These visual addenda add no native wall trial or successful avoidance claim. Their execution plans pin renderer/runtime versions independently of commit `fd19b56`.

## Reproduction and claim boundary

The executed commands were `.venv/bin/python scripts/validate_flybody_habitat.py --prepare` and `--run`, followed by the separately frozen `validate_flybody_habitat_contacts.py` addendum. Receipts pin scripts, runtime files, policy/source manifests and input artifacts by SHA-256. The scripts deliberately refuse to overwrite existing evidence; reproductions need a separate scratch checkout/output copy at the pinned revision, with the already acquired native assets and isolated Python 3.10 runtime available. The main environment unit checks are `tests/test_flybody_habitat.py` and `tests/test_flybody_bridge.py`: 11 tests and 26 subtests passed before execution.

No learned wall avoidance, turning rule, pose clamp, target recenter, neural gain change, male biomechanics or biological feeding/reproduction behavior is established here. The useful result is an opt-in physical enclosure with explicit resource geometry, unchanged pre-contact behavior, independently inspectable contacts, and an honestly retained native failure when the controller continues pushing its reference through a wall.
