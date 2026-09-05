# Optional rolling FlyBody runtime

The real Python 3.12 host / Python 3.10 policy-and-physics bridge reproduces the saved standalone rolling trajectory through **12 simulated seconds**. All three planned bridge comparisons pass. The [source review](flybody-rolling-runtime-review.md), [frozen plan](../validation/flybody-rolling-bridge/plan.json), [results](../validation/flybody-rolling-bridge/results.json), and [independent saved-journal review](flybody-rolling-bridge-review.md) retain the evidence. Subsequent [full-neural trials and browser inspection](flybody-rolling-loop.md) also pass their engineering checks; their sensory-only negative behavior and physiological limits remain explicit.

## Explicit configuration

The existing FlyBody default remains `reference_mode: "bounded", horizon_s: 2.0`. The optional [rolling config](../configs/male-flybody-rolling-probe.json) requires both `reference_mode: "rolling"` and `horizon_s: null`. Inconsistent combinations fail before allocating the public worker. The source body, learned policy, 0.2 ms physics, 2 ms control, native actuator gains/filters and all physical failure limits are unchanged.

The [runtime task](../fruitfly/flybody_persistent_task.py) has the same algorithms as the standalone task frozen at `2853db9`. It replaces finite trajectory bookkeeping with 66 fixed rows, 65 current-command actor preview rows, an absolute control counter and a relative buffer origin. It retains a continuously integrated target, with no reset or recentering at former recording boundaries. Native failures still stop the run and preserve diagnostics.

The worker records a SHA-256 of each actual 741-value float32 actor input before TensorFlow conversion, plus reference shapes, buffer origin and source counter each control step. Metadata records observation key order/shapes, mode, task hash and original source/policy receipts. Both modes share the policy/action/physics/error implementation.

## Actual bridge comparisons

| Comparison | Checked samples (including reset state) | Native duration | Result |
|---|---:|---:|---|
| Bounded stop/resume | 1,001 | 2 s | Exact saved native fields and actor-input hash |
| Rolling stop/resume | 1,001 | 2 s | Exact saved native fields and actor-input hash |
| Rolling repeated stop/resume | 6,001 | 12 s | Exact saved native fields and actor-input hash |

The comparison covers qpos, qvel, qacc, activation, controls, native/canonical actions, integrated targets and native times at every sample. Actor key order/shapes also match. All warning counters remain zero; actual reference shapes/counters stay consistent. Maximum clock discrepancy is **8.03e−12 s**, and maximum reported normalized resource residual is **3.34e−15**. Explicit reset reproduces the initial native state. The checker asserts initial render/zero-step invariance and unchanged state after bounded-overrun rejection.

The independent reviewer checked **138 conditions across 8,003 samples**, including IEEE-byte comparisons after restoring reference dtypes, actor hashes, recorded inventories and force aggregation. Raw journals retain native force diagnostics, although the earlier standalone NPZ lacks raw forces for a cross-run comparison. Complete host physiology ledgers and per-render raw before/after arrays are not retained by this particular checker; its reported residuals and render assertions must not be overstated as independent reconstruction of those missing arrays.

Raw journals are local under `runs/flybody-rolling-bridge-20260905T031039860921Z`. The tracked plan/result/review identifies their hashes. Replay requires the pinned assets and recorded source revision; keep original artifacts intact when repeating.

## Retained comparison slowdown

The first checker repeatedly accessed compressed NPZ members inside the tick loop, decompressing whole reference arrays each time. Both two-second cases passed. The owner interrupted the slow twelve-second comparison with SIGINT during NumPy decompression; its journal retained 2,179 states and 2,178 completed comparisons, with no physical termination. This was an operational interruption of the checker, not a source-body failure.

The [initial plan, checker and result](../validation/flybody-rolling-bridge-initial-checker) remain unchanged. The amendment loads each verified reference array once, leaving physics, commands, tolerances and comparison arithmetic unchanged. Its new plan was frozen before rerunning all three cases. The successful cases took 17.28, 16.33 and 57.09 wall seconds including initialization, rendering, comparison and journaling; concurrent work was present, so these are not isolated performance benchmarks.

## Remaining gate

Use the [full-neural integration plan](flybody-persistent-runtime-plan.md) for the longer closed loop. These body/RPC results do not themselves test variable neural commands, natural foraging, walls/obstacles, biological stance, a male morphology reconstruction or indefinite reliability. The original floor is unbounded. The source's ghost and static trajectory markers are observer aids, not another simulated animal or a continuously updated path prediction.
