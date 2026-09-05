#!/usr/bin/env python3
"""Reconstruct recorded Suver wind responses from valid, individually saved repeats."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_dir = Path("data/raw/wind/neural")
    receipt = json.loads((source_dir/"extraction-receipt.json").read_text())
    names = {"APN2": "24C06_free.mat", "APN3": "70G01_free.mat", "WPN": "70B12_free.mat"}
    rows = np.arange(1, 10, 2)  # Author MATLAB rows2,4,6,8,10; others are not directions.
    directions = [-90, -45, 0, 45, 90]  # Contralateral to ipsilateral after author alignment.
    colors = ["#8b2d28", "#da7351", "#626d7a", "#509a9d", "#304786"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.4), constrained_layout=True)
    fig.suptitle("Recorded female wind responses — empirical calibration targets\nSuver et al., Neuron 2019 / Dryad 10.5061/dryad.k06kh8f", fontsize=14)
    sr_fig, sr_axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    sr_fig.suptitle("Recorded spike-rate changes: APN3 and WPN\nAPN2 is nonspiking and is excluded from this comparison", fontsize=14)
    results, arrays = {}, {}
    for column, (cell, filename) in enumerate(names.items()):
        path = source_dir/filename
        digest = file_hash(path)
        assert digest == receipt["selected_members"][filename]["sha256"]
        t = loadmat(path, simplify_cells=True)["traces"]
        count = int(t["numFlies"])
        vm_per_record = np.stack(t["indvVmTrace"])[:, rows, :]
        vm_mean = vm_per_record.mean(axis=0)
        vm_sd = vm_per_record.std(axis=0, ddof=1)
        np.testing.assert_allclose(vm_mean, t["avgVmTrace"][rows], atol=1e-12)
        np.testing.assert_allclose(vm_sd, t["errorVm"][rows], atol=1e-12)
        assert len(vm_per_record) == count
        sample_hz = t["samplerate"] / t["DSAMP"]
        time = np.arange(vm_mean.shape[1]) / sample_hz - t["preStim"]
        valid_repeats = []
        for repeated, trial_ids in zip(t["indvTonicWindAvg"], t["trialNums"]):
            assert repeated.shape == trial_ids.shape
            valid = np.where(trial_ids > 0, repeated, np.nan)
            assert np.all(np.any(trial_ids > 0, axis=1))
            valid_repeats.append(valid)
        per_record = np.stack([np.nanmean(values, axis=1) for values in valid_repeats])
        saved_per_record = np.stack(t["indvTonicWindAvg_meanCrossFly"])
        np.testing.assert_allclose(per_record, saved_per_record, atol=1e-10)
        np.testing.assert_allclose(per_record.mean(axis=0), t["avgWR"], atol=1e-10)
        # Final one second of the 4s stimulus. Inclusive MATLAB endpoints and
        # prior author downsampling account for sub-microvolt reconstruction differences.
        final = (time >= t["stimOn"]-1) & (time < t["stimOn"])
        final_window_max_error = float(np.max(np.abs(vm_mean[:, final].mean(axis=1)-t["avgWR"])))
        assert final_window_max_error < .002
        trial_counts = [int(np.count_nonzero(ids)) for ids in t["trialNums"]]
        per_direction = np.stack([(ids > 0).sum(axis=1) for ids in t["trialNums"]])
        t50 = []
        for curve, steady in zip(vm_mean, t["avgWR"]):
            crossed = np.flatnonzero((time >= 0) & (time < t["stimOn"]) & (curve * np.sign(steady) >= .5 * abs(steady)))
            t50.append(float(time[crossed[0]]*1000) if len(crossed) else None)
        records = [{"recording": str(notes[0]), "recorded_side": str(notes[3]),
                    "valid_trial_count": trial_counts[i], "trials_per_direction": per_direction[i].tolist(),
                    "valid_trial_ids_per_direction": [ids[ids > 0].astype(int).tolist() for ids in t["trialNums"][i]],
                    "steady_delta_vm_mv": per_record[i].tolist(),
                    "valid_repeat_delta_vm_mv": [values[np.isfinite(values)].tolist() for values in valid_repeats[i]]}
                   for i, notes in enumerate(t["exptNotes"])]
        result = {"source_file": filename, "sha256": digest, "driver": filename.split("_")[0],
                  "recordings": count, "total_valid_trials": sum(trial_counts),
                  "sample_rate_raw_hz": int(t["samplerate"]), "downsample_factor": int(t["DSAMP"]),
                  "stored_trace_sample_rate_hz": sample_hz, "trace_samples": vm_mean.shape[1],
                  "stimulus_on_seconds": float(t["preStim"]), "stimulus_duration_seconds": float(t["stimOn"]),
                  "stored_postStim_seconds": float(t["postStim"]),
                  "actual_poststim_trace_seconds": float(vm_mean.shape[1]/sample_hz-t["preStim"]-t["stimOn"]),
                  "steady_delta_vm_mean_mv": t["avgWR"].tolist(),
                  "steady_delta_vm_sd_mv": per_record.std(axis=0, ddof=1).tolist(),
                  "stored_baseline_avg_vm_uncorrected_mv": float(t["avgVm"]),
                  "half_final_response_first_crossing_after_command_ms": t50,
                  "reconstruction_max_error_mv": float(np.max(np.abs(per_record-saved_per_record))),
                  "final_window_from_downsampled_trace_max_error_mv": final_window_max_error,
                  "author_errorVm_verified_as_recording_sd": True,
                  "individual_records": records}
        arrays[f"{cell}_time_s"] = time
        arrays[f"{cell}_delta_vm_mv"] = vm_per_record
        arrays[f"{cell}_steady_delta_vm_mv"] = per_record
        for row in range(2):
            axes[row, column].set_title(f"{cell}: {count} recordings")
        for direction, color, curve in zip(directions, colors, vm_mean):
            axes[0, column].plot(time[::5], curve[::5], color=color, label=f"{direction:+d}°")
        axes[0, column].axvspan(0, 4, color="#bbbbbb", alpha=.13)
        axes[0, column].axhline(0, color="#dddddd", linewidth=.7)
        axes[0, column].set(xlim=(-.4, 6), xlabel="Time from wind command (s)", ylabel="Mean ΔVm (mV)")
        for individual in per_record:
            axes[1, column].plot(directions, individual, color="#adb5bd", alpha=.5, linewidth=.8)
        axes[1, column].errorbar(directions, per_record.mean(axis=0), per_record.std(axis=0, ddof=1),
                               color="#263746", marker="o", capsize=3, linewidth=2)
        axes[1, column].axhline(0, color="#dddddd", linewidth=.7)
        axes[1, column].set(xlabel="Wind direction, contra → ipsi (°)", ylabel="Final 1 s ΔVm: mean ± SD (mV)", xticks=directions)
        if cell != "APN2":
            sr_per_record = np.stack(t["indvSRTrace"])[:, rows, :] / float(t["SCALE_SR"])
            sr_repeats = [np.where(ids > 0, values, np.nan) for ids, values in zip(t["trialNums"], t["indvTonicWindAvg_SR"])]
            sr_steady = np.stack([np.nanmean(values, axis=1) for values in sr_repeats])
            np.testing.assert_allclose(sr_steady, np.stack(t["indvTonicWindAvg_meanCrossFly_SR"]), atol=1e-10)
            np.testing.assert_allclose(sr_steady.mean(axis=0), t["avgWR_SR"], atol=1e-10)
            np.testing.assert_allclose(sr_per_record.mean(axis=0), t["avgSRTrace"][rows]/float(t["SCALE_SR"]), atol=1e-10)
            assert np.max(np.abs(sr_per_record.mean(axis=0)[:, final].mean(axis=1)-t["avgWR_SR"])) < .02
            result["steady_delta_spike_rate_hz"] = t["avgWR_SR"].tolist()
            result["stored_baseline_avg_sr_hz"] = float(t["avgSR"])
            result["spike_trace_plot_scale_removed"] = float(t["SCALE_SR"])
            result["steady_delta_spike_rate_sd_hz"] = sr_steady.std(axis=0, ddof=1).tolist()
            for i, record in enumerate(records):
                record["steady_delta_spike_rate_hz"] = sr_steady[i].tolist()
                record["valid_repeat_delta_spike_rate_hz"] = [
                    values[np.isfinite(values)].tolist() for values in sr_repeats[i]
                ]
            arrays[f"{cell}_delta_spike_rate_hz"] = sr_per_record
            arrays[f"{cell}_steady_delta_spike_rate_hz"] = sr_steady
            c = column-1
            for direction, color, curve in zip(directions, colors, sr_per_record.mean(axis=0)):
                sr_axes[0, c].plot(time[::5], curve[::5], color=color, label=f"{direction:+d}°")
            sr_axes[0, c].axvspan(0, 4, color="#bbbbbb", alpha=.13)
            sr_axes[0, c].set(title=cell, xlim=(-.4, 6), xlabel="Time from wind command (s)", ylabel="Mean Δspike rate (Hz)")
            for individual in sr_steady:
                sr_axes[1, c].plot(directions, individual, color="#adb5bd", alpha=.5, linewidth=.8)
            sr_axes[1, c].errorbar(directions, sr_steady.mean(axis=0), sr_steady.std(axis=0, ddof=1),
                                 color="#263746", marker="o", capsize=3, linewidth=2)
            sr_axes[1, c].set(xlabel="Wind direction, contra → ipsi (°)", ylabel="Final 1 s ΔHz: mean ± SD", xticks=directions)
        else:
            result["spike_fields_excluded"] = "APN2 is experimentally nonspiking; generic stored SR fields are not biological APN2 spikes."
        results[cell] = result
        print(cell, count, "recordings", sum(trial_counts), "valid trials", "Vm", np.round(t["avgWR"], 3), flush=True)
    axes[0, 2].legend(ncol=3, fontsize=8, loc="upper right")
    sr_axes[0, 1].legend(ncol=3, fontsize=8, loc="upper right")
    output = Path("validation")
    fig.savefig(output/"suver-neural-voltage.png", dpi=160)
    sr_fig.savefig(output/"suver-neural-spikes.png", dpi=160)
    bulk = Path("data/derived/suver-neural-targets.npz")
    bulk.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(bulk, **arrays)
    report = {"completed": True, "dataset_doi": receipt["dataset_doi"], "license": receipt["license"],
              "archive_sha256": receipt["archive_sha256"], "author_code_commit": receipt["author_code_commit"],
              "direction_order_degrees": directions, "direction_frame": "Author-aligned contralateral(-90) to ipsilateral(+90), not world heading",
              "averaging": "Mask trialNums==0 padded slots; average valid repeats within recording, then average recordings equally",
              "repeated_measure_limit": "numFlies metadata counts recordings/cells, not always independent animals; paper APN2 10 cells from 8 flies, APN3 10 cells from 10 flies, WPN 18 cells from 17 flies",
              "voltage_units": "mV baseline-relative; no liquid junction correction added to deltas",
              "source_code": {name: "https://github.com/nagellab/Suveretal2019/blob/"+receipt["author_code_commit"]+"/SuverEtAl2019_AllAnalysis/physiology_plotting_analysis/"+name
                              for name in ["MakeFigure3.m", "MakeFigure4.m", "MakeTracePairFigure.m", "MakeTuningCurveFigure.m", "load_figure_constants.m", "ComputeCellStats_SuverEtAl2019.m"]},
              "bulk_data": {"path": str(bulk), "bytes": bulk.stat().st_size, "sha256": file_hash(bulk)},
              "populations": results,
              "claim_ceiling": "Reconstructed experimental calibration targets, not a simulated match. Female recordings and putative male type identity are separate. No release conductance, membrane time constant or male physiological parameter was fitted."}
    (output/"suver-neural-responses.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
