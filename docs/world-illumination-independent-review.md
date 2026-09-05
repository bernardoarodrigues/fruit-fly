# Independent world-illumination review

The implementation is consistent with an **optional rendering change**, with no identified geometry, actuation or dynamics mutation. Its fixed world light, disabled camera headlight and base-relative gain behavior match the intended design. The saved validation supports this bounded engineering conclusion; it does not establish biological radiometry, complete darkness, visual neural input or continuous-time physics identity.

The [review receipt](../validation/world-illumination/independent-review.json) records exact hashes of the inspected implementation, BodyRuntime integration, tests, original diagnostic script/results, CSV and figure. All implementation hashes match those recorded by the original validation. No original artifact, source module, live viewer or runtime configuration was edited. No physics or rendering diagnostic was rerun. Eight selected configuration/compilation tests passed; the dynamics and rendered-fixture tests were deliberately excluded.

```sh
.venv/bin/python -m pytest -q tests/test_illumination.py -k 'not leaves_fixture_geometry_and_dynamics_exact and not rgb_scaling_world_shadow_and_head_rotation'
```

## Implementation and gain/reset semantics

`add_world_illumination` installs one named directional light on the world body in fixed mode before compilation. It validates finite vectors and bounded RGB coefficients, normalizes the nonzero direction, rejects duplicate installation, sets specular contribution to zero, and both disables and zeroes the camera headlight. Its writes are confined to light and visual-headlight fields. `BodyConfig` defaults to `None`; the old configuration remains available.

BodyRuntime copies the compiled ambient/diffuse arrays after installation. The real `BodyRuntime.set_stimulus` method was independently exercised on a separately compiled static fixture for gains **1, 0.5, 0, 1, 2, 10, 0.5**, without constructing a BodyRuntime or advancing physics. Every coefficient matched the original base times the requested gain exactly; changes did not accumulate. Invalid gains −1, 11, NaN and infinity were rejected without coefficient or stored-gain mutation. The headlight stayed disabled and zero.

Reset restores the base arrays and gain 1 by source inspection and the original recorded body test. A full-body reset was not rerun because it includes settling physics. The opt-in headlight stays inactive; reset does not reinstate it. Render coefficients change immediately on a gain command. The BodyRuntime retinal array remains cached until its next declared simulation-time vision sample, with `sample_t_s` exposed. The original retinal gain diagnostic explicitly renders native eyes directly, so it should not be described as testing immediate refresh of the paused runtime cache.

Illumination provenance remains privileged snapshot metadata. There is no installed retinal-to-neural encoder or hormone/day-night coupling. The pre-existing scalar light setting is telemetry, not a calibrated phototransduction signal.

## What the retained validation can establish

All 12 CSV rows exactly match the saved fixture RGB tensor. Independently recomputed fixture gates agree with the original report: the lit patch is approximately RGB 145 at gain 1 and 73 at gain 0.5; the declared shadow patch and both zero-gain surface samples are black. Maximum half-gain deviation is **0.5 display units** and maximum head-rotation difference **2.84×10⁻¹⁴**. The figure was visually inspected and shows the expected floor darkening plus retained bright background in the actual-body scene.

These are **two interior world points, two head orientations and three gains**. Both points are sampled from cube face index 5 in both orientations. This does not test lighting consistency across cube seams or arbitrary textured facets. The fixed world direction is correct for the stated light-travel convention; the anchor lies above the arena and on the opposite extension through its origin. The selected shadow anchor is an explicit renderer setup choice. Shadow-map resolution, projection extent and clipping must be checked again for changed scenes.

The original body receipt reports **423 equal public non-light/non-name-table model arrays**, equal timestep/gravity, and no differences in the compared arrays. Source inspection supports the narrow rendering-only change. The receipt retains array names and equality results, not the arrays themselves, so this review confirms its consistency rather than independently reconstructing those compiled comparisons.

**The physics coverage is 21 sampled state comparisons over 0.1 s and 1,000 integrated physics steps.** The samples occur every 5 ms, including both endpoints. Saved `qpos`/`qvel` maximum differences are zero and contact counts match at all 21 times. The frozen key `1000_physics_steps_exact` is imprecise: its predicate at `scripts/validate_world_illumination.py:156` operates only on those 21 entries, not every internal step. Contact pair identities and contact forces were not compared. This interpretation applies equally to position, velocity and contact count and does not require changing the frozen evidence.

The artifact retains state-comparison summaries, not raw trajectories. Native retinal shape/range, response magnitude and exact-restoration checks are also producer-recorded witnesses; raw retinal arrays are absent, so their differences cannot be independently recomputed from the receipt. The recorded maximum gain-1-versus-0 retinal change is **0.461302**, and restoration difference is zero. This supports the recorded pipeline response, not a physiological calibration.

## Claim limits

The coefficients are dimensionless renderer RGB values. Quantization, interpolation, shadows, clipping and saturation prevent interpreting global RGB gain as linear photon flux. The two-point half-gain check does not override that limit. Specular zero removes this light's view-dependent specular contribution but does not guarantee identical finite-pixel samples from different viewpoints.

Gain zero is a **light-coefficient intervention**. Background, skybox and emissive appearance can remain bright, as the figure and retained extrema show. The 852-axis sample's count of black axes describes appearance at one pose; blackness is not a test of geometric coverage or a missing-sample diagnosis. No full-field darkness, spectral sensitivities, photoreceptor physiology, vision-guided behavior or biological entrainment claim is supported.

No blocking implementation defect was found. Preserve the corrected 21-snapshot wording and distinguish retained raw fixture RGB from producer-recorded body/retinal comparison summaries when citing these results.
