# Or42a primary-summary excitation experiment

All **15 trials completed and passed the frozen execution checks**. Blocking
the 36 VM7d source neurons' outgoing delivery eliminated all activity outside
those neurons while preserving their external excitation. The unblocked
network remained numerically finite, but sampled voltages reached **−503.07 mV**.
This is a propagation result with a known physiological failure, not a
validated olfactory simulation.

The standalone experiment applies literature-bounded excitation rates to the
36 exact MaleCNS `ORN_VM7d` cells in the unchanged full Shiu network. It does
not simulate a body or identify a chemical concentration-to-rate function.

The [primary assay audit](or42a-primary-assay.md) distinguishes the published
11 Hz baseline, 138 Hz ethyl-acetate increase, and raster-estimated 46.679 Hz
isoamyl-acetate increase. The totals of 149 and 57.67908699377742 Hz combine
different summary cohorts. DoOR's exact historical baseline restoration is
still unresolved. Isoamyl acetate is a reserved chemical lookup, not a
held-out prediction by a fitted receptor model.

## Measured outcome

The following are ranges across three simulation seeds during the middle
500 ms window. They are not confidence intervals or biological replicates.

| Condition | Actual mean VM7d rate, Hz | Non-source spikes | Motor-group result |
|---|---:|---:|---|
| No imposed input | 0 | 0 | All monitored groups silent |
| Constant baseline | 10.78–11.44 | 420,148–438,434 | MN9 23–31 spikes; other groups silent |
| Ethyl acetate | 145.28–150.06 | 413,998–441,727 | MN9 27–28 spikes; other groups silent |
| Isoamyl acetate | 56.94–58.83 | 426,208–441,060 | MN9 30–33 spikes; other groups silent |
| Ethyl acetate, outgoing blocked | 144.89–149.94 | 0 | All monitored groups silent |

All 1,500 middle-window sampled decoder commands were `rest`. Across the full
4,500 samples, there were 4,374 `rest` and 126 `walk` commands. Each unblocked
trial had one right-turn-group spike during its initial baseline window; the
decoder's filtered response yielded 14 unrealized `walk` samples (70 ms) with
zero forward-group spikes. That startup transient repeats across the three
conditions because they have identical pre-pulse inputs within each seed.
No physical movement or intake was tested. This does not establish spontaneous
foraging or odor attraction.

Input events and source spikes are observably different. For the unblocked
ethyl-acetate middle window:

| Seed | Requested arrivals | Applied voltage arrivals | Actual source spikes |
|---|---:|---:|---:|
| 11 | 2,703 | 2,666 | 2,669 |
| 12 | 2,647 | 2,609 | 2,615 |
| 13 | 2,747 | 2,700 | 2,701 |

The rejected arrivals coincide with source-firing ticks. Spike counts also
include recurrent effects and events crossing the window boundary. The blocked
comparison has the same requested event stream but 2,666/2,608/2,699 actual
source spikes in that window. It verifies why nominal excitation Hz must not
be relabeled as an afferent spike clamp.

Constant baseline alone drives extensive downstream activity in this model.
Ethyl acetate's larger input does not increase total downstream counts in
every seed. Neither observation identifies an odor code or a biological gain:
whole-network spike counts conflate heterogeneous neurons, and the voltage
failure already limits physiological interpretation. Unblocked sampled minima
across all conditions span down to −503.07 mV; sampled maxima reach +19.58 mV.
Direct-input block controls also reach +16.75 mV because excitation increments
are applied after the threshold phase of each tick.

The local archive is
`runs/20260905T030251528053Z-or42a-summary` (46,282,879 bytes across all files).
The trials took 66.75 wall seconds in total, excluding graph/plan setup but
including each trial's trace compression and accounting. This was not an
isolated performance benchmark. The compact committed report is
`validation/or42a-summary-experiment.json`; its SHA256 is
`09f8a0135d80b8ecffbc3ffe733fbcb8becba28617d7d2c1b784d073c156dada`.
`or42a-summary-window-table.csv` exposes all 45 windows, and the environment
receipt records the runtime versions and report/table hashes.

## Frozen design and reproduction

The plan was written before any neural advance, with SHA256
`32a0f8f33d61b532c871a025b975945c7d79530d123b4ee5f7753ea54a0dd41e`.
It preserves all 36 body IDs in ascending numeric order: 18 left, 18 right,
all with MxLbN root nerves. The full graph contains 166,700 neurons and
25,582,938 directed neuron pairs. No weights, delays, signs, time constants or
motor rules change.

Each of seeds 11, 12 and 13 runs five independent 1.5 s conditions, sequentially
for memory use. Every condition starts from reset state. Rate windows are
0–0.5, 0.5–1.0 and 1.0–1.5 s:

| Condition | First / middle / final rate per source, Hz |
|---|---|
| No imposed input | 0 / 0 / 0 |
| Constant baseline | 11 / 11 / 11 |
| Ethyl acetate | 11 / 149 / 11 |
| Isoamyl acetate | 11 / 57.67908699377742 / 11 |
| Ethyl acetate with source outputs blocked | 11 / 149 / 11 |

Even zero-rate controls retain the same 36-entry input list, 0.1 ms clock and
zero-refractory setting for listed sources. These are finite-grid Bernoulli
excitation events with probability `rate * 0.0001`, using the existing
68.75 mV direct voltage increment. They are **not forced afferent spikes**.
Uniform bilateral palpal input is imposed without a simulated delivery plume.
The final baseline window is not a validated biological recovery trajectory.

```sh
# On an empty output location, freezing the plan precedes running:
.venv/bin/python scripts/experiment_or42a_summary.py plan
.venv/bin/python scripts/experiment_or42a_summary.py run
```

The checked-in plan/report are intentionally protected from overwriting. To
repeat, use a separate checkout/output copy and preserve the original evidence.
Source hashes in the plan must match before running and after the experiment.

## What is counted

For every 5 ms interval, the script copies the RNG state and replays the
existing RNG algorithm without changing the live state. It records the
resulting requested events and verifies the live post-interval RNG state
exactly. With zero refractory time, a source is eligible for an excitation
event unless it has already fired on that same tick; all source spikes are
recorded, so this rejection and the applied direct voltage event set can be
reconstructed separately. The latter is a source-code-based reconstruction,
not a newly instrumented kernel counter.

The kernel's existing edge-visit counter is independently reconstructed from
every network spike, its 1.8 ms delivery delay, source outdegree and outgoing
block flag. It must agree for each 5 ms interval, including deliveries across
window boundaries and excluding the final pending spikes. Edge visits count
targets even when their refractory state prevents a synaptic state increment.
**Accepted postsynaptic increments are not exposed and are left unavailable.**

Outgoing suppression retains the source cells, incoming synapses, RNG draws
and direct excitation. It blocks delivery through their outgoing graph edges.
Actual source firing can therefore differ between blocked and unblocked runs
through changes in recurrent feedback; identical requested input alone does
not guarantee identical source spikes.

The trace retains all network spikes, requested/applied excitation events,
source spike IDs/ticks, per-cell window counts, final neural states and each
5 ms sample. Global and source voltage extrema are sampled at those 5 ms
boundaries; they are not continuous-time extrema. The 365 directly targeted
non-source neurons are a preregistered anatomical subset. Five existing motor
groups are monitored independently. Decoder commands use synthetic false
taste gates and never reach a body, so they are explicitly unrealized commands.

An [independent saved-data review](or42a-summary-independent-review.md) verifies all 15 trials, 4,500 diagnostic samples and 9,694,843 ordered spikes without rerunning the neural model.

## Interpretation limits

Passing identity, finite-state, RNG, time-grid and event-accounting checks
would establish correct execution of this specified numerical experiment.
The plan explicitly excludes biological voltage bounds, attraction, feeding,
walking, input-event/source-spike equality and monotonic downstream responses
from its pass gates. Those remain separate observations, including failures.
No rate or gain may be selected from downstream motor output.

This result inherits the primary input uncertainty and the Shiu network's
documented physiological limits. Independent simulation seeds do not provide
independent animal samples. A whole-network count is not an odor-code assay,
and a fixed lookup replay does not validate mixtures, adaptation, palp geometry
or airborne dose.
