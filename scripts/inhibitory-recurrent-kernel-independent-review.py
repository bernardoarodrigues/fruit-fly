#!/usr/bin/env python3
"""Record independent source review and verify pinned receipts; execute no model."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/inhibitory-recurrent-kernel-independent-review.json"
PINNED = {
    "scripts/inhibitory_recurrent_kernel.py": "52892eabb7124dfe6140f7c0cbc4d9047301978c6706053e3230d72280ec2b0f",
    "scripts/check_inhibitory_recurrent_kernel.py": "be0880ee377c28cd5819d9e78840cd04df878bdb1db8d454ea96bc90fa863963",
    "scripts/inhibitory_factorial_solver.py": "ad92c4aa0292d9809f5fe5de1cf1ee938cdd6a8a6b175b94facc1e73f387f711",
    "fruitfly/neural.py": "940a7b8721ccdf954203d4d08d25cfb70b4e31463262b5dc7d1e901d5a29e0b1",
    "validation/inhibitory-recurrent-kernel-checks.json": "86134f8c541f7a71cb19e15b6fdf8223b2571a2ef6bc6d615b8c73186edf1370",
}


def main():
    if OUT.exists():
        raise FileExistsError("Preserve earlier independent review")
    checks, inputs = [], {}
    for name in [*PINNED, "docs/inhibitory-recurrent-kernel-independent-review.md", str(Path(__file__).relative_to(ROOT))]:
        p = ROOT / name
        inputs[name] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
        if name in PINNED:
            checks.append({"name": "pinned:" + name, "passed": inputs[name]["sha256"] == PINNED[name]})
        if p.suffix == ".py":
            ast.parse(p.read_text())
            checks.append({"name": "syntax_only:" + name, "passed": True})
    reported = json.loads((ROOT / "validation/inhibitory-recurrent-kernel-checks.json").read_text())
    checks.append({"name": "author_receipt_all143_reported_checks", "passed": reported["passed"] and reported["check_count"] == len(reported["checks"]) == 143 and all(reported["checks"].values())})
    checks.append({"name": "author_receipt_pins_reviewed_sources", "passed": all(inputs[p]["sha256"] == h for p, h in reported["source_sha256"].items())})
    result = {
        "schema": 1, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Independent manual source review plus retained receipt/hash/syntax verification. No neural kernel, original engine, full graph, conditional replay or synthetic checker executed by this review.",
        "source_review_passed": True, "reported_synthetic_checks": 143, "independent_synthetic_execution": False,
        "synthetic_raw_arrays_independently_reconstructed": False, "inputs": inputs,
        "checks": checks, "check_count": len(checks), "passed": all(c["passed"] for c in checks),
        "findings": [
            "C0 source operation order and source/delay/threshold/direct/reset semantics match the fixed original engine case; no direct current is supported.",
            "Own-arm refractory handling differs only as declared for recurrent synaptic state; direct voltage events retain native same-tick firing rejection in all arms.",
            "Global signed edge counters partition unblocked visits from accepted/unavailable and count blocked edges separately; event logs are selected-target only.",
            "Completed-prefix slicing, exclusive clock and explicit partial mutable state agree; recognized failure prohibits continuation. Uncaught allocation/interruption remains runner responsibility.",
            "H uses the unchanged scalar solver and normalized negative increments; this review does not independently validate full-graph H trajectories or local accuracy on newly generated states."
        ],
        "resolved_before_freeze": [
            "Ambiguous delivery mask now separated into direct and synaptic eligibility; compatibility alias documented and synthetic assertions added.",
            "Failure clock now distinguishes completed_prefix_end_tick from last_completed_transition_tick."
        ],
        "limits": [
            "Author control receipt retains booleans and hashes, not raw synthetic trajectories; no independent numerical reconstruction of those results is claimed.",
            "Author numerical parity uses np.array_equal; stronger raw-byte parity remains appropriate for full-graph C0 reference gates.",
            "Only injected H interval failure and invalid external-input rejection are exercised by the reported checker; all other failure paths have source-review coverage only here.",
            "Prospective reset counters on a failed partial tick require phase-based validity; placeholders are not observations.",
            "No full-graph performance, physiology, seed robustness, complete recurrent comparison or default promotion is established."
        ],
        "documentation": "docs/inhibitory-recurrent-kernel-independent-review.md",
    }
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": result["passed"], "receipt_checks": len(checks), "author_reported_synthetic_checks": 143, "model_executed_by_review": False}), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
