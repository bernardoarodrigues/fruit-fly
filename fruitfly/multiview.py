"""Isolated head-frame cube acquisition; no retinal or neural transfer model.

Directions are unit vectors in x-forward/y-left/z-up head coordinates. Six
90-degree cores have one guard pixel on every edge. Bilinear RGB interpolation
uses their finite raster pixels: it is an approximation to a point query, not a
measured ommatidial acceptance kernel. Invalid source rows remain present, with
NaN samples, face/index -1 and zero weights. No nearest-facet substitution.
"""
from __future__ import annotations

from dataclasses import dataclass

import mujoco
import numpy as np


FACE_NAMES = ("+x", "-x", "+y", "-y", "+z", "-z")
FORWARD_HEAD = np.array(((1, 0, 0), (-1, 0, 0), (0, 1, 0),
                         (0, -1, 0), (0, 0, 1), (0, 0, -1)), dtype=float)
UP_HEAD = np.array(((0, 0, 1),) * 4 + ((0, 1, 0),) * 2, dtype=float)
RIGHT_HEAD = np.cross(FORWARD_HEAD, UP_HEAD)


def _rotation(value):
    value = np.asarray(value, dtype=float)
    if (value.shape != (3, 3) or not np.isfinite(value).all()
            or not np.allclose(value.T @ value, np.eye(3), atol=1e-8, rtol=0)
            or not np.isclose(np.linalg.det(value), 1, atol=1e-8, rtol=0)):
        raise ValueError("head_to_world must be a finite proper rotation")
    return value.copy()


@dataclass(frozen=True)
class EyePose:
    """Single shared eye origin in model length units; no lens-specific parallax."""

    origin_world: np.ndarray
    head_to_world: np.ndarray

    def __post_init__(self):
        origin = np.asarray(self.origin_world, dtype=float)
        if origin.shape != (3,) or not np.isfinite(origin).all():
            raise ValueError("origin_world must be a finite three-vector")
        object.__setattr__(self, "origin_world", origin.copy())
        object.__setattr__(self, "head_to_world", _rotation(self.head_to_world))


def eye_pose_from_body(body, side="R"):
    """Read current compiled FlyGym camera origin and BodyRuntime head basis.

    Requires vision-enabled body and current MuJoCo forward kinematics; never
    advances or modifies the body. This is an explicit adapter to the audited
    BodyRuntime private fields, not an independent anatomical registration.
    """
    if side not in ("L", "R"):
        raise ValueError("side must be L or R")
    ids = body.sim._intern_eye_camera_ids_by_fly.get(body.fly.name, ())
    if len(ids) != 2 or min(ids) < 0:
        raise ValueError("body must expose both compiled eye cameras")
    camera_id = int(ids[("L", "R").index(side)])
    return EyePose(body.data.cam_xpos[camera_id],
                   body.data.geom_xmat[body._head_geom_id].reshape(3, 3)
                   @ body._head_anatomical_basis)


@dataclass(frozen=True)
class CubeMapping:
    directions_head: np.ndarray
    valid: np.ndarray
    face: np.ndarray
    pixel_rows: np.ndarray
    pixel_cols: np.ndarray
    weights: np.ndarray
    core_resolution: int

    @property
    def image_size(self):
        return self.core_resolution + 2

    @property
    def fovy_deg(self):
        return float(np.degrees(2*np.arctan(self.image_size/self.core_resolution)))

    def sample(self, faces):
        """Bilinear numeric samples with source order retained; no channel gain.

        Input (6,H,H[,channels...]); output (sources[,channels...]), float64.
        Do not interpolate object-ID segmentation images; convert IDs to masks
        first when using this function in a geometry diagnostic.
        """
        faces = np.asarray(faces)
        if faces.shape[:3] != (6, self.image_size, self.image_size):
            raise ValueError("cube image dimensions do not match the mapping")
        if not np.issubdtype(faces.dtype, np.number):
            raise ValueError("cube images must contain numeric values")
        output = np.full((len(self.valid),) + faces.shape[3:], np.nan)
        v = self.valid
        pixels = faces[self.face[v, None], self.pixel_rows[v], self.pixel_cols[v]]
        weights = self.weights[v].reshape((v.sum(), 4) + (1,) * (faces.ndim-3))
        output[v] = np.sum(weights*pixels, axis=1)
        return output

    def support_rays_head(self):
        """The four actual pixel-centre rays, (sources,4,3), NaN if invalid."""
        return self._support_rays_head(.5, .5)

    def support_cell_corners_head(self):
        """Four corners of all four raw pixel cells, (sources,4,4,3).

        Pixel-centre interpolation is not exact point sampling. These geometric
        cell boundaries expose its finite raster support; renderer anti-aliasing
        is additional numerical raster behavior, not physiological filtering.
        """
        return np.stack([self._support_rays_head(row, col)
                         for row, col in ((0, 0), (0, 1), (1, 1), (1, 0))], axis=2)

    def _support_rays_head(self, row_offset, col_offset):
        rays = np.full((len(self.valid), 4, 3), np.nan)
        v = self.valid
        x = (self.pixel_cols[v]+col_offset-self.image_size/2)/(self.core_resolution/2)
        y = (self.image_size/2-self.pixel_rows[v]-row_offset)/(self.core_resolution/2)
        local = (FORWARD_HEAD[self.face[v], None, :]
                 + x[..., None]*RIGHT_HEAD[self.face[v], None, :]
                 + y[..., None]*UP_HEAD[self.face[v], None, :])
        rays[v] = local/np.linalg.norm(local, axis=-1, keepdims=True)
        return rays


def make_cube_mapping(directions_head, core_resolution=256):
    """Map unit axes, preserving invalid rows. Face ties follow FACE_NAMES order.

    Source rows must already be unit vectors (absolute norm tolerance 1e-6).
    Only tiny floating-point norm error is normalized; malformed rows are not
    silently turned into directions. Indices are zero-based; invalid is -1.
    """
    if (isinstance(core_resolution, (bool, np.bool_))
            or not isinstance(core_resolution, (int, np.integer)) or core_resolution < 4):
        raise ValueError("core_resolution must be an integer >= 4")
    rays = np.array(directions_head, dtype=float, copy=True)
    if rays.ndim != 2 or rays.shape[1] != 3:
        raise ValueError("directions_head must have shape (sources,3)")
    norm = np.linalg.norm(rays, axis=1)
    valid = np.isfinite(rays).all(axis=1) & (abs(norm-1) <= 1e-6)
    rays[valid] /= norm[valid, None]
    face = np.full(len(rays), -1, dtype=np.int32)
    rows = np.full((len(rays), 4), -1, dtype=np.int32)
    cols = rows.copy()
    weights = np.zeros((len(rays), 4))
    dots = rays[valid] @ FORWARD_HEAD.T
    selected = np.argmax(dots, axis=1)
    face[valid] = selected
    forward = dots[np.arange(valid.sum()), selected]
    px = ((core_resolution+2)/2-.5
          + core_resolution/2*np.sum(rays[valid]*RIGHT_HEAD[selected], axis=1)/forward)
    py = ((core_resolution+2)/2-.5
          - core_resolution/2*np.sum(rays[valid]*UP_HEAD[selected], axis=1)/forward)
    left, top = np.floor(px).astype(int), np.floor(py).astype(int)
    dx, dy = px-left, py-top
    rows[valid] = np.stack((top, top, top+1, top+1), axis=1)
    cols[valid] = np.stack((left, left+1, left, left+1), axis=1)
    weights[valid] = np.stack(((1-dx)*(1-dy), dx*(1-dy), (1-dx)*dy, dx*dy), axis=1)
    if np.any(rows[valid] < 0) or np.any(cols[valid] < 0) or np.any(rows[valid] >= core_resolution+2) or np.any(cols[valid] >= core_resolution+2):
        raise AssertionError("Guarded cube support escaped its image")
    return CubeMapping(rays, valid, face, rows, cols, weights, int(core_resolution))


def cube_pixel_rays_head(core_resolution=256):
    """All six rendered pixel-centre rays, shape (6,H,H,3)."""
    size = core_resolution+2
    row, col = np.indices((size, size))
    x, y = (col+.5-size/2)/(core_resolution/2), (size/2-row-.5)/(core_resolution/2)
    rays = (FORWARD_HEAD[:, None, None, :] + x[None, ..., None]*RIGHT_HEAD[:, None, None, :]
            + y[None, ..., None]*UP_HEAD[:, None, None, :])
    return rays/np.linalg.norm(rays, axis=-1, keepdims=True)


class CubeEyeSampler:
    """Owns an isolated renderer; model/data are read only during acquisition.

    Call sample(data, eye_pose_from_body(body)) at a stable simulation state.
    Six views share one origin, time and current head pose. Default hidden geom
    groups 1/2 match FlyGym's markers/selected body segments; other body parts
    remain occluders. Clipping planes retain MuJoCo model near/far conventions.
    Camera-attached headlight contributions are zeroed in the private scene;
    world lights are preserved. A camera must not illuminate different cube
    faces differently just because it samples them in separate render calls.
    RGB is renderer display RGB uint8 before interpolation, not photon flux.
    """

    def __init__(self, model, directions_head, *, core_resolution=256,
                 hidden_geom_groups=(1, 2)):
        self.mapping = make_cube_mapping(directions_head, core_resolution)
        self.model = model
        self.scene_option = mujoco.MjvOption()
        for group in hidden_geom_groups:
            if not isinstance(group, (int, np.integer)) or not 0 <= group < len(self.scene_option.geomgroup):
                raise ValueError("hidden geom groups must be valid integer group indices")
            self.scene_option.geomgroup[group] = 0
        self.renderer = mujoco.Renderer(model, height=self.mapping.image_size,
                                        width=self.mapping.image_size)

    def render_faces(self, data, pose: EyePose, *, segmentation=False):
        """Acquire six images; optional IDs only for independent geometry tests."""
        # Update geometry once. Subsequent changes affect this owned renderer's
        # scene only. GL cameras are colocated; no inherited inter-pupil offset.
        self.renderer.update_scene(data, scene_option=self.scene_option)
        scene = self.renderer.scene
        scene.stereo = mujoco.mjtStereo.mjSTEREO_NONE
        # update_scene initially constructs a free-camera headlight. It must
        # neither survive as an unrelated light nor rotate once per cube face.
        # Zero only its private-scene light contribution; preserve model/world
        # lights and do not alter the model's headlight or default eye pipeline.
        for light in scene.lights[:scene.nlight]:
            if light.headlight:
                light.ambient[:] = 0
                light.diffuse[:] = 0
                light.specular[:] = 0
                light.intensity = 0
        near = float(self.model.vis.map.znear*self.model.stat.extent)
        far = float(self.model.vis.map.zfar*self.model.stat.extent)
        if not 0 < near < far or not np.isfinite([near, far]).all():
            raise ValueError("invalid model clipping planes")
        if segmentation:
            self.renderer.enable_segmentation_rendering()
        else:
            self.renderer.disable_segmentation_rendering()
        images = []
        for forward, up in zip(FORWARD_HEAD, UP_HEAD, strict=True):
            for camera in scene.camera:
                camera.pos[:] = pose.origin_world
                camera.forward[:] = pose.head_to_world @ forward
                camera.up[:] = pose.head_to_world @ up
                camera.orthographic = 0
                camera.frustum_near, camera.frustum_far = near, far
                camera.frustum_top = near*self.mapping.image_size/self.mapping.core_resolution
                camera.frustum_bottom = -camera.frustum_top
                camera.frustum_center = 0
                # Match MuJoCo fovy cameras: zero delegates width to aspect.
                camera.frustum_width = 0
            images.append(self.renderer.render())
        return np.stack(images)

    def sample(self, data, pose: EyePose):
        return self.mapping.sample(self.render_faces(data, pose))

    def close(self):
        self.renderer.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
