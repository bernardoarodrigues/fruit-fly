import unittest

import numpy as np
import pandas as pd

from fruitfly.proprioception import ClubMovementEncoder, FECO_TYPES, LEGS, NERVES


class FixtureConnectome:
    def __init__(self):
        rows = []
        for family, types in FECO_TYPES.items():
            for cell_type in types:
                for leg in LEGS:
                    rows.append(dict(type=cell_type, rootSide=leg[0], entryNerve=NERVES[leg[1]],
                                     synonyms="FeCO " + family))
        self.neurons = pd.DataFrame(rows)
        self.neuron_ids = np.arange(len(rows)) + 1_000_000
        self.manifest = {"dataset": "test-fixture"}

    def select(self, types, side, nerve):
        return np.flatnonzero(self.neurons.type.isin(types) & self.neurons.rootSide.eq(side)
                              & self.neurons.entryNerve.eq(nerve)).astype(np.int32)


class ProprioceptionTests(unittest.TestCase):
    def test_leg_and_bidirectional_selectivity_without_target_data(self):
        graph = FixtureConnectome()
        encoder = ClubMovementEncoder(graph, max_rate_hz=20, half_speed_rad_s=2)
        observation = {"proprioception": {"joint_velocities_rad_s": {"tibia_pitch": [2, 0, 0, 0, 0, 0]}}}
        positive = encoder.encode(observation)
        np.testing.assert_array_equal(positive.indices, encoder.groups["LF"])
        np.testing.assert_allclose(positive.rates_hz, 10)
        observation["proprioception"]["joint_velocities_rad_s"]["tibia_pitch"][0] = -2
        negative = encoder.encode(observation)
        np.testing.assert_array_equal(positive.indices, negative.indices)
        np.testing.assert_array_equal(positive.rates_hz, negative.rates_hz)
        self.assertTrue(graph.neurons.iloc[positive.indices].type.isin(FECO_TYPES["club"]).all())

    def test_no_input_at_zero_velocity_and_no_unsupported_alias(self):
        graph = FixtureConnectome()
        encoder = ClubMovementEncoder(graph, max_rate_hz=20, half_speed_rad_s=2)
        drive = encoder.encode({"proprioception": {"joint_velocities_rad_s": {"tibia_pitch": [0] * 6}}})
        self.assertEqual(len(drive.indices), 0)
        graph.neurons.loc[graph.neurons.type.eq("SNpp40"), "synonyms"] = None
        with self.assertRaises(ValueError):
            ClubMovementEncoder(graph, max_rate_hz=20, half_speed_rad_s=2)


if __name__ == "__main__":
    unittest.main()
