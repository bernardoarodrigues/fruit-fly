#!/usr/bin/env python3
"""Read-only population/graph identity review; no simulator imports or runs."""
from pathlib import Path
import argparse
import hashlib
import json
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / 'data/processed/malecns_v1'


def record(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=h.hexdigest())


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value)):
        return None
    return value


def histogram(series):
    return {('<missing>' if pd.isna(k) else str(k)): int(n)
            for k, n in series.value_counts(dropna=False).items()}


def same_column(a, b):
    return a.astype(object).where(a.notna(), '<missing>').tolist() == b.astype(object).where(b.notna(), '<missing>').tolist()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'validation/pn-kc-apl-identity-review.json')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing receipt; use a new output path for another review.')
    result = dict(schema='pn-kc-apl-identity-review/v1', passed=False, checks=[],
                  scope='Exact retained MaleCNS annotation identities and direct adjacency only. No spikes, model execution, fit, or physiological promotion.')

    def ck(name, value):
        result['checks'].append(dict(name=name, passed=bool(value)))
        if not value:
            raise AssertionError(name)

    try:
        paths = [Path(__file__), GRAPH/'manifest.json', GRAPH/'neurons.feather',
                 ROOT/'data/raw/body-annotations-male-cns-v1.0-minconf-0.5.feather',
                 ROOT/'data/raw/body-neurotransmitters-male-cns-v1.0.feather',
                 ROOT/'validation/navigation-ladder-anatomy.json',
                 ROOT/'validation/navigation-ladder-mbon-input-results.json',
                 ROOT/'validation/navigation-ladder-mbon-input-independent-review.json',
                 ROOT/'validation/navigation-ladder-mbon-input-edges.csv']
        paths += [GRAPH/(name+'.npy') for name in ('neuron_ids','signs','indptr','targets','weights','contact_counts')]
        pins = {str(p.relative_to(ROOT)): record(p) for p in paths}
        result['inputs'] = list(pins.values())
        manifest = json.loads((GRAPH/'manifest.json').read_text())
        for name, rec in (manifest['arrays'] | manifest['metadata']).items():
            ck('manifest_'+name, pins[str((GRAPH/name).relative_to(ROOT))]['sha256'] == rec['sha256'])
        for src in manifest['sources'][:2]:
            ck('raw_source_'+Path(src['path']).name, pins[src['path']]['sha256'] == src['sha256'])
        d = pd.read_feather(GRAPH/'neurons.feather')
        ids = np.load(GRAPH/'neuron_ids.npy', mmap_mode='r')
        signs = np.load(GRAPH/'signs.npy', mmap_mode='r')
        ptr = np.load(GRAPH/'indptr.npy', mmap_mode='r')
        targets = np.load(GRAPH/'targets.npy', mmap_mode='r')
        weights = np.load(GRAPH/'weights.npy', mmap_mode='r')
        counts = np.load(GRAPH/'contact_counts.npy', mmap_mode='r')
        ck('graph_id_order', np.array_equal(ids, d.bodyId.to_numpy()) and np.all(np.diff(ids)>0) and len(ids)==166700)
        raw = pd.read_feather(ROOT/'data/raw/body-annotations-male-cns-v1.0-minconf-0.5.feather')
        retained = raw.loc[raw.superclass.notna()].sort_values('bodyId').reset_index(drop=True)
        for field in ['bodyId','type','class','subclass','superclass','supertype','instance','rootSide','somaSide','flywireType','hemibrainType','status','statusLabel']:
            ck('raw_annotation_'+field, same_column(retained[field], d[field]))
        nt = pd.read_feather(ROOT/'data/raw/body-neurotransmitters-male-cns-v1.0.feather').set_index('body').reindex(ids)
        for field in ['consensus_nt','predicted_nt','ground_truth','cell_type']:
            ck('raw_nt_'+field, same_column(nt[field], d[field]))
        ck('model_sign_column_and_array', np.array_equal(signs,d.model_sign.to_numpy()))
        expected_sign = d.consensus_nt.fillna('unknown').map(manifest['sign_rule']).to_numpy(np.int8)
        ck('model_sign_declared_rule', np.array_equal(signs,expected_sign))

        kc = d['class'].eq('Kenyon_Cell').to_numpy()
        apl = d.type.eq('APL').to_numpy()
        alpn = d['class'].eq('ALPN').to_numpy()
        ck('KC_class_equals_primary_type_prefix', np.array_equal(kc,d.type.fillna('').str.startswith('KC').to_numpy()))
        for field in ['flywireType','hemibrainType','cell_type']:
            ck('no_cross_namespace_KC_prefix_outside_class_'+field, not (d[field].fillna('').str.startswith('KC').to_numpy() & ~kc).any())
        ck('all_raw_KCs_retained', raw.loc[raw['class'].eq('Kenyon_Cell'),'bodyId'].sort_values().tolist()==ids[kc].tolist())
        ck('all_raw_APLs_retained', raw.loc[raw.type.eq('APL'),'bodyId'].sort_values().tolist()==ids[apl].tolist())
        ck('all_raw_ALPNs_retained', raw.loc[raw['class'].eq('ALPN'),'bodyId'].sort_values().tolist()==ids[alpn].tolist())
        # This is a retained anatomical edge-presence predicate, without an additional strength cutoff.
        direct = np.fromiter((np.any(kc[targets[ptr[i]:ptr[i+1]]]) for i in range(len(d))), bool, len(d))

        def group(mask, predicate):
            ii = np.flatnonzero(mask).astype('<i4')
            sub = d.iloc[ii]
            return dict(predicate=predicate,count=len(ii),index_sha256=hashlib.sha256(ii.tobytes()).hexdigest(),
                        index_encoding='ascending graph indices, contiguous little-endian int32 bytes',
                        body_ids_sha256=hashlib.sha256(ids[ii].astype('<i8').tobytes()).hexdigest(),
                        body_id_encoding='graph order, contiguous little-endian int64 bytes',
                        metadata={field:histogram(sub[field]) for field in ['type','class','subclass','superclass','rootSide','somaSide','consensus_nt','model_sign','status','statusLabel']})

        groups = {'KC_all':group(kc,"class == 'Kenyon_Cell'"),
                  'APL':group(apl,"type == 'APL'"),
                  'ALPN_all':group(alpn,"class == 'ALPN'"),
                  'ALPN_direct_to_KC':group(alpn & direct,"class == 'ALPN' AND any retained outgoing CSR target has class == 'Kenyon_Cell'"),
                  'SEZPN_all':group(d['class'].eq('SEZPN').to_numpy(),"class == 'SEZPN'"),
                  'SEZPN_direct_to_KC':group(d['class'].eq('SEZPN').to_numpy() & direct,"class == 'SEZPN' AND direct_to_KC"),
                  'visual_projection_direct_to_KC':group(d.superclass.eq('visual_projection').to_numpy() & direct,"superclass == 'visual_projection' AND direct_to_KC")}
        result['groups'] = groups
        result['kc_type_by_soma_side'] = {str(t):histogram(s.somaSide) for t,s in d.loc[kc].groupby('type')}
        result['kc_literal_prefix_counts'] = {p:int(d.loc[kc,'type'].str.startswith(p).sum()) for p in ['KCab',"KCa'b'",'KCg']}
        result['kc_unspecified_type_count'] = int((kc & d.type.eq('KC').to_numpy()).sum())
        result['kc_supertype_counts'] = histogram(d.loc[kc,'supertype'])
        result['APL_records'] = [dict(index=int(i),**clean(d.iloc[i][['bodyId','type','instance','class','superclass','subclass','rootSide','somaSide','consensus_nt','predicted_nt','ground_truth','model_sign','status','statusLabel','flywireType','hemibrainType']].to_dict())) for i in np.flatnonzero(apl)]
        pnname = d.type.fillna('').str.contains('PN', regex=False).to_numpy()
        cb = d.type.fillna('').str.startswith('CB').to_numpy()
        result['PN_name_ambiguity'] = dict(type_contains_PN_count=int(pnname.sum()),
            ALPN_with_PN_in_type=int((alpn & pnname).sum()),
            ALPN_with_CB_prefix=int((alpn & cb).sum()), ALPN_missing_primary_type=int((alpn & d.type.isna().to_numpy()).sum()),
            non_ALPN_PN_name=group(pnname & ~alpn,"type contains literal 'PN' AND class != 'ALPN'; candidates only"),
            non_ALPN_PN_name_direct_to_KC=group(pnname & ~alpn & direct,"type contains literal 'PN' AND class != 'ALPN' AND direct_to_KC; candidates only"),
            ALPN_missing_type_records=clean(d.loc[alpn & d.type.isna().to_numpy(),['bodyId','instance','flywireType','hemibrainType','somaSide']].to_dict('records')))

        previous = json.loads((ROOT/'validation/navigation-ladder-mbon-input-results.json').read_text())
        reviewer = json.loads((ROOT/'validation/navigation-ladder-mbon-input-independent-review.json').read_text())
        ck('prior_MBON_anatomical_audit_passed', previous['passed'] and reviewer['passed'])
        edge_path = ROOT/'validation/navigation-ladder-mbon-input-edges.csv'
        ck('prior_edge_table_hash', record(edge_path)==next(r for r in previous['artifacts'] if r['path']==str(edge_path.relative_to(ROOT))))
        edge = pd.read_csv(edge_path)
        ei=edge.edge_index.to_numpy(np.int64); source=edge.source_index.to_numpy(np.int64); target=edge.target_index.to_numpy(np.int64)
        ck('edge_table_unique_ids',len(np.unique(ei))==len(ei))
        ck('edge_table_CSR_source_row', np.all((ei>=ptr[source])&(ei<ptr[source+1])))
        ck('edge_table_graph_targets', np.array_equal(targets[ei],target))
        ck('edge_table_graph_body_ids', np.array_equal(ids[source],edge.source_body_id.to_numpy()) and np.array_equal(ids[target],edge.target_body_id.to_numpy()))
        ck('edge_table_weights_contacts', np.array_equal(weights[ei],edge.weight_float32.to_numpy(np.float32)) and np.array_equal(counts[ei],edge.contact_count.to_numpy()))
        ck('edge_table_class_annotations', same_column(edge['class'],d.iloc[source]['class']))
        mbon=np.flatnonzero(d.type.isin(['MBON12','MBON13','MBON14']).to_numpy())
        expected_edges=np.flatnonzero(np.isin(targets,mbon))
        ck('edge_table_complete_all_MBON12_14_incoming', np.array_equal(np.sort(ei),expected_edges))
        selected=np.unique(source[kc[source]])
        subset=np.zeros(len(d),bool);subset[selected]=True
        complement=kc & ~subset
        ck('KC_subset_and_complement_counts',len(selected)==3957 and int(complement.sum())==107 and int(kc.sum())==4064)
        result['previous_KC_MBON_subset'] = dict(
            selected=group(subset,'KC_all AND any retained edge to exact MBON12/13/14'),
            complement=group(complement,'KC_all without retained edge to exact MBON12/13/14'),
            selected_edge_count=int(kc[source].sum()), complement_indices=np.flatnonzero(complement).tolist(),
            complement_body_ids=ids[complement].tolist(),
            label='3,957 is a target-dependent presynaptic subset, not the full retained KC population.')
        result['selection_recommendations'] = [
            "Use class == 'Kenyon_Cell' for all retained KCs; the primary type prefix is equivalent in this pinned dataset only.",
            "Use type == 'APL' for APL; its class is missing. Preserve both soma-side cells and do not filter by rootSide or statusLabel == 'Traced'.",
            "Use class == 'ALPN' for the anatomical ALPN population, retaining its4 unnamed primary types and44 CB-prefixed cells.",
            "For direct upstream ALPNs, intersect ALPN_all with retained CSR adjacency into KC_all. Keep all ALPNs and directly connected ALPNs as separate cohorts.",
            "Do not silently merge all PN-name matches, visual_projection or SEZPN into olfactory ALPNs. These are separate annotation namespaces/scopes."
        ]
        result['limits'] = [
            "KC subclass is missing for every cell. Exact type names and literal prefixes are available; no functional subclass or unknown numeric supertype semantics were invented.",
            "ALPN subclass BI occurs67times and is otherwise missing; its abbreviation is retained without assigning physiological meaning.",
            "rootSide is missing for all KC/APL/ALPN cells. somaSide is an annotation of the soma, not inferred projection laterality or a mirror pairing.",
            "APL consensus_nt and ground_truth columns both say gaba, but these are source annotation fields, not new physiological measurements. model_sign−1 follows the existing declared transmitter-to-effect rule.",
            "Direct contact presence uses the already retained minconf0.5 graph and>=1contact. It does not establish a strong/effective olfactory connection, independent synapse verification, or functional drive.",
            "The314 direct ALPNs and252 visual_projection sources include any retained edge; no stronger biological threshold was introduced. No raw contact-file rescan was needed: all compiled graph array hashes were checked against the manifest.",
            "No saved trial activity was analyzed. This review does not claim sparsity, response calibration, APL spiking/compartmental validity, or causal effects."
        ]
        for path in paths:
            ck('source_unchanged_'+str(path.relative_to(ROOT)),record(path)==pins[str(path.relative_to(ROOT))])
        result['passed']=True
    except Exception:
        result['error']=traceback.format_exc()
    result['check_count']=len(result['checks'])
    result['checks_passed']=sum(c['passed'] for c in result['checks'])
    with args.output.open('x') as f:
        json.dump(clean(result),f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(receipt=record(args.output),passed=result['passed'],checks=result['check_count'])))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
