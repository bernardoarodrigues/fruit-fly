# Visual input: released columns and missing optical registration

The physical body produces camera-derived compound-eye samples. Those samples
are **not yet neural input**. The released male annotations contain useful
optic-lobe columns, but matching their integers to camera-facet indices would
invent retinal directions, handedness and coverage.

## Executed full-graph audit

Run `.venv/bin/python scripts/audit_visual_columns.py` to reproduce
[the saved audit](../validation/visual-column-audit.json). It verifies the complete
MaleCNS import, records all array/annotation hashes, and uses integer contact
counts rather than the simulator's assumed signed weights. Every retained
photoreceptor stays in the graph, including unresolved cells.

| Population | Left cells / assigned columns | Right cells / assigned columns |
|---|---:|---:|
| L1 | 884 / 875 | 892 / 892 |
| L2 | 886 / 874 | 893 / 892 |
| L3 | 880 / 0 | 892 / 892 |
| Mi1 | 886 / 875 | 887 / 886 |
| R1–R6 | 1,112 / 0 | 2,265 / 0 |

“Assigned columns” counts unique finite `assignedOlHex1/assignedOlHex2` pairs.
It is not the count of covered visual angles. Some cells share an assigned
column. All retained R1–R6, R7 and R8 photoreceptors lack these column labels;
their consensus transmitter is histamine.

An exploratory rule assigns an R1–R6 cell only when its same-side L1 and L2
targets independently satisfy these numerical conditions: at least ten contacts
to labeled targets; a unique leading column holding at least 90% of those
contacts; and agreement between the leading L1 and L2 columns. Thresholds are
analyst choices, not experimentally established classification cutoffs.

| Side | Accepted R1–R6 cells | Unresolved | Covered columns |
|---|---:|---:|---:|
| Left | 1,064 | 48 | 286 |
| Right | 2,053 | 212 | 486 |

Every cell's evidence and unresolved result are preserved. Coverage is uneven
and incomplete; some columns receive more than six accepted cells. The audit
does not force a six-cell count, invent missing photoreceptors, assign R7/R8,
or reverse the assumed histamine sign. Because the released column annotations
are themselves connectivity-informed, L1/L2 agreement is **not independent
retinal ground truth**. Further anatomical/optical registration is required.

## What the current eye actually measures

The pinned FlyGym implementation uses a 512×450 rectilinear image, a specified
fisheye resampling, and 721 facet masks per eye. Each facet averages **one**
selected RGB channel: green for its bundled yellow label or blue for its pale
label. Its other output channel remains zero. Thus an array shaped `721×2` is
not two independently measured spectral signals per facet. The bundled labels
are not the male connectome's identified R7/R8 mosaic; RGB rendering does not
measure Rh1 photon catch or ultraviolet sensitivity.

Camera calibration must recover actual rays through the renderer and resampling
operation. Anatomical registration must then relate these directions to the
released column lattice with correct eye/axis conventions and a declared domain.
Only after that can irradiance/contrast be connected to photoreceptor voltage
and histaminergic graded release. The separate [mixed backend](graded-model.md)
can represent continuous transmission, but currently supplies no visual
phototransduction parameters.

## Primary-source constraints and alternatives

[Nern et al. (2025)](https://www.nature.com/articles/s41586-025-08746-0)
provides a right male optic-lobe inventory and column assignments for fifteen
columnar types. Eye-equator features help orient its lattice. Its
[author code](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code)
is the next source for checking coordinate conventions. A column coordinate
alone does not specify a ray in our body camera.

[Lappalainen et al. (2024)](https://www.nature.com/articles/s41586-024-07939-3)
uses 45,669 model neurons, 64 types and 721 central columns with trained graded
dynamics. Its tiled consensus circuit and fitted parameters are useful model
references, but are not a ready registration or validated parameter transfer
for our individual full MaleCNS graph.

[Eye structure shapes neuron function (2025)](https://www.nature.com/articles/s41586-025-09276-5)
relates anatomical visual coordinates to nonuniform acuity and spherical motion
directions. This motivates checking angular geometry rather than assuming a
constant angle per column everywhere. Its specimen and coordinate construction
must be reconciled with our male annotations before transfer.

The September 1, 2026 [orientation-map preprint](https://arxiv.org/html/2609.01330v1)
instead injects synthetic Poisson input into L1–L3, bypassing unmapped
photoreceptors. Its displayed equations use an additive effective-voltage
synaptic variable without a reversal-potential term, despite the text's
conductance terminology. It increases synaptic scale to obtain sufficient
medulla activity, uses imposed spatial rates, and reports little T4/T5 response
to static stimuli. These choices make it an exploratory central-circuit assay,
not a calibrated peripheral visual encoder. Its
[code](https://github.com/JNLiew/flylif_orientation_maps) has not yet been audited
here; no parameter or claimed synapse count was imported from it.

## Next bounded experiment

Calibrate the existing camera/retina against known directions without touching
the neural graph. Preserve each facet's angular support, source-pixel weights,
out-of-image fraction, pose transform and optical asset hashes. Verify with
rendered targets independently of the algebraic projection. In parallel, audit
the author's anatomical registration data. A future adapter must explicitly
reject unresolved mappings and distinguish measured anatomy, transferred
optics and fitted physiology; it must not fill missing directions by index.
