"""Declared nearby-branch stress test; not a probabilistic anatomy correction."""
import numpy as np


def node_distances(forest, i, j):
    """Vectorized forest paths using the existing binary ancestor table."""
    i,j=np.broadcast_arrays(np.asarray(i,dtype=np.int64),np.asarray(j,dtype=np.int64))
    a=i.copy();b=j.copy()
    swap=forest.depth[a]<forest.depth[b]
    a,b=np.where(swap,b,a),np.where(swap,a,b)
    delta=forest.depth[a]-forest.depth[b]
    for k in range(len(forest.up)):
        a=np.where((delta & (1<<k))!=0,forest.up[k,a],a)
    for k in reversed(range(len(forest.up))):
        different=forest.up[k,a]!=forest.up[k,b]
        a,b=np.where(different,forest.up[k,a],a),np.where(different,forest.up[k,b],b)
    ancestor=np.where(a==b,a,forest.parent[a])
    d=forest.root_distance[i]+forest.root_distance[j]-2*forest.root_distance[ancestor]
    return np.where(forest.component[i]==forest.component[j],d,np.inf)


def attachment_distances(forest, ei, ti, ej, tj):
    p=forest.parent;l=forest.length
    values=[]
    for a,x in [(ei,ti*l[ei]),(p[ei],(1-ti)*l[ei])]:
        for b,y in [(ej,tj*l[ej]),(p[ej],(1-tj)*l[ej])]:
            values.append(x+y+node_distances(forest,a,b))
    return np.where(ei==ej,np.abs(ti-tj)*l[ei],np.minimum.reduce(values))


def nearby_nonlocal(forest, points, original_edge, original_fraction, original_residual,
                    envelope_um, separation_um, chunk_size=2048):
    """Closest eligible projection within residual+envelope, same component.

    Eligible means geodesic separation >= separation_um. The envelope is a
    declared sensitivity magnitude, not an estimated confidence interval.
    Unchanged when none qualifies; candidates include every native segment.
    """
    if envelope_um<0 or separation_um<=0 or chunk_size<=0:
        raise ValueError('Nonnegative envelope and positive separation/chunk required')
    edge=original_edge.copy();fraction=original_fraction.copy();residual=original_residual.copy()
    separation=np.zeros(len(points));count=np.zeros(len(points),dtype=np.int64)
    for lo in range(0,len(points),chunk_size):
        hi=min(lo+chunk_size,len(points))
        candidates=forest.center_tree.query_ball_point(points[lo:hi],
                        original_residual[lo:hi]+envelope_um+forest.length.max()/2+1e-9)
        sizes=np.array([len(c) for c in candidates])
        row=np.repeat(np.arange(lo,hi),sizes)
        seg=np.concatenate(candidates).astype(np.int64)
        start=forest.xyz[seg];vector=forest.xyz[forest.parent[seg]]-start
        square=np.einsum('ij,ij->i',vector,vector)
        dot=np.einsum('ij,ij->i',points[row]-start,vector)
        t=np.clip(np.divide(dot,square,out=np.zeros_like(dot),where=square>0),0,1)
        dist=np.linalg.norm(points[row]-start-t[:,None]*vector,axis=1)
        valid=(dist<=original_residual[row]+envelope_um+1e-12) & (forest.component[seg]==forest.component[original_edge[row]])
        row,seg,t,dist=row[valid],seg[valid],t[valid],dist[valid]
        d=attachment_distances(forest,original_edge[row],original_fraction[row],seg,t)
        valid=d>=separation_um
        row,seg,t,dist,d=row[valid],seg[valid],t[valid],dist[valid],d[valid]
        if len(row)==0: continue
        count+=np.bincount(row,minlength=len(points))
        order=np.lexsort((seg,dist,row))
        first=order[np.r_[True,np.diff(row[order])!=0]]
        ids=row[first]
        edge[ids]=seg[first];fraction[ids]=t[first];residual[ids]=dist[first];separation[ids]=d[first]
    return edge,fraction,residual,separation,count
