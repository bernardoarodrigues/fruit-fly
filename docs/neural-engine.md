# Persistent neural engine

`fruitfly/neural.py` runs an imported outgoing CSR graph with one persistent
membrane potential, synaptic drive, refractory clock, and delayed-event state
per neuron. It does not replace the imported graph with a small controller.
`LIFNetwork.from_connectome(connectome)` accepts the MaleCNS import directly.

The implementation is an explicitly limited point-neuron model. Matching its
reference implementation establishes numerical agreement; it does not establish
whole-organism biological validity, identify physiological synaptic strengths,
or validate sensory/motor interface mappings.

## Model and reference

The baseline follows [Shiu's model.py at commit
91bdd1e7](https://github.com/philshiu/Drosophila_brain_model/blob/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/model.py):

```
dv/dt = (v_rest - v + g + external_drive) / tau_membrane
dg/dt = -g / tau_synapse
spike when v > threshold
reset v to v_reset and g to zero
```

The defaults are `v_rest = v_reset = -52 mV`, threshold `-45 mV`, membrane
time constant `20 ms`, synaptic time constant `5 ms`, refractory time `2.2 ms`,
and fixed synaptic delay `1.8 ms`, with integration step `0.1 ms`. The original
reset code additionally assigns `w = 0`; `w` is not a neuron state variable in
that model, so this does not reset synaptic edge weights and is omitted here.
Despite the source's “alpha synapse” comment, the implemented `g` is a single
exponentially decaying voltage-valued state, not an alpha-function conductance.

The graph importer supplies **already signed and scaled mV weights**. The engine
does not infer signs, threshold edges, normalize degrees, or multiply by another
contact scale. The Shiu baseline uses `0.275 mV` per signed synaptic contact.
Applying the same numerical parameter to MaleCNS is a transfer assumption,
not a fitted male physiological parameter. Keep the import transform manifest
with every run. Unsupported graded transmission, receptor-specific polarity,
electrical coupling, compartment dynamics, and neuromodulation remain limitations.

Voltage and synaptic state use float64; input edge weights use float32. The
continuous two-state system is integrated with its exact linear transition for
each fixed input interval. A finite timestep still quantizes threshold crossing,
spike time, and event delivery. Both time constants may be equal. Neural steps,
delay and refractory durations must be exact integer multiples of `dt_ms`;
incompatible values are rejected instead of silently rounded.

## Timestep semantics

The execution order matches the relevant Brian2 default schedule:

1. Determine which neurons have left refractory state; integrate their `v` and
   `g`. Both variables remain frozen for refractory neurons.
2. Detect thresholds and timestamp spikes with the current tick time. Mark
   spiking neurons refractory for the rest of this tick.
3. Deliver due graph events to `g`; refractory targets reject the updates.
4. Deliver direct stochastic voltage stimulation after threshold detection.
5. Reset both `v` and `g` for neurons that spiked this tick.

Consequently, a spike at `t = 0` with `1.8 ms` delay reaches the target's
synaptic state during tick `t = 1.8 ms`; the first resulting membrane integration
is at `t = 1.9 ms`. Even zero-delay events influence the next threshold evaluation.
A `2.2 ms` refractory neuron becomes available at spike tick plus 22 default
steps. Incoming updates to clamped state are discarded, not buffered until the
refractory period ends. These details were checked against the installed
Brian2 2.10.1, including its generated state-update code.

Brian documents [refractory write protection](https://brian2.readthedocs.io/en/stable/user/refractoriness.html)
and the [default simulation schedule](https://brian2.readthedocs.io/en/stable/user/running.html#scheduling).

## API and units

```python
import numpy as np
from fruitfly.neural import LIFNetwork, LIFParameters, SparseDrive

brain = LIFNetwork.from_connectome(connectome, seed=17)
sensory_indices = brain.indices_for_ids(sensor_body_ids)
motor_indices = brain.indices_for_ids(motor_body_ids)

activity = brain.advance(
    1.0,  # milliseconds, not seconds
    drive=SparseDrive(sensory_indices, rates_hz=sensory_rates_hz),
    outputs=motor_indices,
)
motor_spike_counts = activity.counts(motor_indices)
```

Indices are positions in the imported neuron array; `neuron_ids` are source IDs.
They are never interchangeable. `SpikeBatch` includes the filtered indices,
source IDs, absolute `times_ms`, interval bounds, full-network `total_spikes`,
and the number of synaptic edges visited during event delivery.

`outputs=None` records every spike; `outputs=[]` disables spike storage.
Filtering output never disables hidden neurons or their propagation. Sampling
only a motor population can reduce recording memory without truncating dynamics.
`step(...)` is equivalent to advancing one `dt_ms` interval. No state is rebuilt
at body, sensory, display, or recording boundaries.

`SparseDrive` accepts unique neuron indices plus scalar or per-index arrays:

| Argument | Interpretation |
|---|---|
| `rates_hz` | One independent Bernoulli arrival per target per step, probability `rate_hz * dt_ms / 1000`, matching the original `PoissonInput(N=1)` discretization |
| `poisson_weight_mv` | Voltage jump per arrival; defaults to `68.75 mV = 250 × 0.275 mV` |
| `current_mv` | Held additive effective drive in the membrane equation; an equilibrium-voltage displacement, **not amperes** |
| `disable_refractory` | Defaults to true for the specified Poisson targets, as in the original activation model |

Rates must lie in `[0, 1000 / dt_ms]`; this finite-step input is not a sampler
allowing multiple arrivals in one tick. A physiological sensory encoder must
justify its rates and stimulation amplitude independently. Shiu's large direct
voltage jumps model experimental activation, not an already calibrated receptor
transduction mechanism. Supplying `rates_hz=0` still declares a direct Poisson
target and removes its refractory period unless `disable_refractory=False`.
Leaving `rates_hz=None` does not alter refractory time for current-only input.
Drive is held for the requested interval and replaced at the next call.

## State, reproducibility and interventions

The engine owns a deterministic xorshift64* random stream seeded through NumPy's
SeedSequence. RNG state advances continuously and is included in checkpoints.
For the same graph, seed, ordered drive sequence and parameters, changing
`advance()` chunk boundaries does not change spikes or final states. Equivalent
drives with differently ordered target arrays do not promise identical random
assignments to neurons. This RNG is not Brian2's RNG; stochastic sample paths
across implementations need not match even with equal integer seeds.

`reset(seed=...)` resets time, state, delay queue and random stream; by default
it also clears ablations. `reset(keep_ablations=True)` retains interventions.
`save_checkpoint(path)` / `load_checkpoint(path)` preserve membrane/synaptic
state, last-spike clocks, current drive, refractory overrides, RNG state, pending
events, ablation mask and clock. Checkpoints use non-pickled NPZ arrays and verify
a SHA-256 hash of graph IDs/topology/weights plus all numerical parameters.
The same graph must be constructed before loading. Treat graph arrays as immutable
for the lifetime of an engine; checkpoints do not duplicate large graph data.

`ablate(indices)` suppresses **outgoing graph edges at delivery**, including
already pending events. It does not silence incoming edges or prevent the
neuron from spiking. `ablate(indices, enabled=False)` restores those outgoing
edges. A motor-readout silencing experiment must separately suppress the motor
adapter's readout. These are distinct interventions and must be named accurately
in experiment manifests.

## Tests and performance contract

Run the focused checks with:

```
.venv/bin/python -m pytest tests/test_neural.py -q
```

The reference-engine suite contains **27 checks**; the combined reference and
conductance suite passed **46 checks in 1.59 s** on 2026-09-05 UTC. Two
tests ran live Brian2 2.10.1: a recurrent excitatory/inhibitory network with
fixed current, and probability-one direct Poisson stimulation. The deterministic
spike times match; voltage/synaptic traces agree to absolute tolerance
`4e-11 mV`. Brian2 tests skip only when the optional validation dependency is
unavailable; the independent SciPy matrix-exponential reference remains required.

Additional tests check delayed causality across calls, zero delay, refractory
freezing and rejected arrivals, conductance reset, equal time constants,
deterministic seed/reset behavior, arbitrary chunk boundaries, complete checkpoint
restoration while spikes are pending, atomic rejection of corrupt/nonfinite
checkpoint state, graph mismatch rejection, recording-only
filters, outgoing ablation, quiet-network behavior and invalid inputs. These
tests establish numerical/control behavior on controlled networks; they do not
substitute for full-connectome benchmarks, published circuit replication, or
male sensory-to-motor and behavioral validation.

Every timestep visits neuron state once. Only presynaptic neurons whose spikes
are due trigger outgoing-edge traversal: no whole-edge-matrix scan occurs in
quiet timesteps. Memory for the delay queue is approximately
`4 * neuron_count * (delay_steps + 1)` bytes plus per-slot counts, rather than
one queue entry per anatomical edge. At 166,700 neurons and default delay,
that is 12.7 MB decimal. Queues store only source identities; counts limit the
valid entries and checkpoint serialization never writes uninitialized storage.

The real-graph benchmark should load the released MaleCNS CSR, warm the JIT
with a short run, reset, and measure at least 100 ms with recorded input indices,
rate distribution, parameter values and output selection. Report full neuron
and edge counts, graph hash, `total_spikes`, `traversed_edges`, wall/simulated
time and peak resident memory. Compare quiet and active regimes. Keep load/JIT,
neural evolution, rendering and body-loop timing separate. A quiet-graph timing
is not a full closed-loop or high-activity benchmark; GPU need must follow the
measured active workload.

The first actual MaleCNS benchmark is saved in
[`validation/neural-benchmark.json`](../validation/neural-benchmark.json).
It uses **166,700 neurons and 25,582,938 directed edges**, preserves the import's
sign/weight rules, and records the 1,314 annotated descending neurons:

| 100 ms condition | Stimulated cells | Wall time | Whole-network spikes | Descending spikes | Edges visited |
|---|---:|---:|---:|---:|---:|
| Quiet | 0 | 0.161 s | 0 | 0 | 0 |
| ORN_VA2 at 150 Hz | 83 | 0.237 s | 53,604 | 601 | 20,953,972 |
| All annotated ORNs at 150 Hz | 2,635 | 0.348 s | 144,164 | 969 | 40,007,768 |

Every condition ended with finite state. These measurements establish actual
full-graph execution and sensory-population-to-descending activity, with neural
runtime around 2.4–3.5 wall seconds per active simulated second in these brief
conditions. They do not establish calibrated motor behavior or long-run network
stability. Input IDs, seed, graph hash and timing boundaries are in the result;
other concurrent work on this Mac may affect the timing.

The original Shiu graph has also been exercised against the original Brian2
builder; see [`replication.md`](replication.md) for the separate source-release
selection, complete-network numerical comparison and sugar/MN9 trial results.
