#!/usr/bin/env python3
"""Correct only the source raster's nonzero PDF page frame; no re-extraction."""
import hashlib
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/ln-inhibitory-transfer/phase2"
PREFIX = ROOT / "validation/ln-inhibitory-transfer-phase2"
OUT = Path(str(PREFIX) + "-overlay-corrected.png")
RECEIPT = Path(str(PREFIX) + "-overlay-corrected-receipt.json")


def receipt(p):
    return {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


if OUT.exists() or RECEIPT.exists():
    raise FileExistsError("Preserve corrected overlay")
raw = json.loads((RAW / "source-geometry.json").read_text())
result = json.loads(Path(str(PREFIX) + "-results.json").read_text())
plan = json.loads(Path(str(PREFIX) + "-plan.json").read_text())
assert raw["page_size_pt"] == [585, 783]
pic = Image.open(RAW / "source-page.png")
assert pic.size == (2438, 3263)
# Verified with pypdf and pdfplumber after the first visual check. The primary
# PDF MediaBox/CropBox is [9, 9, 594, 792], rotation 0. pdfplumber y is height-y.
extent = (9, 594, 774, -9)
crops = {"D_mean": (150, 286, 425, 350), "F_mean": (342, 482, 421, 352), "E_mean": (342, 482, 336, 250)}
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, name in zip(axes, ("F_mean", "E_mean", "D_mean")):
    ax.imshow(pic, extent=extent)
    for obj in raw["objects"][name]:
        points, codes = [], []
        for op, *coords in obj["path"]:
            if op == "m": points.append(coords[0]); codes.append(MPath.MOVETO)
            elif op == "l": points.append(coords[0]); codes.append(MPath.LINETO)
            elif op == "c": points.extend(coords); codes.extend([MPath.CURVE4] * 3)
            elif op == "h": points.append([0, 0]); codes.append(MPath.CLOSEPOLY)
            else: raise ValueError("Unsupported native overlay operator " + op)
        ax.add_patch(PathPatch(MPath(points, codes), facecolor="#cf00aa", edgecolor="none", alpha=.45))
    c = result["calibration"][name]
    origin = sum(c["origin_x_pt"]) / 2
    scale = sum(c["x_pt_per_s"]) / 2
    for label, (a, b) in plan["windows_s"].items():
        ax.axvspan(origin + a * scale, origin + b * scale, alpha=.09, color="#2487c5")
        ax.text(origin + (a + b) / 2 * scale, crops[name][3] + 1,
                label, ha="center", va="top", fontsize=7, rotation=90)
    ax.set_xlim(*crops[name][:2]); ax.set_ylim(*crops[name][2:]); ax.set_axis_off()
    ax.set_title(name + " selected ink / fixed windows", fontsize=10)
fig.suptitle("Figure 6: corrected nonzero page frame; native mean artwork in magenta\nOriginal extraction unchanged; shading uses nominal time anchors", fontsize=11)
fig.tight_layout(); fig.savefig(OUT, dpi=200); plt.close(fig)
evidence = {"reason": "First overlay assumed raster extent (0,585,783,0); actual PDF page has a nonzero origin. Correction changes raster registration only, without new geometry or numerical extraction.",
    "source_pdf_media_and_crop_box": [9, 9, 594, 792], "rotation": 0,
    "pdfplumber_bbox": [9, -9, 594, 774], "imshow_extent": extent,
    "source_box_verified_with": "pypdf and pdfplumber read-only inspection",
    "inputs": [receipt(p) for p in (RAW / "source-geometry.json", RAW / "source-page.png",
        Path(str(PREFIX) + "-plan.json"), Path(str(PREFIX) + "-results.json"),
        Path(str(PREFIX) + "-overlay.png"), Path(__file__).resolve())],
    "output": receipt(OUT), "numerical_extraction_repeated": False}
with RECEIPT.open("x") as f:
    json.dump(evidence, f, indent=2, allow_nan=False); f.write("\n")
print(json.dumps(receipt(OUT), indent=2))
