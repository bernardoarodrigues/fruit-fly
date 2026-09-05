#!/usr/bin/env python3
"""Post-hoc navigation population readout of the already audited 60-trial panel.

No neural model executes. Counts come from pinned final checkpoints whose raw
spike provenance was independently audited before this population selection.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/navigation-ladder-readout-plan.json"
RESULT = ROOT / "validation/navigation-ladder-readouts.json"
ARRAYS = ROOT / "validation/navigation-ladder-readouts.npz"
ANATOMY = ROOT / "validation/navigation-ladder-anatomy.json"
PANEL = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
PANEL_SHA = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
COMBINED = ROOT / "validation/inhibitory-recurrent-panel-combined-analysis.json"
COMBINED_SHA = "bb42919231572491e2adbd4adfa67f53c1ce0b87bdd5a8f229628b0797488d29"
checks = 0


def require(ok, message):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(message)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def record(path):
    path = Path(path)
    b = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(b), sha256=sha(b))


def load(path):
    return json.loads(Path(path).read_text())


def typed_array(node, archive):
    meta = node["array"]; a = archive[meta["key"]]
    require(list(a.shape) == meta["shape"] and a.dtype.str == meta["dtype"] and
            a.nbytes == meta["bytes"] and sha(a.tobytes()) == meta["sha256"], "typed payload")
    return a


def prepare():
    if PLAN.exists():
        raise FileExistsError("Preserve the first readout plan")
    require(record(PANEL)["sha256"] == PANEL_SHA and record(COMBINED)["sha256"] == COMBINED_SHA, "original panel pins")
    panel = load(PANEL); combined = load(COMBINED)
    require(combined["passed"] and combined["independently_reviewed_trials"] == 60, "completed audited panel")
    anatomy = load(ANATOMY)
    require(anatomy["passed"] and anatomy["source_unchanged"] and not anatomy["errors"], "passed unchanged anatomy audit")
    require(isinstance(anatomy["groups"], dict) and "DN_all" in anatomy["groups"], "explicit cohort manifest")
    records = [record(p) for p in [Path(__file__), PANEL, COMBINED, ANATOMY, ROOT / "data/processed/malecns_v1/neuron_ids.npy"]]
    cp = []
    for spec in panel["order"]:
        directory = ROOT / panel["run_dir"] / spec["name"]
        result = load(directory / "result.json")
        terminal = load(directory / "terminal.json")
        amap = {a["path"]: a for a in result["artifacts"]}
        rr = record(directory / "result.json"); tt = record(directory / "terminal.json")
        require(rr == terminal["result"] and terminal["complete"], "terminal result")
        records += [rr, tt]
        for suffix in [".json", ".npz"]:
            r = record(directory / ("checkpoint-30000" + suffix))
            require(r == amap[r["path"]], "checkpoint pinned in completed trial")
            records.append(r)
        cp.append(dict(spec=spec, checkpoint_json=str((directory / "checkpoint-30000.json").relative_to(ROOT)),
                       checkpoint_npz=str((directory / "checkpoint-30000.npz").relative_to(ROOT))))
    plan = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(), input_records=records, trials=cp,
        population_selection="Post-hoc diagnostic requested after the full factorial result; not a preregistered biological prediction or unseen validation.",
        cohort_names=list(anatomy["groups"]), edges_ticks=panel["window_edges_ticks"], dt_s=.0001,
        outputs=[str(RESULT.relative_to(ROOT)), str(ARRAYS.relative_to(ROOT))],
        method="Use the already raw-spike-audited per-neuron seven-window counts. Retain each selected cell separately and overlapping named groups without summing groups into one population. No graph propagation or integrator execution.",
        comparisons=["EA minus matched constant in pulse", "IA minus matched constant in pulse", "EA minus IA in pulse", "each input-off window versus its matched constant trial", "source-output-blocked and no-input controls"],
        limits=["No wind, hunger, reflection, clamp or body intervention was part of these trials.",
                "Coarse complete-window counts cannot identify latency, synaptic depression, a transmission bottleneck or the first causal failure boundary.",
                "Annotated soma/root side and instance column tokens are not a calibrated circular heading coordinate or a mirror pairing.",
                "Activity at every named stage does not demonstrate the proposed route carried the signal; overlapping and recurrent paths exist.",
                "All60trials are reused from the preceding factorial; no additional independent simulation or biological evidence unit is created."])
    PLAN.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps(record(PLAN)))


def analyze():
    if RESULT.exists() or ARRAYS.exists():
        raise FileExistsError("Preserve first readout execution")
    plan = load(PLAN); plan_record = record(PLAN)
    for r in plan["input_records"]:
        require(record(ROOT / r["path"]) == r, "unchanged readout input " + r["path"])
    anatomy = load(ANATOMY); groups = anatomy["groups"]
    graph_ids = np.load(ROOT / "data/processed/malecns_v1/neuron_ids.npy", allow_pickle=False)
    selected = np.unique(np.concatenate([np.asarray(g["indices"], dtype=np.int64) for g in groups.values()]))
    require(selected.ndim == 1 and len(selected) > 0 and selected[0] >= 0 and selected[-1] < len(graph_ids), "selected graph indices")
    for name, g in groups.items():
        idx = np.asarray(g["indices"], dtype=np.int64)
        require(len(idx) == len(np.unique(idx)) and graph_ids[idx].tolist() == g["body_ids"], "cohort identity " + name)
    edges = np.asarray(plan["edges_ticks"]); duration = np.diff(edges) * plan["dt_s"]
    all_counts = []; all_final_v = []; all_final_s = []; all_final_h = []
    trials = []; lookup = {}
    for t in plan["trials"]:
        spec = t["spec"]
        meta = dict(load(ROOT/t["checkpoint_json"])["tree"]["items"])
        require(meta["tick"]["value"] == 30000 and meta["coherent_state"]["value"] and
                meta["arm"]["value"] == spec["arm"] and meta["seed"]["value"] == spec["seed"], "terminal checkpoint state identity")
        with np.load(ROOT/t["checkpoint_npz"], allow_pickle=False) as z:
            counts = typed_array(meta["window_counts_observed"], z)
            require(counts.shape == (7, len(graph_ids)) and counts.dtype.str == "<i8" and (counts >= 0).all(), "complete count array")
            v = typed_array(meta["v"], z); s = typed_array(meta["s"], z); h = typed_array(meta["h"], z)
        all_counts.append(counts[:,selected]); all_final_v.append(v[selected]); all_final_s.append(s[selected]); all_final_h.append(h[selected])
        cm = {}
        for name, g in groups.items():
            idx = np.asarray(g["indices"], dtype=np.int64)
            if len(idx) == 0:
                cm[name] = dict(availability=g.get("availability", "empty"), count=0, counts=None, mean_rates_hz=None)
                continue
            c = counts[:,idx]; totals = c.sum(axis=1); active = (c > 0).sum(axis=1)
            cm[name] = dict(availability="mapped", count=len(idx), counts=totals.tolist(),
                mean_rates_hz=(totals/(duration*len(idx))).tolist(), active_cells=active.tolist(),
                active_fraction=(active/len(idx)).tolist(),
                max_cell_rates_hz=(c.max(axis=1)/duration).tolist(),
                off_spikes=int(totals[4:].sum()), final_voltage_mv_range=[float(v[idx].min()),float(v[idx].max())])
        tr = dict(spec=spec, cohorts=cm); trials.append(tr); lookup[spec["arm"],spec["seed"],spec["condition"]] = tr
    contrasts = []
    for arm in ["C0","C1","H0","H1"]:
        for seed in [11,12,13]:
            for name,g in groups.items():
                if not g["indices"]:
                    contrasts.append(dict(arm=arm,seed=seed,cohort=name,available=False)); continue
                r = {c:np.array(lookup[arm,seed,c]["cohorts"][name]["mean_rates_hz"]) for c in
                     ["no_input","constant_baseline","ethyl_acetate","isoamyl_acetate","ethyl_acetate_source_outputs_blocked"]}
                contrasts.append(dict(arm=arm,seed=seed,cohort=name,available=True,
                    EA_minus_constant_hz=(r["ethyl_acetate"]-r["constant_baseline"]).tolist(),
                    IA_minus_constant_hz=(r["isoamyl_acetate"]-r["constant_baseline"]).tolist(),
                    EA_minus_IA_hz=(r["ethyl_acetate"]-r["isoamyl_acetate"]).tolist()))
    np.savez_compressed(ARRAYS, graph_indices=selected, body_ids=graph_ids[selected],
        counts=np.array(all_counts,dtype=np.int64), final_v=np.array(all_final_v), final_s=np.array(all_final_s), final_h=np.array(all_final_h))
    for r in plan["input_records"]:
        require(record(ROOT/r["path"]) == r, "unchanged input at end")
    require(record(PLAN) == plan_record, "unchanged plan")
    out = dict(schema=1, passed=True, created_utc=datetime.now(timezone.utc).isoformat(), plan=plan_record,
        array_artifact=record(ARRAYS), check_count=checks, distinct_selected_cells=len(selected),
        group_definitions=groups, trials=trials, contrasts=contrasts, window_edges_ticks=edges.tolist(),
        dt_s=plan["dt_s"], limits=plan["limits"], population_selection=plan["population_selection"])
    RESULT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(passed=True, checks=checks, result=record(RESULT), arrays=record(ARRAYS))))


def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=["prepare","analyze"]);args=p.parse_args()
    if args.action=="prepare": prepare()
    else:
        try: analyze()
        except (Exception, KeyboardInterrupt) as e:
            failure=RESULT.with_name("navigation-ladder-readouts-first-failure.json")
            if not failure.exists():
                failure.write_text(json.dumps(dict(passed=False,error=repr(e),traceback=traceback.format_exc(),checks=checks),indent=2)+"\n")
            raise


if __name__ == "__main__":
    main()
