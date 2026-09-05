# Rolling FlyBody reference experiment

The standalone rolling-reference task passes its first engineering validation: **exact first-two-second actor/physics parity with the bounded worker, followed by two uninterrupted 12-second trials**. The repeated stop/resume trial passes every declared stopping and resumption window. This prototype is not yet installed in the body bridge, full neural loop, or browser viewer.

The [frozen plan](../validation/flybody-persistent-plan.json), [experiment results](../validation/flybody-persistent-experiment.json), and [saved-trace validation](../validation/flybody-persistent-validation.json) record 108 passing checks. The active plan SHA256 is `d0140c002dab792b13457f0f6d43815d9f611336ddaacb0381faab5735ec00f4`. Each trial stores a hashed native NPZ trace under `runs/flybody-persistent-20260905T025638072453Z/`; raw traces remain local and are not silently substituted with summary checks.

## What changes

The source [WalkImitation task](https://github.com/TuragaLab/flybody/blob/d015e9bfe441bd90ae431bac24c55cb74bdbce26/flybody/tasks/walk_imitation.py) has three finite-recording constraints: a Composer time limit, the trajectory-end condition, and absolute reference indexing. [RollingWalkImitation](../scripts/flybody_persistent_task.py) replaces only this bookkeeping for inference:

- Composer receives an infinite episode time limit. The task retains the source's 10-second construction parameter to create the same 500 static trajectory visualization sites. Those sites do not track the new rolling path, and are not policy inputs.
- The active reference holds 66 poses and 66 velocities. Every actor call still receives exactly 65 reference poses, representing the present and 64 future control intervals, or 128 ms. The extra row supports the source's post-step observation update.
- The task keeps the original absolute control counter and native MuJoCo time. A buffer-origin counter converts to relative index 0 before a step and 1 afterward. A missing command refresh raises an error; it cannot quietly reuse a stale window.
- The target pose integrates the current command continuously. It is never recentered on the physical fly. Future stop/resume schedule edges are not provided to the actor.
- The trajectory-end flag no longer terminates inference. The source's physical conditions remain: linear speed greater than 50 cm/s, angular speed greater than 200 rad/s, root-reference error greater than 0.3 cm, or mixed-unit acceleration norm greater than `1e14`. Native time is never reset to work around a cutoff.

The experiment uses the original policy weights and distribution mean, actor normalization/action order, native float32 action conversion, position actuators, filters, adhesion gain, body, collision/contact parameters, 2 ms control clock, and 0.2 ms physics clock. During rest, the already-tested engineering stance commands adhesion 1 and all 53 position targets 0. The frozen policy is still evaluated with the current zero-speed reference, but its proposed action does not drive a resting body. This is active posture control, not a force-free fly or a measured neural stance reflex.

The experiment's temporary factory injection is limited to a Worker reset and restored immediately afterward. The source checkout and `fruitfly/flybody_worker.py` are not changed. Only inference is supported: training rewards and finite source-recording playback are outside this prototype.

## Exact parity and the cached tail

The bounded and rolling workers receive identical commands: 20 mm/s walking from 0–0.6 s, rest from 0.6–1.2 s, then walking to 2 s. All 1,001 recorded actor evaluations match bitwise, including the unused reset-time warm-up evaluation and 1,000 commanded control evaluations. Each has the same 12 observation keys and 741 float32 values. Mean and native actions, `qpos`, `qvel`, `qacc`, actuator activation, native controls, integrated targets, and native clocks are also bitwise identical. All 380 exposed numeric model arrays match.

The source refreshes 65 rows before an action, then increments its reference index during `before_step`. Its post-step observation therefore includes one row beyond the refreshed window, left over from the original finite trajectory. The rolling task fills that extra row using the same present command. The first 64 cached post-step rows match exactly, while the final cached displacement row differs in 700 samples, by up to 1.43042 cm in one component. Quaternions are identical in these straight-line cases.

This cache difference never enters the actual actor: both workers refresh both reference observations after receiving the next current command. Actual actor inputs were recorded at that boundary and compared directly, not inferred from cached telemetry. The source termination distance uses the first row, which is unchanged. The rolling task's extra row does not anticipate a future command.

## Twelve-second results

Both rolling cases complete 6,000 consecutive control intervals, corresponding to 60,000 native physics steps, with no automatic reset, source termination, or MuJoCo warning. Their final native time is `11.99999999999871` seconds; the largest native-time versus control-counter error is `8.033e-12` seconds. Active reference storage remains constant and each actor observation retains its original shape.

One trial holds the neutral stance for all 12 seconds. A descriptive, additional 0.3–12 s window gives median raw chord speed 0.000541 mm/s and net displacement 0.00699 mm. That window was not a separately predeclared performance gate. The maximum reference error over the entire trial, including initial settling, is 0.02359 mm; the final error is 0.00891 mm.

The other trial walks during 0–0.6, 1.2–3, 3.6–6, 6.6–9, and 10.6–12 seconds, with zero-speed stance between those intervals. All four predeclared stop and resume gates pass:

| Window | Median raw speed | Net displacement | Gate |
|---|---:|---:|---|
| Stop 0.85–1.2 s | 0.00324 mm/s | 0.00115 mm | Pass |
| Stop 3.25–3.6 s | 0.00804 mm/s | 0.00271 mm | Pass |
| Stop 6.25–6.6 s | 0.00579 mm/s | 0.00201 mm | Pass |
| Stop 9.25–10.6 s | 0.00652 mm/s | 0.00886 mm | Pass |
| Resume 1.5–3 s | 19.662 mm/s | 30.011 mm | Pass |
| Resume 3.9–6 s | 19.405 mm/s | 41.917 mm | Pass |
| Resume 6.9–9 s | 19.273 mm/s | 41.920 mm | Pass |
| Resume 10.9–12 s | 19.611 mm/s | 21.964 mm | Pass |

Stopping gates require median raw speed at most 1 mm/s and displacement at most 0.5 mm. Resumption gates require median speed 16–24 mm/s. Speed is calculated from consecutive, unfiltered 2 ms root-position differences in the horizontal plane. The checker records the exact window endpoints; no display smoothing affects these results.

Speed-window inclusion is based on each interval's **end** time, including both declared endpoints. For example, the 0.85–1.2 s stop window includes 176 chords from 0.848–0.850 through 1.198–1.200 s; displacement uses the actual positions at 0.850 and 1.200 s. The independent review records the exact slices, rather than treating every retained chord as wholly inside the nominal window.

The moving trial's maximum root-reference error is 0.4330 mm, maximum source linear speed 4.5005 cm/s, maximum angular speed 31.1428 rad/s, and maximum mixed-unit acceleration norm 572,897. All remain below the unchanged source guard thresholds. The respective 12-second trial wall times are 40.39 and 41.04 seconds, including actor inference and diagnostics but excluding process initialization; concurrent work was running, so these are not isolated performance benchmarks.

## Guard audit and evidence limits

Before each rollout, the experiment checks the initial baseline and isolated injections above each physical guard threshold, then restores the physical arrays. Both bounded and rolling tasks return false for the baseline and true for all four above-threshold cases. The strict `>` comparison is confirmed in source code; exact threshold-boundary equivalence was not tested empirically.

A separate [initialization-only restoration audit](../validation/flybody-persistent-guard-restoration.json) verifies that all 144 exposed numeric data arrays, 380 model arrays, active reference arrays, cached observations, and complete collected worker state are identical before and after the probes. Native time remains zero. There is one disclosed source-only bookkeeping difference: its first termination check creates `_reached_traj_end=False`, where that attribute had been absent. The rolling task already initializes it to false. There is no residual physical or observation mutation, and the frozen actor/physics parity remains exact.

The worker's live `finite` flag checks `qpos`, `qvel`, `qacc`, activations, controls, actuator forces, calculated support/ground forces, and spatial velocity. The NPZ retains the kinematic/control arrays and that flag, but does **not** retain raw force arrays. The saved-trace checker can independently recompute kinematic/control finiteness; force finiteness relies on the recorded live worker check. Diagnostics are recorded every 2 ms, not at each 0.2 ms physics substep. Source or native exceptions would be retained with their partial native state and logs; none occurred in the amended rollouts.

These are two selected deterministic schedules, one seed, straight commanded motion, and the original flat floor. They do not establish indefinite physical reliability, turning transitions, collision robustness, sex-specific biomechanics, biological neural motor control, or success under variable full-brain commands. In particular, this experiment did not put the full connectome or its food/odor feedback into the loop. The next step is separately reviewed integration of the rolling task into the optional bridge, followed by longer closed-loop neural and viewer tests with actual sensory feedback.

## Retained initialization failure and reproduction

The first planned attempt completed the bounded parity trial but failed all rolling cases before reset or any physics step: Composer probes observation shapes during environment construction, before `initialize_episode_mjcf`. The rolling-origin counter initially did not exist at that point. The [original plan](../validation/flybody-persistent-initialization-v0-plan.json), [results](../validation/flybody-persistent-initialization-v0-experiment.json), and exact [task](../validation/flybody-persistent-initialization-v0-task.py) and [runner](../validation/flybody-persistent-initialization-v0-runner.py) are retained. Logs are in `runs/flybody-persistent-20260905T025520517153Z/`.

The amendment initializes the origin in the constructor. It changes no command schedule, performance threshold, controller, or physical guard. The amended plan was saved before rerunning all four cases.

From the repository root, with pinned source and weights already materialized:

```sh
tmp/flybody-env/bin/python -m scripts.experiment_flybody_persistent --run
tmp/flybody-env/bin/python -m scripts.check_flybody_persistent
tmp/flybody-env/bin/python -m scripts.audit_flybody_persistent_guard_restoration
```

The experiment refuses a source/script hash mismatch against the frozen plan. Reproduction should use the saved revision in an isolated checkout and preserve existing result receipts before rerunning; do not overwrite them to conceal a failed repeat. The `--plan-only` mode intentionally refuses to replace an existing plan.

The worker used here is the bounded implementation introduced in repository commit `928e062` and present at `f433f4f`; its byte hash is recorded in the plan. Once an opt-in persistent mode changes the live worker, reproduce this standalone result by checking out the commit that freezes this experiment and its receipts. Running the frozen experiment against a later edited worker is intentionally rejected, even if the new worker supports an equivalent bounded mode.
