"""Acquire/parse notebook source cells only. No notebook executes."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,urllib.request
BASE=Path(__file__).resolve().parents[1];OUT=BASE/'data/raw/eon-public-code';records=[]
jobs=[]
for repo in ['fly-brain','flybody','drosophila_brain_model_lif']:
 h=json.loads((OUT/('head-commit.json' if repo=='fly-brain' else repo+'/head-commit.json')).read_text())
 t=json.loads((OUT/('head-tree.json' if repo=='fly-brain' else repo+'/head-tree.json')).read_text())
 for x in t['tree']:
  if x['path'].endswith('.ipynb'):jobs.append((repo,h['sha'],x['path']))
def fetch(job):
 repo,sha,path=job;url=f'https://raw.githubusercontent.com/eonsystemspbc/{repo}/{sha}/{path}'
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'fruit-fly-research-read-only'}),timeout=40) as r:b=r.read()
 p=OUT/repo/'source'/path;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 p.write_bytes(b);j=json.loads(b)
 source='\n\n'.join(f"# CELL {i} {c['cell_type']}\n"+''.join(c['source']) for i,c in enumerate(j['cells']))
 dest=p.with_suffix('.cells.txt');dest.write_text(source)
 return {'url':url,'path':str(p.relative_to(BASE)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'source_cells_path':str(dest.relative_to(BASE)),'source_cells_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'cells':len(j['cells'])}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex: records=list(ex.map(fetch,jobs))
r={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Inert notebook bytes and source text only; outputs not interpreted, no upstream code executed.','records':records}
p=BASE/'validation/eon-public-code-notebook-acquisition.json'
if p.exists():raise FileExistsError(p)
p.write_text(json.dumps(r,indent=2)+'\n');print(len(records))
