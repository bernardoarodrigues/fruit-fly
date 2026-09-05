# Navigation ladder: exact male identities and contacts

The proposed anatomical populations are present in the retained MaleCNS v1.0 graph. **All ten quoted contact totals reproduce after their selectors are made explicit, but three descriptions conceal broader selections.** The audit passed **2,070 checks**, joining **947 selected neuron pairs to 947 original contact-table rows**. No graph, neural dynamics, defaults or gains changed; no neural simulation ran.

The reproducible [manifest](../validation/navigation-ladder-anatomy.json) contains **34 groups and 1,649 distinct cells**, including the full annotated DN population. Each group supplies ordered graph `indices`, `body_ids`, its exact selector, annotation counts and exhaustive side partitions. The centralized `neurons_by_index` preserves each cell's type, cross-dataset names, soma/root side, instance, grouping, transmitter annotations and literal column tokens. `mirror_mapping` and `column_angle_mapping` remain null. An anatomically mapped group is not a validated functional ensemble.

## What the ten totals select

All values below are unsigned synaptic-contact multiplicities, without mV scaling or transmitter signs.

| Connection | Contacts | Exact selection |
|---|---:|---|
| VM7d ORNs → VM7d adPNs | 10,251 | 36 `ORN_VM7d` → 7 `VM7d_adPN` |
| Pooled DM1/DM4 ORNs → cholinergic PN set | 18,390 | 106 ORNs → 2 `DM1_lPN` + 2 `DM4_adPN`; includes cross-glomerular edges |
| DM1/DM4 cholinergic PNs → LHAD1b2 family | 96 | Those four PNs → 8 `LHAD1b2` + 6 `LHAD1b2_b` + 5 `LHAD1b2_d` |
| LHAD1b2 family → LHCENT3 | 257 | The same 19-cell family → 2 `LHCENT3` |
| MBON12–14 → FB5AB | 316 | 4 `MBON12` + 2 `MBON13` + 4 `MBON14` → 2 `FB5AB` |
| LHPV5e1 → FB5AB | 224 | 2 → 2 cells |
| FB5AB → hDeltaC | 1,751 | 2 → 20 cells |
| PFNa → hDeltaC | 1,303 | 58 → 20 cells |
| PFL3 → DNa02 | 736 | 24 → 2 cells |
| PFL3 → DNg97 | 301 | 24 → 2 cells |

The strict cognate cholinergic sum is **18,165**, comprising DM1 ORN→DM1_lPN **13,384** and DM4 ORN→DM4_adPN **4,781**. The quoted pooled total adds **225 cross-glomerular contacts**. Including the two GABA-annotated `DM4_vPN` cells raises the pooled total to **18,471**. These are distinct, explicitly named groups in the manifest.

Selecting only the exact primary type `LHAD1b2` gives **72** contacts from the four cholinergic PNs and **115** contacts to LHCENT3. It must remain separate from the 19-cell family. A further cross-namespace hazard is retained: 17 cells with primary types `CB4208`/`CB4209` carry FlyWire labels `LHAD1b2_a,LHAD1b2_c`. They are listed as cross-dataset alias candidates and are not silently included in either primary-type group.

## Identity and side evidence

The source's annotation table has `rootSide` and `somaSide`, without a separate `hemisphere` field. The current code's `rootSide.fillna(somaSide)` fallback is recorded as a convenience partition, alongside both original fields; it is not a calibrated projection side or directional tuning label. The [MaleCNS paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12636603/) also distinguishes the two source annotations when describing its combined side field.

| Population | Cells | Available side evidence |
|---|---:|---|
| ORN_VM7d | 36 | Root L18/R18; soma absent |
| ORN_DM1 | 74 | Root L35/R39; soma absent |
| ORN_DM4 | 32 | Root L16/R15/unknown1; soma absent |
| VM7d_adPN | 7 | Soma L3/R4 |
| LHAD1b2 exact / family | 8 / 19 | Soma L4/R4 / L10/R9 |
| MBON12 / MBON13 / MBON14 | 4 / 2 / 4 | Two / one / two somas per side |
| hDeltaC / hDeltaK | 20 / 31 | Soma L9/R11 / L16/R15 |
| PFNa / PFL2 / PFL3 | 58 / 12 / 24 | Soma L29/R29 / L6/R6 / L12/R12 |
| All annotated descending neurons | 1,314 | Soma L656/R648/M10; root absent |

`ORN_DM4` body **766592451** has `rootSide="unknown"`, no soma side, and entry nerve `AN`. Thus the anatomical DM1/DM4 union has **106** cells, while the explicitly known-root-side subset has **105**. The unassigned cell remains in the anatomical population; it is not assigned to an invented hemisphere.

The full DN selector is **`superclass == "descending_neuron"`**. A `type.startswith("DN")` query instead returns 1,342 cells, misses 18 true annotated DNs, and admits 46 cells of other superclasses, including `DN1*` names. Ten midline DNs remain in the full population and in a separate `M` side bucket. The DN label establishes an anatomical class, not navigation-specific function.

| Named DN | Left soma body ID | Right soma body ID | Current transmitter annotation |
|---|---:|---:|---|
| DNa01 | 10442 | 10760 | acetylcholine |
| DNa02 | 523769 | 10360 | acetylcholine |
| DNg97 / current oDN1 readout | 13805 | 230783 | acetylcholine |
| DNp09 / P9 | 10783 | 11177 | acetylcholine |
| DNb05 | 10118 | 10065 | acetylcholine |
| DNg34 | 10295 | 13585 | unclear |

The two DNg34 cells currently have `model_sign=0` because their consensus transmitter is unclear. The audit preserves that implementation fact and does not assign a biological sign. Likewise, grouping two somas by name and side does not itself establish matched response amplitudes or mirror-equivalent wiring.

## Columns and hDelta interpretation

No dedicated column-angle field is present. Literal `_C…` instance tokens occur in all 20 hDeltaC cells, all 31 hDeltaK cells, 56 of 58 PFNa cells, and every PFL2/PFL3 cell. They are not unique: hDeltaC has 12 distinct tokens, hDeltaK has 18 including lettered sublabels, and PFNa/PFL2/PFL3 have nine each. Two PFNa instances lack these tokens. The `assignedOlHex*` fields are not populated for these navigation populations and provide no fan-shaped-body angle map.

Four PFL3 instances explicitly marked `irreg` have a PB token side letter opposite their soma side: bodies **15210**, **17286**, **18851** and **19009**. For example, body 15210 has instance `PFL3(PB12c)_R2_C1_irreg` and a left soma. An `_R2` token must not be treated as a right-soma label. Repeated labels, asymmetric cell counts and shared annotation `group` IDs do not supply a one-to-one mirror map. Circular metrics need a separately justified coordinate mapping; these metadata alone do not establish a localized activity bump.

The [2024 primary addendum](https://www.nature.com/articles/s41467-024-46225-8.pdf) states that VT062617 additionally, or predominantly, labels hDeltaK; the older sensory responses and navigation effects cannot be assigned unambiguously to hDeltaC. Its structural discussion concerns the earlier reference connectome. This male v1.0 audit finds **41 FB5AB→hDeltaK contacts** and **5 PFNa→hDeltaK contacts**, alongside the much larger hDeltaC totals. These sparse male contacts neither resolve the driver ambiguity nor establish efficacy, sex equivalence or a functional memory population. Keep both exact types as separate observations.

## Provenance and reproduction

The [official download documentation](https://male-cns.janelia.org/download/) identifies the annotation and segment-to-segment connection tables used here. The pinned files are the June 2026 v1.0 release, with a 0.5 synapse-detector confidence threshold. The processed inventory retains 166,700 cells with non-null superclass annotations, 25,582,938 neuron-pair edges and 124,177,617 contacts; it imposes no additional pair-strength threshold. The full original table scanned for this audit contains 151,856,684 segment-pair rows and 311,833,243 contacts, including segments outside that retained neuronal inventory. These two inventories are not interchangeable.

The receipt records every selected CSR edge index, source/target graph index and biological ID, raw contact multiplicity, original Feather record batch, row within batch and absolute row offset. Its before/after hashes cover graph arrays, metadata and original sources. The final receipt SHA-256 is `6020e73f80a552b960df5f042de619543bc6717a2c3d6ac1611b90a9b08908e9`; the [script](../scripts/audit_navigation_ladder_anatomy.py) SHA-256 is `e17371b15f121778dbc32cf159d00c289348ab123ccfeb5ccb168d8070c969ef`.

The [initial receipt](../validation/navigation-ladder-anatomy-initial-v0.json) and its [executed source](../validation/navigation-ladder-anatomy-initial-v0-source.py) remain preserved. Its cohorts and contact totals were correct, but convenience side partitions omitted an `M` bucket for the ten midline DNs. The final version adds that bucket and checks every side partition for exhaustive, disjoint coverage; cohort membership and contact totals are unchanged.

```sh
.venv/bin/python scripts/audit_navigation_ladder_anatomy.py \
  --output validation/navigation-ladder-anatomy-reproduction.json
```

Use these populations first to describe retained responses and select a prospective causal test. Contact sums cannot locate a dynamical bottleneck, demonstrate that a particular recurrent route carried the signal, or determine stimulation rates, synaptic gains, receptor effects, depression, delays or behavioral calibration.
