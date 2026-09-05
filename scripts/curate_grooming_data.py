"""Extract small numeric examples from two checksum-verified CC0 Ozdil files.

This preserves author coordinates/signs and generates no controller. The source
pickles stay in ignored data/raw/grooming. Outputs require no pickle loading.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import pickle

import numpy as np
import pandas as pd


SOURCES = {
    "Fig1_panelC.pkl": {
        "file_id": 10810237,
        "md5": "d1a737c166123ba8731ccb6e5ff0b2d5",
        "sha256": "89826e646018a5184f13b2ccbdcb4f7713ed26deab98f84fcddf8e237a55892e",
    },
    "Fig1_panelF-G.pkl": {
        "file_id": 10810262,
        "md5": "ff686a720654bd7c5b461ab36b5946c4",
        "sha256": "49bcde5b66447c9c1fffb88441c1dffa93e71905948cb4e90f34dabcc55a8340",
    },
}

# Hash verification is required before this restricted legacy-data conversion.
_ALLOWED = {
    ("pandas.core.frame", "DataFrame"),
    ("pandas.core.internals.managers", "BlockManager"),
    ("pandas._libs.internals", "_unpickle_block"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy", "ndarray"), ("numpy", "dtype"), ("builtins", "slice"),
    ("pandas.core.indexes.base", "_new_Index"),
    ("pandas.core.indexes.base", "Index"),
    ("pandas.core.indexes.range", "RangeIndex"),
}


class _AuditedDataUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) == ("pandas.core.indexes.numeric", "Int64Index"):
            return pd.Index  # pandas 2+ compatibility; values stay unchanged.
        if (module, name) not in _ALLOWED:
            raise pickle.UnpicklingError(f"Unexpected source object {module}.{name}")
        return super().find_class(module, name)


def read_source(directory: Path, name: str):
    content = (directory / name).read_bytes()
    source = SOURCES[name]
    if hashlib.sha256(content).hexdigest() != source["sha256"]:
        raise ValueError(f"Source hash mismatch: {name}")
    return _AuditedDataUnpickler(io.BytesIO(content)).load()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/raw/grooming"))
    parser.add_argument("--output", type=Path, default=Path("data/grooming"))
    args = parser.parse_args()
    panel_c = read_source(args.source, "Fig1_panelC.pkl")
    panel_fg = read_source(args.source, "Fig1_panelF-G.pkl")
    examples = {
        "figure1c_2to5s": (panel_c[(panel_c.Time >= 2) & (panel_c.Time < 5)], "Fig1_panelC.pkl"),
        **{name: (frame, "Fig1_panelF-G.pkl") for name, frame in panel_fg.items()},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    provenance = {
        "dataset_doi": "10.7910/DVN/N8ITTG", "dataset_version": "1.0",
        "paper_doi": "10.1038/s41467-026-72152-x", "data_license": "CC0-1.0",
        "source_sex": "female", "source_age_days": [3, 5],
        "code_repository": "https://github.com/NeLy-EPFL/antennal-grooming",
        "code_commit": "65787ac7fa35aa5520addb6d3e4ac27887bbaf60",
        "code_license": "Apache-2.0", "sources": SOURCES,
        "transformations": ["Figure 1C cropped to 2 <= time < 5 seconds", "added time relative to each snippet start", "converted degrees to radians in a separate array"],
        "unchanged": ["source angle signs and zero references", "source frame IDs", "source stimulus values", "author container labels"],
        "limitations": ["female tethered recording", "inverse-kinematics-derived joint angles", "no validated mapping to current body joints", "author example names are not per-frame behavior annotations", "no neural-to-motor mapping or force validation"],
        "examples": {},
    }
    for name, (frame, source_name) in examples.items():
        columns = [column for column in frame if column.startswith("Angle_")]
        values = frame[columns].to_numpy(dtype=np.float64)
        times = frame.Time.to_numpy(dtype=np.float64)
        if values.shape[1] != 21 or not np.isfinite(values).all():
            raise ValueError(f"Invalid joint-angle matrix for {name}")
        if not np.allclose(np.diff(times), 0.01, atol=1e-10, rtol=0):
            raise ValueError(f"Non-contiguous 100 Hz samples for {name}")
        output = args.output / f"{name}.npz"
        pose_names = [column for column in frame if column.startswith("Pose_")]
        np.savez_compressed(output, joint_names=np.asarray(columns), angles_deg=values,
                            angles_rad=np.deg2rad(values), time_source_s=times,
                            time_relative_s=times-times[0], frame=frame.Frame.to_numpy(dtype=np.int64),
                            stimulus=frame.Stimulus.to_numpy(dtype=np.float64),
                            pose_names=np.asarray(pose_names),
                            pose_source=frame[pose_names].to_numpy(dtype=np.float64))
        # Reload through the no-pickle path used by any future adapter.
        with np.load(output, allow_pickle=False) as result:
            if not np.array_equal(result["angles_deg"], values):
                raise ValueError(f"Numeric roundtrip failed for {name}")
        metadata = {column: str(frame[column].iloc[0]) for column in
                    ("Date", "Genotype", "Fly", "Exp_Type", "Trial")}
        provenance["examples"][name] = {
            "source": source_name, "recording_metadata": metadata,
            "file": str(output), "samples": len(frame), "sample_rate_hz": 100,
            "first_source_time_s": float(times[0]), "last_source_time_s": float(times[-1]),
            "first_frame": int(frame.Frame.iloc[0]), "last_frame": int(frame.Frame.iloc[-1]),
            "joint_names": columns, "angles_finite": True,
            "source_degrees_min": float(values.min()), "source_degrees_max": float(values.max()),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({k: {"samples": v["samples"], "file": v["file"]}
                      for k, v in provenance["examples"].items()}, indent=2))


if __name__ == "__main__":
    main()
