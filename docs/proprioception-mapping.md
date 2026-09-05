# MaleCNS leg proprioception: exact types and limited adapter

Research snapshot: 2026-09-04. FeCO identities are supported by the **synonyms in the primary MaleCNS v1.0 annotation file**, rather than by guessing from `SNpp` names or treating every mechanosensory cell as equivalent. The [primary annotation download](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather) has SHA-256 `2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2`; it is part of the [MaleCNS release](https://male-cns.janelia.org/). These are male neuron IDs, not substituted FANC/FlyWire IDs.

| Source-supported family | Exact MaleCNS types | What remains unresolved |
|---|---|---|
| FeCO hook | SNpp39, SNpp41 | Which type is flexion versus extension selective |
| FeCO claw | SNpp50, SNpp51 | Flexion/extension assignment and each neuron's angle band |
| FeCO club | SNpp40, SNpp47, SNpp56, SNpp57, SNpp60 | Individual movement/vibration tuning, gains and adaptation |

Synonyms are populated on some exemplars, not every row. The catalogue explicitly propagates the family identity at the **annotated type level**, requiring at least one matching source synonym for every included type. This does not infer an individual cell's tuning curve. Combined or unresolved labels such as `SApp23,SNpp56`, generic `SNppxx`, unknown sensory cells, tactile bristles, hair plates and campaniform sensilla are excluded from the adapter.

## Leg routing and counts

Use `rootSide` for receptor side, with the existing loader's soma-side fallback only when root side is absent. The nerve mapping is ProLN→front, MesoLN→middle, MetaLN→hind. One SNpp40 cell annotated with ProAN is excluded; that route must be resolved independently.

| Family | LF | LM | LH | RF | RM | RH | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hook | 4 | 11 | 10 | 7 | 17 | 12 | 61 |
| Claw | 4 | 23 | 23 | 1 | 18 | 25 | 94 |
| Club | 9 | 31 | 32 | 3 | 31 | 31 | 137 |

Exact body IDs, graph row indices and types are saved in [the machine-readable catalogue](../data/proprioception-mapping.json). These are **identified subsets**, not a claim that all FeCO afferents are mapped. Their strong foreleg and left/right count differences must not be interpreted as biological sexual dimorphism or compensated by inventing missing cells.

## Functional evidence and implementation boundary

Mamiya et al. used controlled tibia movements and calcium imaging to identify position-selective claw, direction-selective hook, and bidirectional movement/vibration-sensitive club projections. The measured variable is **relative femur–tibia joint motion**, not the animal's translational world speed. [Neuron 2018](https://doi.org/10.1016/j.neuron.2018.09.009)

Peripheral biomechanics separate the FeCO compartments and help establish their selectivity. Claw cells cover different angle ranges; submicrometre, high-frequency vibrations recruit club pathways. Thus one global contact-force scalar cannot replace all three families. [Neuron 2023](https://doi.org/10.1016/j.neuron.2023.07.009)

The 2025 circuit reconstruction distinguishes local motor feedback through claw/hook from club pathways that integrate across limbs and ascend toward brain mechanosensory regions. That work reconstructed **female** FANC/FAFB circuitry; it informs functional hypotheses but does not provide interchangeable male IDs. [Nature Communications 2025](https://www.nature.com/articles/s41467-025-59302-3)

`fruitfly.proprioception.ClubMovementEncoder` is therefore a deliberately limited, optional **bidirectional tibia-speed proxy** for the 137 typed male club afferents. It reads the actual body joint velocities in LF, LM, LH, RF, RM, RH order and stimulates only the corresponding leg's exact club types. It returns the existing `SparseDrive` format. It does not read food, coordinates, whole-body speed or support forces.

The caller must explicitly choose `max_rate_hz` and `half_speed_rad_s`; neither has a claimed biological default. The rate law is the declared engineering approximation `max_rate × abs(joint_speed) / (half_speed + abs(joint_speed))`. Zero motion emits no event-drive entries. Opposite signed velocities have the same club rate. The transfer is not fitted to calcium signals, measured spikes, subtype adaptation or movement-state suppression.

```python
from fruitfly.proprioception import ClubMovementEncoder

# These numbers are an assay configuration, not measured receptor constants.
encoder = ClubMovementEncoder(connectome, max_rate_hz=30, half_speed_rad_s=5)
drive = encoder.encode(body.observe())
```

No hook/claw rate adapter is supplied because the required sign and angle-band crosswalk is unresolved. Vibration encoding is also absent: sampling joint speed at an ordinary sensory coupling interval cannot claim to resolve a high-frequency vibration spectrum. Contact force remains a physical observation until a separate, supported campaniform-sensillum mapping and strain model exist.

## Reproduce and validate

```bash
.venv/bin/python -m fruitfly.proprioception
.venv/bin/python -m unittest tests.test_proprioception -v
```

Tests establish leg-specific targeting, bidirectional symmetry, zero-drive behavior, and rejection of an unsupported type-family alias. Catalogue generation was run against the actual 166,700-neuron male import. These are interface and provenance checks. They do not establish biological gait correction, natural firing rates or the completeness of proprioceptive feedback. Integrate the adapter only with its own on/off and gain-sensitivity assays; keep club, hook and claw interventions separate.
