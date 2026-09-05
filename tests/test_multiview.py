import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fruitfly.multiview import (CubeEyeSampler, EyePose, cube_pixel_rays_head,
                               make_cube_mapping)


def test_all_sphere_axes_and_seams_keep_guarded_support():
    rng = np.random.default_rng(2029)
    directions = rng.normal(size=(10000, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    corners = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])/np.sqrt(3)
    directions = np.vstack((np.eye(3), -np.eye(3), corners, directions))
    mapping = make_cube_mapping(directions, 64)
    assert mapping.valid.all()
    assert np.all(mapping.weights >= 0)
    np.testing.assert_allclose(mapping.weights.sum(axis=1), 1, atol=1e-15)
    assert mapping.pixel_rows.min() >= 0 and mapping.pixel_cols.min() >= 0
    assert mapping.pixel_rows.max() < 66 and mapping.pixel_cols.max() < 66
    np.testing.assert_allclose(mapping.sample(np.ones((6, 66, 66, 3))), 1)
    rays = mapping.support_rays_head()
    grid = cube_pixel_rays_head(64)
    np.testing.assert_allclose(rays, grid[mapping.face[:, None], mapping.pixel_rows, mapping.pixel_cols])


def test_invalid_sources_are_retained_and_never_read_as_last_pixel():
    directions = [[1, 0, 0], [0, 0, 0], [np.nan, 0, 0], [2, 0, 0], [0, 0, -1]]
    mapping = make_cube_mapping(directions, 4)
    np.testing.assert_array_equal(mapping.valid, [True, False, False, False, True])
    assert (mapping.face[~mapping.valid] == -1).all()
    assert (mapping.pixel_cols[~mapping.valid] == -1).all()
    assert not mapping.weights[~mapping.valid].any()
    values = mapping.sample(np.full((6, 6, 6, 3), 7, dtype=np.uint8))
    assert np.isnan(values[~mapping.valid]).all()
    assert (values[mapping.valid] == 7).all()
    empty = make_cube_mapping(np.empty((0, 3)), 4)
    assert empty.sample(np.zeros((6, 6, 6))).shape == (0,)


def test_coordinate_field_accuracy_and_cube_seam_limits():
    # Smooth directional field independent of any scene. Values on either side
    # of a seam converge to the same continuous signal to raster accuracy.
    directions = []
    for edge in ((1, 1, 0), (1, 0, -1), (0, -1, 1), (1, 1, 1)):
        for perturbation in (-1e-7, 0, 1e-7):
            vector = np.array(edge, dtype=float)
            vector[0] += perturbation
            directions.append(vector/np.linalg.norm(vector))
    mapping = make_cube_mapping(directions, 128)
    values = mapping.sample(cube_pixel_rays_head(128))
    assert abs(values-directions).max() < 5e-5
    assert np.max(np.ptp(values.reshape(-1, 3, 3), axis=1)) < 5e-5


@pytest.mark.parametrize("resolution", [True, 3, 8.5])
def test_reject_bad_resolution(resolution):
    with pytest.raises(ValueError):
        make_cube_mapping([[1, 0, 0]], resolution)


def test_reject_bad_pose():
    for matrix in (np.zeros((3, 3)), np.diag([1, 1, -1]), np.ones((3, 2))):
        with pytest.raises(ValueError):
            EyePose(np.zeros(3), matrix)
    with pytest.raises(ValueError):
        EyePose([0, np.nan, 0], np.eye(3))


def test_render_known_target_at_cube_corner_and_rotated_head():
    import mujoco
    model = mujoco.MjModel.from_xml_string('''<mujoco><visual>
      <global offwidth="130" offheight="130"/>
      <quality offsamples="0" numslices="128" numstacks="128"/></visual>
      <worldbody><geom name="target" type="sphere" size="1" pos="20 0 0"/>
      </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    direction = np.ones(3)/np.sqrt(3)
    raw_rays = cube_pixel_rays_head(128)
    with CubeEyeSampler(model, [direction], core_resolution=128) as sampler:
        for angles in ((0, 0, 0), (29, -43, 17)):
            pose = EyePose([1.2, -2.3, 3.4], Rotation.from_euler("xyz", angles, degrees=True).as_matrix())
            model.geom_pos[0] = pose.origin_world + pose.head_to_world @ (20*direction)
            mujoco.mj_forward(model, data)
            qpos, cam_pos = data.qpos.copy(), model.cam_pos.copy()
            seg = sampler.render_faces(data, pose, segmentation=True)
            np.testing.assert_array_equal(data.qpos, qpos)
            np.testing.assert_array_equal(model.cam_pos, cam_pos)
            rendered = (seg[..., 0] == 0) & (seg[..., 1] == int(mujoco.mjtObj.mjOBJ_GEOM))
            analytic = raw_rays @ direction >= np.sqrt(1-(1/20)**2)
            assert (rendered & analytic).sum()/(rendered | analytic).sum() > .97
            assert sampler.mapping.sample(rendered.astype(float))[0] == 1


def test_hidden_geometry_groups_match_explicit_occlusion_convention():
    import mujoco
    model = mujoco.MjModel.from_xml_string('''<mujoco><visual>
      <global offwidth="34" offheight="34"/></visual><worldbody>
      <geom name="visible" type="sphere" size="1" pos="10 0 0" group="0"/>
      <geom name="hidden_marker" type="sphere" size="1" pos="0 10 0" group="1"/>
      <geom name="hidden_body" type="sphere" size="1" pos="0 0 10" group="2"/>
      <geom name="other_body" type="sphere" size="1" pos="-10 0 0" group="0"/>
      </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    with CubeEyeSampler(model, [[1, 0, 0]], core_resolution=32) as sampler:
        seg = sampler.render_faces(data, EyePose([0, 0, 0], np.eye(3)), segmentation=True)
        for light in sampler.renderer.scene.lights[:sampler.renderer.scene.nlight]:
            if light.headlight:
                assert not light.ambient.any() and not light.diffuse.any() and not light.specular.any()
                assert light.intensity == 0
        assert model.vis.headlight.active == 1
        assert model.vis.headlight.diffuse.sum() > 0
    seen = set(np.unique(seg[..., 0]))
    assert 0 in seen and 3 in seen
    assert 1 not in seen and 2 not in seen
