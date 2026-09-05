"""Conservative FeCO type catalogue and optional club movement input.

Only bidirectional tibia movement is encoded. Hook direction, claw position
bands, vibration tuning, force receptors and presynaptic state are unresolved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .neural import SparseDrive


LEGS = ("LF", "LM", "LH", "RF", "RM", "RH")
NERVES = {"F": "ProLN", "M": "MesoLN", "H": "MetaLN"}
FECO_TYPES = {
    "hook": ("SNpp39", "SNpp41"),
    "claw": ("SNpp50", "SNpp51"),
    "club": ("SNpp40", "SNpp47", "SNpp56", "SNpp57", "SNpp60"),
}


def feco_catalog(connectome) -> dict:
    """Produce exact IDs/counts, checking type-level synonym evidence exists."""
    rows = connectome.neurons
    result = {"dataset": connectome.manifest.get("dataset"), "families": {},
              "mapping_basis": "MaleCNS v1.0 exact type names; type-level FeCO synonyms; rootSide and entryNerve",
              "unknown_direction": ["hook", "claw"],
              "type_level_alias_propagation": True}
    for family, types in FECO_TYPES.items():
        for cell_type in types:
            aliases = rows.loc[rows.type.eq(cell_type), "synonyms"].dropna().astype(str)
            if not aliases.str.contains("FeCO " + family, regex=False).any():
                raise ValueError(f"No source synonym supports {cell_type} as FeCO {family}")
        by_leg = {}
        for leg in LEGS:
            indices = connectome.select(types, side=leg[0], nerve=NERVES[leg[1]])
            by_leg[leg] = {
                "count": len(indices), "indices": indices.tolist(),
                "body_ids": connectome.neuron_ids[indices].tolist(),
                "types": rows.iloc[indices].type.tolist(),
            }
        result["families"][family] = {"types": list(types), "legs": by_leg,
                                        "count": sum(x["count"] for x in by_leg.values())}
    return result


class ClubMovementEncoder:
    """Opt-in, uncalibrated event-rate proxy for typed FeCO club afferents.

    The caller must explicitly supply a rate ceiling and half-response angular
    speed. This saturating transfer is an engineering approximation, not a fit
    to calcium signals or measured firing rates. It sees only the actual local
    femur-tibia joint angular speed of each leg. No position/force/target input.
    """

    def __init__(self, connectome, *, max_rate_hz: float, half_speed_rad_s: float):
        if not np.isfinite(max_rate_hz) or not 0 <= max_rate_hz <= 1000:
            raise ValueError("Rate ceiling must be finite and in [0,1000] Hz")
        if not np.isfinite(half_speed_rad_s) or half_speed_rad_s <= 0:
            raise ValueError("Half-response angular speed must be finite and positive")
        self.max_rate_hz = float(max_rate_hz)
        self.half_speed_rad_s = float(half_speed_rad_s)
        self.catalog = feco_catalog(connectome)
        self.groups = {leg: np.asarray(group["indices"], dtype=np.int32)
                       for leg, group in self.catalog["families"]["club"]["legs"].items()}
        if any(len(group) == 0 for group in self.groups.values()):
            raise ValueError("Typed club group missing for at least one leg")
        self.last_rates = {leg: 0.0 for leg in LEGS}

    def encode(self, observation: dict) -> SparseDrive:
        velocities = np.asarray(observation["proprioception"]["joint_velocities_rad_s"]["tibia_pitch"], dtype=float)
        if velocities.shape != (6,) or not np.isfinite(velocities).all():
            raise ValueError("Tibia pitch velocity must be six finite values in LF,LM,LH,RF,RM,RH order")
        speed = np.abs(velocities)
        rates = self.max_rate_hz * speed / (self.half_speed_rad_s + speed)
        self.last_rates = dict(zip(LEGS, rates.tolist()))
        indices, values = [], []
        for leg, rate in zip(LEGS, rates):
            if rate > 0:
                indices.append(self.groups[leg])
                values.append(np.full(len(self.groups[leg]), rate))
        return SparseDrive(np.concatenate(indices) if indices else np.empty(0, dtype=np.int32),
                           rates_hz=np.concatenate(values) if values else np.empty(0))

    def reset(self):
        self.last_rates = {leg: 0.0 for leg in LEGS}


if __name__ == "__main__":
    from .data import Connectome
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectome", type=Path, default=Path("data/processed/malecns_v1"))
    parser.add_argument("--output", type=Path, default=Path("data/proprioception-mapping.json"))
    args = parser.parse_args()
    catalog = feco_catalog(Connectome.load(args.connectome))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")
    print(json.dumps({name: {leg: group["count"] for leg, group in family["legs"].items()}
                      for name, family in catalog["families"].items()}, indent=2))
