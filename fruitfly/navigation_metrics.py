"""Observational navigation metrics. No anatomy lookup, encoders or motor control.

Spike and exposure intervals are half-open [start, end) in integer ticks. Body
measurements use world XY in mm, seconds, and counterclockwise yaw in radians.
Undefined rates/geometry remain NaN with explicit validity/status metadata.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import numpy as np


def _integers(values, name, *, unique=False):
    a = np.asarray(values)
    if a.ndim != 1 or (a.size and a.dtype.kind not in 'iu'):
        raise ValueError(f'{name} must be a one-dimensional integer sequence')
    if a.size and (np.any(a < 0) or np.any(a > np.iinfo(np.int64).max)):
        raise ValueError(f'{name} must contain nonnegative int64-range values')
    a = a.astype(np.int64, copy=True)
    if unique and len(np.unique(a)) != len(a):
        raise ValueError(f'{name} must not contain duplicate indices')
    return a


def _interval(value, name):
    a = _integers(value, name)
    if a.shape != (2,) or a[1] <= a[0]:
        raise ValueError(f'{name} must be two strictly increasing ticks')
    return int(a[0]), int(a[1])


def spike_activity(spike_ticks, spike_indices, cohorts, bin_edges_ticks, *,
                   dt_s, observed_interval_ticks, windows=None):
    """Count actual emitted spikes for arbitrary named, possibly overlapping cohorts.

    `cohorts` maps names to ordered unique graph indices, or None if unresolved.
    An empty index list is explicitly mapped-but-empty. `windows` optionally maps
    names (e.g. odor_ON/odor_OFF) to tick pairs, independent of bin boundaries.
    `observed_interval_ticks` declares a continuous, completely recorded interval;
    all supplied spikes must lie in it. Inputs must be ordered by spike tick.

    Per-cohort `observed_counts` always describe the observed intersection, never
    an extrapolated full window. `complete` identifies full requested coverage;
    rates are NaN otherwise. Zero spikes in a complete, mapped window is zero.
    Missing cohorts have None counts/rates rather than silent empty substitutes.
    """
    ticks = _integers(spike_ticks, 'spike_ticks')
    indices = _integers(spike_indices, 'spike_indices')
    edges = _integers(bin_edges_ticks, 'bin_edges_ticks')
    if ticks.shape != indices.shape or np.any(ticks[1:] < ticks[:-1]):
        raise ValueError('Spikes must have equal-length, time-ordered tick/index arrays')
    if len(edges) < 2 or np.any(edges[1:] <= edges[:-1]):
        raise ValueError('bin_edges_ticks must be strictly increasing, with at least two edges')
    if not math.isfinite(dt_s) or dt_s <= 0:
        raise ValueError('dt_s must be finite and positive')
    start, end = _interval(observed_interval_ticks, 'observed_interval_ticks')
    if len(ticks) and (ticks[0] < start or ticks[-1] >= end):
        raise ValueError('Spikes outside the declared observed interval')
    if not isinstance(cohorts, Mapping) or not all(isinstance(k, str) and k for k in cohorts):
        raise ValueError('cohorts must map nonempty names to indices or None')
    groups = {name: None if value is None else _integers(value, name, unique=True)
              for name, value in cohorts.items()}
    windows = {} if windows is None else windows
    if not isinstance(windows, Mapping) or not all(isinstance(k, str) and k for k in windows):
        raise ValueError('windows must map nonempty names to tick intervals')
    named = {name: _interval(value, name) for name, value in windows.items()}
    union = np.unique(np.concatenate([v for v in groups.values() if v is not None])) if any(v is not None for v in groups.values()) else np.empty(0, np.int64)

    def measure(intervals):
        bounds = np.asarray(intervals, np.int64).reshape(-1, 2)
        duration = (bounds[:, 1] - bounds[:, 0]) * dt_s
        exposure = np.maximum(0, np.minimum(bounds[:, 1], end) - np.maximum(bounds[:, 0], start)) * dt_s
        complete = (bounds[:, 0] >= start) & (bounds[:, 1] <= end)
        status = np.where(complete, 'complete', np.where(exposure > 0, 'partial', 'unobserved'))
        counts = np.zeros((len(bounds), len(union)), np.int64)
        for row, (a, b) in enumerate(bounds):
            lo, hi = np.searchsorted(ticks, [a, b], side='left')
            cell = indices[lo:hi]
            if len(union) and len(cell):
                column = np.searchsorted(union, cell)
                inside = column < len(union)
                inside[inside] &= union[column[inside]] == cell[inside]
                counts[row] = np.bincount(column[inside], minlength=len(union))
        output = {}
        for name, idx in groups.items():
            if idx is None:
                output[name] = dict(status='missing_annotation', indices=None, observed_counts=None,
                    per_neuron_rate_hz=None, observed_population_counts=None, mean_cell_rate_hz=None)
                continue
            c = counts[:, np.searchsorted(union, idx)].copy()
            rates = np.full(c.shape, np.nan)
            rates[complete] = c[complete] / duration[complete, None]
            mean = np.full(len(bounds), np.nan)
            if len(idx):
                mean[complete] = rates[complete].mean(axis=1)
            output[name] = dict(status='mapped' if len(idx) else 'empty_cohort', indices=idx.copy(),
                observed_counts=c, per_neuron_rate_hz=rates, observed_population_counts=c.sum(axis=1),
                mean_cell_rate_hz=mean)
        return dict(intervals_ticks=bounds, duration_s=duration, observed_duration_s=exposure,
                    complete=complete, status=status, cohorts=output)

    return dict(dt_s=float(dt_s), observed_interval_ticks=(start, end),
        bins=measure(list(zip(edges[:-1], edges[1:]))), window_names=list(named),
        windows=measure(list(named.values())),
        counting='actual supplied spike events; overlapping cohorts/windows are not disjoint totals')


def planar_kinematics(times_s, positions_mm, yaw_rad, *, local_airflow_world_mm_s=None,
                      speed_floor_mm_s=0.1, wind_floor_mm_s=1e-12):
    """Return N-1 interval metrics from N poses; no resampling or hidden smoothing.

    positions_mm is (N,2) or (N,3); Z is deliberately excluded. Wind, when given,
    is (N-1,2) or (N-1,3), sampled physical AIR velocity in world coordinates,
    not air minus body/sensor velocity. Upwind = -horizontal air velocity.
    Heading is the circular interval midpoint. Yaw differences use the shortest
    arc; exact half-turn intervals have ambiguous yaw/forward metrics (NaN).
    Sampling must resolve changes smaller than pi; full turns cannot be recovered.
    Curvature is signed yaw-rate/planar speed (heading curvature), not curvature
    of the translation path when the body sidesteps or walks backward. Separate
    path-turn metrics have N-2 samples between adjacent velocity midpoints: turn
    angle divided by elapsed midpoint time or mean neighboring chord length.
    Both chords must meet the speed floor; a half-turn path reversal is undefined.
    """
    t = np.asarray(times_s, float); p = np.asarray(positions_mm, float); yaw = np.asarray(yaw_rad, float)
    if (t.ndim != 1 or len(t) < 2 or p.ndim != 2 or p.shape[0] != len(t)
            or p.shape[1] not in (2, 3) or yaw.shape != t.shape
            or not np.isfinite(t).all() or not np.isfinite(p).all() or not np.isfinite(yaw).all()
            or np.any(np.diff(t) <= 0)):
        raise ValueError('Require finite N times/poses/yaws, increasing times, positions (N,2|3), N>=2')
    if not math.isfinite(speed_floor_mm_s) or speed_floor_mm_s <= 0:
        raise ValueError('speed_floor_mm_s must be positive and finite')
    if not math.isfinite(wind_floor_mm_s) or wind_floor_mm_s < 0:
        raise ValueError('wind_floor_mm_s must be nonnegative and finite')
    dt = np.diff(t); velocity = np.diff(p[:, :2], axis=0) / dt[:, None]
    delta = np.arctan2(np.sin(np.diff(yaw)), np.cos(np.diff(yaw)))
    yaw_valid = ~np.isclose(np.abs(delta), np.pi, rtol=0, atol=1e-12)
    delta[~yaw_valid] = np.nan
    heading = yaw[:-1] + delta / 2
    unit = np.column_stack([np.cos(heading), np.sin(heading)])
    speed = np.linalg.norm(velocity, axis=1); omega = delta / dt
    forward = np.sum(velocity * unit, axis=1)
    lateral = velocity[:, 1] * unit[:, 0] - velocity[:, 0] * unit[:, 1]
    curvature_valid = (speed >= speed_floor_mm_s) & yaw_valid
    curvature = np.full(len(dt), np.nan); curvature[curvature_valid] = omega[curvature_valid] / speed[curvature_valid]
    upwind = np.full_like(velocity, np.nan); wind_valid = np.zeros(len(dt), bool)
    wind_status = np.full(len(dt), 'missing_airflow', dtype='<U20')
    if local_airflow_world_mm_s is not None:
        air = np.asarray(local_airflow_world_mm_s, float)
        if air.ndim != 2 or air.shape[0] != len(dt) or air.shape[1] not in (2, 3) or not np.isfinite(air).all():
            raise ValueError('Airflow must contain finite (N-1,2|3) interval world air velocities')
        magnitude = np.linalg.norm(air[:, :2], axis=1)
        wind_valid = magnitude > wind_floor_mm_s
        wind_status[:] = 'below_wind_floor'; wind_status[wind_valid] = 'defined'
        upwind[wind_valid] = -air[wind_valid, :2] / magnitude[wind_valid, None]
    midpoint = t[:-1] + dt / 2
    path_heading = np.arctan2(velocity[:, 1], velocity[:, 0])
    path_delta = np.arctan2(np.sin(np.diff(path_heading)), np.cos(np.diff(path_heading)))
    path_valid = ((speed[:-1] >= speed_floor_mm_s) & (speed[1:] >= speed_floor_mm_s)
                  & ~np.isclose(np.abs(path_delta), np.pi, rtol=0, atol=1e-12))
    path_delta[~path_valid] = np.nan
    path_turn_rate = path_delta / np.diff(midpoint)
    # Distance between the two chord midpoints measured along the polygonal path.
    path_distance = (speed[:-1] * dt[:-1] + speed[1:] * dt[1:]) / 2
    path_curvature = np.full(len(path_delta), np.nan)
    path_curvature[path_valid] = path_delta[path_valid] / path_distance[path_valid]
    cosine = np.sum(unit * upwind, axis=1)
    cross = unit[:, 0] * upwind[:, 1] - unit[:, 1] * upwind[:, 0]
    heading_error = np.arctan2(cross, cosine)
    # At exact opposition, left versus right is not determined by the vectors.
    error_valid = wind_valid & yaw_valid & ~np.isclose(np.abs(heading_error), np.pi, rtol=0, atol=1e-12)
    heading_error[~error_valid] = np.nan
    return dict(interval_start_s=t[:-1].copy(), interval_end_s=t[1:].copy(), interval_midpoint_s=t[:-1]+dt/2,
        duration_s=dt, velocity_world_xy_mm_s=velocity, speed_mm_s=speed,
        forward_mm_s=forward, lateral_mm_s=lateral, yaw_rate_rad_s=omega, yaw_valid=yaw_valid,
        heading_curvature_rad_per_mm=curvature, curvature_valid=curvature_valid,
        path_interval_start_s=midpoint[:-1], path_interval_end_s=midpoint[1:],
        path_turn_rate_rad_s=path_turn_rate, path_curvature_rad_per_mm=path_curvature, path_valid=path_valid,
        below_speed_floor=speed < speed_floor_mm_s, speed_floor_mm_s=float(speed_floor_mm_s),
        upwind_unit_world_xy=upwind, wind_valid=wind_valid, wind_status=wind_status,
        wind_floor_mm_s=float(wind_floor_mm_s), upwind_projection_mm_s=np.sum(velocity*upwind, axis=1),
        upwind_heading_cosine=cosine, upwind_heading_error_rad=heading_error,
        upwind_heading_error_valid=error_valid,
        convention='XY; positive yaw is counterclockwise; upwind opposes physical world air velocity')


def circular_activity(weights, indices, *, angles_rad=None, coordinate_label=None):
    """Descriptive first circular moment only with explicit cell coordinates.

    weights is (..., cells), finite nonnegative counts or rates, with ordered
    unique graph indices. angles_rad maps graph index to a caller-supplied angle.
    Missing coordinates stop the calculation; there is no anatomical angle
    inference or partial-cell normalization. A moment is NOT a detected FB bump.
    Repeated/uneven coordinates can bias the moment; their sampling must be
    assessed separately. Silent/empty rows have undefined phase and resultant.
    """
    idx = _integers(indices, 'indices', unique=True); w = np.asarray(weights, float)
    if w.ndim < 1 or w.shape[-1] != len(idx) or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError('weights must be finite nonnegative (...,cells) aligned with indices')
    if angles_rad is not None and not isinstance(angles_rad, Mapping):
        raise ValueError('angles_rad must explicitly map graph indices to radians')
    missing = idx.copy() if angles_rad is None else np.array([i for i in idx if int(i) not in angles_rad], np.int64)
    base = dict(indices=idx, missing_coordinate_indices=missing, coordinate_label=coordinate_label,
        phase_rad=None, resultant_length=None, activity_present=None, interpretation='first circular moment; not bump detection or biological localization')
    if angles_rad is None or len(missing):
        return dict(base, status='missing_coordinates' if angles_rad is None else 'incomplete_coordinates')
    if not isinstance(coordinate_label, str) or not coordinate_label.strip():
        raise ValueError('Explicit coordinate_label/provenance is required')
    angles = np.array([angles_rad[int(i)] for i in idx], float)
    if not np.isfinite(angles).all():
        raise ValueError('Supplied angles must be finite radians')
    total = w.sum(axis=-1); active = total > 0
    moment = np.sum(w * np.exp(1j * angles), axis=-1)
    resultant = np.full(total.shape, np.nan); np.divide(np.abs(moment), total, out=resultant, where=active)
    # A cancelling first moment has no preferred angle even if activity exists.
    phase = np.where(active & (resultant > 1e-12), np.angle(moment), np.nan)
    return dict(base, status='descriptive_moment' if len(idx) else 'empty_cohort',
        phase_rad=phase, resultant_length=resultant, activity_present=active, angles_rad=angles)
