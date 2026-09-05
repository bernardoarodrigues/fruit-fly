# Review of optional rolling-reference runtime integration

**The reviewed runtime is ready for the declared bridge parity experiment.** No functional blocker remains in the reviewed changes. This is a source review before those experiments; it is not a claim that they have passed. No new physics or neural run was performed by the reviewer. The review covers `fruitfly/flybody_worker.py`, `flybody_bridge.py`, `simulation.py`, the new `flybody_persistent_task.py`, the rolling example configuration, its browser label, and `scripts/check_flybody_rolling_bridge.py`.

## Runtime findings

No functional blocker was found in the reviewed mode selection, import path, clock handling or metadata flow. Bounded mode remains the default with a two-second horizon. Public rolling configuration requires both `reference_mode: "rolling"` and `horizon_s: null`; incompatible combinations fail before the public runtime starts a worker. The runner and body adapter skip only the finite-horizon check for `None`; native and neural clock agreement remains checked during actual coupled steps.

The dedicated worker runs under the existing pinned Python 3.10 environment. Importing `fruitfly.flybody_persistent_task` is valid after the repository root is placed on its path: `fruitfly/__init__.py` is lightweight and does not pull the host FlyGym/MuJoCo stack into that process. Source/policy verification and version checks remain intact. Both modes use the common action, native step, observation, error and cleanup code. Reset recreates the same selected mode and initializes the actor hash before the initial state is collected.

The new task's parsed syntax tree is **identical to the standalone task at commit `2853db9` except for its module docstring**. Constructor-time rolling-origin initialization, the fixed 66-row reference, absolute counter, offset-0/1 observation lifecycle and physical guards are unchanged. Runtime integration uses the same 65-row bounded versus 66-row rolling preview generation, installs the rolling preview at the current absolute tick, refreshes both actor reference observations, and advances the integrated target by preview row 1. No advance-path assignment recenters the target on the actual fly pose.

The actor hash is calculated over the actual dictionary-ordered float32 observation values before those values are converted to TensorFlow tensors. This adds observation evidence without changing tensor values or policy action calculation. The hash identifies values, not their semantic names/shapes; the corrected bridge checker separately compares the observation key order and shapes with the saved standalone schema.

Native metadata distinguishes `reference_mode`, nullable horizon, actual initialized reference-array length, preview length and rolling task source hash. Host snapshots use the same nullable horizon and publish the persistent-reference capability only in rolling mode. The browser's label derives the mode from backend metadata and retains the engineering motor-surrogate wording. Existing viewer handling of `horizon_s: null` bypasses finite-trial completion, while explicit reset remains available. A source review alone does not prove the rendered persistent viewer lifecycle.

Both the public dataclass and private worker now reject a rolling configuration that omits the explicit null horizon. The public host sends the complete validated dataclass. Legacy private bounded initialization still defaults to the existing two-second horizon when that field is absent.

## Checker findings raised before freezing

Two evidence issues were reported and **corrected before freezing the bridge plan**:

1. The initial checker compared the hash of concatenated actor values but did not compare `actor_observation_shapes` and key order against the saved standalone actor schema. The corrected plan retains that schema, and the checker explicitly compares metadata key order and shapes before stepping. It also compares source commit, source/policy receipts, dependency versions and Python version with the reference provenance.
2. Its initial `exact_actor_hashes` and `exact_native_fields` summaries were set to true before comparison and left true even after a failed assertion. Those misleading fields were removed. The case's result now reports its actual failure and the number of successfully checked samples.

The owner also added per-step read-only reference-position and reference-velocity shapes, source control counter and buffer-origin diagnostics. The corrected checker validates the 1100-row bounded or 66-row rolling shape, six velocity columns and seven pose columns at every sample. The post-step rolling buffer origin must equal `max(0, tick-1)`, matching the preview installed before that physical step. These reads do not alter the task's arrays or counters.

The checker otherwise compares every native/action/target/time sample to a pre-existing hashed reference and tests initial zero-duration/render invariance, bounded overrun rejection, explicit reset and host resource residuals. It flushes sample events before the comparison assertions, retaining the native state that caused a mismatch. It does not run the connectome; body/RPC parity is a prerequisite for the separate coupled experiment.

## Limits that must remain visible

The metadata's reference-array length is sampled at initialization, and the new diagnostics supply both current array shapes and counters every tick. The checker can therefore verify storage shape throughout each bridge trial. Complete reference-array values are still not transmitted: actual actor-value hashes, physical/action parity and the inspected target-generation code support the reference-content claim. The plan explicitly declares this limit.

Complete native force arrays are not present in the standalone NPZ reference. The worker's finite flag checks a wider set of arrays than the raw arrays available for independent comparison. Source/warning/clock checks and raw kinematic parity do not establish biological forces, natural stance or arbitrary physical failure recovery.

Reference trajectories cover straight walking/rest for the bridge comparison; the later full-neural experiment must test actual changing motor commands and sensory feedback. Twelve seconds of earlier standalone stability does not prove indefinite robustness, turning, obstacles or a successful persistent browser session. Successful runtime startup, bridge parity, longer full-graph trials and live viewer checks remain separate evidence requirements.

After this pre-run source review, the [actual bridge experiment](flybody-rolling-runtime.md) passed both two-second comparisons and the twelve-second comparison. A read-only checker performance amendment and its interrupted initial attempt are retained separately. The [saved-journal review](flybody-rolling-bridge-review.md) supplies the subsequent independent evidence; this original source-review scope is unchanged.
