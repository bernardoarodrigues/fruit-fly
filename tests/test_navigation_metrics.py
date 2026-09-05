"""Analytic controls for observational navigation metrics, without a simulator."""
import numpy as np
import pytest

from fruitfly.navigation_metrics import spike_activity, planar_kinematics, circular_activity


def test_actual_spikes_half_open_bins_named_on_off_and_distinct_dn_cohorts():
    result = spike_activity([0, 1, 2, 3, 4, 5, 7, 8], [5, 2, 5, 8, 2, 8, 8, 5],
        {'DN_all': [8, 5, 2], 'DNa01': [5], 'DNa02': [2]}, [0, 4, 8],
        dt_s=.001, observed_interval_ticks=(0, 9), windows={'ON': (2, 5), 'OFF': (5, 8)})
    np.testing.assert_array_equal(result['bins']['cohorts']['DN_all']['observed_counts'], [[1, 2, 1], [2, 0, 1]])
    np.testing.assert_array_equal(result['bins']['cohorts']['DNa01']['observed_counts'], [[2], [0]])
    np.testing.assert_array_equal(result['bins']['cohorts']['DNa02']['observed_counts'], [[1], [1]])
    np.testing.assert_allclose(result['bins']['cohorts']['DNa01']['per_neuron_rate_hz'], [[500], [0]])
    assert result['window_names'] == ['ON', 'OFF']
    np.testing.assert_array_equal(result['windows']['cohorts']['DN_all']['observed_counts'], [[1, 1, 1], [2, 0, 0]])
    assert result['bins']['complete'].all()


def test_missing_partial_empty_and_true_zero_remain_distinct():
    r = spike_activity([3], [8], {'known': [8], 'unknown': None, 'empty': []}, [0, 2, 4, 6, 8],
                       dt_s=.01, observed_interval_ticks=(2, 5))['bins']
    assert r['status'].tolist() == ['unobserved', 'complete', 'partial', 'unobserved']
    np.testing.assert_allclose(r['observed_duration_s'], [0, .02, .01, 0])
    assert r['cohorts']['unknown']['observed_counts'] is None
    assert r['cohorts']['empty']['status'] == 'empty_cohort'
    assert r['cohorts']['empty']['observed_counts'].shape == (4, 0)
    assert np.isnan(r['cohorts']['empty']['mean_cell_rate_hz']).all()
    assert np.isnan(r['cohorts']['known']['per_neuron_rate_hz'][[0, 2, 3]]).all()
    assert r['cohorts']['known']['per_neuron_rate_hz'][1, 0] == 50
    silent = spike_activity([], [], {'known': [8]}, [0, 2], dt_s=.01, observed_interval_ticks=(0, 2))
    assert silent['bins']['cohorts']['known']['per_neuron_rate_hz'][0, 0] == 0
    assert silent['windows']['intervals_ticks'].shape == (0, 2)


@pytest.mark.parametrize('change', [
    {'spike_ticks': [2, 1]}, {'spike_indices': [1.2, 3.]}, {'bin_edges_ticks': [0, 0]},
    {'observed_interval_ticks': (0, 0)}, {'dt_s': 0}, {'cohorts': {'duplicate': [1, 1]}},
    {'spike_ticks': [0, 4]}, {'windows': {'ON': (2, 1)}}])
def test_invalid_spike_time_identity_and_exposure_rejected(change):
    kwargs = dict(spike_ticks=[0, 1], spike_indices=[1, 3], cohorts={'a': [1]}, bin_edges_ticks=[0, 2],
                  observed_interval_ticks=(0, 4), dt_s=.001)
    kwargs.update(change)
    with pytest.raises(ValueError):spike_activity(**kwargs)


def test_irregular_time_straight_motion_and_wind_sign():
    r = planar_kinematics([0, .5, 2], [[0, 0, 0], [1, 0, 5], [4, 0, -9]], [0, 0, 0],
                         local_airflow_world_mm_s=[[-10, 0], [-20, 0]])
    np.testing.assert_allclose(r['forward_mm_s'], 2)
    np.testing.assert_allclose(r['speed_mm_s'], 2)
    np.testing.assert_allclose(r['upwind_projection_mm_s'], 2)
    np.testing.assert_allclose(r['upwind_heading_cosine'], 1)
    np.testing.assert_allclose(r['yaw_rate_rad_s'], 0)
    np.testing.assert_allclose(r['heading_curvature_rad_per_mm'], 0)
    np.testing.assert_allclose(r['path_curvature_rad_per_mm'], 0)


def test_heading_wrap_and_path_turn_are_separate_for_sideways_motion():
    r = planar_kinematics([0, 1, 2], [[0, 0], [1, 0], [1, 1]], np.deg2rad([179, -179, -177]))
    np.testing.assert_allclose(r['yaw_rate_rad_s'], np.deg2rad([2, 2]), atol=1e-14)
    np.testing.assert_allclose(r['heading_curvature_rad_per_mm'], np.deg2rad([2, 2]), atol=1e-14)
    np.testing.assert_allclose(r['path_turn_rate_rad_s'], [np.pi/2])
    np.testing.assert_allclose(r['path_curvature_rad_per_mm'], [np.pi/2])
    assert r['path_interval_start_s'].tolist() == [.5]
    assert r['path_interval_end_s'].tolist() == [1.5]


def test_reflection_preserves_speed_forward_upwind_and_reverses_turn_signs():
    times = [0, .5, 1.5, 2.]
    positions = np.array([[0., 0.], [1., .3], [1.5, 1.], [1.2, 1.7]])
    yaw = np.array([.1, .3, .6, .9]); wind = np.array([[-10., 4.], [-9., 3.], [-8., 2.]])
    a = planar_kinematics(times, positions, yaw, local_airflow_world_mm_s=wind)
    b = planar_kinematics(times, positions*[1, -1], -yaw, local_airflow_world_mm_s=wind*[1, -1])
    for key in ['speed_mm_s', 'forward_mm_s', 'upwind_projection_mm_s', 'upwind_heading_cosine']:
        np.testing.assert_allclose(a[key], b[key], atol=1e-12)
    for key in ['lateral_mm_s', 'yaw_rate_rad_s', 'heading_curvature_rad_per_mm', 'path_turn_rate_rad_s', 'path_curvature_rad_per_mm', 'upwind_heading_error_rad']:
        np.testing.assert_allclose(a[key], -b[key], atol=1e-12)


def test_stopped_slow_and_still_air_metrics_are_undefined_without_faking_zero():
    r = planar_kinematics([0, 1, 2, 3], [[0, 0], [0, 0], [.05, 0], [.15, 0]], [0, .1, .2, .3],
                         speed_floor_mm_s=.075, local_airflow_world_mm_s=[[0, 0], [0, 0], [0, 1]])
    assert r['curvature_valid'].tolist() == [False, False, True]
    assert np.isnan(r['heading_curvature_rad_per_mm'][:2]).all()
    assert not r['path_valid'].any()
    assert np.isnan(r['path_curvature_rad_per_mm']).all()
    assert np.isnan(r['upwind_projection_mm_s'][:2]).all()
    assert not r['wind_valid'][:2].any()
    missing = planar_kinematics([0, 1], [[0, 0], [1, 0]], [0, 0])
    assert missing['wind_status'].tolist() == ['missing_airflow']
    assert np.isnan(missing['upwind_heading_cosine']).all()


def test_half_turn_is_ambiguous_and_two_pose_path_output_is_empty():
    r = planar_kinematics([0, 1], [[0, 0], [1, 0]], [0, np.pi])
    assert not r['yaw_valid'][0]
    assert np.isnan(r['forward_mm_s'][0]) and np.isnan(r['heading_curvature_rad_per_mm'][0])
    assert r['path_curvature_rad_per_mm'].shape == (0,)


@pytest.mark.parametrize('change', [{'times_s': [0, 0]}, {'positions_mm': [[0, 0], [np.nan, 1]]},
                                   {'yaw_rad': [0, np.inf]}, {'speed_floor_mm_s': 0},
                                   {'local_airflow_world_mm_s': [[0, 0], [0, 0]]}])
def test_invalid_pose_duration_and_wind_shapes_rejected(change):
    args = dict(times_s=[0, 1], positions_mm=[[0, 0], [1, 0]], yaw_rad=[0, 0]);args.update(change)
    with pytest.raises(ValueError):planar_kinematics(**args)


def test_circular_activity_requires_explicit_complete_coordinates():
    unknown = circular_activity([[3, 1]], [17, 4])
    assert unknown['status'] == 'missing_coordinates' and unknown['phase_rad'] is None
    partial = circular_activity([[3, 1]], [17, 4], angles_rad={17: 0}, coordinate_label='declared toy sectors')
    assert partial['status'] == 'incomplete_coordinates'
    assert partial['missing_coordinate_indices'].tolist() == [4]
    with pytest.raises(ValueError):circular_activity([[1]], [17], angles_rad={17: 0})


def test_silent_uniform_localized_and_double_peaked_circular_moments():
    coords = {4: 0, 5: np.pi/2, 6: np.pi, 7: 3*np.pi/2}
    r = circular_activity([[0, 0, 0, 0], [1, 1, 1, 1], [0, 2, 0, 0], [1, 0, 1, 0]],
                          [4, 5, 6, 7], angles_rad=coords, coordinate_label='synthetic circular sectors')
    assert np.isnan(r['resultant_length'][0])
    assert np.isnan(r['phase_rad'][[0, 1, 3]]).all()
    np.testing.assert_allclose(r['resultant_length'][1:], [0, 1, 0], atol=1e-15)
    assert r['phase_rad'][2] == np.pi/2
    assert 'not bump detection' in r['interpretation']


def test_metrics_do_not_mutate_caller_arrays():
    ticks=np.array([0,1]);cells=np.array([3,4]);cohort=np.array([4,3])
    r=spike_activity(ticks,cells,{'a':cohort},[0,2],dt_s=.1,observed_interval_ticks=(0,2))
    r['bins']['cohorts']['a']['indices'][0]=999
    np.testing.assert_array_equal(cohort,[4,3]);np.testing.assert_array_equal(ticks,[0,1]);np.testing.assert_array_equal(cells,[3,4])


def test_antipodal_wind_turn_and_path_reversal_have_no_invented_direction():
    r = planar_kinematics([0, 1, 2], [[0, 0], [1, 0], [0, 0]], [0, 0, 0],
                         local_airflow_world_mm_s=[[1, 0], [1, 0]])
    np.testing.assert_allclose(r['upwind_heading_cosine'], -1)
    assert not r['upwind_heading_error_valid'].any()
    assert np.isnan(r['upwind_heading_error_rad']).all()
    assert not r['path_valid'][0] and np.isnan(r['path_turn_rate_rad_s'][0])


def test_speed_floor_boundary_is_included_and_zero_wind_stays_undefined_at_zero_floor():
    r = planar_kinematics([0, 1], [[0, 0], [.1, 0]], [0, .1], speed_floor_mm_s=.1,
                         wind_floor_mm_s=0, local_airflow_world_mm_s=[[0, 0]])
    assert r['curvature_valid'][0]
    assert not r['wind_valid'][0] and np.isnan(r['upwind_projection_mm_s'][0])
