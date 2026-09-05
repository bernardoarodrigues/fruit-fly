#!/usr/bin/env python3
"""Inventory the paper-linked public OSF project; download no data payloads."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/salman-osf-inventory.json"
RAW = ROOT / "data/raw/antennal-lobe-inhibition/osf-pfbea/metadata"
records = []
cache = {}


def get(url):
    if url in cache:
        return cache[url]
    if urlsplit(url).scheme != "https" or urlsplit(url).netloc != "api.osf.io":
        raise ValueError("Unexpected metadata endpoint: " + url)
    if len(records) >= 200:
        raise ValueError("Metadata request ceiling reached")
    with urlopen(Request(url, headers={"User-Agent": "fruitfly-research/0.1"}), timeout=20) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Metadata response exceeds 2 MB")
        final_url = response.url
    value = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    path = RAW / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    path.write_bytes(raw)
    records.append({"url": url, "final_url": final_url, "bytes": len(raw),
                    "sha256": digest, "path": str(path.relative_to(ROOT))})
    cache[url] = value
    return value


def listing(url):
    rows = []
    seen = set()
    while url:
        if url in seen:
            raise ValueError("Repeated pagination URL")
        seen.add(url)
        value = get(url)
        rows.extend(value["data"])
        url = value.get("links", {}).get("next")
    return rows


def related(row, name):
    return row["relationships"][name]["links"]["related"]["href"]


def main():
    if OUT.exists():
        raise FileExistsError("Preserve existing inventory: " + str(OUT))
    RAW.mkdir(parents=True, exist_ok=True)
    nodes, files, folders, licenses = [], [], [], {}
    queue, seen = ["https://api.osf.io/v2/nodes/pfbea/"], set()
    started = datetime.now(timezone.utc).isoformat()
    try:
        while queue:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            node = get(url)["data"]
            if not node["attributes"]["public"]:
                raise ValueError("Project node is not public")
            children = listing(related(node, "children"))
            queue.extend(child["links"]["self"] for child in children)
            license_id = node["relationships"].get("license", {}).get("data", {}).get("id")
            if license_id and license_id not in licenses:
                lic = get(related(node, "license"))["data"]["attributes"]
                licenses[license_id] = {"name": lic["name"], "url": lic["url"]}
            nodes.append({"id": node["id"], "title": node["attributes"]["title"],
                          "url": node["links"]["html"], "license_id": license_id,
                          "date_modified": node["attributes"]["date_modified"],
                          "child_ids": [child["id"] for child in children]})
            providers = listing(related(node, "files"))
            folder_queue = [(provider, provider["attributes"]["name"]) for provider in providers]
            while folder_queue:
                folder, display_path = folder_queue.pop(0)
                rows = listing(related(folder, "files"))
                folders.append({"node": node["id"], "id": folder["id"],
                                "path": display_path, "entries": len(rows)})
                for row in rows:
                    attrs = row["attributes"]
                    path = display_path + "/" + attrs["name"]
                    if attrs["kind"] == "folder":
                        folder_queue.append((row, path))
                    else:
                        files.append({"node": node["id"], "node_title": node["attributes"]["title"],
                                      "id": row["id"], "path": path,
                                      "attributes": attrs, "links": row["links"],
                                      "metadata_url": row["links"].get("info", row["links"].get("self")),
                                      "node_license_id": license_id})
        result = {"complete": True, "started_utc": started,
                  "completed_utc": datetime.now(timezone.utc).isoformat(),
                  "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "nodes": nodes, "folders": folders, "files": files, "licenses": licenses,
                  "metadata_requests": records, "data_payload_downloaded": False,
                  "scope": "Public project and recursively listed child components/files; metadata snapshot, not file integrity verification."}
    except Exception as error:
        result = {"complete": False, "started_utc": started, "error": repr(error),
                  "nodes": nodes, "files": files, "metadata_requests": records}
        OUT.write_text(json.dumps(result, indent=2) + "\n")
        raise
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"complete": True, "nodes": len(nodes), "files": len(files),
                      "reported_total_bytes": sum(f["attributes"].get("size", 0) or 0 for f in files),
                      "files_summary": [{"node": f["node_title"], "path": f["path"],
                                         "size": f["attributes"].get("size")} for f in files]}, indent=2))


if __name__ == "__main__":
    main()
