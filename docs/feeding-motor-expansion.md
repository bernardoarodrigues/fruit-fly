# From a taste-triggered intake assay to physical feeding

The current simulator demonstrates a causal tarsal-taste → neural-activity →
abstract-intake interface. It does not yet implement a swallowing motor program.
The next physical boundary should separate reaching the food, opening the mouth,
pumping fluid and moving that fluid into the foregut.

## Newly checked primary evidence

[McKellar et al. (2020)](https://doi.org/10.7554/eLife.54978)
combines anatomy, activation and silencing to distinguish proboscis movements.
Muscle 9 protracts the rostrum; muscle 4 extends the haustellum; muscle 3 flexes
it; muscles 6/7 affect labellar extension/abduction. Rostrum retraction involves
muscles 1, 2D and 2V. Their pharyngeal muscle insertions distinguish positioning
from pumping. Male feeding and courtship measurements also show that the same
appendage reaches in different directions. Consequently MN9 is not a generic
flow-rate signal. Published figures/videos and annotations were inspected; a
raw numeric angle dataset has not been recovered here.

[Manzo et al. (2012)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3341050/)
measures pump frequency, ingestion rate and volume per pump separately.
Perturbed animals can cycle fluid without comparably reducing the external
droplet. Thus motor activity, pumping cycles and successful net ingestion are
different observables. Only indexed primary extracts were accessible in this
pass; full numerical methods/values have not been imported.

[Qin et al. (2024)](https://doi.org/10.7554/eLife.88614)
studies pharyngeal mechanosensory feedback during cibarium filling and emptying.
Perturbing nompC, Tmc or piezo changes swallowing, including its emptying phase;
viscosity matters. A future model needs a physical or explicitly reduced
cibarium state and separately mapped feedback, rather than copying foot contact
into all pharyngeal neurons. The paper links a
[Dryad dataset](https://doi.org/10.5061/dryad.vdncjsz4q); it has not been acquired
or assigned a license here. The full article fetch returned 403; indexed primary
text supplied these bounded qualitative findings.

[Wei et al. (2025)](https://elifesciences.org/articles/101440)
finds direct volatile-odor responses in gustatory neurons and enhanced feeding
under odor/taste combinations. Experiments use female flies and include labellar
stimulation; this does not establish the same response curve for our mapped leg
cells. The study provides tracked proboscis landmarks and
[author code](https://github.com/hpwei82/2022_hpwei), with data at
[RIKEN](https://doi.org/10.60178/cbs.20250801-001).
These are candidates for a later calibrated multimodal encoder. No rates,
weights or new non-contact taste inputs were installed. The dataset's primary
license and numeric files still need direct verification before reuse.

## What is present in our actual graph and body

The [executed catalogue and recruitment audit](../validation/feeding-motor-recruitment.json)
identifies 48 `cb_motor` cells across 18 exact MN-number annotations. It retains
every ID, soma side, exit nerve, transmitter consensus, FlyWire cross-reference
and synonym. `rootSide` is null for these cells; soma side does not establish
which muscle compartments an axon innervates. The imported CNS graph does not
contain muscle targets or a calibrated neuromuscular transfer function.

Two `GNG588` cells, IDs **12617** and **14321**, carry the released synonym
`Shiu 2022: Fdg`. A literal search for a `type` called `Fdg` would miss them.
This is an annotation-supported candidate correspondence, not a new functional
discovery. They are included separately from the motor-neuron catalogue.

The constructed default NeuroMechFly has rostrum and haustellum meshes but
**zero proboscis joint degrees of freedom and zero proboscis actuators**.
The anatomical composition API can add joints, but there is no validated mouth
contact point, independent labellar opening, cibarium or liquid-flow mechanism
in the current runtime. The alternate FlyBody assets contain additional oral
segments; their presence alone does not implement a feeding controller.

## Executed recruitment and afferent replay

The first script ran five conditions for each of seeds 11 and 12, all for
0.5 seconds with the unchanged full graph and existing taste calibration.
It monitored every catalogued cell, not only cells that happened to respond.

| Closed-loop condition | Intake, seed 11 | Intake, seed 12 | MN9 spikes, seed 11 / 12 |
|---|---:|---:|---:|
| Original taste assay | 0.009432 | 0.005904 | 3 / 3 |
| Motor readout muted | 0 | 0 | 4 / 1 |
| Fdg candidate outputs blocked | 0.001648 | 0.009056 | 2 / 3 |
| Taste disabled | 0 | 0 | 0 / 0 |
| Sweet-cell outputs blocked | 0 | 0 | 0 / 0 |

Intake uses the existing normalized engineering units, not microlitres. Neither
baseline recruited MN4a/MN4b or MN6. MN7 emitted zero/one spike, and MN11D/MN11V
were silent. Some other motor classes responded sparsely. This is insufficient
evidence of coordinated oral extension, opening and pumping. All counts and
5 ms voltage samples are preserved. Sampled whole-network minima reached
approximately −408 to −437 mV in active conditions, retaining the previously
documented physiological failure of the transferred Shiu baseline.

The original equality control **failed**, and its failed check remains in the
first result. In baseline trials the body starts walking at 30/25 ms; foot
contacts change at those same times. Muted trials instead retain the initial
159 ordered inputs (105 zero-rate ORNs plus 54 sweet cells), and their complete
input hashes equal repetition of that initial array. This is a feedback change,
not evidence that the mute directly rewrites neural equations.

The follow-up recaptured both original baselines exactly, including ordered
input hashes, every monitored spike count and intake. It saved all 100 ordered
5 ms afferent arrays per seed and replayed them into fresh **neural-only**
networks. Unblocked replay reproduced the monitored spike times and identities
exactly in both seeds. With the same external inputs and candidate Fdg outgoing
synapses blocked, MN9 counts changed from **3→0** and **3→1**. Fdg cells still
fired, and their activity could change through recurrent feedback. No replay
intake value is reported because the replay did not run a body.

Thus the matched-input experiment supports a contribution of the two candidate
Fdg cells to MN9 recruitment **within this uncalibrated model and these two
input histories**. The opposing closed-loop intake changes are not an isolated
measure of that neural contribution. Two seeds with few motor spikes do not
establish biological necessity or a robust motor program.

```sh
# Preserves the failed closed-loop equality assumption and exits nonzero.
.venv/bin/python scripts/audit_feeding_motor_recruitment.py

# Reproduces the baseline and tests recorded afferents separately; all3checks pass.
.venv/bin/python scripts/check_feeding_afferent_replay.py
```

These are research diagnostics, not failing unit tests or changes to runtime
defaults. The follow-up links the original result by checksum. Neither result
was used to tune a parameter, select a motor gain or install a new feeding rule.

## Prospective implementation sequence

1. Recover numeric joint/landmark trajectories and their anatomical angle
   convention. Reproduce an isolated rostrum/haustellum replay with measured
   geometry before changing ingestion. Keep head motion and labellar motion
   explicit; mouth position must follow actual joint transforms.
2. Resolve each motor population's projection and muscle action. Add a declared
   activation/force or bounded position interface, then compare extension and
   withdrawal under individual MN interventions. Do not interpret a CNS
   transmitter classifier as a signed mechanical torque.
3. Gate fluid contact at the actual mouth, not the feet. Retain tarsal taste as
   a sensory trigger. A reduced two-phase pump can be useful, but its pressure,
   resistance, compliance and rate constants need source units and viscosity
   checks. Until then, keep normalized engineering intake units.
4. Conserve volume and nutrient/water content separately through external food,
   cibarium, foregut and storage. Count successful transported volume, not just
   pump activation. Feedback should sense the represented physical state.
5. Validate target-height changes, interruption, viscosity, source depletion,
   motor/source-output interventions and matched afferent replay. Feeding
   initiation, oral movements and ingestion each need their own endpoint.

The new audit's initial assumption that motor muting would preserve sensory
inputs failed: the unmuted fly briefly walks, changing its leg contacts. That
result is retained, and the [recorded-input follow-up](../validation/feeding-afferent-replay.json)
separates neural-circuit effects from altered sensory feedback. No controller or
parameter was changed to make that assumption pass.
