# Native male APL geometry and synaptic attachments

Completed 2026-09-05 UTC. This step acquires the two native MaleCNS APL centerlines and implements a reusable forest-path calculation, following the [spatial physiology comparison](29-apl-spatial-data-comparison.md). It provides actual male neurite-path geometry for a future distributed feedback model. It does not assign membrane properties, fit release, or run the neural circuit.

## Source identity

The [official MaleCNS download documentation](https://male-cns.janelia.org/download/) exposes individual native SWC files in `v1.0/segmentation/skeletons-malecns/skeletons-swc/`. Their coordinates use 8 nm units, converted here to micrometers with factor 0.008. These are native EM coordinates, with no mirroring or unisex-template transform. The release is CC-BY.

The processed annotation table independently identifies exactly two `type=APL` cells: **10540 / APL_R / graph index 502**, and **10977 / APL_L / graph index 904**. Both retain `status=Traced` and `statusLabel=Roughly traced`; neither label is silently replaced by a claim of complete anatomy.

The [acquisition receipt](../validation/male-apl-skeleton-acquisition.json) records public URLs, immutable object generations, byte counts, MD5 and SHA-256. Both downloads matched the expected object generation, size and MD5. Raw sources remain ignored under `data/raw/male-apl-skeletons/` and can be reacquired with the [download script](../scripts/acquire_male_apl_skeletons.py).

| Cell | Source bytes | Nodes / edges | Component sizes | Total centerline length |
|---|---:|---|---|---:|
| APL_R | 1,565,689 | 43,737 / 43,734 | 43,724; 4; 9 | 37,267.61 µm |
| APL_L | 1,616,710 | 45,168 / 45,166 | 45,160; 8 | 37,613.96 µm |

Total length sums the entire branched arbor; it is not the linear extent of the neuron. The SWC headers explicitly describe coarse downsampling (`ds_intv=[63,63,63]`, `downresLevel=coarse`). Median segment length is 0.7241 µm. The longest edges are 9.2588 and 7.0574 µm. Radii have a 0.256 µm minimum, attained at 30,102 right and 31,545 left nodes. This coarse radius distribution is not a measured local membrane diameter distribution suitable for unqualified cable-parameter fitting.

## Geometry implementation and checks

[apl_skeleton_geometry.py](../scripts/apl_skeleton_geometry.py) validates SWC node/parent identity, finite coordinates, nonnegative radii and forest topology. It rejects missing parents and cycles. Components remain disconnected; no nearest-neighbor bridge is inserted. Distances between components return infinity.

Each synaptic endpoint is projected onto the **nearest line segment**, including degenerate root points. An initial nearest-node distance supplies a search upper bound. Any segment that could improve that bound must have its midpoint within the upper bound plus the maximum half-segment length. A midpoint tree therefore reduces the search while retaining all possible closer candidates. Each selected candidate is evaluated by exact Euclidean segment projection. The result retains segment identity, within-segment fraction and residual distance.

Tree path distances use a lowest-common-ancestor index. Paths between two edge projections include their fractional edge lengths; points on the same edge use their direct within-edge separation. Euclidean projection residuals are stored as uncertainty diagnostics and are **not added as invented neurites**.

Five focused tests pass on a known branching forest, interior-edge projections, same-edge distances, disconnected trees, cycles, missing parents and duplicate IDs. The complete real-cell batch passes **2,477 reference comparisons**, using independent sparse Dijkstra paths, brute-force searches over all segments for selected contact points, and shortest paths with independently inserted projected vertices. Largest errors are:

- node path versus Dijkstra: 1.876 × 10⁻¹² µm;
- nearest-segment residual versus brute force: 2.732 × 10⁻¹⁴ µm;
- projected-point path versus inserted-vertex graph: 1.507 × 10⁻¹² µm.

These establish numerical consistency for the declared geometry, not anatomical correctness of every nearest-segment assignment. The [frozen plan](../validation/male-apl-geometry-plan.json) pins sources, seed, reference counts and tolerances before execution. The [complete results](../validation/male-apl-geometry-results.json) and [9.62 MB geometry/attachment arrays](../validation/male-apl-geometry-arrays.npz) retain both cells together. The batch finished in 9.04 wall seconds, with no need for additional compute.

## Contact coverage and attachment uncertainty

The source is the previously verified raw-partner subset whose targets are the 4,064 KCs and two APL cells. Thus this audit covers **every retained incoming APL endpoint**, plus APL outgoing endpoints onto those selected targets. It does not cover APL outputs onto every other CNS cell. For incoming contacts it uses the APL postsynaptic coordinate; for outgoing contacts it uses the APL presynaptic coordinate. Both sources use the same native 8 nm space and release version.

All **439,226 endpoint records** remain represented. Repeated presynaptic locations are shared only for geometric computation: every polyadic partner row retains its original absolute source-row ordinal and inverse mapping. Counterpart identity, incoming/outgoing role and KC membership remain explicit. Missing counterpart IDs are encoded as −1, not silently joined to a modeled cell. The array has 140,331 right and 135,011 left distinct endpoint locations.

| Pathway | Contact rows | Distinct APL locations | Median residual | 95th percentile | Maximum |
|---|---:|---:|---:|---:|---:|
| KC → APL_R | 108,338 | 108,338 | 0.7310 µm | 1.5235 µm | 2.5788 µm |
| APL_R → KC | 95,542 | 15,674 | 0.6253 µm | 1.3486 µm | 2.2833 µm |
| KC → APL_L | 102,014 | 102,014 | 0.7242 µm | 1.5143 µm | 2.3675 µm |
| APL_L → KC | 100,658 | 16,661 | 0.6191 µm | 1.3472 µm | 2.4469 µm |

Residual quantiles are contact-row weighted. A frequently reused presynaptic release location therefore contributes once per retained partner, as the original contact accounting requires. No distance threshold filters the data. The 406,552 KC-related endpoint records all attach to their APL's main component.

The remaining records include incoming non-KC contacts and 22 outgoing contacts onto selected non-KC targets (the APL cells). **Two incoming right and three incoming left non-KC contacts** project onto small disconnected components. Those fragments cannot reach the main arbor under the current forest geometry. They are retained explicitly; this is a skeleton limitation, not proof that the biological contacts are functionally isolated.

## What this enables, and what remains unproven

The project now has a male-specific spatial index between actual input and output sites, rather than only ROI membership or Euclidean distance. It can support an explicit distributed-APL reference and anatomical sensitivity experiments without deleting contact multiplicity or silently connecting fragments.

Nearest projection does not prove that a contact belongs to that precise branch when coarse centerlines pass close together. Residuals on the scale of the neurite thickness, coarse radii and reconstruction status require attachment/geometry sensitivity before precise cable physiology. A missing branch must not be compensated by an arbitrary membrane or release gain. The source study's normalized backbone length also cannot be transferred unchanged to physical native path lengths without an explicit correspondence.

Next establish a bounded spatial operator using these forests, with constant-diameter and source-radius cases explicitly labeled as anatomical assumptions. Preserve the published reference's finite stimulation footprint, and verify spatial propagation and discretization before attempting a physiological fit. Keep voltage, calcium, local transmitter release and KC response as separate states/observations. Absolute APL membrane properties and the voltage-to-release law remain unidentified; a static attenuation result alone cannot select recurrent dynamics.

The CNS graph, neural engine, sensory encoder, motor decoder and body are unchanged. H1 remains experimental. The Eon embodied benchmark remains cancelled. This closes the initial APL-geometry acquisition/attachment prerequisite while leaving the complete single-male milestones active.
