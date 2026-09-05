#!/usr/bin/env python3
"""Isolated inhibition-only interval solver and frozen synthetic validation.

No graph, recorded source history, threshold, reset, or runtime is advanced here.
The caller owns macro-clock event/availability decisions. p is positive effective
current in mV; h is a nonnegative inhibitory conductance/leak ratio.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "validation/inhibitory-factorial-solver-plan.json"
RESULTS = ROOT / "validation/inhibitory-factorial-solver-results.json"
REST, REVERSAL, TAU_M, TAU_S = -52., -75., 20., 5.
TAIL_ATOL = 1e-13
INVERSION_RTOL = 1e-13
MAX_INVERSION_ITERATIONS = 48
NODES32, WEIGHTS32 = np.polynomial.legendre.leggauss(32)
NODES64, WEIGHTS64 = np.polynomial.legendre.leggauss(64)


def coefficients(dt):
    """NumPy-computed coefficients, including the source's operation order."""
    a, b = np.exp(-dt / TAU_M), np.exp(-dt / TAU_S)
    c = TAU_S / (TAU_M - TAU_S) * (a - b)
    return float(a), float(b), float(c)


@njit(cache=True)
def _inverse_attenuation(x, dt, h_end):
    """Return r=dt-u, residual and iterations using safeguarded Newton."""
    lo, hi = 0., dt
    r = min(dt, TAU_M * x / (1. + h_end))
    for iteration in range(MAX_INVERSION_ITERATIONS):
        exponential = np.exp(r / TAU_S)
        residual = r / TAU_M + h_end * TAU_S / TAU_M * np.expm1(r / TAU_S) - x
        if abs(residual) <= INVERSION_RTOL * (1. + x):
            return r, abs(residual), iteration + 1
        if residual > 0.:
            hi = r
        else:
            lo = r
        proposal = r - residual * TAU_M / (1. + h_end * exponential)
        r = proposal if lo < proposal < hi else .5 * (lo + hi)
    raise ValueError("Attenuation inversion did not meet frozen residual tolerance")


@njit(cache=True)
def hybrid_step(v, p, h, dt, a, b, coefficient, nodes, weights):
    """One event-free interval, with coefficients and positive GL rule supplied.

    Returns (v_next, p_next, h_next, tail_bound_mv, max_inverse_residual,
    max_inverse_iterations, cutoff). No voltage clamp or target spike logic.
    For h=0 the voltage expression preserves the original source order exactly.
    """
    if not (np.isfinite(v) and np.isfinite(p) and np.isfinite(h) and np.isfinite(dt)):
        raise ValueError("Nonfinite interval input")
    if p < 0. or h < 0. or dt <= 0.:
        raise ValueError("Require nonnegative p,h and positive dt")
    p_end, h_end = p * b, h * b
    if h == 0.:
        value = REST + (v - REST) * a + p * coefficient + 0. * (1. - a)
        return value, p_end, h_end, 0., 0., 0, dt / TAU_M
    attenuation = dt / TAU_M + h * TAU_S / TAU_M * (-np.expm1(-dt / TAU_S))
    cutoff = min(attenuation, np.log((REST - REVERSAL) + p) - np.log(TAIL_ATOL))
    cutoff = max(0., cutoff)
    tail = 0. if cutoff == attenuation else ((REST - REVERSAL) + p) * np.exp(-cutoff)
    half = cutoff * .5
    integral = 0.
    max_residual, max_iterations = 0., 0
    for j in range(len(nodes)):
        x = half * (nodes[j] + 1.)
        r, residual, iterations = _inverse_attenuation(x, dt, h_end)
        exponential = np.exp(r / TAU_S)
        kernel = np.exp(-x) * ((REST - REVERSAL) + p_end * exponential) / (1. + h_end * exponential)
        integral += weights[j] * kernel
        max_residual = max(max_residual, residual)
        max_iterations = max(max_iterations, iterations)
    value = REVERSAL + np.exp(-attenuation) * (v - REVERSAL) + half * integral
    if not np.isfinite(value):
        raise ValueError("Nonfinite hybrid result")
    return value, p_end, h_end, tail, max_residual, max_iterations, cutoff


def hybrid_reference(v, p, h, dt):
    """Independent adaptive quadrature with Brent inversion, same exact ODE."""
    from scipy.integrate import quad
    from scipy.optimize import brentq

    h_end, p_end = h * np.exp(-dt / TAU_S), p * np.exp(-dt / TAU_S)
    attenuation = dt / TAU_M + h * TAU_S / TAU_M * (-np.expm1(-dt / TAU_S))
    # Tighter tail than production; no h=0 shortcut in this reference.
    cutoff = min(attenuation, np.log(23. + p) - np.log(1e-15))
    def kernel(x):
        def f(r):
            return r / TAU_M + h_end * TAU_S / TAU_M * np.expm1(r / TAU_S) - x
        r = brentq(f, 0., dt, xtol=np.nextafter(0., 1.), rtol=8*np.finfo(float).eps)
        exponential = np.exp(r / TAU_S)
        return np.exp(-x) * (23. + p_end * exponential) / (1. + h_end * exponential)
    integral, error = quad(kernel, 0., cutoff, epsabs=1e-11, epsrel=1e-13, limit=200)
    tail = 0. if cutoff == attenuation else (23. + p) * np.exp(-cutoff)
    return float(REVERSAL + np.exp(-attenuation) * (v - REVERSAL) + integral), float(error + tail)


def ode_reference(v, p, h, dt):
    """Independent time-domain ODE; implicit Radau resolves stiff cases."""
    from scipy.integrate import solve_ivp

    method = "Radau" if (1. + h) * dt / TAU_M > 10. else "DOP853"
    def derivative(t, value):
        decay = np.exp(-t / TAU_S)
        return [(23. + p * decay - (1. + h * decay) * value[0]) / TAU_M]
    result = solve_ivp(derivative, (0., dt), [v - REVERSAL], method=method,
                       rtol=2e-12, atol=2e-12)
    if not result.success or result.t[-1] != dt:
        raise RuntimeError("Independent ODE reference failed: " + result.message)
    return float(REVERSAL + result.y[0, -1]), method, int(result.nfev)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def prepare():
    if PLAN.exists() or RESULTS.exists():
        raise FileExistsError("Preserve frozen helper validation")
    grid = []
    for h in [0., 1e-8, .1, 2.999999, 3., 3.000001, 100., 1e4, 1e8]:
        for ratio in [0., .1, 1., 100.]:
            for v in [-75., -52., -45.1]:
                grid.append({"v": v, "p": h * ratio, "h": h, "dt": .1, "p_over_h": ratio if h else None})
    # Nonzero excitation-only tests and macro-interval subdivision checks.
    grid += [{"v": v, "p": p, "h": 0., "dt": .1, "p_over_h": None}
             for v in [-75., -52., -45.1] for p in [1., 100., 1e4]]
    grid += [{"v": -52., "p": h*ratio, "h": h, "dt": dt, "p_over_h": ratio}
             for h in [3., 1e8] for ratio in [0., 100.] for dt in [.05, .025]]
    versions = {}
    from importlib.metadata import version
    for name in ["numpy", "scipy", "numba"]:
        versions[name] = version(name)
    write(PLAN, {"schema": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(Path(__file__).relative_to(ROOT)): sha(__file__)},
        "dependencies": versions, "cases": grid, "case_count": len(grid),
        "constants": {"rest_mv": REST, "reversal_mv": REVERSAL, "tau_m_ms": TAU_M, "tau_s_ms": TAU_S},
        "production": {"quadrature": "32-point Gauss-Legendre, positive weights; attenuation coordinate", "comparison_order": 64,
            "tail_bound_mv": TAIL_ATOL, "inversion_residual": "abs(f(r)-x)<=1e-13*(1+x)",
            "inversion_max_iterations": MAX_INVERSION_ITERATIONS,
            "h_zero": "Original NumPy coefficients and exact source operation order; no quadrature"},
        "reference": {"quadrature": "SciPy quad epsabs1e-11 epsrel1e-13; independent Brent inversion; tail1e-15",
            "ode": "DOP853 if stiffness<=10, otherwise Radau; rtol2e-12 atol2e-12",
            "constant_conductance": "Separate independent scalar ODE vs analytic constant-h/exponentially decaying-p formula; not the production decaying-h equation"},
        "tolerances_mv": {"production_vs_quad": 1e-8, "32_vs_64": 1e-8, "ode_vs_quad": 2e-8,
            "bounds": 1e-10, "quad_error_estimate": 1e-9, "constant_h_reference": 2e-8},
        "synthetic_controls": ["passive and excitation-only exact source transition", "near frozen lambda=nu h=3", "constant h analytic reference", "interval split .05/.025 without any threshold events", "lower EI and upper max(v0,EL+p0) interval bounds", "exact p,h exponential decay"],
        "claim_limit": "Synthetic scalar numerical validation only. No recorded history, graph, threshold, refractory protocol, fit or physiological validity test.",
        "failure_policy": "Retain failed receipt; no silent change to grid, tolerance, solver or source"})
    print(json.dumps({"plan_sha256": sha(PLAN), "cases": len(grid)}), flush=True)


def constant_h_check(v, p, h, dt):
    """Analytic control for a different, explicitly constant-h equation."""
    from scipy.integrate import solve_ivp

    lam, nu = (1. + h) / TAU_M, 1. / TAU_S
    equilibrium = (REST + h * REVERSAL) / (1. + h)
    delta = lam - nu
    # Stable divided difference, including the coincident-exponent limit.
    response = dt*np.exp(-lam*dt) if delta == 0. else np.exp(-min(lam,nu)*dt)*(-np.expm1(-abs(delta)*dt))/abs(delta)
    analytic = equilibrium + (v-equilibrium)*np.exp(-lam*dt) + p/TAU_M*response
    def f(t, y):
        return [(REST - y[0] + p*np.exp(-t/TAU_S) + h*(REVERSAL-y[0]))/TAU_M]
    numerical = solve_ivp(f, (0.,dt), [v], method="DOP853", rtol=2e-12, atol=2e-12)
    if not numerical.success:
        raise RuntimeError(numerical.message)
    return float(analytic), float(numerical.y[0,-1])


def validate():
    if RESULTS.exists():
        raise FileExistsError("Preserve prior helper receipt")
    plan = json.loads(PLAN.read_text())
    for path, digest in plan["source_sha256"].items():
        if sha(ROOT/path) != digest:
            raise ValueError("Frozen helper changed")
    report = {"plan_sha256": sha(PLAN), "complete": False, "cases": [], "controls": [], "error": None}
    try:
        for i, case in enumerate(plan["cases"]):
            v,p,h,dt = (case[k] for k in ["v", "p", "h", "dt"])
            a,b,c = coefficients(dt)
            result = hybrid_step(v,p,h,dt,a,b,c,NODES32,WEIGHTS32)
            fine = hybrid_step(v,p,h,dt,a,b,c,NODES64,WEIGHTS64)
            ref, estimate = hybrid_reference(v,p,h,dt)
            ode, method, nfev = ode_reference(v,p,h,dt)
            checks = {"finite": bool(np.isfinite(result).all()), "32_vs_64": abs(result[0]-fine[0])<=1e-8,
                "production_vs_quad": abs(result[0]-ref)<=1e-8, "ode_vs_quad": abs(ode-ref)<=2e-8,
                "quad_error_estimate": estimate<=1e-9, "lower_bound": result[0]>=REVERSAL-1e-10,
                "upper_bound": result[0]<=max(v,REST+p)+1e-10, "exact_synaptic_decay": result[1]==p*b and result[2]==h*b,
                "tail_bound": result[3]<=1.01e-13, "inversion_iterations": result[5]<=MAX_INVERSION_ITERATIONS}
            if h == 0.:
                expected = REST+(v-REST)*a+p*c+0.*(1.-a)
                checks["h_zero_bitwise_source"] = np.float64(result[0]).tobytes()==np.float64(expected).tobytes()
            report["cases"].append({"case": case, "production": list(result), "order64_mv": fine[0],
                "quad_mv": ref, "quad_error_bound_estimate_mv": estimate, "ode_mv": ode, "ode_method": method, "ode_nfev": nfev,
                "errors_mv": {"production_quad": abs(result[0]-ref), "production64": abs(result[0]-fine[0]), "ode_quad": abs(ode-ref)},
                "checks": {k:bool(value) for k,value in checks.items()}})
            if (i+1)%25 == 0:
                print(json.dumps({"completed_cases": i+1, "all_checks_so_far": all(all(r["checks"].values()) for r in report["cases"])}), flush=True)
        for h in [0., 2.999999, 3., 3.000001, 100.]:
            analytic, numeric = constant_h_check(-52., 100., h, .1)
            report["controls"].append({"name": "constant_h_reference", "h": h, "analytic_mv": analytic, "ode_mv": numeric,
                "checks": {"analytic_vs_ode": abs(analytic-numeric)<=2e-8}})
        for h in [0., 3., 1e8]:
            v,p = -52., max(100.,100*h)
            whole = hybrid_step(v,p,h,.1,*coefficients(.1),NODES32,WEIGHTS32)[0]
            subdivided = []
            for pieces in [2,4]:
                vv,pp,hh = v,p,h
                for _ in range(pieces):
                    vv,pp,hh,*_ = hybrid_step(vv,pp,hh,.1/pieces,*coefficients(.1/pieces),NODES32,WEIGHTS32)
                subdivided.append(vv)
            report["controls"].append({"name": "event_free_interval_subdivision", "h": h, "whole_mv": whole,
                "subdivided_mv": subdivided, "checks": {"same_interval": max(abs(x-whole) for x in subdivided)<=1e-8}})
        report["complete"] = len(report["cases"]) == plan["case_count"]
    except Exception as exc:
        import traceback
        report["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    report["checks"] = {"source_unchanged": all(sha(ROOT/p)==h for p,h in plan["source_sha256"].items()),
        "positive_quadrature_weights": bool((WEIGHTS32>0).all() and (WEIGHTS64>0).all()),
        "no_error": report["error"] is None}
    report["passed"] = report["complete"] and all(report["checks"].values()) and all(all(r["checks"].values()) for r in report["cases"]+report["controls"])
    report["check_count"] = len(report["checks"])+sum(len(r["checks"]) for r in report["cases"]+report["controls"])
    write(RESULTS, report)
    print(json.dumps({k:report[k] for k in ["complete","passed","check_count","error"]}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else validate()
