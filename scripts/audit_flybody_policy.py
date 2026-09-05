"""Read small, pinned FlyBody policy metadata; do not install or load weights.

Uses the ZIP central directory and walking/saved_model.pb only. A ZIP suffix
request incidentally overlaps the last few KiB of the weight member; those bytes
are neither decompressed nor interpreted. No whole-archive hash is claimed.

The minimal protobuf reader follows TensorFlow v2.8.0 SavedModel schemas:
https://github.com/tensorflow/tensorflow/tree/v2.8.0/tensorflow/core/protobuf
It inspects shapes/signatures, not executable graph semantics or weight values.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import urllib.request
import zipfile
import zlib

COMMIT = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
ARCHIVE_URL = "https://ndownloader.figshare.com/files/44815195"
ARCHIVE_SIZE = 6537720
GRAPH_SHA256 = "49cdb0874021609c1aa5634a3073a394ef55b7ce54b6487c020c8ed2ec37d5d4"
SOURCE_FILES = ["LICENSE", "pyproject.toml", "flybody/fly_envs.py",
    "flybody/fruitfly/fruitfly.py", "flybody/tasks/base.py",
    "flybody/tasks/constants.py", "flybody/tasks/walk_imitation.py",
    "flybody/tasks/trajectory_loaders.py", "flybody/tasks/synthetic_trajectories.py",
    "flybody/tasks/task_utils.py", "flybody/agents/utils_tf.py",
    "flybody/agents/network_factory.py"]
PYPI_PACKAGES = [("tensorflow", "2.8.0"), ("tensorflow-macos", "2.8.0"),
    ("dm-reverb", "0.7.0"), ("tensorflow", "2.15.1"),
    ("tensorflow-probability", "0.23.0")]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, limit=2_000_000):
    with urllib.request.urlopen(url, timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Metadata exceeds declared download limit")
    return data


def byte_range(start, end):
    expected = f"bytes {start}-{end}/{ARCHIVE_SIZE}"
    request = urllib.request.Request(ARCHIVE_URL,
        headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 206 or response.headers.get("Content-Range") != expected:
            raise ValueError("Server did not honor exact range; no response body read")
        data = response.read(end - start + 2)
        receipt = {"url": ARCHIVE_URL, "status": response.status,
                   "content_range": expected, "etag": response.headers.get("ETag"),
                   "last_modified": response.headers.get("Last-Modified")}
    if len(data) != end - start + 1:
        raise ValueError("Unexpected range length")
    receipt.update(bytes_read=len(data), sha256=sha(data))
    return data, receipt


def read_varint(data, position):
    result = shift = 0
    while True:
        if position >= len(data) or shift > 63:
            raise ValueError("Truncated or excessive protobuf varint")
        item = data[position]
        position += 1
        result |= (item & 127) << shift
        if item < 128:
            return result, position
        shift += 7


def fields(data):
    """Return repeated wire fields; reject unsupported groups/truncation."""
    result = defaultdict(list)
    position = 0
    while position < len(data):
        tag, position = read_varint(data, position)
        wire, number = tag & 7, tag >> 3
        if not number:
            raise ValueError("Invalid protobuf field zero")
        if wire == 0:
            value, position = read_varint(data, position)
        elif wire in (1, 2, 5):
            if wire == 2:
                length, position = read_varint(data, position)
            else:
                length = {1: 8, 5: 4}[wire]
            value = data[position:position + length]
            position += length
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire}")
        if position > len(data):
            raise ValueError("Truncated protobuf field")
        result[number].append(value)
    return result


def first(mapping, number, default=b""):
    return mapping.get(number, [default])[0]


def shape(data):
    dims = [first(fields(item), 1, 0) for item in fields(data).get(2, [])]
    return [value - (1 << 64) if value >= 1 << 63 else value for value in dims]


def structured(data):
    mapping = fields(data)
    if 1 in mapping:
        return None
    if 13 in mapping:
        return first(mapping, 13).decode()
    if 14 in mapping:
        return bool(first(mapping, 14))
    if 12 in mapping:
        value = first(mapping, 12)
        return (value >> 1) ^ -(value & 1)
    if 33 in mapping:
        spec = fields(first(mapping, 33))
        return {"tensor_name": first(spec, 1).decode(),
                "shape": shape(first(spec, 2)), "dtype_enum": first(spec, 3, 0)}
    if 34 in mapping:
        spec = fields(first(mapping, 34))
        return {"registered_type": first(spec, 3).decode(),
                "class_enum": first(spec, 1, 0), "state": structured(first(spec, 2))}
    for number in (51, 52):
        if number in mapping:
            return [structured(value) for value in fields(first(mapping, number)).get(1, [])]
    if 53 in mapping:
        result = {}
        for value in fields(first(mapping, 53)).get(1, []):
            entry = fields(value)
            result[first(entry, 1).decode()] = structured(first(entry, 2))
        return result
    if 31 in mapping:
        return {"shape": shape(first(mapping, 31))}
    if 32 in mapping:
        return {"dtype_enum": first(mapping, 32)}
    raise ValueError(f"Unsupported StructuredValue field: {list(mapping)}")


def inspect_graph(data):
    if sha(data) != GRAPH_SHA256:
        raise ValueError("SavedModel graph changed; inspect before updating pin")
    model = fields(data)
    if len(model[2]) != 1:
        raise ValueError("Expected one MetaGraph")
    meta_graph = fields(first(model, 2))
    meta = fields(first(meta_graph, 1))
    objects = fields(first(meta_graph, 7))
    output = {"sha256": sha(data), "bytes": len(data),
        "tensorflow_version": first(meta, 5).decode(),
        "tensorflow_git_version": first(meta, 6).decode(),
        "variables": [], "functions": {}}
    for index, item in enumerate(objects[1]):
        node = fields(item)
        if 7 in node:
            variable = fields(first(node, 7))
            output["variables"].append({"object_node_id": index,
                "name": first(variable, 6).decode(), "shape": shape(first(variable, 2)),
                "dtype_enum": first(variable, 1, 0)})
    for item in objects[2]:
        entry = fields(item)
        function = fields(first(entry, 2))
        output["functions"][first(entry, 1).decode()] = {
            "input": structured(first(function, 3)),
            "output": structured(first(function, 4))}
    graph = fields(first(meta_graph, 2))
    nodes = list(graph[1])
    for library in graph.get(2, []):
        for function in fields(library).get(1, []):
            nodes.extend(fields(function).get(3, []))
    output["op_counts_including_save_restore"] = dict(Counter(
        first(fields(node), 2).decode() for node in nodes))
    output["parameter_count"] = sum(math.prod(v["shape"]) for v in output["variables"])
    inputs = next(iter(output["functions"].values()))["input"][0][0]
    output["flat_input_count"] = sum(math.prod(v["shape"][1:]) for v in inputs.values())
    assert output["parameter_count"] == 1229430 and output["flat_input_count"] == 741
    assert all(variable["dtype_enum"] == 1 for variable in output["variables"])
    return output


def acquire(cache):
    cache.mkdir(parents=True, exist_ok=True)
    figshare = fetch("https://api.figshare.com/v2/articles/25309105/versions/4")
    (cache / "figshare-pinned.json").write_bytes(figshare)
    tail_start = ARCHIVE_SIZE - 65536
    tail, tail_receipt = byte_range(tail_start, ARCHIVE_SIZE - 1)
    sparse = io.BytesIO()
    sparse.seek(tail_start)
    sparse.write(tail)
    archive = zipfile.ZipFile(sparse)
    members = [{"name": item.filename, "bytes": item.file_size,
        "compressed_bytes": item.compress_size, "header_offset": item.header_offset,
        "crc32": f"{item.CRC:08x}", "compression": item.compress_type}
        for item in archive.infolist()]
    graph = archive.getinfo("walking/saved_model.pb")
    # Read the exact local header, then only its filename/extra and graph payload.
    header, header_receipt = byte_range(graph.header_offset, graph.header_offset + 29)
    values = struct.unpack("<4s5H3I2H", header)
    if values[0] != b"PK\x03\x04" or values[3] != zipfile.ZIP_DEFLATED:
        raise ValueError("Unexpected ZIP local header")
    start = graph.header_offset + 30
    size = values[-2] + values[-1] + graph.compress_size
    payload, graph_receipt = byte_range(start, start + size - 1)
    data = zlib.decompress(payload[values[-2] + values[-1]:], -15)
    if len(data) != graph.file_size or zlib.crc32(data) != graph.CRC:
        raise ValueError("Graph ZIP CRC/size check failed")
    inspect_graph(data)
    (cache / "walking-saved_model.pb").write_bytes(data)
    (cache / "zip-members.json").write_text(json.dumps(members, indent=2) + "\n")
    (cache / "range-receipts.json").write_text(json.dumps(
        [tail_receipt, header_receipt, graph_receipt], indent=2) + "\n")
    sources = []
    for path in SOURCE_FILES:
        url = f"https://raw.githubusercontent.com/TuragaLab/flybody/{COMMIT}/{path}"
        content = fetch(url)
        destination = cache / "source" / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        sources.append({"path": path, "url": url, "bytes": len(content), "sha256": sha(content)})
    (cache / "source-manifest.json").write_text(json.dumps(sources, indent=2) + "\n")
    for name, version in PYPI_PACKAGES:
        (cache / f"pypi-{name}-{version}.json").write_bytes(fetch(
            f"https://pypi.org/pypi/{name}/{version}/json"))


def summarize(cache):
    figshare = json.loads((cache / "figshare-pinned.json").read_text())
    policies = next(file for file in figshare["files"] if file["id"] == 44815195)
    packages = []
    for name, version in PYPI_PACKAGES:
        raw = (cache / f"pypi-{name}-{version}.json").read_bytes()
        package = json.loads(raw)
        packages.append({"name": name, "version": version,
            "url": f"https://pypi.org/pypi/{name}/{version}/json", "metadata_sha256": sha(raw),
            "requires_python": package["info"]["requires_python"],
            "requires_dist": package["info"]["requires_dist"],
            "files": [{"filename": item["filename"], "bytes": item["size"],
                       "sha256": item["digests"]["sha256"]} for item in package["urls"]]})
    return {"schema_version": 1, "audit_date": "2026-09-04",
        "scope": "source and metadata only; no inference, weight load, package install, or runtime change",
        "repository_commit": COMMIT, "figshare_version": figshare["version"],
        "figshare_doi": figshare["doi"], "figshare_collection_license": figshare["license"],
        "policy_archive": policies, "full_archive_digest_verified": False,
        "zip_members": json.loads((cache / "zip-members.json").read_text()),
        "range_receipts": json.loads((cache / "range-receipts.json").read_text()),
        "source_manifest": json.loads((cache / "source-manifest.json").read_text()),
        "graph": inspect_graph((cache / "walking-saved_model.pb").read_bytes()),
        "package_metadata": packages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("tmp/flybody-policy-audit"))
    parser.add_argument("--cached", action="store_true", help="Use already acquired small metadata only")
    parser.add_argument("--output", type=Path, default=Path("validation/flybody-policy-audit.json"))
    args = parser.parse_args()
    if not args.cached:
        acquire(args.cache)
    report = summarize(args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "parameters": report["graph"]["parameter_count"],
        "inputs": report["graph"]["flat_input_count"], "archive_bytes_read": sum(
            item["bytes_read"] for item in report["range_receipts"])}, indent=2))


if __name__ == "__main__":
    main()
