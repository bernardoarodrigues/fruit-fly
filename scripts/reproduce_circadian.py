"""Reproduce LG1998 Figure2 and Figure4 oscillations without phase fitting."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.signal import find_peaks

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fruitfly.circadian import (CircadianClock, LG1998Parameters, LightDarkSchedule,
                               STATE_ORDER, MODEL_ID, SOURCE_DOI)
from fruitfly.data import sha256


PAPER = Path("tmp/circadian/leloup-goldbeter-1998.pdf")
PAPER_SHA256 = "efdb43c8d3d8a434721ddfe00afc8ba038bfb1b36e566a12b69265f55d12f1aa"
BURN_IN_H = 1200.
OBSERVATION_H = 240.
SAMPLE_H = .05


def reference_rhs(y, p, vdT):
    """Independent reaction-flux oracle; does not call circadian._rhs."""
    out = np.zeros(10)
    for letter, offset, degradation in (("P", 0, p.vdP), ("T", 4, vdT)):
        m, u, mono, bis = y[offset:offset+4]
        affinity = getattr(p, "KI"+letter)
        out[offset] = getattr(p, "vs"+letter)*affinity**p.n/(affinity**p.n+y[9]**p.n)
        out[offset] -= getattr(p, "vm"+letter)*m/(getattr(p, "Km"+letter)+m)
        out[offset+1] += getattr(p, "ks"+letter)*m
        for number, source, target in ((1, 1, 2), (2, 2, 1), (3, 2, 3), (4, 3, 2)):
            substrate = y[offset+source]
            flux = getattr(p, f"V{number}{letter}")*substrate/(getattr(p, f"K{number}{letter}")+substrate)
            out[offset+source] -= flux
            out[offset+target] += flux
        out[offset+3] -= degradation*bis/(getattr(p, "Kd"+letter)+bis)
        out[offset:offset+4] -= p.kd*y[offset:offset+4]
    for rate, stoichiometry in (
        (p.k3*y[3]*y[7], {3:-1, 7:-1, 8:1}), (p.k4*y[8], {3:1, 7:1, 8:-1}),
        (p.k1*y[8], {8:-1, 9:1}), (p.k2*y[9], {8:1, 9:-1}),
        (p.kdC*y[8], {8:-1}), (p.kdN*y[9], {9:-1}),
    ):
        for index, factor in stoichiometry.items():
            out[index] += factor*rate
    return out


def oracle(y, p, duration, vdT=None):
    solution = solve_ivp(lambda t, x: reference_rhs(x, p, p.vdT if vdT is None else vdT),
        (0, duration), y, method="DOP853", rtol=2e-12, atol=2e-13, max_step=.1)
    if not solution.success:
        raise RuntimeError(solution.message)
    return solution.y[:, -1]


def sample(clock, duration):
    times, states = [clock.time_h], [clock.concentrations_nm]
    for _ in range(round(duration/SAMPLE_H)):
        clock.advance_hours(SAMPLE_H)
        times.append(clock.time_h); states.append(clock.concentrations_nm)
    return np.asarray(times), np.asarray(states)


def series(states):
    values = dict(zip(STATE_ORDER, states.T))
    values["PER_total"] = states[:,1:4].sum(axis=1)+states[:,8:10].sum(axis=1)
    values["TIM_total"] = states[:,5:8].sum(axis=1)+states[:,8:10].sum(axis=1)
    return values


def peak_times(times, values):
    indices, _ = find_peaks(values, distance=round(12/SAMPLE_H))
    # Three-point quadratic interpolation reduces the sampling-grid phase error.
    curvature = values[indices-1]-2*values[indices]+values[indices+1]
    displacement = .5*(values[indices-1]-values[indices+1])/curvature
    return times[indices]+displacement*SAMPLE_H


def characterize(times, states, *, light):
    values = series(states)
    peaks = {name: peak_times(times, v) for name,v in values.items()}
    metrics = {}
    for name, v in values.items():
        intervals = np.diff(peaks[name])
        if len(intervals) < 5:
            raise AssertionError("Not enough settled cycles for period estimation")
        metrics[name] = {"minimum_nm": float(v.min()), "maximum_nm": float(v.max()),
            "peak_to_trough_nm": float(np.ptp(v)), "period_mean_h": float(intervals.mean()),
            "period_sd_h": float(intervals.std(ddof=1)), "peak_times_h": peaks[name].tolist()}
        if light:
            metrics[name]["peak_zeitgeber_h"] = float(np.mean(peaks[name] % 24))
            metrics[name]["peak_zeitgeber_sd_h"] = float(np.std(peaks[name] % 24, ddof=1))
    lags = {}
    for source, target in (("MP", "PER_total"), ("MP", "CN"), ("MP", "MT"), ("PER_total", "TIM_total")):
        delays = []
        for t in peaks[source]:
            later = peaks[target][peaks[target] >= t-1e-8]
            if len(later):
                delays.append(later[0]-t)
        lags[f"{source}_to_{target}"] = {"mean_h": float(np.mean(delays)), "sd_h": float(np.std(delays, ddof=1))}
    result = {"states": metrics, "peak_lags": lags,
        "per_tim_symmetry_max_difference_nm": float(np.max(abs(states[:,:4]-states[:,4:8])))}
    if light:
        cycle = round(24/SAMPLE_H)
        result["maximum_24h_stroboscopic_residual_nm"] = float(np.max(abs(states[cycle:]-states[:-cycle])))
    return result


def numerical_check(parameters, schedule):
    initial = np.arange(1., 11.)/20
    if schedule is None:
        reference = oracle(initial, parameters, 48.)
    else:
        reference = initial
        for light in (True, False, True, False):
            reference = oracle(reference, parameters, 12., vdT=4. if light else 2.)
    result = {}
    for dt in (.04, .02, .01):
        clock = CircadianClock(parameters, step_h=dt, initial_state=initial, light_schedule=schedule)
        clock.advance_hours(48.)
        result[str(dt)] = float(np.max(abs(clock.concentrations_nm-reference)))
    if not result["0.01"] < 2e-7:
        raise AssertionError("RK4 disagrees with independent high-accuracy integration")
    return {"comparison_h": 48., "solver": "SciPy DOP853 independent reaction-flux RHS",
            "rtol": 2e-12, "atol": 2e-13, "max_step_h": .1, "rk4_max_absolute_error_nm": result}


def plot(records, trajectories, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(12, 9), constrained_layout=True)
    colors = {"PER_total":"#2166ac", "TIM_total":"#c05a18", "MP":"#2166ac", "MT":"#c05a18", "CN":"#555555"}
    for row, record in enumerate(records):
        times, states = trajectories[record["name"]]
        mask = times >= times[-1]-72
        x = times[mask]-(times[-1]-72)
        values = series(states[mask])
        symmetric = record["name"] == "figure2_DD"
        groups = [("PER_total",) if symmetric else ("PER_total", "TIM_total"),
                  ("MP", "CN") if symmetric else ("MP", "MT", "CN")]
        for col, names in enumerate(groups):
            ax = axes[row,col]
            for name in names:
                label = {"PER_total":"PER = TIM" if symmetric else "PER total", "TIM_total":"TIM total",
                         "MP":"per = tim mRNA" if symmetric else "per mRNA", "MT":"tim mRNA", "CN":"Nuclear complex"}[name]
                ax.plot(x, values[name], color=colors[name], label=label, lw=1.6,
                        linestyle="--" if name == "CN" else "-")
            if record["light_schedule"]:
                for start in (12,36,60): ax.axvspan(start,start+12,color="#e5e7eb",zorder=-1)
            ax.set_xlim(0,72); ax.set_xticks(np.arange(0,73,12)); ax.set_ylim(bottom=0)
            ax.set_ylabel("Concentration (tentative nM)"); ax.grid(alpha=.16)
            ax.legend(fontsize=8,loc="upper right")
            if row == 2: ax.set_xlabel("Biological hours in final 72-hour window")
        period = record["metrics"]["states"]["MP"]["period_mean_h"]
        title = {"figure2_DD":"Figure 2 parameters - symmetric, constant dark",
                 "figure4_DD":"Figure 4 parameters - asymmetric, constant dark",
                 "figure4_LD":"Figure 4 parameters - 12:12 light/dark"}[record["name"]]
        axes[row,0].set_title(f"{title}\nSettled period {period:.4f} h",fontsize=10)
        lag = record["metrics"]["peak_lags"]["MP_to_CN"]["mean_h"]
        axes[row,1].set_title(f"Transcripts and nuclear repression\nper mRNA to nuclear-complex peak: {lag:.2f} h",fontsize=10)
    fig.suptitle("Leloup-Goldbeter 1998: isolated PER/TIM oscillator reproduction",fontsize=14)
    fig.supxlabel("Author-chosen parameters; analyst-chosen initial state and burn-in; no fitted phase or brain/body/sleep coupling.\nShading denotes darkness only in the light/dark row.",fontsize=9)
    fig.savefig(destination,dpi=160)
    plt.close(fig)


def main():
    if not PAPER.exists() or sha256(PAPER) != PAPER_SHA256:
        raise SystemExit("Expected primary PDF missing/different; obtain https://utc.ulb.be/ARTICLES/1998_Leloup_JBR.pdf and verify source receipt")
    output = Path("validation/circadian-lg1998"); output.mkdir(parents=True, exist_ok=True)
    provenance_dir = Path("data/circadian"); provenance_dir.mkdir(parents=True, exist_ok=True)
    provenance = {"model": MODEL_ID, "doi": SOURCE_DOI,
        "source_url": "https://utc.ulb.be/ARTICLES/1998_Leloup_JBR.pdf",
        "title": "A Model for Circadian Rhythms in Drosophila Incorporating the Formation of a Complex between the PER and TIM Proteins",
        "authors": ["Jean-Christophe Leloup", "Albert Goldbeter"], "year": 1998,
        "pdf_sha256": PAPER_SHA256, "pdf_bytes": PAPER.stat().st_size,
        "source_location": str(PAPER), "pdf_redistributed": False,
        "license": "Source article copyright1998 Sage; no open license established; PDF remains an ignored research copy",
        "equations": "1a-j, physical PDFpages3-4, journalpages72-73; totals equations2-3",
        "figure2_parameters": "physical PDFpage5, journalpage74, full caption",
        "figure4_parameters": "physical PDFpage9, journalpage78, full caption",
        "period_reference": "Figure6 caption, physical PDFpage11/journalpage80: Figure2 wild-type free-running period24.135h",
        "concentration_convention": "Tentative nM; all concentrations and parameters referenced to total cell volume",
        "parameter_evidence": "Author-chosen model values; not measured male-specific biochemical kinetics",
        "access_note": "CellML repository pages returned403 in prior source review; not accessed through a workaround; equations transcribed from primaryPDF"}
    (provenance_dir/"lg1998-provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    report = {"complete": False, "provenance": provenance,
        "initial_state_nm": [.1]*10, "initial_state_claim": "Analyst-chosen positive initial state; paper figure captions do not specify exact phase/state; no phase fitting",
        "burn_in_h": BURN_IN_H, "observation_h": OBSERVATION_H, "sample_h": SAMPLE_H,
        "step_h": .01, "state_order": list(STATE_ORDER),
        "metric_convention": "Local peaks: three-point quadratic interpolation; amplitudes: sampled peak-to-trough, not half-range; positive lag uses next target peak",
        "code_sha256": {p:sha256(Path(p)) for p in ("fruitfly/circadian.py", "scripts/reproduce_circadian.py", "tests/test_circadian.py")},
        "records": []}
    trajectories = {}
    protocols = [("figure2_DD",LG1998Parameters(),None),
                 ("figure4_DD",LG1998Parameters.figure4(),None),
                 ("figure4_LD",LG1998Parameters.figure4(),LightDarkSchedule())]
    for name, parameters, schedule in protocols:
        clock = CircadianClock(parameters, light_schedule=schedule)
        clock.advance_hours(BURN_IN_H)
        times, states = sample(clock, OBSERVATION_H)
        metrics = characterize(times, states, light=schedule is not None)
        record = {"name":name,"parameters":asdict(parameters),
            "light_schedule":asdict(schedule) if schedule else None,
            "metrics":metrics,"numerical_check":numerical_check(parameters,schedule)}
        clock.save_checkpoint(output/f"{name}-checkpoint.json")
        trajectories[name]=(times,states)
        np.savez_compressed(output/f"{name}-timeseries.npz",biological_time_h=times,
                            concentrations_tentative_nm=states,state_order=np.asarray(STATE_ORDER))
        # Distinct positive IC checks attraction without shifting/fitting phase.
        alternate = CircadianClock(parameters,light_schedule=schedule,
            initial_state=[.6,.2,.3,.4,.9,.7,.1,.5,.2,.3])
        alternate.advance_hours(BURN_IN_H)
        alternate_times,alternate_states=sample(alternate,OBSERVATION_H)
        alternate_metrics=characterize(alternate_times,alternate_states,light=schedule is not None)
        record["alternate_initial_state_nm"]=[.6,.2,.3,.4,.9,.7,.1,.5,.2,.3]
        record["alternate_initial_condition"]={
            "MP_period_difference_h":abs(metrics["states"]["MP"]["period_mean_h"]-alternate_metrics["states"]["MP"]["period_mean_h"]),
            "maximum_amplitude_difference_nm":max(abs(metrics["states"][k]["peak_to_trough_nm"]-alternate_metrics["states"][k]["peak_to_trough_nm"]) for k in metrics["states"]),
            "maximum_synchronized_state_difference_nm":float(np.max(abs(states-alternate_states))) if schedule else None,
            "interpretation":"No time/phase alignment applied; DD phases need not coincide, LD attraction compared at same Zeitgeber time"}
        report["records"].append(record)
        (output/"results.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
        print(name,"period",metrics["states"]["MP"]["period_mean_h"],"lags",metrics["peak_lags"],flush=True)
    dd,asym,ld=report["records"]
    report["checks"]={
        "figure2_published_period_within_0_01h":abs(dd["metrics"]["states"]["MP"]["period_mean_h"]-24.135)<.01,
        "figure2_symmetric_branches":dd["metrics"]["per_tim_symmetry_max_difference_nm"]<1e-12,
        "figure2_nuclear_peak_about5h_later":4.5<dd["metrics"]["peak_lags"]["MP_to_CN"]["mean_h"]<5.5,
        "ld_24h_period":abs(ld["metrics"]["states"]["MP"]["period_mean_h"]-24)<1e-6,
        "ld_stroboscopic_recurrence":ld["metrics"]["maximum_24h_stroboscopic_residual_nm"]<1e-7,
        "ld_distinct_ic_same_phase":ld["alternate_initial_condition"]["maximum_synchronized_state_difference_nm"]<1e-6,
        "alternate_ic_amplitude_and_period_agree":all(r["alternate_initial_condition"]["MP_period_difference_h"]<1e-3 and r["alternate_initial_condition"]["maximum_amplitude_difference_nm"]<1e-3 for r in report["records"]),
        "rk4_all_oracle_checks":all(r["numerical_check"]["rk4_max_absolute_error_nm"]["0.01"]<2e-7 for r in report["records"]),
    }
    report["comparison_limit"]="Period reference is explicit in Figure6. Amplitudes visually agree with Figure2/4; no raw source trajectory or plot digitization is available. Figure4 prose gives approximate lags; computed values are retained without parameter/phase adjustment."
    report["complete"]=True;report["passed"]=all(report["checks"].values())
    (output/"results.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    plot(report["records"],trajectories,output/"reproduction.png")
    print(json.dumps(report["checks"],indent=2))
    if not report["passed"]:
        raise SystemExit("Reproduction check failed; no parameter/phase fitting performed")


if __name__=="__main__":
    main()
