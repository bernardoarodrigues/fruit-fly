# Wind input: verified evidence and experimental boundary

**Incomplete source audit, 2026-09-05.** Further retrieval was stopped after a platform content-filter error. This note preserves findings already verified; it is not an exhaustive literature review. No wind encoding experiment, neural fit or runtime/backend change was made in this subtask.

The mixed backend can represent a nonspiking APN2 candidate, but the inspected evidence does **not yet identify a quantitative physical-wind → individual JO-C/E spike train → APN2 release model**. Existing measurements constrain different parts of that chain in different preparations.

## What is supported

| Source | Verified measurement or protocol | Limit on interpretation |
|---|---|---|
| [Patella & Wilson 2018](https://doi.org/10.1016/j.cub.2018.02.074), [author paper](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/patellawilson2018.pdf) | Female flies, 1–2 days old; JON population calcium imaging. Steady distal-arista displacements of ±6.000, ±9.246 and ±14.250 **µm**, lasting 2.5 s. Opponent push/pull response classes. | These are displacement stimulus values and calcium responses, not per-cell firing rates or a calibrated calcium-to-Hz relation. Neuropil signals mix cells. |
| [Chang, Vaughan & Wilson 2016](https://doi.org/10.1016/j.neuron.2016.09.059), [author paper](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/changwilson2016.pdf) | aPN3 recordings with ±0.5, 1, 2, 4 and 8 **µm** steps lasting 5 s; response window 2–5 s. Most cells depolarized to headward push and hyperpolarized to outward pull; cells differed substantially. | These are central aPN3 responses, not direct JON tuning measurements. Experimental holding current and cell heterogeneity matter. |
| [Suver et al. 2019](https://doi.org/10.1016/j.neuron.2019.03.012) | Recovered female recordings provide directional APN2 ΔVm, APN3 ΔVm/ΔHz and WPN ΔVm/ΔHz under four-second wind. Separate paired antenna measurements provide projected arista angles at five azimuths. | Absolute sensory spike input, APN2 release and conversion between these projected angles and the other studies' displacement coordinates are not measured by these recovered targets. |

The source-backed polarity is **JO-E: headward push; JO-C: outward pull**. JO-D can also carry pull/displacement signals; a C/E-only experiment is not an exhaustive mechanosensory input model. Chang's convention assigns positive displacement to headward push. The curated Suver arista curves assign negative deflection to headward movement. That sign difference must be handled explicitly, alongside the unresolved geometric conversion. Micrometres at an arista attachment point cannot be replaced by angular degrees through a unit conversion alone.

Chang's physiological account includes weak responses in the nonpreferred direction and withdrawal of tonic input. A zero-baseline half-wave rectifier would remove those mechanisms. The retrieved studies do not supply an identified single-cell JO-C/E spontaneous firing baseline usable for this male specimen.

## Published model parameters are not measured sensory rates

The [Chang 2016 supplement](https://wilson.hms.harvard.edu/sites/g/files/omnuum8421/files/wilson-lab/files/changwilson2016_som.pdf), Modeling, uses mirrored sigmoid JON responses. Its push parameters are α=100, β=−0.5, γ=1.4, δ=0; pull parameters are α=−100, β=−0.5, γ=−1.4, δ=100. It specifies a 25% adaptation shift over 500 ms and a subsequent integrating alpha filter with τ=23 ms. The authors explicitly describe qualitative hand tuning and do not report goodness of fit.

Those values can motivate a separately labelled response-shape hypothesis. The sigmoid ceiling of 100 is **not an established 100 Hz JON ceiling**. Likewise, their later 60 Hz maximum applies to a simulated **aPN3** spike generator, not to sensory afferents. An adaptation or filter constant in that model is not a measured intrinsic time constant for every MaleCNS JO cell.

## Mixed-model review and missing measurements

The reviewed [mixed model](graded-model.md) preserves APN2 candidate voltage and continuous release separately from spikes. Its [400 ms smoke assay](../validation/graded-male-smoke.json) establishes numerical transmission and source-output suppression. The −35 mV rest, 20 event-equivalents/s release baseline and 2 event-equivalents/s/mV release gain are explicitly illustrative. They do not calibrate wind transduction. The zero-history reset also requires an explicit equilibration period before any tonic-baseline comparison.

The following gaps remain material:

- Per-subtype JO-C/E baseline spikes, preferred and nonpreferred response curves, adaptation and variability, tied to a measured displacement coordinate and the current male identities.
- Geometric registration between distal-point displacement, Suver's projected arista angle and the simulated a2–a3 rotation; wind-speed and sex transfer remain separate uncertainties.
- Input-event conductance versus actual JON output firing. `ConductanceDrive.rates_hz` specifies events delivered **to** a neuron; it does not clamp that neuron to the same firing rate.
- APN2 voltage-to-release baseline, gain, saturation and kinetics; receptor-specific strengths remain unmeasured. The SAD003/SAD004 correspondence is putative.
- Baseline activity and inhibitory balance for APN3. The differing Chang and Suver response preparations cannot be reconciled by silently reversing sensory polarity.
- WPN identity/output mechanism. Male LHPV6q1's retained unknown-sign outputs remain zero; a voltage comparison does not validate downstream wind behavior.

## Defensible next experimental boundary

A future fixed sensitivity assay may impose **declared artificial push/pull afferent inputs**, retain tonic and nonpreferred-channel hypotheses, record actual source spikes, and compare intact versus same-source outgoing suppression. It should preserve the full graph, use matched initial states and no-stimulus controls, and report all declared parameter choices rather than selecting a successful directional pattern. Such an assay tests model consequences of assumptions; it does not validate physical wind encoding.

For any later quantitative comparison, freeze parameters and split rules before using the [individual Suver targets](suver-neural-calibration.md). Keep every repeat from a biological animal together once the record-to-animal map is verified; ten APN2 recordings are not ten independent flies. Existing population summaries have already been inspected, so a retrospective split must not be called an untouched test set. Compare baseline-relative voltage without per-direction offsets or target-dependent rescaling. Clamping APN2 to the measured curve would instead define an imposed downstream boundary and cannot count as a prediction of APN2 physiology.

The inaccessible full Kamikouchi 2009 article remains a useful optional follow-up: [institutional-access page](https://www.nature.com/articles/nature07810). Its publicly inspected supplement reports amplitude-dependent population calcium responses; that alone does not close the missing single-cell rate calibration. No institutional download is required to interpret the limitations documented here.
