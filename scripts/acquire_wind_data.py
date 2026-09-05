#!/usr/bin/env python3
"""Inspect/extract Suver 2019 primary wind data and fit paired antenna curves.

Run from the repository root. Optional archive dependency: py7zr==1.1.3.
Metadata access needs only stdlib. Fitting needs existing numpy/scipy.
No full archive download or synthetic fallback is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RAW = ROOT / "data/raw/wind"
DOI = "10.5061/dryad.k06kh8f"
DATASET_API = "https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.k06kh8f"
FILE_API = "https://datadryad.org/api/v2/files/82268"
SIZE = 9477291049
MD5 = "e1ff6c0c61077b7777ccd83395f92477"
TARGETS = ("all_anterior.mat", "Anemometer_2018_03_23.mat", "antTracking_2017_01_05_E1.mat")


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def digest(path, algorithm="sha256"):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def metadata():
    receipt = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for name, url in (("dataset", DATASET_API), ("file", FILE_API)):
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = response.read(1024 * 1024)
        value = json.loads(payload)
        save(RAW / f"{name}-metadata.json", value)
        receipt["sources"][name] = {"url": url, "sha256": digest(RAW / f"{name}-metadata.json")}
    save(RAW / "metadata-receipt.json", receipt)
    return receipt


def remote_reader(url, size, budget):
    from fruitfly.morphology import RangeReader

    class BudgetReader(RangeReader):
        def read(self, size=-1):
            requested = self.size - self.position if size < 0 else min(size, self.size - self.position)
            if self.bytes_received + max(0, requested) > budget:
                raise ValueError("HTTP byte budget exceeded; no whole-file fallback is allowed")
            return super().read(size)

    return BudgetReader(url, size)


def archive_index(archive):
    # py7zr 1.1.3 archiveinfo() requires a filesystem name even for HTTP-backed
    # streams. These two private fields are isolated here and version-pinned.
    import py7zr
    if py7zr.__version__ != "1.1.3":
        raise RuntimeError("Archive inspection requires py7zr==1.1.3")
    files = archive.list()
    found = {}
    for target in TARGETS:
        matches = [entry for entry in files if PurePosixPath(entry.filename).name == target]
        if len(matches) != 1:
            raise ValueError(f"Expected one unambiguous archive member for {target}, found {len(matches)}")
        entry = matches[0]
        name = PurePosixPath(entry.filename)
        if name.is_absolute() or ".." in name.parts or "\\" in entry.filename:
            raise ValueError("Unsafe archive member path")
        if not entry.is_file or entry.is_symlink or entry.uncompressed > 2 * 1024**3:
            raise ValueError("Selected member is not a regular file within the 2 GiB limit")
        found[target] = {"archive_path": entry.filename, "bytes": entry.uncompressed,
                         "compressed_bytes": entry.compressed, "crc32": entry.crc32}
    return {"py7zr_version": py7zr.__version__, "solid": archive._is_solid(),
            "blocks": len(archive.header.main_streams.unpackinfo.folders),
            "total_members": len(files), "selected_members": found}


def inspect_archive(path=None, url=None, size=SIZE, budget=16 * 1024**2):
    import py7zr
    if url:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or parts.username or parts.password:
            raise ValueError("Expected an HTTP(S) URL without embedded credentials")
        # Signed query parameters may be necessary for transfer but never belong
        # in a provenance receipt. Local archives are preferred for private URLs.
        source_label = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    else:
        source_label = str(Path(path).resolve())
    reader = remote_reader(url, size, budget) if url else None
    with py7zr.SevenZipFile(reader if reader else Path(path), "r") as archive:
        result = archive_index(archive)
    result.update({"source": source_label,
                   "bytes_transferred": reader.bytes_received if reader else 0})
    save(RAW / "archive-index.json", result)
    return result


def extract_archive(path, output=RAW):
    import py7zr
    path, output = Path(path), Path(output)
    # Verify the published archive before trusting extracted primary data.
    if path.stat().st_size != SIZE or digest(path, "md5") != MD5:
        raise ValueError("Archive does not match the Dryad file size and published MD5")
    archive_sha = digest(path)
    output.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(path, "r") as archive:
        index = archive_index(archive)
        with tempfile.TemporaryDirectory(prefix="wind-selected-", dir=output) as temporary:
            archive.extract(path=temporary, targets=[r["archive_path"] for r in index["selected_members"].values()])
            for target, info in index["selected_members"].items():
                source = Path(temporary) / info["archive_path"]
                if source.is_symlink() or source.stat().st_size != info["bytes"]:
                    raise ValueError("Extracted member does not match archive metadata")
                info["sha256"] = digest(source)
                info["local_path"] = str((output / target).resolve())
                source.replace(output / target)
    receipt = {"dataset_doi": DOI, "license": "CC0-1.0", "archive_bytes": SIZE,
               "archive_md5": MD5, "archive_sha256": archive_sha, **index}
    save(output / "extraction-receipt.json", receipt)
    return receipt


def mat_summary(directory):
    """Describe actual MAT fields; do not infer absent calibration units."""
    import numpy as np
    from scipy.io import loadmat

    def describe(value):
        if isinstance(value, dict):
            return {key: describe(item) for key, item in value.items() if not key.startswith("__")}
        arr = np.asarray(value)
        result = {"shape": list(arr.shape), "dtype": str(arr.dtype)}
        if np.issubdtype(arr.dtype, np.number) and arr.size:
            finite = arr[np.isfinite(arr)]
            result.update({"finite_values": int(finite.size), "minimum": float(finite.min()) if finite.size else None,
                           "maximum": float(finite.max()) if finite.size else None})
        return result

    return {name: {"sha256": digest(Path(directory) / name),
                   "fields": describe(loadmat(Path(directory) / name, simplify_cells=True))} for name in TARGETS}


def anemometer_summary(directory):
    """Recompute an explicit steady-state window from saved calibrated traces.

    The author's MakeTracePairFigure selects MATLAB rows 2,4,6,8,10 and
    labels the already converted avgVmTrace values in cm/s. We do not apply
    the unrelated original-voltage avgVm baseline or spike-rate fields.
    """
    import numpy as np
    from scipy.io import loadmat
    source = loadmat(Path(directory) / TARGETS[1], simplify_cells=True)["traces"]
    frequency = float(source["samplerate"]) / float(source["DSAMP"])
    rows = [1, 3, 5, 7, 9]
    traces = np.asarray(list(source["indvVmTrace"]), dtype=float)[:, rows, :]
    average = np.asarray(source["avgVmTrace"], dtype=float)[rows, :]
    if traces.shape != (6, 5, 10000) or frequency != 1000:
        raise ValueError("Unexpected anemometer schema")
    if not np.allclose(traces.mean(axis=0), average, atol=1e-8):
        raise ValueError("Individual probe traces do not reproduce saved averages")
    end = round((float(source["preStim"]) + float(source["stimOn"])) * frequency)
    start = end - round(frequency)
    steady = traces[:, :, start:end].mean(axis=2)
    mount_means = steady.mean(axis=1)
    return {"units": "cm/s", "calibration": "Values already converted in deposited MAT; source plotting labels cm/s",
            "sample_rate_hz_after_DSAMP": frequency, "matlab_rows": [2, 4, 6, 8, 10],
            "analysis_window_s_from_trial_start": [start / frequency, end / frequency],
            "analysis_window_description": "Our explicit final 1 s of 4 s wind; publication's exact averaging window not recovered",
            "per_mount_per_direction_cm_s": steady.tolist(), "direction_means_cm_s": steady.mean(axis=0).tolist(),
            "mount_means_cm_s": mount_means.tolist(), "mean_cm_s": float(mount_means.mean()),
            "sd_across_six_mount_means_cm_s": float(mount_means.std(ddof=1)),
            "paper_nominal_cm_s": 59.57, "paper_reported_sd_cm_s": 1.4,
            "difference_from_paper_nominal_cm_s": float(mount_means.mean() - 59.57),
            "paper_nominal_exactly_reproduced": False}


def fit(directory, destination=ROOT / "data/wind-calibration.json"):
    """Fit actual per-fly paired measurements only, preserving sampling limits.

    Published plotting code fixes five columns at -90,-45,0,45,90 degrees.
    Schema checks fail closed until the real MAT data have been inspected.
    Fitting does not validate a MaleCNS input mapping or velocity scaling.
    """
    import numpy as np
    from scipy.io import loadmat

    directory = Path(directory)
    summary = mat_summary(directory)  # All three requested primary files required.
    receipt = json.loads((directory / "extraction-receipt.json").read_text())
    if receipt.get("archive_md5") != MD5 or receipt.get("archive_bytes") != SIZE:
        raise ValueError("Missing verified primary archive provenance")
    for name in TARGETS:
        if receipt["selected_members"][name]["sha256"] != summary[name]["sha256"]:
            raise ValueError(f"Extracted primary measurement hash changed: {name}")
    traces = loadmat(directory / TARGETS[0], simplify_cells=True)["traces"]
    left = np.asarray(traces["leftDeflect_indvAvgs"], dtype=float)
    right = np.asarray(traces["rightDeflect_indvAvgs"], dtype=float)
    if left.shape != (17, 5) or right.shape != left.shape:
        raise ValueError(f"Unverified MAT schema: expected published 17 flies x 5 angles, got {left.shape}, {right.shape}")
    if np.isinf(left).any() or np.isinf(right).any():
        raise ValueError("Infinite measured antenna values")
    for side, data in (("left", left), ("right", right)):
        expected = np.asarray(traces[f"{side}Deflect_crossFlyAvgs"], dtype=float).reshape(-1)
        if expected.shape != (5,) or not np.allclose(np.nanmean(data, axis=0), expected, atol=1e-7, equal_nan=True):
            raise ValueError(f"Per-fly {side} means differ from source published plotting values")
    if not np.allclose(right - left, traces["rMinLDeflect_indvAvgs"], atol=1e-8):
        raise ValueError("Paired right-minus-left observations differ from the source")
    paired = np.isfinite(left) & np.isfinite(right)
    if (paired.sum(axis=0) < 2).any():
        raise ValueError("Insufficient paired observations")
    theta = np.asarray([-90., -45., 0., 45., 90.])
    anemometer = anemometer_summary(directory)
    basis = np.column_stack([np.ones(5), np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))])
    results = {}
    for name, values in (("left", left), ("right", right), ("right_minus_left", right - left)):
        values = np.where(paired, values, np.nan)
        mean = np.nanmean(values, axis=0)
        sd = np.nanstd(values, axis=0, ddof=1)
        # Pair validity is common to both antennae; uncertainty uses paired flies,
        # not 85 angles or individual video frames as independent animals.
        design = np.column_stack([np.ones(5), theta]) if name == "right_minus_left" else basis
        coefficients = np.linalg.lstsq(design, mean, rcond=None)[0]
        predicted = design @ coefficients
        residual = mean - predicted
        denominator = np.sum((mean - mean.mean())**2)
        heldout_errors = []
        for heldout in range(len(values)):
            training_mean = np.nanmean(np.delete(values, heldout, axis=0), axis=0)
            training_fit = np.linalg.lstsq(design, training_mean, rcond=None)[0]
            heldout_errors.append(values[heldout] - design @ training_fit)
        heldout_errors = np.asarray(heldout_errors)
        results[name] = {"mean_deg": mean.tolist(), "sd_deg": sd.tolist(),
                         "sem_deg": (sd / np.sqrt(paired.sum(axis=0))).tolist(),
                         "coefficients": coefficients.tolist(),
                         "basis": ["1", "wind_angle_deg"] if name == "right_minus_left" else ["1", "cos(wind_angle_rad)", "sin(wind_angle_rad)"],
                         "fitted_mean_deg": predicted.tolist(), "residual_deg": residual.tolist(),
                         "r_squared_five_means": float(1 - np.sum(residual**2) / denominator) if denominator > 0 else None,
                         "leave_one_fly_out": {
                             "folds": len(values), "training_flies_per_fold": len(values) - 1,
                             "rmse_deg": float(np.sqrt(np.nanmean(heldout_errors**2))),
                             "mae_deg": float(np.nanmean(np.abs(heldout_errors))),
                             "rmse_by_heldout_fly_deg": np.sqrt(np.nanmean(heldout_errors**2, axis=1)).tolist(),
                             "interpretation": "Predict five observations in one unseen female from other 16 females' mean fit; within this preparation/speed only"}}
    report = {"status": "fitted_from_primary_mat_not_runtime_validated", "dataset_doi": DOI,
              "raw_measurements_available": True, "runtime_usable": False,
              "archive_sha256": receipt["archive_sha256"],
              "archive_md5": MD5, "archive_bytes": SIZE,
              "analysis_reference_commit": "dc5180e4af6352f03f9a86b9f03185dba7926244",
              "paper_doi": "10.1016/j.neuron.2019.03.012",
              "license": "CC0-1.0", "measurements": summary,
              "wind_angle_deg": theta.tolist(), "angle_convention": "wind source: negative left, positive right, zero anterior",
              "paired_flies_per_angle": paired.sum(axis=0).tolist(), "curves": results,
              "per_fly_measurements": {"experiment_ids": [str(v) for v in traces["exptListRet"]],
                                       "left_deg": left.tolist(), "right_deg": right.tolist(),
                                       "angle_order_deg": theta.tolist(), "source_fields": ["leftDeflect_indvAvgs", "rightDeflect_indvAvgs"]},
              "deflection_sign": "negative headward, positive away from head; arista angles, not mapped joint angles",
              "anemometer": anemometer,
              "velocity_m_s": anemometer["mean_cm_s"] / 100,
              "velocity_basis": "Our explicit final 1s steady-state average of deposited calibrated anemometer traces; paper nominal 0.5957m/s differs",
              "paper_nominal_velocity_m_s": 0.5957,
              "preparation": "Tethered adult female Drosophila, 2-7 days old; Fig 2 anterior mount; 4 s wind",
              "analysis": "Per-fly paired averages from source; SD ddof=1 and SEM explicitly distinguished; OLS on five means",
              "valid_angle_domain_deg": [-90, 90], "velocity_scaling_validated": False,
              "male_transfer_validated": False, "runtime_input_mapping_validated": False,
              "limitations": ["Single nominal wind speed; no validated speed-response law",
                              "Five azimuths only; no rear wind, elevation, flight or free-walking validation",
                              "Cosine and linear fits are our derived summaries, not original measured points",
                              "Female measurements do not establish male stiffness or motor gains",
                              "Arista angle is not neural firing rate or a calibrated MuJoCo joint angle"]}
    save(destination, report)
    return report


def plot_fit(source=ROOT / "data/wind-calibration.json", destination=ROOT / "validation/wind-antenna-response.png"):
    """Render source-derived means and SD; no image is made from placeholders."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    report = json.loads(Path(source).read_text())
    if report.get("status") != "fitted_from_primary_mat_not_runtime_validated":
        raise ValueError("A measured fit is required before plotting")
    theta = np.asarray(report["wind_angle_deg"])
    dense = np.linspace(-90, 90, 301)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), layout="constrained")
    for label, color in (("left", "#b54376"), ("right", "#168978"), ("right_minus_left", "#5a4ba0")):
        curve = report["curves"][label]
        panel = axes[1] if label == "right_minus_left" else axes[0]
        basis = np.column_stack([np.ones(len(dense)), dense]) if label == "right_minus_left" else np.column_stack([np.ones(len(dense)), np.cos(np.deg2rad(dense)), np.sin(np.deg2rad(dense))])
        panel.errorbar(theta, curve["mean_deg"], yerr=curve["sd_deg"], color=color,
                       fmt="o", capsize=3, label=label.replace("_", " ") + " measured mean ± SD")
        panel.plot(dense, basis @ curve["coefficients"], color=color, linestyle="--", label="derived OLS fit")
    for panel in axes:
        panel.axhline(0, color="#cccccc", linewidth=.7)
        panel.set(xlabel="Wind source azimuth (deg; left −, right +)", ylabel="Arista deflection (deg)", xticks=theta)
        panel.spines[["top", "right"]].set_visible(False)
        panel.legend(fontsize=8, frameon=False)
    axes[0].set_title("Individual antenna response")
    axes[1].set_title("Paired right − left response")
    fig.suptitle("Suver et al. 2019 · 17 females · nominal ~0.60 m/s · 4 s wind\nPrimary MAT measurements; runtime and male transfer unvalidated", fontsize=11)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=170)
    plt.close(fig)
    return {"plot": str(destination.resolve()), "sha256": digest(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("metadata")
    commands.add_parser("plot")
    inspect = commands.add_parser("inspect")
    source = inspect.add_mutually_exclusive_group(required=True)
    source.add_argument("--archive", type=Path)
    source.add_argument("--url")
    inspect.add_argument("--size", type=int, default=SIZE)
    inspect.add_argument("--byte-budget", type=int, default=16 * 1024**2)
    extract = commands.add_parser("extract")
    extract.add_argument("archive", type=Path)
    extract.add_argument("--output", type=Path, default=RAW)
    for name in ("summarize", "fit"):
        command = commands.add_parser(name)
        command.add_argument("--mat-dir", type=Path, default=RAW)
    args = parser.parse_args()
    if args.command == "metadata": result = metadata()
    elif args.command == "plot": result = plot_fit()
    elif args.command == "inspect": result = inspect_archive(args.archive, args.url, args.size, args.byte_budget)
    elif args.command == "extract": result = extract_archive(args.archive, args.output)
    elif args.command == "summarize":
        result = mat_summary(args.mat_dir)
        save(RAW / "mat-field-summary.json", result)
    else: result = fit(args.mat_dir)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
