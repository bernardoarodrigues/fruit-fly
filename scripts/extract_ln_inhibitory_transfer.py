#!/usr/bin/env python3
"""One frozen, vector-ink enclosure extraction; no fitted neural centerlines."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "validation/ln-inhibitory-transfer-phase2"
RAW = ROOT / "data/raw/ln-inhibitory-transfer/phase2"
SOURCE = ROOT / "data/raw/ln-inhibitory-transfer/nagelwilson2016.pdf"
WINDOWS = {"baseline": [-.15, -.05], "early": [.05, .15], "late": [.25, .35]}
SELECT = {"F_mean": [235], "D_mean": [234], "E_mean": list(range(143, 150)),
          "F_SEM_artwork": [231], "D_SEM_artwork": [233], "D_control_artwork": [232]}


def now():
    return datetime.now(timezone.utc).isoformat()


def receipt(path):
    p = Path(path)
    return {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def write(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def prepare():
    import pdfplumber
    sources = [SOURCE, ROOT / "validation/ln-inhibitory-transfer-extraction-plan.json",
               ROOT / "validation/ln-inhibitory-transfer-layout.json",
               ROOT / "docs/ln-inhibitory-transfer-phase2-review.md", Path(__file__).resolve()]
    plan = {"schema": 1, "frozen_utc": now(), "inputs": [receipt(p) for p in sources],
        "runtime": {"pdfplumber": pdfplumber.__version__, "numpy": np.__version__},
        "amendment": "F replaces D as primary onset geometry of the same n=9 current dataset; D is an independently calibrated graphical check. E is one n=5 mean represented by a union of pieces. Old plan retained unchanged; figure9 means PDF page 9, Figure 6.",
        "selection": SELECT, "page_index": 8, "windows_s": WINDOWS,
        "bin_width_s": .001, "curve_enclosure_tolerance_pt": .001, "maximum_subdivision_depth": 24,
        "full_display_bin_ranges_s": {"D_mean": [-1., 3.5], "E_mean": [-.2, .4], "F_mean": [-.2, .4]},
        "calibration": {"D_bars": [135, 136], "F_bars": [141, 140],
            "D_light_on_x_pt": [183.431, 183.86], "EF_light_on_x_pt": [390.498, 391.143],
            "bar_endpoint_rule": "Nominal rectangle-axis endpoints, each expanded by half the perpendicular ink thickness. Time/current scale ranges use shortest and longest allowed lengths. The light origin ranges are the retained command ink bounds.",
            "E_rate_anchor_rectangles_and_values": [[137, 20], [139, 60]],
            "E_intermediate_check": [138, 40],
            "E_endpoint_axis_check": "Curve142 overall ink extent contains the extrapolated 0/80 anchors within the tick half-thickness; not used to fit anchors",
            "shared_scale_rule": "Integrate graphical y-coordinate enclosures first. Differences cancel the same vertical origin before dividing by a shared positive scale interval; no double baseline subtraction."},
        "geometry_rule": "Retain transformed native PDF paths and full decoded page content. Flatten cubic curves only through recursive de Casteljau subdivision whose control-point distance to the chord segment is at most 0.001 pt; expand queried strips and y extents by this tolerance. Unsupported operators or depth overflow yield unresolved/failure. Union attributable boundary extents over each entire bin; no midpoint, reconstructed centerline, smoothing, fit or neural gap interpolation.",
        "coverage_rule": "All admitted time-anchor/scale positions in each required window must be supported by the selected filled contours. Unsupported bins make that window unavailable. Full-display edge failures are retained, not extrapolated.",
        "uncertainty": "Ink, anchor and finite-bin enclosures are graphical sensitivity ranges, not biological confidence intervals or bounds on original recording error. E SEM and D control mean remain unavailable unless independently identifiable; this run does not derive them. Gray/control geometry retained only.",
        "decision": "Late-minus-early F current >0 and E rate <0 are graphically resolved only if the entire interval has the required sign. Zero overlap is unresolved, opposite sign is a retained negative result. D/F disagreements are retained; never pool the same dataset twice.",
        "bounded_attempt": "One vector attribution/extraction attempt. If vector attribution or coverage fails, retain unresolved output; no segmentation tuning or repeated fallback search. Original PDF render and overlays are verification evidence, not a second extraction.",
        "prohibitions": ["no model fit", "no pA/nS conversion", "no causal latency or time constant", "no current/rate ratio across different cohorts", "no model simulation", "no fabricated SEM/control mean"],
        "source_render_dpi": 300}
    write(str(PREFIX) + "-plan.json", plan)
    print(json.dumps(receipt(str(PREFIX) + "-plan.json"), indent=2))


def flatten(path, eps, max_depth):
    segments, supports = [], []
    cur = start = None
    contour = []

    def line(a, b):
        segments.append([a, b]); contour.extend([a[0], b[0]])

    def cubic(points, depth=0):
        p = np.asarray(points, dtype=float)
        chord = p[-1] - p[0]
        den = float(chord @ chord)
        t = np.zeros(2) if den == 0 else np.clip((p[1:3] - p[0]) @ chord / den, 0, 1)
        distance = np.linalg.norm(p[1:3] - (p[0] + t[:, None] * chord), axis=1)
        if distance.max() <= eps:
            line(p[0].tolist(), p[-1].tolist()); return
        if depth >= max_depth:
            raise ValueError("Curve subdivision depth exceeded")
        a = (p[:-1] + p[1:]) / 2
        b = (a[:-1] + a[1:]) / 2
        mid = (b[0] + b[1]) / 2
        cubic([p[0], a[0], b[0], mid], depth + 1)
        cubic([mid, b[1], a[2], p[3]], depth + 1)

    def close():
        nonlocal cur, start, contour
        if start is not None:
            if cur != start:
                line(cur, start)
            if contour:
                supports.append([min(contour), max(contour)])
        cur = start = None; contour = []

    for operation in path:
        op, *points = operation
        points = [list(p) for p in points]
        if op == "m":
            close(); cur = start = points[0]
        elif op == "l":
            line(cur, points[0]); cur = points[0]
        elif op in ("c", "v", "y"):
            if op == "v":
                points = [cur, *points]
            if op == "y":
                points = [*points, points[-1]]
            cubic([cur, *points]); cur = points[-1]
        elif op == "h":
            close()
        else:
            raise ValueError("Unsupported path operator: " + op)
    close()
    return np.asarray(segments, dtype=float), supports


def strip_bounds(segments, supports, x0, x1, eps):
    merged = []
    for a, b in sorted(supports):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    covered = any(a <= x0 and b >= x1 for a, b in merged)
    if not covered:
        return None
    q = segments[(segments[:, :, 0].min(axis=1) <= x1 + eps) &
                 (segments[:, :, 0].max(axis=1) >= x0 - eps)]
    if not len(q):
        return None
    dx = q[:, 1, 0] - q[:, 0, 0]
    lo = np.zeros(len(q)); hi = np.ones(len(q))
    nz = dx != 0
    t0 = (x0 - eps - q[nz, 0, 0]) / dx[nz]
    t1 = (x1 + eps - q[nz, 0, 0]) / dx[nz]
    lo[nz] = np.clip(np.minimum(t0, t1), 0, 1)
    hi[nz] = np.clip(np.maximum(t0, t1), 0, 1)
    dy = q[:, 1, 1] - q[:, 0, 1]
    yy = np.r_[q[:, 0, 1] + lo * dy, q[:, 0, 1] + hi * dy]
    return [float(yy.min() - eps), float(yy.max() + eps)]


def interval_divide(interval, positive_scale):
    values = [v / s for v in interval for s in positive_scale]
    return [min(values), max(values)]


def extract():
    import pdfplumber
    from pypdf import PdfReader
    plan = json.loads(Path(str(PREFIX) + "-plan.json").read_text())
    out = Path(str(PREFIX) + "-results.json")
    if out.exists() or RAW.exists():
        raise FileExistsError("Preserve phase-2 extraction evidence")
    RAW.mkdir()
    result = {"schema": 1, "started_utc": now(), "plan": receipt(str(PREFIX) + "-plan.json"),
              "checks": [], "signals": {}, "artifacts": [], "model_fit_or_simulation": False}

    def check(name, value):
        result["checks"].append({"name": name, "passed": bool(value)})
        if not value:
            raise ValueError(name)

    try:
        for item in plan["inputs"]:
            check("input receipt: " + item["path"], receipt(ROOT / item["path"]) == item)
        check("parser version", pdfplumber.__version__ == plan["runtime"]["pdfplumber"])
        with pdfplumber.open(SOURCE) as pdf:
            page = pdf.pages[8]
            raw = {"page_size_pt": [page.width, page.height], "objects": {}, "scale_rectangles": {},
                   "coordinates": "Transformed PDF points, x right and y down; full source PDF/page content preserve original transforms, clipping and paint order"}
            for name, indices in SELECT.items():
                raw["objects"][name] = [{"curve_index": i, **{k: page.curves[i].get(k) for k in
                    ("path", "pts", "fill", "stroke", "evenodd", "linewidth", "non_stroking_color", "x0", "x1", "top", "bottom")}} for i in indices]
            for i in (135, 136, 137, 138, 139, 140, 141):
                raw["scale_rectangles"][str(i)] = {k: page.rects[i][k] for k in ("x0", "x1", "top", "bottom")}
            raw["rate_axis_curve"] = page.curves[142]["path"]
            raw["light_command_paths"] = {str(i): page.curves[i]["path"] for i in (126, 134, 152)}
            raw["overlapping_control_images"] = [{k: im.get(k) for k in ("x0", "x1", "top", "bottom", "srcsize", "name")} for im in page.images]
        write(RAW / "source-geometry.json", raw)
        (RAW / "decoded-page-content.bin").write_bytes(PdfReader(SOURCE).pages[8].get_contents().get_data())
        rect = raw["scale_rectangles"]
        cal = {}
        for panel, v, h, duration, origin in (("F_mean", "141", "140", .2, plan["calibration"]["EF_light_on_x_pt"]),
                                             ("D_mean", "135", "136", 1., plan["calibration"]["D_light_on_x_pt"])):
            vr, hr = rect[v], rect[h]
            width = hr["x1"] - hr["x0"]
            xt = vr["x1"] - vr["x0"]
            height = vr["bottom"] - vr["top"]
            yt = hr["bottom"] - hr["top"]
            cal[panel] = {"origin_x_pt": origin, "x_pt_per_s": [(width - xt) / duration, (width + xt) / duration],
                          "y_pt_per_unit": [(height - yt) / 4, (height + yt) / 4], "units": "pA"}
        y20 = [rect["137"]["top"], rect["137"]["bottom"]]
        y60 = [rect["139"]["top"], rect["139"]["bottom"]]
        rate_scale = [(y20[0] - y60[1]) / 40, (y20[1] - y60[0]) / 40]
        cal["E_mean"] = {"origin_x_pt": cal["F_mean"]["origin_x_pt"], "x_pt_per_s": cal["F_mean"]["x_pt_per_s"],
                         "y_pt_per_unit": rate_scale, "y20_ink_pt": y20, "y60_ink_pt": y60, "units": "spikes/s"}
        predicted40 = [(a + b) / 2 for a in y20 for b in y60]
        check("rate intermediate 40 tick overlaps anchor interval", max(predicted40) >= rect["138"]["top"] and min(predicted40) <= rect["138"]["bottom"])
        axis_y = [p[1] for op in raw["rate_axis_curve"] for p in op[1:]]
        predicted0 = [a + (a - b) / 2 for a in y20 for b in y60]
        predicted80 = [b - (a - b) / 2 for a in y20 for b in y60]
        half_tick = max(y20[1] - y20[0], y60[1] - y60[0]) / 2
        check("rate endpoint 0/80 ink checks", min(predicted0) - half_tick <= max(axis_y) <= max(predicted0) + half_tick
              and min(predicted80) - half_tick <= min(axis_y) <= max(predicted80) + half_tick)
        write(RAW / "calibration.json", cal)
        bins_all = {}
        eps = plan["curve_enclosure_tolerance_pt"]
        for name in ("F_mean", "E_mean", "D_mean"):
            obj = raw["objects"][name]
            check(name + " filled nonstroked artwork", all(x["fill"] and not x["stroke"] for x in obj))
            parsed = [flatten(x["path"], eps, plan["maximum_subdivision_depth"]) for x in obj]
            segments = np.concatenate([p[0] for p in parsed]); supports = sum([p[1] for p in parsed], [])
            c = cal[name]; lo, hi = plan["full_display_bin_ranges_s"][name]
            intervals = []
            for k in range(round((hi - lo) * 1000)):
                a, b = (round(lo * 1000) + k) / 1000, (round(lo * 1000) + k + 1) / 1000
                x = [origin + t * scale for origin in c["origin_x_pt"] for t in (a, b) for scale in c["x_pt_per_s"]]
                intervals.append({"time_s": [a, b], "y_ink_enclosure_pt": strip_bounds(segments, supports, min(x), max(x), eps)})
            bins_all[name] = intervals
            windows = {}
            for label, (a, b) in WINDOWS.items():
                take = [x for x in intervals if x["time_s"][0] >= a and x["time_s"][1] <= b]
                coverage = sum(x["time_s"][1] - x["time_s"][0] for x in take if x["y_ink_enclosure_pt"] is not None)
                complete = len(take) == 100 and abs(coverage - (b - a)) < 1e-12
                windows[label] = {"window_s": [a, b], "bins": len(take), "coverage_s": coverage, "complete": complete,
                    "mean_y_ink_enclosure_pt": (np.mean([x["y_ink_enclosure_pt"] for x in take], axis=0).tolist() if complete else None)}
            differences = {}
            for label, a, b in (("early_minus_baseline", "baseline", "early"), ("late_minus_baseline", "baseline", "late"), ("late_minus_early", "early", "late")):
                ya, yb = windows[a]["mean_y_ink_enclosure_pt"], windows[b]["mean_y_ink_enclosure_pt"]
                interval = None if ya is None or yb is None else interval_divide([ya[0] - yb[1], ya[1] - yb[0]], c["y_pt_per_unit"])
                differences[label] = {"units": c["units"], "graphical_interval": interval,
                    "direction": "unavailable" if interval is None else ("positive" if interval[0] > 0 else "negative" if interval[1] < 0 else "unresolved")}
            if name == "E_mean":
                for row in windows.values():
                    yy = row["mean_y_ink_enclosure_pt"]
                    values = [] if yy is None else [20 + (a - y) * 40 / (a - b) for a in y20 for b in y60 for y in yy]
                    row["plotted_rate_graphical_interval_spikes_per_s"] = [min(values), max(values)] if values else None
            result["signals"][name] = {"units": c["units"], "source_curve_indices": SELECT[name], "windows": windows,
                "differences": differences, "full_display_bins": len(intervals),
                "unsupported_full_display_bins": sum(x["y_ink_enclosure_pt"] is None for x in intervals),
                "flattened_boundary_segments": len(segments), "attribution_visual_review": "pending overlay inspection"}
        write(RAW / "ink-bins.json", bins_all)
        result["calibration"] = cal
        f = result["signals"]["F_mean"]["differences"]["late_minus_early"]
        e = result["signals"]["E_mean"]["differences"]["late_minus_early"]
        result["graphical_direction_test"] = {"current": f["direction"], "rate": e["direction"],
            "both_expected_directions_resolved": f["direction"] == "positive" and e["direction"] == "negative",
            "not_statistical_significance": True}
        result["D_F_same_cohort_consistency"] = {}
        for key in result["signals"]["F_mean"]["differences"]:
            fi = result["signals"]["F_mean"]["differences"][key]["graphical_interval"]
            di = result["signals"]["D_mean"]["differences"][key]["graphical_interval"]
            result["D_F_same_cohort_consistency"][key] = None if fi is None or di is None else max(fi[0], di[0]) <= min(fi[1], di[1])
        result["unavailable"] = {"E_SEM": "Not separately identifiable; no derived SEM", "D_control_mean": "Overlapping raster/vector artwork, retained without selecting a mean", "absolute_holding_current": None, "conductance_nS": None}
        subprocess.run(["/opt/homebrew/bin/pdftoppm", "-f", "9", "-l", "9", "-singlefile", "-r", "300", "-png", str(SOURCE), str(RAW / "source-page")], check=True, capture_output=True)
        result["completed_extraction"] = True
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    result["artifacts"] = [receipt(p) for p in sorted(RAW.iterdir()) if p.is_file()]
    result["completed_utc"] = now()
    write(out, result)
    print(json.dumps({"output": str(out), "completed": result.get("completed_extraction", False), "directions": result.get("graphical_direction_test"), "failure": result.get("failure")}, indent=2))


def plot():
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    from PIL import Image
    output = Path(str(PREFIX) + "-overlay.png")
    if output.exists():
        raise FileExistsError("Preserve overlay")
    raw = json.loads((RAW / "source-geometry.json").read_text())
    result = json.loads(Path(str(PREFIX) + "-results.json").read_text())
    pic = Image.open(RAW / "source-page.png")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    crops = {"D_mean": (150, 286, 425, 350), "F_mean": (342, 482, 421, 352), "E_mean": (342, 482, 336, 250)}
    for ax, name in zip(axes, ("F_mean", "E_mean", "D_mean")):
        ax.imshow(pic, extent=(0, 585, 783, 0))
        for obj in raw["objects"][name]:
            points, codes = [], []
            for operation in obj["path"]:
                op, *coords = operation
                if op == "m": points.append(coords[0]); codes.append(MPath.MOVETO)
                elif op == "l": points.append(coords[0]); codes.append(MPath.LINETO)
                elif op == "c": points.extend(coords); codes.extend([MPath.CURVE4] * 3)
                elif op == "h": points.append([0, 0]); codes.append(MPath.CLOSEPOLY)
                else: raise ValueError("Unsupported overlay path operator: " + op)
            ax.add_patch(PathPatch(MPath(points, codes), facecolor="#cf00aa", edgecolor="none", alpha=.45))
        c = result["calibration"][name]
        origin = sum(c["origin_x_pt"]) / 2; scale = sum(c["x_pt_per_s"]) / 2
        for label, (a, b) in WINDOWS.items():
            ax.axvspan(origin + a * scale, origin + b * scale, alpha=.09, color="#2487c5")
            ax.text(origin + (a + b) / 2 * scale, crops[name][3] + 1, label, ha="center", va="top", fontsize=7, rotation=90)
        ax.set_xlim(*crops[name][:2]); ax.set_ylim(*crops[name][2:]); ax.set_title(name + " selected ink / fixed windows", fontsize=10); ax.set_axis_off()
    fig.suptitle("Figure 6: source rendering with selected native mean artwork (magenta)\nWindow shading is nominal; reported intervals include calibration uncertainty", fontsize=11)
    fig.tight_layout(); fig.savefig(output, dpi=200); plt.close(fig)
    write(str(PREFIX) + "-overlay-receipt.json", {"source": receipt(RAW / "source-page.png"), "geometry": receipt(RAW / "source-geometry.json"),
          "results": receipt(str(PREFIX) + "-results.json"), "script": receipt(Path(__file__).resolve()), "overlay": receipt(output)})
    print(json.dumps(receipt(output), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "extract", "plot"))
    args = parser.parse_args()
    {"plan": prepare, "extract": extract, "plot": plot}[args.mode]()
