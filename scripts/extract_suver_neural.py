#!/usr/bin/env python3
"""Select exact neural data members from the verified CC0 Suver Dryad archive."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

import py7zr

ARCHIVE_SHA256 = "4812e1f0a5d905b9269a40dc91a4894673c9a7ac1ca4591246adc07b61ac37e6"
BASE = "DATA_SETS_SuverEtAl2019/SuverEtAl2019_DATA/"
NAMES = ["24C06_free.mat", "70G01_free.mat", "70B12_free.mat",
         "2017_01_05_E1.mat", "2017_04_28_E7.mat", "2016_10_07_E1.mat",
         "readme.txt", "readme_all_anterior.txt"]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path.home()/"Downloads/DATA_SETS_SuverEtAl2019.7z")
    parser.add_argument("--output", type=Path, default=Path("data/raw/wind/neural"))
    args = parser.parse_args()
    started = perf_counter()
    checksum = sha256(args.archive)
    if checksum != ARCHIVE_SHA256:
        raise ValueError("Archive differs from verified Dryad release; no extraction performed")
    print("Verified archive SHA256", flush=True)
    members = [BASE + name for name in NAMES]
    args.output.mkdir(parents=True, exist_ok=True)
    records = {}
    with tempfile.TemporaryDirectory(prefix="fruitfly-suver-neural-") as temp:
        with py7zr.SevenZipFile(args.archive, "r") as archive:
            inventory = {row.filename: row for row in archive.list()}
            if any(name not in inventory for name in members):
                raise ValueError("Required exact archive member missing")
            archive.extract(path=temp, targets=members)
        for member in members:
            source = Path(temp)/member
            destination = args.output/Path(member).name
            digest = sha256(source)
            if destination.exists() and sha256(destination) != digest:
                raise ValueError(f"Preserving different existing file {destination}")
            if not destination.exists():
                shutil.copyfile(source, destination)
            row = inventory[member]
            records[destination.name] = {"archive_path": member, "local_path": str(destination.resolve()),
                                         "bytes": source.stat().st_size, "crc32": row.crc32, "sha256": digest}
    receipt = {"dataset_doi": "10.5061/dryad.k06kh8f", "license": "CC0-1.0", "archive_sha256": checksum,
               "archive_bytes": args.archive.stat().st_size, "author_code_commit": "dc5180e4af6352f03f9a86b9f03185dba7926244",
               "selection_evidence": "MakeFigure3.m, MakeFigure4.m and load_figure_constants.m at pinned nagellab/Suveretal2019 commit",
               "py7zr_version": py7zr.__version__, "selected_members": records, "wall_seconds": perf_counter()-started}
    (args.output/"extraction-receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(f"Extracted {len(records)} files, {sum(row['bytes'] for row in records.values()):,} bytes", flush=True)


if __name__ == "__main__":
    main()
