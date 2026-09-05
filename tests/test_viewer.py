"""Viewer plumbing tests; FakeRunner is deliberately not a biological simulation."""

from __future__ import annotations

import io
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from fruitfly.viewer import SimulationService, _json_safe, make_handler, validate_command


class FakeRunner:
    """Deterministic test double, used only to test IPC and HTTP plumbing."""

    def __init__(self, config):
        if config.get("test_constructor_error"):
            raise ValueError("Deliberate test-only initialization failure")
        self.t = 0.0
        self.odor = 1.0
        self.ablated = False

    def advance(self, sim_seconds):
        self.t += sim_seconds
        return {"t_s": self.t, "behavior": "test double", "senses": {"odor": [self.odor, self.odor]},
                "neural": {"ablated": self.ablated}, "warnings": ["TEST DOUBLE: no neural or physical simulation"]}

    def render(self, camera):
        pixels = np.zeros((16, 24, 3), dtype=np.uint8)
        pixels[:, :, {"overview": 0, "follow": 1, "side": 2}[camera]] = 200
        return pixels

    def control(self, command):
        if command["type"] == "reset":
            self.t = 0.0
        elif command["type"] == "ablation":
            self.ablated = command["enabled"]
        elif command["type"] == "stimulus":
            self.odor = command["value"]

    def close(self):
        pass


class QuantizedRunner(FakeRunner):
    """Contract fixture: rejects chunks that cut across sensor coupling steps."""

    def __init__(self, config):
        super().__init__(config)
        self.coupling_s = config["coupling_s"]

    def advance(self, sim_seconds):
        if not np.isclose(round(sim_seconds / self.coupling_s) * self.coupling_s,
                          sim_seconds, atol=1e-12, rtol=0):
            raise ValueError("Duration cuts a coupling interval")
        return super().advance(sim_seconds)


def wait_for(service, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = service.snapshot()
        if predicate(state):
            return state
        time.sleep(0.02)
    raise AssertionError(f"State did not satisfy predicate: {service.snapshot()}")


class ViewerValidationTests(unittest.TestCase):
    def test_invalid_viewer_configuration_fails_before_worker_allocation(self):
        for viewer in [[], {"camera": "bogus"}, {"paused": "false"}, {"speed": -1},
                       {"step_seconds": float("nan")}, {"fps": 0}, {"fps": True}]:
            with self.subTest(viewer=viewer), self.assertRaises(ValueError):
                SimulationService({"viewer": viewer}, runner_factory=FakeRunner)

    def test_commands_validate_ranges_and_shapes(self):
        self.assertEqual(validate_command({"type": "stimulus", "name": "odor", "value": 0}),
                         {"type": "stimulus", "name": "odor", "value": 0.0})
        self.assertEqual(validate_command({"type": "camera", "camera": "side"}), {"type": "camera", "camera": "side"})
        source_control = {"type": "synaptic_output", "group": "grooming_sensory", "blocked": True}
        self.assertEqual(validate_command(source_control), source_control)
        for invalid in [[], None, {"type": "stop"}, {"type": "pause", "paused": 1},
                        {"type": "speed", "value": True}, {"type": "speed", "value": float("nan")},
                        {"type": "stimulus", "name": "odor", "value": -1},
                        {"type": "stimulus", "name": "unknown", "value": 1},
                        {"type": "ablation", "enabled": "false"}, {"type": "camera", "camera": "../../file"},
                        {"type": "synaptic_output", "group": "grooming_sensory", "blocked": "false"},
                        {"type": "synaptic_output", "group": "unknown", "blocked": True}]:
            with self.subTest(command=invalid), self.assertRaises(ValueError):
                validate_command(invalid)

    def test_numpy_and_nonfinite_telemetry_is_valid_json(self):
        value = _json_safe({"values": np.array([1.0, float("nan"), float("inf")]), "count": np.int64(3)})
        self.assertEqual(json.loads(json.dumps(value, allow_nan=False)), {"values": [1.0, None, None], "count": 3})


class ViewerWorkerTests(unittest.TestCase):
    def test_chunks_respect_runtime_coupling_interval(self):
        # Covers an interval above the requested chunk and a non-divisor of it.
        for interval in (.02, .003):
            with self.subTest(interval=interval):
                service = SimulationService({"coupling_s": interval,
                    "viewer": {"step_seconds": .01, "fps": 30, "speed": .5}},
                    runner_factory=QuantizedRunner)
                service.start()
                try:
                    state = wait_for(service, lambda s: s["telemetry"].get("t_s", 0) >= .03
                                     and s["observed_realtime_factor"] is not None)
                    self.assertEqual(state["status"], "running")
                    self.assertEqual(state["speed"], .5)
                    self.assertGreater(state["observed_realtime_factor"], 0)
                    self.assertLess(state["observed_realtime_factor"], .8)
                finally:
                    service.close()

    def test_pause_controls_reset_camera_and_graceful_close(self):
        service = SimulationService({"viewer": {"paused": True, "fps": 30}}, runner_factory=FakeRunner)
        service.start()
        try:
            initial = wait_for(service, lambda state: state["status"] == "paused")
            self.assertEqual(initial["telemetry"]["t_s"], 0)
            image, sequence = service.image()
            self.assertGreater(sequence, 0)
            self.assertEqual(Image.open(io.BytesIO(image)).size, (24, 16))
            service.command({"type": "pause", "paused": False})
            wait_for(service, lambda state: state["telemetry"].get("t_s", 0) > 0.05)
            service.command({"type": "pause", "paused": True})
            paused = wait_for(service, lambda state: state["status"] == "paused")
            time.sleep(0.12)
            self.assertEqual(service.snapshot()["telemetry"]["t_s"], paused["telemetry"]["t_s"])
            service.command({"type": "stimulus", "name": "odor", "value": 0.25})
            wait_for(service, lambda state: state["telemetry"]["senses"]["odor"][0] == 0.25)
            service.command({"type": "ablation", "enabled": True})
            wait_for(service, lambda state: state["telemetry"]["neural"]["ablated"])
            service.command({"type": "camera", "camera": "side"})
            wait_for(service, lambda state: state["camera"] == "side")
            image, _ = service.image()
            rgb = np.asarray(Image.open(io.BytesIO(image)))
            self.assertGreater(rgb[:, :, 2].mean(), 190)
            service.command({"type": "reset"})
            wait_for(service, lambda state: state["telemetry"].get("t_s") == 0)
        finally:
            service.close()
        self.assertFalse(service.process.is_alive())
        with self.assertRaises(RuntimeError):
            service.command({"type": "reset"})
        service.close()  # Cleanup is idempotent.

    def test_worker_exception_is_visible_and_does_not_restart(self):
        service = SimulationService({"test_constructor_error": True}, runner_factory=FakeRunner)
        service.start()
        try:
            error = wait_for(service, lambda state: state["status"] == "error")
            self.assertIn("Deliberate test-only initialization failure", error["error"])
            wait_for(service, lambda state: not state["worker_alive"])
            self.assertIsNone(service.image()[0])
        finally:
            service.close()


class ViewerHTTPTests(unittest.TestCase):
    def test_static_state_jpeg_and_origin_command_validation(self):
        service = SimulationService({"viewer": {"paused": True}}, runner_factory=FakeRunner)
        service.start()
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            wait_for(service, lambda state: state["status"] == "paused")
            with urlopen(base + "/") as response:
                self.assertIn(b"One fly. A world to explore.", response.read())
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            with urlopen(base + "/api/state") as response:
                self.assertEqual(json.load(response)["telemetry"]["t_s"], 0)
            with urlopen(base + "/api/frame") as response:
                self.assertEqual(response.headers["Content-Type"], "image/jpeg")
                self.assertEqual(Image.open(io.BytesIO(response.read())).size, (24, 16))
            request = Request(base + "/api/control", data=json.dumps({"type": "pause", "paused": False}).encode(),
                              headers={"Content-Type": "application/json", "Origin": base})
            with urlopen(request) as response:
                self.assertEqual(response.status, 202)
            wait_for(service, lambda state: state["status"] == "running")
            bad_origin = Request(base + "/api/control", data=b'{"type":"reset"}',
                                 headers={"Content-Type": "application/json", "Origin": "https://foreign.example"})
            with self.assertRaises(HTTPError) as error:
                urlopen(bad_origin)
            self.assertEqual(error.exception.code, 403)
            for path, body in [("/api/state", None), ("/api/control", b'{"type":"reset"}')]:
                rebound_host = Request(base + path, data=body, headers={
                    "Content-Type": "application/json", "Host": "foreign.example",
                    "Origin": "http://foreign.example"})
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    urlopen(rebound_host)
                self.assertEqual(error.exception.code, 403)
            invalid = Request(base + "/api/control", data=b'{"type":"speed","value":-1}',
                              headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as error:
                urlopen(invalid)
            self.assertEqual(error.exception.code, 400)
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/../viewer.py")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            service.close()


if __name__ == "__main__":
    unittest.main()
