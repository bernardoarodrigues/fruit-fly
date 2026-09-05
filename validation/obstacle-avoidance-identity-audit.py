"""Read-only MaleCNS candidate joins; no receptor substitution or simulation."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]
folder=root/'data/processed/malecns_v1'
out=root/'validation/obstacle-avoidance-identities.json'
assert not out.exists()
neurons=pd.read_feather(folder/'neurons.feather')
ids=np.load(folder/'neuron_ids.npy');assert np.array_equal(ids,neurons.bodyId.to_numpy())
indptr=np.load(folder/'indptr.npy',mmap_mode='r');targets=np.load(folder/'targets.npy',mmap_mode='r')
contacts=np.load(folder/'contact_counts.npy',mmap_mode='r');weights=np.load(folder/'weights.npy',mmap_mode='r')
fields=['bodyId','type','flywireType','mancType','synonyms','somaSide','rootSide','entryNerve','class','subclass','consensus_nt','model_sign']
types=['AN17A026','MDN','DNa02','DNg13','LC16','LC4','LPLC2','DNp01','LBL40']
groups={}
for kind in types:
    selected=neurons.type.eq(kind)
    table=neurons.loc[selected,fields].copy();table['graph_index']=np.flatnonzero(selected)
    groups[kind]=json.loads(table.to_json(orient='records'))
mdn=np.flatnonzero(neurons.type.eq('MDN'));tlai=np.flatnonzero(neurons.type.eq('AN17A026'))
edges=[];sensory=[]
for pre in tlai:
    for post in mdn:
        a,b=int(indptr[pre]),int(indptr[pre+1]);matches=np.flatnonzero(targets[a:b]==post)+a
        assert len(matches)<=1
        edges.append({'pre_id':int(ids[pre]),'post_id':int(ids[post]),'pre_index':int(pre),'post_index':int(post),
            'contacts':int(contacts[matches[0]]) if len(matches) else 0,'signed_weight_mv':float(weights[matches[0]]) if len(matches) else 0.})
    edge_indices=np.flatnonzero(targets==pre);sources=np.searchsorted(indptr,edge_indices,side='right')-1
    for source,index in zip(sources,edge_indices):
        row=neurons.iloc[source]
        if not str(row['class']).startswith('mechanosensory'):continue
        item=json.loads(row[fields].to_json());item.update(graph_index=int(source),target_tla_id=int(ids[pre]),contacts=int(contacts[index]),signed_weight_mv=float(weights[index]))
        sensory.append(item)
result={'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [folder/x for x in ['neurons.feather','neuron_ids.npy','indptr.npy','targets.npy','contact_counts.npy','weights.npy','manifest.json']]},
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'selection':'Exact processed type equality; TLA additionally has source synonym Sen 2019: TwoLumps Ascending (TLA). No substring populations promoted.',
    'groups':groups,'tla_to_mdn_all_eight_pairs':edges,'tla_direct_mechanosensory_inputs':sensory,
    'missing_exact_labels':['LUL130','Pair1','MAN'],'missing_note':'No exact match in type/mancType/flywireType/synonyms tokens was established; do not substitute related labels.',
    'scope':'Candidate identities and structural edges only. Entry nerve or broad mechanosensory class does not establish individual bristle site, NOMPC-driver membership, receptor transfer, firing physiology or behavioral sufficiency.',
    'runtime_changes':False,'simulated_steps':0}
out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({'groups':{k:len(v) for k,v in groups.items()},'tla_mdn_contacts':sum(x['contacts'] for x in edges),'direct_mechanosensory_rows':len(sensory)}))
