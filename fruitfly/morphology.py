"""Selective morphology-source extraction and declared CT envelope analysis.

This module never treats a CT intensity envelope as a calibrated articulated
body. Remote ZIP reads require HTTP byte ranges and refuse full-file fallbacks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile


ARTICLE_API = "https://api.figshare.com/v2/articles/25598859"
SOURCE_PREFIX = "BlackieGasparEtAl2024-sourceData/"


class RangeReader(io.RawIOBase):
    """Minimal seekable HTTP reader; never downloads an unrequested whole file."""

    def __init__(self, url: str, size: int):
        self.url, self.size, self.position = url, size, 0
        self.bytes_received = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if target < 0:
            raise ValueError("Negative file offset")
        self.position = target
        return target

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        if size <= 0:
            return b""
        # zipfile reads its directory (~1 MB) or a stream chunk; an accidental
        # full-archive read must fail before issuing the request.
        if size > 8 * 1024 * 1024:
            raise ValueError("Requested range exceeds the 8 MiB per-request budget")
        start = self.position
        end = start + size - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=60) as response:
            expected = f"bytes {start}-{end}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise IOError("Server did not honor the exact byte range; refusing full download")
            data = response.read(size + 1)
        if len(data) != size:
            raise IOError("Incomplete or oversized HTTP range")
        self.position += len(data)
        self.bytes_received += len(data)
        return data


def source_metadata():
    with urllib.request.urlopen(ARTICLE_API, timeout=30) as response:
        return json.load(response)


def extract_members(member_names: list[str], output_dir: Path) -> dict:
    """Download named members, validate ZIP CRC, save SHA256 and provenance.

    Names are exact archive-relative paths. Outputs preserve paths beneath the
    source prefix. Existing verified members are not downloaded a second time.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = source_metadata()
    archive = next(f for f in metadata["files"] if f["name"] == "BlackieGasparEtAl2024-sourceData.zip")
    reader = RangeReader(archive["download_url"], archive["size"])
    manifest_path = output_dir / "provenance.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "article_id": metadata["id"], "article_version": metadata["version"],
        "article_doi": metadata["doi"], "title": metadata["title"],
        "license": metadata["license"], "archive": archive, "members": [],
    }
    with zipfile.ZipFile(reader) as remote:
        for name in member_names:
            if not name.startswith(SOURCE_PREFIX) or ".." in Path(name).parts:
                raise ValueError("Member path is outside the known source root")
            info = remote.getinfo(name)
            target = output_dir / name.removeprefix(SOURCE_PREFIX)
            old = next((m for m in manifest["members"] if m["archive_path"] == name), None)
            if target.exists() and old:
                with target.open("rb") as existing:
                    existing_sha = hashlib.file_digest(existing, "sha256").hexdigest()
                if existing_sha == old["sha256"]:
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            digest = hashlib.sha256()
            with remote.open(info) as source, partial.open("wb") as destination:
                while chunk := source.read(4 * 1024 * 1024):
                    destination.write(chunk)
                    digest.update(chunk)
            if partial.stat().st_size != info.file_size:
                raise IOError("Extracted member size differs from ZIP metadata")
            partial.replace(target)
            record = {"archive_path": name, "local_path": str(target.resolve()),
                      "compressed_bytes": info.compress_size, "bytes": info.file_size,
                      "zip_crc32": f"{info.CRC:08x}", "sha256": digest.hexdigest()}
            manifest["members"] = [m for m in manifest["members"] if m["archive_path"] != name]
            manifest["members"].append(record)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(json.dumps({"downloaded": str(target), "bytes": info.file_size}), flush=True)
    manifest["last_transfer_bytes"] = reader.bytes_received
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def trace_lattice_spacing(swc_path: Path) -> tuple[float, float]:
    """Recover a common native coordinate lattice, without assuming SWC units.

    This applies to these source traces, which retain integer voxel locations.
    It rejects interpolated or nonuniformly sampled coordinate sets.
    """
    import numpy as np
    coordinates = np.loadtxt(swc_path, usecols=(2, 3, 4))
    deltas = np.concatenate([np.diff(np.unique(coordinates[:, axis])) for axis in range(3)])
    deltas = deltas[deltas > 1e-9]
    if not len(deltas):
        raise ValueError("Trace has no measurable coordinate spacing")
    pitch = round(float(deltas.min()), 12)
    error = float(np.max(np.abs(coordinates / pitch - np.rint(coordinates / pitch))))
    if error > 1e-5:
        raise ValueError("Trace does not lie on one uniform lattice")
    return pitch, error


def analyze_male_scan(scan_path: Path, trace_path: Path, output_dir: Path, *, downsample=3) -> dict:
    """Derive an unrigged CT tissue envelope, explicitly unsuitable for physics.

    A thresholded stained-tissue volume is not a cuticle segmentation. Threshold
    sensitivity, fixed appendages and tissue loss must remain visible in results.
    """
    import numpy as np
    import nibabel as nib
    from scipy import ndimage as ndi
    from skimage.filters import threshold_otsu
    from skimage.measure import marching_cubes
    from skimage.morphology import ball
    from PIL import Image, ImageDraw

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image = nib.load(scan_path)
    volume = np.asanyarray(image.dataobj)[::downsample, ::downsample, ::downsample]
    pitch, error = trace_lattice_spacing(trace_path)
    # Source-specific conversion: 0.002951345 in the trace, interpreted as mm,
    # agrees with the paper's 2.95 micrometre acquisition scale. This is inferred
    # from paired files; the NIfTI header's 1 mm cannot be used as real anatomy.
    if not .00249 - .00001 <= pitch <= .00296:
        raise ValueError("Recovered pitch is inconsistent with this paper's scanner scales")
    spacing_mm = pitch * downsample
    trace = np.loadtxt(trace_path, usecols=(2, 3, 4))
    trace_indices = np.rint(trace / spacing_mm).astype(int)
    if (trace_indices < 0).any() or (trace_indices >= np.asarray(volume.shape)).any():
        raise ValueError("Paired trace does not fit the scan index bounds")
    otsu = int(threshold_otsu(volume))
    thresholds = sorted(set((max(1, otsu - 20), otsu, min(254, otsu + 20))))
    canvas = Image.new("RGB", (1200, 440), "white")
    draw = ImageDraw.Draw(canvas)
    projection = volume.max(axis=1)
    results = []
    primary_vertices = primary_faces = None
    for panel, threshold in enumerate(thresholds):
        candidate = ndi.binary_closing(volume > threshold, structure=ball(2))
        candidate = ndi.binary_fill_holes(candidate)
        candidate = ndi.binary_opening(candidate, structure=ball(3))
        components, _ = ndi.label(candidate)
        counts = np.bincount(components.ravel())
        counts[0] = 0
        mask = components == int(np.argmax(counts))
        indices = np.column_stack(np.nonzero(mask))
        centred = indices - indices.mean(axis=0)
        covariance = centred.T @ centred / max(1, len(centred) - 1)
        _, basis = np.linalg.eigh(covariance)
        projected = centred @ basis[:, ::-1] * spacing_mm
        flipped = trace_indices.copy()
        flipped[:, 1] = volume.shape[1] - 1 - flipped[:, 1]
        results.append({
            "threshold_uint8": threshold,
            "volume_mm3": float(mask.sum() * spacing_mm**3),
            "scanner_axis_extent_mm": (np.ptp(indices, axis=0) * spacing_mm).tolist(),
            "principal_axis_extent_mm": np.ptp(projected, axis=0).tolist(),
            "trace_inside_fraction": float(mask[tuple(trace_indices.T)].mean()),
            "mirrored_y_trace_inside_fraction": float(mask[tuple(flipped.T)].mean()),
        })
        rgb = np.repeat(projection[:, :, None], 3, axis=2)
        overlay = mask.any(axis=1)
        rgb[overlay, 0] = 255
        rgb[overlay, 1] //= 2
        rgb[overlay, 2] //= 2
        picture = Image.fromarray(rgb)
        picture.thumbnail((380, 395))
        canvas.paste(picture, (panel * 400 + 5, 35))
        draw.text((panel * 400 + 5, 10), f"Male M5H: threshold {threshold}; tissue envelope", fill="black")
        if threshold == otsu:
            primary_vertices, primary_faces, _, _ = marching_cubes(
                mask.astype(np.uint8), level=.5, spacing=(spacing_mm,) * 3)
    canvas.save(output_dir / "male-envelope-sensitivity.png")
    mesh_path = output_dir / "male-M5H-tissue-envelope.obj"
    with mesh_path.open("w") as mesh:
        mesh.write("# Male OregonR M5H stained-tissue envelope, inferred mm.\n")
        mesh.write("# Not a cuticle segmentation, not articulated, not ready for physics.\n")
        mesh.write("# Source CC-BY4.0 Blackie, Gaspar et al 2024 doi:10.25418/crick.25598859.v1\n")
        for vertex in primary_vertices:
            mesh.write("v " + " ".join(f"{value:.8f}" for value in vertex) + "\n")
        for face in primary_faces + 1:
            mesh.write("f " + " ".join(map(str, face)) + "\n")
    report = {
        "specimen": "M5H", "sex": "Male", "genotype": "OregonR",
        "scan_file": str(Path(scan_path).resolve()),
        "paired_trace_file": str(Path(trace_path).resolve()),
        "nifti_shape": list(image.shape), "nifti_units": list(image.header.get_xyzt_units()),
        "nifti_zooms": [float(x) for x in image.header.get_zooms()],
        "nifti_spatial_calibration_valid": False,
        "inferred_voxel_pitch_mm": pitch, "trace_lattice_max_error_voxels": error,
        "calibration_basis": "Exact lattice in paired M5H.swc; mm interpretation agrees with reported 2.95 micrometre scanner sampling",
        "downsample_stride": downsample, "threshold_method": "Otsu on downsampled uint8 volume",
        "closing_radius_downsampled_voxels": 2, "opening_radius_downsampled_voxels": 3,
        "sensitivity": results, "mesh_vertices": len(primary_vertices),
        "mesh_faces": len(primary_faces), "mesh_sha256": hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        "body_physics_ready": False,
        "limitations": ["Stained tissue envelope is not external cuticle", "Fixed legs and wings overlap the body",
                        "Thresholding changes tissue extent and volume", "No segment articulation, densities or inertias",
                        "No global female-to-male scaling ratio is justified by this extraction"],
    }
    (output_dir / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/raw/morphology"))
    parser.add_argument("--member", action="append")
    parser.add_argument("--analyze-scan", type=Path)
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args()
    if args.analyze_scan:
        if not args.trace:
            parser.error("--analyze-scan requires --trace")
        print(json.dumps(analyze_male_scan(args.analyze_scan, args.trace, args.output), indent=2))
    elif args.member:
        extract_members(args.member, args.output)
    else:
        parser.error("Provide --member or --analyze-scan")
