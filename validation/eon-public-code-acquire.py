"""Acquire public source/metadata only; never import or execute upstream code."""
from pathlib import Path
import datetime, hashlib, json, urllib.request
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'data/raw/eon-public-code'
OUT.mkdir(parents=True,exist_ok=True)
records=[]
def get(url,name):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'fruit-fly-research-read-only','Accept':'application/vnd.github+json'})
  with urllib.request.urlopen(req,timeout=40) as r:
   b=r.read(); status=r.status; headers=dict(r.headers); final=r.url
  p.write_bytes(b)
  rec={'url':url,'path':str(p.relative_to(BASE)),'status':status,'final_url':final,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'etag':headers.get('ETag'),'last_modified':headers.get('Last-Modified')}
  records.append(rec);return json.loads(b)
 except Exception as e:
  records.append({'url':url,'error':str(e)});raise
api='https://api.github.com'
org=get(api+'/orgs/eonsystemspbc/repos?per_page=100&type=public','org-repositories.json')
repo=get(api+'/repos/eonsystemspbc/fly-brain','repository.json')
heads=get(api+'/repos/eonsystemspbc/fly-brain/branches?per_page=100','branches.json')
releases=get(api+'/repos/eonsystemspbc/fly-brain/releases?per_page=100','releases.json')
tags=get(api+'/repos/eonsystemspbc/fly-brain/tags?per_page=100','tags.json')
head=get(api+'/repos/eonsystemspbc/fly-brain/commits/'+repo['default_branch'],'head-commit.json')
tree=get(api+'/repos/eonsystemspbc/fly-brain/git/trees/'+head['sha']+'?recursive=1','head-tree.json')
result={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Public GitHub metadata only. No upstream source code executed.','head_sha':head['sha'],'default_branch':repo['default_branch'],'tree_truncated':tree.get('truncated'),'records':records,'org_public_repositories':[x['full_name'] for x in org],'branches':[{k:x[k] for k in ('name','commit')} for x in heads],'releases_count':len(releases),'tags_count':len(tags)}
p=BASE/'validation/eon-public-code-acquisition.json'
if p.exists():raise FileExistsError(p)
p.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
print('\nTREE\n'+'\n'.join(x['path'] for x in tree['tree']))
