# Free-running data: timing, coordinates and provenance

The public single-fly file contains useful kinematics, but **its saved `qpos`
and `qvel` rows are not time-aligned**. Native positions and cropped interpolated
velocities share an array length while referring to different times. The file
also combines raw tracking coordinates, size-normalized model coordinates and
different site definitions. It is a mixed-sex dataset with no per-fly sex labels
in the inspected HDF5.

This audit inspected author source at commit
[`d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f`](https://github.com/elliottabe/3d_tracking_dataset/tree/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f)
and independently reconstructed the arrays using NumPy/SciPy. It did not execute
the author pipeline, alter downloaded data, or export trajectories for control.

## Exact inspected release

- File: `data/raw/freewalking/free_running_raw_combined_v1.h5`.
- Bytes: 714,915,024.
- Observed SHA256: `369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e`.
  This is an observed checksum, not a separately published author checksum.
- 372 bouts, 22 distinct `fly_ids`; 371 `csv_matched=true` entries and one
  unmatched entry, `bout_346`.
- Typical arrays: `qpos (N,93)`, `qvel (N,92)`, `orig_keypoints (N,50,3)`.
  HDF5 metadata lists are groups keyed by numeric strings; sort these keys
  numerically, not lexicographically.

The independent check is reproducible with:

```sh
.venv/bin/python scripts/check_freewalking_alignment.py
```

[Its JSON report](../validation/freewalking-alignment.json) preserves all-bout
metrics, duplicate matching groups, exact timing grids and the source hash.

## Native positions versus interpolated velocities

The acquisition paper specifies 800 Hz cameras, and the author running-analysis
notebook uses `FPS=800`. In the pipeline, `postprocess_stac_data.py` retains
original `qpos`, `xpos`, `xquat` and `kp_data` under `_stac` names, then performs
cubic interpolation from 800 to nominally 1000 Hz. It computes `qvel` from that
interpolated trajectory.
[Paper, preprint DOI 10.64898/2026.05.03.722293](https://doi.org/10.64898/2026.05.03.722293),
[running notebook](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/notebooks/Scutellum_Height_Running.ipynb),
[postprocessor](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/scripts/postprocess_stac_data.py)

The non-interpolated branch in
[combine_data.py](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/scripts/combine_data.py)
restores the native `_stac` arrays while retaining other arrays, cropped to the
original length. Consequently, `qpos` becomes native again but `qvel` retains
the first `N` interpolated samples. Cropping is not resampling.

Independent reconstruction for **every one of 372 bouts** confirms that account:

1. Let `D=(N−1)/800`, `M=int(D*1000)+1`.
2. Cubically interpolate native `qpos` from `linspace(0,D,N)` onto
   `linspace(0,D,M)`, matching the author implementation.
3. Forward-difference the interpolated scalar coordinates and divide by 0.001 s.
4. Compare the first `N` results with the stored `qvel`.

For root translation plus all scalar joint velocities, the relative L2 errors
are **4.37×10⁻⁷ to 1.65×10⁻⁶**, median **6.83×10⁻⁷**. The maximum absolute
error across those checks is 0.000238 in the relevant velocity units. By
comparison, differentiating the native positions at 800 Hz disagrees with stored
velocities at relative errors **1.290–1.666**, median **1.464**. Root quaternion
angular velocity is excluded from this numerical comparison; the translational
and scalar-joint agreement already establishes the time-grid mismatch.

For `bout_000`, the final stored native position is at relative time **0.268750 s**.
The last stored velocity instead corresponds to an interpolated interval starting
at **0.215602 s**. Pairing row indices would create approximately 53 ms of drift
over this short bout.

There is a second, smaller numerical convention: the author's endpoint-preserving
`linspace` grid is not always spaced at exactly 0.001 s, but velocities are always
divided by 0.001 s. For `bout_000` its spacing is 0.0010027985 s. This should be
preserved when reproducing the export and corrected explicitly when deriving a
new physically timed trajectory.
[interpolation helper](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/utils/stac_data_utils.py),
[velocity helper](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/utils/mjx_preprocess.py)

`site_xpos` and `xpos_egocentric` are also computed on the interpolated,
floor-adjusted trajectory and are not restored from `_stac` arrays by the
non-interpolated exporter. The inspected source therefore places these on the
cropped interpolated grid too. That is a source-based conclusion; this audit
numerically reconstructed `qvel`, not a complete forward-kinematics replay of
every site. Equal leading dimensions do not establish temporal correspondence.

## One-frame metadata discrepancy remains unresolved

For all 371 matched entries:

```text
csv__n_frames = csv__end_frame − csv__start_frame + 1 = stored N + 1
csv__duration_s = csv__n_frames / 800
```

For example, `bout_000` stores 216 frames while its attached CSV describes
217 frames, inclusive range 12426–12642. This does **not** establish whether
the first frame, last frame, or another frame was omitted.

The inspected current preprocessor explicitly selects the inclusive range using
`end_frame+1`. Its velocity helper appends the final `qpos` before forward
differencing, preserving the number of samples. Neither operation explains a
dropped frame. Furthermore, the current exporter matches CSV rows only when
their `n_frames` equals `info.clip_lengths`, whereas these attached values differ
by one. Thus the current pinned source is not a complete reproduction receipt
for the exact released file; prior pipeline versions or upstream metadata edits
remain possible. Do not attribute the missing frame to differentiation without
additional evidence.
[preprocessor](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/scripts/preprocess_keypoints_for_ik.py),
[export loader](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/utils/free_running_loader.py)

For a native kinematic replay, `t_relative = arange(N)/800` is a supported
within-bout clock. Exact absolute video-frame IDs require the original CSV,
preprocessing file/frame map and release-generation revision. Keep attached CSV
start/end values as unverified provenance fields rather than assigning them to
individual samples.

## Identity matching and repeated-length ambiguity

The exporter groups CSV rows by `fly_id` and greedily takes the next unused row
with the requested frame count. It separately applies the same rule to
preprocessing `orig_keypoints`. It does not use an exact source path, original
bout index or start/end frame pair as a primary key. `csv_matched=true` means the
algorithm found a candidate; it is not independent verification of identity.

The HDF5 has **14 repeated `(fly_id, N)` groups**, each containing two bouts.
Our scalar raw-to-`kp_data` residual check favors the attached raw sequence over
the alternative sequence in every one of these groups; the weakest alternative
is still 184 times worse. This supports internal correspondence between the
attached raw and processed trajectories. It does not prove that the attached CSV
row has the exact original source-frame interval.

The original CSV files are not included in this inspected HDF5, and the export
does not retain their paths. Attached scutellum summary statistics are not exact
recomputations from the exported raw sequence: mean discrepancies occur in all
matched bouts, and extrema also differ for some. Different preprocessing or
selection is possible; the discrepancy alone does not establish a wrong match.
The report preserves these differences without replacing source metadata.

## Coordinate systems and units

| Field | Representation and conversion | Interpretation limit |
|---|---|---|
| `orig_keypoints` | Raw JARVIS coordinates; multiply by **0.1 to obtain mm** | Reordered into model keypoint order, before model size alignment; not the `qpos` coordinate scale |
| `kp_data` | Preprocessed, per-bout scaled IK targets; model lengths ×**10 → mm** | Model-normalized dimensions, with filtering/interpolation effects |
| `qpos[:, :3]` | Free-root position in model length units; ×**10 → mm** | Native trajectory, before the later floor correction retained by some other fields |
| `qpos[:, 3:7]` | Free-root quaternion in **w,x,y,z** order | Not angles and not four independent joint coordinates |
| `qpos[:, 7:]` | Named scalar joints, **radians** | Resolve by XML joint name, not an assumed target-model ordering |
| `qvel[:, :3]` | Model length units per second; ×**10 → mm/s** | Cropped interpolated grid; not aligned to native `qpos` |
| `qvel[:, 3:]` | Root angular velocity and scalar joint velocities, rad/s | Root gyro uses the author's quaternion convention; the scalar coordinates begin at column 6 |
| `marker_sites` | IK-fitted marker attachment positions in model units | Learned attachment offsets; not necessarily default XML sites |
| `site_xpos` | Default model tracking sites on the interpolated, floor-adjusted trajectory | Different time, floor and attachment conventions from native IK marker positions |
| `xpos_egocentric` | Model sites relative to thorax, rotated into its frame | Source computes `(site−thorax_position) @ thorax_rotation`; cropped interpolated grid |

Raw units are explicit in the author's
[Sandbox_Strict notebook](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/notebooks/Sandbox_Strict.ipynb):
`JARVIS_SCALE=10` and coordinates are divided by that value to obtain millimetres.
The running notebook explicitly multiplies model coordinates by 10 for
millimetres. The [model XML](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/models/fruitfly_v1/fruitfly_v1_free.xml)
uses radians and gravity −981, consistent with centimetre length units. A few
notebook comments call these coordinates “model metres”; that wording conflicts
with their explicit ×10 conversion and should not be used to apply ×1000.

The preprocessor fits a Procrustes size factor per bout and applies it uniformly
to coordinates. A single scalar least-squares diagnostic from `orig_keypoints`
to `kp_data` yields factors **0.011107–0.013251**, median **0.012041**. These are
not merely the raw-to-centimetre factor 0.01; they also normalize animal size to
the model. Corresponding scalar-fit relative errors range from 2.2×10⁻⁸ to
0.00744, consistent with additional preprocessing differences. These fitted
numbers are diagnostics, not recovered author transformation parameters.

The preprocessing `alignment_info` contains the intended scale/transform, but
the raw exporter does not preserve it. The combined `info.offsets` is also a
single global object: the concatenate helper retains the first file's
non-concatenated metadata. If different source files had different learned marker
offsets, that one object cannot reconstruct every file's fitted attachments.
Use per-source preprocessing/IK outputs to establish those transforms rather
than assuming a universal offset.

## Sex, assay and safe downstream use

The paper describes male and female single-fly running experiments, with
13 males and 9 females in the tracked population. Its running analysis reports
22 flies and 372 bouts, matching this file's inventory. No inspected HDF5 field
maps a particular `fly_id` to sex. `sex_id.py` is a heuristic for **paired
courtship**, using relative song production with a body-length fallback; it
provides no ground truth sex labels for these solitary running bouts.
[paper](https://doi.org/10.64898/2026.05.03.722293),
[sex heuristic](https://github.com/elliottabe/3d_tracking_dataset/blob/d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f/utils/sex_id.py)

Usable bounded next work is a clearly labelled mixed-sex kinematic reference:
native `qpos` with an 800 Hz relative clock, resolved joint names, explicit
centimetre-to-target conversion, and newly derived velocities from that same
trajectory. Recompute target-model site positions on that same clock. For a
forward-difference derivative, retain `N−1` valid intervals or explicitly mark an
endpoint convention; do not silently treat an invented last velocity as measured.
The released arrays remain unchanged for reproducibility.

Do not call this a male-specific calibration, pair the stored `qpos/qvel` rows,
transfer model-scaled coordinates as raw measured body size, or infer exact video
frame origins from the one-frame discrepancy. These restrictions follow from
observed source/data inconsistencies, not from absence of useful kinematic data.
