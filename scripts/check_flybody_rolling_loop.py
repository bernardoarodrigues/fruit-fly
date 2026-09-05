#!/usr/bin/env python3
"""Three frozen 12 s full-neural rolling FlyBody trials.

No plan is written and no simulator is constructed without explicit CLI mode.
Plan creation requires completed passing rolling-bridge evidence. Full native
states, ordered drives and lossless ordered spikes remain in ignored raw files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from check_flybody_loop import (
    Capture, DT, SENSORY_GROUPS, inspect_physical, native_state_hash,
    paired_mechanisms, physical_summary, safe, write_json,
)

OUT = ROOT / "validation/flybody-rolling-loop"
PLAN = OUT / "plan.json"
RESULT = OUT / "results.json"
BRIDGE = ROOT / "validation/flybody-rolling-bridge"
OLD = ROOT / "validation/flybody-loop"
MUTES = ((300, 600), (1500, 1800), (4500, 5300))
MAGIC = b"FFSPK001"
BLOCK = struct.Struct("<QQdd")
PREFIX_NATIVE_FIELDS = (
    "native_time_s", "tick", "qpos", "qvel", "qacc", "act", "ctrl",
    "native_action", "canonical_action", "actuator_ids", "action_names",
    "pose_cm_quat", "target_pose_cm_quat", "up_z", "support_dyne_by_leg",
    "contacts", "antenna_positions_mm", "tibia_velocity_rad_s", "command",
    "warnings", "finite", "source_terminated",
)
PREFIX_NEURAL_FIELDS = (
    "start_ms", "end_ms", "ordered_drive_sha256", "full_event_sha256",
    "downstream_event_sha256", "total_spikes", "traversed_edges",
    "monitored_counts", "voltage_mv", "rng_state_before", "rng_state_after",
    "positive_input_cells_by_encoder", "max_input_event_rate_hz_by_encoder",
    "listed_input_refractory_zero", "sensory_outgoing_mask", "blocked_neuron_count",
)


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def canonical(value):
    return json.dumps(safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class CompressedJournal:
    """One gzip member, flushed after each complete UTF-8 JSON event line."""
    def __init__(self, path):
        self.path = path
        self.file = path.open("xb")
        self.stream = gzip.GzipFile(filename="", mode="wb", fileobj=self.file, mtime=0)
        self.records = 0
        self.raw_bytes = 0
        self.raw_digest = hashlib.sha256()
        self.last_stage = "journal_open"
        self.current = {}

    def append(self, event, **payload):
        value = safe(dict(record=self.records, event=event, **payload))
        raw = json.dumps(value, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        self.stream.write(raw)
        self.stream.flush()
        self.file.flush()
        self.raw_digest.update(raw)
        self.raw_bytes += len(raw)
        self.records += 1
        self.last_stage = event
        # One interval only; full histories live in the streamed artifact.
        if event == "coupling_start":
            self.current = {}
        if event == "encoder":
            self.current.setdefault("encoders", []).append(copy.deepcopy(payload))
        elif event in ("neural_start", "neural_complete", "ordered_spikes"):
            self.current[event] = copy.deepcopy(payload)

    def close(self):
        self.stream.close()
        self.file.close()

    def receipt(self):
        return dict(path=str(self.path.relative_to(ROOT)), compressed_bytes=self.path.stat().st_size,
                    sha256=digest_file(self.path), uncompressed_bytes=self.raw_bytes,
                    uncompressed_sha256=self.raw_digest.hexdigest(), records=self.records)


class OrderedSpikes:
    """Lossless gzip stream of framed ordered ID/time arrays, written before Capture analysis."""
    def __init__(self, path, *, graph_sha256, plan_sha256):
        self.path = path
        self.file = path.open("xb")
        self.stream = gzip.GzipFile(filename="", mode="wb", fileobj=self.file, mtime=0)
        self.raw_digest = hashlib.sha256()
        self.raw_bytes = self.blocks = self.events = 0
        self.last = None
        header = dict(format="FFSPK001", endian="little", graph_sha256=graph_sha256,
            plan_sha256=plan_sha256,
            file_header="8-byte ASCII magic; uint32 JSON-header byte length; UTF-8 JSON header",
            block_header="uint64 zero-based coupling tick; uint64 event count; float64 start_ms; float64 end_ms",
            block_payload="N signed int64 body IDs followed by N float64 absolute milliseconds, unchanged batch order",
            block_header_bytes=BLOCK.size, bytes_per_event=16,
            schedule="0.1 ms Shiu; 2 ms coupling; no sorting or timestamp rounding")
        raw = canonical(header)
        self._write(MAGIC + struct.pack("<I", len(raw)) + raw)
        self.stream.flush(); self.file.flush()

    def _write(self, raw):
        self.stream.write(raw)
        self.raw_digest.update(raw)
        self.raw_bytes += len(raw)

    def append(self, tick, batch):
        ids = np.asarray(batch.neuron_ids, dtype="<i8")
        times = np.asarray(batch.times_ms, dtype="<f8")
        if ids.ndim != 1 or times.shape != ids.shape or len(ids) != batch.total_spikes:
            raise ValueError("Cannot archive a truncated/invalid full spike batch")
        offset = self.raw_bytes
        body = ids.tobytes() + times.tobytes()
        self._write(BLOCK.pack(tick, len(ids), batch.start_ms, batch.end_ms) + body)
        self.stream.flush(); self.file.flush()
        self.blocks += 1; self.events += len(ids)
        self.last = dict(tick=tick, uncompressed_offset=offset,
            uncompressed_block_bytes=BLOCK.size+len(body), events=len(ids),
            start_ms=batch.start_ms, end_ms=batch.end_ms,
            event_sha256=hashlib.sha256(struct.pack("<Q", len(ids)) + body).hexdigest())
        return self.last

    def close(self):
        self.stream.close(); self.file.close()

    def receipt(self):
        return dict(path=str(self.path.relative_to(ROOT)), format="FFSPK001",
            compressed_bytes=self.path.stat().st_size, sha256=digest_file(self.path),
            uncompressed_bytes=self.raw_bytes, uncompressed_sha256=self.raw_digest.hexdigest(),
            blocks=self.blocks, events=self.events, last_complete_block=self.last)


def read_spike_blocks(path):
    """Read-only format helper; rejects truncated headers/arrays rather than guessing."""
    with gzip.open(path, "rb") as stream:
        if stream.read(8) != MAGIC:
            raise ValueError("Unexpected spike-stream magic")
        size_raw = stream.read(4)
        if len(size_raw) != 4:
            raise EOFError("Truncated spike-stream header size")
        size = struct.unpack("<I", size_raw)[0]
        if size > 65536:
            raise ValueError("Implausible spike-stream metadata size")
        raw = stream.read(size)
        if len(raw) != size:
            raise EOFError("Truncated spike-stream metadata")
        metadata = json.loads(raw)
        if metadata["format"] != "FFSPK001" or metadata["block_header_bytes"] != 32:
            raise ValueError("Unknown spike block format")
        while header := stream.read(BLOCK.size):
            if len(header) != BLOCK.size:
                raise EOFError("Truncated ordered-spike block header")
            tick, n, start, end = BLOCK.unpack(header)
            if n > 166700 * 20:
                raise ValueError("Spike count exceeds 20 neural ticks over the full graph")
            ids, times = stream.read(n*8), stream.read(n*8)
            if len(ids) != n*8 or len(times) != n*8:
                raise EOFError("Truncated ordered-spike arrays")
            yield dict(tick=tick, start_ms=start, end_ms=end,
                neuron_ids=np.frombuffer(ids,dtype="<i8"), times_ms=np.frombuffer(times,dtype="<f8"),
                event_sha256=hashlib.sha256(struct.pack("<Q",n)+ids+times).hexdigest())


class LosslessCapture(Capture):
    def __init__(self, runner, journal, spikes):
        original = runner.brain.advance
        def lossless_advance(*args, **kwargs):
            batch = original(*args, **kwargs)
            packet = spikes.append(self.tick, batch)
            journal.append("ordered_spikes", **packet)
            return batch
        # Capture's original method becomes this writer. It archives the actual
        # returned arrays before Capture's own assertions/counting can fail.
        runner.brain.advance = lossless_advance
        try:
            super().__init__(runner, journal)
        except BaseException:
            runner.brain.advance = original
            raise
        self.restore.insert(0, (runner.brain, "advance", original))


class OriginalPrefix:
    """Stream one original 2 ms bundle at a time from the immutable gzip journal."""
    def __init__(self, reference):
        self.path = ROOT/reference["journal_gzip_path"]
        if digest_file(self.path) != reference["journal_gzip_sha256"]:
            raise ValueError("Original prefix archive changed")
        self.stream = gzip.open(self.path,"rt")
        self.initial = None
        for line in self.stream:
            event = json.loads(line)
            if event["event"] == "initial":
                self.initial = event
                break
        if self.initial is None:
            raise ValueError("Missing original initial state")
        self.checked = 0
        self.digest = hashlib.sha256()

    def check_initial(self, diagnostics):
        old = self.initial["diagnostics"]
        for field in PREFIX_NATIVE_FIELDS:
            if canonical(old[field]) != canonical(diagnostics[field]):
                raise AssertionError(f"Initial native prefix differs: {field}")

    def compare(self, tick, journal, diagnostics):
        if tick >= 1000:
            return
        old = {}
        for line in self.stream:
            event = json.loads(line)
            kind = event["event"]
            if kind.startswith("intervention_"):
                continue
            if kind == "encoder":
                old.setdefault("encoders",[]).append(event)
            else:
                old[kind] = event
            if kind == "physical_complete":
                break
        if old.get("physical_complete",{}).get("tick") != tick:
            raise AssertionError("Original prefix lacks requested complete interval")
        current = journal.current
        for old_encoder,new_encoder in zip(old["encoders"],current["encoders"],strict=True):
            for field in ("encoder","actual_local_observation","actual_drive"):
                if canonical(old_encoder[field]) != canonical(new_encoder[field]):
                    raise AssertionError(f"Ordered encoder prefix differs at tick{tick}: {field}")
        for field in ("brain_t_ms","duration_ms","actual_drive","rng_state"):
            if canonical(old["neural_start"][field]) != canonical(current["neural_start"][field]):
                raise AssertionError(f"Neural input/RNG prefix differs at tick{tick}: {field}")
        for field in PREFIX_NEURAL_FIELDS:
            if canonical(old["neural_complete"][field]) != canonical(current["neural_complete"][field]):
                raise AssertionError(f"Neural output prefix differs at tick{tick}: {field}")
        if current["ordered_spikes"]["event_sha256"] != old["neural_complete"]["full_event_sha256"]:
            raise AssertionError("Lossless ordered arrays do not reproduce original spike hash")
        for field in PREFIX_NATIVE_FIELDS:
            if canonical(old["physical_complete"]["diagnostics"][field]) != canonical(diagnostics[field]):
                raise AssertionError(f"Native prefix differs at tick{tick}: {field}")
        self.checked += 1
        self.digest.update(struct.pack("<Q",tick))
        self.digest.update(canonical({k:diagnostics[k] for k in PREFIX_NATIVE_FIELDS}))
        self.digest.update(canonical({k:current["neural_complete"][k] for k in PREFIX_NEURAL_FIELDS}))

    def close(self):
        self.stream.close()


def require_bridge_pass():
    result, plan = read_json(BRIDGE/"results.json"), read_json(BRIDGE/"plan.json")
    if not result.get("complete") or not result.get("passed"):
        raise ValueError("Complete passing rolling-bridge evidence is required before freezing/running")
    if result["plan_sha256"] != digest_file(BRIDGE/"plan.json"):
        raise ValueError("Rolling-bridge plan/result mismatch")
    review = read_json(BRIDGE/"independent-review.json")
    if (not review.get("passed")
        or review.get("plan_sha256") != digest_file(BRIDGE/"plan.json")
        or review.get("results_sha256") != digest_file(BRIDGE/"results.json")):
        raise ValueError("Matching passing independent bridge review is required")
    if {x["name"] for x in result["cases"]} != {"bounded_parity","rolling_parity","rolling_switch12"}:
        raise ValueError("Rolling-bridge evidence has different cases")
    for case in result["cases"]:
        if not case["passed"] or digest_file(ROOT/case["journal"]) != case["journal_sha256"]:
            raise ValueError("Rolling-bridge case failure or missing/changed raw proof")
    # These are the bridge's direct runtime dependencies. Unrelated full-neural
    # files may change after that bridge-only experiment and are frozen below.
    for path in ("fruitfly/flybody_bridge.py","fruitfly/flybody_worker.py",
                 "fruitfly/flybody_persistent_task.py","fruitfly/physiology.py","fruitfly/wind.py"):
        if digest_file(ROOT/path) != plan["source_hashes"][path]:
            raise ValueError("Bridge runtime changed since physical parity: "+path)


def create_plan(config_path):
    if PLAN.exists() or RESULT.exists():
        raise FileExistsError("Existing rolling-loop plan/results are immutable")
    require_bridge_pass()
    old_plan, archive = read_json(OLD/"plan.json"), read_json(OLD/"archival.json")
    config = read_json(config_path)
    config["body"]["food_position_mm"] = [6.,10.]
    config["body"]["food_radius_mm"] = 3.
    if config["body"].get("reference_mode") != "rolling" or config["body"].get("horizon_s",2.) is not None:
        raise ValueError("Explicit rolling mode and null horizon are required")
    normalized = copy.deepcopy(config)
    del normalized["body"]["reference_mode"], normalized["body"]["horizon_s"]
    if normalized != old_plan["config"]:
        raise ValueError("Configuration differs from original pair beyond rolling reference mode")
    if archive["plan_sha256"] != digest_file(OLD/"plan.json"):
        raise ValueError("Original archival plan mismatch")
    original = archive["original_results"]
    if digest_file(ROOT/original["path"]) != original["sha256"]:
        raise ValueError("Original full results unavailable or changed")
    old_results = read_json(ROOT/original["path"])
    refs = {}
    for name in ("locomotor_feedback","locomotor_sensory_block"):
        condition = next(c for c in old_results["conditions"] if c["condition"]==name)
        archived = next(j for j in archive["journals"] if f"/{name}/" in j["path"])
        if not condition["complete"] or condition["completed_ticks"] != 1000:
            raise ValueError("Original pair is incomplete")
        if condition["journal"]["sha256"] != archived["sha256"]:
            raise ValueError("Original condition/journal mismatch")
        if digest_file(ROOT/archived["gzip_path"]) != archived["gzip_sha256"]:
            raise ValueError("Missing/changed original journal")
        refs[name] = dict(journal_gzip_path=archived["gzip_path"],journal_gzip_sha256=archived["gzip_sha256"],
            original_uncompressed_sha256=archived["sha256"],original_uncompressed_bytes=archived["raw_bytes"],
            original_plan_sha256=archive["plan_sha256"],graph_sha256=condition["graph_sha256"],
            neural_parameters=condition["neural_parameters"],groups=condition["groups"],probe_ids=condition["probe_ids"])
    sources = ["scripts/check_flybody_rolling_loop.py","scripts/check_flybody_loop.py",
        str(config_path.relative_to(ROOT)),"fruitfly/simulation.py","fruitfly/neural.py","fruitfly/data.py",
        "fruitfly/body.py","fruitfly/sensors.py","fruitfly/proprioception.py","fruitfly/physiology.py",
        "fruitfly/wind.py","fruitfly/flybody_bridge.py","fruitfly/flybody_worker.py","fruitfly/flybody_persistent_task.py",
        "pyproject.toml","uv.lock","validation/flybody-source-manifest.json","validation/flybody-walking-acquisition.json",
        "validation/flybody-inference-requirements.lock","validation/flybody-stance-plan.json",
        "validation/flybody-stance-experiment.json","validation/flybody-loop/plan.json",
        "validation/flybody-loop/archival.json","validation/flybody-rolling-bridge/plan.json",
        "validation/flybody-rolling-bridge/results.json","validation/flybody-rolling-bridge/independent-review.json",
        "docs/flybody-persistent-runtime-plan.md",
        "data/processed/malecns_v1/manifest.json","data/processed/malecns_v1/neurons.feather"]
    graph_manifest=read_json(ROOT/"data/processed/malecns_v1/manifest.json")
    if (graph_manifest["neurons"],graph_manifest["edges"]) != (166700,25582938):
        raise ValueError("Wrong full graph")
    plan=dict(schema_version=1,created_utc=datetime.now(timezone.utc).isoformat(),
        source_revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        config=config,source_sha256={p:digest_file(ROOT/p) for p in sources},
        expected_neurons=166700,expected_edges=25582938,seed=11,coupling_s=DT,duration_s=12.,ticks=6000,
        graph_sha256=refs["locomotor_feedback"]["graph_sha256"],
        neural_parameters=refs["locomotor_feedback"]["neural_parameters"],references=refs,
        conditions=[dict(name="locomotor_feedback",assay="motor_probe",outgoing_blocks=[],motor_mute=True),
            dict(name="locomotor_sensory_block",assay="motor_probe",outgoing_blocks=list(SENSORY_GROUPS),motor_mute=True),
            dict(name="sensory_only",assay="sensory",outgoing_blocks=[],motor_mute=False)],
        mute_intervals_ticks=[list(pair) for pair in MUTES],
        mute_intervals_s=[[a*DT,b*DT] for a,b in MUTES],
        initial_prefix_ticks=1000,prefix_native_fields=PREFIX_NATIVE_FIELDS,prefix_neural_fields=PREFIX_NEURAL_FIELDS,
        prefix_exclusions="Rolling bookkeeping fields and cached post-step reference tails differ by design; original archive has no actor-input array. Physical/action/target fields and ordered neural input/RNG/spike hashes must remain exact.",
        spike_format=dict(magic=MAGIC.decode(),file_header="8s uint32 JSONlength JSONbytes",
            block_header="<QQdd (32bytes): couplingtick,eventcount,startms,endms",
            payload="N<int64 bodyIDs>,then N<float64 absolutems>; unchanged ordered batch arrays",compression="gzip mtime0; flush after every block"),
        gates=["All three6000tick attempts complete without physical/source termination, nonfinite arrays or native warnings",
            "Each completed coupling interval has brain/body/native clock error<1e-9s and actual native tick correct",
            "Same-seed initial reset, render and advance0 preserve exact initial native/neural state",
            "All real encoders retain exact ordered input composition, zero-rate members and source-output mask",
            "Original two locomotor trials reproduced through1000ticks for declared native fields, drives, RNG and ordered spike hashes",
            "Rolling reference storage66frames, actor preview65, origin/source control tick advance without recenter/reset",
            "Every completed neural batch has a lossless framed spike block whose event hash equals Capture's full hash",
            "Exact neutral hold/action scaling, current command map and physical antenna/contact/tibia feedback mappings",
            "All three declared motor-readout mutes produce rest/zero drive while recorded neural spikes are retained",
            "Normalized resource residual<1e-8 per completed step; workers closed/reaped; hashes unchanged"],
        nongates=["No minimum walking, post-mute movement, feeding, natural navigation, biological voltage range or indefinite stability",
            "Sensory-only trial has no DN probe and no imposed motor mutes; cannot compare its full prefix to original on-food trials",
            "No afferent equality required after locomotor feedback and blocked trajectories diverge",
            "Graph transmission during identical input history is reported separately without a new behavior threshold"],
        failure_retention="Gzip JSON event journal and lossless binary spikes flushed each event/batch. Preserve latest native/host cache plus full brain checkpoint, stage and completed/pending clocks before cleanup. No replacement trial or automatic reset.",
        data_scope="Female-derived pretrained motor surrogate, full male graph, current uncalibrated odor/sweet/club encoders; vision/wind neural/grooming/flight disabled")
    OUT.mkdir(parents=True,exist_ok=True)
    write_json(PLAN,plan)
    print("Frozen rolling-loop plan",digest_file(PLAN),flush=True)


def file_receipt(path):
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=digest_file(path))


def retain_actual_state(runner, capture, spikes, folder, stage):
    """Save actual states before cleanup, even if the latest body observation is invalid."""
    retained = dict(stage=stage,brain_time_ms=runner.brain.time_ms,
        brain_tick=runner.brain.tick,completed_coupling_spikes=runner.total_spikes,
        completed_coupling_edge_visits=runner.edge_visits,
        latest_lossless_neural_batch=spikes.last if spikes else None,
        latest_completed_capture_interval=capture.neural if capture else None,
        runner_failure=runner._failure)
    for name, reader in (
        ("cached_native_state",runner.body.diagnostics),
        ("public_snapshot",runner.snapshot),
        ("cached_physical_observation",lambda:copy.deepcopy(runner.body._observation)),
        ("physiology",runner.body.physiology.snapshot),
        ("food_resource",lambda:asdict(runner.body.food)),
        ("water_resource",lambda:asdict(runner.body.water)),
    ):
        try:
            retained[name] = reader()
        except BaseException as error:
            retained[name+"_error"] = repr(error)
    native=retained.get("cached_native_state") or {}
    retained["stage_clocks"] = dict(brain_t_ms=runner.brain.time_ms,
        native_time_s=native.get("native_time_s"),native_control_tick=native.get("tick"),
        host_physiology_t_s=None,
        host_physiology_clock_note="No independent elapsed physiology clock is exposed. A partial native step may not update physiology; do not infer its clock from native or observation time.",
        cached_observation_t_s=(retained.get("cached_physical_observation") or {}).get("t_s"),
        latest_neural_interval_end_ms=spikes.last.get("end_ms") if spikes and spikes.last else None)
    checkpoint=folder/"brain-final-or-failure.npz"
    try:
        runner.brain.save_checkpoint(checkpoint)
        retained["brain_checkpoint"] = file_receipt(checkpoint)
    except BaseException as error:
        retained["brain_checkpoint_error"] = repr(error)
    path=folder/"actual-state-before-cleanup.json"
    write_json(path,retained)
    return dict(state=file_receipt(path),stage_clocks=retained["stage_clocks"],
        brain_checkpoint=retained.get("brain_checkpoint"),
        brain_checkpoint_error=retained.get("brain_checkpoint_error"),
        completed_coupling_spikes=runner.total_spikes,
        latest_lossless_neural_batch=spikes.last if spikes else None,
        cached_native_finite=native.get("finite"),cached_source_terminated=native.get("source_terminated"))


def verify_spike_archive(spike_path,journal_path):
    """Read every completed binary block back and match its ordered-event journal receipt."""
    def packets():
        with gzip.open(journal_path,"rt") as stream:
            for line in stream:
                value=json.loads(line)
                if value["event"]=="ordered_spikes":
                    yield value
    blocks=events=0
    for block,packet in zip(read_spike_blocks(spike_path),packets(),strict=True):
        for field in ("tick","start_ms","end_ms","event_sha256"):
            if block[field]!=packet[field]:
                raise AssertionError("Saved ordered-spike block differs from receipt: "+field)
        if len(block["neuron_ids"])!=packet["events"]:
            raise AssertionError("Saved ordered-spike event count mismatch")
        if block["tick"]!=blocks:
            raise AssertionError("Missing/reordered neural spike block")
        times=block["times_ms"]
        if not np.isfinite(times).all() or np.any(times<block["start_ms"]) or np.any(times>=block["end_ms"]):
            raise AssertionError("Spike outside archived neural interval")
        blocks+=1; events+=len(times)
    return dict(passed=True,blocks=blocks,events=events,
        method="Read/decompress all framed arrays and compare unchanged ordered event hashes, counts, block order and time bounds against flushed journal receipts")


def self_test():
    """Exercise recording/failure paths with fake states; never construct a simulator."""
    checks=[]
    (ROOT/"runs").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rolling-loop-recorder-test-",dir=ROOT/"runs") as tmp:
        folder=Path(tmp)
        journal=CompressedJournal(folder/"events.jsonl.gz")
        spikes=OrderedSpikes(folder/"spikes.bin.gz",graph_sha256="fake-graph",plan_sha256="fake-plan")
        # Unsorted/repeated IDs above float64's exact integer range and signed
        # zero timestamps make sorting, lossy casts and rounding observable.
        ids=np.asarray([9007199254740993,17,9007199254740993,4],dtype="<i8")
        times=np.asarray([-0.,.1,.1,1.9],dtype="<f8")
        batches=[SimpleNamespace(neuron_ids=ids,times_ms=times,total_spikes=4,start_ms=0.,end_ms=2.),
            SimpleNamespace(neuron_ids=np.asarray([],dtype="<i8"),times_ms=np.asarray([],dtype="<f8"),
                total_spikes=0,start_ms=2.,end_ms=4.)]
        for tick,batch in enumerate(batches):
            journal.append("ordered_spikes",**spikes.append(tick,batch))
        spikes.close();journal.close()
        decoded=list(read_spike_blocks(spikes.path))
        assert len(decoded)==2
        for batch,block in zip(batches,decoded,strict=True):
            assert block["neuron_ids"].tobytes()==batch.neuron_ids.tobytes()
            assert block["times_ms"].tobytes()==batch.times_ms.tobytes()
        assert verify_spike_archive(spikes.path,journal.path)==dict(passed=True,blocks=2,events=4,
            method="Read/decompress all framed arrays and compare unchanged ordered event hashes, counts, block order and time bounds against flushed journal receipts")
        raw=gzip.decompress(spikes.path.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==spikes.receipt()["uncompressed_sha256"]
        checks.append("ordered ID/time bytes, empty batch, receipts and full readback")
        first_payload=spikes.last["uncompressed_offset"]
        # Valid gzip members containing malformed/truncated binary records.
        corruptions={"short_metadata_size":raw[:10],"short_metadata":raw[:20],
            "short_block_header":raw[:first_payload+7],"short_arrays":raw[:first_payload-1]}
        for name,payload in corruptions.items():
            path=folder/(name+".gz");path.write_bytes(gzip.compress(payload,mtime=0))
            try:list(read_spike_blocks(path))
            except (EOFError,ValueError,json.JSONDecodeError):pass
            else:raise AssertionError("Malformed binary archive accepted: "+name)
        path=folder/"short_gzip.gz";path.write_bytes(spikes.path.read_bytes()[:-8])
        try:list(read_spike_blocks(path))
        except EOFError:pass
        else:raise AssertionError("Truncated gzip trailer accepted")
        checks.append("truncated metadata, block headers, ID/time arrays and gzip rejected")

        @dataclass
        class Resource:
            remaining_uj: float = 123.
        class FakeBrain:
            time_ms=4.
            tick=40
            def save_checkpoint(self,path):
                np.savez(path,pending=np.asarray([[1.,-7.],[2.,3.]]),rng=np.asarray([11,12]))
        def snapshot_error():
            raise RuntimeError("Intentional invalid public observation")
        for name,public_snapshot in (("completed",lambda:{"t_s":.004}),
                                     ("partial_failure",snapshot_error)):
            destination=folder/name;destination.mkdir()
            native=dict(native_time_s=.0034,tick=1,finite=False,source_terminated=True,
                qpos=[float("nan")]) if name=="partial_failure" else dict(
                native_time_s=.004,tick=2,finite=True,source_terminated=False,qpos=[0.])
            body=SimpleNamespace(diagnostics=lambda:copy.deepcopy(native),
                _observation={"t_s":.002},physiology=SimpleNamespace(snapshot=lambda:{"energy_uj":120.}),
                food=Resource(),water=Resource())
            runner=SimpleNamespace(brain=FakeBrain(),body=body,snapshot=public_snapshot,
                total_spikes=3,edge_visits=7,_failure={"pending_spikes":4} if name=="partial_failure" else None)
            receipt=retain_actual_state(runner,None,spikes,destination,"fake_"+name)
            saved=read_json(destination/"actual-state-before-cleanup.json")
            assert receipt["brain_checkpoint"] is not None
            assert saved["stage_clocks"]["host_physiology_t_s"] is None
            assert saved["stage_clocks"]["cached_observation_t_s"]==.002
            assert saved["stage_clocks"]["brain_t_ms"]==4.
            assert saved["stage_clocks"]["native_time_s"]==native["native_time_s"]
            assert ("public_snapshot_error" in saved)==(name=="partial_failure")
            if name=="partial_failure":
                assert saved["cached_native_state"]["qpos"]==[{"nonfinite":"nan"}]
                assert saved["runner_failure"]=={"pending_spikes":4}
            with np.load(destination/"brain-final-or-failure.npz") as checkpoint:
                np.testing.assert_array_equal(checkpoint["pending"],[[1.,-7.],[2.,3.]])
            assert digest_file(destination/"brain-final-or-failure.npz")==receipt["brain_checkpoint"]["sha256"]
        checks.append("fake completed/partial failed runner retains independent clocks, nonfinite native evidence and pending checkpoint")
    print(json.dumps(dict(self_test_passed=True,checks=checks,simulation_constructed=False),indent=2))


def run_condition(condition,plan,root_folder):
    from fruitfly.simulation import SimulationRunner
    from PIL import Image
    name=condition["name"]
    folder=root_folder/name;folder.mkdir()
    journal=CompressedJournal(folder/"events.jsonl.gz")
    config=copy.deepcopy(plan["config"])
    config["run_dir"]=str(folder/"runner")
    config["assay"]=condition["assay"]
    record=dict(condition=name,design=condition,complete=False,returned_physical_ticks=0,
        completed_physical_ticks=0,validated_physical_ticks=0,
        failures=[],checks={},run_dir=str(folder.relative_to(ROOT)))
    metrics=dict(completed_coupling_spikes=0,completed_coupling_edge_visits=0,
        monitored_spikes=Counter(),behavior_counts=Counter(),sweet_input_ever_positive=False,
        max_input_event_rate_hz={g:0. for g in SENSORY_GROUPS},
        min_voltage_mv=None,max_voltage_mv=None,min_up_z=None,
        max_clock_error_s=0.,max_resource_residual=0.,max_abs_qacc_native=0.,
        planar_path_mm=0.,
        mute_intervals=[dict(first_tick=a,end_tick=b,completed_ticks=0,neural_spikes=0) for a,b in MUTES]
            if condition["motor_mute"] else [])
    runner=capture=process=spikes=prefix=None
    latest_state=None
    start=None
    try:
        journal.append("condition_start",condition=condition,config=config,plan_sha256=digest_file(PLAN))
        runner=SimulationRunner(config);process=runner.body._proc
        record["worker_pid"]=process.pid
        if (runner.brain.n_neurons,runner.brain.n_edges)!=(plan["expected_neurons"],plan["expected_edges"]):
            raise AssertionError("Wrong full neural graph")
        if runner.brain.graph_sha256!=plan["graph_sha256"] or asdict(runner.brain.parameters)!=plan["neural_parameters"]:
            raise AssertionError("Graph/parameters differ from original pair")
        metadata=runner.body.snapshot()["backend"]
        if (metadata["reference_mode"],metadata["horizon_s"],metadata["reference_frames"],metadata["preview_frames"])!=("rolling",None,66,65):
            raise AssertionError("Not the declared rolling reference backend")
        if (metadata["physics_timestep_s"],metadata["control_timestep_s"])!=(.0002,.002):
            raise AssertionError("Native clocks changed")
        record["body_metadata"]=metadata
        initial=inspect_physical(runner)
        initial_hash=native_state_hash(initial)
        runner.control({"type":"reset"})
        if native_state_hash(inspect_physical(runner))!=initial_hash:
            raise AssertionError("Same-seed reset did not restore initial native state")
        before=runner.brain.state_dict()
        runner.advance(0)
        Image.fromarray(runner.render("overview")).save(folder/"initial.png")
        after=runner.brain.state_dict()
        for key,value in before.items():
            if isinstance(value,np.ndarray):np.testing.assert_array_equal(value,after[key])
            elif value!=after[key]:raise AssertionError("Render/zero advance changed brain: "+key)
        if native_state_hash(inspect_physical(runner))!=initial_hash:
            raise AssertionError("Render/zero advance changed native state")
        del before,after
        record["checks"]["initial_lifecycle"]=True
        for group in condition["outgoing_blocks"]:
            runner.control({"type":"synaptic_output","group":group,"blocked":True})
        spikes=OrderedSpikes(folder/"spikes.bin.gz",graph_sha256=runner.brain.graph_sha256,plan_sha256=digest_file(PLAN))
        capture=LosslessCapture(runner,journal,spikes)
        mask=np.zeros(runner.brain.n_neurons,dtype=bool)
        for group in condition["outgoing_blocks"]:mask[runner._input_group(group)]=True
        groups={k:dict(indices=v.tolist(),neuron_ids=runner.graph.neuron_ids[v].tolist(),
            types=runner.graph.neurons.iloc[v].type.tolist()) for k,v in capture.monitor_groups.items()}
        record["groups"]=groups
        record["probe_ids"]=runner.graph.neuron_ids[runner.probe_indices].tolist()
        record["graph_sha256"]=runner.brain.graph_sha256
        record["neural_parameters"]=asdict(runner.brain.parameters)
        latest_state=runner.snapshot()
        journal.append("initial",state=latest_state,diagnostics=initial,groups=groups,probe_ids=record["probe_ids"])
        if name in plan["references"]:
            reference=plan["references"][name]
            if groups!=reference["groups"] or record["probe_ids"]!=reference["probe_ids"]:
                raise AssertionError("Original source/motor group identities changed")
            prefix=OriginalPrefix(reference);prefix.check_initial(initial)
        previous_xy=np.asarray(initial["pose_cm_quat"][:2],dtype=float)*10
        intervention_map={edge:(i==0) for pair in MUTES for i,edge in enumerate(pair)} if condition["motor_mute"] else {}
        start=time.perf_counter()
        for tick in range(plan["ticks"]):
            capture.begin(tick)
            if tick in intervention_map:
                command=dict(type="ablation",enabled=intervention_map[tick])
                journal.append("intervention_start",tick=tick,command=command)
                runner.control(command)
                journal.append("intervention_complete",tick=tick,state=runner.snapshot())
            np.testing.assert_array_equal(runner.brain.ablated,mask)
            journal.append("coupling_start",tick=tick,physical_t_s=runner.body.time_s,
                brain_t_ms=runner.brain.time_ms,physical_observation=runner.body.observe())
            state=runner.advance(DT)
            record["returned_physical_ticks"]=tick+1
            record["completed_physical_ticks"]=tick+1
            latest_state=state
            diagnostics=inspect_physical(runner)
            # Save completed state before evaluator assertions. physical_summary
            # can itself fail, but must not erase the actual native return.
            journal.append("physical_returned",tick=tick,diagnostics=diagnostics,state=state)
            summary=physical_summary(runner,diagnostics,state,tick+1)
            journal.append("physical_complete",tick=tick,checks=summary)
            neural=capture.neural
            if neural is None:raise AssertionError("Missing captured completed neural interval")
            metrics["completed_coupling_spikes"]+=neural["total_spikes"]
            metrics["completed_coupling_edge_visits"]+=neural["traversed_edges"]
            metrics["monitored_spikes"].update(neural["monitored_counts"])
            metrics["behavior_counts"][state["motor"]["behavior"]]+=1
            metrics["sweet_input_ever_positive"] |= neural["positive_input_cells_by_encoder"]["sweet"]>0
            for group in SENSORY_GROUPS:
                metrics["max_input_event_rate_hz"][group]=max(metrics["max_input_event_rate_hz"][group],neural["max_input_event_rate_hz_by_encoder"][group])
            for key,value,func in (("min_voltage_mv",neural["voltage_mv"]["min"],min),
                ("max_voltage_mv",neural["voltage_mv"]["max"],max),("min_up_z",summary["up_z"],min)):
                metrics[key]=value if metrics[key] is None else func(metrics[key],value)
            metrics["max_clock_error_s"]=max(metrics["max_clock_error_s"],summary["clock_max_error_s"])
            metrics["max_resource_residual"]=max(metrics["max_resource_residual"],summary["resource_residual_max"])
            metrics["max_abs_qacc_native"]=max(metrics["max_abs_qacc_native"],summary["qacc_abs_max_native"])
            xy=np.asarray(diagnostics["pose_cm_quat"][:2],dtype=float)*10
            metrics["planar_path_mm"]+=float(np.linalg.norm(xy-previous_xy));previous_xy=xy
            for window in metrics["mute_intervals"]:
                if window["first_tick"]<=tick<window["end_tick"]:
                    window["completed_ticks"]+=1;window["neural_spikes"]+=neural["total_spikes"]
            if summary["clock_max_error_s"]>=1e-9 or diagnostics["tick"]!=tick+1:
                raise AssertionError("Completed neural/host/native clocks disagree")
            if not(summary["finite_native_arrays"] and diagnostics["finite"] and neural["finite_voltage"] and neural["finite_synaptic_state"]):
                raise AssertionError("Nonfinite actual physical/neural state")
            if any(summary["warnings"]) or diagnostics["source_terminated"]:
                raise AssertionError("Native warning/source termination retained")
            if summary["resource_residual_max"]>=1e-8:
                raise AssertionError("Resource ledger residual exceeded declared bound")
            if not neural["listed_input_refractory_zero"]:
                raise AssertionError("Input refractory contract changed")
            if neural["full_event_sha256"]!=spikes.last["event_sha256"] or spikes.last["tick"]!=tick:
                raise AssertionError("Lossless ordered batch differs from Capture")
            if diagnostics["reference_qpos_shape"]!=[66,7] or diagnostics["reference_qvel_shape"]!=[66,6]:
                raise AssertionError("Rolling reference storage changed")
            if diagnostics["reference_buffer_origin"]!=tick or diagnostics["source_control_tick"]!=tick+1:
                raise AssertionError("Rolling origin/native control clock changed")
            if summary["neutral_hold_required"] and not summary["neutral_hold_exact"]:
                raise AssertionError("Exact neutral-zero stance not applied")
            if condition["motor_mute"] and any(a<=tick<b for a,b in MUTES):
                if state["motor"]!={"behavior":"rest","left":0.,"right":0.}:
                    raise AssertionError("Muted motor readout moved away from rest/zero")
            if prefix is not None:prefix.compare(tick,journal,diagnostics)
            record["validated_physical_ticks"]=tick+1
            if (tick+1)%250==0:
                write_json(folder/"progress.json",dict(completed_physical_ticks=tick+1,
                    native_t_s=diagnostics["native_time_s"],brain_t_ms=runner.brain.time_ms,
                    prefix_checked_ticks=prefix.checked if prefix else None,metrics=metrics))
                print(name,"completed",tick+1,"ticks",state["behavior"],flush=True)
        record["loop_wall_s"]=time.perf_counter()-start
        native_hash=native_state_hash(inspect_physical(runner))
        for camera in ("overview","follow"):
            Image.fromarray(runner.render(camera)).save(folder/f"final-{camera}.png")
            if native_state_hash(inspect_physical(runner))!=native_hash:
                raise AssertionError("Final render changed native state: "+camera)
        record["checks"]["all_completed_interval_checks"]=True
        record["complete"]=True
    except BaseException as error:
        record["failures"].append(dict(type=type(error).__name__,message=str(error),
            traceback=traceback.format_exc(),stage=journal.last_stage,
            requested_tick=capture.tick if capture else None))
        journal.append("condition_failure",failure=record["failures"][-1])
    finally:
        if start is not None and "loop_wall_s" not in record:
            record["loop_wall_s_until_failure"]=time.perf_counter()-start
        if prefix is not None:
            record["original_prefix"]=dict(checked_ticks=prefix.checked,
                required_ticks=1000,passed=prefix.checked==1000,matched_content_sha256=prefix.digest.hexdigest())
            prefix.close()
        else:record["original_prefix"]=dict(required=name in plan["references"],passed=name not in plan["references"])
        if runner is not None:
            try:
                retained=retain_actual_state(runner,capture,spikes,folder,journal.last_stage)
                record["actual_final_or_failure_state"]=retained
                journal.append("actual_state_retained",receipt=retained)
            except BaseException as error:
                record["failures"].append(dict(state_retention_error=repr(error)))
                journal.append("state_retention_failure",error=repr(error))
            if latest_state is not None:
                record["last_completed_public_summary"]=dict(t_s=latest_state["t_s"],
                    brain_t_s=latest_state["brain_t_s"],physiology=latest_state["physiology"],
                    resource_balance=latest_state["resource_balance"],motor=latest_state["motor"])
        if capture is not None:capture.close()
        if runner is not None:
            try:runner.close()
            except BaseException as error:
                record["failures"].append(dict(cleanup_error=repr(error)))
                journal.append("cleanup_failure",error=repr(error))
        record["worker_exit_code_after_close"]=process.poll() if process else None
        if spikes is not None:
            spikes.close();record["lossless_spikes"]=spikes.receipt()
        journal.append("condition_end",complete=record["complete"],
            returned_physical_ticks=record["returned_physical_ticks"],
            validated_physical_ticks=record["validated_physical_ticks"])
        journal.close();record["journal"]=journal.receipt()
        if spikes is not None:
            try:record["spike_archive_readback"]=verify_spike_archive(spikes.path,journal.path)
            except BaseException as error:
                record["spike_archive_readback"]=dict(passed=False,error=repr(error))
                record["failures"].append(dict(spike_readback_error=repr(error)))
        record["metrics"]=metrics
        record["files"]={str(p.relative_to(folder)):file_receipt(p) for p in sorted(folder.rglob("*")) if p.is_file()}
        record["checks"].update(
            completed_declared_duration=record["complete"] and record["validated_physical_ticks"]==plan["ticks"],
            no_retained_failures=not record["failures"],
            original_prefix=record["original_prefix"]["passed"],
            all_spike_blocks=spikes is not None and spikes.blocks==plan["ticks"],
            lossless_readback=record.get("spike_archive_readback",{}).get("passed",False),
            worker_reaped=process is not None and process.poll() is not None,
            state_and_checkpoint_retained=record.get("actual_final_or_failure_state",{}).get("brain_checkpoint") is not None)
        record["all_condition_gates_pass"]=all(record["checks"].values())
        write_json(folder/"condition-summary.json",record)
    return record


def paired_journal_mechanisms(conditions):
    records=[]
    fields=("tick","ordered_drive_sha256","downstream_event_sha256","rng_state_before","rng_state_after")
    for condition in conditions:
        neural=[]
        with gzip.open(ROOT/condition["journal"]["path"],"rt") as stream:
            for line in stream:
                event=json.loads(line)
                if event["event"]=="neural_complete":neural.append({k:event[k] for k in fields})
        records.append(dict(neural_intervals=neural))
    return paired_mechanisms(records)


def run():
    if RESULT.exists():raise FileExistsError("Existing rolling-loop results must be preserved")
    plan=read_json(PLAN)
    require_bridge_pass()
    for path,expected in plan["source_sha256"].items():
        if digest_file(ROOT/path)!=expected:raise ValueError("Source changed since frozen plan: "+path)
    folder=ROOT/"runs"/("flybody-rolling-loop-"+digest_file(PLAN)[:12]);folder.mkdir()
    report=dict(schema_version=1,complete=False,plan_sha256=digest_file(PLAN),run_dir=str(folder.relative_to(ROOT)),
        biological_behavior_validated=False,gain_tuning=None,conditions=[])
    write_json(RESULT,report)
    for condition in plan["conditions"]:
        record=run_condition(condition,plan,folder)
        report["conditions"].append(record);write_json(RESULT,report)
    try:report["locomotor_paired_mechanisms"]=paired_journal_mechanisms(report["conditions"][:2])
    except BaseException as error:report["paired_comparison_failure"]=dict(error=repr(error),traceback=traceback.format_exc())
    report["source_hashes_unchanged_after"]={p:digest_file(ROOT/p)==h for p,h in plan["source_sha256"].items()}
    report["complete"]=True # Every attempt concluded, independently of success.
    report["all_declared_gates_pass"]=(len(report["conditions"])==3
        and all(c["all_condition_gates_pass"] for c in report["conditions"])
        and all(report["source_hashes_unchanged_after"].values()) and "paired_comparison_failure" not in report)
    write_json(RESULT,report)
    print(json.dumps(dict(complete=True,all_declared_gates_pass=report["all_declared_gates_pass"],
        conditions=[dict(name=c["condition"],completed=c["completed_physical_ticks"],passed=c["all_condition_gates_pass"]) for c in report["conditions"]]),indent=2),flush=True)
    if not report["all_declared_gates_pass"]:raise SystemExit(1)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan",action="store_true")
    mode.add_argument("--run",action="store_true")
    mode.add_argument("--self-test",action="store_true")
    parser.add_argument("--config",type=Path,default=ROOT/"configs/male-flybody-rolling-probe.json")
    args=parser.parse_args()
    if args.self_test:self_test()
    elif args.plan:create_plan(args.config.resolve())
    else:run()
