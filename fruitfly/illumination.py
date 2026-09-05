"""Explicit optional world illumination, in dimensionless renderer units.

One world-attached directional light replaces camera headlights only when
requested. Coefficients and direction are engineering choices, not measured
irradiance, fly spectral sensitivities or neural stimulus gains. The existing
background/skybox is not scaled by these light coefficients.
"""
from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np


LIGHT_NAME = "engineering_world_illumination"


@dataclass(frozen=True)
class WorldIlluminationConfig:
    """Light travels along direction_world; RGB coefficients are dimensionless.

    Diffuse-only material illumination plus ambient fill, with zero specular
    light, makes this mode's brightness independent of which camera acquires a
    view. Geometry may still occlude the view or cast world-relative shadows.
    """

    direction_world: tuple[float, float, float] = (.3, -.2, -1.)
    # Directional illumination has no inverse-square attenuation. Its position
    # still anchors MuJoCo's shadow projection, so keep it above the arena.
    # Coordinates use model length units (millimetres for BodyRuntime).
    position_world: tuple[float, float, float] = (-6., 4., 20.)
    ambient_rgb: tuple[float, float, float] = (.1, .1, .1)
    diffuse_rgb: tuple[float, float, float] = (.65, .65, .65)
    cast_shadows: bool = True

    def __post_init__(self):
        for name in ("direction_world", "position_world", "ambient_rgb", "diffuse_rgb"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (3,) or not np.isfinite(value).all():
                raise ValueError(f"{name} must have three finite values")
            if name in ("ambient_rgb", "diffuse_rgb") and (np.any(value < 0) or np.any(value > 1)):
                raise ValueError(f"{name} coefficients must be in [0,1]")
            object.__setattr__(self, name, tuple(float(v) for v in value))
        if not np.isfinite(np.linalg.norm(self.direction_world)) or np.linalg.norm(self.direction_world) <= 1e-12:
            raise ValueError("direction_world must be nonzero")
        if not isinstance(self.cast_shadows, bool):
            raise ValueError("cast_shadows must be a boolean")


def add_world_illumination(spec: mujoco.MjSpec, config: WorldIlluminationConfig):
    """Before compilation, add one fixed world light and disable headlight.

    The caller opts in by invoking this function. No geom, body, joint,
    actuator, camera, texture, timestep or dynamics parameter is changed.
    Existing world lights are not rewritten. Duplicate installation is rejected.
    """
    if not isinstance(config, WorldIlluminationConfig):
        raise TypeError("config must be WorldIlluminationConfig")
    if any(light.name == LIGHT_NAME for light in spec.lights):
        raise ValueError("World illumination was already installed")
    direction = np.asarray(config.direction_world)
    direction /= np.linalg.norm(direction)
    light = spec.worldbody.add_light(name=LIGHT_NAME, pos=config.position_world,
        dir=direction, mode=mujoco.mjtCamLight.mjCAMLIGHT_FIXED,
        type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL, active=True,
        castshadow=config.cast_shadows, ambient=config.ambient_rgb,
        diffuse=config.diffuse_rgb, specular=(0., 0., 0.))
    spec.visual.headlight.active = 0
    spec.visual.headlight.ambient[:] = 0
    spec.visual.headlight.diffuse[:] = 0
    spec.visual.headlight.specular[:] = 0
    return light


def illumination_snapshot(model, config: WorldIlluminationConfig | None, gain: float):
    """Privileged rendering provenance for snapshots/viewers, not brain input."""
    return {
        "mode": "fixed_world_directional" if config is not None else "legacy_camera_headlight",
        "world_light_count": int(model.nlight),
        "camera_headlight_active": bool(model.vis.headlight.active),
        "light_stimulus_gain": float(gain),
        "world_ambient_rgb": model.light_ambient.tolist(),
        "world_diffuse_rgb": model.light_diffuse.tolist(),
        "coefficient_units": "dimensionless renderer RGB; no biological radiometry",
        "background_scaled_by_light_gain": False,
    }
