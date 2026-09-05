"""Local airflow geometry, before antennal mechanics or neural transduction.

Head axes are forward, left, up. Paper azimuth is the direction air comes
FROM: negative on the fly's left, positive on its right, zero anterior.
No food/source coordinates or motor commands enter this calculation.
"""
from __future__ import annotations

import numpy as np
import hashlib
import json
from pathlib import Path


_ARCHIVE_SHA256 = "4812e1f0a5d905b9269a40dc91a4894673c9a7ac1ca4591246adc07b61ac37e6"
# Independently computed from the checksum-verified deposited MAT files. The
# first fingerprint encodes source angles, 17 paired fly rows and experiment
# IDs; the second encodes six probe-placement x five-direction final-1s means,
# rounded to 1e-9 cm/s solely to tolerate floating-point summation differences.
_PAIRED_OBSERVATIONS_SHA256 = "605b8ea5ba6899cb329713cef4f350fa684c67bd931888b430ec0c3ec219e029"
_ANEMOMETER_WINDOW_SHA256 = "8f577aabf74f815f8fd5ac8fd8abdda84f91fa1094482b9958c970535c093ace"


def _validate_primary_reference(source):
    """Check fixed primary observations and recompute derived parameters.

    Notes may change without invalidating the artifact. Observations, basis,
    angle order, nominal-speed window and fitted numbers may not silently drift.
    """
    try:
        if not isinstance(source, dict):
            raise ValueError("Expected a primary calibration JSON object")
        if (source.get("raw_measurements_available") is not True
                or source.get("status") != "fitted_from_primary_mat_not_runtime_validated"
                or source.get("dataset_doi") != "10.5061/dryad.k06kh8f"
                or source.get("license") != "CC0-1.0"
                or source.get("archive_sha256") != _ARCHIVE_SHA256
                or source.get("archive_md5") != "e1ff6c0c61077b7777ccd83395f92477"
                or source.get("archive_bytes") != 9477291049):
            raise ValueError("Expected the verified primary Suver 2019 calibration record")
        angles = np.asarray(source["wind_angle_deg"], dtype="<f8")
        measured = source["per_fly_measurements"]
        ordered_angles = np.asarray(measured["angle_order_deg"], dtype="<f8")
        left = np.asarray(measured["left_deg"], dtype="<f8", order="C")
        right = np.asarray(measured["right_deg"], dtype="<f8", order="C")
        experiment_ids = measured["experiment_ids"]
        if (not np.array_equal(angles, [-90, -45, 0, 45, 90])
                or not np.array_equal(ordered_angles, angles)
                or left.shape != (17, 5) or right.shape != (17, 5)
                or not np.isfinite(left).all() or not np.isfinite(right).all()
                or len(experiment_ids) != 17 or not all(isinstance(v, str) for v in experiment_ids)):
            raise ValueError("Invalid primary paired antenna observation schema")
        canonical = (b"Suver2019-paired-arista-v1\0" + angles.tobytes()
                     + left.tobytes() + right.tobytes()
                     + json.dumps(experiment_ids, separators=(",", ":"), ensure_ascii=True).encode())
        if hashlib.sha256(canonical).hexdigest() != _PAIRED_OBSERVATIONS_SHA256:
            raise ValueError("Primary paired antenna observations have changed")
        basis = np.column_stack([np.ones(5), np.cos(np.deg2rad(angles)), np.sin(np.deg2rad(angles))])
        coefficients = []
        for side, observations in (("left", left), ("right", right)):
            curve = source["curves"][side]
            if curve["basis"] != ["1", "cos(wind_angle_rad)", "sin(wind_angle_rad)"]:
                raise ValueError("Antenna coefficient basis or angular units changed")
            supplied = np.asarray(curve["coefficients"], dtype=float)
            expected = np.linalg.lstsq(basis, observations.mean(axis=0), rcond=None)[0]
            if supplied.shape != (3,) or not np.allclose(supplied, expected, atol=1e-10, rtol=0):
                raise ValueError("Antenna coefficients do not reproduce the primary observations")
            coefficients.append(expected)
        anemometer = source["anemometer"]
        window_means = np.asarray(anemometer["per_mount_per_direction_cm_s"], dtype="<f8", order="C")
        if (window_means.shape != (6, 5) or not np.isfinite(window_means).all()
                or hashlib.sha256(np.asarray(np.round(window_means, 9), dtype="<f8", order="C").tobytes()).hexdigest() != _ANEMOMETER_WINDOW_SHA256
                or anemometer["analysis_window_s_from_trial_start"] != [4.0, 5.0]
                or anemometer["units"] != "cm/s"):
            raise ValueError("Primary anemometer window or units changed")
        nominal_speed_mm_s = float(window_means.mean()) * 10
        if (not np.isclose(float(source["velocity_m_s"]) * 1000, nominal_speed_mm_s, atol=1e-9, rtol=0)
                or not np.array_equal(source["valid_angle_domain_deg"], [-90, 90])):
            raise ValueError("Derived wind speed or measured angular domain changed")
        return np.asarray(coefficients), nominal_speed_mm_s, np.asarray([-90., 90.])
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("Incomplete or invalid primary calibration schema") from error


def local_airflow(air_world_mm_s, sensor_velocity_world_mm_s, head_to_world):
    """Return relative air vectors and source azimuth for two antenna sensors.

    Near-zero horizontal flow has no defined azimuth and returns None. The
    3-D vectors retain vertical flow; the azimuth alone is a planar summary.
    This is rigid-body geometry, not a calibrated antennal response function.
    """
    air = np.asarray(air_world_mm_s, dtype=float)
    sensor = np.asarray(sensor_velocity_world_mm_s, dtype=float)
    rotation = np.asarray(head_to_world, dtype=float)
    if air.shape != (3,) or sensor.shape != (2, 3) or rotation.shape != (3, 3):
        raise ValueError("Expected air (3,), two sensor velocities (2,3), rotation (3,3)")
    if not all(np.isfinite(x).all() for x in (air, sensor, rotation)):
        raise ValueError("Airflow geometry must be finite")
    if (not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8, rtol=0)
            or not np.isclose(np.linalg.det(rotation), 1, atol=1e-8, rtol=0)):
        raise ValueError("Head orientation must be a proper rotation")
    relative = (air - sensor) @ rotation
    horizontal = np.linalg.norm(relative[:, :2], axis=1)
    # atan2(-source_y, source_x), where source = -relative air velocity.
    azimuth = [float(np.degrees(np.arctan2(v[1], -v[0]))) if speed > 1e-9 else None
               for v, speed in zip(relative, horizontal)]
    return {"relative_velocity_head_mm_s": relative.tolist(),
            "horizontal_speed_mm_s": horizontal.tolist(),
            "source_azimuth_deg": azimuth,
            "antenna_order": ["L", "R"],
            "head_axes": ["forward", "left", "up"]}


class MeasuredAntennaReference:
    """Quasistatic empirical reference, never a spike-rate or joint command.

    The tolerance gates are explicit engineering assay tolerances. They are
    not confidence intervals or experimentally validated speed/elevation laws.
    Outside them the estimate is unavailable, not extrapolated or set to zero.
    """

    def __init__(self, path, *, intended_sex, allow_sex_transfer=False,
                 speed_tolerance_fraction=.05, elevation_tolerance_deg=5.):
        if type(allow_sex_transfer) is not bool:
            raise ValueError("allow_sex_transfer must be an explicit boolean")
        if intended_sex not in ("male", "female"):
            raise ValueError("Intended sex must be explicit")
        if intended_sex != "female" and not allow_sex_transfer:
            raise ValueError("The measured antenna curve is female; sex transfer must be explicit")
        if (not np.isfinite(speed_tolerance_fraction) or not 0 <= speed_tolerance_fraction <= .1
                or not np.isfinite(elevation_tolerance_deg) or not 0 <= elevation_tolerance_deg <= 10):
            raise ValueError("Reference tolerances must be finite and narrow")
        content = Path(path).read_bytes()
        source = json.loads(content)
        self.coefficients, self.nominal_speed_mm_s, self.domain = _validate_primary_reference(source)
        self.speed_tolerance_fraction = speed_tolerance_fraction
        self.elevation_tolerance_deg = elevation_tolerance_deg
        self.provenance = {"source_file_sha256": hashlib.sha256(content).hexdigest(),
            "dataset_doi": source["dataset_doi"], "archive_sha256": source["archive_sha256"],
            "paired_observations_sha256": _PAIRED_OBSERVATIONS_SHA256,
            "anemometer_window_sha256": _ANEMOMETER_WINDOW_SHA256,
            "nominal_speed_mm_s": self.nominal_speed_mm_s,
            "speed_basis": source["velocity_basis"],
            "intended_sex": intended_sex, "measured_sex": "female",
            "allow_sex_transfer": allow_sex_transfer,
            "male_transfer_validated": False, "speed_scaling_validated": False,
            "speed_tolerance_fraction": speed_tolerance_fraction,
            "elevation_tolerance_deg": elevation_tolerance_deg,
            "role": "quasistatic empirical reference; no joint actuation or neural transduction"}

    def evaluate(self, wind):
        vectors = np.asarray(wind["relative_velocity_head_mm_s"], dtype=float)
        if vectors.shape != (2, 3) or not np.isfinite(vectors).all():
            raise ValueError("Expected two finite head-frame air velocities")
        horizontal = np.linalg.norm(vectors[:, :2], axis=1)
        angles = np.degrees(np.arctan2(vectors[:, 1], -vectors[:, 0]))
        elevations = np.degrees(np.arctan2(np.abs(vectors[:, 2]), horizontal))
        estimates, exclusions = [], []
        for index, (angle, speed, elevation) in enumerate(zip(angles, horizontal, elevations)):
            reasons = []
            if speed <= 1e-9:
                reasons.append("undefined_horizontal_direction")
            if not self.domain[0] <= angle <= self.domain[1]:
                reasons.append("outside_measured_azimuths")
            if abs(speed / self.nominal_speed_mm_s - 1) > self.speed_tolerance_fraction + 1e-12:
                reasons.append("outside_declared_speed_tolerance")
            if elevation > self.elevation_tolerance_deg + 1e-12:
                reasons.append("outside_declared_elevation_tolerance")
            theta = np.deg2rad(angle)
            estimates.append(None if reasons else float(self.coefficients[index]
                             @ np.array([1, np.cos(theta), np.sin(theta)])))
            exclusions.append(reasons)
        return {"estimated_steady_arista_deflection_deg": estimates,
                "excluded_because": exclusions,
                "sign_convention": "negative headward, positive away",
                "interpretation": "female-derived reference; not measured male mechanics or neural input"}
