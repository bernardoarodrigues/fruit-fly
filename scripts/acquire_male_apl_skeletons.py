#!/usr/bin/env python3
"""Acquire the two public native-coordinate MaleCNS v1.0 APL skeletons."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'data/raw/male-apl-skeletons'
OUT = ROOT/'validation/male-apl-skeleton-acquisition.json'
OBJECTS = [(10540, '1777993070926297', 1565689, '6ca0f2485e8191bd647b9f296ff5a5a6'),
           (10977, '1777993083355148', 1616710, '9e71ed407e77d3036842b3ebac2789c6')]


def main():
    if OUT.exists():
        raise FileExistsError('Preserve first acquisition')
    DEST.mkdir(parents=True, exist_ok=True)
    rows = []
    for body, generation, size, md5 in OBJECTS:
        path = DEST/f'{body}.swc'
        if path.exists():
            raise FileExistsError(path)
        url = f'https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/{body}.swc'
        req = urllib.request.Request(url+'?generation='+generation,
                                     headers={'If-Match': '"'+md5+'"', 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 200
            assert response.headers['x-goog-generation'] == generation
            payload = response.read(size+1)
            assert len(payload) == size
            assert hashlib.md5(payload).hexdigest() == md5
        payload.decode('utf-8')
        with path.open('xb') as f:
            f.write(payload)
        rows.append(dict(body_id=body,url=url,generation=generation,bytes=size,md5=md5,
                         sha256=hashlib.sha256(payload).hexdigest(),path=str(path.relative_to(ROOT))))
    receipt = dict(completed_utc=datetime.now(timezone.utc).isoformat(),objects=rows,
                   dataset='male-cns:v1.0',coordinates='Native MaleCNS EM, 8 nm units',
                   mirrored=False,license='CC-BY',
                   documentation='https://male-cns.janelia.org/download/',
                   source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with OUT.open('x') as f:
        json.dump(receipt,f,indent=2); f.write('\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()
