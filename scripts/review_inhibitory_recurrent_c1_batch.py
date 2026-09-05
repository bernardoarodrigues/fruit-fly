#!/usr/bin/env python3
"""Complete only missing frozen C1 saved-data reviews, sequentially."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-recurrent-panel-plan.json"
READER = ROOT / "scripts/review_inhibitory_recurrent_panel_active.py"
OUT = ROOT / "validation/inhibitory-recurrent-panel-c1-batch-index.json"
PLAN_SHA = "c7af957eb89a04a3edbbcc2a9d9b2b2d6936a07c4b3fe019448287467e9183d5"
READER_SHA = "2329e31a90bfaae48372a36ce3ccd03146bdec785dff9c511737c10bead81226"
REQUESTED = [27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57]


def receipt(path):
    data = Path(path).read_bytes()
    return {"path": str(Path(path).relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    if OUT.exists():
        raise FileExistsError("Preserve the first C1 batch index")
    out = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(), "passed": False,
           "requested_missing_ordinals": REQUESTED, "executed_ordinals": [], "reused_ordinals": [], "reviews": [],
           "scope": "Sequential frozen independent C1 saved-data reader only, after authoritative completion; no producer or neural execution.",
           "limits": ["Selected48 state transitions and ordered selected edges are reconstructed, not every intermediate global voltage or global accepted/unavailable edge disposition.",
                      "Passing numerical/archive checks is not physiological accuracy, long-term stability or promotion."]}
    preserved = {}
    try:
        plan = json.loads(PLAN.read_text())
        run = ROOT / plan["run_dir"]
        assert receipt(PLAN)["sha256"] == PLAN_SHA
        assert receipt(READER)["sha256"] == READER_SHA
        terminal = json.loads((run / "terminal.json").read_text())
        assert terminal["complete"] and terminal["status"] == "complete"
        out.update(plan=receipt(PLAN), reader=receipt(READER), script=receipt(Path(__file__)), parent_terminal=receipt(run / "terminal.json"))
        specs = [s for s in plan["order"] if s["arm"] == "C1"]
        assert [s["ordinal"] for s in specs] == list(range(15, 60, 3))
        protected = ROOT / "validation/inhibitory-recurrent-panel-c1-first-stimulus-summary.json"
        if protected.exists():
            preserved[str(protected)] = receipt(protected)
            out["preserved_optional_summary_failure"] = receipt(protected)
        for spec in specs:
            dest = ROOT / "validation" / ("inhibitory-recurrent-panel-" + spec["name"] + "-active-review.json")
            if dest.exists():
                preserved[str(dest)] = receipt(dest)
            else:
                assert spec["ordinal"] in REQUESTED, "Unexpected missing previously completed review"
        for spec in specs:
            directory = run / spec["name"]
            dest = ROOT / "validation" / ("inhibitory-recurrent-panel-" + spec["name"] + "-active-review.json")
            term = json.loads((directory / "terminal.json").read_text())
            assert term["complete"] and term["status"] == "complete"
            assert receipt(PLAN)["sha256"] == PLAN_SHA and receipt(READER)["sha256"] == READER_SHA
            if dest.exists():
                out["reused_ordinals"].append(spec["ordinal"])
            else:
                out["executed_ordinals"].append(spec["ordinal"])
                with tempfile.NamedTemporaryFile(prefix=f'c1-batch-review-{spec["ordinal"]:02d}-', suffix=".log", delete=False) as log:
                    process = subprocess.run([sys.executable, str(READER), "--ordinal", str(spec["ordinal"])], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                if process.returncode or not dest.exists():
                    out["failed_ordinal"] = spec["ordinal"]
                    out["failure_log"] = log.name
                    raise RuntimeError("Frozen reader failed; later reviews were not started")
            review = json.loads(dest.read_text())
            assert review["passed"] and not review["failures"] and review["error"] is None
            assert review["trial"] == spec and review["plan_sha256"] == PLAN_SHA
            assert review["source_sha256"][str(READER.relative_to(ROOT))] == READER_SHA
            assert review["terminal_sha256"] == receipt(directory / "terminal.json")["sha256"]
            assert review["result_sha256"] == receipt(directory / "result.json")["sha256"] == term["result"]["sha256"]
            assert all(c["checked"] == c["passed"] for c in review["categories"].values())
            out["reviews"].append({"spec": spec, "receipt": receipt(dest), "passed": True, "check_count": review["check_count"],
                                   "terminal_sha256": review["terminal_sha256"], "result_sha256": review["result_sha256"],
                                   "statistics": review["statistics"]})
        assert all(receipt(Path(path)) == original for path, original in preserved.items())
        out.update(passed=True, reviewed_C1_trials=len(out["reviews"]), component_checks=sum(r["check_count"] for r in out["reviews"]),
                   preexisting_receipts_unchanged=True, total_archived_spikes=sum(r["statistics"]["spikes"] for r in out["reviews"]))
    except Exception as error:
        out["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    out["finished_utc"] = datetime.now(timezone.utc).isoformat()
    with OUT.open("x") as f:
        json.dump(out, f, indent=2, allow_nan=False); f.write("\n")
    print(json.dumps({"passed": out["passed"], "executed_count": len(out["executed_ordinals"]), "index": receipt(OUT), "error": out.get("error")}))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
