"""Download pinned public source as inert bytes; no upstream imports/execution."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,urllib.request
BASE=Path(__file__).resolve().parents[1];OUT=BASE/'data/raw/eon-public-code';records=[]
def get(url,name,parse=True):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'fruit-fly-research-read-only'}),timeout=40) as r:b=r.read();status=r.status
  p.write_bytes(b);rec={'url':url,'path':str(p.relative_to(BASE)),'status':status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};records.append(rec)
  return json.loads(b) if parse else b
 except Exception as e:records.append({'url':url,'error':str(e)});return None
api='https://api.github.com/repos/eonsystemspbc/'
metas=[]
for repo in ['flybody','drosophila_brain_model_lif','pathintegrationBPU']:
 m=get(api+repo,repo+'/repository.json')
 h=get(api+repo+'/commits/'+m['default_branch'],repo+'/head-commit.json')
 t=get(api+repo+'/git/trees/'+h['sha']+'?recursive=1',repo+'/head-tree.json')
 branches=get(api+repo+'/branches?per_page=100',repo+'/branches.json')
 releases=get(api+repo+'/releases?per_page=100',repo+'/releases.json')
 metas.append({'repo':repo,'sha':h['sha'],'commit_date':h['commit']['committer']['date'],'tree_truncated':t['truncated'],'parent':m.get('parent',{}).get('full_name'),'branches':branches,'releases_count':len(releases)})
 if repo=='flybody':
  paths=[x['path'] for x in t['tree'] if x['type']=='blob' and x['path'].endswith(('.py','.md','.toml','.yml','.yaml'))]
 else:paths=[x['path'] for x in t['tree'] if x['type']=='blob' and x['path'].endswith(('.py','.md','.txt','.yml','.yaml'))]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
  list(ex.map(lambda path:get(f'https://raw.githubusercontent.com/eonsystemspbc/{repo}/{h["sha"]}/{path}',repo+'/source/'+path,False),paths))
h=json.loads((OUT/'head-commit.json').read_text());t=json.loads((OUT/'head-tree.json').read_text())
paths=[x['path'] for x in t['tree'] if x['type']=='blob' and (x['path'].endswith(('.py','.md','.yml','.cu','.h')) or x['path'].endswith('LICENSE'))]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 list(ex.map(lambda path:get(f'https://raw.githubusercontent.com/eonsystemspbc/fly-brain/{h["sha"]}/{path}','fly-brain/source/'+path,False),paths))
r={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Pinned inert source bytes only; no upstream imports or execution. CSV, parquet, pickle, notebook and model assets not loaded.','repo_metadata':metas,'records':sorted(records,key=lambda x:x['url'])}
p=BASE/'validation/eon-public-code-source-acquisition.json'
if p.exists():raise FileExistsError(p)
p.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(metas,indent=2));print('Records',len(records),'errors',[x for x in records if 'error'in x])
