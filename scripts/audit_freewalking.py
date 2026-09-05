"""Inventory the downloaded curated free-walking HDF5 without inferring sex.

No source frame alignment or unit conversion is invented. This records missing
metadata and the one-frame discrepancy for the separate pipeline audit.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np

PATH = Path("data/raw/freewalking/free_running_raw_combined_v1.h5")
EXPECTED_SHA256 = "369c57365b0155ea0e7d25b61ecfe09e08163ad44c896819c6f9dfb69f31f49e"


def scalar(group, index):
    value = group[str(index)][()]
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.generic):
        return value.item()
    return value


def main():
    digest = hashlib.sha256()
    with PATH.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != EXPECTED_SHA256:
        raise ValueError("HDF5 differs from the acquired source; preserve and investigate")
    report = {"source_sha256": digest.hexdigest(), "source_bytes": PATH.stat().st_size,
              "source_doi": "10.64898/2026.05.03.722293", "data_license": "not identified",
              "male_individual_assignments": None, "curated_arrays_exported": False,
              "source_frame_alignment": "pending author-code audit", "bouts": []}
    with h5py.File(PATH, "r") as source:
        info = source["info"]
        keys = sorted(k for k in source if k.startswith("bout_"))
        report["info_fields"] = sorted(info)
        for label in ("kp_names", "names_qpos", "names_xpos"):
            report[label] = [scalar(info[label], i) for i in range(len(info[label]))]
        for index, key in enumerate(keys):
            bout = source[key]
            item = {"key": key, "fly_id": scalar(info["fly_ids"], index),
                    "csv_matched": scalar(info["csv_matched"], index), "arrays": {}}
            for label in ("csv__n_frames", "csv__start_frame", "csv__end_frame",
                          "csv__mean_speed_mm_s", "csv__duration_s"):
                item[label] = scalar(info[label], index)
            for label, dataset in bout.items():
                values = dataset[()]
                item["arrays"][label] = {"shape": list(values.shape), "dtype": str(values.dtype),
                    "nonfinite_count": int((~np.isfinite(values)).sum())}
                if label == "qpos":
                    item["quaternion_max_norm_error"] = float(np.max(
                        np.abs(np.linalg.norm(values[:, 3:7], axis=1) - 1)))
            n = bout["qpos"].shape[0]
            item["stored_samples"] = n
            item["csv_minus_stored_frames"] = (item["csv__n_frames"] - n
                if isinstance(item["csv__n_frames"], (int, float)) else None)
            report["bouts"].append(item)
    report["summary"] = {"bouts": len(report["bouts"]),
        "individuals": len(set(b["fly_id"] for b in report["bouts"])),
        "stored_frames": sum(b["stored_samples"] for b in report["bouts"]),
        "csv_matched_bouts": sum(bool(b["csv_matched"]) for b in report["bouts"]),
        "frame_count_discrepancies": dict(Counter(str(b["csv_minus_stored_frames"]) for b in report["bouts"])),
        "nonfinite_values_by_array": {name: sum(b["arrays"][name]["nonfinite_count"] for b in report["bouts"])
                                      for name in report["bouts"][0]["arrays"]}}
    output = Path("validation/freewalking-inventory.json")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
