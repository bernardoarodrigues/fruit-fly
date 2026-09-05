"""Acquire exact manifest-listed FlyBody files into durable ignored storage.

Use --from-local for an already acquired checkout. Otherwise fetch each pinned
raw GitHub object. Existing different files are rejected, never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'validation/flybody-source-manifest.json'


def verified_bytes(data, item):
    blob = b'blob ' + str(len(data)).encode() + b'\0' + data
    if (len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']
            or hashlib.sha1(blob).hexdigest() != item['git_blob_sha1']):
        raise ValueError(f"Source bytes differ from pinned manifest: {item['path']}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-local', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/raw/flybody/source')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    acquired = skipped = size = 0
    for item in manifest['files']:
        relative = PurePosixPath(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe manifest path')
        dest = args.output / relative
        if dest.exists():
            verified_bytes(dest.read_bytes(), item)
            skipped += 1
        else:
            if args.from_local:
                data = verified_bytes((args.from_local / relative).read_bytes(), item)
            else:
                url = f"https://raw.githubusercontent.com/TuragaLab/flybody/{manifest['source_commit']}/{relative}"
                with urllib.request.urlopen(url, timeout=60) as response:
                    data = verified_bytes(response.read(item['bytes'] + 1), item)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as handle:
                temporary = Path(handle.name)
                try:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                    # An exclusive hard link publishes complete bytes without
                    # replacing a file created concurrently by another process.
                    os.link(temporary, dest)
                finally:
                    temporary.unlink(missing_ok=True)
            acquired += 1
        size += item['bytes']
    receipt = {'source_commit': manifest['source_commit'],
        'source_manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        'output': str(args.output.resolve()), 'files_verified': len(manifest['files']),
        'verified_bytes': size, 'files_acquired': acquired, 'files_already_present': skipped,
        'method': 'verified local copy' if args.from_local else 'pinned raw GitHub objects',
        'verification': 'size, SHA256 and Git blob SHA1 for every manifest-listed file',
        'source_and_assets_modified': False}
    (args.output / 'LOCAL-ACQUISITION.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
