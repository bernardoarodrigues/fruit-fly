#!/usr/bin/env python3
"""H1-only contact-weight diagnostic, derived from the frozen panel dispatcher.

Graph arrays remain unchanged. Retained float64 weights apply only at delayed
arrival in the declared half-open window. No receptor or anatomical inference.
"""
import hashlib
from pathlib import Path
import numpy as np
import navigation_mbon_intervention_kernel as prior

original=prior.original
DERIVATION=[]
def replace(source,label,old,new):
    if source.count(old)!=1:raise RuntimeError('Source anchor mismatch: '+label)
    DERIVATION.append(dict(label=label,old=old,new=new,replacement_count=1))
    return source.replace(old,new,1)
run=prior._extract('_run')
run=replace(run,'arguments','selected_column, log_events, event_mask):','selected_column, log_events, event_mask, modified, retained, window_start, window_end):')
run=replace(run,'telemetry','edge_counts = np.zeros((nsteps, 4, 3), np.int64)','edge_counts = np.zeros((nsteps, 4, 3), np.int64)\n    changed_counts = np.zeros((nsteps, 2), np.int64)\n    removed_sum = np.zeros(nsteps, np.float64)')
old='''                        else:
                            s[target] += weight
                        edge_counts[k, 1, sign] += 1
                        disposition = 0'''
new='''                        else:
                            if modified[edge] and window_start <= tick < window_end:
                                s[target] += retained[edge]
                                changed_counts[k, 0 if retained[edge] == 0. else 1] += 1
                                removed_sum[k] += weight - retained[edge]
                            else:
                                s[target] += weight
                        edge_counts[k, 1, sign] += 1
                        disposition = 3 if modified[edge] and window_start <= tick < window_end else 0'''
run=replace(run,'eligible_positive_delivery',old,new)
run=replace(run,'return','ref_found, ref_ticks, ref_cells, ref_values,\n            tick_ref_found, tick_ref_ticks, tick_ref_cells, tick_ref_values)','ref_found, ref_ticks, ref_cells, ref_values,\n            tick_ref_found, tick_ref_ticks, tick_ref_cells, tick_ref_values, changed_counts, removed_sum)')
namespace=dict(vars(original));namespace.update(__name__=__name__,__file__=__file__)
exec(compile('@njit(cache=False)\n'+run,__file__,'exec'),namespace)
advance=prior._extract('advance','FactorialNetwork')
advance=replace(advance,'advance_call','bool(log_selected_events),event_mask)','bool(log_selected_events),event_mask,self._modified,self._retained,self._window_start,self._window_end)')
advance=replace(advance,'unpack','rf,rt,ri,rv,tf,ttick,ti,tv) = values','rf,rt,ri,rv,tf,ttick,ti,tv,changed_counts,removed_sum) = values')
advance=replace(advance,'sidecar','return result','''self.last_contact_intervention = dict(start_tick=start,end_tick=self.tick,counts=changed_counts[:done],removed_weight_sum=removed_sum[:done],partial=dict(counts=changed_counts[done].copy(),removed_weight_sum=float(removed_sum[done]),validity="Only operations through failure.phase completed") if code else None)
    if np.any(changed_counts):
        result["schema"]["dispositions"] = dict(DISPOSITIONS, contact_weight_modified=3)
    return result''')
exec(compile(advance,__file__,'exec'),namespace)
_advance=namespace['advance']

def source_derivation():
    return dict(base_sha256=prior.BASE_SHA256,solver_sha256=prior.SOLVER_SHA256,checkpoint_helper=prior.source_derivation(),patches=DERIVATION,
        derived_run_sha256=hashlib.sha256(run.encode()).hexdigest(),derived_advance_sha256=hashlib.sha256(advance.encode()).hexdigest(),derived_numba_cache=False)

class GammaContactNetwork(prior.EdgeDeliveryInterventionNetwork):
    def __init__(self,neuron_ids,indptr,targets,weights,arm,input_indices,selected_indices,seed=11,*,modified_edge_indices=(),retained_weights=(),delivery_window=None):
        # Inherit validated checkpoint restoration/observation relabeling, with
        # the old whole-edge suppression feature disabled.
        super().__init__(neuron_ids,indptr,targets,weights,arm,input_indices,selected_indices,seed)
        edges=self._integers(modified_edge_indices,np.int64,'modified edges').copy()
        values=np.asarray(retained_weights,dtype=np.float64).copy()
        if values.shape!=edges.shape or len(np.unique(edges))!=len(edges) or ((edges<0)|(edges>=self.n_edges)).any():raise ValueError('Invalid edge/weight shape or identity')
        if not np.isfinite(values).all() or (values<0).any() or (self.weights[edges]<=0).any() or (values>=self.weights[edges].astype(np.float64)).any():raise ValueError('Require a strict reduction of positive weights only')
        if delivery_window is None:
            if len(edges):raise ValueError('Nonempty intervention requires a delivery window')
            start=end=0
        else:
            if not isinstance(delivery_window,(tuple,list)) or len(delivery_window)!=2:raise ValueError('Expected half-open tick pair')
            start,end=[self._tick_integer(t,'delivery tick') for t in delivery_window]
            if end<=start:raise ValueError('Empty delivery window')
        self._modified=np.zeros(self.n_edges,np.bool_);self._modified[edges]=True
        self._retained=np.zeros(self.n_edges,np.float64);self._retained[edges]=values
        for a in [edges,values,self._modified,self._retained]:a.flags.writeable=False
        self.modified_edge_indices,self.retained_weights=edges,values
        self._window_start,self._window_end=start,end
        self.last_contact_intervention=None

    def intervention_specification(self):
        return dict(version=1,graph_sha256=self.graph_sha256,modified_edge_indices=self.modified_edge_indices.copy(),retained_weights=self.retained_weights.copy(),delivery_window_ticks=[self._window_start,self._window_end],
            semantics='Positive pair contribution replaced at eligible delayed arrival only. The graph weight remains original; archive and apply this experiment specification separately.',
            counters='Base accepted/visited counters retain original graph sign and count the delivery even when retained contribution is zero. Sidecar counts split zero and partial retained weights; selected-event disposition3 identifies changed deliveries. Complete affected arrival identities are reconstructible from original queues and full spike histories, not stored as a second huge event stream.',
            count_columns=['zero_retained','partial_retained'],removed_weight_sum='Sum of original float64(pair_weight)-retained_weight in original source/CSR delivery order; p-state units, not h or voltage.',
            physiology='No biological ablation, sign flip or calibrated GPCR law; no promotion.')

    def advance(self,uniforms,probabilities,*,log_selected_events=False,event_indices=None):
        if self.tick+len(uniforms)>np.iinfo(np.int64).max-19:raise ValueError('Advance exceeds safe absolute tick range')
        return _advance(self,uniforms,probabilities,log_selected_events=log_selected_events,event_indices=event_indices)

    @classmethod
    def from_checkpoint(cls,neuron_ids,indptr,targets,weights,checkpoint,*,modified_edge_indices=(),retained_weights=(),delivery_window=None):
        net=cls(neuron_ids,indptr,targets,weights,'H1',checkpoint['input_indices'],checkpoint['selected_indices'],checkpoint['seed'],modified_edge_indices=modified_edge_indices,retained_weights=retained_weights,delivery_window=delivery_window)
        return net.restore_checkpoint(checkpoint)
