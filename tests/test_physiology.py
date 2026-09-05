import unittest

from fruitfly.physiology import Physiology, PhysiologyConfig, ResourcePatch


class PhysiologyTests(unittest.TestCase):
    def test_long_run_conserves_resources_and_depletes_finite_patches(self):
        state = Physiology()
        food = ResourcePatch("food", "food", .15)
        water = ResourcePatch("water", "water", .1)
        for _ in range(10000):
            state.advance(.01, speed_mm_s=0, food_contact=True, water_contact=True,
                          feed_requested=True, food=food, water=water)
        self.assertEqual(food.remaining, 0)
        self.assertEqual(water.remaining, 0)
        for residual in state.balance_residuals(food, water).values():
            self.assertAlmostEqual(residual, 0, places=11)
        self.assertGreater(state.food_ingested, 0)
        self.assertGreaterEqual(state.crop, 0)
        self.assertLessEqual(state.energy, state.config.energy_capacity)

    def test_ingestion_requires_every_gate(self):
        for speed, contact, request in ((2, True, True), (0, False, True), (0, True, False)):
            with self.subTest(speed=speed, contact=contact, request=request):
                state = Physiology()
                food, water = ResourcePatch("f", "food", 1), ResourcePatch("w", "water", 1)
                state.advance(1, speed_mm_s=speed, food_contact=contact,
                              water_contact=contact, feed_requested=request,
                              food=food, water=water)
                self.assertEqual((food.remaining, water.remaining), (1, 1))

    def test_crop_and_hydration_capacity(self):
        state = Physiology(PhysiologyConfig(assimilation_per_s=0,
                    basal_energy_per_s=0, basal_water_loss_per_s=0))
        food, water = ResourcePatch("f", "food", 10), ResourcePatch("w", "water", 10)
        for _ in range(10):
            state.advance(1, speed_mm_s=0, food_contact=True, water_contact=True,
                          feed_requested=True, food=food, water=water)
        self.assertAlmostEqual(state.crop, state.config.crop_capacity)
        self.assertAlmostEqual(state.hydration, state.config.hydration_capacity)
        self.assertAlmostEqual(state.food_ingested, state.config.crop_capacity)
        self.assertAlmostEqual(state.water_ingested, .25)

    def test_negative_inputs_rejected(self):
        with self.assertRaises(ValueError):
            ResourcePatch("f", "food", -1)
        with self.assertRaises(ValueError):
            PhysiologyConfig(assimilation_per_s=-1)
        food = ResourcePatch("f", "food", 1)
        with self.assertRaises(ValueError):
            food.take(float("nan"))


class BodyPhysicsTests(unittest.TestCase):
    """Integration checks exercise the actual compiled MuJoCo contact model."""

    def test_physical_contact_controls_resource_transfer(self):
        from fruitfly.body import BodyConfig, BodyRuntime
        with BodyRuntime(config=BodyConfig(food_position_mm=(-4, 0))) as body:
            observed = body.advance(.05, behavior="feed")
            self.assertTrue(observed["taste_food"])
            self.assertFalse(observed["taste_water"])
            self.assertTrue(any(observed["food_contact_by_leg"].values()))
            self.assertFalse(any(observed["water_contact_by_leg"].values()))
            self.assertEqual(list(observed["food_contact_by_leg"]), ["LF", "LM", "LH", "RF", "RM", "RH"])
            self.assertGreater(observed["physiology"]["food_ingested"], 0)
            self.assertEqual(observed["physiology"]["water_ingested"], 0)
            for residual in body.snapshot()["resource_balance"].values():
                self.assertAlmostEqual(residual, 0, places=11)
        with BodyRuntime() as body:
            observed = body.advance(.05, behavior="feed")
            self.assertFalse(observed["taste_food"])
            self.assertEqual(observed["physiology"]["food_ingested"], 0)

    def test_split_advance_reset_and_cached_forces_match_reference(self):
        import numpy as np
        from fruitfly.body import BodyRuntime
        from flygym_demo.complex_terrain import HybridControllerObservation
        with BodyRuntime(seed=7) as body:
            for _ in range(5):
                body.advance(.02)
                reference = HybridControllerObservation.from_sim(body.sim, body.fly.name)
                cached = body._controller_observation()
                np.testing.assert_array_equal(reference.tarsus5_z, cached.tarsus5_z)
                np.testing.assert_allclose(reference.stumbling_contact_forces,
                                           cached.stumbling_contact_forces, atol=1e-12)
            state = body.data.qpos.copy()
            body.reset(seed=7)
            body.advance(.1)
            np.testing.assert_array_equal(state, body.data.qpos)
            self.assertEqual(body.observe()["t_s"], .1)
            self.assertNotIn("food_position_mm", body.observe())
            self.assertNotIn("resources", body.observe())

    def test_drive_is_bounded_and_bad_timing_rejected(self):
        from fruitfly.body import BodyRuntime
        with BodyRuntime() as body:
            observed = body.advance(.001, 100, -100)
            self.assertEqual(observed["motor"]["drive"], [1.2, -1.2])
            with self.assertRaises(ValueError):
                body.advance(.00015)
            with self.assertRaises(ValueError):
                body.advance(.001, float("nan"), 1)

    def test_standing_support_includes_distal_tarsi(self):
        import numpy as np
        from fruitfly.body import BodyRuntime
        with BodyRuntime() as body:
            proprioception = body.advance(.05, behavior="rest")["proprioception"]
            forces = np.asarray(proprioception["ground_force_by_leg"])
            self.assertTrue(np.isfinite(forces).all())
            self.assertGreater(forces[:, 2].sum(), 0)
            # An independent all-leg query covers tarsus3/4/5 support excluded
            # from the controller's tibia/tarsus1/tarsus2 stumble detector.
            segments = [segment for segment in body.fly.get_bodysegs_order()
                        if segment.name[:2] in body.controller.legs]
            reference = body.sim.get_bodysegment_contact_forces(body.fly.name, segments).sum(axis=0)
            np.testing.assert_allclose(forces.sum(axis=0), reference, atol=1e-12)
            self.assertEqual(len(proprioception["joint_angles_rad"]["tibia_pitch"]), 6)

    def test_optional_compound_eyes_sample_only_at_fixed_ticks(self):
        from fruitfly.body import BodyConfig, BodyRuntime
        import numpy as np
        with BodyRuntime(config=BodyConfig(enable_vision=True)) as body:
            initial = body.vision_readouts()
            self.assertEqual(initial.shape, (2, 721, 2))
            self.assertTrue(np.isfinite(initial).all())
            self.assertGreater(initial.max(), initial.min())
            body.advance(.01, behavior="rest")
            np.testing.assert_array_equal(initial, body.vision_readouts())
            self.assertEqual(body.observe()["vision"]["sample_t_s"], 0)
            body.advance(.01, behavior="rest")
            self.assertEqual(body.observe()["vision"]["sample_t_s"], .02)
            self.assertEqual(len(body.sim._intern_eye_camera_ids_by_fly[body.fly.name]), 2)


class OdorFieldTests(unittest.TestCase):
    def test_symmetry_and_residual_plume_after_source_stops(self):
        import numpy as np
        from fruitfly.body import PuffField
        field = PuffField((0, 0, .001), (0, 0, 0))
        field.advance(0, 1)
        sensors = np.array([[.002, 0, .001], [-.002, 0, .001]])
        c = field.sample(sensors, 0)
        self.assertGreater(c[0], 0)
        self.assertAlmostEqual(c[0], c[1])
        field.advance(.1, 0)
        self.assertTrue((field.sample(sensors, .1) > 0).all())
        field.advance(9, 0)
        np.testing.assert_array_equal(field.sample(sensors, 9), [0, 0])
        self.assertGreater(field.retired_mass, 0)


if __name__ == "__main__":
    unittest.main()


def test_light_control_changes_actual_eye_images_and_reset_restores():
    import numpy as np
    from fruitfly.body import BodyConfig, BodyRuntime
    with BodyRuntime(config=BodyConfig(enable_vision=True)) as body:
        initial = body.vision_readouts().copy()
        normal = initial.mean()
        body.set_stimulus('light', 0)
        body._sample_vision()  # identical pose isolates lighting from body motion
        dark = body.vision_readouts().mean()
        body.set_stimulus('light', 2)
        body._sample_vision()
        bright = body.vision_readouts().mean()
        assert dark < normal
        assert bright > normal
        body.reset()
        np.testing.assert_array_equal(body.vision_readouts(), initial)
