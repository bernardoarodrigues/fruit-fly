"""Download, audit and import the full retained MaleCNS neuronal graph.

Raw contact counts and assumed signed physiological weights are kept separately.
No neuron-pair strength threshold or subgraph selection is applied by default.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
import urllib.request

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
from scipy.sparse import csr_matrix

BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/"
FILES = {
    "annotations": "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "neurotransmitters": "body-neurotransmitters-male-cns-v1.0.feather",
    "connections": "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
}
# SHA-256 observed during this project's actual 2026-09-04 download.
EXPECTED_SHA256 = {
    "annotations": "2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2",
    "neurotransmitters": "95c9289220663abeb3409f3ad9e5a7f8a53f8093f5139d15502cd08da8879621",
    "connections": "e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1",
}
# This is a declared model rule, NOT experimentally established per-edge sign.
# Monoamines are point-synapse approximations, without receptor/volume signaling.
SIGN_RULE = {
    "acetylcholine": 1, "gaba": -1, "glutamate": -1, "histamine": -1,
    "dopamine": 1, "octopamine": 1, "serotonin": 1,
    "unclear": 0, "unknown": 0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def download(raw_dir: Path) -> list[dict]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    receipts = []
    for role, name in FILES.items():
        path = raw_dir / name
        if path.exists() and sha256(path) == EXPECTED_SHA256[role]:
            receipt_path = path.with_suffix(".receipt.json")
            receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
            receipt.update(url=BASE + name, size=path.stat().st_size, sha256=EXPECTED_SHA256[role])
            receipts.append(receipt)
            print(f"Verified existing {name}", flush=True)
            continue
        if path.exists():
            raise ValueError(f"Existing {path} does not match pinned source; preserve and investigate it")
        started = time.monotonic()
        partial = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(BASE + name, timeout=90) as response:
            headers = response.headers
            with partial.open("wb") as handle:
                while block := response.read(8 * 1024 * 1024):
                    handle.write(block)
        checksum = sha256(partial)
        if checksum != EXPECTED_SHA256[role]:
            raise ValueError(f"Upstream bytes changed for {name}; partial preserved for review")
        partial.replace(path)
        receipt = dict(url=BASE + name, size=path.stat().st_size, sha256=checksum,
                       etag=headers.get("ETag"), generation=headers.get("x-goog-generation"),
                       last_modified=headers.get("Last-Modified"), seconds=time.monotonic() - started)
        path.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        receipts.append(receipt)
        print(f"Downloaded and verified {name}", flush=True)
    return receipts


def map_ids(ids: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map sorted unique biological IDs without mapping missing IDs to neighbours."""
    indices = np.searchsorted(ids, values)
    valid = indices < len(ids)
    valid[valid] &= ids[indices[valid]] == values[valid]
    return indices.astype(np.int32), valid


def build(raw_dir: Path, output: Path, weight_scale_mv: float = .275) -> dict:
    if not np.isfinite(weight_scale_mv) or weight_scale_mv <= 0:
        raise ValueError("weight_scale_mv must be finite and positive")
    receipts = download(raw_dir)
    output.mkdir(parents=True, exist_ok=True)
    annotations = feather.read_feather(raw_dir / FILES["annotations"])
    # Final Cell inventory uses non-null superclass, not only status='Traced'.
    neurons = annotations.loc[annotations.superclass.notna()].sort_values("bodyId").copy()
    if neurons.bodyId.duplicated().any():
        raise ValueError("Duplicate annotated neuron IDs")
    nt = feather.read_feather(raw_dir / FILES["neurotransmitters"])
    neurons = neurons.merge(nt, left_on="bodyId", right_on="body", how="left", validate="one_to_one")
    ids = neurons.bodyId.to_numpy(np.int64)
    if len(ids) != 166700:
        raise ValueError(f"Pinned MaleCNS inventory changed: expected 166700, got {len(ids)}")
    consensus = neurons.consensus_nt.fillna("unknown")
    extra_nt = set(consensus.unique()) - set(SIGN_RULE)
    if extra_nt:
        raise ValueError(f"Unknown transmitter categories need a declared rule: {extra_nt}")
    signs = consensus.map(SIGN_RULE).to_numpy(np.int8)
    neurons["model_sign"] = signs
    reader = pa.ipc.open_file(pa.memory_map(str(raw_dir / FILES["connections"])))
    pres, posts, counts = [], [], []
    raw_edges = raw_contacts = retained_contacts = 0
    for batch_index in range(reader.num_record_batches):
        batch = reader.get_batch(batch_index)
        pre = batch.column("body_pre").to_numpy()
        post = batch.column("body_post").to_numpy()
        weight = batch.column("weight").to_numpy()
        if np.any(weight <= 0) or np.any(weight > np.iinfo(np.uint32).max):
            raise ValueError("Invalid raw synaptic contact multiplicity")
        i, valid_i = map_ids(ids, pre)
        j, valid_j = map_ids(ids, post)
        keep = valid_i & valid_j
        pres.append(i[keep]); posts.append(j[keep]); counts.append(weight[keep].astype(np.uint32))
        raw_edges += len(weight); raw_contacts += int(weight.sum())
        retained_contacts += int(weight[keep].sum())
        if batch_index % 400 == 0:
            print(f"Import {batch_index}/{reader.num_record_batches} batches; retained {sum(map(len,counts)):,} edges", flush=True)
    source, target, multiplicity = np.concatenate(pres), np.concatenate(posts), np.concatenate(counts)
    del pres, posts, counts
    raw_retained_pairs = len(multiplicity)
    graph = csr_matrix((multiplicity, (source, target)), shape=(len(ids), len(ids)), dtype=np.uint32)
    graph.sum_duplicates(); graph.sort_indices()
    del source, target, multiplicity
    indptr = graph.indptr.astype(np.int64)
    targets = graph.indices.astype(np.int32)
    contact_counts = graph.data
    weights = contact_counts.astype(np.float32) * np.float32(weight_scale_mv)
    row_sign = np.repeat(signs, np.diff(indptr))
    weights *= row_sign
    zero_sign_edges = int(np.count_nonzero(row_sign == 0))
    incoming = np.bincount(targets, minlength=len(ids))
    disconnected = (np.diff(indptr) + incoming) == 0
    for name, value in dict(neuron_ids=ids, indptr=indptr, targets=targets,
                            contact_counts=contact_counts, weights=weights, signs=signs).items():
        np.save(output / f"{name}.npy", value, allow_pickle=False)
    feather.write_feather(neurons, output / "neurons.feather")
    manifest = {
        "dataset": "male-cns:v1.0", "sex": "male", "inventory": "non-null superclass annotations",
        "neurons": len(ids), "edges": graph.nnz, "retained_synaptic_contacts": retained_contacts,
        "raw_segment_edges": raw_edges, "raw_segment_contacts": raw_contacts,
        "unaggregated_retained_rows": raw_retained_pairs, "disconnected_neurons": int(disconnected.sum()),
        "connection_strength_threshold": 1, "synapse_detector_minconf": .5,
        "weight_scale_mv": weight_scale_mv, "transmitter_column": "consensus_nt",
        "sign_rule": SIGN_RULE, "transmitter_counts": consensus.value_counts().to_dict(),
        "zero_sign_neurons": int((signs == 0).sum()), "zero_sign_edges": zero_sign_edges,
        "sign_caveat": "Declared transmitter-to-effect approximation; unknown/unclear outgoing weights zero; no receptor-specific or volume transmission.",
        "all_selected_neurons_retained": True, "sources": receipts,
        "license": "MaleCNS data CC BY 4.0; attribution Berg et al., Cell 2026, DOI 10.1016/j.cell.2026.08.015",
        "arrays": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in output.glob("*.npy")},
        "metadata": {"neurons.feather": {"sha256": sha256(output / "neurons.feather"),
                     "bytes": (output / "neurons.feather").stat().st_size}},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k:v for k,v in manifest.items() if k not in ("sources", "arrays")}, indent=2))
    return manifest


@dataclass
class Connectome:
    neuron_ids: np.ndarray
    indptr: np.ndarray
    targets: np.ndarray
    weights: np.ndarray
    neurons: pd.DataFrame
    manifest: dict

    @classmethod
    def load(cls, path: Path | str, verify: bool = False):
        path = Path(path)
        manifest = json.loads((path / "manifest.json").read_text())
        if verify:
            if not manifest.get("metadata"):
                raise ValueError("Processed graph lacks metadata checksums; rebuild the pinned graph")
            for name, expected in (manifest["arrays"] | manifest["metadata"]).items():
                if sha256(path / name) != expected["sha256"]:
                    raise ValueError(f"Processed artifact checksum differs: {name}")
        arrays = {n: np.load(path / f"{n}.npy", mmap_mode="r", allow_pickle=False)
                  for n in ("neuron_ids", "indptr", "targets", "weights")}
        neurons = feather.read_feather(path / "neurons.feather")
        if not np.array_equal(arrays["neuron_ids"], neurons.bodyId):
            raise ValueError("Neuron metadata and matrix order disagree")
        return cls(**arrays, neurons=neurons, manifest=manifest)

    def select(self, types: list[str] | tuple[str, ...], side: str | None = None,
               nerve: str | None = None) -> np.ndarray:
        mask = self.neurons.type.isin(types)
        if side is not None:
            # For sensory afferents, rootSide is the receptor's side, not somaSide.
            annotated_side = self.neurons.rootSide.fillna(self.neurons.somaSide)
            mask &= annotated_side.eq(side)
        if nerve is not None:
            mask &= self.neurons.entryNerve.eq(nerve)
        return np.flatnonzero(mask.to_numpy()).astype(np.int32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("download", "build", "verify"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/malecns_v1"))
    args = parser.parse_args()
    if args.command == "download":
        download(args.raw_dir)
    elif args.command == "build":
        build(args.raw_dir, args.output)
    else:
        graph = Connectome.load(args.output, verify=True)
        print(json.dumps(graph.manifest, indent=2))


if __name__ == "__main__":
    main()
