"""Independently check public free-running array alignment without modifying data."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np
from scipy.interpolate import interp1d


SOURCE = Path("data/raw/freewalking/free_running_raw_combined_v1.h5")
EXPECTED_SHA256 = "369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e"
COMMIT = "d346fcc50bc67e41ef57f98a44c0f53bebb2ab8f"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def relative_error(predicted, observed):
    good = np.isfinite(predicted) & np.isfinite(observed)
    return float(np.linalg.norm(predicted[good] - observed[good]) /
                 max(np.linalg.norm(observed[good]), 1e-15))


def scalar_alignment(raw, target):
    good = np.isfinite(raw) & np.isfinite(target)
    x, y = raw[good], target[good]
    scale = float(x @ y / (x @ x))
    return scale, relative_error(raw * scale, target)


def main():
    assert digest(SOURCE) == EXPECTED_SHA256
    rows, duplicate_index = [], defaultdict(list)
    pcols, vcols = np.r_[:3, 7:93], np.r_[:3, 6:92]
    with h5py.File(SOURCE) as f:
        info = f["info"]
        names = [info["kp_names"][str(i)][()].decode() for i in range(50)]
        scut = names.index("Scutellum")
        bouts = sorted(k for k in f if k.startswith("bout_"))
        for i, name in enumerate(bouts):
            b = f[name]
            q, v = b["qpos"][:].astype(float), b["qvel"][:].astype(float)
            assert np.all(np.isfinite(q)) and np.all(np.isfinite(v))
            n = len(q)
            # Exact author's endpoint-preserving interpolation grid, which is
            # close to but not necessarily exactly 1000 samples per second.
            duration = (n - 1) / 800.0
            n_interp = int(duration * 1000.0) + 1
            t_native = np.linspace(0, duration, n)
            t_interp = np.linspace(0, duration, n_interp)
            interpolated = interp1d(t_native, q, kind="cubic", axis=0)(t_interp)
            predicted = np.diff(interpolated[:, pcols], axis=0)[:n] * 1000.0
            observed = v[:len(predicted), vcols]
            native_predicted = np.diff(q[:, pcols], axis=0) * 800.0
            raw = b["orig_keypoints"][:].astype(float)
            kp = b["kp_data"][:].astype(float).reshape(raw.shape)
            scale, scale_error = scalar_alignment(raw, kp)
            fid = info["fly_ids"][str(i)][()].decode()
            duplicate_index[(fid, n)].append(name)
            matched = bool(info["csv_matched"][str(i)][()])
            row = {"bout": name, "fly_id": fid, "frames": n,
                   "csv_matched": matched,
                   "qvel_native_800hz_relative_error": relative_error(native_predicted, v[:-1, vcols]),
                   "qvel_cropped_interpolation_relative_error": relative_error(predicted, observed),
                   "qvel_cropped_interpolation_max_abs_error": float(np.max(np.abs(predicted - observed))),
                   "tested_velocity_components": "root translation and all scalar joints; root quaternion angular velocities excluded",
                   "native_last_time_s": float(t_native[-1]),
                   "stored_velocity_last_interval_start_s": float(t_interp[n-1]),
                   "interpolated_actual_spacing_s": float(t_interp[1]),
                   "derivative_divisor_s": .001,
                   "raw_to_kp_fitted_scale": scale,
                   "raw_to_kp_scalar_fit_relative_error": scale_error}
            if matched:
                cn = int(info["csv__n_frames"][str(i)][()])
                start = int(info["csv__start_frame"][str(i)][()])
                end = int(info["csv__end_frame"][str(i)][()])
                z = raw[:, scut, 2] * .1
                zmin = float(info["csv__scut_z_min"][str(i)][()])
                zmax = float(info["csv__scut_z_max"][str(i)][()])
                row.update(csv_n_frames=cn, csv_start=start, csv_end_inclusive=end,
                           csv_n_minus_stored_n=cn-n,
                           csv_inclusive_range_equals_n=(end-start+1 == cn),
                           csv_duration_hz=cn/float(info["csv__duration_s"][str(i)][()]),
                           raw_mm_zmin_difference=float(np.min(z)-zmin),
                           raw_mm_zmax_difference=float(np.max(z)-zmax),
                           raw_mm_zmean_difference=float(np.mean(z)-float(info["csv__scut_z_mean"][str(i)][()])))
            rows.append(row)
        duplicates = []
        for (fid, n), names in duplicate_index.items():
            if len(names) < 2:
                continue
            matrix = []
            for raw_name in names:
                raw = f[raw_name+"/orig_keypoints"][:].astype(float)
                matrix.append([scalar_alignment(raw, f[target+"/kp_data"][:].astype(float).reshape(raw.shape))[1]
                               for target in names])
            duplicates.append({"fly_id": fid, "frames": n, "bouts": names,
                               "raw_to_kp_relative_error_matrix": matrix,
                               "own_pair_best_per_row": bool(np.all(np.argmin(matrix, axis=1) == np.arange(len(names))))})
    metrics = ["qvel_native_800hz_relative_error", "qvel_cropped_interpolation_relative_error",
               "qvel_cropped_interpolation_max_abs_error", "raw_to_kp_fitted_scale",
               "raw_to_kp_scalar_fit_relative_error"]
    summary = {key: dict(zip(["min", "median", "max"], np.percentile([r[key] for r in rows], [0, 50, 100]).tolist()))
               for key in metrics}
    summary.update(bouts=len(rows), flies=len({r["fly_id"] for r in rows}),
                   matched_csv=sum(r["csv_matched"] for r in rows),
                   duplicate_fly_length_groups=len(duplicates),
                   all_duplicate_own_pairs_best=all(r["own_pair_best_per_row"] for r in duplicates))
    report = {"source": str(SOURCE), "sha256": EXPECTED_SHA256, "source_code_commit": COMMIT,
              "method": "Independent NumPy/SciPy reconstruction, no author pipeline code executed or source arrays modified",
              "summary": summary, "duplicate_groups": duplicates, "bouts": rows,
              "claim_ceiling": "Timing mismatch numerically established; native source frame origin and exact metadata assignment not established from absent original CSV/preprocessing receipt. Fitted raw scale is a diagnostic, not a recovered author alignment transform."}
    Path("validation/freewalking-alignment.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
