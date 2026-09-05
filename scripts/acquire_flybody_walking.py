"""Acquire only the author's walking SavedModel via bounded ZIP-member ranges.

The Figshare collection declares GPL-3.0-or-later; preserve the separate receipt.
No flight controllers or training data are downloaded. The archive MD5 is not
verified by partial extraction; each member gets ZIP CRC and local SHA-256.
"""
from pathlib import Path
import hashlib
import json
import struct
import urllib.request
import zlib

from scripts.audit_flybody_policy import ARCHIVE_URL, ARCHIVE_SIZE, GRAPH_SHA256

OUTPUT = Path("data/raw/flybody/walking")
MEMBERS = ["walking/saved_model.pb", "walking/variables/variables.index",
           "walking/variables/variables.data-00000-of-00001"]


def read_range(start, end):
    if not (0 <= start <= end < ARCHIVE_SIZE) or end - start + 1 > 5_000_000:
        raise ValueError("Range outside declared walking download budget")
    request = urllib.request.Request(ARCHIVE_URL,
        headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{ARCHIVE_SIZE}":
            raise ValueError("Range ignored; no body read")
        data = response.read(end - start + 2)
    if len(data) != end - start + 1:
        raise ValueError("Truncated/oversized range")
    return data


def main():
    audit = json.loads(Path("validation/flybody-policy-audit.json").read_text())
    entries = {entry["name"]: entry for entry in audit["zip_members"]}
    receipt = {"source_url": ARCHIVE_URL, "archive_size": ARCHIVE_SIZE,
        "collection_doi": audit["figshare_doi"], "collection_license": audit["figshare_collection_license"],
        "supplied_archive_md5": audit["policy_archive"]["supplied_md5"],
        "full_archive_digest_verified": False,
        "scope": "walking SavedModel only, exact ZIP CRC checked; no training dataset",
        "members": []}
    for name in MEMBERS:
        item = entries[name]
        start = item["header_offset"]
        header = read_range(start, start + 29)
        values = struct.unpack("<4s5H3I2H", header)
        if values[0] != b"PK\x03\x04" or values[3] != 8:
            raise ValueError("Unexpected ZIP header")
        metadata_size = values[-2] + values[-1]
        size = metadata_size + item["compressed_bytes"]
        payload = read_range(start + 30, start + 30 + size - 1)
        if payload[:values[-2]].decode() != name:
            raise ValueError("ZIP member name mismatch")
        data = zlib.decompress(payload[metadata_size:], -15)
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != item["bytes"] or f"{zlib.crc32(data):08x}" != item["crc32"]:
            raise ValueError("ZIP member size/CRC mismatch")
        if name.endswith("saved_model.pb") and digest != GRAPH_SHA256:
            raise ValueError("Graph differs from audited checkpoint")
        path = OUTPUT / Path(name).relative_to("walking")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"Existing different data at {path}")
        path.write_bytes(data)
        receipt["members"].append({**item, "local_path": str(path), "sha256": digest,
                                   "compressed_bytes_read": len(header) + len(payload)})
    receipt_path = Path("validation/flybody-walking-acquisition.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    (OUTPUT / "ASSET-LICENSE.md").write_text(
        "# Walking policy asset provenance\n\n"
        "Author source: https://doi.org/10.25378/janelia.25309105.v4\n\n"
        "Figshare collection license: GPL 3.0+ (GPL-3.0-or-later).\n"
        "https://www.gnu.org/licenses/gpl-3.0.html\n\n"
        "This is separate from the FlyBody repository's Apache-2.0 code license.\n"
        "Acquired unchanged ZIP members only; see validation/flybody-walking-acquisition.json.\n")
    print(json.dumps({"receipt": str(receipt_path), "members": len(receipt["members"]),
        "downloaded_archive_bytes": sum(x["compressed_bytes_read"] for x in receipt["members"])}, indent=2))


if __name__ == "__main__":
    main()
