# Durable archive utilities for the recurrent panel

The standalone [archive module](../scripts/inhibitory_recurrent_panel_archive.py) passed **45/45 focused filesystem checks** on its first execution. The [frozen plan](../validation/inhibitory-recurrent-panel-archive-plan.json), [receipt](../validation/inhibitory-recurrent-panel-archive-checks.json), and 37 retained tiny fixture files record the successful publications and 17 intentional exception cases. No graph, neuron model, runtime default or existing frozen source was changed.

The public API is:

```python
atomic_json(path, obj, *, overwrite=False)  # -> {path, bytes, sha256}
save_archive(stem, nested_dict)            # -> [NPZ, schema, completion records]
load_archive(stem)                        # -> restored nested dictionary
```

Record paths are relative to the repository root. Each record includes file size in bytes and SHA256. `save_archive` writes `stem.npz`, `stem.json` and `stem.complete.json`. It refuses to overwrite any existing archive payload, completion marker, publication lock, unexpected temporary or failure record. `atomic_json` defaults to the same immutable behavior for its target; a caller may explicitly use `overwrite=True` for mutable progress. Existing locks and temporaries are refused even with that option. Output scans, budgets, checkpoint selection and process orchestration remain the caller's responsibility.

Each writer first acquires an exclusive lock file. Temporary files have unique transaction names, are closed after flush/fsync, and are hashed before `os.replace`. The containing directory is fsynced after each replacement. Archive payloads publish before the completion marker, whose version, transaction ID and payload checksums bind the files together. The completion marker is the last published archive artifact; successful lock cleanup follows it. A failed publication preserves its lock, any written payloads and temporaries, and attempts to write a separate failure record. `ArchivePublicationError.retained_paths` reports surviving evidence. Keyboard interruption and system exit preserve evidence and propagate their original exception types.

`load_archive` is read-only and refuses completion while lock, temporary or failure evidence remains. It verifies both payload file hashes, lengths and expected paths; the transaction/version link; every array's name, shape, dtype description, item size, element count and raw C-order checksum; and the absence of duplicate or unreferenced arrays. It never enables pickle. Returned arrays have their writeable flag disabled. This flag discourages accidental writes; it is not a security boundary against a caller deliberately changing ownership flags.

The typed JSON tree preserves ordinary dictionaries and insertion order, lists, tuples, Python scalars, NumPy scalars and arrays. Arrays retain dtype, shape and logical C-order bytes, including NaN payloads, infinities, signed zero and explicit byte order. Strides, views and shared-memory identity are outside the archival contract. Object arrays, dtype metadata, and padded, overlapping or aligned structured dtypes are rejected rather than silently normalized. The panel's plain numeric arrays and tightly packed spike records are supported. Python nonfinite scalars have a JSON `null` value plus an explicit `nan`, `positive_infinity` or `negative_infinity` flag, and are restored on load. NumPy scalars are represented by exact zero-dimensional NPZ values. For ordinary `atomic_json`, a nonfinite scalar becomes `{"value": null, "nonfinite": "…"}`; finite fields retain ordinary JSON form.

Root-level and `root.partial` spike pairs are each stored once as a structured array with dtype `[('tick','<i8'), ('index','<i4')]`, **item size 12 bytes with no padding**. A versioned header records count, shape, exact little-endian fields, item size, packed checksum, original integer dtypes and original component checksums. Inputs must be equal-length one-dimensional integer arrays and fit signed int64 ticks and signed int32 indices. Loading validates the header and record dtype, reconstructs each original integer dtype and verifies its original checksum. Empty pairs are valid; missing components or out-of-range integers are rejected without coercion. Larger original integer dtypes are supported when their values fit, and their original dtype is restored.

The [focused checker](../scripts/check_inhibitory_recurrent_panel_archive.py) retained exact roundtrip fixtures for full and partial spikes, big-endian arrays, unsigned indices, nonfinite values, a noncontiguous view, a tightly packed structured array, zero-dimensional values, tuples and empty arrays. It observed real fsync calls around replacements, verified completion publication order, and checked immutable/progress behavior. Injected failures during payload and completion replacement preserve partial evidence and deny loading. Tests also retain a truncated temporary, a competing writer's lock, an unexpected existing file, rejected object/padded/overflow inputs, a changed payload checksum, and internally rehashed but invalid spike-count/endian headers. These are expected negative tests, not scientific or source failures.

The exclusive locks coordinate writers using these utilities; an unrelated process ignoring the protocol is outside that guarantee. The tests exercise the local filesystem and mocked exceptions, not hardware power loss, every operating-system failure point or historical storage durability. Complete storage failure can prevent writing the diagnostic itself. Existing partial evidence is never automatically repaired, removed or reused. A retained failure requires a separately named attempt or an explicit recovery policy from the caller.

Frozen SHA256 pins:

- Module: `3352c667249482e655116d073f899a3943e39c4d58fd53248801336abeade067`.
- Checker: `a4896139db56a132987ee61f90ff54f0a991d431c8cffffe0d78b7e3fb84b164`.
- Plan: `a4594bfaf649bb205db6a0bbddc55f657d486379b1e2a93b935f8c2fcad9c4b5`.
- Receipt: `0557d6e3880997a33be446c5bc6119c9a10bf8f51b0915d93e7d86c4e017f7ed`.

The checker refuses to overwrite its frozen attempt. This module is ready for the panel runner's separate integration and review; it does not establish that the full panel has run or that its prospective checkpoints satisfy a budget.
