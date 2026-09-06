"""Verify the complete source ZIP and inventory every member without executing it."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'validation/apl-sk-ephys-acquisition.json'
OUT = ROOT / 'validation/apl-sk-ephys-inventory.json'
DEST = ROOT / 'data/raw/apl-sk-electrophysiology/inventory-files'


def main():
    if OUT.exists() or DEST.exists():
        raise FileExistsError('Preserve previous inventory and extracted sources')
    receipt = json.loads(RECEIPT.read_text())
    archive = ROOT / receipt['archive']['path']
    digest = hashlib.sha256(); md5 = hashlib.md5()
    with archive.open('rb') as f:
        while block := f.read(4 * 1024 * 1024):
            digest.update(block); md5.update(block)
    assert archive.stat().st_size == receipt['archive']['bytes'] == 2287477173
    assert md5.hexdigest() == receipt['archive']['md5'] == 'c6d63ac25c504db4fc3ee45578d63169'
    assert digest.hexdigest() == receipt['archive']['sha256']
    rows = []; counts = Counter(); abf_counts = Counter(); directories = defaultdict(set)
    hashes = defaultdict(list)
    with zipfile.ZipFile(archive) as z:
        seen = set()
        # Validate all destinations before writing any extracted member.
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename:
                raise ValueError(f'Unsafe member path: {info.filename!r}')
            if p.as_posix() in seen:
                raise ValueError(f'Duplicate normalized member: {info.filename!r}')
            seen.add(p.as_posix())
            if stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1:
                raise ValueError('Links or encrypted members are unsupported')
        DEST.mkdir()
        for ordinal, info in enumerate(z.infolist()):
            p = PurePosixPath(info.filename)
            row = dict(ordinal=ordinal, member=info.filename, directory=info.is_dir(),
                       bytes=info.file_size, compressed_bytes=info.compress_size,
                       crc32=f'{info.CRC:08x}')
            if not info.is_dir():
                suffix = p.suffix.lower(); counts[suffix] += 1
                group = p.parts[1] if len(p.parts) > 1 else ''
                apl = group.startswith('APL_')
                # Retain APL electrical/metadata sources and all author workbooks.
                # Images and KC electrical files remain available in the original ZIP.
                selected = suffix == '.xlsx' or (apl and suffix in ('.abf', '.txt', '.json'))
                target = DEST / p
                if selected:
                    target.parent.mkdir(parents=True, exist_ok=True)
                sha = hashlib.sha256(); n = 0; first = b''
                output = target.open('xb') if selected else None
                try:
                    with z.open(info) as source:
                        while block := source.read(4 * 1024 * 1024):
                            if n == 0: first = block[:4]
                            n += len(block); sha.update(block)
                            if output: output.write(block)
                finally:
                    if output: output.close()
                # Reading to EOF also checks every member's ZIP CRC.
                assert n == info.file_size
                row.update(sha256=sha.hexdigest(), crc_verified=True)
                hashes[sha.hexdigest()].append(info.filename)
                if selected: row['extracted_path'] = str(target.relative_to(ROOT))
                if suffix == '.abf':
                    row['abf_signature_hex'] = first.hex()
                    row['candidate_recording_directory'] = str(p.parent)
                    abf_counts[group] += 1; directories[group].add(str(p.parent))
            rows.append(row)
    result = dict(completed_utc=datetime.now(timezone.utc).isoformat(),
        archive=receipt['archive'], acquisition_receipt_sha256=hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        entry_count=len(rows), file_count=sum(not r['directory'] for r in rows),
        uncompressed_bytes=sum(r['bytes'] for r in rows), extension_counts=dict(counts),
        abf_counts_by_source_folder=dict(abf_counts),
        candidate_recording_directories_by_source_folder={k:len(v) for k,v in directories.items()},
        extracted_file_count=sum('extracted_path' in r for r in rows),
        duplicate_file_content_groups=[v for v in hashes.values() if len(v)>1],
        scope='Complete archive integrity and source inventory only. Directory names are candidate identities, not verified cell/animal/group joins. ABF channels, actual commands, compensation/correction and author exclusions remain unparsed. No physiological measurements or fitting.',
        entries=rows)
    OUT.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('entries','duplicate_file_content_groups')},indent=2))


if __name__ == '__main__': main()
