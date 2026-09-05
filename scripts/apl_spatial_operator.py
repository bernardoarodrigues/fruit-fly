"""Exact static exponential-distance sums on APL forests.

Reference for Amin 2020 Eqs. 1-3; no cable branch-current balance, time dynamics,
reporter calibration, or transmitter release law is implied.
"""
import numpy as np


def split_at_attachments(parent, length, radius, edges, fractions):
    """Insert all contact projections, preserving linear taper and forest gaps."""
    parent=np.asarray(parent,dtype=np.int64)
    length=np.asarray(length,dtype=float)
    radius=np.asarray(radius,dtype=float)
    edges=np.asarray(edges,dtype=np.int64)
    fractions=np.asarray(fractions,dtype=float)
    n=len(parent)
    if length.shape!=(n,) or radius.shape!=(n,) or fractions.shape!=edges.shape:
        raise ValueError('Inconsistent array shapes')
    if not np.isfinite(length).all() or not np.isfinite(radius).all() or not np.isfinite(fractions).all():
        raise ValueError('Finite geometry required')
    if np.any(length<0) or np.any(radius<=0) or np.any((fractions<0)|(fractions>1)):
        raise ValueError('Positive radii, nonnegative lengths and fractions in [0,1] required')
    if np.any((parent<0)|(parent>=n)) or np.any((edges<0)|(edges>=n)):
        raise ValueError('Index outside forest')
    pp=parent.tolist(); ll=length.tolist(); rr=radius.tolist()
    nodes=np.empty(len(edges),dtype=np.int64)
    order=np.lexsort((fractions,edges))
    groups=np.split(order,np.flatnonzero(np.diff(edges[order]))+1) if len(order) else []
    for group in groups:
        child=int(edges[group[0]])
        p=int(parent[child])
        if child==p:
            nodes[group]=child
            continue
        t,inverse=np.unique(fractions[group],return_inverse=True)
        interior=t[(t>0)&(t<1)]
        new=np.arange(len(pp),len(pp)+len(interior),dtype=np.int64)
        chain=np.r_[child,new,p]
        coords=np.r_[0.,interior,1.]
        pp.extend([0]*len(new));ll.extend([0.]*len(new))
        rr.extend((radius[child]+interior*(radius[p]-radius[child])).tolist())
        for a,b,d in zip(chain[:-1],chain[1:],np.diff(coords)*length[child]):
            pp[a]=int(b);ll[a]=float(d)
        lookup=chain[np.searchsorted(coords,t)]
        nodes[group]=lookup[inverse]
    pp=np.array(pp,dtype=np.int64);ll=np.array(ll);rr=np.array(rr)
    traversal=forest_order(pp)
    return pp,ll,rr,nodes,traversal


def forest_order(parent):
    """Parent-before-child traversal; reject cycles instead of bridging them."""
    n=len(parent)
    children=[[] for _ in range(n)]
    roots=[]
    for i,p in enumerate(parent):
        if p==i: roots.append(i)
        else: children[p].append(i)
    stack=list(reversed(roots));order=[]
    while stack:
        i=stack.pop();order.append(i);stack.extend(reversed(children[i]))
    if len(order)!=n:
        raise ValueError('Parent array is not a rooted forest')
    return np.array(order,dtype=np.int64)


def electrotonic_lengths(parent,length,radius):
    """Integral dl/sqrt(r) for each linearly tapered segment, in sqrt(um).

    Rationalized expression handles equal or nearly equal endpoint radii.
    """
    return 2*np.asarray(length)/(np.sqrt(radius)+np.sqrt(np.asarray(radius)[parent]))


def exponential_sum(parent,order,metric_length,scale,mass):
    """Sum mass[j]*exp(-path_metric(i,j)/scale) over each component, O(N).

    mass may have multiple columns for separate finite input footprints.
    No row normalization or cross-component coupling is introduced.
    """
    metric_length=np.asarray(metric_length,dtype=float)
    mass=np.asarray(mass,dtype=float)
    if mass.shape[0]!=len(parent) or np.any(mass<0) or not np.isfinite(mass).all():
        raise ValueError('Finite nonnegative mass must match nodes')
    if np.any(metric_length<0) or not np.isfinite(metric_length).all() or not (scale>0):
        raise ValueError('Positive scale and nonnegative finite lengths required')
    q=np.exp(-metric_length/scale)
    down=mass.copy()
    for i in order[::-1]:
        p=parent[i]
        if p!=i: down[p]+=q[i]*down[i]
    total=down.copy()
    correction=-np.expm1(-2*metric_length/scale)
    for i in order:
        p=parent[i]
        if p!=i: total[i]=q[i]*total[p]+correction[i]*down[i]
    return total
