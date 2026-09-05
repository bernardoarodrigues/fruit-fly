"""Static AST extraction of literal source assignments. Never imports upstream code."""
from pathlib import Path
import ast,datetime,hashlib,json
BASE=Path(__file__).resolve().parents[1];RAW=BASE/'data/raw/eon-public-code'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def val(n,env):
 if isinstance(n,ast.Constant):return n.value
 if isinstance(n,ast.Name):return env[n.id]
 if isinstance(n,(ast.List,ast.Tuple)):return [val(x,env) for x in n.elts]
 if isinstance(n,ast.Dict):return {val(k,env):val(v,env) for k,v in zip(n.keys,n.values)}
 if isinstance(n,ast.BinOp):
  a,b=val(n.left,env),val(n.right,env)
  if isinstance(n.op,ast.Add):return a+b
  if isinstance(n.op,ast.Mult):return a*b
 if isinstance(n,ast.Subscript):return val(n.value,env)[val(n.slice,env)]
 raise ValueError(type(n).__name__)
def notebook(repo,path):
 p=RAW/repo/'source'/path;j=json.loads(p.read_text());env={'Hz':1,'params':{}};assignments=[];calls=[]
 for ci,c in enumerate(j['cells']):
  if c['cell_type']!='code':continue
  source=''.join(c['source']);source='\n'.join(l for l in source.splitlines() if not l.startswith(('%','!','pip ')))
  try: tree=ast.parse(source)
  except SyntaxError:continue
  for node in tree.body:
   if isinstance(node,ast.Assign):
    try:v=val(node.value,env)
    except (KeyError,ValueError,TypeError):continue
    for target in node.targets:
     if isinstance(target,ast.Name):env[target.id]=v;assignments.append({'cell_index':ci,'name':target.id,'value':v})
     elif isinstance(target,ast.Tuple):
      for t,x in zip(target.elts,v):env[t.id]=x;assignments.append({'cell_index':ci,'name':t.id,'value':x})
     elif isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id=='params':env['params'][val(target.slice,env)]=v
   elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='run_exp':
    call={'cell_index':ci,'source':ast.get_source_segment(source,node),'params_rates_Hz':dict(env['params'])}
    for k in node.value.keywords:
     if k.arg in ('exp_name','neu_exc','neu_exc2','neu_slnc'):
      try:call[k.arg]=val(k.value,env)
      except (KeyError,ValueError,TypeError):call[k.arg]={'unresolved':ast.unparse(k.value)}
    calls.append(call)
 return {'path':str(p.relative_to(BASE)),'sha256':sha(p),'source_assignments':assignments,'experiments':calls,'output_neurons':env.get('output_neurons'),'named_output_ids':{k:v for k,v in env.items() if isinstance(v,int) and v>10**15},'config':env.get('config')}
p=RAW/'fly-brain/source/code/benchmark.py';tree=ast.parse(p.read_text());experiments=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXPERIMENTS' for t in n.targets))
notebooks=[notebook('fly-brain','code/paper-phil-drosophila/example.ipynb'),notebook('drosophila_brain_model_lif','results/eon_1/demo_notebook.ipynb')]
def group(nb,name):return next(x['value'] for x in nb['source_assignments']if x['name']==name)
sugar_b=set(experiments['sugar']['neu_exc']);sugar_n=set(group(notebooks[0],'sugar_GRNs'))
r={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Static AST literal/name/list addition and Hz scalar assignment extraction only; no upstream import, eval, exec, notebook execution or simulation. Hz treated as 1 only to label source rate magnitudes. Cells zero-indexed. Unknown dynamic expressions are skipped, not executed.','benchmark':{'path':str(p.relative_to(BASE)),'sha256':sha(p),'experiments':experiments},'notebooks':notebooks,'sugar_list_difference':{'benchmark_count':len(sugar_b),'notebook_count':len(sugar_n),'notebook_only':sorted(sugar_n-sugar_b),'benchmark_only':sorted(sugar_b-sugar_n)},'model_source_constants':{'voltage_rest_reset_mV':-52,'threshold_strictly_greater_mV':-45,'tau_mem_ms':20,'tau_syn_ms':5,'refractory_ms':2.2,'delay_ms':1.8,'contact_weight_mV':0.275,'poisson_scale':250,'derived_direct_voltage_jump_mV':68.75,'source_notebook_default_trial_duration_ms':1000,'source_notebook_default_trials':30,'source_notebook_rate_estimator':'utils.get_rate divides trial spike counts by full t_run, then groups mean/std; no online motor filter'} }
o=BASE/'validation/eon-public-code-extracted.json'
if o.exists():raise FileExistsError(o)
o.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r['sugar_list_difference']))
for nb in notebooks:
 print(nb['path'],'outputs',len(nb['output_neurons']))
 for c in nb['experiments']:print(c['cell_index'],c.get('exp_name'),'n1',len(c.get('neu_exc',[])),'n2',len(c.get('neu_exc2',[])),c['params_rates_Hz'])
