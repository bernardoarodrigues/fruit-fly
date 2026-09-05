"""Save bounded public release/tree comparisons, no upstream execution."""
from pathlib import Path
import datetime,hashlib,json,urllib.request
B=Path(__file__).resolve().parents[1];O=B/'data/raw/eon-public-code';records=[]
def get(url,name):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'fruit-fly-research-read-only'}),timeout=40) as r:b=r.read()
  p.write_bytes(b);records.append({'url':url,'path':str(p.relative_to(B)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return json.loads(b)
 except Exception as e:records.append({'url':url,'error':str(e)});return None
m=json.loads((O/'flybody/repository.json').read_text());c=get('https://api.github.com/repos/TuragaLab/flybody/compare/'+m['parent']['default_branch']+'...eonsystemspbc:main','flybody/upstream-comparison.json')
summary={'flybody_upstream_comparison':None}
if c:summary['flybody_upstream_comparison']={k:c.get(k) for k in ['status','ahead_by','behind_by','total_commits']};summary['flybody_upstream_comparison']['commits']=[{'sha':x['sha'],'message':x['commit']['message']}for x in c['commits']];summary['flybody_upstream_comparison']['files']=[x['filename']for x in c.get('files',[])]
# Branches are enumerated so the scope does not silently claim only main exists.
branches=json.loads((O/'pathintegrationBPU/branches.json').read_text());bs=[]
for branch in branches:
 if branch['name']=='main':continue
 sha=branch['commit']['sha'];t=get('https://api.github.com/repos/eonsystemspbc/pathintegrationBPU/git/trees/'+sha+'?recursive=1','pathintegrationBPU/branch-'+sha[:12]+'-tree.json')
 if t:bs.append({'name':branch['name'],'sha':sha,'truncated':t['truncated'],'file_count':sum(x['type']=='blob' for x in t['tree']),'embodiment_named_paths':[x['path'] for x in t['tree'] if any(k in x['path'].lower() for k in ['embod','forag','mujoco','flygym','neuromech'])]})
summary['pathintegration_other_branches_tree_only']=bs
summary['records']=records;summary['created_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();summary['scope']='Read-only GitHub metadata. Non-main BPU branch trees inventoried, not full content audited. No simulation.'
p=B/'validation/eon-public-code-scope.json'
if p.exists():raise FileExistsError(p)
p.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
