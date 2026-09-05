"""Local receptor-drive adapters with named anatomy and declared calibration gaps."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .neural import SparseDrive


class TasteEncoder:
    """Leg-specific appetitive input from actual tarsal food contact.

    Exact LgAG2/LgLG4 types follow Tastekin et al., Cell 2026,
    DOI 10.1016/j.cell.2026.08.016, Figs. 3J/4J. Event rate is an
    uncalibrated activation proxy; no labellar/pharyngeal cells are stimulated
    from foot contact, and tarsal water is explicitly unmapped.
    """

    def __init__(self, connectome, contact_rate_hz=100.0):
        if not np.isfinite(contact_rate_hz) or not 0 <= contact_rate_hz <= 300:
            raise ValueError("Taste event rate must be finite and in [0,300] Hz")
        self.contact_rate_hz = float(contact_rate_hz)
        self.groups = {side + leg: connectome.select(["LgAG2", "LgLG4"], side=side, nerve=nerve)
                       for side in ("L", "R")
                       for leg, nerve in (("F", "ProLN"), ("M", "MesoLN"), ("H", "MetaLN"))}
        if any(len(v) == 0 for v in self.groups.values()):
            raise ValueError("Leg-specific appetitive taste mapping is incomplete")
        self.last_rates = {leg: 0.0 for leg in self.groups}

    def encode(self, observation):
        contacts = observation["food_contact_by_leg"]
        if set(contacts) != set(self.groups) or any(not isinstance(v, (bool, np.bool_)) for v in contacts.values()):
            raise ValueError("Taste requires six named boolean physical leg contacts")
        self.last_rates = {leg: self.contact_rate_hz if contacts[leg] else 0.0 for leg in self.groups}
        # Omit inactive channels: a zero-rate target still changes the reference
        # activation model's refractory declaration and RNG assignment.
        active = [v for leg, v in self.groups.items() if self.last_rates[leg] > 0]
        indices = np.concatenate(active) if active else np.empty(0, dtype=np.int32)
        return SparseDrive(indices, rates_hz=np.full(len(indices), self.contact_rate_hz))

    def reset(self):
        self.last_rates = {leg: 0.0 for leg in self.groups}


@dataclass(frozen=True)
class SensoryParameters:
    odor_half_response: float = 1e8
    odor_baseline_hz: float = 5.0
    odor_max_increment_hz: float = 145.0
    adaptation_tau_s: float = .3
    adaptation_strength: float = 1.0
    hunger_gain: float = .5

    def __post_init__(self):
        values = vars(self)
        if any(not np.isfinite(v) or v < 0 for v in values.values()):
            raise ValueError("Sensory parameters must be finite and nonnegative")
        if self.odor_half_response <= 0 or self.adaptation_tau_s <= 0:
            raise ValueError("Odor half response and adaptation timescale must be positive")


class SensoryEncoder:
    """DM1/DM4 afferents receive independent left/right odor histories.

    Choice of DM1/DM4 follows Or42b/Or59b attraction experiments; numerical
    concentrations, tuning and adaptation here are uncalibrated approximations.
    This adapter never reads world coordinates or evaluator target positions.
    Taste/visual/proprioceptive neural mappings must be added from verified types;
    observing those physical signals alone does not imply their neural use.
    """

    def __init__(self, connectome, parameters=None):
        self.parameters = parameters or SensoryParameters()
        self.groups = {side: connectome.select(["ORN_DM1", "ORN_DM4"], side=side)
                       for side in ("L", "R")}
        if any(len(group) == 0 for group in self.groups.values()):
            raise ValueError("MaleCNS DM1/DM4 bilateral receptor groups missing")
        if np.intersect1d(self.groups["L"], self.groups["R"]).size:
            raise ValueError("Left and right receptor groups must be disjoint")
        self.adaptation = np.zeros(2)
        self.last_rates = np.zeros(2)
        self.last_concentration = np.zeros(2)

    def encode(self, observation: dict, duration_s: float) -> SparseDrive:
        p = self.parameters
        concentrations = np.asarray(observation["antenna_odor"], dtype=float)
        if concentrations.shape != (2,) or not np.isfinite(concentrations).all() or np.any(concentrations < 0):
            raise ValueError("Bilateral odor samples must be finite nonnegative values")
        if not np.isfinite(duration_s) or duration_s < 0:
            raise ValueError("Sensory duration must be finite and nonnegative")
        occupancy = concentrations / (p.odor_half_response + concentrations)
        hunger = float(np.clip(observation.get("physiology", {}).get("hunger", 0), 0, 1))
        rates = p.odor_baseline_hz + p.odor_max_increment_hz * occupancy * (
            1 + p.hunger_gain * hunger) / (1 + p.adaptation_strength * self.adaptation)
        self.adaptation += (occupancy - self.adaptation) * (1 - np.exp(-duration_s / p.adaptation_tau_s))
        self.last_rates, self.last_concentration = rates, concentrations
        indices = np.concatenate([self.groups["L"], self.groups["R"]])
        values = np.repeat(rates, [len(self.groups["L"]), len(self.groups["R"])])
        return SparseDrive(indices, rates_hz=values)

    def reset(self):
        self.adaptation[:] = 0
        self.last_rates[:] = 0
        self.last_concentration[:] = 0


class MotorDecoder:
    """Motor-interface baseline using anatomically identified descending outputs.

    Rate-to-drive gains and thresholds are engineering parameters. MN9 is a
    proboscis motor readout; the body's feed mode substitutes tarsal contact plus
    stationary ingestion until mouth/pump mechanics are implemented.
    """

    def __init__(self, connectome, tau_s=.05, *, enable_grooming=False, grooming_threshold_hz=10.):
        if not np.isfinite(tau_s) or tau_s <= 0:
            raise ValueError("Motor readout time constant must be positive")
        self.groups = {
            "forward": connectome.select(["DNg97"]),
            "turn_left": connectome.select(["DNa01", "DNa02"], side="L"),
            "turn_right": connectome.select(["DNa01", "DNa02"], side="R"),
            "feeding": connectome.select(["MN9"]),
            "escape": connectome.select(["DNp01"]),
        }
        if not isinstance(enable_grooming, bool):
            raise ValueError("enable_grooming must be boolean")
        if not np.isfinite(grooming_threshold_hz) or grooming_threshold_hz <= 0:
            raise ValueError("Grooming threshold must be finite and positive")
        self.enable_grooming = enable_grooming
        self.grooming_threshold_hz = grooming_threshold_hz
        if enable_grooming:
            # Exact Hampel aDN1/aDN2 crosswalk. Only a unilateral-left motor
            # template exists; the unrelated AOTU103m 'aDN' is excluded.
            self.groups["grooming_left"] = connectome.select(["DNg62", "DNge078"], side="L")
        if any(len(v) == 0 for v in self.groups.values()):
            raise ValueError("Required motor readout cell types missing")
        self.tau_s = tau_s
        self.rates = {key: 0.0 for key in self.groups}

    def decode(self, spike_batch, duration_s, observation, muted=False):
        if not np.isfinite(duration_s) or duration_s <= 0:
            raise ValueError("Motor readout duration must be finite and positive")
        alpha = 1 - np.exp(-duration_s / self.tau_s)
        for name, indices in self.groups.items():
            rate = float(spike_batch.counts(indices).mean() / duration_s)
            self.rates[name] += alpha * (rate - self.rates[name])
        if muted:
            return {"behavior": "rest", "left": 0.0, "right": 0.0}
        # This priority and rate threshold are declared engineering choices.
        # The body plays one measured template per request, with no raw-angle
        # or resource-location access from this neural readout.
        if self.enable_grooming and self.rates["grooming_left"] > self.grooming_threshold_hz:
            return {"behavior": "groom", "left": 0.0, "right": 0.0}
        # Contact only gates consumption, never long-range approach or steering.
        if self.rates["feeding"] > 5 and (observation["taste_food"] or observation["taste_water"]):
            return {"behavior": "feed", "left": 0.0, "right": 0.0}
        forward = np.clip(self.rates["forward"] / 40.0, 0, 1)
        turn = np.clip((self.rates["turn_left"] - self.rates["turn_right"]) / 50.0, -.6, .6)
        if forward < .05 and abs(turn) < .05:
            return {"behavior": "rest", "left": 0.0, "right": 0.0}
        # Turning sign is an explicit provisional decoder to calibrate in assays.
        return {"behavior": "walk", "left": float(np.clip(forward - turn, -1.2, 1.2)),
                "right": float(np.clip(forward + turn, -1.2, 1.2))}

    def reset(self):
        self.rates = {key: 0.0 for key in self.groups}
