#!/usr/bin/env python3
"""Frozen, tiny filesystem checks; no graph, neuron model or runtime imports."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import os
import traceback
import numpy as np
import inhibitory_recurrent_panel_archive as archive

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'validation/inhibitory-recurrent-panel-archive'
PLAN = Path(str(BASE)+'-plan.json')
RECEIPT = Path(str(BASE)+'-checks.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if PLAN.exists() or RECEIPT.exists() or BASE.exists():
        raise RuntimeError('Refusing to replace frozen filesystem attempt')
    sources = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), Path(archive.__file__)]}
    PLAN.write_text(json.dumps(dict(version=1, frozen_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sources,
        scope='Tiny synthetic filesystem fixtures only; no neural graph or execution.',
        checks=['Finite/nonfinite nested roundtrip and exact arrays including endian/structured/scalar/empty values.',
            'Root and partial spike packing: exact 12-byte little-endian records, version/count/hash and restored original dtypes.',
            'Immutable overwrite refusal, explicit progress replacement and retained unexpected targets/temporaries.',
            'Injected payload and completion replacement failures retain evidence and deny loading.',
            'Truncated temporary is never completed; checksum, packed-count and packed-endian corruption rejected.',
            'Spy verifies flush/fsync/replace ordering and completion last; publication lock blocks competing writer.',
            'Reject object arrays and integer overflow without coercion; preserve failed publication.'],
        failure_policy='Retain all deliberate invalid fixtures and any unexpected test failure. Do not overwrite or remove them.'), indent=2)+'\n')
    BASE.mkdir()
    checks, errors, expected_errors = [], [], []

    def ck(name, result):
        checks.append(dict(name=name, passed=bool(result)))
        if not result: raise AssertionError(name)

    def expect(name, function, kind):
        try: function()
        except kind as error:
            expected_errors.append(dict(name=name, type=type(error).__name__, message=str(error)))
            ck(name, True)
        else: ck(name, False)

    def same(a, b):
        if isinstance(a, np.ndarray):
            return isinstance(b, np.ndarray) and a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes() and not b.flags.writeable
        if isinstance(a, np.generic):
            return type(a) is type(b) and a.dtype == b.dtype and a.tobytes() == b.tobytes()
        if type(a) is not type(b): return False
        if isinstance(a, dict): return list(a) == list(b) and all(same(a[k], b[k]) for k in a)
        if isinstance(a, (tuple, list)): return len(a) == len(b) and all(same(x,y) for x,y in zip(a,b))
        if isinstance(a, float) and np.isnan(a): return np.isnan(b)
        return a == b

    try:
        payload = dict(spike_indices=np.array([7, -1, 2**31-1], dtype='>i8'),
            spike_ticks=np.array([0, 123, 2**63-1], dtype='>i8'),
            partial=dict(spike_indices=np.array([12, 4], dtype=np.uint32), spike_ticks=np.array([8, 9], dtype=np.int32),
                         failed=True, voltage=np.array([np.nan, np.inf, -np.inf, -0.], dtype='>f8')),
            finite=np.arange(24, dtype=np.int16).reshape(4,6)[:,::2],
            structured=np.array([(2, 3.5)], dtype=[('id','>i4'),('value','<f8')]),
            zero_dim=np.array(3, dtype='<i8'), scalar=np.float32(np.nan),
            extra=(None, True, 2**90, 'text', [float('nan'), float('inf'), -float('inf'), -0.]),
            empty=np.empty((0,3), dtype=np.float64))
        events = []
        original_replace, original_fsync = archive.os.replace, archive.os.fsync
        def replaced(src, dst):
            events.append(['replace', Path(src).name, Path(dst).name])
            return original_replace(src, dst)
        def synced(fd):
            events.append(['fsync']); return original_fsync(fd)
        with patch.object(archive.os, 'replace', side_effect=replaced), patch.object(archive.os, 'fsync', side_effect=synced):
            records = archive.save_archive(BASE/'roundtrip', payload)
        ck('record_order_and_hashes', [Path(r['path']).name for r in records] == ['roundtrip.npz','roundtrip.json','roundtrip.complete.json'] and
           all((ROOT/r['path']).stat().st_size == r['bytes'] and sha(ROOT/r['path']) == r['sha256'] for r in records))
        ck('exact_nested_roundtrip', same(payload, archive.load_archive(BASE/'roundtrip')))
        ck('native_arrays_unmodified', payload['spike_indices'].dtype.str == '>i8' and payload['finite'].strides == (12,4))
        ck('completion_published_last', [e[2] for e in events if e[0] == 'replace'] == ['roundtrip.npz','roundtrip.json','roundtrip.complete.json'])
        replace_positions = [i for i,e in enumerate(events) if e[0] == 'replace']
        ck('sync_before_and_after_replaces', all(events[i-1][0] == events[i+1][0] == 'fsync' for i in replace_positions))
        metadata = json.loads((BASE/'roundtrip.json').read_text())
        root = metadata['tree']; partial = dict(root['items'])['partial']
        with np.load(BASE/'roundtrip.npz', allow_pickle=False) as z:
            for label,node,count in [('root',root,3),('partial',partial,2)]:
                packed=z[node['spikes']['array']['key']];h=node['spikes']['header']
                ck(label+':packed_12B_little_endian', packed.dtype.descr == [('tick','<i8'),('index','<i4')] and packed.itemsize == 12 and packed.nbytes == count*12 and not packed.dtype.isalignedstruct)
                ck(label+':packed_header', h['version'] == 1 and h['count'] == count and h['shape'] == [count] and h['sha256'] == hashlib.sha256(packed.tobytes()).hexdigest())
            ck('NPZ_no_objects', all(not z[key].dtype.hasobject for key in z.files))
        ck('nonfinite_scalar_null_flags', '"kind": "nonfinite"' in (BASE/'roundtrip.json').read_text() and '"value": null' in (BASE/'roundtrip.json').read_text() and '"nonfinite": "negative_infinity"' in (BASE/'roundtrip.json').read_text())
        before = {r['path']:sha(ROOT/r['path']) for r in records}
        expect('immutable_refuses_overwrite', lambda: archive.save_archive(BASE/'roundtrip',payload), FileExistsError)
        ck('immutable_preserves_existing', all(sha(ROOT/p)==h for p,h in before.items()))
        archive.save_archive(BASE/'empty', dict(spike_indices=np.empty(0,np.int32),spike_ticks=np.empty(0,np.int64),partial=None))
        ck('empty_spikes_roundtrip', len(archive.load_archive(BASE/'empty')['spike_indices']) == 0)

        progress=BASE/'progress.json'
        archive.atomic_json(progress, dict(tick=0, value=float('inf')))
        ck('atomic_json_nonfinite_tag', json.loads(progress.read_text()) == dict(tick=0,value=dict(value=None,nonfinite='positive_infinity')))
        expect('atomic_json_refuses_default_overwrite',lambda:archive.atomic_json(progress,dict(tick=1)),FileExistsError)
        archive.atomic_json(progress,dict(tick=1),overwrite=True)
        ck('atomic_json_explicit_overwrite',json.loads(progress.read_text())==dict(tick=1))

        truncated=BASE/'truncated.tmp-interrupted.npz';truncated.write_bytes(b'PK\x03\x04partial')
        before_hash=sha(truncated)
        expect('truncated_temp_not_loadable',lambda:archive.load_archive(BASE/'truncated'),ValueError)
        expect('truncated_temp_not_overwritten',lambda:archive.save_archive(BASE/'truncated',{}),FileExistsError)
        ck('truncated_temp_retained',sha(truncated)==before_hash and not (BASE/'truncated.complete.json').exists())
        (BASE/'unknown.npz').write_bytes(b'preexisting')
        expect('unexpected_existing_file_refused',lambda:archive.save_archive(BASE/'unknown',{}),FileExistsError)
        ck('unexpected_existing_file_preserved',(BASE/'unknown.npz').read_bytes()==b'preexisting')

        for label,target in [('payload_failure','payload_failure.json'),('completion_failure','completion_failure.complete.json')]:
            def fail(src,dst):
                if Path(dst).name == target: raise PermissionError('intentional replacement failure')
                return original_replace(src,dst)
            with patch.object(archive.os,'replace',side_effect=fail):
                expect(label,lambda label=label:archive.save_archive(BASE/label,payload),archive.ArchivePublicationError)
            ck(label+':retained', (BASE/(label+'.publish.lock')).exists() and bool(list(BASE.glob(label+'.tmp-*'))) and bool(list(BASE.glob(label+'.failure-*.json'))))
            ck(label+':no_completion',not (BASE/(label+'.complete.json')).exists())
            expect(label+':load_refused',lambda label=label:archive.load_archive(BASE/label),ValueError)
        (BASE/'contending.publish.lock').write_bytes(b'other writer')
        expect('competing_writer_refused',lambda:archive.save_archive(BASE/'contending',{}),FileExistsError)
        ck('competing_lock_preserved',(BASE/'contending.publish.lock').read_bytes()==b'other writer')

        for label,bad in [('object',dict(a=np.array([object()],dtype=object))),
                          ('padded',dict(a=np.zeros(2,dtype=np.dtype([('a','i1'),('b','i8')],align=True)))),
                          ('overflow',dict(spike_indices=np.array([2**31],np.int64),spike_ticks=np.array([0],np.int64))),
                          ('tick_overflow',dict(spike_indices=np.array([0],np.int32),spike_ticks=np.array([2**63],np.uint64)))]:
            expect(label+':refused_without_loss',lambda label=label,bad=bad:archive.save_archive(BASE/label,bad),archive.ArchivePublicationError)
            ck(label+':no_completion',not (BASE/(label+'.complete.json')).exists())

        for label,field,value in [('bad_count','count',999),('bad_endian','dtype',[['tick','>i8'],['index','<i4']])]:
            archive.save_archive(BASE/label,dict(spike_indices=np.array([1],np.int32),spike_ticks=np.array([3],np.int64)))
            path=BASE/(label+'.json');header=json.loads(path.read_text());header['tree']['spikes']['header'][field]=value
            path.write_text(json.dumps(header)+'\n')
            marker_path=BASE/(label+'.complete.json');marker=json.loads(marker_path.read_text())
            marker['artifacts'][1]['bytes']=path.stat().st_size;marker['artifacts'][1]['sha256']=sha(path)
            marker_path.write_text(json.dumps(marker)+'\n')
            expect(label+':semantic_header_refused',lambda label=label:archive.load_archive(BASE/label),ValueError)
        archive.save_archive(BASE/'bad_checksum',dict(a=np.arange(3)))
        with (BASE/'bad_checksum.npz').open('ab') as f:f.write(b'changed')
        expect('payload_checksum_refused',lambda:archive.load_archive(BASE/'bad_checksum'),ValueError)
        (BASE/'events.json').write_text(json.dumps(events,indent=2)+'\n')
    except Exception as error:
        errors.append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    for path,digest in sources.items():
        checks.append(dict(name='unchanged:'+path,passed=sha(ROOT/path)==digest))
    files={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in BASE.rglob('*') if p.is_file()}
    result=dict(version=1,completed_utc=datetime.now(timezone.utc).isoformat(),plan_sha256=sha(PLAN),source_sha256=sources,
        passed=not errors and all(c['passed'] for c in checks),checks=checks,check_count=len(checks),errors=errors,
        expected_errors=expected_errors,artifacts=files,scope='Synthetic filesystem data only; intentional failures and corruptions retained.',
        limits=['Mocked exceptions and actual local fsync calls are not a hardware power-loss test.',
                'Exclusive locks coordinate users of these utilities, not unrelated writers ignoring the protocol.',
                'If the filesystem fails completely, diagnostic writing can also fail; already-created evidence is retained.'])
    RECEIPT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],checks=len(checks),expected_errors=len(expected_errors),artifacts=len(files),errors=errors),indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
