import numpy as np
import pytest

from fruitfly.wind import local_airflow


def test_source_direction_convention_and_undefined_still_air():
    for air, angle in [((-600, 0, 0), 0), ((0, -600, 0), -90),
                       ((0, 600, 0), 90), ((600, 0, 0), 180)]:
        observed = local_airflow(air, np.zeros((2, 3)), np.eye(3))
        np.testing.assert_allclose(observed["source_azimuth_deg"], [angle, angle])
    assert local_airflow((0, 0, 10), np.zeros((2, 3)), np.eye(3))["source_azimuth_deg"] == [None, None]


def test_common_translation_and_world_rotation_do_not_change_relative_flow():
    air = np.array([-400, 200, 5.])
    sensors = np.array([[5, -1, 2], [3, 2, 3.]])
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.]])
    base = local_airflow(air, sensors, np.eye(3))
    shift = np.array([70, -30, 1])
    translated = local_airflow(air + shift, sensors + shift, np.eye(3))
    rotated = local_airflow(rotation @ air, sensors @ rotation.T, rotation)
    for other in (translated, rotated):
        np.testing.assert_allclose(base["relative_velocity_head_mm_s"], other["relative_velocity_head_mm_s"])
        np.testing.assert_allclose(base["source_azimuth_deg"], other["source_azimuth_deg"])
    with pytest.raises(ValueError):
        local_airflow(air, sensors, np.ones((3, 3)))


def test_actual_antenna_velocity_matches_position_finite_difference():
    import mujoco
    from fruitfly.body import BodyConfig, BodyRuntime
    with BodyRuntime(config=BodyConfig(wind_mm_s=(-600, 0))) as body:
        # A mixture of base and articulated velocities detects COM/origin and
        # rotation mistakes that testing a stationary body would miss.
        body.data.qvel[:] = np.random.default_rng(8).normal(0, .2, body.model.nv)
        mujoco.mj_forward(body.model, body.data)
        before = body.data.xpos[body._antenna_ids].copy()
        observation = body.observe()["wind"]
        head_rotation = body.data.xmat[body._head_id].reshape(3, 3) @ body._head_anatomical_basis
        relative_world = np.asarray(observation["relative_velocity_head_mm_s"]) @ head_rotation.T
        measured_velocity = np.array([-600, 0, 0]) - relative_world
        advanced = mujoco.MjData(body.model)
        advanced.qpos[:] = body.data.qpos
        epsilon = 1e-7
        mujoco.mj_integratePos(body.model, advanced.qpos, body.data.qvel, epsilon)
        mujoco.mj_forward(body.model, advanced)
        reference_velocity = (advanced.xpos[body._antenna_ids] - before) / epsilon
        np.testing.assert_allclose(measured_velocity, reference_velocity, atol=2e-7, rtol=2e-6)
        assert observation["antenna_order"] == ["L", "R"]


def test_fast_wind_emission_refinement_preserves_flux_and_converges():
    from fruitfly.body import PuffField
    samples = []
    for interval in (.1, .001, .0005):
        field = PuffField((0, 0, .00007), (-.5957, 0, 0),
                          emission_interval_s=interval, prehistory_s=0, lifetime_s=.2)
        field.advance(.1 - 1e-8, 1)
        assert sum(field.masses) == pytest.approx(1, abs=1e-12)
        steady = PuffField((0, 0, .00007), (-.5957, 0, 0),
                           emission_interval_s=interval, prehistory_s=.1, lifetime_s=.2)
        values = []
        for at in np.linspace(0, .01, 101):
            steady.advance(at, 1)
            values.append(steady.sample([[-.01, 0, .0007]], at)[0])
        samples.append(np.array(values))
    np.testing.assert_allclose(samples[1], samples[2], rtol=1e-8)
    # Coarse spacing in fast flow can suppress the signal almost completely.
    assert samples[0].mean() < .01 * samples[1].mean()
