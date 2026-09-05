"""Acquire the author's public curated single-fly HDF5, without raw videos.

Follows Google Drive's normal public large-file confirmation form. The file is
data, not executed code. An observed SHA256 is provenance, not a published
independent checksum. Public metadata supplies the expected byte count.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

FILE_ID = "1EktWQq4ZPAtuzhIlwvSGRNSa9WCQTLW7"
EXPECTED_BYTES = 714_915_024
BASE = "https://drive.usercontent.google.com/download"
OUTPUT = Path("data/raw/freewalking/free_running_raw_combined_v1.h5")


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            if attrs.get("method", "get").lower() != "get":
                raise ValueError("Unexpected public download form method")
            self.action = attrs.get("action")
        if tag == "input" and attrs.get("type") == "hidden":
            self.fields[attrs["name"]] = attrs.get("value", "")


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise FileExistsError("Archive already exists; preserve and verify its saved receipt")
    partial = OUTPUT.with_suffix(".h5.part")
    if partial.exists():
        raise FileExistsError("Partial archive exists; preserve it before restarting")
    public_url = BASE + "?" + urllib.parse.urlencode({"id": FILE_ID, "export": "download"})
    response = urllib.request.urlopen(public_url, timeout=30)
    if "text/html" in response.headers.get("Content-Type", ""):
        form = DownloadForm()
        form.feed(response.read(65536).decode("utf-8"))
        response.close()
        if form.action != BASE or form.fields.get("id") != FILE_ID:
            raise ValueError("Unexpected large-file confirmation target")
        response = urllib.request.urlopen(form.action + "?" + urllib.parse.urlencode(form.fields), timeout=30)
    if "text/html" in response.headers.get("Content-Type", ""):
        response.close()
        raise ValueError("Download returned HTML instead of HDF5; no data was saved")
    digest, size, start = hashlib.sha256(), 0, time.monotonic()
    next_report = 64 * 1024 * 1024
    with response, partial.open("xb") as stream:
        while block := response.read(8 * 1024 * 1024):
            if size == 0 and block[:8] != b"\x89HDF\r\n\x1a\n":
                raise ValueError("Download does not start with the expected HDF5 signature")
            size += len(block)
            if size > EXPECTED_BYTES:
                raise ValueError("Download exceeds published byte count")
            stream.write(block)
            digest.update(block)
            if size >= next_report:
                print(f"{size / 1e6:.0f}/{EXPECTED_BYTES / 1e6:.0f} MB", flush=True)
                next_report += 64 * 1024 * 1024
    if size != EXPECTED_BYTES:
        raise ValueError("Incomplete HDF5 download; partial preserved")
    partial.replace(OUTPUT)
    receipt = {"public_file_id": FILE_ID, "public_url": public_url,
               "source_folder": "https://drive.google.com/drive/folders/1flBiyFmJYWPA6EIN4Xoh_2Lc5VT2_AoV",
               "source_paper_doi": "10.64898/2026.05.03.722293", "bytes": size,
               "sha256": digest.hexdigest(), "published_checksum_available": False,
               "data_license": "not identified; preserve separately from code license",
               "wall_seconds": time.monotonic() - start,
               "method": "normal public download, including provider large-file confirmation form"}
    OUTPUT.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
