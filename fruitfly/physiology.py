"""Conservative, explicitly abstract feeding and reserve bookkeeping.

All resource quantities use arbitrary normalized units. None of the defaults is
an empirical Drosophila metabolic constant. A nutrient unit transfers 1:1 from a
patch to crop to energy and finally to the spent-energy ledger.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class PhysiologyConfig:
    energy_capacity: float = 1.0
    hydration_capacity: float = 1.0
    crop_capacity: float = 0.3
    initial_energy: float = 0.55
    initial_hydration: float = 0.75
    food_intake_per_s: float = 0.08
    water_intake_per_s: float = 0.12
    assimilation_per_s: float = 0.04
    basal_energy_per_s: float = 0.0005
    locomotion_energy_per_mm: float = 0.00008
    basal_water_loss_per_s: float = 0.0003
    locomotion_water_loss_per_mm: float = 0.00004
    stationary_threshold_mm_s: float = 1.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and nonnegative")
        if min(self.energy_capacity, self.hydration_capacity, self.crop_capacity) <= 0:
            raise ValueError("Reserve capacities must be positive")
        if self.initial_energy > self.energy_capacity:
            raise ValueError("Initial energy exceeds capacity")
        if self.initial_hydration > self.hydration_capacity:
            raise ValueError("Initial hydration exceeds capacity")


@dataclass
class ResourcePatch:
    name: str
    kind: str
    initial: float
    remaining: float | None = None

    def __post_init__(self):
        if self.kind not in ("food", "water"):
            raise ValueError("Patch kind must be food or water")
        if not math.isfinite(self.initial) or self.initial < 0:
            raise ValueError("Initial resource must be finite and nonnegative")
        if self.remaining is None:
            self.remaining = self.initial
        if not math.isfinite(self.remaining) or not 0 <= self.remaining <= self.initial:
            raise ValueError("Remaining resource must lie within initial inventory")

    def take(self, amount: float) -> float:
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Requested resource must be finite and nonnegative")
        transferred = min(amount, self.remaining)
        self.remaining -= transferred
        return transferred

    @property
    def fraction(self) -> float:
        return self.remaining / self.initial if self.initial else 0.0


class Physiology:
    """Reserve state with feeding gated by explicit physical observations.

    Tarsal contact + stationary body + a feed command substitutes for an as-yet
    unimplemented proboscis/pump motor circuit. This is not a mouth-contact or
    digestion model. The caller must supply actual contact, never proximity.
    """

    def __init__(self, config: PhysiologyConfig | None = None):
        self.config = config or PhysiologyConfig()
        self.energy = self.config.initial_energy
        self.hydration = self.config.initial_hydration
        self.crop = 0.0
        self.food_ingested = 0.0
        self.water_ingested = 0.0
        self.energy_spent = 0.0
        self.water_lost = 0.0
        self.feeding_s = 0.0
        self.resting_s = 0.0

    @property
    def alive(self) -> bool:
        return self.energy > 0 and self.hydration > 0

    def advance(self, dt_s: float, *, speed_mm_s: float,
                food_contact: bool, water_contact: bool, feed_requested: bool,
                food: ResourcePatch, water: ResourcePatch) -> dict:
        if not math.isfinite(dt_s) or dt_s < 0:
            raise ValueError("dt_s must be finite and nonnegative")
        if not math.isfinite(speed_mm_s) or speed_mm_s < 0:
            raise ValueError("speed must be finite and nonnegative")
        if food.kind != "food" or water.kind != "water":
            raise ValueError("Resource arguments do not match their kinds")
        cfg = self.config
        stationary = speed_mm_s <= cfg.stationary_threshold_mm_s
        food_taken = water_taken = 0.0
        if stationary:
            self.resting_s += dt_s
        # A depleted animal does not recover by an externally forced feed action.
        if stationary and feed_requested and self.alive:
            if food_contact:
                food_taken = food.take(min(cfg.food_intake_per_s * dt_s,
                                           max(0.0, cfg.crop_capacity - self.crop)))
                self.crop += food_taken
                self.food_ingested += food_taken
            if water_contact:
                water_taken = water.take(min(cfg.water_intake_per_s * dt_s,
                    max(0.0, cfg.hydration_capacity - self.hydration)))
                self.hydration += water_taken
                self.water_ingested += water_taken
            if food_taken or water_taken:
                self.feeding_s += dt_s
        assimilated = min(self.crop, cfg.assimilation_per_s * dt_s,
                          max(0.0, cfg.energy_capacity - self.energy))
        self.crop -= assimilated
        self.energy += assimilated
        spent = min(self.energy, dt_s * (cfg.basal_energy_per_s +
                                        cfg.locomotion_energy_per_mm * speed_mm_s))
        lost = min(self.hydration, dt_s * (cfg.basal_water_loss_per_s +
                                         cfg.locomotion_water_loss_per_mm * speed_mm_s))
        self.energy -= spent
        self.hydration -= lost
        self.energy_spent += spent
        self.water_lost += lost
        return {"food_taken": food_taken, "water_taken": water_taken,
                "assimilated": assimilated, "energy_spent": spent,
                "water_lost": lost}

    def snapshot(self) -> dict:
        return {"energy": self.energy, "hydration": self.hydration,
                "capacities": {"energy": self.config.energy_capacity,
                               "hydration": self.config.hydration_capacity,
                               "crop": self.config.crop_capacity},
                "crop": self.crop, "hunger": 1 - self.energy / self.config.energy_capacity,
                "thirst": 1 - self.hydration / self.config.hydration_capacity,
                "alive": self.alive, "food_ingested": self.food_ingested,
                "water_ingested": self.water_ingested,
                "energy_spent": self.energy_spent, "water_lost": self.water_lost,
                "feeding_s": self.feeding_s, "resting_s": self.resting_s,
                "units": "normalized engineering resource units; uncalibrated"}

    def balance_residuals(self, food: ResourcePatch, water: ResourcePatch) -> dict:
        """Expected zero, independently of feeding/depletion/digestion history."""
        return {
            "nutrient": (food.remaining + self.crop + self.energy + self.energy_spent
                         - food.initial - self.config.initial_energy),
            "water": (water.remaining + self.hydration + self.water_lost
                      - water.initial - self.config.initial_hydration),
        }
