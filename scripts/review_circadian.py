"""Reproduce the independent, local-source LG1998 numerical review.

No web access or brain/body integration. Time is hours; concentrations are
tentatively nM. The scalar RHS is a separate transcription of equations 1a–j.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fruitfly.circadian import CircadianClock, LG1998Parameters, LightDarkSchedule, _rhs


def reference_rhs(y, p, vdT):
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
        (p.k3*y[3]*y[7], {3:-1, 7:-1, 8:1}),
        (p.k4*y[8], {3:1, 7:1, 8:-1}),
        (p.k1*y[8], {8:-1, 9:1}), (p.k2*y[9], {8:1, 9:-1}),
        (p.kdC*y[8], {8:-1}), (p.kdN*y[9], {9:-1}),
    ):
        for index, factor in stoichiometry.items():
            out[index] += factor*rate
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/circadian-lg1998/independent-review.json")
    parser.add_argument("--source-pdf", type=Path, default=ROOT/"tmp/circadian/leloup-goldbeter-1998.pdf")
    args = parser.parse_args()
    source_hash = hashlib.sha256(args.source_pdf.read_bytes()).hexdigest()
    rng = np.random.default_rng(1978)
    max_rhs = max_balance = 0.
    for _ in range(200):
        p = LG1998Parameters(**{k: float(v*rng.uniform(.25, 2)) for k, v in asdict(LG1998Parameters()).items()})
        y = rng.uniform(0, 12, size=10)
        vdT = float(rng.uniform(0, 5))
        actual = _rhs(y, np.array(list(asdict(p).values())), vdT)
        max_rhs = max(max_rhs, float(np.max(abs(actual-reference_rhs(y, p, vdT)))))
        for indices, m, protein, vd, Kd, ks in (
            ([1, 2, 3, 8, 9], 0, slice(1, 4), p.vdP, p.KdP, p.ksP),
            ([5, 6, 7, 8, 9], 4, slice(5, 8), vdT, p.KdT, p.ksT),
        ):
            balance = ks*y[m]-vd*y[m+3]/(Kd+y[m+3])-p.kd*y[protein].sum()-p.kdC*y[8]-p.kdN*y[9]
            max_balance = max(max_balance, float(abs(actual[indices].sum()-balance)))
    p = LG1998Parameters.figure4()
    clock = CircadianClock(p, light_schedule=LightDarkSchedule(phase_h=3.))
    y = clock.concentrations_nm
    segments = [(3., 2.), (12., 4.), (12., 2.), (12., 4.), (9., 2.)]
    for duration, vdT in segments:
        sol = solve_ivp(lambda t, x: reference_rhs(x, p, vdT), (0, duration), y,
                        method="DOP853", rtol=1e-12, atol=1e-13, max_step=.1)
        if not sol.success:
            raise RuntimeError(sol.message)
        y = sol.y[:, -1]
    clock.advance_hours(48.)
    shift_error = float(np.max(abs(clock.concentrations_nm-y)))
    if max_rhs > 1e-11 or max_balance > 1e-11 or shift_error > 1e-7:
        raise AssertionError("Independent circadian numerical review failed")
    result = {
        "source_doi": "10.1177/074873098128999934", "source_pdf_sha256": source_hash,
        "time_unit": "biological_hours", "concentration_unit": "tentative_nM",
        "visual_source_audit": "Local equations1a–j, totals2–3 and Figure2/4 captions inspected; no transcription mismatch found. Manual source review is not automated by this script.",
        "seed": 1978, "randomized_asymmetric_cases": 200,
        "randomization": "Each Figure2 parameter independently multiplied by uniform[.25,2]; states uniform[0,12] tentative nM; vdT uniform[0,5] tentative nM/h.",
        "max_rhs_absolute_error_nm_per_h": max_rhs,
        "max_total_balance_error_nm_per_h": max_balance,
        "shifted_LD": {"duration_h": 48., "step_h": .01, "phase_h": 3.,
            "segments_duration_h_and_vdT_nm_per_h": segments, "parameters": asdict(p),
            "initial_state_nm": [.1]*10, "oracle": "piecewise DOP853 rtol1e-12 atol1e-13 max_step.1h",
            "max_state_error_nm": shift_error},
        "reviewed_files_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT/"fruitfly/circadian.py", Path(__file__))},
        "completed": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"output": str(args.output), "rhs_error": max_rhs,
                      "total_balance_error": max_balance, "shifted_LD_error_nm": shift_error}))


if __name__ == "__main__":
    main()
