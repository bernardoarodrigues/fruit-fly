# Conductance-based neural extension

`fruitfly/conductance.py` adds the separately named `ConductanceNetwork` backend.
The original `LIFNetwork` remains the exact Shiu replication baseline. This
extension addresses unbounded hyperpolarization observed after transferring
Shiu's current-based model to the male brain-and-cord graph; it is not a claim
that male neural physiology or behavior has been reconstructed.

## Equations and units

For each neuron, the model maintains membrane voltage `v` in mV and two
nonnegative conductances `gE` and `gI`, expressed **relative to leak conductance**:

```
dv/dt  = [Erest - v + gE*(EE - v) + gI*(EI - v) + current_mv] / tau_membrane
dgE/dt = -gE / tau_E
dgI/dt = -gI / tau_I
```

The default reversal potentials are `EE = 0 mV`, `EI = -75 mV`. Leak/resting
potential `-52 mV`, threshold `-45 mV`, reset `-52 mV`, membrane time constant
`20 ms`, synaptic decay `5 ms`, refractory period `2.2 ms` and delay `1.8 ms`
are initially retained from the Shiu comparison. These defaults form a declared
hybrid starting model, not one jointly fitted measurement of a male cell type.
The code exposes separate excitatory/inhibitory time constants and gains.

Inhibitory chloride conductances approach a reversal potential rather than
driving voltage indefinitely negative. Without external current, a neuron
initialized between the reversals stays between them, including after reset.
During refractory intervals voltage is held at reset, but synapses continue to
decay and receive incoming events. Spikes reset voltage only; they do not erase
the two conductances. These semantics deliberately differ from the Shiu
replication backend.

The anatomical graph still contains signed mV weight priors from the importer.
For a positive edge `w`, its excitatory conductance increment is
`gain_E * w / (EE - Erest)`. For a negative edge, its inhibitory increment is
`gain_I * abs(w) / (Erest - EI)`. At rest, these conversions give the same
initial signed driving term as the imported current-based edge. This is a
dimensional transfer rule derived here, not a measurement of quantal conductance.
Changing `EI` or `Erest` consequently also changes this transfer conversion.
No absolute nS value is claimed because per-cell leak conductance is unknown.

This import cannot represent receptor-dependent mixed signs, pure shunting
inhibition exactly at rest, or depolarizing chloride transmission through the
signed-weight conversion. Those cases require explicit receptor conductances
instead of a single signed current proxy. Neuromodulators still inherit the
import's simplified point-synapse assumptions. Unknown-sign edges remain zero.

## Evidence for the priors and its limits

An adult Drosophila MN5 experiment reported a chloride reversal near **−74 mV**
and average resting potential near **−63 mV**. This supports the plausibility
of a −75 mV inhibitory starting prior for some adult cells, not a universal
brain-wide value. [Adult MN5 chloride physiology, 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5614441/)

A published fly spatial-orientation model used conductance-based LIF neurons
with cholinergic reversal **0 mV** and GABA reversal **−70 mV**, a 15 ms
membrane time constant, −70 mV rest/reset and −50 mV threshold. Those are
model parameters, not a parameter set automatically transferable to MaleCNS.
[Su et al., Nature Communications 2017](https://doi.org/10.1038/s41467-017-00191-6)

Chloride reversal depends strongly on preparation and intracellular chloride.
For example, cultured fly neurons had GABA reversal near −41.5 mV under
particular pipette conditions; adult lLNv experiments also reported approximately
−48 mV with a matching chloride equilibrium. It would be incorrect to combine
these values into an unqualified “fly inhibitory voltage.”
[Rdl-mediated GABA transmission, 2003](https://pmc.ncbi.nlm.nih.gov/articles/PMC6740792/),
[Rest/arousal neuron synaptic inputs, 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3125135/)

Glutamate inhibition via GluCl was demonstrated in the antennal lobe, while
histamine-channel activation can act substantially through shunting inhibition
and chloride gradients can change. Neither finding establishes a single
unchanging receptor rule for all male CNS contacts.
[Liu and Wilson, PNAS 2013](https://pubmed.ncbi.nlm.nih.gov/23729809/),
[Liu and Wilson, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3725270/)

## Integration and performance options

Both conductances decay analytically. Voltage uses the exponential solution
for conductances held at the midpoint of that decay interval. The complete
voltage update is second-order accurate between synaptic events; spike timing
still depends on the neural clock. It is a convex combination of the old
voltage and an equilibrium inside the reversals, which gives the voltage bound.

`voltage_method="exponential"` is the reference and default. The optional
`"pade22"` method substitutes the positive Padé approximation

```
exp(-z) ≈ (12 - 6*z + z*z) / (12 + 6*z + z*z),  z = dt * total_conductance / tau
```

only for `0 <= z <= 1`. Larger `z` uses the exact exponential. This fallback
avoids the incorrect large-`z` limit of Padé[2/2]. The optional method preserves
the reversal bound and is explicitly recorded in parameter/checkpoint metadata;
it does not silently replace the reference. In an initial full-MaleCNS 100 ms
comparison, the two methods produced the same total and selected motor spike
counts; measured runtime was 1.74 s versus 1.53 s on this Mac. This is a modest
speed improvement, not proof of real-time complete simulation.

Sparse edge propagation and source-ID delay queues use the same full anatomical
graph as the baseline. Numerical performance is more expensive than the Shiu
kernel because voltage depends on both conductances at each cell. No reduced
graph or increased physical timestep is substituted without an explicit option.

## Input and checkpoint API

```python
from fruitfly.conductance import (
    ConductanceNetwork, ConductanceParameters, ConductanceDrive, SynapticEvents,
)

brain = ConductanceNetwork.from_connectome(graph, seed=42)
activity = brain.advance(
    5.0,
    drive=ConductanceDrive(orn_indices, rates_hz=150, event_gleak=1),
    outputs=descending_indices,
)
```

`rates_hz` is the rate of **external presynaptic input events** arriving at the
selected modeled afferents. Each event increases excitatory conductance; there
is no direct 68.75 mV voltage jump, and stimulation never removes refractoriness.
The default event amplitude of one leak conductance is an uncalibrated numerical
input parameter. The target ORN's actual output rate is measured and may differ
from the requested input rate. Calling it a 150 Hz ORN output without checking
the resulting spikes would misstate the model. `SparseDrive` remains accepted
for API compatibility, but its voltage-amplitude override is rejected and its
Shiu-specific refractory bypass is not applied.

`SynapticEvents(indices, times_ms, conductance_gleak, inhibitory=False)` replays
exact external events. Times are absolute milliseconds on the neural clock and
must lie within the current advance interval. Repeated targets are allowed.
This makes numerical comparisons across dt possible using an identical event
schedule rather than different stochastic samples. An exact prescribed ORN
axon spike source would be a different explicit sensory-boundary model; it is
not silently introduced by this API.

Membrane voltage, both conductances, refractory clocks, delayed graph events,
RNG, interventions and current drive survive calls and checkpoints. Checkpoint
loads verify backend, graph and parameter identity and reject nonfinite current,
negative conductance, invalid clocks, fractional source indices or a zero RNG
state before mutating the network. `synaptic_mv` is retained only as a
compatibility diagnostic of equivalent signed drive **at rest**; it is not the
actual voltage-dependent current. Use `excitatory_g` and `inhibitory_g` for the
new states.

## Verification and fixed parameter screen

The combined focused suite currently passes 46 checks in 2.34 s, including
unchanged Shiu/Brian2 parity, an independent high-accuracy ODE solution, analytic
equilibrium, step-size convergence, extreme conductance reversal bounds,
Padé/exponential comparison including a stiff pulse, delayed causality,
refractory preservation, checkpoint continuity and invalid-state rejection.

```
.venv/bin/python -m pytest tests/test_neural.py tests/test_conductance.py -q
.venv/bin/python scripts/calibrate_conductance.py
.venv/bin/python scripts/check_conductance_numerics.py
```

The fixed grid varies global and separate E/I gains, inhibitory reversal, and
rest/reset voltage. It includes a stimulus interval followed by stimulus offset,
and reflected left/right conditions. Results, including actual sensory firing,
named DN rates, voltage extrema and runtime, are saved under
`validation/conductance-*.json`. Parameter sets are **not selected for food
approach or movement**. In the first screen, bounds held but the default
DNg97/DNa01/DNa02 outputs remained largely silent. Reducing inhibition recruited
them at high rates while greatly increasing network activity; that is a
sensitivity result, not evidence that weaker inhibition is biologically correct.
The readout/behavior calibration problem remains separate from fixing the
unbounded current equation.

The completed initial screen contains 17 conditions across
[`conductance-calibration.json`](../validation/conductance-calibration.json)
and [`conductance-baseline-sensitivity.json`](../validation/conductance-baseline-sensitivity.json),
including one Shiu comparison. Each condition used 100 ms stimulation and 100 ms
offset. Default conductance stimulation generated 102,828 network spikes and
77.7 Hz mean actual ORN output, despite 150 Hz external event input. Its offset
interval generated 168,872 spikes while mean ORN output fell to 1.1 Hz. Thus
continued recurrent activity outlasted the external stimulus; this does not by
itself demonstrate meaningful memory. With inhibitory gain 0.25, stimulus/offset
spikes rose to 836,353 / 1,284,559 and several named DNs fired above 300 Hz.
With global gain 0.1, stimulus/offset spikes were 1,771 / 4,462 and the selected
motor DNs were silent. The strong dependence on gains is an unresolved model
calibration issue. No condition was designated the biological or foraging winner.

The shared-event 100 ms numerical comparison used a fixed 5 ms coupling interval,
50 ms of event input and 50 ms offset. Events lay on a common 0.2 ms clock, so
the `.2`, `.1` and `.05 ms` runs received exactly the same events. Results are in
[`conductance-numerics.json`](../validation/conductance-numerics.json):

| Neural dt | Network spikes, either method | Exponential wall time | Padé wall time | Spike-count difference vs .05 ms |
|---|---:|---:|---:|---:|
| .2 ms | 101,800 | .959 s | .844 s | 3.11% |
| .1 ms | 100,529 | 1.778 s | 1.520 s | 1.82% |
| .05 ms | 98,731 | 3.455 s | 2.952 s | Reference |

At each dt, Padé and exponential methods matched total/selected motor counts;
their final whole-network voltage RMSE was at most `1.09e-5 mV`. Changing dt
had a much larger effect: approximately `0.85–0.92 mV` final voltage RMSE
relative to the .05 ms run, with threshold-event differences and recurrence.
This provides a measured accuracy/speed tradeoff, not proof that all biological
or embodied outputs have converged. The default remains exponential at .1 ms.

## Proposed graded visual boundary, not implemented here

R1–R6 photoreceptors release histamine through graded, tonic transmission;
turning their luminance responses into artificial spike trains would discard
that mechanism. Primary photoreceptor studies also demonstrate substantial
feedback and graded LMC hyperpolarization downstream.
[Photoreceptor axonal calcium and exocytosis, 2012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3432082/),
[Zheng et al., 2006](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151524/)

A future API can explicitly register `configure_graded_sources(indices,
release_model, parameter_manifest)` and accept `graded_drive=GradedDrive(...)`.
The identified source IDs and real outgoing contacts remain in the graph;
threshold/reset/spike emission are replaced only for registered graded cells.
Persistent light adaptation, membrane and release/Ca states should transform
retinal input into a voltage-dependent continuous release signal. Preserve
incoming synaptic feedback instead of forcibly overwriting the entire source
state with luminance. A normalized release unit and its conductance conversion
must be declared; “equivalent Hz” must not be described as actual spiking.
Delayed continuous release and its clock phase must also survive checkpoints.

Start with specifically identified R1–R6 populations and receptor-appropriate
histaminergic targets. R8 can co-transmit ACh and histamine to different targets,
so a uniform sign for every photoreceptor would miss known biology.
[Photoreceptor cotransmission, Nature 2023](https://www.nature.com/articles/s41586-023-06681-6)
L1/L2 and other early visual cells also use graded responses; replacing only
photoreceptors does not validate an otherwise spiking visual pathway.

Until the compound-eye samples are spatially registered to identified retinal
cells and spectral channels, uniform luminance can test a limited input pathway.
It cannot establish optic flow, object direction, or visual steering. Needed
checks include dark/light steady states, flash/on/off responses, adaptation,
histamine receptor perturbations, feedback dependence and retinotopic mapping.
