# KC–MBON functional calibration: evidence and gates

Snapshot: 2026-09-05. This note was prepared while the six-trial
[KC-to-MBON delivery intervention](../docs/navigation-mbon-intervention.md) was
running. It does not change the simulator, experiment, parameters, checkpoints,
or acceptance rules.

## Bottom line

The current evidence points first to a **functional-calibration problem**, not
to a demonstrated failure of the MaleCNS connectivity graph.

The connectome supplies a structural prior: which reconstructed neurons contact
which others, where, and with how many detected synapses. It does not supply a
complete transfer function for those contacts or cells. In particular, it does
not determine release probability, postsynaptic receptor complement, unitary
conductance, short-term plasticity, compartmental attenuation, intrinsic
excitability, state dependence, or the natural sensory drive. A structurally
correct path from odor receptor neurons to motor circuits can therefore coexist
with profoundly wrong activity in a dynamical simulation.

That is what the present traces show. During the audited 0.5–1.5 s interval,
all **3,957 of 3,957** Kenyon cells presynaptic to MBON12–14 fire in each of the
six H1 trials, at a mean of **312.999–313.082 spikes/s per cell**. Biological
odor responses instead recruit only a small minority of Kenyon cells and give
responding cells relatively few spikes. The ten simulated MBONs are
simultaneously fixed at their 2.2 ms refractory limit, approximately
**454.5 spikes/s**, rather than
near measured spontaneous and odor-response rates. Synapse-reconstruction
errors or animal-to-animal variation remain real limitations, but they are not
the parsimonious explanation for this network-wide, repeatable dynamic regime.

## What the connectome can and cannot establish

| Layer | What current evidence can support | What still has to be calibrated or tested |
|---|---|---|
| Anatomy | A detected directed contact from one reconstructed cell to another; a contact count; anatomical cell-type hypotheses | Missed/false synapses, individual variation, receptor identity, sign exceptions, electrical or graded transmission, compartmental effect |
| Sensory entry | The selected receptor/PN populations are anatomically upstream of mushroom-body circuitry | Natural concentration-to-spike transfer, adaptation, correlated noise, bilateral plume sampling |
| PN→KC/APL computation | PN contacts reach KC claws and APL participates in sparse coding | KC recruitment fraction, spike counts, coincidence threshold, APL spatial/temporal gain, intrinsic KC parameters |
| KC→MBON computation | KCs make cholinergic contacts onto MBONs | Per-contact conductance, kinetics, release probability, dendritic integration, depression, MBON intrinsic properties |
| MBON→action | Some MBON populations bias valence and locomotor variables | Context-dependent population code, downstream transformations, body/world coupling; no one-to-one “odor means this motor command” rule |

The 2026 MaleCNS reconstruction is a major anatomical resource, but it remains
one male specimen and its chemical synapses are machine detected. The paper
reports approximately 0.82 precision and 0.81 recall for synapse detection.
Neurotransmitter labels are also model predictions rather than measurements of
the receptors on every target. These qualifications matter for exact-edge and
exact-sign claims, but they do not turn the connectome into a physiological
model. See the primary [MaleCNS report](https://pmc.ncbi.nlm.nih.gov/articles/PMC12636603/)
and the primary [neurotransmitter-classifier report](https://pmc.ncbi.nlm.nih.gov/articles/PMC11106717/).

## Direct audit of the current model

The local values below were recomputed from the independently reviewed
[MBON input arrays](../validation/navigation-ladder-mbon-input-arrays.npz)
(SHA-256 `2322d1dd1ef826e1400c9b9d3a04b365b6c034821cdbb2a5ef3c63a99c1112a0`)
and the retained [incoming-edge table](../validation/navigation-ladder-mbon-input-edges.csv).
The interval is `[5000,15000)` ticks, exactly 1 s. No new simulation was run.

| H1 control | Condition | Seed | Active presynaptic KCs | Mean KC rate | Total KC spikes |
|---:|---|---:|---:|---:|---:|
| 26 | constant baseline | 11 | 3,957 / 3,957 | 313.062 Hz | 1,238,785 |
| 29 | constant baseline | 12 | 3,957 / 3,957 | 313.046 Hz | 1,238,725 |
| 32 | constant baseline | 13 | 3,957 / 3,957 | 313.082 Hz | 1,238,866 |
| 35 | ethyl acetate | 11 | 3,957 / 3,957 | 313.016 Hz | 1,238,604 |
| 38 | ethyl acetate | 12 | 3,957 / 3,957 | 312.999 Hz | 1,238,538 |
| 41 | ethyl acetate | 13 | 3,957 / 3,957 | 313.072 Hz | 1,238,824 |

Across these trials, individual KC counts range from 159 to 417 spikes in the
one-second interval; the median is 322. The reconstructed positive input state
`p` of the ten MBONs reaches approximately 3,078 model mV. This is an
effective current-like state, not a measured membrane voltage or current. From
0.5 s onward, every observed within-cell MBON interspike interval is 22 ticks,
the exact refractory limit. The previously reviewed input decomposition shows
that KCs supply 92.144–92.149% of accepted positive increments, while matched
ethyl-acetate and constant-baseline MBON spike sequences are identical.

These facts localize the immediate failure:

1. the PN/KC/recurrent regime has lost biological sparseness before the signal
   reaches these MBONs;
2. the MBONs have no remaining output range in which an odor-dependent
   increment can appear; and
3. the current uniform weight and point-neuron assumptions convert that dense
   presynaptic activity into overwhelming sustained drive.

The shared `0.275 mV/contact` scale is not a MaleCNS KC→MBON measurement.
In the source model it is the single free synaptic-weight parameter applied
throughout a different whole-brain LIF simulation; the current project
transferred it as an explicit assumption. Shiu et al. chose it so that 100 Hz
sugar-GRN activation produced roughly 80% of maximal MN9 firing; they did not
measure it at KC→MBON contacts. See [Shiu et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11446845/)
and the local [neural-engine specification](../docs/neural-engine.md).

## Biological calibration targets

These are constraints from different assays, not interchangeable hard
tolerances. Species, sex, preparation, stimulus concentration, recording
method, and cell type have to remain attached to each number.

### Kenyon-cell sparseness

- Cellular-resolution calcium imaging found that a monomolecular odor activated
  approximately **5%** of KCs on average, and the mean did not exceed 10% for
  any odor in that monomolecular panel (8 female flies, 933 cells). Recruitment
  required a baseline-significant calcium response reliably across presentations,
  rather than any spike on one trial; individual flies reached 17%. The measurement
  establishes sparse recruitment, not a spike count
  ([Honegger et al. 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3180869/)).
- In-vivo whole-cell recordings found highly selective KC odor responses,
  rapidly decaying excitatory potentials, low PN convergence, and a high firing
  threshold; together these support a few-spike rather than sustained-rate code
  ([Turner et al. 2008](https://pubmed.ncbi.nlm.nih.gov/18094099/)).
- In vivo patch recordings found that 20 of 50 recorded KCs had no classified
  spiking response to any tested odor. Responses required spikes on at least
  three trials, so this does not mean no individual spikes occurred
  ([Murthy et al. 2008](https://pmc.ncbi.nlm.nih.gov/articles/PMC2654402/)).
- Direct PN/KC physiology supports coincidence-like claw integration rather
  than indiscriminate relay: KCs sum multiple PN inputs approximately linearly,
  with reliable spiking requiring sufficient coactive claws
  ([Gruntman and Turner 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3908930/)).
- APL feedback inhibition sparsens and decorrelates KC population output, and
  its effects are substantially local rather than a single uniform global gain
  ([Lin et al. 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4000970/);
  [Amin et al. 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7541083/)).

For a first calibration assay, an odor-recruited KC fraction in the broad
**5–10%** literature range with only a few spikes per responding cell is a useful
target. It is not a universal law for every odor, concentration, or time window.
The current 100% recruitment at approximately 313 Hz is far enough outside this
range that calibration should begin upstream of the MBONs.

### Exact MBON types in vivo

Huang et al. imaged the same three named types at 1 kHz in awake, head-fixed
female flies (3–8 days old at surgery): MBON-γ2α′1 (MBON12), MBON-α′2
(MBON13), and MBON-α3 (MBON14). Imaging and behavioral tests used separate
sets of flies because blue imaging illumination disrupted normal odor-driven
behavior. The source workbooks report the following across-fly means:

| Observable | MBON12 | MBON13 | MBON14 | Protocol |
|---|---:|---:|---:|---|
| Spontaneous firing, mean ± SEM | 21.542 ± 0.657 Hz | 16.452 ± 1.013 Hz | 15.474 ± 0.775 Hz | n=20 flies/type |
| 1% ethyl-acetate response, baseline-subtracted mean ± SEM | +8.101 ± 2.602 spikes/s | +9.990 ± 2.986 spikes/s | +9.785 ± 1.569 spikes/s | n=12 flies/type, 5 s odor |

All three types showed excitatory responses to the tested odors, but response
amplitudes did not significantly differ across the five odors in that dataset.
Accordingly, a calibrated model should preserve an ethyl-acetate-versus-clean
baseline response without assuming that these MBONs alone identify odor
identity. The spontaneous and odor cohorts differ, so their means should not be
added and treated as an exact expected absolute rate. See
[Huang et al. 2024 and its source data](https://pmc.ncbi.nlm.nih.gov/articles/PMC11525173/).
The retained [Fig. 1 workbook](../data/raw/kc-mbon-calibration/41586_2024_7819_MOESM6_ESM.xlsx)
and [Extended Data Fig. 4 workbook](../data/raw/kc-mbon-calibration/41586_2024_7819_MOESM14_ESM.xlsx)
independently reproduce all six means and SEMs from the per-fly rows; these
numbers were not digitized from a plot. Here 1% means a volume/volume liquid
dilution in mineral oil, and the response subtracts the preceding 5 s baseline
from the 5 s odor interval. This whole-animal odor protocol differs from the
project's isolated Or42a/VM7d input assay; these values are physiological
comparison targets, not predictions for that narrow simulation assay.

### Exact MBON14 cellular constraints

Ex-vivo patch recordings of MBON-α3 reported a resting potential of
**−56.7 ± 2.0 mV**, spontaneous firing of **12.1 Hz**, membrane time constant
of **16.06 ± 2.2 ms**, and input resistance of **926 ± 55 MΩ**. Capacitance,
**16.76 ± 1.90 pF**, was calculated from the time constant and input resistance.
The passive measurements came from five cells; sex was not specified in the
inspected methods, and the two labeled α3 MBONs could not be distinguished.
The time-constant SEM follows Table 1 (2.20 ms); the prose instead says 2.3 ms.
A morphology-based conductance model used 12,770 synaptic
contacts from 948 KCs, or 13.47 contacts/KC on average. In that fitted model,
one KC produced approximately 0.37 mV mean somatic depolarization, while one
spike from 50 random KCs, approximately 5%, produced 15.24 mV. These are
reported passive-model outputs, not measured unitary EPSPs. Its synapses used
an alpha-function conductance with a **0.44 ms time to maximum conductance**
and an 8.9 mV reversal, borrowed from recordings in KCs; the fitted conductance
was not a direct KC→MBON measurement. The composite morphology joined a
Takemura α3A dendrite, a hemibrain axon, and confocal soma/neurite measurements.
See [Hafez et al. 2023](https://elifesciences.org/articles/77578)
and the permanent [model/data archive](https://archive.data.jhu.edu/dataset.xhtml?persistentId=doi:10.7281/T1/HRK27V).

The current H1 parameters (`−52 mV` rest/reset, `−45 mV` threshold, 20 ms
membrane time constant, 5 ms synaptic decay) are therefore engineering values,
not an exact MBON12–14 calibration. The Hafez model is useful for MBON14
sensitivity analysis, but it should not be copied blindly to MBON12/13 or
treated as in-vivo male ground truth.
The [independent source review](../validation/kc-mbon-calibration-source-review.json)
records source hashes, workbook cells, preparation limits, and these wording
corrections. It does not evaluate the intervention outcomes.

### Circuit meaning and movement

KC→MBON transmission is cholinergic, but that fact establishes transmitter
identity rather than the effective weight of every contact
([Barnstedt et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4819445/)).
MBON populations bias valence and behavioral choice in combinations; they are
not simply final motor neurons. MBON12 activation has been associated with
attraction, and activation of MBON12 and MBON14 can promote upwind locomotion,
with further downstream neurons transforming that signal toward action
([Aso et al. 2014](https://elifesciences.org/articles/04580);
[Aso et al. 2023](https://elifesciences.org/articles/85756v2)).

Thus “food odor can cause movement” and “stimulating motor pathways can cause
movement” validate the two ends of a causal chain. They do not determine the
gain, timing, sparsity, state dependence, or code in the intervening circuit.

## What the running intervention can tell us

The intervention suppresses only the 8,236 selected positive KC→MBON12–14
deliveries during `[5000,15000)` ticks and restores them afterward. Because it
does not retune the network, it is a causal localization experiment, not a
physiological calibration.

| Complete-batch outcome | Interpretation |
|---|---|
| MBON `p` and firing fall promptly below the ceiling; EA and baseline become distinguishable; restoration reverses the change | Strong model-level evidence that KC delivery was masking contrast through saturation. This is the most informative result, but rates/amplitudes must still be calibrated. |
| MBON activity falls, but remains saturated or EA and baseline remain equal | KCs are a major contributor, while retained state, other positive inputs, or upstream loss of contrast still dominate. |
| Little or no MBON change | Recheck target delivery accounting; if verified, other input classes or the H1 state/reset/refractory rules dominate the ceiling. |
| MBONs become nearly silent | The KC pathway is necessary in this model, but the model lacks realistic spontaneous drive or balancing mechanisms; silence is not a physiological success. |
| Suppression behaves as expected but restoration fails or leaks outside the interval | Implementation failure; do not interpret the biology. |

A “good” experimental result is therefore not merely fewer spikes. It is a
clean, time-locked, reversible and seed-consistent causal effect with intact
untargeted projections and a measurable within-cell EA-versus-baseline dynamic
range. Even that result would diagnose the current model rather than validate
the whole mushroom-body circuit.

## Prospective calibration sequence

Do not tune against the running intervention. Freeze a new plan only after the
complete batch and its independent audit are available.

1. **Calibrate PN→KC/APL first.** Use clean baseline and several odor
   concentrations. Measure recruited-KC fraction, spikes per active KC,
   spontaneous rate, population overlap, and decay after odor. Require sparse
   activity before touching KC→MBON gain.
2. **Separate cell classes and synapse models.** Stop treating the global
   `0.275 mV/contact` value as a measurement. Compare a current-like baseline
   with conductance-based, receptor-aware sensitivity models; keep contact count
   distinct from fitted per-contact strength.
3. **Anchor exact MBON physiology where available.** Start with MBON14 passive
   and firing constraints. Treat MBON12/13 parameters as uncertain rather than
   silently inheriting MBON14.
4. **Model dopamine as modulation/plasticity where the assay requires it.** Do
   not interpret the current dopamine-class positive increment as a measured
   generic fast excitatory current.
5. **Validate dynamic range, not just connectivity.** Require non-ceiling
   spontaneous activity, a baseline-subtracted EtA response of the right order,
   recovery, seed robustness, and retained numerical accuracy. Keep odor
   detection, odor identity, learned value, locomotor bias, and physical
   navigation as separate gates.
6. **Protect against circular fitting.** Fit on a declared subset of cell types,
   odors, concentrations, and seeds; reserve others for validation. Preserve the
   female-to-male and ex-vivo-to-in-vivo transfer uncertainty in every claim.

The immediate expected win is not a perfectly behaving fly. It is a calibrated
subsystem in which sparse odor-dependent KC activity reaches MBON12–14 without
forcing them to the refractory ceiling, and in which a targeted perturbation
produces a reversible effect for the reason predicted.
