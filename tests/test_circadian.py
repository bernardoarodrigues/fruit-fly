import copy
from dataclasses import asdict, replace

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from fruitfly.circadian import (CircadianClock, LG1998Parameters, LightDarkSchedule,
                               STATE_ORDER, _rhs)


def reference_rhs(y, p, vdT):
    """Independent reaction-flux transcription of paper1a–j, without module RHS."""
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
        (p.k1*y[8], {8:-1, 9:1}),
        (p.k2*y[9], {8:1, 9:-1}),
        (p.kdC*y[8], {8:-1}), (p.kdN*y[9], {9:-1}),
    ):
        for index, factor in stoichiometry.items():
            out[index] += factor*rate
    return out


def oracle(y, p, duration, vdT=None):
    solution = solve_ivp(lambda t, x: reference_rhs(x, p, p.vdT if vdT is None else vdT),
        (0, duration), y, method="DOP853", rtol=2e-12, atol=2e-13, max_step=.1)
    assert solution.success
    return solution.y[:, -1]


def test_equations_match_independent_reaction_fluxes_and_total_balances():
    p = replace(LG1998Parameters.figure4(), V2T=1.7, K3P=.9, kdC=.03, kdN=.04)
    y = np.arange(1., 11.)/7
    observed = _rhs(y, np.array(list(asdict(p).values())), 4.)
    np.testing.assert_allclose(observed, reference_rhs(y, p, 4.), rtol=1e-14, atol=1e-14)
    expected_per = p.ksP*y[0]-p.vdP*y[3]/(p.KdP+y[3])-p.kd*y[1:4].sum()-p.kdC*y[8]-p.kdN*y[9]
    expected_tim = p.ksT*y[4]-4*y[7]/(p.KdT+y[7])-p.kd*y[5:8].sum()-p.kdC*y[8]-p.kdN*y[9]
    assert observed[[1,2,3,8,9]].sum() == pytest.approx(expected_per)
    assert observed[[5,6,7,8,9]].sum() == pytest.approx(expected_tim)


def test_rk4_converges_to_independent_high_accuracy_solver():
    p = LG1998Parameters.figure4()
    initial = np.arange(1., 11.)/20
    reference = oracle(initial, p, 48.)
    errors = []
    for dt in (.04, .02, .01):
        clock = CircadianClock(p, step_h=dt, initial_state=initial)
        clock.advance_hours(48.)
        errors.append(np.max(abs(clock.concentrations_nm-reference)))
    assert errors[1] < errors[0]/12
    assert errors[2] < errors[1]/12
    assert errors[2] < 2e-7


def test_ld_switches_align_and_use_piecewise_derivatives():
    p = LG1998Parameters.figure4()
    clock = CircadianClock(p, step_h=.01, light_schedule=LightDarkSchedule())
    reference = oracle(clock.concentrations_nm, p, 12., vdT=4.)
    assert clock.is_light() and clock.snapshot()["tim_degradation_nm_per_h"] == 4
    clock.advance_hours(12.)
    assert not clock.is_light() and clock.time_h == 12
    np.testing.assert_allclose(clock.concentrations_nm, reference, rtol=0, atol=2e-8)
    reference = oracle(reference, p, 12., vdT=2.)
    clock.advance_hours(12.)
    assert clock.is_light() and clock.time_h == 24
    np.testing.assert_allclose(clock.concentrations_nm, reference, rtol=0, atol=2e-8)


def test_checkpoint_chunking_reset_and_exposed_state_integrity(tmp_path):
    kwargs = dict(parameters=LG1998Parameters.figure4(), light_schedule=LightDarkSchedule())
    a, b = CircadianClock(**kwargs), CircadianClock(**kwargs)
    a.advance_hours(13.37)
    path = tmp_path/'circadian.json'
    a.save_checkpoint(path); b.load_checkpoint(path)
    a.advance_hours(40.)
    for _ in range(4):
        b.advance_hours(10.)
    assert a.state_dict() == b.state_dict()
    exposed = a.concentrations_nm
    exposed.fill(0)
    assert np.any(a.concentrations_nm > 0)
    a.reset()
    assert a.time_h == 0
    np.testing.assert_array_equal(a.concentrations_nm, np.full(10, .1))


@pytest.mark.parametrize('mutation',[
    lambda s: s.update(tick=True), lambda s:s.update(tick=-1),
    lambda s:s.update(time_unit='seconds'), lambda s:s.update(step_h=.02),
    lambda s:s.update(state_order=list(reversed(STATE_ORDER))),
    lambda s:s['state'].__setitem__(0, -1), lambda s:s['state'].__setitem__(0, float('nan')),
    lambda s:s['state'].__setitem__(0, True), lambda s:s['parameters'].update(vsP=True),
    lambda s:s['parameters'].update(k3=1.1), lambda s:s.update(light_schedule={}),
])
def test_invalid_checkpoint_rejected_before_any_write(mutation):
    clock = CircadianClock(); clock.advance_hours(1.)
    before = clock.state_dict(); state = copy.deepcopy(before); mutation(state)
    with pytest.raises(ValueError):
        clock.load_state_dict(state)
    assert clock.state_dict() == before


@pytest.mark.parametrize('changes',[{'vsP':True},{'vdT':float('inf')},{'K1P':0},{'k3':-.1},{'n':0}])
def test_invalid_parameters(changes):
    with pytest.raises(ValueError):
        replace(LG1998Parameters(), **changes)


def test_step_alignment_and_numerical_failure_are_atomic():
    clock = CircadianClock()
    for hours in (.001, -1, float('nan'), True):
        with pytest.raises(ValueError):
            clock.advance_hours(hours)
    assert clock.time_h == 0
    with pytest.raises(ValueError):
        CircadianClock(step_h=.07, light_schedule=LightDarkSchedule())
    large_step = CircadianClock(step_h=100.)
    before = large_step.state_dict()
    with pytest.raises(FloatingPointError):
        large_step.advance_hours(100.)
    assert large_step.state_dict() == before
