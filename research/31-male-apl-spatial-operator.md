# Static spatial propagation on male APL forests

Completed 2026-09-05 UTC. The complete **36-probe anatomical batch** passes its frozen numerical checks. It implements the exponential path-distance reference from [Amin et al. 2020, Connectome analysis, Eqs. 1–3](https://elifesciences.org/articles/56954), independently of the neural runtime. This is a static input-to-output coupling calculation, not a fitted physiological model or a recurrent simulation.

## Calculation and declared inputs

The [operator](../scripts/apl_spatial_operator.py) evaluates

`u(i) = sum_j mass(j) exp(-distance(i,j) / scale)`.

The constant-diameter reference uses physical path length in µm. The source-radius reference integrates `dl / sqrt(r)` along each linearly tapered edge. Its exact segment integral is `2 L / (sqrt(r_child) + sqrt(r_parent))`; this expression remains stable for equal or nearly equal radii. We set `scale = lambda * total_electrotonic_length / total_physical_length`, following the source's normalization relation, but using the **whole native male forest**. That differs from the author's hemibrain/MB-restricted geometry. The declared 25, 50 and 75 µm length parameters are sensitivity references, not male physiological estimates.

All retained contact projections are inserted as vertices on their original edges. Linear taper and path lengths are preserved. Coincident points share a geometric node while retaining every contact's weight and partner identity. No artificial connection bridges a disconnected component.

Two tree traversals compute the exponential sum in linear time per input column. A postorder traversal accumulates each subtree's attenuated input. A preorder traversal adds the contribution from the rest of its component, using an algebraically equivalent expression with `expm1` to reduce cancellation. This implements the paper's pairwise attenuation model; it does **not** enforce physical branch-current conservation or supply voltage, calcium, release or membrane time dynamics.

Each source footprint uses all KC→APL contacts with a literal ipsilateral CA, gL or aL ROI label. Every selected contact receives equal mass, with total input one per footprint. These broad regional probes are not an ATP puff, natural odor ensemble or measured KC spike train. They do not replicate the published finite dye footprint.

| Cell | CA input contacts | gL input contacts | aL input contacts | APL→KC output contacts / distinct sites |
|---|---:|---:|---:|---:|
| APL_R, 10540 | 14,728 | 32,786 | 13,350 | 95,542 / 15,674 |
| APL_L, 10977 | 12,574 | 27,548 | 11,389 | 100,658 / 16,661 |

The frozen factorial is two cells × two path metrics × three length parameters × three footprints. Both cells completed before the results were interpreted. Source files, code and geometry are pinned in the [plan](../validation/apl-spatial-operator-plan.json), SHA-256 `2b24d9773aa2c4e89d4c3811ad51470666647511b5cb7e1973dd574e102fa0ef`.

## Numerical evidence

Six focused tests pass, comparing taper integrals with independent quadrature and full pairwise shortest-path kernels on small branched/disconnected examples. Tests include repeated contacts, zero-length edges and infinite attenuation scale.

The real-cell [benchmark](../scripts/benchmark_apl_spatial_operator.py) passes 294 reference checks in 13.92 seconds. It independently computes sparse shortest paths from eight fixed-seed output sites per cell and directly sums all input masses for each metric/length/footprint. Maximum absolute difference from tree propagation is **3.28 × 10⁻¹⁵**. With infinite scale, the operator returns each component's total source mass, with maximum difference **7.79 × 10⁻¹³**; disconnected fragments receive no source contribution.

Contact insertion expands the right/left forests to 154,911/151,764 nodes. Splitting every expanded segment at its midpoint increases these to 309,819/303,526. At the predeclared 50 µm parameter, both metrics and all three footprints agree at every pre-existing node to **1.84 × 10⁻¹⁵** absolute error. Physical and tapered metric totals remain within the frozen 10⁻⁸ tolerance. Output fields remain finite, nonnegative and no larger than the unit total input within the 10⁻¹⁰ response tolerance.

The [complete results](../validation/apl-spatial-operator-results.json) retain every case, and the [8.41 MB array artifact](../validation/apl-spatial-operator-arrays.npz) preserves the expanded forests, contact maps, source selections and output fields. SHA-256: `bbbaf0a61bcf3be7d3fec7b328aecf2bd87aa8813cea16982aa7586ee7f5c78e`. A separate post-completion reduction from these saved arrays reproduced all **216 mean/quantile scalar values** within 10⁻¹⁴ and checked that coupling at every saved output increases monotonically with the length parameter. This reduction checks serialization/summaries, not independent biological validity.

## Combined findings

At the 50 µm reference, mean output coupling weighted by retained synaptic contacts is:

| Cell | Input region | Constant diameter | Coarse source radii | Relative increase |
|---|---|---:|---:|---:|
| APL_R | CA | 0.03190 | 0.03953 | 23.93% |
| APL_R | gL | 0.07585 | 0.09532 | 25.66% |
| APL_R | aL | 0.06329 | 0.08154 | 28.85% |
| APL_L | CA | 0.02450 | 0.02873 | 17.30% |
| APL_L | gL | 0.06841 | 0.08074 | 18.03% |
| APL_L | aL | 0.04396 | 0.05623 | 27.90% |

Across all paired cases, the radius variant increases this mean by **15.72–32.34%**. This is conditional on the specified global normalization and coarse radius field; it is not a measured physiological increase or proof that every individual connection becomes stronger. The [geometry audit](30-male-apl-skeleton-geometry.md) documents the large number of nodes at the radius floor.

Averaging once per distinct output site instead of once per contact changes case means by **−12.52% to +31.89%** relative to the contact-weighted value. Geometric deduplication therefore cannot silently substitute for synaptic accounting. The result also depends on input region despite equal total drive, so a single pooled APL scalar discards spatial structure under this model. These are model-derived findings, not new experimental observations. Both cells are from one male reconstruction, not independent biological replicates.

## Next boundary

The static operator now has a verified reference implementation. Its discretization consistency does not validate nearest-branch attachment, missing fragments, coarse radii, or the transferred attenuation law. Attachment uncertainty remains untested; a finer sampling of the same chosen edges cannot resolve it.

Before physiological fitting or recurrent integration, retain an explicit distinction between input drive, spatial spread, membrane/calcium time dynamics, local GABA release and the measured KC response. The published normalized calcium/inhibition profiles do not identify all of those mappings. A bounded graded candidate must declare unsupported parameters and separate source-compatible calibration from untouched evaluation; an attractive static field is not a promotion criterion.

Performance also remains an integration constraint: this Python implementation takes roughly 0.3 seconds per cell for three footprints. Linear complexity makes the static reference practical, but that measurement does not establish suitability for the neural engine's 0.1 ms step. Any optimized or reduced runtime implementation must be checked against this reference, including contact multiplicity and spatial sensitivity.

No neural, sensory, decoder or body default changed. H1 remains experimental, the Eon embodied benchmark remains cancelled, and the single-male milestones remain incomplete.
