import numpy as np
import pytest
import json
from pathlib import Path

from fruitfly.wind import local_airflow, MeasuredAntennaReference


CALIBRATION = Path(__file__).resolve().parents[1] / "data/wind-calibration.json"


def reference_flow(angle_deg, speed):
    theta = np.deg2rad(angle_deg)
    return {"relative_velocity_head_mm_s": [[-speed * np.cos(theta), speed * np.sin(theta), 0]] * 2}


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
        head_rotation = body.data.geom_xmat[body._head_geom_id].reshape(3, 3) @ body._head_anatomical_basis
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


def test_retained_head_geometry_and_distinct_antennae_align_with_physical_left():
    import mujoco
    from fruitfly.body import BodyConfig, BodyRuntime
    with BodyRuntime(config=BodyConfig(wind_mm_s=(-595.7, 0))) as body:
        assert body._head_geom_id >= 0
        assert all(i >= 0 for i in body._antenna_ids)
        assert len(set(body._antenna_ids)) == 2
        body.data.qvel[:] = 0
        mujoco.mj_forward(body.model, body.data)
        head_rotation = body.data.geom_xmat[body._head_geom_id].reshape(3, 3) @ body._head_anatomical_basis
        antenna_left_vector = body.data.xpos[body._antenna_ids[0]] - body.data.xpos[body._antenna_ids[1]]
        # This anatomical landmark check does not merely invert the same frame
        # used by the implementation; it caught the old fused-body id=-1 bug.
        lateral = antenna_left_vector @ head_rotation
        assert lateral[1] > .1  # mm, measured bilateral sensor separation
        np.testing.assert_allclose(lateral[[0, 2]], [0, 0], atol=1e-5)
        assert abs(body.observe()["wind"]["source_azimuth_deg"][0]) < .001


def test_measured_reference_matches_refit_of_primary_paired_observations():
    source = json.loads(CALIBRATION.read_text())
    reference = MeasuredAntennaReference(CALIBRATION, intended_sex="female")
    theta = np.asarray(source["wind_angle_deg"])
    basis = np.column_stack([np.ones(5), np.cos(np.deg2rad(theta)), np.sin(np.deg2rad(theta))])
    predictions = []
    for side in ("left", "right"):
        observed = np.asarray(source["per_fly_measurements"][f"{side}_deg"])
        assert observed.shape == (17, 5)
        predictions.append(basis @ np.linalg.lstsq(basis, observed.mean(axis=0), rcond=None)[0])
    for i, angle in enumerate(theta):
        result = reference.evaluate(reference_flow(angle, reference.nominal_speed_mm_s))
        assert result["excluded_because"] == [[], []]
        np.testing.assert_allclose(result["estimated_steady_arista_deflection_deg"], np.asarray(predictions)[:, i], atol=1e-10)
    assert reference.nominal_speed_mm_s == pytest.approx(582.3281619913032)


def test_measured_reference_abstains_outside_declared_domain():
    reference = MeasuredAntennaReference(CALIBRATION, intended_sex="female")
    nominal = reference.nominal_speed_mm_s
    for angle, speed, reason in ((0, 2, "outside_declared_speed_tolerance"),
                                  (0, nominal * 1.06, "outside_declared_speed_tolerance"),
                                  (91, nominal, "outside_measured_azimuths"),
                                  (-91, nominal, "outside_measured_azimuths"),
                                  (180, nominal, "outside_measured_azimuths"),
                                  (0, 0, "undefined_horizontal_direction")):
        result = reference.evaluate(reference_flow(angle, speed))
        assert result["estimated_steady_arista_deflection_deg"] == [None, None]
        assert all(reason in reasons for reasons in result["excluded_because"])
    elevated = {"relative_velocity_head_mm_s": [[-nominal, 0, nominal * np.tan(np.deg2rad(6))]] * 2}
    assert reference.evaluate(elevated)["estimated_steady_arista_deflection_deg"] == [None, None]
    mixed = {"relative_velocity_head_mm_s": [[-nominal, 0, 0], [-2, 0, 0]]}
    result = reference.evaluate(mixed)
    assert result["estimated_steady_arista_deflection_deg"][0] is not None
    assert result["estimated_steady_arista_deflection_deg"][1] is None


def test_measured_reference_sex_transfer_requires_boolean_opt_in():
    with pytest.raises(ValueError):
        MeasuredAntennaReference(CALIBRATION, intended_sex="male")
    with pytest.raises(ValueError):
        MeasuredAntennaReference(CALIBRATION, intended_sex="male", allow_sex_transfer="false")
    reference = MeasuredAntennaReference(CALIBRATION, intended_sex="male", allow_sex_transfer=True)
    assert reference.provenance["measured_sex"] == "female"
    assert reference.provenance["male_transfer_validated"] is False


@pytest.mark.parametrize("mutation", ["coefficients", "archive", "basis", "observations", "speed", "window"])
def test_measured_reference_rejects_inconsistent_primary_provenance(tmp_path, mutation):
    source = json.loads(CALIBRATION.read_text())
    if mutation == "coefficients":
        source["curves"]["left"]["coefficients"][0] += 10
    elif mutation == "archive":
        source["archive_sha256"] = "0" * 64
    elif mutation == "basis":
        source["curves"]["left"]["basis"] = ["1", "cos(wind_angle_deg)", "sin(wind_angle_deg)"]
    elif mutation == "observations":
        source["per_fly_measurements"]["left_deg"][0][0] += 1
    elif mutation == "speed":
        source["velocity_m_s"] = .002
    else:
        source["anemometer"]["analysis_window_s_from_trial_start"] = [3, 4]
    path = tmp_path / "inconsistent.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError):
        MeasuredAntennaReference(path, intended_sex="female")


def test_reference_allows_note_changes_and_records_current_file_hash(tmp_path):
    import hashlib
    source = json.loads(CALIBRATION.read_text())
    source["notes"] = "Additional review annotation; measurements unchanged."
    path = tmp_path / "annotated.json"
    path.write_text(json.dumps(source))
    reference = MeasuredAntennaReference(path, intended_sex="female")
    assert reference.provenance["source_file_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


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
