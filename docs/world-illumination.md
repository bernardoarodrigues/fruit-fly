# Optional fixed world illumination

The body now accepts an explicit `world_illumination` configuration. In this mode one fixed directional world light illuminates scene surfaces and casts shadows; the camera headlight is disabled. Omitting the option preserves the legacy body with no world lights and its existing headlight. The earlier [unilluminated multiview result](multiview-eye.md) remains unchanged as evidence of that configuration.

The coefficients and light placement are **engineering choices in MuJoCo renderer units**. They are not irradiance measurements, a day/night schedule, fly spectral sensitivities or a neural phototransduction model. No visual-to-MaleCNS mapping was introduced.

## Configuration and integration

Use [male-world-illumination-probe.json](../configs/male-world-illumination-probe.json) for the existing multisensory motor-probe configuration with the added illumination option. Its motor probe remains an imposed activation assay. Only the following body option is needed for illumination:

```json
{
  "body": {
    "world_illumination": {
      "direction_world": [0.3, -0.2, -1.0],
      "position_world": [-6.0, 4.0, 20.0],
      "ambient_rgb": [0.1, 0.1, 0.1],
      "diffuse_rgb": [0.65, 0.65, 0.65],
      "cast_shadows": true
    }
  }
}
```

The direction is normalized and points along light travel, downward toward the arena. Position uses model length units, millimetres in BodyRuntime. The light is attached to the world body with fixed mode, not a fly, head or camera. Its directional field has no inverse-square attenuation. Position nevertheless anchors MuJoCo's shadow projection: the declared point is 20 mm above the arena, on the opposite extension of the direction through the origin. Specular light is fixed at zero, so this option supplies diffuse surface illumination and an ambient coefficient without a camera-dependent specular component. Rasterization, visibility and shadows can still change the sampled pixel values as the viewpoint moves.

[fruitfly/illumination.py](../fruitfly/illumination.py) contains the validated configuration and before-compilation insertion helper. [BodyRuntime](../fruitfly/body.py) adds the light only when the option is present. All light RGB coefficients are captured by its existing `_original_ambient`/`_original_diffuse` state. `set_stimulus("light", gain)` therefore continues to scale relative to the saved base coefficients, and `reset()` restores gain 1. The headlight is both inactive and zeroed in this mode, so neither operation reinstates it. Its legacy behavior is preserved when the option is absent. Configuration snapshots include the explicit parameters. The privileged snapshot also provides `illumination.mode` (`fixed_world_directional` or `legacy_camera_headlight`), world-light count, headlight-active flag, current gain/coefficient arrays and the fixed-background caveat. This provenance is outside the neural observation and does not add a visual brain input.

The background caveat remains important: the existing skybox, background and emissive surfaces are not controlled by these light coefficients. At gain 0, non-emissive lit surfaces become dark while parts of the background can stay white or gray. This is a light-coefficient intervention, not a simulation of complete environmental darkness. Rendered RGB is quantized and clipped display color; it is not globally linear photon flux. Higher gains can saturate.

## Executed checks

```sh
.venv/bin/python -m pytest -q tests/test_illumination.py tests/test_multiview.py
.venv/bin/python scripts/validate_world_illumination.py --body
```

The 19 focused tests passed. All 13 diagnostic checks passed. Exact configuration, source hashes, light gains, test poses, comparison fields and 21 state-comparison summaries are retained in [results.json](../validation/world-illumination/results.json), with [fixture RGB values](../validation/world-illumination/fixture-rgb.csv) and a [visually inspected figure](../validation/world-illumination/diagnostic.png).

The small fixture holds two floor points and a box occluder fixed in world coordinates while the head/cube-camera frame rotates from Euler xyz `[0,0,0]` to `[21,-38,63]` degrees. The sampled lit point gives approximately `[145,145,145]` at gain 1 and `[73,73,73]` at gain 0.5; the declared shadow point stays black. Gain0 makes both points black. Maximum half-gain error is 0.5 display units, consistent with rounding; maximum difference between the two camera orientations is 2.84e−14. This tests two interior surface samples and two poses, not arbitrary-texture or all-seam radiometric fidelity. MuJoCo's per-light ambient contribution is also occluded in the tested shadow; it should not be interpreted as a calibrated global diffuse sky term.

An initial shadow check placed the directional light at world origin. The expected geometrical shadow point incorrectly remained as bright as the lit floor point. Moving the **declared shadow-projection anchor** above the geometry resolved that renderer setup error. The final anchor was chosen from the arena's length scale and light direction, without a behavioral or physiological fit. Future larger scenes must recheck shadow projection and clipping rather than treating directional-light position as irrelevant.

The actual body comparison used seed 7 and identical initial configurations except illumination. It verified:

- **423 public non-light/non-name-table model arrays match exactly**, including geometry, mass/inertia, contacts, joints, actuators, cameras and sensors. Timestep and gravity also match. The only changed public count/storage scalars are `nlight` 0→1, `nnames` 20981→21012, `nnames_map` 1604→1606 and the model buffer size. Private storage-size and name-offset tables were excluded because adding a named light necessarily changes them; exclusions are explicit in the receipt.
- **`qpos`, `qvel` and contact counts match exactly at all 21 retained sample times** across 1,000 physics steps (0.1 s) of the same `[0.8,1.0]` walking drive. Intermediate steps, contact-pair identity and contact forces were not compared. The frozen receipt's shorter check key refers to these sampled comparisons. This is a bounded dynamics invariance check, not a new locomotion calibration.
- Gain sequence 1→0.5→0→1 leaves `qpos` unchanged, restores exact base light arrays, keeps the headlight disabled and is correctly restored by reset.
- The existing native two-eye retinal pipeline returns finite `(2,721,2)` values. Its maximum gain 1-versus0 change is 0.461302; restoring gain 1 reproduces the original retinal array exactly.
- The isolated 852-axis cube sampler reports no fully black axes at gain 1 in the tested pose; at gain 0 it reports 329 fully black axes. Remaining bright values at zero gain expose the fixed-background caveat, not missing sampling support.

The receipt retains aggregate producer checks for model arrays and native retina restoration, rather than the raw compared arrays. The independent review can inspect those checks but cannot recompute native-retina equality from the stored artifacts alone.

The original viewer processes were left running. No neural backend, motor decoder, source geometry, physics parameter, existing config or default illumination was changed. The optional config enables this rendering improvement explicitly.

## Live viewer inspection

Launch the separate configuration with:

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-world-illumination-probe.json --port 8770
```

The live browser was inspected while running, paused, at light gain 0, and after restoring gain 1 and resetting. The visible **Fixed arena light** label agrees with runtime provenance. At gain 0 the scene surfaces became black while the background stayed gray. On resumed stepping the displayed two-eye means changed from about 0.319/0.311 to 0.252/0.247. These samples occur at different times and are UI response checks, not matched-pose radiometric measurements; the numerical diagnostic above provides that control. While paused, the viewport updates on a lighting intervention but retinal telemetry retains its explicitly displayed sampling time until the next sensor update. Reset restores gain 1, zero simulation time, initial neural/physiology state and initial eye samples. The viewer was left paused and ready to resume. The [UI inspection receipt](../validation/world-illumination/viewer-inspection.json) records the final state and reviewed source hashes.
