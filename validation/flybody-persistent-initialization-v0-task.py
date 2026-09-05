"""Experimental rolling FlyBody inference task; never imported by live runtime.

Run in the pinned Python 3.10 environment with the verified source on sys.path.
Only finite-recording bookkeeping changes. Native body, policy and physical
termination limits retain the source configuration.
"""
from __future__ import annotations

import numpy as np
from dm_control import composer
from dm_control.composer.observation import observable
from dm_control.locomotion.arenas import floors
from flybody.fruitfly import fruitfly
from flybody.quaternions import get_dquat_local
from flybody.tasks.base import Walking
from flybody.tasks.constants import _TERMINAL_ANGVEL, _TERMINAL_LINVEL
from flybody.tasks.trajectory_loaders import InferenceWalkingTrajectoryLoader
from flybody.tasks.walk_imitation import WalkImitation


class RollingWalkImitation(WalkImitation):
    """65 current-command actor rows plus one post-step observation guard row."""

    def initialize_episode_mjcf(self, random_state):
        # Preserve source model/trajectory-site construction at initialization.
        super().initialize_episode_mjcf(random_state)
        self._rolling_origin = 0
        self._ref_qpos = self._ref_qpos[:66].copy()
        self._ref_qvel = self._ref_qvel[:66].copy()
        self._snippet = dict(self._snippet, qpos=self._ref_qpos, qvel=self._ref_qvel)
        self._episode_steps = self._snippet_steps = None
        self._reached_traj_end = False
        self._should_terminate = False

    def install_preview(self, qpos, qvel, absolute_tick):
        if qpos.shape != (66, 7) or qvel.shape != (66, 6):
            raise ValueError("Rolling reference requires 66 poses and velocities")
        if absolute_tick != self._step_counter:
            raise ValueError("Reference tick disagrees with source control counter")
        if not np.isfinite(qpos).all() or not np.isfinite(qvel).all():
            raise ValueError("Nonfinite rolling reference")
        self._ref_qpos[:] = qpos
        self._ref_qvel[:] = qvel
        self._rolling_origin = absolute_tick

    def _reference_index(self):
        offset = self._step_counter - self._rolling_origin
        if offset not in (0, 1):
            raise RuntimeError("A current command must refresh the reference each tick")
        return offset

    @composer.observable
    def ref_displacement(self):
        def get_ref_displacement(physics):
            start = self._reference_index()
            position, _ = self._walker.get_pose(physics)
            reference = self._ref_qpos[start:start + self._future_steps + 1, :3]
            return self._walker.transform_vec_to_egocentric_frame(physics, reference - position)
        return observable.Generic(get_ref_displacement)

    @composer.observable
    def ref_root_quat(self):
        def get_root_quat(physics):
            start = self._reference_index()
            reference = self._ref_qpos[start:start + self._future_steps + 1, 3:7]
            _, quaternion = self._walker.get_pose(physics)
            return get_dquat_local(quaternion, reference)
        return observable.Generic(get_root_quat)

    def before_step(self, physics, action, random_state):
        if int(np.round(physics.data.time / self.control_timestep)) != self._step_counter:
            raise RuntimeError("Native clock disagrees with source control counter")
        if self._reference_index() != 0:
            raise RuntimeError("Reference was not refreshed before native step")
        ghost_qpos = self._ref_qpos[0, :7] + self._ghost_offset_with_quat
        ghost_qvel = self._ref_qvel[0, :6]
        self._ghost.set_pose(physics, ghost_qpos[:3], ghost_qpos[3:])
        self._ghost.set_velocity(physics, ghost_qvel[:3], ghost_qvel[3:])
        action[np.isnan(action)] = 0.  # Unchanged source behavior.
        # WalkImitation's other behavior is exactly Walking.before_step.
        Walking.before_step(self, physics, action, random_state)

    def check_termination(self, physics):
        linvel = np.linalg.norm(self._walker.observables.velocimeter(physics))
        angvel = np.linalg.norm(self._walker.observables.gyro(physics))
        com_dist = np.linalg.norm(self.observables['walker/ref_displacement'](physics)[0])
        self._reached_traj_end = False
        return (linvel > _TERMINAL_LINVEL or angvel > _TERMINAL_ANGVEL
                or com_dist > self._terminal_com_dist
                or Walking.check_termination(self, physics))


def rolling_walk_imitation(random_state=None):
    """Match source default factory; omit only the environment's 10 s cutoff.

    The task's finite construction value keeps 500 static visualization sites
    identical. It no longer controls task termination or allocates growing data.
    """
    loader = InferenceWalkingTrajectoryLoader()
    task = RollingWalkImitation(
        walker=fruitfly.FruitFly, arena=floors.Floor(), traj_generator=loader,
        terminal_com_dist=.3, mocap_joint_names=loader.get_joint_names(),
        mocap_site_names=loader.get_site_names(), inference_mode=True,
        force_actuators=False, disable_wings=True, joint_filter=.01,
        future_steps=64, time_limit=10.)
    return composer.Environment(time_limit=float('inf'), task=task,
                                random_state=random_state,
                                strip_singleton_obs_buffer_dim=True)
