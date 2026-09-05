# Eon follow-up: a concrete protocol to reuse

Follow-up on 2026-09-05 UTC to the user's request to inspect Eon's working embodiment. **The useful discovery is an additional public demo notebook with explicit walking-context and taste-input experiments.** The initial audit concentrated on `fly-brain`'s benchmark entrypoint and underweighted this integration evidence. The [expanded repository audit](15-eon-public-code-audit.md) records the current source revisions and release scope.

## What the article contributes

[Eon's March 10 account](https://eon.systems/updates/embodied-brain-emulation) describes taste-cue navigation, feeding and dust-triggered grooming using a Shiu-derived FlyWire model, NeuroMechFly/MuJoCo and selected neural outputs. Its forward readout is oDN1; steering uses DNa01/DNa02; feeding uses MN9. Sensory and motor gains are hand chosen, with 15 ms brain/body exchanges. Vision contributes little to demonstrated behavior. The body does not use the full biological motor hierarchy. These are useful engineering choices for a working embodiment. Exact online mappings and the start-of-walking mechanism are not specified by the article.

The original tutorial links now return 404. The authors' [current documentation](https://neuromechfly.org/tutorials/index.html) points to the legacy Gymnasium tutorials; the current [hybrid controller](https://neuromechfly.org/tutorials/4c_hybrid_controller/) combines CPGs, measured step trajectories and reflex corrections. Eon's description of imitation-trained controllers does not identify their private modifications or establish that an arbitrary current tutorial is the exact demo policy.

## The additional source that changes the next experiment

The pinned [demo notebook in `drosophila_brain_model_lif`](https://github.com/eonsystemspbc/drosophila_brain_model_lif/blob/c976c7a90b2ac5a472c028b5862974217e93573f/results/eon_1/demo_notebook.ipynb) supplies a more specific starting point:

- Bilateral **P9 activation at 100 Hz** establishes an imposed locomotor context. **P9/DNp09 is distinct from the oDN1/DNg97 forward readout.**
- `P9_legs` adds twelve named lgAG2 cells and two ascending-leg cells at 200 Hz. Separate experiments activate each ascending cell on the same P9 background.
- Labellar sugar and sugar-plus-bitter are separate experiments; they should not be silently combined with P9 or substituted for tarsal input.
- The imported source defaults are 1 s and 30 trials. Its stored tables are upstream results, not a local rerun or a verified history of the embodied video.

The saved table in cell 38 is especially informative (rounded here, Hz):

| Stored condition | oDN1 L / R | DNa02 L / R |
|---|---:|---:|
| P9 only | 14.83 / 10.73 | 17.03 / 6.43 |
| P9 + bilateral leg set | 8.80 / 8.63 | 20.93 / 22.47 |
| P9 + notebook-labelled left ascending cell | 16.77 / 12.07 | 28.97 / 6.33 |
| P9 + notebook-labelled right ascending cell | 6.13 / 11.73 | 11.17 / 30.03 |

This gives concrete targets: altered walking output and lateralized steering during an already active locomotor context. It also exposes unequal baseline steering rates. We should measure stimulus-induced changes and baseline bias before fitting any motor offset. These are simulated source responses, not measured biological firing rates.

The [ascending-leg crosswalk](../docs/eon-leg-afferent-crosswalk.md) identifies a material transfer issue: the two source IDs share FlyWire type `AN_GNG_162`; MaleCNS has eight type-level candidates. The notebook's side labels differ from released nerve-entry sides. A represented leg and a nerve-entry side need not mean the same thing. Neither a one-to-one male pair nor a side reversal is justified without further evidence. Activating these ascending neurons also enters the circuit at a different level from activating peripheral GRNs.

## Comparison with our current implementation

The [executed read-only comparison](../validation/eon-interface-comparison.json) verifies 12 readout cells with optional grooming enabled and 8,276 incoming neuron-pair edges. The default decoder without grooming has ten readout cells. This uses the unchanged, checksum-verified full male graph. No neural or body simulation ran in this comparison.

| Component | Current local evidence | Consequence |
|---|---|---|
| Forward and steering readouts | DNg97/oDN1 and DNa01/DNa02 are already selected in `MotorDecoder` | Renaming or replacing the walking output is not the missing step |
| Locomotor drive | Existing calibration directly drives DNg97; sensory-only assays do not provide P9 context | The upstream P9 protocol is a distinct experiment worth reproducing |
| Taste entry point | 54 LgAG2/LgLG4 peripheral cells, six physical leg-contact channels, 100 Hz | This differs in cell populations, hierarchy and rate from Eon's notebook |
| Body controller | Existing NeuroMechFly `HybridTurningController`; optional FlyBody branch | Use the existing NeuroMechFly branch first to reduce comparison differences |
| Graph | Full male CNS, including VNC; Eon's neural source uses female FlyWire | Shared parameter names do not make the models equivalent |

The previous 0.5 s on-food **taste-only** trial already produced feeding and steering, with 0.586 mm net XY displacement. It did not demonstrate approach from outside food. The odor-only failure therefore does not establish that the whole male graph is incapable of sensorimotor behavior. Taste and odor need separate assay conclusions. The taste trial itself reached a sampled minimum of **−284.05 mV**; its physical outputs do not resolve the model's voltage failure.

The named dominant inhibitory types in the earlier odor diagnostic—VES104, GNG127, CB0677, PS059, MBON31 and MBON32—are all annotated central-brain intrinsic neurons. This is not a VNC-ablation experiment: their upstream activity may still depend on the cord. It supplies no evidence that removing VNC neurons would repair navigation.

## Change in work order

1. Reproduce the **P9-to-oDN1 locomotor-context assay** on the full male graph with explicit imposed input, output-block and no-input controls. This is a source-protocol transfer test, not natural spontaneous walking.
2. Add the existing verified male peripheral taste inputs; keep unknown ascending homologs separate. Compare P9 alone, taste alone and their combination before changing global synaptic gains. Then test unilateral inputs and stimulus withdrawal.
3. Couple a successful, declared interface to the existing NeuroMechFly controller and inspect an actual taste-driven sequence. Ground contact remains the source of tarsal taste. A distant virtual taste field would be a separately labelled engineering model.
4. Test odor background as a distinct interaction, followed by 5 versus 15 ms coupling. Measure what each change contributes.

The [replication design](../docs/eon-taste-replication-design.md) expands these steps. The separate [inhibitory factorial proposal](../docs/inhibitory-factorial-design-review.md) remains prospective and paused. Physiological calibration remains necessary, but it need not precede testing this more closely matched integration protocol.

**New project hypotheses:** imposed locomotor context and sensory entry level may explain part of the difference between the working source assay and our sensory-only trials; baseline steering asymmetry may require a calibrated decoder. None is established as the cause of Eon's video behavior or as a new biological discovery. No runtime default, graph weight, viewer state or scientific milestone was changed by this audit.
