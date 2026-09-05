# Independent review of the optional FlyBody bridge

The saved bridge traces reproduce the original source-body stance trials
exactly for the compared native arrays. The action/observation boundary,
reference-preview timing, and unit conversions are consistent with the pinned
source. Four failure-handling defects found during review were corrected by
the owning agents before final review. This supports the bounded integration
test; it does not validate natural male behavior or indefinite operation.

The review is read-only with respect to runtime and native assets. It ran no
physics trajectory, policy inference, full-brain trial, or parameter search.
`scripts/review_flybody_bridge.py` independently reads the saved JSONL/NPZ
arrays without importing the experiment/checker or their metric helpers.
`validation/flybody-bridge-independent-review.json` records hashes and results.

```sh
.venv/bin/python scripts/review_flybody_bridge.py
.venv/bin/python -m pytest tests/test_flybody_bridge.py tests/test_simulation.py -q -k 'not full_graph_reset_chunking'
```

The second command completed with **10 passed, 1 deselected, 9 subtests passed**.
These are pure configuration, mock failure, contact-classification and runner
lifecycle tests. The full-graph/physics test was explicitly deselected.

## Independent array checks

Both saved trials contain 1,001 states and 1,000 submitted actions over 2 s:

| Trial | Largest compared array difference | Largest clock error | Active tarsal contact entries |
|---|---:|---:|---:|
| `zero_start` | 0 | 1.8763×10^-13 s | 6,006 |
| `walk_stop_resume` | 0 | 1.8763×10^-13 s | 4,432 |

Compared every qpos, qvel, attachment pose, actuator length, actuator activation,
tibia angle, claw-site position, uprightness and support sample; also compared
every submitted native action and shadow canonical action. Applied controls
match those native actions in the named actuator order. Saved reference targets
before the next action match the original target sequence. Every saved state
reports finite arrays, zero warnings and no source termination.

Independently summing each saved contact's world-vertical absolute force
reproduces per-leg support exactly. Summing its world force vector and
multiplying by 10 reproduces public g·mm/s² force telemetry exactly. Active
contacts all have nonpositive saved separation. These checks establish saved
data consistency; they do not independently solve MuJoCo constraints. The
support metric includes artificial adhesion and absolute vertical forces, so
it is not net weight balance or biological force validation. Contact entries
are discrete 2 ms samples, not a continuous-contact duration measurement.

The producer additionally tested paused observation, reset, partial-tick and
horizon rejection, rendering and bookkeeping. Those checks are recorded in
`flybody-bridge-plan.json` / `flybody-bridge-validation.json`; this review did
not rerun them on a live worker. All frozen plan, source-trace, bridge-trace,
worker and bridge hashes matched before this independent comparison.

## Source action and clock semantics

The pinned FlyBody source uses 59 native actions: six adhesion controls and
53 position targets. The worker obtains source bounds and names, verifies their
compiled actuator correspondence, and applies the standard clipped affine
canonical-to-native transformation. It uses the original SavedModel's mean,
with float32 observations and preserved source observation keys. The declared
neutral hold sets position targets to zero and adhesion targets to one while
retaining the original 10 ms position and 7 ms adhesion filters.

The walking factory sets 2 ms control, 0.2 ms physics, and 64 future frames.
Before each action the worker rebuilds the current 65-row, 128 ms preview and
refreshes only the two reference observations against the current physical
state. This matches the task's pre-step `_step_counter` indexing. The original
synthetic helper constructs quaternion velocity with a unit timestep despite
forming a 2 ms rotation; the worker's explicit yaw velocity corrects that
per-step value to rad/s. The target integrates submitted commands, with no food
coordinates or future intervention schedule entering the policy target.

The 1,100-row reference safely accommodates the declared 1,000 control ticks
plus preview. Source termination conditions remain enabled; the 2 s limit is
an explicit adapter boundary. The runner rejects other coupling intervals and
does not round the old 5 ms schedule to a fractional policy step.

## Physical feedback and measurement points

Positions and velocities convert cm→mm and cm/s→mm/s by 10. Odor sampling then
converts mm→m for the existing puff field. Joint angles and velocities remain
rad and rad/s. Native gravity and dynamics are unchanged. Resource markers are
noncolliding sites; a taste event requires an active tarsal ground contact at a
point within the configured region, not proximity of the body origin.

The sensor point matters. `antenna_positions_mm` samples the named left/right
antenna **body-frame origins**, not registered receptor locations. The public
pose is the free-joint attachment origin. MuJoCo's `mjOBJ_BODY` velocity uses
the thorax **inertial center**, whereas `mjOBJ_XBODY` would use the body-frame
origin. Current speed is therefore legitimate thorax-center feedback but is
not exactly the derivative of the reported pose during rotation. This follows
the [MuJoCo 3.2.7 implementation](https://github.com/google-deepmind/mujoco/blob/3.2.7/src/engine/engine_support.c#L1165-L1210)
and the local dm-control `Entity.get_pose` implementation. No frozen runtime
change was requested; the measurement distinction must remain documented.

Tibia feedback uses actual source hinge state in LF/LM/LH/RF/RM/RH order. Coxa
and femur keys retain source naming; claw height is explicitly different from
the other backend's tarsus-body origin. The optional club gain is still an
engineering encoder. Head-frame wind, compound vision, grooming, and a
physiological proboscis remain unsupported and are rejected/disabled rather
than silently synthesized.

## Failure and process review

The owners corrected these concrete issues identified in the initial diff:

1. The runner now preflights the entire requested duration against the body
   horizon before changing sensory, neural or motor state. Previously a request
   crossing 2 s could advance the brain before the body rejected it.
2. Failed body ticks and failed final snapshots now append a structured receipt
   with cached raw body diagnostics, brain time, original error and pending
   interval information. Nonfinite values are represented as null while the
   failure flag is retained; ordinary snapshots need not succeed.
3. A finite partial native-step failure retains its true clock/state and the
   original worker error without advancing a full 2 ms host physiology tick.
   Previously the host's clock check could mask that error.
4. Transport timeout, EOF or framing failure terminates the worker transport;
   later RPCs fail rather than consuming a late reply as the next response.

Stdout is reserved through a duplicated descriptor; native library output is
redirected to the retained worker log. Requests/replies carry a protocol
version and matching request ID, length bounds and explicit RGB byte counts.
Physics and rendering remain owned by the isolated Python 3.10 process.
Environment versions and source/policy asset hashes are checked at startup.
Explicit close/EOF paths release native resources; the bridge terminates and,
if needed, kills/reaps an unresponsive process. Runner cleanup still executes
when final snapshot recording fails. A failed body tick prevents subsequent
advance until an explicit reset; a broken transport requires a new runtime.

The review checked these paths in code and the mock regressions. It did not
inject process kills, fragmented writes, disk exhaustion or numerical failures
into a live physics process. Full-neural loop outcomes are separate evidence
owned by the integration trial, and must retain any instability or absent
behavior without adjusting the frozen motor map to make the run succeed.
