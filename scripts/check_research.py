"""Check local research artifacts; this does not validate biological claims."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    papers = json.loads((ROOT / "research/provided-papers.json").read_text())
    for paper in papers:
        path = ROOT / paper["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != paper["sha256"]:
            errors.append(f"Input paper changed: {path.name}")
    docs = [ROOT / "README.md", *sorted((ROOT / "research").glob("*.md")), ROOT / "prototype/README.md"]
    internal_links = 0
    for path in docs:
        text = path.read_text()
        if "turn0" in text or "cite" in text:
            errors.append(f"Unresolved web citation marker: {path.name}")
        for link in re.findall(r"\]\(([^\n]+?)\)", text):
            if link.startswith(("https://", "http://", "mailto:", "#")):
                continue
            target = link.split("#")[0]
            if not target:
                continue
            internal_links += 1
            if not (path.parent / target).exists():
                errors.append(f"Broken local link in {path.relative_to(ROOT)}: {link}")
    source_groups = 0
    for path in sorted((ROOT / "research").glob("sources-*.json")):
        data = json.loads(path.read_text())
        ids = [row["id"] for row in data["sources"]]
        source_groups += len(ids)
        if len(ids) != len(set(ids)):
            errors.append(f"Duplicate source ID within {path.name}")
    for path in (ROOT / "prototype").glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    for name in ("metrics.json", "stimuli_metrics.json"):
        report = json.loads((ROOT / "prototype/output" / name).read_text())
        if not report.get("finite") or report["simulated_s"] <= 0:
            errors.append(f"Invalid smoke report {name}")
    report = {
        "purpose": "local artifact integrity only; no scientific validation implied",
        "input_papers_unchanged": len(papers), "markdown_files_checked": len(docs),
        "internal_links_checked": internal_links, "source_groups": source_groups,
        "python_syntax": "passed", "errors": errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)
    (ROOT / "research/verification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
