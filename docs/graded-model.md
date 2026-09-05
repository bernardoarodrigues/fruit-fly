# Experimental mixed spiking and nonspiking neural model

`fruitfly.graded.MixedNetwork` adds explicitly selected nonspiking cells to the existing conductance backend. They retain their incoming and outgoing connectome edges, integrate a membrane voltage, and transmit a delayed continuous release signal. They never cross a spike threshold, reset after a spike, or emit artificial spike records. The optional implementation is available for research assays; it is not enabled by a body/viewer configuration.

This capability is motivated by APN2's experimentally nonspiking response in [Suver et al., Neuron 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6533146/). [The reconstructed primary recordings](suver-neural-calibration.md) constrain voltage responses but do not identify the voltage-to-release function. The APN2–SAD003/SAD004 correspondence is a putative morphological crosswalk, not a verified one-to-one functional identity in this male specimen. No claim of measured synaptic release or a fitted wind circuit follows from this implementation.

## Equations and units

For a graded neuron, in milliseconds and millivolts:

```text
tau_m * dV/dt = V_rest − V + g_e*(E_e − V) + g_i*(E_i − V) + I_equiv
r_target(V) = clip(r_baseline + gain*(V − V_reference), 0, r_max)
tau_release * dr/dt = r_target(V) − r
```

Conductances are nonnegative ratios to leak conductance. `I_equiv` is an effective voltage displacement in the membrane equation, not amperes. The release variable `r` is in **spike-event-equivalents per second**. This is a numerical normalization: a unit of integrated release has the same conductance increment as one presynaptic spike under this model's existing weight conversion. It is not a firing rate, vesicle count, release probability or measured concentration.

Every `GradedPopulationSpec` requires exact biological neuron IDs and all seven scalar parameters: resting potential, membrane time constant, release reference voltage, baseline, gain, maximum and release time constant. No defaults silently assign a graded cell type. Duplicate IDs, unknown IDs, invalid bounds and nonfinite parameters fail explicitly. Numeric scalars are normalized before checkpoint serialization.

The graph's existing weight `w` is still converted using the global conductance model's reference rest, even when the target graded neuron has a different resting voltage:

```text
positive edge increment = integrated_release * w * excitatory_gain / (E_e − global_V_rest)
negative edge increment = integrated_release * (−w) * inhibitory_gain / (global_V_rest − E_i)
```

This preserves the graph-weight convention; it does not make that convention physiological. Unknown zero-sign outputs remain zero. The model uses the existing common graph delay. Per-cell delays, receptor-specific kinetics, gap junctions, graded adaptation beyond first-order release, cotransmission and peptide signaling remain absent.

## Timing, state and interventions

Spiking cells retain the original conductance backend's update order. The graded membrane uses the same midpoint conductance approximation, with its supplied resting voltage and time constant. Release relaxes toward the target at the updated membrane voltage, with an analytic step integral for that frozen target. The integral is placed in a persistent delay queue and delivered through actual graph edges at the end of the due tick. Source injection makes the coupled mixed scheme **first order overall**; the isolated conductance membrane scheme's second-order property must not be claimed for the full mixed model.

An `expm1` calculation and small-step series preserve tiny positive release integrals at very long release time constants. Release stays nonnegative and bounded. Reset starts at each graded resting voltage and its corresponding release target, with zero conductance and an empty delay queue. There is no invented synaptic history before time zero; equilibration must be part of any experiment that requires a tonic baseline.

Outgoing-source suppression applies at delivery to both queued spikes and queued graded release. It leaves the source membrane, incoming connections and release dynamics intact. Spike recording contains spiking cells only; graded voltage and release are separate state variables. Checkpoints include the exact graded specification, release vector and delay queue, as well as all inherited voltage/conductance/spike/RNG state. A changed specification or invalid release state is rejected before loading.

## Independent numerical checks

```sh
.venv/bin/python -m pytest tests/test_conductance.py tests/test_graded.py -q
.venv/bin/python scripts/validate_graded_male.py
```

Tests cover bitwise parity with the original conductance backend when the graded set is empty, absence of graded spikes/reset, incoming synapses, signed delayed release, empty prehistory, outgoing suppression, tonic-release reduction under hyperpolarization, first-order convergence to an independent SciPy ODE solution, chunk invariance, saved-state replay, reset, and atomic checkpoint rejection. These are numerical/model-contract checks, not biological validation.

The [executed full-male smoke assay](../validation/graded-male-smoke.json) uses the unchanged 166,700-neuron/25,582,938-edge graph and converts the 16 SAD003/SAD004 candidates, eight per side, to graded cells. All candidate IDs, source hashes, parameters and 5 ms samples are retained. The illustrative hypothesis uses −35 mV rest/reference, 20 ms membrane tau, 20 event-equivalents/s baseline, gain 2 event-equivalents/s/mV, maximum 100 event-equivalents/s, and 10 ms release tau. **These values are engineering choices, not a fit to the female recordings or male physiology.** Each condition runs 400 ms from a cold reset.

| Condition | Network spikes | Candidate spikes | Final total conductance, leak ratios |
|---|---:|---:|---:|
| Ordinary spiking model, no input | 0 | 0 | 0 |
| Graded tonic release | 251 | 0 | 102.496 |
| Same graded cells, outgoing synapses suppressed | 0 | 0 | 0 |
| Graded cells, effective current −10 mV from 200 ms | 129 | 0 | 0.01370 |

The tonic condition ends with mean candidate voltage −34.021 mV and mean release 21.869 event-equivalents/s. Hyperpolarization ends at −44.991 mV and 0.02614 event-equivalents/s. All six smoke checks pass; graph identity stays fixed, graded cells do not spike, output suppression blocks transmission, and release remains bounded. None of the recorded network voltages in these conditions reaches the implausible hundreds-of-millivolts hyperpolarization seen with the transferred Shiu model. This is a small illustrative activation assay, not evidence that the mixed model solves navigation or predicts APN2 recordings.

Next comparison: independently specify a peripheral wind transduction hypothesis, stimulate that pathway, and compare candidate voltage responses with held-out recordings and perturbations. Clamping APN2 to measured curves would instead be a prescribed experimental boundary. Neither method resolves candidate identity, sex transfer, unknown WPN output mechanisms or parameter non-identifiability.
