# Measured grooming trajectories and male free-walking data

Audited 2026-09-05. Two small public grooming source files were acquired and checksum-verified. Three numeric snippets are available under `data/grooming/`, preserving measured source angles and timing. **They are female, tethered, inverse-kinematics-derived trajectories; no male grooming motor controller or physics replay has been validated.** The newer free-walking study's single-fly HDF5 was subsequently acquired; individual sex labels and exact source-frame alignment remain unresolved.

## The 2026 grooming source

Özdil et al., [*Centralized brain networks controlling antennal grooming coordination*](https://doi.org/10.1038/s41467-026-72152-x), Nature Communications, 2026-04-23. The [Europe PMC full-text XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13314972/fullTextXML) was read successfully. Local XML: `tmp/grooming-audit/grooming.xml`, SHA-256 `78597b8078b4b67aa8940b14f041359c9e1e2935e7700a330a1d94f17d119cf4`.

All experimental animals were female, 3–5 days after eclosion. Five synchronized cameras recorded at 100 fps. The analysis reconstructs 3D positions and estimates head, antennal, and foreleg angles. Unilateral and bilateral grooming coordinate these parts differently. This is evidence for measured coordination, not a male motor calibration. The paper's network combines female FlyWire brain connectivity and male MANC correspondence, and its trained model predicts head/antennal variables rather than all foreleg motor commands. [Primary article, Methods](https://doi.org/10.1038/s41467-026-72152-x)

The [author analysis repository](https://github.com/NeLy-EPFL/antennal-grooming) was pinned at **`65787ac7fa35aa5520addb6d3e4ac27887bbaf60`**. It uses [Apache-2.0](https://github.com/NeLy-EPFL/antennal-grooming/blob/65787ac7fa35aa5520addb6d3e4ac27887bbaf60/LICENSE). Its notebooks contain figure analysis; they reference separate [kinematics3d](https://github.com/NeLy-EPFL/kinematics3d), [SeqIKPy](https://nely-epfl.github.io/sequential-inverse-kinematics), FARMS, and FlyVis tools. A runnable, pinned FARMS grooming replay configuration was not found among the audited repository files. Installing the figure-analysis dependencies alone does not reproduce the biomechanics.

## Actual acquired data and provenance

The [public dataset](https://doi.org/10.7910/DVN/N8ITTG), *Replication Data for All Figures*, is **V1.0, published 2025-01-09**, with a **CC0-1.0** dedication. This predates the final article; it is the dataset linked by the current author download script, not a claim that every final figure was regenerated from this snapshot.

Harvard's API returned HTTP 403 to command-line requests here, while its public web page opened without login. Downloading through the normal public page supplied an S3 file URL, which was fetched and matched against the MD5 shown on the file page. No institutional login was needed. Durable provenance uses the public file IDs below; temporary download URLs are not retained.

| Source file | Public file page / API ID | Bytes | Verified MD5 |
|---|---|---:|---|
| `Fig1_panelC.pkl` | [10810237](https://dataverse.harvard.edu/file.xhtml?fileId=10810237&version=1.0) | 3,494,410 | `d1a737c166123ba8731ccb6e5ff0b2d5` |
| `Fig1_panelF-G.pkl` | [10810262](https://dataverse.harvard.edu/file.xhtml?fileId=10810262&version=1.0) | 383,577 | `ff686a720654bd7c5b461ab36b5946c4` |

The files are stored in ignored `data/raw/grooming/`. Their SHA-256 hashes, source identities, transformations, and output hashes are in [provenance.json](../data/grooming/provenance.json). The official download endpoints are `https://dataverse.harvard.edu/api/access/datafile/10810237` and `https://dataverse.harvard.edu/api/access/datafile/10810262`.

`Fig1_panelC.pkl` contains one 6000-row, 60 s recording: Date `220809`, Fly `3`, Trial `1`, genotype `aJO-GAL4xUAS-CsChr`. Each row has 74 fields including 21 angles, 3D poses, stimulus, frame ID, and time. The 21 angles comprise seven degrees of freedom for each foreleg, three head rotations, and pitch/yaw for each antenna.

`Fig1_panelF-G.pkl` contains two author-named dataframes from Date `220713`, Fly `1`, Trial `2`. Those names are **example containers, not per-frame behavioral classifications**. In particular, the six-second bilateral container includes pre/post-grooming periods and visibly non-bilateral motion. Its later foreleg estimates also include abrupt excursions and a run at an IK boundary. No automatic cleanup was applied.

| Numeric output | Source selection | Samples / source times | What the label means |
|---|---|---|---|
| [figure1c_2to5s.npz](../data/grooming/figure1c_2to5s.npz) | Figure 1C source, `2 <= Time < 5` | 300; 2.00–4.99 s | The interval displayed by the author notebook; no subtype label assigned |
| [unilateral_left.npz](../data/grooming/unilateral_left.npz) | Complete author `unilateral_left` container | 51; 49.39–49.89 s | Author-selected half-second example |
| [bilateral.npz](../data/grooming/bilateral.npz) | Complete author `bilateral` container | 600; 2.00–7.99 s | Mixed temporal context around the illustrated example |

For Figure 1F's especially short illustrated paths, the author notebook specifically selects source frames **4961–4976** for unilateral-left and **270–285** for bilateral. Those 16-frame windows are already contained in the exported examples. They are too short to establish a sustained grooming controller.

Regenerate the numeric files from the two acquired sources:

```sh
.venv/bin/python scripts/curate_grooming_data.py
```

The [curation script](../scripts/curate_grooming_data.py) checks exact source hashes before using a restricted legacy pandas unpickler. It writes ordinary numeric/string NumPy arrays; future adapters can load them using `np.load(path, allow_pickle=False)`. Each file includes `joint_names`, `angles_deg`, `angles_rad`, `time_source_s`, `time_relative_s`, `frame`, and `stimulus`.

The checks actually performed were: contiguous 0.01 s samples, exactly 21 angle channels, finite values, and lossless numeric roundtrip. [The saved plot](../validation/grooming-curated-data.png) was visually inspected. These checks establish a reproducible data conversion. They do not establish marker accuracy, physical feasibility, correct body-joint mapping, or stable free-standing replay.

## Replay fidelity and body compatibility

The published biomechanical replay actively drove **14 foreleg joints plus head roll/pitch**. Antennae were passive spring-damper joints with behavior-dependent rest poses and empirically tuned stiffness/damping. It therefore did **not** replay all measured antennal angles as active motor outputs. The reported implementation used MuJoCo 2.3.7, a 0.1 ms timestep, roughly five-second snippets, Euler integration, PGS, and restricted foreleg/head collision detection. Its high solver-iteration cap and simplified collision scope are experiment settings, not validated settings for the current whole-body runtime. [Primary article, kinematic-replay Methods](https://doi.org/10.1038/s41467-026-72152-x)

The source variables describe these anatomical joints:

| Source suffix | Anatomical meaning | Candidate physical target; requires validation |
|---|---|---|
| `ThC_pitch/roll/yaw` | Thorax–coxa rotation | Corresponding foreleg coxa axes |
| `CTr_pitch/roll` | Coxa–trochanter/femur rotation in the reduced model | Corresponding femur axes |
| `FTi_pitch` | Femur–tibia rotation | Tibia pitch |
| `TiTa_pitch` | Tibia–tarsus rotation | Proximal tarsal pitch |
| `head_pitch/roll/yaw` | Neck rotation | Head axes, currently outside the walking actuator set |
| `antenna_pitch/yaw_L/R` | Measured antennal rotation | Cannot equate automatically with individual pedicel/funiculus joints |

This is an anatomical correspondence table, **not a verified numeric actuator map**. Source data were retargeted to NeuroMechFly segment proportions. Their zero poses, local axes, degree signs, joint limits, and model version must be compared with the current body. The plotting notebooks negate some head/antenna variables for presentation; those display operations were deliberately not applied to the exported data. No mirrored right-grooming trace was invented from the left example.

A credible next replay milestone is one finite, source-timed snippet in a separate test harness, initially with the author's tethered condition. Measure joint tracking error and head/leg contacts; then establish stable support by the other four legs before attempting free-standing replay. Any transition/blending controller, passive antennal parameters, trial selection, or amplitude limiting must be labeled as an engineering addition. The scientific endpoint is physical contact and coordinated kinematics; playing angles or attaching a “grooming” label alone is insufficient.

## Grooming descending-neuron identity

The local MaleCNS table was checked directly. Its exact type/synonym crosswalk is:

| Published name | MaleCNS type | Left / right body IDs | Annotation evidence |
|---|---|---|---|
| Hampel 2015 aDN1 | `DNg62` | **13624 / 15148** | `synonyms="Hampel 2015: aDN1"` |
| Hampel 2015 aDN2 | `DNge078` | **14537 / 36541** | `synonyms="Hampel 2015: aDN2"` |

These rows are marked `Prelim Roughly traced`. `rootSide` is missing; left/right is supported by `somaSide` and `instance`, so a selector must use that fallback. `AOTU103m` instead carries the unrelated Lee/Rideout/Nojima `aDN` synonym and must not be selected by a blanket substring match. None of these identities supplies a measured spike-to-joint trajectory mapping by itself.

## Male/female freely behaving data: useful next source

Ispizua, Abe et al., [*Whole-body 3D kinematics of freely behaving Drosophila*](https://doi.org/10.64898/2026.05.03.722293), is available as the [author-hosted PDF](https://faculty.washington.edu/tuthill/docs/3D_freewalking_2026%20final.pdf). It reports 800 Hz, 50-keypoint tracking, with 13 males and 9 females in the single-animal dataset and 11 male/female pairs for social recordings. Single-fly animals were 3–5 days old. The pipeline retargets tracking to a MuJoCo body using STAC; inverse kinematics and numerically inferred velocities are not direct force measurements. This is a stronger candidate for male terrestrial motor calibration than relabeling female grooming. [Primary preprint](https://doi.org/10.64898/2026.05.03.722293)

The local PDF is `tmp/grooming-audit/freewalking-paper.pdf`, 38,482,161 bytes, SHA-256 `b76e6b824a702c507b9fb94af83ee7136517c7b13da654677564de37896c6095`.

The [analysis repository](https://github.com/elliottabe/3d_tracking_dataset) was pinned at **`d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f`**. Its `pyproject.toml` declares **BSD-3-Clause**; no root `LICENSE` file was present in the inspected tree and GitHub's license field was null. The package declaration should not be erased by that detector result. Submodules and vendored models have their own provenance. No code from this pipeline was imported into the fly runtime.

The PDF's dataset hyperlink resolves to the [public curated Drive folder](https://drive.google.com/drive/folders/1flBiyFmJYWPA6EIN4Xoh_2Lc5VT2_AoV). Public listing metadata showed:

| Public file | Drive file ID | Listed bytes |
|---|---|---:|
| `free_running_raw_combined_v1.h5` | `1EktWQq4ZPAtuzhIlwvSGRNSa9WCQTLW7` | 714,915,024 |
| `courtship_raw_combined_v1.h5` | `1qeUVSdD9b_S0DChIFGtGWBFptR-5fmYs` | 716,629,687 |

The initial range probe returned Google's large-file notice. Following the provider's normal public confirmation form subsequently obtained the full single-fly file: 714,915,024 bytes, SHA256 `369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e`. The observed checksum records the acquired bytes; no independent published checksum was available. The courtship file was not downloaded. [Acquisition script](../scripts/acquire_freewalking.py) and the ignored source receipt retain durable file identity without temporary confirmation parameters.

Actual inventory: 372 filtered bouts from 22 unique recording IDs, containing 93-component model `qpos`, 92-component `qvel`, original and retargeted 50-keypoint arrays, and metadata. No individual sex field is present. The author's `sex_id.py` is a song/body-length heuristic for paired courtship, not a ground-truth sex map for these single-fly recordings. Do not assign a small body or a date-coded recording as male by assumption. An explicit data license was not found in the inspected folder/repository text; keep that separate from the code's declared BSD license.

The 371 matched CSV records each contain one more source frame than their stored arrays; one bout lacks matched CSV metadata. The currently pinned export pipeline does not explain that discrepancy simply as derivative truncation. A separate alignment audit is in progress. [Inventory script](../scripts/audit_freewalking.py) records shapes, finiteness and metadata before any trajectory is mapped into the simulator.

The next gate is an explicit per-recording sex map, source-frame alignment and body-model/unit audit before exporting a male calibration bout. Acquisition alone has not integrated or validated male joint trajectories.
