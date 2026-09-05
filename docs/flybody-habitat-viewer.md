# Actual habitat viewer and retained wall failure

The [browser inspection receipt](../validation/flybody-habitat-viewer/inspection.json) covers the actual full-graph viewer at source commit `ef6e230`, under a [frozen plan](../validation/flybody-habitat-viewer-plan.json). It is separate from the native controller tests and from subsequent rendering changes. Commands were clicked in the Codex in-app browser; screenshots and accessibility trees were inspected. The retained local HTTP state/frame files are the server's actual outputs, not reconstructed animation.

The sensory viewer on port 8774 displayed the 166,700-cell graph and the 30 × 24 mm habitat. Overview, Follow and Side cameras changed while time remained zero. Resume advanced the neural/body loop; Pause stopped it at **0.890 s**, with an unchanged clock and frame over the following wall second. The fly remained at rest. Reset restored exact initial pose, senses, physiology, neural telemetry, stimuli, physics, behavior and body metadata. No food approach or successful foraging is claimed.

The separate `configs/male-flybody-habitat-wall-contact.json` selects **Controller-only baseline**, and the page explicitly says its walking commands bypass neural activity. The full graph still evolves and receives sensory inputs. This isolates a known straight-command physical failure for the viewer check; it is not evidence of neural walking selection.

One Resume on port 8775 produced the source physical termination at **tick 384 / 0.768 s**. The viewer worker exited, controls became disabled, and the image was labeled **LAST FRAME / SIMULATION STOPPED**. The message correctly distinguished these four values:

| State represented | Time shown |
|---|---:|
| Last rendered image | 0.7500 s |
| Last completed telemetry update | 0.7600 s |
| Neural clock at failure | 0.7680 s |
| Native physical clock at failure | 0.7680 s |

The cached failure exactly equals the run's single `failures.jsonl` entry. It includes the pending walking action, actual native state and active positive-x wall contact. Later read-only API queries returned identical failure/telemetry and image bytes, with unchanged frame time/sequence and increasing frame age. No post-failure render, reset, retry or recovery was requested. The earlier image is not presented as the failed physical pose. The API equality, terminal state, reset and age checks pass all **10 recorded conditions**.

This first display correction fixed the jagged resource discs, but the actual close views exposed **residual shadows from the reference trajectory**, even with its visible alpha set to zero. The images and that failed visual observation remain retained. They are not final clean-render evidence; removal from the derived scene requires a separate source version and inspection. The source floor also reflects the actual fly, which is a rendering property rather than a second simulated animal.

The [final display addendum](../validation/flybody-habitat-viewer-final/inspection.json) now verifies source commit `62129a3` in the actual browser. It removes reference objects from the derived scene, including their shadow/reflection passes. The restarted 8774 viewer's overview, follow and side images show clean resources and no dotted reference artifacts; the real fly's floor reflection remains. All three camera snapshots preserve the earlier reset's pose, senses, physiology, neural telemetry, stimuli, physics and behavior. The ten final receipt checks pass, and the viewer is left paused in overview at t=0. This addendum performs no neural evolution or new wall-contact trial. Its [separate frozen plan](../validation/flybody-habitat-viewer-final-plan.json), images and exact source hashes preserve the distinction from the earlier control/failure experiment.

At `ef6e230`, the complete Python suite passed **175 tests and 54 subtests**, with 22 existing Brian2 parser deprecation warnings. JavaScript syntax validation also passed. Those checks and the successful failure display do not convert the native wall-contact termination or the earlier contact-force gate failures into successful avoidance.

After final scene removal, the focused habitat/bridge suite also passes **11 tests and 26 subtests**; the separate native scene validation passes 26/26 checks, including complete compiled-model invariance and 101 exact controller-state samples.

```sh
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-rolling-habitat.json --port 8774 --paused
.venv/bin/python -m fruitfly.viewer --config configs/male-flybody-habitat-wall-contact.json --port 8775 --paused
```

The second command is a deliberate failure demonstration. After a terminal error, stop that viewer process and launch a fresh run to repeat it; the failed instance stays terminal. See [native habitat evidence](flybody-habitat.md) and the [failure-reporting contract](viewer-failure-reporting.md).
