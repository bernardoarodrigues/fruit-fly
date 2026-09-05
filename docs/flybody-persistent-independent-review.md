# Independent review of the rolling FlyBody task

**The saved-array review passes for all 14,000 commanded control steps.** The rolling task preserves the bounded worker's complete actual policy inputs and physical trajectory for the two-second comparison, and both longer trials reach twelve seconds without reset or source termination. This supports the standalone rolling-reference change for the tested commands. It does not establish a working persistent full-brain viewer.

The [review script](../scripts/review_flybody_persistent.py) independently reads the saved NPZ arrays and performs numerical calculations without importing the experiment, checker, `fruitfly` runtime, MuJoCo, TensorFlow or the source task. No physics, policy inference or neural run was repeated. Its [receipt](../validation/flybody-persistent-independent-review.json) pins artifacts and separates independent calculations from source-reviewed producer assertions.

## Provenance and parity

The [amended plan](../validation/flybody-persistent-plan.json) hash is `d0140c002dab792b13457f0f6d43815d9f611336ddaacb0381faab5735ec00f4`. All declared script, worker and data-receipt hashes match, as do the raw NPZ hashes and [producer checker receipt](../validation/flybody-persistent-validation.json). Every file in the pinned source manifest was checked against the local checkout at upstream commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`.

The bounded and rolling comparison contains 1,000 actual actor calls each, with **all 741 float32 inputs bitwise equal**. The extra unused reset-time evaluation also matches. All twelve observation keys and shapes agree. Native and canonical actions, `qpos`, `qvel`, `qacc`, activation, controls, integrated targets, native times, root poses and reported native velocities are bitwise equal. The recorded hashes of all **380 exposed numeric model arrays** match. This includes the source position actuators, filters and physical parameters; the reference-storage change does not require changing the learned policy weights or body.

There is a real difference in the unused post-step observation cache. Its first 64 reference rows match, but the final cached displacement row differs in 700 samples, by up to 1.43042 cm in one component. The cached quaternion rows agree in these straight-line trials. Both workers explicitly refresh the reference observables after receiving the next command, before calling the policy. Direct inspection of the complete actual actor inputs confirms that this cached difference does not reach that comparison's policy.

## Causal rolling reference

The source task used absolute positions in a finite reference recording. The rolling task keeps its absolute control counter and native time while mapping the buffer origin to relative offset 0 before each step and 1 afterward. It installs 66 current-command poses and velocities, delivers rows 0–64 to the actor, and makes rows 1–65 available to post-step observations. An absent or stale refresh is an error. The source's present-plus-64-step actor preview remains 128 ms at the 2 ms control period.

The independent reviewer reconstructed **all 910,000 actual reference rows** across the four trials from the preceding native root pose, saved target and current command. For these straight, zero-yaw schedules, each future target advances by 0.004 cm per row when walking and remains fixed during rest. Transforming these world displacements into the previous body's quaternion frame reproduces every actor displacement after float32 conversion exactly. The inverse body quaternion similarly reproduces every actor reference quaternion. This is stronger than checking preview length alone: the complete 65-row reference has the expected geometry and time direction.

The target is integrated from its previous commanded position. The reviewer checked every next target exactly; it is never recentered on the measured fly pose. Native times and source counters remain continuous through all 6,000 control steps of each long run, including the original ten-second boundary. Maximum clock discrepancy is below 10⁻¹⁰ s. The active recorded reference position shape remains `(66, 7)` at every sample. Reference velocities are allocated `(66, 6)` and assigned in place in the inspected task; their complete per-tick arrays/shapes were not recorded, so that part is source evidence rather than an independent array trace.

The task retains the original 500 static trajectory visualization sites created during initialization. Those are not the rolling path display or actor inputs. The source's inference reward is unchanged; ordinary finite-recording training is outside this modification's supported scope.

## Native control and twelve-second measurements

All commanded schedules match their declared tick boundaries. Native action order agrees with the separately audited actuator IDs. Every walking action exactly equals the original float32 clipping/scaling operation on the saved canonical action. Every off action is precisely six adhesion values of 1 followed by 53 neutral position targets of 0. Rest retains active posture control.

The repeated-switch trial passes all four stopping windows and all four resumption windows. Independently recomputed median raw chord speeds are 0.003244, 0.008042, 0.005792 and 0.006519 mm/s during stops and 19.6622, 19.4046, 19.2731 and 19.6107 mm/s after resumption. The all-rest trial has a descriptive 0.3–12 s median of 0.000541 mm/s and 0.006990 mm net displacement. That all-rest speed window is diagnostic, not an additional predeclared gate.

**The speed and drift windows use slightly different lower-edge conventions.** The checker includes a chord according to its completed interval's end time, including the lower endpoint. For example, stop 0.85–1.2 s selects `speed[424:600]`: 176 chords starting at 0.848–1.198 s and ending at 0.850–1.200 s. Drift is the difference between positions at 0.850 and 1.200 s. Every exact slice and sample count is retained in the independent receipt. No smoothing was used and no gate was recomputed with a more favorable window.

Root reference error was independently recalculated from saved target and physical root positions. Its maximum in the moving trial is 0.0433004 cm (0.433004 mm), below the source's 0.3 cm guard. The maximum saved source speed is 4.50048 cm/s, angular speed 31.1428 rad/s and acceleration-vector norm 572,897 in native mixed units. All recorded kinematic/control/actor arrays are finite, warning counters are zero, and no saved step is a source termination. The two long traces end at `11.99999999999871` s.

## Guards, restoration and failures

Source inspection confirms that the rolling predicate retains the original strict `>` tests for velocimeter norm above 50 cm/s, gyro norm above 200 rad/s, root-reference error above 0.3 cm, and the base task's full acceleration-vector Euclidean norm above `1e14` mixed units. `Walking` does not override the base acceleration predicate. The rolling implementation removes the finite-recording end condition and Composer time limit; it does not relax a physical threshold or add a pose/velocity clamp. The reference distance is based on the root pose used by the source observable, despite the source variable's “com” name.

The initial guard probes return false at the baseline and true after each isolated 1%-above-threshold injection for both tasks. The experiment restores `qacc`, sensor data and reference positions after each probe, including its `finally` path. Source `check_termination` also sets `_reached_traj_end`. The bounded task initially lacks that attribute; the probe leaves it newly present and false. The rolling task already initializes it to false. Therefore **exact whole-object restoration is not true for the source task**, although this bookkeeping addition does not change the saved actor/physics parity.

The separate [restoration audit](../validation/flybody-persistent-guard-restoration.json) reports unchanged 144 numeric data arrays, 380 model arrays, both reference arrays, cached observations and collected worker state with zero elapsed physics steps. Its implementation and receipt hashes match. That receipt stores equality booleans and array counts rather than all before/after arrays or individual hashes, so numerical restoration remains a source-reviewed producer assertion. No independent construction or probe run was performed in this review. Exact threshold-boundary behavior was not empirically tested; strictness is established from source code.

The [original attempt](../validation/flybody-persistent-initialization-v0-experiment.json) remains available. The bounded trial completed; all rolling processes failed while Composer was probing observation shape because `_rolling_origin` had not yet been initialized. Their logs retain the corresponding `AttributeError`. The amended task initializes this field in its constructor, before that probe. This is an initialization failure, not a twelve-second native dynamics failure.

The worker code preserves a partial native state and source exception on a failed step and marks nonfinite/source-LAST results as failures. However, the successful rollouts and direct predicate probes do not exercise an actual failing native step. They do not independently prove exception/partial-step handling or recovery from arbitrary physical failures. No such failure was fabricated or hidden to make these results pass.

## Remaining limits

The NPZ contains actor force sensors, which were checked for finiteness, but does not contain all raw native actuator/contact forces. The worker's `finite` flag includes actuator-force and calculated support/ground-force arrays. Independent array finiteness and the broader producer flag must remain separate claims. Diagnostics sample each 2 ms control step, not every 0.2 ms native substep.

The evidence covers one seed, two selected twelve-second straight/rest schedules and the original flat floor. It does not validate turning commands, obstacles, long-run statistical reliability, biological stance or sex-specific biomechanics. The full connectome, odor/taste feedback, physiology and browser lifecycle are outside this standalone experiment. Integration and actual longer closed-loop trials remain necessary.

With the pinned code and local raw traces retained, rerun only the saved-data review using:

```sh
.venv/bin/python scripts/review_flybody_persistent.py
```

The raw NPZ files are ignored local artifacts under `runs/flybody-persistent-20260905T025638072453Z/`. A fresh clone needs those exact files to repeat this review. Later runtime changes must not be substituted for the experiment's frozen worker/script hashes.
