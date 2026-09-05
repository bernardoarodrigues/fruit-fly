# Eon public code: useful interface evidence and release scope

Fresh read-only audit on 2026-09-05 UTC, prompted by the user's request to revisit Eon's embodied demonstration. **The most useful additional finding is Eon's explicit neural test recipe: ongoing P9 stimulation accompanies leg-taste and other sensory perturbations, while oDN1 and several other named cells are read out.** This is a concrete starting point for a separate replication. It does not establish the undisclosed physical demo's exact inputs or gains. No downloaded code was executed, no model was loaded, and no local runtime or parameter changed.

The current `fly-brain` head is still `a3db62f9436074e485c0278290c2164ed6150808` (commit date 2026-08-29). The earlier [audit](07-reference-code-audit.md) remains correct about its benchmark entrypoint, but omitted useful notebook-level details and the other public Eon repositories. Current API snapshots, source hashes and static extractions are retained below.

## What is public now

| Author repository and pinned revision | Inspected contents | Reuse boundary |
|---|---|---|
| [fly-brain, a3db62f](https://github.com/eonsystemspbc/fly-brain/tree/a3db62f9436074e485c0278290c2164ed6150808) | Six neural backends; v783 connectivity; benchmark CLI; original/adapted notebooks. One branch, no tags or releases at retrieval. | Neural implementation and experiment references. Inspected Python/notebook sources do not contain a physical body loop or sensory-to-controller bridge. |
| [drosophila_brain_model_lif, c976c7a](https://github.com/eonsystemspbc/drosophila_brain_model_lif/tree/c976c7a90b2ac5a472c028b5862974217e93573f) | Shiu fork with `results/eon_1/demo_notebook.ipynb`, including leg-taste and unilateral ascending-neuron experiments. One branch, no releases. | Particularly useful named-cell recipes; notebook output tables are not newly reproduced results. |
| [flybody, dd72f41](https://github.com/eonsystemspbc/flybody/tree/dd72f4138d2c4a4dc6797227a12d1e89ffc104c9) | Native MuJoCo/RL body tasks and policy examples. GitHub comparison reports zero commits ahead and one behind current TuragaLab upstream. One branch, no releases. | Existing upstream body/controller resources; no Eon-specific brain bridge found. Its presence does not establish this is the body used in the March NeuroMechFly demonstration. |
| [pathintegrationBPU, 943c55e](https://github.com/eonsystemspbc/pathintegrationBPU/tree/943c55ef6eecfd8bc97d38e1b5154f89940ad333) | Connectome-derived RNN experiments, task/region selection, optic flow, associative memory and plume subproject. | A separate research program. `embodied_foraging` specifies channel names; it is not an implemented Shiu/MuJoCo embodiment in the inspected main sources. |

The public organization API lists these four plus `NEURD-sandbox`, described as proofreading/data transformation tooling and not audited further here. All downloaded tree responses are nontruncated. Five non-main BPU branches were inventoried by filenames only; their full content was not audited. This is a bounded public-source finding, not a claim about private code, unlinked author repositories or every historical branch.

## Exact neural model and stimulation

The Brian2 runner uses `dv/dt=(v0-v+g)/20 ms` and `dg/dt=-g/5 ms`, each marked `unless refractory`; resting/reset voltage is −52 mV, threshold is strictly above −45 mV, refractory 2.2 ms, delay 1.8 ms, and each signed contact contributes 0.275 mV to the synaptic state. Spiking resets voltage and synaptic state. These are the Shiu-style current-based equations; `g` has voltage units and is not a receptor conductance with a reversal potential. The inspected equations provide no inhibitory voltage floor. [Runner source, lines 36–58 and 80–97](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/run_brian2_cuda.py#L36-L97).

Poisson stimulation adds `250×0.275=68.75 mV` directly to voltage and sets the stimulated cell's refractory interval to zero. It represents imposed activation, not measured receptor transduction. The original notebook imports defaults of 1,000 ms and 30 trials, without overriding either. [Original model defaults and stimulation](https://github.com/eonsystemspbc/drosophila_brain_model_lif/blob/c976c7a90b2ac5a472c028b5862974217e93573f/model.py#L15-L118).

The PyTorch backend uses 0.1 ms Euler-style updates, Bernoulli draws with probability `rate_Hz×0.0001`, signed sparse recurrent weights, and a delay buffer. It has an explicit per-step state interface, but its benchmark supplies a constant rate tensor. It chooses CUDA or CPU, not MPS. Names such as `AlphaSynapse` and `conductance` do not change its actual first-order equations. Its current wrapper uses only `neu_exc`; the configured second-input/silencing arrays are empty in the two bundled benchmarks. Do not treat shared parameter names as proof of exact backend parity or arbitrary intervention support. [PyTorch source](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/run_pytorch.py).

## What the notebooks actually test

In the older [Eon demo notebook](https://github.com/eonsystemspbc/drosophila_brain_model_lif/blob/c976c7a90b2ac5a472c028b5862974217e93573f/results/eon_1/demo_notebook.ipynb), the following are independent whole-trial neural experiments, not a single continuous body run. Cell numbers are zero-based and exact lists are in the [extraction receipt](../validation/eon-public-code-extracted.json).

| Source cells / experiment | Direct stimulation |
|---|---|
| 9 / `P9s_100Hz` | P9 left `720575940627652358` and right `720575940635872101`, 100 Hz |
| 14–16 / `P9_legs` | Same P9 pair at 100 Hz, plus 12 `lgAG2` and two ascending leg cells at 200 Hz |
| 35 / `P9_right_leg` | Same P9 pair at 100 Hz, plus right ascending cell `720575940627697664` at 200 Hz |
| 36 / `P9_left_leg` | Same P9 pair at 100 Hz, plus left ascending cell `720575940618066369` at 200 Hz |
| 22 / `Sugar_200Hz` | 23 labellar sugar-labelled cells at 200 Hz; no P9 list supplied |
| 29 / `Sugar_and_bitter` | The 23 sugar cells and 42 bitter-labelled cells, each group 200 Hz |
| 41 / `P9_LC4s` | P9 pair 100 Hz; 104 LC4-labelled cells 200 Hz |
| 83 / `P9_Or56a` | P9 pair 100 Hz; 39 Or56a-labelled cells 250 Hz |

The leg union deliberately mixes primary sensory-labelled cells and ascending cells; it must not be relabelled as fourteen primary GRNs. The unilateral assays are also **not sensory-only**: both P9 cells are directly driven. JO experiments are retained in the receipt but do not establish wall-touch or airflow transduction.

The newer `fly-brain` [example notebook](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/paper-phil-drosophila/example.ipynb) retains P9/sugar/bitter/LC4/JO/Or56a tests, but omits the older leg experiments. Its 23-cell sugar list differs from the [21-cell benchmark list](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/benchmark.py#L56-L104): three notebook-only IDs and one benchmark-only ID are preserved in the receipt. Neither list is automatically the physical demo's taste population.

The shared 16-cell output list is explicit:

| Source label | FlyWire ID(s), preserving notebook ordering/side labels |
|---|---|
| P9_oDN1 left / right | `720575940626730883` / `720575940620300308` |
| DNa01 right / left | `720575940627787609` / `720575940644438551` |
| DNa02 right / left | `720575940629327659` / `720575940604737708` |
| MDN 1–4 | `720575940616026939`, `720575940631082808`, `720575940640331472`, `720575940610236514` |
| Giant Fiber 1–2 | `720575940622838154`, `720575940632499757` |
| MN9 left / right | `720575940660219265` / `720575940618238523` |
| aDN1 right / left | `720575940616185531` / `720575940624319124` |

These are female FlyWire identifiers and source labels, not MaleCNS IDs or newly established biological mappings. P9 itself is an input here; P9_oDN1 is in the output list. `utils.get_rate` divides each trial's spike count by the full duration, then computes mean and population standard deviation across trials. There is no online smoothing window, deadband, controller gain or actuator command in this analysis. [Rate estimator](https://github.com/eonsystemspbc/fly-brain/blob/a3db62f9436074e485c0278290c2164ed6150808/code/paper-phil-drosophila/utils.py#L32-L84).

## Retained author output tables

The older notebook's stored tables (cells 11, 18 and 38) report the following full-trial mean firing rates in Hz. These are **transcribed upstream outputs**, not a rerun or proof that the retained source exactly generated the output. The [structured receipt](../validation/eon-public-code-author-output-tables.json) retains all 16 rows across the three tables, exact printed strings, HTML table fragments, source-cell indices and literal `NaN`; no missing value was converted to zero.

| Condition | oDN1 left | oDN1 right | DNa02 left | DNa02 right |
|---|---:|---:|---:|---:|
| P9 only, 100 Hz | 14.833333 | 10.733333 | 17.033333 | 6.433333 |
| P9 + bilateral leg union | 8.800000 | 8.633333 | 20.933333 | 22.466667 |
| P9 + left ascending leg cell | 16.766667 | 12.066667 | 28.966667 | 6.333333 |
| P9 + right ascending leg cell | 6.133333 | 11.733333 | 11.166667 | 30.033333 |

Thus the saved neural results support testing modulation of an already active locomotor circuit: the bilateral leg union reduces the reported oDN1 rates, and unilateral leg input changes the DNa02 balance. They do not show sensory-only initiation, body movement, a particular motor gain, or general natural behavior. [Pinned notebook](https://github.com/eonsystemspbc/drosophila_brain_model_lif/blob/c976c7a90b2ac5a472c028b5862974217e93573f/results/eon_1/demo_notebook.ipynb).

## Body and other integration leads

The Eon FlyBody fork includes existing policy loaders and links to Janelia's trained policies and controller-reuse checkpoints in [download_data.py](https://github.com/eonsystemspbc/flybody/blob/dd72f4138d2c4a4dc6797227a12d1e89ffc104c9/flybody/download_data.py#L22-L32). These are upstream locomotion assets, already relevant to our native body, not a released Eon whole-brain policy. The article's wording about imitation learning and its NeuroMechFly controller links must be kept distinct from the actual released FlyGym hybrid CPG/reflex controller and from our trained FlyBody actor. This audit did not execute or compare those policies.

BPU's [channels.py](https://github.com/eonsystemspbc/pathintegrationBPU/blob/943c55ef6eecfd8bc97d38e1b5154f89940ad333/src/channels.py#L230-L244) specifies two scalar inputs (`left_taste`, `right_taste`) and outputs (`turn_command`, `forward_speed`). Its [selector](https://github.com/eonsystemspbc/pathintegrationBPU/blob/943c55ef6eecfd8bc97d38e1b5154f89940ad333/src/selector.py#L193-L216) explicitly describes whole-brain pools as heuristic. The inspected [models.py](https://github.com/eonsystemspbc/pathintegrationBPU/blob/943c55ef6eecfd8bc97d38e1b5154f89940ad333/src/models.py#L20-L98) uses recurrent ReLU dynamics and trainable input/output projections; the plume subproject includes a separate abstract plume environment. Main Python sources contain no FlyGym/MuJoCo import or runnable `embodied_foraging` environment. A task-channel declaration is useful interface documentation, but does not supply the missing physical loop. No model checkpoint was downloaded.

## Consequence for our next experiment

The strongest actionable hypothesis is **locomotor-state conditioning**, not an inhibitory gain change: compare the source's fixed P9 recipe with the same sensory input without P9, retaining oDN1 as readout. A valid next step first needs an exact MaleCNS P9 identity crosswalk, a frozen brain-only protocol and explicit acknowledgement that direct P9 drive is imposed state. The public notebooks do not establish that this will restore our dynamics or yield natural wall avoidance. This audit did not run that experiment.

For literal Eon embodiment replication, the unresolved artifacts are still the demo's physical contact/cue-to-input transfer; exact selected IDs/hemispheres and any ongoing background drive; online neural readout filters and gains; body-controller version/modifications; action arbitration; and the persistent exchange implementation. The source assays materially improve our starting point, without filling these missing specifications.

Receipts: [API acquisition](../validation/eon-public-code-acquisition.json), [pinned source acquisition](../validation/eon-public-code-source-acquisition.json), [notebook acquisition](../validation/eon-public-code-notebook-acquisition.json), [static ID/protocol extraction](../validation/eon-public-code-extracted.json), and [release/branch/upstream scope](../validation/eon-public-code-scope.json). Each acquired raw file has a SHA-256; raw files are under ignored `data/raw/eon-public-code/`. Acquisition scripts in `validation/eon-public-code-*.py` operate on public bytes only and refuse to overwrite existing receipts.
