"""Local airflow geometry, before antennal mechanics or neural transduction.

Head axes are forward, left, up. Paper azimuth is the direction air comes
FROM: negative on the fly's left, positive on its right, zero anterior.
No food/source coordinates or motor commands enter this calculation.
"""
from __future__ import annotations

import numpy as np


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
