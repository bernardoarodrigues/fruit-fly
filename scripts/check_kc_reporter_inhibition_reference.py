#!/usr/bin/env python3
"""One complete scalar batch: recurrence, composition and independent ODE checks."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import platform
import numpy as np
import scipy
from scipy.integrate import solve_ivp
from kc_reporter_inhibition_reference import source_step, embedded_step, embedding

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'validation/kc-reporter-inhibition-reference-plan.json'
OUT = ROOT / 'validation/kc-reporter-inhibition-reference-results.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError('Preserve completed results')
    plan = json.loads(PLAN.read_text())
    for p in plan['source_pins']:
        assert sha(ROOT / p['path']) == p['sha256']
    reference_dt = plan['reference_dt_s']
    checks = 0
    rows = []
    max_error = 0.
    for tau in plan['tau_s']:
        for m in plan['modulations']:
            for initial, drive in plan['state_drive_pairs']:
                # Independent exact discrete-map sum over N steps.
                q = m * (1 - reference_dt / tau)
                b = m * reference_dt / tau * drive
                n = plan['reference_steps']
                expected = q ** n * initial + b * sum(q ** j for j in range(n))
                state = initial
                for _ in range(n):
                    state = source_step(state, drive, m, tau, reference_dt)
                exact = embedded_step(initial, drive, m, tau, reference_dt, n * reference_dt)
                errors = [abs(state - expected), abs(exact - expected)]
                # Independently form coefficients from affine map and solve ODE.
                equilibrium = b / (1 - q)
                lam = -math.log(q) / reference_dt
                solution = solve_ivp(lambda t, y: lam * (equilibrium - y),
                                     (0, n * reference_dt), [initial], method='DOP853',
                                     rtol=plan['ode_rtol'], atol=plan['ode_atol'])
                assert solution.success
                errors.append(abs(float(solution.y[0, -1]) - exact))
                for subdivisions in plan['subdivisions']:
                    refined = initial
                    for _ in range(n * subdivisions):
                        refined = embedded_step(refined, drive, m, tau, reference_dt,
                                                reference_dt / subdivisions)
                    errors.append(abs(refined - expected))
                assert max(errors) <= plan['comparison_atol'], (tau, m, errors)
                assert min(state, exact, expected) >= 0
                checks += len(errors) + 2
                max_error = max(max_error, *errors)
                rows.append(dict(tau_s=tau, modulation=m, initial=initial, drive=drive,
                                 discrete_endpoint=state, embedded_endpoint=exact,
                                 ode_endpoint=float(solution.y[0, -1]), max_abs_error=max(errors)))
    # m=0 exposes the deliberate non-embeddable boundary rather than hiding it.
    assert source_step(2., 1., 0., 1.5, reference_dt) == 0.
    try:
        embedding(0., 1.5, reference_dt)
    except ValueError:
        checks += 2
    else:
        raise AssertionError('Zero modulation must not pretend to have finite rate')
    # Fixed declared initial parameters only, not fitted receptor estimates.
    dependence = []
    for calcium in plan['illustrative_calcium']:
        m = 1 / (1 + math.exp((calcium - 0.5) / 0.03))
        for dt in plan['naive_dt_s']:
            a = dt / 1.5
            q = m * (1 - a)
            eq = m * a / (1 - q)
            dependence.append(dict(calcium_arbitrary_units=calcium, modulation=m,
                                   dt_s=dt, equilibrium_per_unit_drive=eq,
                                   effective_decay_s=-dt / math.log(q)))
    result = dict(completed_utc=datetime.now(timezone.utc).isoformat(),
                  status='passed_scalar_numerical_reference', checks=checks,
                  cases=len(rows), max_abs_error=max_error, cases_results=rows,
                  naive_timestep_dependence=dependence, plan_sha256=sha(PLAN),
                  source_pins=plan['source_pins'], python=platform.python_version(),
                  numpy=np.__version__, scipy=scipy.__version__,
                  fitted=False, author_modules_executed=False, neural_network_run=False,
                  physiological_validation=False, runtime_changed=False)
    with OUT.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('cases_results', 'source_pins')}, indent=2))


if __name__ == '__main__':
    main()
