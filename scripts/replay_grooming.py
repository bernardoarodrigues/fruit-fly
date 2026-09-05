"""Run the measured female grooming actuator diagnostic and save evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np

from fruitfly.grooming import run_replay, audit_foreleg_forward_kinematics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/grooming/unilateral_left.npz"))
    parser.add_argument("--output", type=Path, default=Path("validation/grooming-replay-diagnostic.json"))
    parser.add_argument("--no-video", action="store_true")
    args = parser.parse_args()
    frames = []
    renderer = None

    def render_frame(model, data, time_s):
        nonlocal renderer
        if renderer is None:
            renderer = mujoco.Renderer(model, height=480, width=640)
        thorax = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "grooming/c_thorax")
        camera = mujoco.MjvCamera()
        camera.lookat[:] = data.xpos[thorax] + np.asarray([.25, 0, .05])
        camera.distance, camera.azimuth, camera.elevation = 3.5, 135, -20
        renderer.update_scene(data, camera=camera)
        frames.append(renderer.render().copy())

    try:
        result = run_replay(args.source, frame_callback=None if args.no_video else render_frame)
    finally:
        if renderer is not None:
            renderer.close()
    result["forward_kinematic_audit"] = audit_foreleg_forward_kinematics(args.source)
    trace = result["traces"]
    time = np.asarray(trace["time_s"])
    error = np.rad2deg(np.asarray(trace["actual_rad"])-np.asarray(trace["target_rad"]))
    fig, axes = plt.subplots(3, 1, figsize=(8, 7), constrained_layout=True, sharex=True)
    axes[0].plot(time, error)
    axes[0].set_ylabel("Angle error (degrees)")
    axes[0].set_title("Measured female grooming: position-actuated diagnostic")
    axes[1].plot(time, trace["ground_normal_force"])
    axes[1].set_ylabel("Ground normal force\n(native g·mm/s²)")
    axes[1].legend(["LF", "LM", "LH", "RF", "RM", "RH"], ncol=6, fontsize=8)
    axes[2].plot(time, trace["thorax_height_mm"])
    axes[2].set(ylabel="Thorax height (mm)", xlabel="Measured snippet time (s)")
    args.output.parent.mkdir(exist_ok=True, parents=True)
    plot_path = args.output.with_suffix(".png")
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)
    result["plot"] = str(plot_path)
    if frames:
        video_path = args.output.with_suffix(".mp4")
        imageio.mimsave(video_path, frames, fps=25, codec="libx264", quality=7)
        still = args.output.with_name(args.output.stem + "-frame.png")
        imageio.imwrite(still, frames[len(frames)//2])
        result["video"] = {"path": str(video_path), "fps": 25, "sample_rate_hz": 100,
                           "playback": "4x slower; one traversal; antennae rigid", "midpoint_frame": str(still)}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "duration_replayed_s", "position_tracking_rms_deg",
        "position_tracking_max_abs_deg", "thorax_height_range_mm", "finite")}, indent=2))
    print(args.output)


if __name__ == "__main__":
    main()
