"""Read-only proximal-antenna geometry for the pinned native FlyBody model.

This module belongs to the isolated MuJoCo environment. Callers supply detached,
forwarded native data. It supplies no drag, antenna deflection or neural drive.
The neutral thorax-aligned head basis was audited in flybody-airflow-geometry.json.
"""
from __future__ import annotations

import numpy as np
import mujoco


class FlyBodyAirflow:
    def __init__(self, model, neutral_data):
        self.model = model
        names = ("head", "thorax", "abdomen", "antenna_left", "antenna_right")
        ids = {name: int(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "walker/" + name))
               for name in names}
        if min(ids.values()) < 0 or len(set(ids.values())) != len(names):
            raise ValueError("Missing or aliased FlyBody airflow bodies")
        self.head = ids["head"]
        self.antennae = (ids["antenna_left"], ids["antenna_right"])
        head_rotation = neutral_data.xmat[self.head].reshape(3, 3)
        neutral_rotation = neutral_data.xmat[ids["thorax"]].reshape(3, 3)
        self.basis = head_rotation.T @ neutral_rotation
        anterior = (neutral_data.xpos[self.head] - neutral_data.xpos[ids["abdomen"]]) @ neutral_rotation
        leftward = (neutral_data.xpos[self.antennae[0]] - neutral_data.xpos[self.antennae[1]]) @ neutral_rotation
        if anterior[0] <= 0 or leftward[1] <= 0 or np.linalg.det(self.basis) < .999999999:
            raise ValueError("Pinned FlyBody head/antenna axis signs changed")
        self.metadata = {
            "enabled": True,
            "sampling_point": "proximal antenna body origin; not distal arista or sensillum",
            "antenna_bodies": ["walker/antenna_left", "walker/antenna_right"],
            "antenna_order": ["L", "R"],
            "head_axes": ["forward", "left", "up"],
            "basis_in_head": self.basis.tolist(),
            "frame_definition": "neutral thorax axes expressed in head; follows articulated head rotation",
            "velocity_method": "mj_jac at body origin times native qvel; cm/s multiplied by 10",
            "audit": "docs/flybody-airflow-independent-review.md",
            "distal_receptor_frame_validated": False,
            "mechanical_or_neural_transduction": False,
        }

    def sample(self, data):
        """Read point geometry only; do not step, forward, or modify native data."""
        positions = np.asarray(data.xpos[list(self.antennae)]).copy()
        velocity = np.empty((2, 3))
        jacobian = np.empty((3, self.model.nv))
        for index, body in enumerate(self.antennae):
            mujoco.mj_jac(self.model, data, jacobian, None, positions[index], body)
            velocity[index] = jacobian @ data.qvel
        rotation = data.xmat[self.head].reshape(3, 3) @ self.basis
        return {
            "antenna_origin_positions_mm": (positions * 10.).tolist(),
            "antenna_origin_velocity_world_mm_s": (velocity * 10.).tolist(),
            "head_to_world": rotation.tolist(),
        }
