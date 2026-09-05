"""Source-native FlyMimic muscle twitch and declared timestep audit.

No brain, policy, or production body adapter is used. Source controls, mechanics,
and units are retained; only the separately named timestep diagnostic changes dt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "9ea1131626cd76f7203b74076ef8f0e9cab30bef"
MODEL_REL = "flymimic/assets/models/best_combined_arm_cvt3.xml"
MODEL_SHA = "59d7db31eb756c61661065c16cfbbb1e3400da1a9df8b1f02fe79dc87bd48724"
PULSE_START_S, PULSE_END_S, END_S, AMPLITUDE = .005, .010, .030, .05
MOTION_THRESHOLD_RAD = 1e-9


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def moments(model, data):
    """Expand current MuJoCo's sparse tendon transmission Jacobian."""
    if data.actuator_moment.shape == (model.nu, model.nv):
        return data.actuator_moment.copy()
    matrix = np.zeros((model.nu, model.nv))
    for i in range(model.nu):
        start, count = int(data.moment_rowadr[i]), int(data.moment_rownnz[i])
        matrix[i, data.moment_colind[start:start+count]] = data.actuator_moment[start:start+count]
    return matrix


def fresh(model):
    data = mujoco.MjData(model)
    key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "default-pose")
    assert key >= 0
    mujoco.mj_resetDataKeyframe(model, data, key)
    mujoco.mj_forward(model, data)
    return data


def run(model, target=None):
    data = fresh(model)
    dt = model.opt.timestep
    steps = int(round(END_S/dt))
    on, off = int(round(PULSE_START_S/dt)), int(round(PULSE_END_S/dt))
    assert abs(steps*dt-END_S) < 1e-14
    assert abs(on*dt-PULSE_START_S) < 1e-14 and abs(off*dt-PULSE_END_S) < 1e-14
    names = ("qpos", "qvel", "act", "actuator_force", "actuator_length", "actuator_velocity", "qfrc_actuator")
    trace = {name: [getattr(data, name).copy()] for name in names}
    trace["time_s"] = [float(data.time)]
    trace["requested_ctrl"] = [data.ctrl.copy()]
    torque_errors = []
    initial_moments = moments(model, data)
    for step in range(steps):
        data.ctrl[:] = 0
        if target is not None and on <= step < off:
            data.ctrl[target] = AMPLITUDE
        mujoco.mj_step(model, data)
        # Refresh derived quantities at the saved post-integration state.
        mujoco.mj_forward(model, data)
        for name in names:
            trace[name].append(getattr(data, name).copy())
        trace["time_s"].append(float(data.time))
        trace["requested_ctrl"].append(data.ctrl.copy())
        torque_errors.append(float(abs(moments(model, data).T @ data.actuator_force-data.qfrc_actuator).max()))
    trace = {name: np.asarray(value) for name, value in trace.items()}
    warning_count = sum(int(w.number) for w in data.warning)
    if not all(np.isfinite(value).all() for value in trace.values()):
        raise AssertionError("Non-finite source-native mechanics")
    assert np.allclose(trace["time_s"], np.arange(steps+1)*dt, rtol=0, atol=1e-14)
    return trace, {"warning_count": warning_count,
        "torque_from_transmission_max_error_native": max(torque_errors),
        "initial_moment_matrix_native_length_per_rad": initial_moments.tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT/"tmp/musculoskeletal-audit/FlyMimic")
    parser.add_argument("--out", type=Path, default=ROOT/"validation/muscle-twitch")
    args = parser.parse_args()
    path = args.source_dir/MODEL_REL
    assert sha(path) == MODEL_SHA, "Expected the pinned, unmodified source MJCF"
    xml = ET.parse(path).getroot()
    meshes = sorted({(path.parent/node.attrib["file"]).resolve() for node in xml.findall("./asset/mesh")})
    source_hashes = {str(p.relative_to(args.source_dir.resolve())): sha(p) for p in [path.resolve(), *meshes]}
    model = mujoco.MjModel.from_xml_path(str(path))
    assert (model.nq, model.nv, model.nu, model.na) == (14, 14, 15, 15)
    assert np.all(model.jnt_type == mujoco.mjtJoint.mjJNT_HINGE)
    assert model.opt.timestep == .0001 and model.opt.integrator == mujoco.mjtIntegrator.mjINT_EULER
    muscle_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)]
    joint_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)]
    parameter_checks = []
    for index, node in enumerate(xml.find("actuator")):
        assert node.attrib["name"] == muscle_names[index]
        for attribute, compiled in [("dynprm", model.actuator_dynprm), ("gainprm", model.actuator_gainprm),
                                    ("biasprm", model.actuator_biasprm), ("ctrlrange", model.actuator_ctrlrange),
                                    ("lengthrange", model.actuator_lengthrange)]:
            parameter_checks.append(np.array_equal(np.fromstring(node.attrib[attribute], sep=" "), compiled[index]))
    assert all(parameter_checks)

    # Independent d(length)/d(q) check at the unchanged source keyframe.
    data = fresh(model)
    analytic = moments(model, data)
    finite_difference = np.zeros_like(analytic)
    epsilon = 1e-7
    q0 = data.qpos.copy()
    for joint in range(model.nv):
        data.qpos[:] = q0
        data.qpos[joint] += epsilon
        mujoco.mj_forward(model, data)
        plus = data.actuator_length.copy()
        data.qpos[:] = q0
        data.qpos[joint] -= epsilon
        mujoco.mj_forward(model, data)
        finite_difference[:, joint] = (plus-data.actuator_length)/(2*epsilon)
    moment_error = float(abs(analytic-finite_difference).max())

    baseline, baseline_info = run(model)
    cases, traces = [], {"baseline__"+key: value for key, value in baseline.items()}
    for index, name in enumerate(muscle_names):
        trace, info = run(model, index)
        pre = trace["time_s"] <= PULSE_START_S + 1e-14
        pulse = (trace["time_s"] > PULSE_START_S + 1e-14) & (trace["time_s"] <= PULSE_END_S + 1e-14)
        gain = np.array([mujoco.mju_muscleGain(length, velocity, model.actuator_lengthrange[index],
            model.actuator_acc0[index], model.actuator_gainprm[index, :9])
            for length, velocity in zip(trace["actuator_length"][pulse, index],
                trace["actuator_velocity"][pulse, index], strict=True)])
        zero_velocity_gain = np.array([mujoco.mju_muscleGain(length, 0., model.actuator_lengthrange[index],
            model.actuator_acc0[index], model.actuator_gainprm[index, :9])
            for length in trace["actuator_length"][pulse, index]])
        delta_q = float(abs(trace["qpos"]-baseline["qpos"]).max())
        cases.append({"muscle": name, "index": index, **info,
            "pre_pulse_qpos_exactly_matches_baseline": bool(np.array_equal(trace["qpos"][pre], baseline["qpos"][pre])),
            "peak_activation": float(trace["act"][:, index].max()),
            "peak_activation_minus_command": float(trace["act"][pulse, index].max()-AMPLITUDE),
            "max_activation_delta_from_baseline": float(abs(trace["act"][:, index]-baseline["act"][:, index]).max()),
            "max_target_force_delta_native": float(abs(trace["actuator_force"][:, index]-baseline["actuator_force"][:, index]).max()),
            "max_generalized_actuator_force_delta_native": float(abs(trace["qfrc_actuator"]-baseline["qfrc_actuator"]).max()),
            "max_joint_angle_delta_rad": delta_q,
            "joint_motion_detected": bool(delta_q > MOTION_THRESHOLD_RAD),
            "actual_active_gain_during_pulse_range_native": [float(gain.min()), float(gain.max())],
            "zero_velocity_active_gain_at_sampled_pulse_lengths_range_native": [float(zero_velocity_gain.min()), float(zero_velocity_gain.max())]})
        traces.update({f"muscle_{index:02d}__"+key: value for key, value in trace.items()})

    representative = muscle_names.index("LFTibia_flex_93434")
    sensitivity, diagnostic_traces = [], []
    for dt in (.0001, .00005, .000025):
        variant = mujoco.MjModel.from_xml_path(str(path))
        variant.opt.timestep = dt  # Declared numerical diagnostic, not source edit.
        trace, info = run(variant, representative)
        diagnostic_traces.append(trace)
        sensitivity.append({"dt_s": dt, "source_default": dt == .0001,
            "warning_count": info["warning_count"],
            "peak_activation": float(trace["act"][:, representative].max()),
            "peak_target_force_magnitude_native": float(abs(trace["actuator_force"][:, representative]).max()),
            "final_qpos_rad": trace["qpos"][-1].tolist()})
        traces.update({f"dt_{round(dt*1e6):03d}us__"+key: value for key, value in trace.items()})
    finest = diagnostic_traces[-1]
    for item, trace in zip(sensitivity, diagnostic_traces, strict=True):
        ratio = round(item["dt_s"]/.000025)
        ref = {key: value[::ratio] for key, value in finest.items()}
        item["max_activation_error_vs_25us_at_shared_times"] = float(abs(trace["act"][:, representative]-ref["act"][:, representative]).max())
        item["max_target_force_error_vs_25us_at_shared_times_native"] = float(abs(trace["actuator_force"][:, representative]-ref["actuator_force"][:, representative]).max())
        item["max_qpos_error_vs_25us_at_shared_times_rad"] = float(abs(trace["qpos"]-ref["qpos"]).max())

    # Scalar oracle for the source's unsmoothed activation ODE, checked against
    # current compiled MuJoCo. Clamps apply before the activation-dependent tau.
    ode_error = 0.
    for control in (.0001, .05, 1.):
        for activation in (0., .0001, .01, .05, .1, 1.):
            tau = .0001*(.5+1.5*activation) if control > activation else .0004/(.5+1.5*activation)
            expected = (control-activation)/tau
            ode_error = max(ode_error, abs(expected-mujoco.mju_muscleDynamics(control, activation, np.array([.0001, .0004, 0.]))))
    checks = {"source_actuator_parameters_preserved": all(parameter_checks),
        "moment_arm_finite_difference": moment_error < 1e-7,
        "torque_from_transmission": max(c["torque_from_transmission_max_error_native"] for c in cases) < 1e-9,
        "source_all_15_activation_responses": all(c["max_activation_delta_from_baseline"] > 1e-6 for c in cases),
        "pre_pulse_paired_equality": all(c["pre_pulse_qpos_exactly_matches_baseline"] for c in cases),
        "no_mujoco_warnings": baseline_info["warning_count"] == 0 and all(c["warning_count"] == 0 for c in cases+sensitivity),
        "activation_ode_oracle": ode_error < 1e-10,
        "source_files_unchanged": all(sha(args.source_dir/p) == digest for p, digest in source_hashes.items())}
    args.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out/"traces.npz", **traces)
    result = {"schema_version": 1, "scope": __doc__, "completed": True,
        "biological_force_validated": False, "motor_neuron_coupling_installed": False,
        "source_commit": COMMIT, "source_sha256": source_hashes,
        "script_sha256": sha(__file__), "mujoco_version": mujoco.__version__, "random_seed": None,
        "protocol": {"initial_state": "source default-pose keyframe; activation zero; no equilibrium burn-in",
            "source_dt_s": .0001, "integrator": "Euler", "pulse_start_s": PULSE_START_S,
            "pulse_end_s": PULSE_END_S, "end_s": END_S, "requested_baseline_control": 0.,
            "requested_pulse_control": AMPLITUDE, "effective_baseline_excitation_floor": .0001,
            "trace_convention": "states after mj_step plus mj_forward; requested_ctrl is the input for the preceding integration interval",
            "motion_detection_threshold_rad": MOTION_THRESHOLD_RAD},
        "compiled_model": {"nq": model.nq, "nv": model.nv, "nu": model.nu, "na": model.na,
            "ntendon": model.ntendon, "equality_constraints": model.neq, "total_mass_native": float(model.body_mass.sum()),
            "gravity_native": model.opt.gravity.tolist(), "joint_names": joint_names, "muscle_names": muscle_names,
            "actuator_dynprm": model.actuator_dynprm.tolist(), "actuator_gainprm": model.actuator_gainprm.tolist(),
            "actuator_biasprm": model.actuator_biasprm.tolist(), "actuator_lengthrange": model.actuator_lengthrange.tolist(),
            "actuator_ctrlrange": model.actuator_ctrlrange.tolist()},
        "units": {"time": "seconds as used by source simulation protocol", "angles": "radians",
            "length_mass_force_torque": "native source model units retained; SI conversion unresolved; do not interpret force as N"},
        "moment_arm_finite_difference_epsilon_rad": epsilon, "moment_arm_max_error_native_length_per_rad": moment_error,
        "integrity_tolerances": {"moment_arm_max_error_native_length_per_rad": 1e-7,
            "torque_reconstruction_max_error_native": 1e-9, "activation_delta_detection": 1e-6,
            "activation_ode_max_error_per_s": 1e-10, "clock_max_error_s": 1e-14,
            "pre_pulse_qpos": "exact equality", "source_parameters": "exact equality"},
        "activation_ode_max_absolute_error_per_s": ode_error, "baseline": baseline_info, "source_native_cases": cases,
        "activation_dynamics_source": {
            "url": "https://github.com/google-deepmind/mujoco/blob/3.9.0/src/engine/engine_util_misc.c",
            "sha256": "0e532965c14a8e0f405b5b718e1ce52261819137435e5b3d7c7ff8cf97d60068",
            "function": "mju_muscleDynamics; tau_act*(0.5+1.5*act_clamped) on rising activation; tau_deact/(0.5+1.5*act_clamped) otherwise; smoothing_width=0",
            "documentation": "https://mujoco.readthedocs.io/en/3.3.2/modeling.html#muscle-actuators"},
        "source_native_mechanically_responsive_count": sum(c["joint_motion_detected"] for c in cases),
        "timestep_sensitivity_muscle": muscle_names[representative], "timestep_sensitivity": sensitivity,
        "checks": checks, "traces_sha256": sha(args.out/"traces.npz"),
        "limits": ["Fourteen clear mechanical responses do not validate all fifteen MTUs across poses or loads.",
            "Zero requested control is not zero excitation; passive forces and gravity remain active.",
            "Source Euler activation overshoot is retained; smaller dt runs are labeled diagnostics, not corrections.",
            "Finest 25us diagnostic is a comparison reference, not proven convergence or biological ground truth.",
            "No motor-neuron identity, spike-to-excitation transfer, force calibration, policy, or whole-body walking is tested."]}
    (args.out/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    axes[0, 0].bar(np.arange(15), [c["max_joint_angle_delta_rad"] for c in cases])
    axes[0, 0].set(xlabel="Source MTU index", ylabel="Maximum paired joint-angle difference (rad)", title="Source dt: 14 clear responses; MTU 4 near zero")
    for trace, item in zip(diagnostic_traces, sensitivity, strict=True):
        label = f"dt {item['dt_s']*1e3:g} ms"
        axes[0, 1].plot(trace["time_s"]*1000, trace["act"][:, representative], label=label)
        axes[1, 0].plot(trace["time_s"]*1000, trace["actuator_force"][:, representative], label=label)
        axes[1, 1].plot(trace["time_s"]*1000, trace["qpos"][:, 6], label=label)
    axes[0, 1].axhline(AMPLITUDE, color="black", ls=":", label="Pulse excitation 0.05")
    for ax, ylabel in zip((axes[0, 1], axes[1, 0], axes[1, 1]), ("Activation (dimensionless)", "Target actuator force (native units)", "Left tibia joint angle (rad)"), strict=True):
        ax.axvspan(5, 10, color="gray", alpha=.1)
        ax.set(xlabel="Simulation time (ms)", ylabel=ylabel)
        ax.legend(fontsize=8)
    fig.suptitle("Source-native FlyMimic mechanical audit / LFTibia_flex_93434 timestep diagnostic\nNo neural coupling or physiological force validation")
    fig.savefig(args.out/"twitch-audit.png", dpi=150)
    plt.close(fig)
    print(json.dumps({"checks": checks, "mechanical_response_count": result["source_native_mechanically_responsive_count"],
        "moment_arm_error": moment_error, "timestep_sensitivity": sensitivity}, indent=2))
    if not all(checks.values()):
        raise AssertionError("Mechanical audit integrity check failed; inspect receipt")


if __name__ == "__main__":
    main()
