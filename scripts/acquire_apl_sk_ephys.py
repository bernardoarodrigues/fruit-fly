#!/usr/bin/env python3
"""Acquire the public electrophysiology archive, validating its published MD5."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,urllib.request,time
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'data/raw/apl-sk-electrophysiology'
record=folder/'zenodo-record.json'
metadata=json.loads(record.read_text())
f=next(x for x in metadata['files'] if x['key']=='Ephys_sparse coding.zip')
final=folder/f['key'];partial=folder/(f['key']+'.part')
receipt=ROOT/'validation/apl-sk-ephys-acquisition.json'
if final.exists() or partial.exists() or receipt.exists():raise FileExistsError('Preserve existing download or partial; inspect before resuming')
md5=hashlib.md5();sha=hashlib.sha256();size=0;start=time.perf_counter()
with urllib.request.urlopen(f['links']['self'],timeout=60) as response,partial.open('xb') as out:
    if response.status!=200:raise ValueError(response.status)
    while block:=response.read(4*1024*1024):
        out.write(block);md5.update(block);sha.update(block);size+=len(block)
assert size==f['size'],(size,f['size'])
assert 'md5:'+md5.hexdigest()==f['checksum']
partial.rename(final)
result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),record_id=18644411,doi=metadata['metadata']['doi'],license=metadata['metadata']['license'],
    archive=dict(path=str(final.relative_to(ROOT)),url=f['links']['self'],bytes=size,md5=md5.hexdigest(),sha256=sha.hexdigest()),
    source_metadata=dict(path=str(record.relative_to(ROOT)),sha256=hashlib.sha256(record.read_bytes()).hexdigest()),
    paper=dict(path='data/raw/apl-sk-electrophysiology/chen-2026.pdf',url='https://eprints.whiterose.ac.uk/id/eprint/239294/1/1-s2.0-S0960982226002058-main.pdf',sha256=hashlib.sha256((folder/'chen-2026.pdf').read_bytes()).hexdigest()),
    wall_seconds=time.perf_counter()-start,failed_source_access=[dict(url='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13075853/fullTextXML',status=404)],
    scope='Complete electrophysiology ZIP acquired. No imaging or behavioral ZIP downloaded; no claim of physiological analysis at acquisition.')
with receipt.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
print(json.dumps(result,indent=2))
