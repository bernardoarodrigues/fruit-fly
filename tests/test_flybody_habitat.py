"""Habitat configuration and food/wall boundary tests without optional physics."""
from dataclasses import asdict
import unittest

from fruitfly.flybody_bridge import FlyBodyConfig, FlyBodyRuntime
from fruitfly.flybody_habitat import FlyBodyHabitatConfig


class HabitatBoundaryTests(unittest.TestCase):
    def test_opt_in_and_serialization(self):
        self.assertIsNone(FlyBodyConfig().habitat)
        c = FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat={})
        self.assertEqual(asdict(c)["habitat"]["inner_size_mm"],(30.,24.))
        with self.assertRaises(ValueError):
            FlyBodyConfig(habitat={})

    def test_invalid_geometry_and_initial_clearance(self):
        for values in ({"inner_size_mm":[0,20]}, {"inner_size_mm":[6,20]}, {"center_mm":[14,0]},
                       {"wall_height_mm":0}, {"wall_thickness_mm":float("nan")}, {"center_mm":[True,0]}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                FlyBodyHabitatConfig(**values)
        for invalid in (False,True,1,"box"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat=invalid)

    def test_regions_must_fit_inside(self):
        offset = FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat={"center_mm":[1,-1]})
        self.assertEqual(offset.habitat.center_mm,(1.,-1.))
        with self.assertRaisesRegex(ValueError,"food"):
            FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat={},food_position_mm=(14,0))
        with self.assertRaisesRegex(ValueError,"water"):
            FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat={},water_radius_mm=9)

    def test_wall_contacts_do_not_count_as_food(self):
        runtime = object.__new__(FlyBodyRuntime)
        runtime.config = FlyBodyConfig(reference_mode="rolling",horizon_s=None,habitat={},food_position_mm=(0,0))
        wall = {"active":True,"is_tarsal":True,"leg":"LF","position_mm":[0,0,0]}
        state = {"contacts":[],"habitat":{"wall_contacts":[wall]}}
        self.assertFalse(any(runtime._contacts(state,"food").values()))
        state["contacts"] = [wall]
        self.assertTrue(runtime._contacts(state,"food")["LF"])


if __name__=="__main__":
    unittest.main()
