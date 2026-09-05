#!/usr/bin/env python3
"""Acquire the exact public v1.0 synaptic-partner object, with resumable bytes."""
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/syn-partners-male-cns-v1.0-minconf-0.5.feather'
GENERATION = '1780494942562468'
SIZE = 6777179098
MD5 = '58efcf712f8c4d4de5f2ad51e97def76'
ETAG = '"' + MD5 + '"'
DEST = ROOT / 'data/raw/pn-kc-apl-compartment/syn-partners-male-cns-v1.0-minconf-0.5.feather'
PART = DEST.with_suffix('.feather.partial')
RECEIPT = ROOT / 'validation/malecns-synaptic-partners-acquisition.json'
LOG = ROOT / 'data/raw/pn-kc-apl-compartment/syn-partners-acquisition-attempts.jsonl'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def log(value):
    with LOG.open('a') as f:
        f.write(json.dumps(dict(utc=stamp(), **value)) + '\n')


def main():
    if RECEIPT.exists():
        raise FileExistsError('Acquisition already has a receipt; preserve it')
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(URL, method='HEAD'), timeout=30) as response:
        headers = {k.lower(): v for k, v in response.headers.items()}
    expected_md5_b64 = base64.b64encode(bytes.fromhex(MD5)).decode()
    if (headers.get('x-goog-generation') != GENERATION or int(headers['content-length']) != SIZE
            or headers.get('etag') != ETAG or headers.get('x-goog-hash') != 'md5=' + expected_md5_b64):
        raise ValueError('Remote object does not match frozen release identity')
    log(dict(event='remote_identity_verified', url=URL, generation=GENERATION, size=SIZE, etag=ETAG))
    start = time.perf_counter()
    if not DEST.exists():
        for attempt in range(1, 6):
            offset = PART.stat().st_size if PART.exists() else 0
            if offset == SIZE:
                break
            if offset > SIZE:
                raise ValueError('Partial file is larger than source')
            request_headers = {'If-Match': ETAG, 'Accept-Encoding': 'identity'}
            if offset:
                request_headers['Range'] = f'bytes={offset}-'
            log(dict(event='download_start', attempt=attempt, offset=offset))
            try:
                request = urllib.request.Request(URL + '?generation=' + GENERATION, headers=request_headers)
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.headers.get('x-goog-generation') != GENERATION or response.headers.get('ETag') != ETAG:
                        raise ValueError('GET object identity changed')
                    if offset:
                        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {offset}-{SIZE-1}/{SIZE}':
                            raise ValueError('Range response does not begin at existing offset')
                    elif response.status != 200:
                        raise ValueError('Full response was not HTTP200')
                    received = offset
                    with PART.open('ab' if offset else 'xb') as f:
                        while block := response.read(4 * 1024**2):
                            if received + len(block) > SIZE:
                                raise ValueError('Response exceeds declared source size')
                            f.write(block)
                            received += len(block)
                log(dict(event='download_response_end', attempt=attempt, bytes=received))
                if received != SIZE:
                    raise IOError('Short response')
                break
            except Exception as exc:
                log(dict(event='download_error', attempt=attempt, error=repr(exc), retained_partial_bytes=PART.stat().st_size if PART.exists() else 0))
                if attempt == 5:
                    raise
                time.sleep(2)
        target = PART
    else:
        target = DEST
    md5 = hashlib.md5(); sha = hashlib.sha256()
    with target.open('rb') as f:
        while block := f.read(8 * 1024**2):
            md5.update(block); sha.update(block)
    if target.stat().st_size != SIZE or md5.hexdigest() != MD5:
        log(dict(event='checksum_failure', file=str(target.relative_to(ROOT)), bytes=target.stat().st_size, md5=md5.hexdigest(), sha256=sha.hexdigest()))
        raise ValueError('Downloaded size/MD5 does not match public object')
    if target == PART:
        PART.rename(DEST)
    value = dict(schema=1, completed_utc=stamp(), passed=True, url=URL, generation=GENERATION, etag=ETAG,
                 expected_md5=MD5, actual_md5=md5.hexdigest(), path=str(DEST.relative_to(ROOT)), bytes=SIZE,
                 sha256=sha.hexdigest(), elapsed_seconds=time.perf_counter()-start,
                 downloader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 log_path=str(LOG.relative_to(ROOT)), log_sha256=hashlib.sha256(LOG.read_bytes()).hexdigest(),
                 scope='Whole public source downloaded and checksum verified; no anatomical reduction yet',
                 license='CC-BY, MaleCNS v1.0; https://male-cns.janelia.org/download/')
    with RECEIPT.open('x') as f:
        json.dump(value, f, indent=2); f.write('\n')
    print(json.dumps(value), flush=True)


if __name__ == '__main__':
    main()
