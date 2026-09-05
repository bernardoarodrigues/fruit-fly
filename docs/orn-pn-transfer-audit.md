# Isolated ORN-to-PN transfer audit

The unchanged model passes **55 numerical/anatomical checks**. A single spike through any of the 616 retained same-glomerulus ORN→adPN edges produces a passive peak below the model's 7 mV threshold gap when its isolated target starts at rest. This is a statement about this fixed point-neuron model and the selected male anatomical edges. It does not establish the size of a female somatic uEPSP, predict an intact PN's response, or validate physiological gain.

The [plan](../validation/orn-pn-transfer-plan.json) was frozen before the isolated runs (SHA-256 `915d0f0ab01a606eb042038644e16121c714839101c21c9489bab896130436f7`). The [script](../scripts/audit_orn_pn_transfer.py), [results](../validation/orn-pn-transfer-results.json), and lossless [traces](../validation/orn-pn-transfer-traces.npz) retain the evidence. No full-brain simulation, parameter fitting, runtime edit, or model promotion occurred. The subsequent [independent review](orn-pn-transfer-independent-review.md) passes 74 saved-data checks using direct CSR lookup and a separate matrix-exponential calculation.

## Anatomical selection

The pinned MaleCNS v1.0 import contains 166,700 neurons and 25,582,938 directed neuron-pair edges. Raw contact counts and assumed physiological weights remain separate. All source, graph, annotation, and paper bytes are hashed in the plan; the import manifest was verified before reading. Data attribution: Berg et al., *Cell* (2026), DOI [10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015), CC BY 4.0.

Selection uses exact case-sensitive `ORN_{glomerulus}` olfactory types and `{glomerulus}_adPN` ALPN types, corresponding to the four antennal glomeruli in the measurement comparison. It does not equate the published genetic labeling scheme with every individual male PN. [Neuron IDs and annotations](../validation/orn-pn-transfer-neurons.csv) include 174 ORNs, 14 adPNs, and two separately classified DM4_vPNs. All selected ORNs are annotated acetylcholine, model sign +1, entry nerve AN. The adPNs are acetylcholine; DM4_vPNs are GABA neurons, although the incoming ORN→vPN edge sign is still determined by its acetylcholine presynaptic ORN.

| Glomerulus | ORNs (root L / R / unknown) | adPN IDs, soma L | adPN IDs, soma R | Actual / possible ORN→adPN pairs |
|---|---:|---|---|---:|
| DM6 | 58 (22 / 29 / 7) | 15184, 17350, 18015 | 15005, 18417, 19953, 519572 | 362 / 406 |
| VM2 | 41 (17 / 20 / 4) | 14665, 15992 | 16083 | 107 / 123 |
| DL5 | 43 (23 / 19 / 1) | 10767 | 525105 | 85 / 86 |
| DM4 | 32 (16 / 15 / 1) | 10670 | 10613 | 62 / 64 |

The [candidate inventory](../validation/orn-pn-transfer-candidates.csv) also retains 161 case-insensitive alias collisions: 99 optic `Dm4` and 62 optic `Dm6` neurons, all `ol_intrinsic`. These are excluded rather than confused with antennal DM4/DM6. No unresolved exact-case alias candidate was found by the declared search of type, hemibrainType, flywireType, supertype, and synonyms. That search does not prove annotation completeness or morphology-based correspondence.

The [pair table](../validation/orn-pn-transfer-pairs.csv) enumerates all 2,784 ORN×candidate-PN combinations, including zeros; the [direct-edge table](../validation/orn-pn-transfer-edges.csv) enumerates all 641 nonzero connections with raw contacts, source graph indices, and exact float32 weight bytes. The 616 core edges contain 25,884 contacts. The two DM4_vPNs (71476, soma L; 73492, soma R) receive 25 selected DM4 ORN edges totaling 65 contacts, 1–8 per edge, and are excluded from the adPN comparison. No cross-glomerulus edge occurs within this selected Cartesian product. This is not a claim about all ORN outputs in the brain.

All thirteen ORNs with unknown root side remain included. Core direct edges include 304 contacts from unknown-root ORNs to soma-L PNs and 549 to soma-R PNs. Side labels mean **ORN root-side annotation → PN soma-side annotation**; soma side alone is not an independent dendritic-location measurement. Edges are not filtered to presumed ipsilateral pairs. Zero pairs mean absent from this retained graph, not proven absence of a biological synapse.

## What the current weight means

Let `u = v − v_rest`. Before threshold/reset, the unchanged equations are

\[
\dot g=-g/\tau_s,\qquad \dot u=(-u+g)/\tau_m,
\quad g(0^+)=w,\quad u(0)=0.
\]

For \(\tau_m=20\) ms and \(\tau_s=5\) ms,

\[
u(t)=w\frac{\tau_s}{\tau_m-\tau_s}
\left(e^{-t/\tau_m}-e^{-t/\tau_s}\right).
\]

The extremum occurs 9.241962407 ms after delivery and is `0.1574901312 × w`. Thus **0.275 mV per contact is a jump in the synaptic effective-voltage state**, not a 0.275 mV peak depolarization. A nominal positive contact produces a 0.0433097861 mV passive peak. Actual stored float32 weights, rather than rounded decimal weights, are used for every prediction and engine comparison. A negative control gives the corresponding hyperpolarizing response; this control is synthetic, not an alternative sign for these ORNs.

| Glomerulus | Contacts per actual edge, min / median / max | Mean passive peak (mV) | Median passive peak (mV) | Passive peak range (mV) |
|---|---:|---:|---:|---:|
| DM6 | 2 / 28 / 61 | 1.188 | 1.213 | 0.087–2.642 |
| VM2 | 12 / 40 / 77 | 1.713 | 1.732 | 0.520–3.335 |
| DL5 | 18 / 81 / 151 | 3.538 | 3.508 | 0.780–6.540 |
| DM4 | 6 / 78 / 155 | 3.340 | 3.378 | 0.260–6.713 |

Across the 616 edges, the contact median is 32.5 and the passive peak median is 1.407568 mV. Every selected edge has an exactly matching float32 contact-rule weight. The largest is ORN 123968→DM4_adPN 10670: 155 contacts, `w=42.625 mV`, continuous passive peak 6.713017 mV. The table concerns isolated response from rest, without ongoing synaptic state, convergent inputs, inhibition, recurrence, or body feedback.

The continuous threshold contact-equivalent is about 161.626 for the 7 mV gap. This is a calculation, not a contact count inferred from physiology. Likewise, dividing the pooled 6.19 mV somatic measurement by the model's per-contact passive peak gives about 142.924 nominal contact-equivalents, but cannot identify a release-site count or justify a new weight. The pronounced between-glomerulus variation under uniform point-neuron parameters is a useful question for a compartment-aware comparison; it cannot establish that anatomical contacts or recorded voltages are erroneous.

## Unchanged-engine check

Eight 60 ms two-neuron runs use the existing `LIFNetwork` at 0.1 ms dt, −52 mV resting/reset voltage, −45 mV strict threshold, 2.2 ms refractory duration, and 1.8 ms delay. Four real-edge rank selections contain three distinct edges because the maximum is also the largest subthreshold edge. Synthetic +1, +161, +162 and −1 contact controls bracket threshold and sign. Only the isolated presynaptic initial voltage is set to −44 mV to produce one spike; there is no input drive or feedback. No neuron parameter is changed.

The closed-form solution is evaluated independently of the runtime's discrete recurrence. Each run has exactly one presynaptic spike at stamp 0 and one traversed edge. Before any threshold crossing, the maximum voltage discrepancy is `7.816e−14 mV`; maximum synaptic-state discrepancy is `4.974e−14 mV`, against a preregistered absolute tolerance of `2e−11 mV`. The real cases remain subthreshold. Synthetic 161 contacts remain subthreshold; 162 contacts produce a PN spike at stamp 10.4 ms, with voltage and synaptic state reset. The analytic passive curve continues beyond this point only as a counterfactual; it is not the native post-spike voltage.

Clock convention matters: the presynaptic spike stamped 0 is delivered in the synapses slot at stamp 1.8 ms, after that tick's integration. The saved state after that step is labeled 1.9 ms. Its `g` has jumped and `u` is still zero; integration appears in the 2.0 ms sample. Predictions use elapsed time from the post-delivery state boundary. The source delay and scheduler are unchanged. Thresholding similarly happens before the post-step state is saved: the 162-contact crossing is at sample index 105, whose state time is 10.5 ms but whose emitted spike stamp is 10.4 ms. The saved voltage at this sample is reset, not the unsaved overshoot.

Reproduce with the retained script and every source hash in the plan matching, including the pinned local graph and papers. The plan's `git_head` records the pre-experiment base; the newly written audit script was not yet present in that commit and is identified by its separate exact file hash:

```sh
.venv/bin/python scripts/audit_orn_pn_transfer.py --prepare
.venv/bin/python scripts/audit_orn_pn_transfer.py --run
```

These commands refuse to overwrite a plan/result. Use a clean checkout without the generated evidence to execute anew, and compare numerical/CSV content; timestamps, Git revision and resulting plan hash can differ. The isolated experiment verifies anatomy selection and this numerical transfer, not all full-graph dynamics or the accuracy of the EM reconstruction.

## Measurement boundary and next reproduction

[Kazama & Wilson (2008)](https://doi.org/10.1016/j.neuron.2008.02.030) measured adult females aged 2–7 days. The pooled low-frequency somatic uEPSP is 6.19 ± 0.45 mV SEM, n=23, at 0.033 Hz. Its glomerulus, compartment, sex, preparation, and sampling distribution differ from this edge-weighted male point-neuron inventory. The measured neuron-pair unitary response is not one EM contact; estimated vesicular release sites are also not established one-to-one equivalents of detector contacts. A current in pA cannot be inferred from this model's `g` in effective mV without a conductance/capacitance and compartment mapping. Root's [physiology lead](orn-pn-physiology-lead.md) retains the broader measurement summary and [source hashes](../validation/orn-pn-physiology-sources.json).

The static source adds the same `w` for each accepted presynaptic event. Its 5 ms decay describes the disappearance of existing synaptic state; it does not reduce the size of the next event. Postsynaptic refractory gating can suppress delivery and reset clears `g`, but those numerical rules are not a model of vesicle depletion, release probability, receptor desensitization, or presynaptic inhibition. The single-spike audit cannot determine which missing process explains a whole-network failure.

The [concrete reproduction proposal](../validation/orn-pn-transfer-depression-proposal.json) distinguishes a published numerical reference from subsequent fly measurement comparisons. Nothing in it is implemented or promoted by this audit.

1. **Reproduce a specified reference equation.** Kazama–Wilson supplies temporal experiments and quantal-analysis equations, but no fitted dynamical depletion/recovery model. Their cited [Abbott et al. (1997), notes 6, 7 and 10](https://huguenardlab.stanford.edu/220/varela1997a.pdf), defines amplitude state \(a\): \(\tau\dot a=1-a\), response amplitude \(a^-\) before each event, followed by \(a^+=f a^-\). Its published reference values are \(f=0.75\), \(\tau=300\) ms. For regular rate \(r\), \(A(r)=[1-e^{-1/(r\tau)}]/[1-f e^{-1/(r\tau)}]\). Implement this scalar event model separately and verify event recurrence, recovery, and the analytic steady state before any biological comparison. These values originate in rat cortex and serve only to reproduce that source. The authors' separate conductance decay is 2 ms; it must not be confused with recovery or silently substituted for the Shiu 5 ms decay.
2. **Reproduce the fly stimulation and normalization.** Use exact event times outside the brain engine: 7 Hz for 4 s, then 15, 20 or 50 Hz for 500 ms, as in Figure 8F (n=6, VM2). Normalize each event's amplitude to the first event of that test train. Report both amplitude state and its response convolution, so temporal summation is distinguishable from event depression. Figure 9 uses VM2 charge transfer during the first 100 and 500 ms, normalized at 100 Hz (n=4); digitize stimulus frequencies and error bars before implementation rather than guess unlabeled coordinates. No absolute uEPSP gain is fitted.
3. **Preserve temporal evaluation sets.** Fix the source reference parameters first and compare all fly panels descriptively. If a later task explicitly fits a fly-specific temporal model, declare Figure 8F's 20 Hz curve as development data and reserve its 15/50 Hz curves, Figure 9 charge curves, and both Figure S8 recovery protocols for evaluation. The figures have already been inspected; this is a prospective fitting split, not an unseen or preregistered biological test. Shared cells, normalizations and panels are not independent replications.
4. **Test recovery as its own constraint.** [Supplement Figure S8](https://kazamalab.riken.jp/pdf/Neuron_Kazama%26Wilson_2008_supplement.pdf) measures VM2 recovery after 50–200 Hz trains and after a pause in 7 Hz stimulation. The reported 7.5 s time constant belongs specifically to the latter. S8B is a separate post-train curve without a printed fitted constant. Retain both protocols; do not use 7.5 s to set a recovery parameter while claiming that same panel as held-out evidence. The deterministic amplitude model cannot reproduce the trial-to-trial quantal-variance assay in Figure 8G: its binomial `1/CV² = Np/(1−p)` argument needs a separately justified stochastic release model. Neither `1−f` nor anatomical contacts can simply be relabeled as measured release probability or release-site count.

Before running the proposal, retain digitized points with figure coordinates, extraction uncertainty, normalization references, stimulus phase, pause/test timing, and any unspecified protocol decisions. Compare normalized predictions and residuals with error bars as descriptive evidence; the printed aggregate figures do not support an independent biological pass/fail threshold or precise raw-trial likelihood. Failure of one recovery state across these protocols would motivate a separately specified model comparison, not a new gain chosen to make the whole brain run.
