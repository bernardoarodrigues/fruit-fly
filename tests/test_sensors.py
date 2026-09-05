import copy
import numpy as np
import pytest

from fruitfly.sensors import SensoryEncoder, SensoryParameters, MotorDecoder, TasteEncoder


class AnatomyFixture:
    groups = {("ORN_DM1", "L"): [0, 1], ("ORN_DM1", "R"): [2, 3],
              ("DNg97", None): [4, 5], ("DNa01", "L"): [6],
              ("DNa01", "R"): [7], ("MN9", None): [8, 9],
              ("DNp01", None): [10, 11]}

    def select(self, types, side=None):
        return np.array([i for t in types for i in self.groups.get((t, side), [])], dtype=np.int32)


def observation(odor=(0, 0), **extra):
    return {"antenna_odor": list(odor), "physiology": {"hunger": .5},
            "taste_food": False, "taste_water": False, **extra}


def test_local_input_is_independent_of_privileged_world_data():
    a, b = SensoryEncoder(AnatomyFixture()), SensoryEncoder(AnatomyFixture())
    first = observation((1e8, 2e8))
    poisoned = copy.deepcopy(first)
    poisoned.update(pose={"position_mm": [1e10, -1e10, 100]}, food_position_mm=[0, 0],
                    target_bearing=2.0, food_distance=0.0)
    np.testing.assert_array_equal(a.encode(first, .005).rates_hz, b.encode(poisoned, .005).rates_hz)


def test_bilateral_response_adapts_and_recovers_without_cross_side_leak():
    encoder = SensoryEncoder(AnatomyFixture())
    first = encoder.encode(observation((1e8, 0)), .005).rates_hz.copy()
    for _ in range(200):
        last = encoder.encode(observation((1e8, 0)), .005).rates_hz.copy()
    assert last[0] < first[0] and last[0] > last[2]
    assert last[2] == first[2] == 5
    encoder.reset()
    np.testing.assert_array_equal(encoder.encode(observation((1e8, 0)), .005).rates_hz, first)


@pytest.mark.parametrize("parameters", [{"odor_half_response": 0}, {"adaptation_tau_s": 0},
                                      {"hunger_gain": float("nan")}, {"odor_baseline_hz": -1}])
def test_invalid_transduction_rejected(parameters):
    with pytest.raises(ValueError):
        SensoryParameters(**parameters)


class Counts:
    def __init__(self, firing):
        self.firing = firing

    def counts(self, indices):
        return np.array([self.firing.get(int(i), 0) for i in indices])


def test_motor_readout_requires_spikes_and_muting_preserves_rate_measurement():
    motor = MotorDecoder(AnatomyFixture())
    assert motor.decode(Counts({}), .1, observation())["behavior"] == "rest"
    spikes = Counts({4: 10, 5: 10})
    assert motor.decode(spikes, .1, observation())["behavior"] == "walk"
    assert motor.decode(spikes, .1, observation(), muted=True)["behavior"] == "rest"
    assert motor.rates["forward"] > 50


def test_feeding_needs_neural_readout_and_physical_contact():
    motor = MotorDecoder(AnatomyFixture())
    assert motor.decode(Counts({8: 5, 9: 5}), .1, observation())["behavior"] == "rest"
    assert motor.decode(Counts({8: 5, 9: 5}), .1, observation(taste_food=True))["behavior"] == "feed"
    motor.reset()
    assert motor.decode(Counts({}), .1, observation(taste_food=True))["behavior"] == "rest"


class TasteAnatomyFixture:
    def select(self, types, side=None, nerve=None):
        assert types == ["LgAG2", "LgLG4"]
        return np.array([{"ProLN": 0, "MesoLN": 1, "MetaLN": 2}[nerve] + (3 if side == "R" else 0)])


def test_taste_is_leg_specific_and_does_not_borrow_water_channels():
    encoder = TasteEncoder(TasteAnatomyFixture())
    contacts = {leg: leg == "LF" for leg in encoder.groups}
    result = encoder.encode({"food_contact_by_leg": contacts, "taste_water": True})
    np.testing.assert_array_equal(result.indices, [0])
    assert encoder.last_rates == dict(LF=100, LM=0, LH=0, RF=0, RM=0, RH=0)
    contacts["LF"] = False
    result = encoder.encode({"food_contact_by_leg": contacts, "taste_water": True})
    assert len(result.indices) == 0
    with pytest.raises(ValueError, match="six named"):
        encoder.encode({"food_contact_by_leg": {"LF": True}})
