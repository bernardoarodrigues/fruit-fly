#!/usr/bin/env python3
"""Acquire two declared public supplements; retain challenges/failures verbatim."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,urllib.request,urllib.error,zipfile,io
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data/raw/kc-reporter-data';RECEIPT=ROOT/'validation/kc-reporter-workbook-acquisition.json'
def main():
    if RECEIPT.exists():raise FileExistsError('Preserve first acquisition')
    DEST.mkdir(parents=True,exist_ok=True);rows=[]
    urls=['https://pmc.ncbi.nlm.nih.gov/articles/instance/9613607/bin/NIHMS1837499-supplement-1.xlsx','https://pmc.ncbi.nlm.nih.gov/articles/instance/9613607/bin/NIHMS1837499-supplement-Table_S1.xlsx']
    for url in urls:
        row=dict(url=url,requested_utc=datetime.now(timezone.utc).isoformat(),acquired_xlsx=False);payload=None
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'fruit-fly-research/1.0'})
            with urllib.request.urlopen(request,timeout=45) as response:
                row.update(status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type'));payload=response.read(40*1024**2+1)
            if len(payload)>40*1024**2:raise ValueError('Declared40MiB acquisition limit exceeded')
            if zipfile.is_zipfile(io.BytesIO(payload)):
                with zipfile.ZipFile(io.BytesIO(payload)) as z:row['acquired_xlsx']='xl/workbook.xml' in z.namelist() and '[Content_Types].xml' in z.namelist()
            path=DEST/(url.rsplit('/',1)[-1]+('' if row['acquired_xlsx'] else '.response'))
            with path.open('xb') as f:f.write(payload)
            row.update(path=str(path.relative_to(ROOT)),bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
        except Exception as e:row['error']=dict(type=type(e).__name__,message=str(e))
        rows.append(row)
    result=dict(completed_utc=datetime.now(timezone.utc).isoformat(),attempts=rows,all_workbooks_acquired=all(r['acquired_xlsx'] for r in rows),source_file=dict(path=str(Path(__file__).relative_to(ROOT)),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    with RECEIPT.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
if __name__=='__main__':main()
