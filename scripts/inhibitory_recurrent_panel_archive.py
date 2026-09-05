#!/usr/bin/env python3
"""Immutable, checksummed experiment archives. No neural/runtime imports.

Publication is coordinated by exclusive lock files. Never remove a leftover
lock, temporary file or failed archive automatically: it is retained evidence.
The completion marker is published after both payloads have been fsynced.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VERSION = 1
SPIKE_DTYPE = np.dtype([('tick', '<i8'), ('index', '<i4')], align=False)


class ArchivePublicationError(RuntimeError):
    def __init__(self, message, retained_paths):
        super().__init__(message)
        self.retained_paths = [str(p) for p in retained_paths]


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def _record(path):
    path = Path(path).absolute()
    return dict(path=os.path.relpath(path, ROOT), bytes=path.stat().st_size, sha256=_sha(path))


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _nonfinite(value):
    return 'nan' if math.isnan(value) else 'positive_infinity' if value > 0 else 'negative_infinity'


def _json_safe(value):
    """Finite ordinary JSON stays ordinary; nonfinite scalars are explicit."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return dict(value=None, nonfinite=_nonfinite(value))
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise TypeError('JSON dictionary keys must be strings')
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError('Unsupported ordinary JSON value: '+type(value).__name__)


def _json_bytes(value):
    return (json.dumps(_json_safe(value), indent=2, allow_nan=False)+'\n').encode('utf-8')


def _write_bytes(path, value):
    with Path(path).open('xb') as f:
        f.write(value)
        f.flush()
        os.fsync(f.fileno())


def _publish(temp, final, overwrite=False):
    if not overwrite and os.path.lexists(final):
        raise FileExistsError('Refusing existing publication target: '+str(final))
    # Writers using this module hold the exclusive target/archive lock. An
    # unrelated writer that ignores those locks is outside this protocol.
    os.replace(temp, final)
    _fsync_dir(Path(final).parent)


def atomic_json(path, obj, *, overwrite=False):
    """Publish ordinary JSON atomically; explicit overwrite is for progress.

    Returns {path, bytes, sha256}; path is relative to the repository root.
    Nonfinite scalar values become {value:null, nonfinite:<explicit tag>}.
    Existing temporaries/locks are always refused, even with overwrite=True.
    """
    path = Path(path).absolute()
    payload = _json_bytes(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name+'.atomic.lock')
    if (not overwrite and os.path.lexists(path)) or os.path.lexists(lock) or list(path.parent.glob(path.name+'.tmp-*')):
        raise FileExistsError('Existing JSON target/lock/temporary: '+str(path))
    token = uuid.uuid4().hex
    temp = path.with_name(path.name+'.tmp-'+token)
    _write_bytes(lock, _json_bytes(dict(version=VERSION, transaction=token, target=path.name)))
    try:
        _fsync_dir(path.parent)
        _write_bytes(temp, payload)
        expected = _record(temp)
        _publish(temp, path, overwrite=overwrite)
        actual = _record(path)
        if (expected['bytes'], expected['sha256']) != (actual['bytes'], actual['sha256']):
            raise IOError('Published JSON checksum mismatch')
        lock.unlink()
        _fsync_dir(path.parent)
        return actual
    except BaseException:
        # Preserve lock/temp or published target. The caller retains its error.
        raise


def _dtype_description(dtype):
    return json.loads(json.dumps(np.lib.format.dtype_to_descr(dtype)))


def _array_descriptor(key, array):
    def metadata(dtype):
        return bool(dtype.metadata or (dtype.subdtype and metadata(dtype.subdtype[0])) or
                    (dtype.fields and any(metadata(field[0]) for field in dtype.fields.values())))
    if array.dtype.hasobject or metadata(array.dtype):
        raise TypeError('Object arrays and dtype metadata are unsupported')
    def packed(dtype):
        if dtype.isalignedstruct:
            return False
        if dtype.subdtype:
            return packed(dtype.subdtype[0])
        if dtype.fields:
            offset = 0
            for name in dtype.names:
                child, position = dtype.fields[name][:2]
                if position != offset or not packed(child):
                    return False
                offset += child.itemsize
            return offset == dtype.itemsize
        return True
    if not packed(array.dtype):
        raise TypeError('Padded, overlapping or aligned structured dtypes are unsupported')
    return dict(key=key, shape=list(array.shape), dtype=_dtype_description(array.dtype),
                itemsize=array.dtype.itemsize, count=array.size,
                bytes=array.nbytes, sha256=hashlib.sha256(array.tobytes(order='C')).hexdigest())


def _pack_spikes(indices, ticks):
    for name, a, lo, hi in [('indices', indices, -(2**31), 2**31-1), ('ticks', ticks, -(2**63), 2**63-1)]:
        if not isinstance(a, np.ndarray) or a.ndim != 1 or a.dtype.kind not in 'iu' or a.dtype.metadata:
            raise TypeError('Spike '+name+' must be a one-dimensional integer ndarray')
        if a.size and (int(a.min()) < lo or int(a.max()) > hi):
            raise ValueError('Spike '+name+' outside packed range; refusing coercion loss')
    if indices.shape != ticks.shape:
        raise ValueError('Spike index/tick shapes differ')
    packed = np.empty(len(ticks), dtype=SPIKE_DTYPE)
    packed['tick'], packed['index'] = ticks, indices
    header = dict(version=VERSION, count=len(ticks), shape=[len(ticks)],
        dtype=[['tick', '<i8'], ['index', '<i4']], itemsize=12,
        sha256=hashlib.sha256(packed.tobytes()).hexdigest(),
        original_index_dtype=indices.dtype.str, original_tick_dtype=ticks.dtype.str,
        original_index_sha256=hashlib.sha256(indices.tobytes()).hexdigest(),
        original_tick_sha256=hashlib.sha256(ticks.tobytes()).hexdigest())
    return packed, header


def _encode(value, arrays, path=()):
    if isinstance(value, np.ndarray) or isinstance(value, np.generic):
        a = np.asarray(value).copy(order='K')
        key = 'array_'+str(len(arrays))
        descriptor = _array_descriptor(key, a)
        arrays[key] = a
        return dict(kind='numpy_scalar' if isinstance(value, np.generic) else 'array', array=descriptor)
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise TypeError('Archive dictionary keys must be strings')
        # Preserve mapping insertion order, while replacing exactly the root
        # and root.partial spike pair with one little-endian record array.
        has_pair = path in [(), ('partial',)] and ('spike_indices' in value or 'spike_ticks' in value)
        if has_pair and not ('spike_indices' in value and 'spike_ticks' in value):
            raise ValueError('Incomplete spike pair at '+repr(path))
        items, pair = [], None
        if has_pair:
            packed, header = _pack_spikes(value['spike_indices'], value['spike_ticks'])
            key = 'array_'+str(len(arrays))
            pair = dict(array=_array_descriptor(key, packed), header=header)
            arrays[key] = packed
        for k, v in value.items():
            if has_pair and k in ['spike_indices', 'spike_ticks']:
                items.append([k, dict(kind='spike_component', component='index' if k == 'spike_indices' else 'tick')])
            else:
                items.append([k, _encode(v, arrays, path+(k,))])
        node = dict(kind='dict', items=items)
        if pair is not None:
            node['spikes'] = pair
        return node
    if isinstance(value, (list, tuple)):
        return dict(kind='tuple' if isinstance(value, tuple) else 'list', items=[_encode(v, arrays, path+(str(i),)) for i, v in enumerate(value)])
    if isinstance(value, float) and not math.isfinite(value):
        return dict(kind='nonfinite', value=None, nonfinite=_nonfinite(value))
    if value is None or type(value) in [str, bool, int, float]:
        return dict(kind='scalar', value=value)
    raise TypeError('Unsupported archive value: '+type(value).__name__)


def _paths(stem):
    stem = Path(stem).absolute()
    return stem, Path(str(stem)+'.npz'), Path(str(stem)+'.json'), Path(str(stem)+'.complete.json'), Path(str(stem)+'.publish.lock')


def save_archive(stem, nested_dict):
    """Return [NPZ record, schema record, completion record] after publication.

    Records have repository-relative path, bytes and SHA256. No objects/pickle
    enter the NPZ. Original array dtype/shape/logical C-order bytes are retained;
    original memory strides/aliasing are not part of the archival contract.
    """
    stem, npz, schema, complete, lock = _paths(stem)
    if not isinstance(nested_dict, dict):
        raise TypeError('Archive root must be a dictionary')
    stem.parent.mkdir(parents=True, exist_ok=True)
    unexpected = [p for p in [npz, schema, complete, lock] if os.path.lexists(p)]
    unexpected += list(stem.parent.glob(stem.name+'.tmp-*'))+list(stem.parent.glob(stem.name+'.failure-*'))
    if unexpected:
        raise FileExistsError('Refusing existing archive evidence: '+', '.join(map(str, unexpected)))
    token = uuid.uuid4().hex
    _write_bytes(lock, _json_bytes(dict(version=VERSION, transaction=token, stem=stem.name)))
    try:
        _fsync_dir(stem.parent)
        arrays = {}
        tree = _encode(nested_dict, arrays)
        header = dict(format='inhibitory-recurrent-panel', version=VERSION, transaction=token, tree=tree)
        npz_temp = stem.with_name(stem.name+'.tmp-'+token+'.npz')
        with npz_temp.open('xb') as f:
            np.savez_compressed(f, **arrays)
            f.flush()
            os.fsync(f.fileno())
        npz_record = _record(npz_temp)
        schema_temp = stem.with_name(stem.name+'.tmp-'+token+'.json')
        _write_bytes(schema_temp, _json_bytes(header))
        schema_record = _record(schema_temp)
        for temp, final, expected in [(npz_temp, npz, npz_record), (schema_temp, schema, schema_record)]:
            _publish(temp, final)
            if _sha(final) != expected['sha256'] or final.stat().st_size != expected['bytes']:
                raise IOError('Published archive checksum mismatch')
        records = [_record(npz), _record(schema)]
        completion = dict(format='inhibitory-recurrent-panel-completion', version=VERSION,
                          transaction=token, complete=True, artifacts=records)
        marker_temp = stem.with_name(stem.name+'.tmp-'+token+'.complete.json')
        _write_bytes(marker_temp, _json_bytes(completion))
        expected = _record(marker_temp)
        _publish(marker_temp, complete)
        marker_record = _record(complete)
        if (marker_record['bytes'], marker_record['sha256']) != (expected['bytes'], expected['sha256']):
            raise IOError('Completion checksum mismatch')
        lock.unlink()
        _fsync_dir(stem.parent)
        return records+[marker_record]
    except BaseException as error:
        retained = sorted(stem.parent.glob(stem.name+'.*'))
        failure = stem.with_name(stem.name+'.failure-'+token+'.json')
        try:
            atomic_json(failure, dict(version=VERSION, complete=False, transaction=token,
                error_type=type(error).__name__, error=str(error),
                retained_paths=[os.path.relpath(p, ROOT) for p in retained]))
        except BaseException:
            pass  # Original lock/temporaries remain if diagnostic storage fails.
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
        raise ArchivePublicationError(str(error), sorted(stem.parent.glob(stem.name+'.*'))) from error


def load_archive(stem):
    """Verify a completed immutable archive and restore its original tree.

    Read-only: arrays returned to the caller are non-writeable. Packed spike
    fields are restored to their original integer dtypes without value loss.
    """
    stem, npz, schema, complete, lock = _paths(stem)
    if os.path.lexists(lock) or list(stem.parent.glob(stem.name+'.tmp-*')) or list(stem.parent.glob(stem.name+'.failure-*')):
        raise ValueError('Incomplete or failed publication evidence exists')
    marker = json.loads(complete.read_text())
    if marker.get('format') != 'inhibitory-recurrent-panel-completion' or marker.get('version') != VERSION or marker.get('complete') is not True:
        raise ValueError('Invalid completion header')
    if marker.get('artifacts') != [_record(npz), _record(schema)]:
        raise ValueError('Archive artifact checksum, length or path mismatch')
    header = json.loads(schema.read_text())
    if header.get('format') != 'inhibitory-recurrent-panel' or header.get('version') != VERSION or header.get('transaction') != marker.get('transaction'):
        raise ValueError('Invalid or mismatched archive header')
    with np.load(npz, allow_pickle=False) as z:
        if len(z.files) != len(set(z.files)):
            raise ValueError('Duplicate array payload name')
        arrays = {key: z[key] for key in z.files}
    used = set()

    def array(desc):
        key = desc['key']
        if key in used:
            raise ValueError('Duplicate array reference')
        used.add(key)
        a = arrays[key]
        if desc != _array_descriptor(key, a):
            raise ValueError('Array dtype, shape, size or checksum mismatch')
        a.setflags(write=False)
        return a

    def decode(node):
        kind = node['kind']
        if kind in ['array', 'numpy_scalar']:
            a = array(node['array'])
            if kind == 'numpy_scalar' and a.shape != ():
                raise ValueError('Numpy scalar shape mismatch')
            return a[()] if kind == 'numpy_scalar' else a
        if kind == 'scalar':
            return node['value']
        if kind == 'nonfinite':
            if node.get('value', 'missing') is not None:
                raise ValueError('Nonfinite scalar must carry null value')
            return dict(nan=float('nan'), positive_infinity=float('inf'), negative_infinity=-float('inf'))[node['nonfinite']]
        if kind in ['list', 'tuple']:
            out = [decode(v) for v in node['items']]
            return tuple(out) if kind == 'tuple' else out
        if kind == 'dict':
            pair = {}
            if 'spikes' in node:
                packed = array(node['spikes']['array']); h = node['spikes']['header']
                if (packed.ndim != 1 or packed.dtype.descr != SPIKE_DTYPE.descr or packed.dtype.itemsize != 12 or
                    h.get('version') != VERSION or h.get('count') != len(packed) or h.get('shape') != [len(packed)] or
                    h.get('dtype') != [['tick','<i8'],['index','<i4']] or h.get('itemsize') != 12 or
                    h.get('sha256') != hashlib.sha256(packed.tobytes()).hexdigest()):
                    raise ValueError('Packed spike header/dtype/count/endian/checksum mismatch')
                for field, name in [('index', 'index'), ('tick', 'tick')]:
                    dtype = np.dtype(h['original_'+name+'_dtype'])
                    if dtype.kind not in 'iu':
                        raise ValueError('Invalid original spike dtype')
                    restored = packed[field].astype(dtype)
                    if not np.array_equal(restored, packed[field]) or hashlib.sha256(restored.tobytes()).hexdigest() != h['original_'+name+'_sha256']:
                        raise ValueError('Original spike array reconstruction mismatch')
                    restored.setflags(write=False); pair[field] = restored
            out = {}
            for key, child in node['items']:
                if key in out or not isinstance(key, str):
                    raise ValueError('Duplicate/non-string dictionary key')
                if child['kind'] == 'spike_component' and (
                    key not in ['spike_indices', 'spike_ticks'] or
                    child['component'] != ('index' if key == 'spike_indices' else 'tick')):
                    raise ValueError('Spike field mapping mismatch')
                out[key] = pair[child['component']] if child['kind'] == 'spike_component' else decode(child)
            if pair and sorted(k for k, c in node['items'] if c['kind'] == 'spike_component') != ['spike_indices', 'spike_ticks']:
                raise ValueError('Invalid packed spike components')
            return out
        raise ValueError('Unsupported archive node kind')

    result = decode(header['tree'])
    if not isinstance(result, dict) or used != set(arrays):
        raise ValueError('Invalid root or unreferenced array payload')
    return result
