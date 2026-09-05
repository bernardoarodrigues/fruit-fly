"""Isolated Leloup–Goldbeter (1998) PER/TIM oscillator, equations1a–j.

Time is biological hours; concentrations are tentatively nM, as in the paper.
Figure2 defaults are author-chosen model parameters, not measured male values.
This module has no connection to the neural/body clock, motor drive, or sleep.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import json
import math
from numbers import Real
from pathlib import Path

import numpy as np
from numba import njit


MODEL_ID = "leloup-goldbeter-1998-equations-1a-j"
STATE_ORDER = ("MP", "P0", "P1", "P2", "MT", "T0", "T1", "T2", "C", "CN")
SOURCE_DOI = "10.1177/074873098128999934"


def _real(value, name, *, positive=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    value = float(value)
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return value


@dataclass(frozen=True)
class LG1998Parameters:
    """Paper Figure2 values; Figure4 changes are an explicit named constructor.

    vs/vm/vd/V: nM/hour; K: nM; ks/k1/k2/k4/kd:1/hour;
    k3:1/(nM hour); n: dimensionless. Units are model conventions.
    """
    vsP: float = 1.
    vsT: float = 1.
    vmP: float = .7
    vmT: float = .7
    KmP: float = .2
    KmT: float = .2
    ksP: float = .9
    ksT: float = .9
    vdP: float = 2.
    vdT: float = 2.
    k1: float = .6
    k2: float = .2
    k3: float = 1.2
    k4: float = .6
    KIP: float = 1.
    KIT: float = 1.
    KdP: float = .2
    KdT: float = .2
    n: float = 4.
    K1P: float = 2.
    K1T: float = 2.
    K2P: float = 2.
    K2T: float = 2.
    K3P: float = 2.
    K3T: float = 2.
    K4P: float = 2.
    K4T: float = 2.
    kd: float = .01
    kdC: float = .01
    kdN: float = .01
    V1P: float = 8.
    V1T: float = 8.
    V2P: float = 1.
    V2T: float = 1.
    V3P: float = 8.
    V3T: float = 8.
    V4P: float = 1.
    V4T: float = 1.

    def __post_init__(self):
        for f in fields(self):
            object.__setattr__(self, f.name,
                _real(getattr(self, f.name), f.name, positive=f.name.startswith("K") or f.name == "n"))

    @classmethod
    def figure4(cls):
        return replace(cls(), vsP=.8, vmP=.8, k1=1.2)


@dataclass(frozen=True)
class LightDarkSchedule:
    """Figure4D–F: first12h light, next12h dark, repeated in biological hours.

    Only vdT changes, to4nM/hour in light. Dark vdT comes from the parameters.
    Phase0 is the declared start of light, not a fitted internal oscillator phase.
    """
    period_h: float = 24.
    light_h: float = 12.
    phase_h: float = 0.
    light_vdT: float = 4.

    def __post_init__(self):
        for f in fields(self):
            object.__setattr__(self, f.name, _real(getattr(self, f.name), f.name,
                positive=f.name in ("period_h", "light_h")))
        if self.light_h >= self.period_h or self.phase_h >= self.period_h:
            raise ValueError("Light duration and phase must be less than the period")


@njit(cache=True)
def _rhs(y, p, vdT):
    (vsP, vsT, vmP, vmT, KmP, KmT, ksP, ksT, vdP, unused_vdT,
     k1, k2, k3, k4, KIP, KIT, KdP, KdT, n,
     K1P, K1T, K2P, K2T, K3P, K3T, K4P, K4T, kd, kdC, kdN,
     V1P, V1T, V2P, V2T, V3P, V3T, V4P, V4T) = p
    MP, P0, P1, P2, MT, T0, T1, T2, C, CN = y
    bind = k3*P2*T2-k4*C
    p01, p10 = V1P*P0/(K1P+P0), V2P*P1/(K2P+P1)
    p12, p21 = V3P*P1/(K3P+P1), V4P*P2/(K4P+P2)
    t01, t10 = V1T*T0/(K1T+T0), V2T*T1/(K2T+T1)
    t12, t21 = V3T*T1/(K3T+T1), V4T*T2/(K4T+T2)
    return np.array([
        vsP/(1+(CN/KIP)**n)-vmP*MP/(KmP+MP)-kd*MP,
        ksP*MP-p01+p10-kd*P0,
        p01-p10-p12+p21-kd*P1,
        p12-p21-bind-vdP*P2/(KdP+P2)-kd*P2,
        vsT/(1+(CN/KIT)**n)-vmT*MT/(KmT+MT)-kd*MT,
        ksT*MT-t01+t10-kd*T0,
        t01-t10-t12+t21-kd*T1,
        t12-t21-bind-vdT*T2/(KdT+T2)-kd*T2,
        bind-k1*C+k2*CN-kdC*C,
        k1*C-k2*CN-kdN*CN,
    ])


@njit(cache=True)
def _valid(y):
    return np.all(np.isfinite(y)) and np.all(y >= 0)


@njit(cache=True)
def _integrate(initial, first_tick, steps, dt, p, period_ticks, light_ticks, phase_ticks, light_vdT):
    y = initial.copy()
    for tick in range(first_tick, first_tick+steps):
        light = period_ticks > 0 and (tick-phase_ticks) % period_ticks < light_ticks
        vdT = light_vdT if light else p[9]
        # Light switches are clock-aligned. All stages use the coefficient on
        # this interval, including k4 at its endpoint (the left-hand limit).
        a = _rhs(y, p, vdT)
        stage = y+.5*dt*a
        if not _valid(stage):
            raise FloatingPointError("Invalid circadian RK4 stage; reduce step_h or inspect parameters")
        b = _rhs(stage, p, vdT)
        stage = y+.5*dt*b
        if not _valid(stage):
            raise FloatingPointError("Invalid circadian RK4 stage; reduce step_h or inspect parameters")
        c = _rhs(stage, p, vdT)
        stage = y+dt*c
        if not _valid(stage):
            raise FloatingPointError("Invalid circadian RK4 stage; reduce step_h or inspect parameters")
        d = _rhs(stage, p, vdT)
        y += dt/6*(a+2*b+2*c+d)
        if not _valid(y):
            raise FloatingPointError("Invalid circadian state; no clipping is applied")
    return y


def _state(value):
    array = np.asarray(value)
    if array.shape != (10,) or array.dtype.kind not in "fiu":
        raise ValueError("Circadian state must contain10 real concentrations in declared order")
    if any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
        raise ValueError("Circadian concentrations cannot be boolean")
    array = np.asarray(array, dtype=np.float64)
    if not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError("Circadian concentrations must be finite and nonnegative")
    return array.copy()


class CircadianClock:
    """Fixed-step RK4 with an explicit biological-hour clock and no wall clock.

    Initial concentrations default to0.1nM for all ten states, an analyst choice
    because Figure2/4 captions do not specify their initial phase. No phase fit.
    Advance and light transitions must align with step_h. Failed integration is
    atomic: neither state nor clock advances, and no negative value is clipped.
    """
    def __init__(self, parameters=None, *, step_h=.01, initial_state=None, light_schedule=None):
        self._parameters = parameters if parameters is not None else LG1998Parameters()
        if not isinstance(self.parameters, LG1998Parameters):
            raise ValueError("Expected LG1998Parameters")
        if light_schedule is not None and not isinstance(light_schedule, LightDarkSchedule):
            raise ValueError("Expected LightDarkSchedule or None for continuous darkness")
        self._step_h = _real(step_h, "step_h", positive=True)
        self._light_schedule = light_schedule
        self._p = np.array(list(asdict(self.parameters).values()), dtype=np.float64)
        self._initial = _state(np.full(10, .1) if initial_state is None else initial_state)
        self._period_ticks = self._light_ticks = self._phase_ticks = 0
        if light_schedule is not None:
            self._period_ticks = self._steps(light_schedule.period_h)
            self._light_ticks = self._steps(light_schedule.light_h)
            self._phase_ticks = self._steps(light_schedule.phase_h)
        self.reset()

    def _steps(self, hours):
        hours = _real(hours, "biological hours")
        quotient = hours/self.step_h
        if not math.isfinite(quotient) or quotient > np.iinfo(np.int64).max:
            raise ValueError("Circadian clock interval is too large")
        steps = round(quotient)
        if not math.isclose(quotient, steps, rel_tol=0, abs_tol=1e-9) or (hours > 0 and steps == 0):
            raise ValueError("Biological-hour interval must align with step_h")
        return steps

    @property
    def parameters(self):
        return self._parameters

    @property
    def step_h(self):
        return self._step_h

    @property
    def light_schedule(self):
        return self._light_schedule

    @property
    def tick(self):
        return self._tick

    @property
    def time_h(self):
        return self.tick*self.step_h

    @property
    def concentrations_nm(self):
        return self._y.copy()

    def is_light(self):
        return bool(self._period_ticks and (self.tick-self._phase_ticks) % self._period_ticks < self._light_ticks)

    def snapshot(self):
        concentrations = dict(zip(STATE_ORDER, self._y.tolist()))
        concentrations["PER_total"] = float(self._y[1:4].sum()+self._y[8:10].sum())
        concentrations["TIM_total"] = float(self._y[5:8].sum()+self._y[8:10].sum())
        return {"biological_time_h": self.time_h, "light": self.is_light(),
                "concentrations_tentative_nm": concentrations,
                "tim_degradation_nm_per_h": self.light_schedule.light_vdT if self.is_light() else self.parameters.vdT}

    def advance_hours(self, hours):
        steps = self._steps(hours)
        if self.tick+steps > np.iinfo(np.int64).max:
            raise ValueError("Circadian clock overflow")
        result = _integrate(self._y, self.tick, steps, self.step_h, self._p,
            self._period_ticks, self._light_ticks, self._phase_ticks,
            self.light_schedule.light_vdT if self.light_schedule else 0.)
        self._y, self._tick = result, self.tick+steps
        return self.snapshot()

    def reset(self):
        self._y = self._initial.copy()
        self._tick = 0

    def _metadata(self):
        return {"version": 1, "model": MODEL_ID, "solver": "fixed-step-rk4-v1",
            "time_unit": "biological_hours", "concentration_unit": "tentative_nM",
            "state_order": list(STATE_ORDER), "step_h": self.step_h,
            "parameters": asdict(self.parameters), "initial_state": self._initial.tolist(),
            "light_schedule": asdict(self.light_schedule) if self.light_schedule else None}

    def state_dict(self):
        return {**self._metadata(), "tick": self.tick, "state": self._y.tolist()}

    def load_state_dict(self, state):
        if not isinstance(state, dict):
            raise ValueError("Expected circadian checkpoint dictionary")
        if any(type(state.get(k)) is not type(v) or state.get(k) != v for k,v in self._metadata().items()):
            raise ValueError("Circadian checkpoint metadata, parameters, units or initial state differ")
        expected = json.dumps(self._metadata(), sort_keys=True, allow_nan=False)
        actual = json.dumps({k: state.get(k) for k in self._metadata()}, sort_keys=True, allow_nan=False)
        if actual != expected:
            raise ValueError("Circadian checkpoint metadata value types differ")
        tick = state.get("tick")
        if isinstance(tick, bool) or not isinstance(tick, int) or not 0 <= tick <= np.iinfo(np.int64).max:
            raise ValueError("Invalid circadian checkpoint tick")
        y = _state(state.get("state"))
        self._y, self._tick = y, tick

    def save_checkpoint(self, path):
        Path(path).write_text(json.dumps(self.state_dict(), indent=2, allow_nan=False)+"\n")

    def load_checkpoint(self, path):
        self.load_state_dict(json.loads(Path(path).read_text()))
