# Opt-in native FlyBody habitat: design before implementation

The new `body.habitat` setting will default to `null`. The default worker path retains the source floor, resource sites, cameras, body, policy, gains, clocks and termination rules. The habitat uses the existing rolling runtime; it adds environment geometry and diagnostics, without steering or neural changes.

The proposed interior is a 30 × 24 mm rectangle centered at world (0, 0), with four 6 mm high, 1 mm thick box walls. Dimensions are configurable and stated as inner dimensions. Native geometry uses centimeters: divide configured millimeters by ten. Walls begin at the existing floor surface and copy its contact parameters. The original infinite collision plane is retained to preserve the exact walking surface; its visible extent is reduced to the enclosure footprint. This is a finite enclosure over that plane, with an open top, not an infinite-height containment guarantee.

Food and water remain finite planar regions. Their visible discs use the same world centers and radii as the host's active tarsal-floor-contact test. They do not acquire height, liquid dynamics or extra collision surfaces. Both discs must fit inside the walls. Wall contacts remain separate from floor contacts so touching a wall cannot count as eating or drinking. Odor puffs retain the existing unbounded uniform-advection model: walls do not redirect airflow, reflect puffs or block odor transport.

Reset reconstructs the same habitat. Overview framing will center on the enclosure and use its dimensions; follow/side cameras remain body-centered. Diagnostics expose compiled wall names/poses/sizes, native wall contacts and forces, and root-position containment. Root containment is distinct from exact mesh containment or zero soft-contact penetration.

Validation will freeze a separate execution plan after implementation and lightweight checks:

- Compare the new default against the frozen current worker for 2 seconds using identical commands, preserving all existing actor/native state values. Geometry/provenance metadata additions are not physics parity claims.
- Compare habitat-on and default states through a fixed 0.5 second straight-walking prefix, required to precede any wall contact. Compare actual actor inputs/actions, native state, target and clocks.
- Run a predetermined straight command into the positive-x wall for at most 1.2 seconds. Save native contacts, forces, positions and exact failure state. A source reference-error or other physical termination is retained, not weakened or turned into successful avoidance.
- Check all four compiled walls and resource-disc geometry. Detached native contact probes may validate the other wall orientations without advancing policy or mutating the live state; report those separately from controller trials.
- Verify reset and all three camera renders, floor-only resource-contact semantics, and resource geometry inside bounds. Save screenshots for inspection. Add a small sensory-only rolling-habitat viewer configuration.

No automatic turn, recentering, clipping, reflection or recovery is added. Contact and bounded containment evidence will be reported only for the tested trajectories. Female-derived body and pretrained controller limitations remain explicit. No wall-avoidance or male-morphology claim is made.
