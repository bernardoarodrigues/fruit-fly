"""Persistent full-MaleCNS brain/body loop and recorded experiment runner."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from importlib.metadata import version, PackageNotFoundError

import numpy as np

from .body import BodyRuntime
from .data import Connectome, sha256
from .neural import LIFNetwork, LIFParameters, SparseDrive
from .sensors import SensoryEncoder, SensoryParameters, MotorDecoder, TasteEncoder


# Audited MaleCNS left AN JO-F anatomical union, in graph-index order. This is
# not an exact reproduction of the experimental driver or older JO-F subgroups.
GROOMING_SENSORY_IDS = (38160, 60335, 92767, 127912, 146314, 154152, 162166,
    170014, 179637, 188780, 200259, 224261, 227655, 231936, 237833, 240644,
    246484, 247028, 249842, 279391, 287167, 303968, 308970, 324453, 331081,
    336332, 343346, 360461, 403040, 407092, 426803, 482280, 166331476,
    197061019, 209837831, 238817349, 639242246, 793720445, 812830130,
    906350022, 975904445, 987117568)


class SimulationRunner:
    def __init__(self, config: dict | None = None):
        self.config = copy.deepcopy(config or {})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.run_dir = Path(self.config.get("run_dir", f"runs/{stamp}"))
        if self.run_dir.exists() and (not self.run_dir.is_dir() or any(self.run_dir.iterdir())):
            raise FileExistsError(f"Experiment directory is not empty: {self.run_dir}")
        self._trace = None
        self._closed = True
        self.seed = int(self.config.get("seed", 1))
        self.coupling_s = float(self.config.get("coupling_s", .005))
        if not np.isfinite(self.coupling_s) or not .0001 <= self.coupling_s <= .02:
            raise ValueError("Coupling interval must be in [0.0001, 0.02] seconds")
        graph_path = Path(self.config.get("connectome", "data/processed/malecns_v1"))
        if not (graph_path / "manifest.json").exists():
            raise FileNotFoundError("MaleCNS graph missing. Run: python -m fruitfly.data build")
        self.graph = Connectome.load(graph_path, verify=bool(self.config.get("verify_data", True)))
        self.neural_model = self.config.get("neural_model", "shiu")
        if self.neural_model == "shiu":
            self.brain = LIFNetwork.from_connectome(self.graph, seed=self.seed,
                parameters=LIFParameters(**self.config.get("neural_parameters", {})))
        elif self.neural_model == "conductance":
            from .conductance import ConductanceNetwork, ConductanceParameters
            self.brain = ConductanceNetwork.from_connectome(self.graph, seed=self.seed,
                parameters=ConductanceParameters(**self.config.get("neural_parameters", {})))
        else:
            raise ValueError("neural_model must be shiu or conductance")
        self._require_multiple(self.coupling_s, self.brain.parameters.dt_ms / 1000, "Coupling interval", "neural timestep")
        self.sensors = SensoryEncoder(self.graph, SensoryParameters(**self.config.get("sensory_parameters", {})))
        self.taste = TasteEncoder(self.graph, self.config.get("taste_rate_hz", 100)) if self.config.get("enable_taste", True) else None
        self.proprioceptor = None
        if self.config.get("proprioception") is not None:
            from .proprioception import ClubMovementEncoder
            self.proprioceptor = ClubMovementEncoder(self.graph, **self.config["proprioception"])
        self.motor = MotorDecoder(self.graph,
            enable_grooming=(self.config.get("body") or {}).get("enable_grooming", False),
            grooming_threshold_hz=self.config.get("grooming_threshold_hz", 10.))
        self.ablated = False
        self.outgoing_blocks = set()
        self.assay = self.config.get("assay", "sensory")
        if self.assay not in ("sensory", "motor_probe", "grooming_probe", "grooming_sensory_probe", "controller_only"):
            raise ValueError("Unknown assay")
        if self.assay in ("grooming_probe", "grooming_sensory_probe") and not self.motor.enable_grooming:
            raise ValueError("Grooming probe requires the optional grooming body")
        self.probe_hz = float(self.config.get("probe_hz", 40))
        if not np.isfinite(self.probe_hz) or not 0 <= self.probe_hz <= 300:
            raise ValueError("probe_hz must lie in [0,300]")
        self.probe_indices = (self.motor.groups["grooming_left"] if self.assay == "grooming_probe"
                              else self.graph.select(["DNg97"]))
        if self.assay == "grooming_sensory_probe":
            self.probe_indices = self.graph.select(["JO-FD1", "JO-FD2", "JO-FV"], side="L", nerve="AN")
            if tuple(self.graph.neuron_ids[self.probe_indices]) != GROOMING_SENSORY_IDS:
                raise ValueError("Grooming sensory assay requires the exact audited 42-cell left JO-F union")
            p = self.sensors.parameters
            if (p.odor_baseline_hz != 0 or p.odor_max_increment_hz != 0
                    or self.taste is not None or self.proprioceptor is not None):
                raise ValueError("Grooming sensory assay requires zero odor rates and disabled taste/proprioceptive inputs")
            if [len(self.sensors.groups[s]) for s in ("L", "R")] != [51, 54]:
                raise ValueError("Grooming sensory assay requires the audited 105 zero-rate ORNs first")
            if self.neural_model != "shiu" or self.brain.parameters != LIFParameters():
                raise ValueError("Grooming sensory assay requires the unchanged Shiu baseline")
        self.last_probe_spikes = self.total_probe_spikes = 0
        self.total_spikes = self.last_spikes = self.active_neurons = 0
        self.edge_visits = 0
        self.wall_s = 0.0
        self.last_action = {"behavior": "rest", "left": 0.0, "right": 0.0}
        self.events = []
        # Compile once without advancing the actual experiment state.
        self.brain.advance(self.brain.parameters.dt_ms, outputs=[])
        self.brain.reset(seed=self.seed)
        self.body = None
        try:
            self.body = BodyRuntime(seed=self.seed, config=self.config.get("body"))
            self._require_multiple(self.coupling_s, self.body.timestep, "Coupling interval", "body timestep")
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self._trace = (self.run_dir / "telemetry.jsonl").open("x", buffering=1)
            self._write_manifest()
            self._closed = False
        except BaseException:
            if self._trace is not None:
                self._trace.close()
            if self.body is not None:
                self.body.close()
            raise

    def _write_manifest(self):
        dependencies = {}
        for name in ("flygym", "mujoco", "numpy", "scipy", "numba", "pyarrow", "pandas"):
            try:
                dependencies[name] = version(name)
            except PackageNotFoundError:
                dependencies[name] = "unavailable"
        manifest = {"config": self.config, "seed": self.seed, "assay": self.assay,
                    "neural_model": self.neural_model,
                    "code_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
                    "dependencies": dependencies,
                    "connectome": self.graph.manifest, "graph_sha256": self.brain.graph_sha256,
                    "neural_parameters": asdict(self.brain.parameters),
                    "body_config": self.body.snapshot()["config"],
                    "wind_reference": self.body.snapshot()["wind_reference"],
                    "coupling_s": self.coupling_s, "sensory_parameters": asdict(self.sensors.parameters),
                    "sensory_groups": {k:self.graph.neuron_ids[v].tolist() for k,v in self.sensors.groups.items()},
                    "taste_groups": {k:self.graph.neuron_ids[v].tolist() for k,v in self.taste.groups.items()} if self.taste else {},
                    "taste_contact_event_rate_hz": self.taste.contact_rate_hz if self.taste else None,
                    "proprioceptive_groups": {k:self.graph.neuron_ids[v].tolist() for k,v in self.proprioceptor.groups.items()} if self.proprioceptor else {},
                    "proprioception_parameters": self.config.get("proprioception"),
                    "motor_groups": {k:self.graph.neuron_ids[v].tolist() for k,v in self.motor.groups.items()},
                    "grooming_threshold_hz": self.motor.grooming_threshold_hz if self.motor.enable_grooming else None,
                    "probe_ids": self.graph.neuron_ids[self.probe_indices].tolist(),
                    "probe_input_order_ids": (self.graph.neuron_ids[np.r_[self.sensors.groups["L"],
                        self.sensors.groups["R"], self.probe_indices]].tolist()
                        if self.assay == "grooming_sensory_probe" else None),
                    "probe_input_rate_hz": self.probe_hz,
                    "probe_source_limit": ("Imposed independent JO-F Poisson inputs; putative subgroup crosswalk; not physical touch, dust, wind or natural grooming"
                        if self.assay == "grooming_sensory_probe" else None),
                    "claim": "Full retained male graph with simplified dynamics and declared body/motor/sensory surrogates"}
        (self.run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    @staticmethod
    def _require_multiple(value, step, name, unit):
        count = round(value / step)
        if not np.isclose(count * step, value, atol=1e-10, rtol=0):
            raise ValueError(f"{name} must be an integer multiple of {unit} ({step:g} s)")
        return count

    def advance(self, sim_seconds: float) -> dict:
        if self._closed:
            raise RuntimeError("Simulation is closed")
        if not np.isfinite(sim_seconds) or sim_seconds < 0:
            raise ValueError("Duration must be finite and nonnegative")
        # Enforce fixed sensor/readout timing regardless of viewer chunk size.
        # A partial coupling interval would change the biological input schedule.
        count = self._require_multiple(sim_seconds, self.coupling_s, "Duration", "coupling interval")
        if count == 0:
            return self.snapshot()
        started = time.perf_counter()
        recent_active = set()
        self.last_spikes = 0
        self.last_probe_spikes = 0
        for _ in range(count):
            duration = self.coupling_s
            observation = self.body.observe()
            drive = self.sensors.encode(observation, duration)
            if self.taste is not None:
                taste_drive = self.taste.encode(observation)
                drive = SparseDrive(np.r_[drive.indices, taste_drive.indices],
                                    rates_hz=np.r_[drive.rates_hz, taste_drive.rates_hz])
            if self.proprioceptor is not None:
                movement_drive = self.proprioceptor.encode(observation)
                drive = SparseDrive(np.r_[drive.indices, movement_drive.indices],
                                    rates_hz=np.r_[drive.rates_hz, movement_drive.rates_hz])
            if self.assay in ("motor_probe", "grooming_probe", "grooming_sensory_probe"):
                # Imposed neural inputs; JO-F sensory probe never drives DNs.
                drive = SparseDrive(np.r_[drive.indices, self.probe_indices],
                                    rates_hz=np.r_[drive.rates_hz, np.full(len(self.probe_indices), self.probe_hz)])
            batch = self.brain.advance(duration * 1000, drive=drive)
            if not np.isfinite(self.brain.voltage_mv).all() or not np.isfinite(self.brain.synaptic_mv).all():
                raise RuntimeError("Nonfinite neural state; experiment stopped")
            action = self.motor.decode(batch, duration, observation, muted=self.ablated)
            if self.assay == "controller_only":
                action = {"behavior": "rest" if self.ablated else "walk", "left": 1.0, "right": 1.0}
            self.body.advance(duration, action["left"], action["right"], action["behavior"])
            if action["behavior"] != self.last_action["behavior"]:
                self.events.append({"t_s": self.body.time_s, "behavior": action["behavior"]})
                self.events = self.events[-20:]
            self.last_action = action
            self.last_spikes += batch.total_spikes
            self.total_spikes += batch.total_spikes
            if self.assay == "grooming_sensory_probe":
                source_spikes = int(batch.counts(self.probe_indices).sum())
                self.last_probe_spikes += source_spikes
                self.total_probe_spikes += source_spikes
            self.edge_visits += batch.traversed_edges
            recent_active.update(np.unique(batch.indices).tolist())
        self.wall_s += time.perf_counter() - started
        self.active_neurons = len(recent_active)
        state = self.snapshot()
        self._trace.write(json.dumps(state, allow_nan=False) + "\n")
        return state

    def snapshot(self) -> dict:
        observation = self.body.observe()
        world = self.body.snapshot()
        warnings = ["Female-derived body is a declared morphology surrogate for the male CNS.",
                    "Odor rates, LIF parameters and motor gains are uncalibrated approximations.",
                    "Tarsal sweet cells are mapped; labellar/pharyngeal, water, vision and proprioceptive neural mappings remain incomplete."]
        if self.taste is None:
            warnings.append("Tarsal taste input is disabled in this assay.")
        if self.proprioceptor:
            warnings.append("Optional FeCO club adapter encodes bidirectional tibia movement with configured, uncalibrated gain; hook/claw and vibration are unmapped.")
        if self.body.wind_reference is not None:
            warnings.append("Wind deflection is a quasistatic female-derived reference; it does not actuate antennae or drive neural inputs.")
        if self.neural_model == "shiu":
            warnings.append("Transferred current-based parameters produce implausible hyperpolarization in some male neurons; see motor calibration evidence.")
        else:
            warnings.append("Experimental conductance model: bounded reversals with uncalibrated synaptic/input gains; not the replicated Shiu dynamics.")
        if self.assay == "motor_probe":
            warnings.append("Motor calibration assay: DNg97 neurons receive direct Poisson stimulation.")
        elif self.assay == "grooming_probe":
            warnings.append("Grooming calibration: left DNg62/DNge078 receive direct stimulation and gate a female-derived motion template; not spontaneous sensory-driven grooming.")
        elif self.assay == "grooming_sensory_probe":
            warnings.append("Imposed left JO-F afferent activation: anatomical union with putative subgroup crosswalk, not an exact driver reproduction. No physical touch, dust or wind transduction and no natural grooming claim. Female-derived motor template; rigid antennae.")
            warnings.append("Shiu input events apply voltage jumps and disable refractory time for every listed input, including 105 zero-rate ORNs before the 42 JO-F cells. The input rate is not a measured afferent firing rate.")
            warnings.append("Left afferent input also recruits right grooming DNs in the neural assay. The selected left motor readout/template does not establish unilateral biological behavior.")
        elif self.assay == "controller_only":
            warnings.append("Controller-only baseline: movement is independent of neural outputs.")
        return {
            "status": "running", "t_s": self.body.time_s, "brain_t_s": self.brain.time_ms / 1000,
            "realtime_factor": self.body.time_s / self.wall_s if self.wall_s else 0,
            "behavior": observation["motor"]["mode"],
            "requested_behavior": self.last_action["behavior"], "assay": self.assay,
            "pose": observation["pose"], "physiology": observation["physiology"],
            "senses": {"odor": observation["antenna_odor"], "odor_rates_hz": self.sensors.last_rates.tolist(),
                       "taste_food": observation["taste_food"], "taste_water": observation["taste_water"],
                       "sweet_event_rates_hz": self.taste.last_rates.copy() if self.taste else {},
                       "club_event_rates_hz": self.proprioceptor.last_rates.copy() if self.proprioceptor else {},
                       "light": observation["light_intensity"]},
            "proprioception": observation["proprioception"], "motor": self.last_action,
            "neural": {"neurons": self.brain.n_neurons, "edges": self.brain.n_edges,
                       "active_neurons": self.active_neurons, "spikes": self.last_spikes,
                       "total_spikes": self.total_spikes, "output_rates": self.motor.rates.copy(),
                       "traversed_edges": self.edge_visits,
                       "voltage_mv": {"minimum": float(self.brain.voltage_mv.min()),
                                      "maximum": float(self.brain.voltage_mv.max()),
                                      "mean": float(self.brain.voltage_mv.mean())},
                       "ablated": self.ablated, "ablation_target": "motor readout",
                       "blocked_synaptic_outputs": sorted(self.outgoing_blocks),
                       "backend": f"Numba CPU sparse-event {self.neural_model} LIF",
                       "model": self.neural_model, "graph_sha256": self.brain.graph_sha256},
            "resources": world["resources"], "resource_balance": world["resource_balance"],
            "stimuli": world["stimuli"], "vision": observation["vision"],
            "wind": observation["wind"], "wind_reference": world["wind_reference"],
            "grooming": observation.get("grooming"),
            "grooming_sensory_probe": ({"source_group": "grooming_sensory",
                "source_neurons": len(self.probe_indices), "input_rate_hz_per_cell": self.probe_hz,
                "source_spikes": self.last_probe_spikes, "source_total_spikes": self.total_probe_spikes,
                "outgoing_blocked": "grooming_sensory" in self.outgoing_blocks,
                "input_kind": "imposed Poisson voltage events; not measured afferent firing or physical stimulation"}
                if self.assay == "grooming_sensory_probe" else None),
            "events": list(self.events), "warnings": warnings, "run_dir": str(self.run_dir),
        }

    def control(self, command: dict):
        kind = command.get("type")
        if kind == "reset":
            self.body.reset(seed=self.seed); self.brain.reset(seed=self.seed)
            for group in self.outgoing_blocks:
                self.brain.ablate(self._input_group(group))
            self.sensors.reset(); self.motor.reset()
            if self.taste:
                self.taste.reset()
            if self.proprioceptor:
                self.proprioceptor.reset()
            self.total_spikes = self.last_spikes = self.active_neurons = self.edge_visits = 0
            self.last_probe_spikes = self.total_probe_spikes = 0
            self.wall_s = 0.0
            self.last_action = {"behavior": "rest", "left": 0.0, "right": 0.0}
            self.events = []
        elif kind == "stimulus":
            self.body.set_stimulus(str(command["name"]), float(command["value"]))
        elif kind == "ablation":
            self.ablated = bool(command["enabled"])
        elif kind == "synaptic_output":
            group, blocked = command["group"], command["blocked"]
            if not isinstance(blocked, bool):
                raise ValueError("blocked must be boolean")
            indices = self._input_group(group)
            self.brain.ablate(indices, enabled=blocked)
            if blocked:
                self.outgoing_blocks.add(group)
            else:
                self.outgoing_blocks.discard(group)
        else:
            raise ValueError(f"Unsupported simulation control: {kind}")
        self._trace.write(json.dumps({"control": command, "t_s": self.body.time_s}) + "\n")
        return self.snapshot()

    def _input_group(self, group):
        if group == "grooming_sensory" and self.assay == "grooming_sensory_probe":
            return self.probe_indices
        encoder = {"odor": self.sensors, "sweet": self.taste,
                   "club": self.proprioceptor}.get(group)
        if encoder is None:
            raise ValueError("Requested sensory group is unknown or disabled")
        return np.unique(np.concatenate(list(encoder.groups.values())))

    def render(self, camera="follow"):
        return self.body.render(camera)

    def close(self):
        if self._closed:
            return
        try:
            state = self.snapshot()
            (self.run_dir / "final.json").write_text(json.dumps(state, indent=2) + "\n")
        finally:
            self._closed = True
            try:
                self._trace.close()
            finally:
                self.body.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--seconds", type=float, default=1)
    parser.add_argument("--assay", choices=("sensory", "motor_probe", "grooming_probe", "grooming_sensory_probe", "controller_only"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config else {}
    if args.assay:
        config["assay"] = args.assay
    runner = SimulationRunner(config)
    try:
        print(json.dumps(runner.advance(args.seconds), indent=2))
        from PIL import Image
        Image.fromarray(runner.render("follow")).save(runner.run_dir / "final.png")
    finally:
        runner.close()


if __name__ == "__main__":
    main()
