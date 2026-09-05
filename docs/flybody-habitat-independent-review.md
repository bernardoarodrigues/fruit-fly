# Independent review of the frozen FlyBody habitat evidence

The independent audit passes **460 consistency checks**, while preserving both producer validation failures. The original habitat validation is **64/65**, with the positive-x deep-overlap probe failing its net inward-force gate. The separate shallow-contact addendum is **29/31**, with both y-wall net inward-force gates failing. A passing independent review means the saved evidence agrees with its sources and reported outcomes; it does not convert either producer result to a pass.

The walking trial contacts the positive-x wall at **0.666 s** and reaches a native reference-error termination at **0.768 s**, during its 384th control interval. That failure is retained. This demonstrates a wall collision and source termination under the prescribed straight command, not wall avoidance or sustained control in an enclosure.

The [review script](../scripts/review_flybody_habitat.py) and [receipt](../validation/flybody-habitat-independent-review.json) examine saved journals, raw arrays, contact fields, metadata, and source. They execute no physics, policy, or neural model. A small isolated test executes only the existing pure floor-contact predicate, with fabricated contact records. No runtime or producer artifact was edited.

The primary [execution plan](../validation/flybody-habitat-execution-plan.json) has SHA-256 `a9a5c7dc77124d6008d78ceb9c98b7785c02ff15ce47d3db926d262fd94c4397`. The [shallow addendum plan](../validation/flybody-habitat-shallow-contact-plan.json) has SHA-256 `9886c5a0d3fb86c8451cc3aa27c8fd1049c513b68e229dde2db0f3d1eb3c56f9`. Their pinned source files matched when reviewed, as did the earlier baseline worker, every result-listed artifact, 223 upstream source/asset files, and all three walking-policy members. The exact reviewed worker/habitat hashes are `9885f40c602f5c601bd19815f3e1f67d4bcc86da8e0629cef1b85d30cbeae511` and `24f8c0a08446155f667866e20e711cc7e988309bf2fed5cea9973997f8ec16a1`. This review covers those files and the original images, before the separately proposed rendering correction.

The [original results](../validation/flybody-habitat-results.json) retain five cases in `runs/flybody-habitat-a9a5c7dc7712/`:

| Case | Saved states including reset | Native endpoint | Outcome |
|---|---:|---:|---|
| Frozen default worker | 1,001 | 2.000 s | Complete |
| New default worker, habitat absent | 1,001 | 2.000 s | Complete; exact default parity |
| Rolling reference, habitat absent | 251 | 0.500 s | Complete |
| Rolling habitat, straight wall push | 385 | 0.768 s | Source reference-error termination |
| Habitat centered at (1, -1) mm | 1 | 0 s | Geometry/render case only |

Across these cases the audit checks 2,639 states and **1,955,499 actual float32 actor-input values**, with the exact 741-value layout, key order, shapes, and per-sample hashes. Every retained NPZ state array matches its JSON journal, all gzip journals close cleanly, control ticks are consecutive, and native clocks agree with 2 ms intervals. Warnings remain zero and all retained numeric arrays are finite. Command schedules, native action mapping, and integrated target positions match the frozen plan. The qacc norm and reference-position error are independently recomputed from saved arrays.

Every old state field and actual actor-input value agrees exactly between the two default cases for reset plus all 1,000 steps. The same comparison holds between rolling/no-habitat and rolling/habitat for reset plus the first 250 steps; that 0.5 s prefix contains no wall contacts. These are specific trajectory comparisons, not proof of equivalence for every possible command. Habitat remains opt-in; bounded mode remains the default and the habitat requires explicit rolling mode with a null horizon.

Source inspection and compiled metadata agree on geometry and units. The 30 by 24 mm interior uses four boxes with 6 mm height and 1 mm thickness. Geometry is created in native centimeters, with the correct millimeter conversion on readout. Wall inner faces are at x = +/-15 mm and y = +/-12 mm, and wall bottoms align with the floor. Compiled friction, solref, solimp and contact dimensionality match the floor. The original plane remains an infinite collision surface; only its visible extent and position change. The offset case independently verifies the configured (1, -1) mm center for walls and the visible plane. The floor's visible half-extents are 16 and 13 mm, covering the enclosure's outer dimensions.

Food and water remain noncolliding visual sites with exactly the configured planar centers and radii: food (6, 0) mm / 3 mm, water (5, 7) mm / 2 mm. Both regions fit within the enclosure in both geometry cases. Source inspection confirms that the worker's existing `contacts` list is populated only from contacts with the source floor. Wall contacts are exported in the separate `habitat.wall_contacts` list. The isolated predicate audit covers 48 floor/wall cases, including inactive contacts, non-tarsal contacts, and points on or outside the resource radius. Wall-only contact never produces food or water contact. These native trials do not test host ingestion physiology or behavioral food seeking.

All **167 saved wall-contact records** are checked: 36 in the actual trajectory, 123 in the original detached probes, and 8 in the shallow addendum. Local force/torque, contact-frame rows, both geometry IDs, and reported world force are retained. The review reconstructs force by an explicit linear combination of frame rows, using positive sign when the wall is geom1 and negative sign when it is geom2. Maximum discrepancy is **2.274e-13 dyne**; all saved frames are orthonormal within tolerance. Force units follow the source centimeter/gram/second system. The native contact `efc_address` is not retained, so the active flag cannot be fully reconstructed independently; active records have nonpositive distance, and the observed nonzero forces corroborate physical contact.

The actual trajectory has nonzero active wall force at 35 sampled endpoints. Maximum force magnitude is **6.0311584 dyne** and minimum signed contact distance is **-0.0420185 mm**, recording soft penetration. Root XY remains within the interior at every saved endpoint; its final position is (12.8832924, 1.7135840) mm. This establishes neither full-mesh containment nor what happened between sampled endpoints. At termination, reference error is **0.304047895 cm**, exceeding the unchanged 0.3 cm limit. qacc norm (60,481.88), linear speed (8.22149 cm/s), and angular speed (54.82369 rad/s) remain below their source limits. Earlier sampled reference errors remain within the limit. The failed-state latch and explicit reset are retained, including an exact reset state and actor hash.

The original detached probes translate the reset fly close enough to each wall to create deep intersections. Penetrations reach about 1.54-1.66 mm, exceeding the 1 mm wall thickness and involving different box faces. The positive-x probe's net x force is **+18.9146125 dyne**, outward rather than inward. The review reproduces that failure from the saved local forces and contact frames; it is not a force-sign bookkeeping error. These poses are not valid evidence of uniformly inward force during natural wall approach. They were generated only on detached copies and do not alter the recorded controller trajectory.

The separately frozen shallow addendum retains 40 bisection iterations per wall and an additional 0.01 mm translation. The reviewer checks all 160 branch calculations and final translated qpos/qvel. Final contact depths and inner-plane locations meet its 0.02 mm tolerances, and all active target normals point inward. Nevertheless the two y-wall **net** forces point slightly outward. Normal and tangential components of the same saved contacts explain the distinction:

| Shallow probe | Normal axis component, outward-positive (dyne) | Tangential axis component (dyne) | Net outward component (dyne) |
|---|---:|---:|---:|
| x-negative | -0.0238738 | -0.0276071 | -0.0514808 |
| x-positive | -2.2120599 | 0 | -2.2120599 |
| y-negative | -1.3502764 | +1.4789702 | **+0.1286937** |
| y-positive | -1.3434451 | +1.4843393 | **+0.1408942** |

The y contacts lie near the wall/floor lower edge, around 0.00248 mm above the floor, with tilted normals. Their inward normal-force components are slightly outweighed along y by the tangential components. This is arithmetic on fixed saved contacts, not a frictionless counterfactual or a new trajectory. Both failed net-axis gates remain false. Intermediate bisection states retain counts and minimum distances, rather than complete contact geometry; their forward computations were not rerun by this review.

Detached-probe nonmutation evidence covers nine named live arrays, clock, actor hash, and cached observations. The shallow addendum additionally retains all nine before/after arrays, whose hashes and equality are independently checked. This scope does not include every MuJoCo model/data field. Render and failed-latch nonmutation have producer boolean receipts rather than retained before/after hash dictionaries, so they are weaker independent evidence. Reset does retain its raw state for direct comparison. The complete compiled model is not archived; geometry conclusions combine compiled metadata with the pinned construction source.

All five original camera images were inspected. They show the enclosure, displaced-center layout, and fly near the contacted wall. The original overview images have substantial resource-disc z-fighting, and the source ghost/trajectory is visible. Those are retained visual defects, not clean final-viewer evidence. A rendering-only correction, if subsequently applied, requires separate source/evidence identification and is outside this receipt.

Walls remain finite height with an open top. Odor puffs retain unbounded uniform advection without wall-flow coupling. The body and trained walking policy remain female-derived surrogates; these tests make no male morphology, calibrated physiology, collision avoidance, or long-term containment claim.

To reproduce the saved-data audit, restore the pinned files and recordings in a checkout without its existing review receipt, then run:

```sh
.venv/bin/python scripts/review_flybody_habitat.py
```

The script refuses to overwrite a receipt and does not invoke any controller or physics engine.
