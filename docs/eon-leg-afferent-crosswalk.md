# Eon leg inputs: sensory ascending versus ascending interneurons

**The notebook mixes two distinct input categories: 12 sensory ascending gustatory cells (`SA_VTV_2`) and two ascending interneurons (`AN_GNG_162`).** The two extra cells have a defensible MaleCNS type-family crosswalk, but the available annotations do not identify a unique male pair. No runtime, upstream notebook or model was executed or changed.

The source is [Eon's notebook at commit `c976c7a9`](https://github.com/eonsystemspbc/drosophila_brain_model_lif/blob/c976c7a90b2ac5a472c028b5862974217e93573f/results/eon_1/demo_notebook.ipynb). Cell index 14 defines the 12-element `lgAG2` list and adds `leg_ascending_neurons`; indices 34–36 assign unilateral names and stimulate the two latter IDs. These labels are author code annotations, not independent physiology measurements. Exact source hashes, cell text and all IDs are preserved in the [bounded evidence JSON](../validation/eon-leg-afferent-crosswalk-evidence.json). FlyWire IDs are stored as strings to avoid floating-point truncation.

## Exact FlyWire identities

Both cells have the same type and hierarchy in the [publication annotation release v2.1.0](https://github.com/flyconnectome/flywire_annotations/tree/ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0) and [current release v3.1.0](https://github.com/flyconnectome/flywire_annotations/tree/8587524c1748ce5ef2080822a2fc890fc03bf597): `flow=afferent`, `super_class=ascending`, `cell_class=AN`, `cell_sub_class=AN_GNG`, `cell_type=AN_GNG_162`, `nerve=CV` (cervical connective). Acetylcholine is their predicted transmitter, not a physiological measurement.

| Exact FlyWire root ID | Notebook unilateral label | Primary annotation nerve-entry side | Current-release classification |
|---|---|---|---|
| `720575940627697664` | `ascending_leg_right` | left | `AN_GNG_162`, ascending AN |
| `720575940618066369` | `ascending_leg_left` | right | `AN_GNG_162`, ascending AN |

There are eight `AN_GNG_162` cells in each inspected release, four per entry side; the notebook selects one per side. The current rows mark the type as isomorphic, but provide no individual male ID, synonym, matched hemibrain type or informative matching note for these two cells.

The 12 `lgAG2` IDs all map to `SA_VTV_2` in both releases. **Their hierarchy changed:** v2.1.0 uses the coarse `ascending`/`AN` fields, whereas v3.1.0 uses `sensory_ascending`/`gustatory`; both retain the sensory-ascending subclass `SA_VTV_pro_meso_meta`. The current annotation has six per nerve-entry side. Thus an older superclass string alone must not convert these sensory axons into ascending interneurons.

The [primary annotation paper](https://www.nature.com/articles/s41586-024-07686-5) distinguishes peripheral sensory input from VNC-to-brain ascending neurons, and its “ANs and DNs” methods explicitly separate sensory ascending (SA) neurons from ANs using MANC morphology and tract membership. `afferent` describes direction toward the brain and includes both categories. The evidence supports treating the SA group as gustatory sensory projections, distinct from the two central ascending ANs. It does not independently establish sugar selectivity or the represented leg for the two AN cells.

## MaleCNS crosswalk: eight candidates, no unique pair

Exact matching of `flywireType == AN_GNG_162` in local `data/processed/malecns_v1/neurons.feather` returns the eight rows below. Their biological annotation fields agree with the original [MaleCNS v1.0 body-annotation file](https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather), independently checked locally.

| MaleCNS body ID | Male type | Soma side | Soma neuromere |
|---|---|---|---|
| `25819` | `AN01B004` | R | T2 |
| `27859` | `AN01B004` | L | T2 |
| `28192` | `AN01B004` | L | T3 |
| `30889` | `AN01B004` | R | T3 |
| `57382` | `AN01B004` | R | A1 |
| `64916` | `AN01B004` | L | A1 |
| `516239` | `ANXXX255` | L | T1 |
| `523509` | `ANXXX255` | R | T1 |

All eight have MaleCNS `superclass=ascending_neuron` and CNS soma locations. Six belong to `AN01B004`, two to `ANXXX255`. Body `30889` carries `matchingNotes="biological variability mcns"`; the others have no matching note. None has a per-cell FlyWire ID. Equal group sizes do not establish a one-to-one correspondence, and the T1 pair must not be selected merely because the notebook calls its inputs “leg” neurons. No pair or side mapping is chosen here.

## Side and engineering interpretation

The [primary column definitions](https://github.com/flyconnectome/flywire_annotations/blob/8587524c1748ce5ef2080822a2fc890fc03bf597/supplemental_files/README.md) define `side` as nerve-entry side for sensory/ascending neurons, whereas MaleCNS `somaSide` describes the soma. The notebook does not define whether its unilateral labels indicate a represented leg, entry tract or another convention. Consequently the opposite labels are a **crosswalk uncertainty, not an established biological error**. The paper also documents correction of a left/right inversion in the original FAFB images; raw viewing orientation should not replace annotated biological side.

A defensible comparison is: **Eon's leg-input list includes gustatory sensory ascending axons and direct excitation of two ascending interneurons.** The latter is a different encoding entry point from driving peripheral GRNs alone. It can remove the need to generate those AN inputs through a simulated upstream circuit, but that is an engineering interpretation of direct stimulation, not a claim that all sensory ascending cells bypass primary afferents, that a biological pathway has been lost, or that the notebook reproduces natural sugar sensing. Equivalence to this project's 54 peripheral GRNs has not been established.

Only two bounded annotation tables, their provenance/column documentation and the primary paper HTML were acquired (about 60 MB total). No morphology, connectivity matrix or additional dataset was downloaded. Source, annotation-release and local-file hashes are retained in the evidence JSON; pre-existing research and experiment outputs remain unchanged.
