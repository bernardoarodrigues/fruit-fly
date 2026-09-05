"""Lightweight boundary tests: no optional worker/environment allocation."""
import unittest
from unittest.mock import Mock
import numpy as np
from fruitfly.flybody_bridge import FlyBodyConfig, FlyBodyRuntime, map_drive, LEGS


class FlyBodyBoundaryTests(unittest.TestCase):
    def test_unsupported_clocks_and_capabilities_rejected(self):
        for values in ({"physics_dt_s": .0001}, {"horizon_s": 3}, {"enable_vision": True},
                       {"reference_mode": "unknown"}, {"reference_mode": "rolling"},
                       {"reference_mode": "bounded", "horizon_s": None},
                       {"enable_grooming": True}, {"world_illumination": {}},
                       {"initial_position_mm": [1, 0, 1.278]}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                FlyBodyConfig(**values)
        with self.assertRaises(TypeError):
            FlyBodyConfig(unsupported_control=True)

    def test_rolling_mode_requires_explicit_unbounded_horizon(self):
        config = FlyBodyConfig(reference_mode="rolling", horizon_s=None)
        self.assertIsNone(config.horizon_s)
        self.assertEqual(config.reference_mode, "rolling")
        self.assertEqual(FlyBodyConfig().horizon_s, 2.)

    def test_drive_map_and_policy_mute(self):
        np.testing.assert_array_equal(map_drive(.5, .5, "walk")[1:], [10, 0])
        np.testing.assert_array_equal(map_drive(1, 1, "walk")[1:], [20, 0])
        np.testing.assert_array_equal(map_drive(-1.2, 1.2, "walk")[1:], [0, 2])
        np.testing.assert_array_equal(map_drive(1.2, -1.2, "walk")[1:], [0, -2])
        np.testing.assert_array_equal(map_drive(1, 1, "rest")[1:], [0, 0])
        for invalid in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                map_drive(invalid, 1, "walk")

    def test_taste_requires_actual_active_tarsal_contact(self):
        body = object.__new__(FlyBodyRuntime)
        body.config = FlyBodyConfig(food_position_mm=(0, 0))
        contact = {"leg": "LF", "active": True, "is_tarsal": True, "position_mm": [1, 1, 0]}
        result = body._contacts({"contacts": [contact]}, "food")
        self.assertEqual(set(result), set(LEGS))
        self.assertEqual([k for k, v in result.items() if v], ["LF"])
        for changed in ({"active": False}, {"is_tarsal": False}, {"position_mm": [4, 0, 0]}):
            with self.subTest(changed=changed):
                self.assertFalse(any(body._contacts({"contacts": [{**contact, **changed}]}, "food").values()))

    def test_transport_failure_is_terminal(self):
        body = object.__new__(FlyBodyRuntime)
        body._transport_failed = None
        body._proc = Mock()
        body._proc.poll.return_value = None
        body._exchange = Mock(side_effect=TimeoutError("delayed reply"))
        with self.assertRaises(TimeoutError):
            body._rpc("advance")
        body._proc.terminate.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "terminal"):
            body._rpc("reset")
        body._exchange.assert_called_once()

    def test_failed_partial_step_keeps_native_state_without_full_physiology_tick(self):
        body = object.__new__(FlyBodyRuntime)
        body.config = FlyBodyConfig()
        body._state = {"native_time_s": 0.}
        body.physiology = Mock()
        body._cache_observation = Mock()
        state = {"native_time_s": .0002, "finite": True, "contacts": [], "velocity_world_mm_s": [1., 0., 0.]}
        body._accept_state(state, failed=True)
        self.assertEqual(body.time_s, .0002)
        self.assertEqual(body.diagnostics(), state)
        body.physiology.advance.assert_not_called()


if __name__ == "__main__":
    unittest.main()
