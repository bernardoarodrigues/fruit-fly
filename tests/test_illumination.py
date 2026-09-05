import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from fruitfly.illumination import LIGHT_NAME, WorldIlluminationConfig, add_world_illumination, illumination_snapshot
from fruitfly.multiview import CubeEyeSampler, EyePose


def test_body_config_preserves_none_and_accepts_explicit_mapping():
    from fruitfly.body import BodyConfig
    assert BodyConfig().world_illumination is None
    assert isinstance(BodyConfig(world_illumination={}).world_illumination, WorldIlluminationConfig)
    with pytest.raises(ValueError):
        BodyConfig(world_illumination=True)


@pytest.mark.parametrize("kwargs", [
    {"direction_world": [0, 0, 0]}, {"direction_world": [1, np.nan, 0]},
    {"ambient_rgb": [1, 1]}, {"ambient_rgb": [-1, 0, 0]},
    {"diffuse_rgb": [2, 0, 0]}, {"cast_shadows": 1},
])
def test_reject_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        WorldIlluminationConfig(**kwargs)


def test_opt_in_fixed_world_light_and_no_duplicate_installation():
    spec = mujoco.MjSpec.from_string('<mujoco><worldbody><geom type="sphere" size="1"/></worldbody></mujoco>')
    assert spec.visual.headlight.active == 1 and len(spec.lights) == 0
    cfg = WorldIlluminationConfig()
    add_world_illumination(spec, cfg)
    model = spec.compile()
    assert model.nlight == 1
    assert mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_LIGHT, LIGHT_NAME) == 0
    assert model.light_bodyid[0] == 0
    assert model.light_mode[0] == mujoco.mjtCamLight.mjCAMLIGHT_FIXED
    assert model.light_type[0] == mujoco.mjtLightType.mjLIGHT_DIRECTIONAL
    assert model.vis.headlight.active == 0
    assert model.light_specular.sum() == 0 and model.vis.headlight.diffuse.sum() == 0
    snapshot = illumination_snapshot(model, cfg, .5)
    assert snapshot["mode"] == "fixed_world_directional"
    assert not snapshot["camera_headlight_active"]
    assert snapshot["world_light_count"] == 1 and snapshot["light_stimulus_gain"] == .5
    assert not snapshot["background_scaled_by_light_gain"]
    np.testing.assert_allclose(model.light_dir[0], np.asarray(cfg.direction_world)/np.linalg.norm(cfg.direction_world))
    with pytest.raises(ValueError, match="already installed"):
        add_world_illumination(spec, cfg)


def test_illumination_leaves_fixture_geometry_and_dynamics_exact():
    xml = '''<mujoco><option timestep=".001"/><worldbody>
      <geom type="plane" size="5 5 .1"/>
      <body pos="0 0 1"><freejoint/><geom type="sphere" size=".2" mass="1"/></body>
      </worldbody></mujoco>'''
    legacy_spec, light_spec = mujoco.MjSpec.from_string(xml), mujoco.MjSpec.from_string(xml)
    add_world_illumination(light_spec, WorldIlluminationConfig())
    legacy, lit = legacy_spec.compile(), light_spec.compile()
    for name in ("body_pos", "body_quat", "body_mass", "body_inertia", "geom_pos", "geom_quat", "geom_size",
                 "geom_friction", "geom_solref", "geom_solimp", "qpos0", "dof_damping", "dof_armature"):
        np.testing.assert_array_equal(getattr(legacy, name), getattr(lit, name))
    legacy_data, lit_data = mujoco.MjData(legacy), mujoco.MjData(lit)
    for _ in range(500):
        mujoco.mj_step(legacy, legacy_data)
        mujoco.mj_step(lit, lit_data)
    np.testing.assert_array_equal(legacy_data.qpos, lit_data.qpos)
    np.testing.assert_array_equal(legacy_data.qvel, lit_data.qvel)
    assert legacy_data.ncon == lit_data.ncon


def test_rgb_scaling_world_shadow_and_head_rotation():
    spec = mujoco.MjSpec.from_string('''<mujoco><visual>
      <global offwidth="258" offheight="258"/><quality offsamples="0" shadowsize="2048"/>
      <map znear=".001"/></visual><worldbody>
      <geom type="plane" size="5 5 .1" rgba=".8 .8 .8 1"/>
      <geom type="box" pos="0 0 1" size=".5 .5 1" rgba=".4 .4 .4 1"/>
      </worldbody></mujoco>''')
    cfg = WorldIlluminationConfig()
    add_world_illumination(spec, cfg)
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    origin = np.array([3., -4., 5.])
    targets = np.array([[-1.5, 0, 0], [.8, -.2, 0]])  # lit floor / cast shadow
    world_axes = targets-origin
    world_axes /= np.linalg.norm(world_axes, axis=1, keepdims=True)
    pose_values = []
    for angles in ((0, 0, 0), (21, -38, 63)):
        rotation = Rotation.from_euler("xyz", angles, degrees=True).as_matrix()
        with CubeEyeSampler(model, world_axes @ rotation) as sampler:
            values = []
            for gain in (1., .5, 0.):
                model.light_ambient[:] = np.asarray(cfg.ambient_rgb)*gain
                model.light_diffuse[:] = np.asarray(cfg.diffuse_rgb)*gain
                values.append(sampler.sample(data, EyePose(origin, rotation)))
            pose_values.append(values)
    values = np.array(pose_values)
    assert values[0, 0, 0].min() > 100  # explicit world light illuminates floor
    assert values[0, 0, 1].max() < 40   # stable world-relative shadow
    np.testing.assert_allclose(values[:, 1], .5*values[:, 0], atol=1)
    assert not values[:, 2].any()
    np.testing.assert_allclose(values[0], values[1], atol=1)
