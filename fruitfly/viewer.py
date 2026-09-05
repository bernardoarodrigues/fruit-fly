"""Local scientific viewer. The spawned worker owns MuJoCo and its GL context.

Run with ``python -m fruitfly.viewer --port 8765``. No browser build is needed.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import multiprocessing as mp
from pathlib import Path
import queue
import signal
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit


WEB_ROOT = Path(__file__).with_name("web")
CAMERAS = ("overview", "follow", "side")


def _viewer_settings(config: dict[str, Any]) -> dict[str, Any]:
    """Validate before allocating a worker, so bad configuration is actionable."""
    viewer = config.get("viewer", {})
    if not isinstance(viewer, dict):
        raise ValueError("viewer configuration must be an object")
    settings = {"paused": False, "camera": "follow", "speed": 1.0,
                "step_seconds": .01, "fps": 8.0} | viewer
    if not isinstance(settings["paused"], bool):
        raise ValueError("viewer.paused must be boolean")
    if settings["camera"] not in CAMERAS:
        raise ValueError("viewer.camera must be overview, follow or side")
    for name, minimum, maximum in (("speed", .05, 10), ("step_seconds", .001, .05), ("fps", 1, 30)):
        value = settings[name]
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value)
                or not (minimum <= value <= maximum or name == "speed" and value == 0)):
            raise ValueError(f"viewer.{name} must be finite and in [{minimum}, {maximum}]"
                             + (", or 0 for maximum speed" if name == "speed" else ""))
        settings[name] = float(value)
    return settings


def _publish(channel: Any, packet: dict[str, Any]) -> None:
    """Bounded latest-state channel: discard a stale frame, never accumulate video."""
    while True:
        try:
            channel.put(packet, timeout=0.1)
            return
        except queue.Full:
            try:
                channel.get_nowait()
            except queue.Empty:
                pass


def _jpeg(rgb: Any) -> bytes:
    from PIL import Image

    output = io.BytesIO()
    Image.fromarray(rgb).convert("RGB").save(output, "JPEG", quality=86)
    return output.getvalue()


def _json_safe(value: Any) -> Any:
    """Normalize numpy telemetry without allowing NaN to break browser JSON."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    return str(value)


def _bounded_step(telemetry: dict, quantum: float, interval: float | None):
    """Respect a declared finite trial without crossing its coupling grid."""
    horizon = (telemetry.get("physics") or {}).get("horizon_s")
    if horizon is None:
        return quantum, False, None
    current = telemetry.get("t_s")
    if (not isinstance(horizon, (int, float)) or not math.isfinite(horizon) or horizon <= 0
            or not isinstance(current, (int, float)) or not math.isfinite(current)
            or interval is None):
        raise ValueError("Finite trial requires a valid horizon, clock and coupling interval")
    if current > horizon + 1e-9:
        raise RuntimeError("Runtime clock exceeds its declared trial horizon")
    ticks = round(max(0., horizon - current) / interval)
    if not math.isclose(current + ticks * interval, horizon, abs_tol=1e-9, rel_tol=0):
        raise ValueError("Trial horizon cuts a coupling interval")
    return min(quantum, ticks * interval), ticks == 0, float(horizon)


def _simulation_worker(
    config: dict[str, Any], commands: Any, updates: Any,
    runner_factory: Callable[..., Any] | None = None,
) -> None:
    """Only this spawned process imports/constructs the physical simulation."""
    runner = None
    viewer = _viewer_settings(config)
    paused, camera, speed = viewer["paused"], viewer["camera"], viewer["speed"]
    quantum = viewer["step_seconds"]
    frame_period = 1.0 / viewer["fps"]
    telemetry: dict[str, Any] = {}
    sequence = 0
    last_frame = 0.0
    needs_frame = True
    stopping = False
    pending_command = None
    trial_complete = False
    trial_limit_s = None
    try:
        if runner_factory is None:
            from .simulation import SimulationRunner
            runner_factory = SimulationRunner
        runner = runner_factory(config)
        interval = getattr(runner, "coupling_s", None)
        if interval is not None:
            if not math.isfinite(interval) or not 0 < interval <= .05:
                raise ValueError("Simulation coupling interval must be finite and in (0, 0.05] seconds")
            # Preserve the runtime's sensor/readout schedule for every valid
            # coupling interval, including ones larger than the requested chunk.
            quantum = interval * max(1, math.floor(quantum / interval + 1e-9))
        while not stopping:
            started = time.monotonic()
            while True:
                try:
                    if pending_command is None:
                        command = commands.get_nowait()
                    else:
                        command, pending_command = pending_command, None
                except queue.Empty:
                    break
                kind = command["type"]
                if kind == "stop":
                    stopping = True
                    break
                if kind == "pause":
                    paused = command["paused"]
                elif kind == "camera":
                    camera = command["camera"]
                elif kind == "speed":
                    speed = command["value"]
                else:
                    result = runner.control(command)
                    if isinstance(result, dict):
                        telemetry = result
                    if kind == "reset":
                        telemetry = {} if not isinstance(result, dict) else result
                needs_frame = True
            if stopping:
                break
            if not telemetry:
                telemetry = runner.advance(0.0)
            if not paused:
                step, trial_complete, trial_limit_s = _bounded_step(telemetry, quantum, interval)
                if step > 0:
                    telemetry = runner.advance(step)
                    _, trial_complete, trial_limit_s = _bounded_step(telemetry, quantum, interval)
                if trial_complete:
                    paused = True
                    needs_frame = True
            elif needs_frame:
                # advance(0) retrieves state without advancing a paused simulation.
                telemetry = runner.advance(0.0)
                _, trial_complete, trial_limit_s = _bounded_step(telemetry, quantum, interval)
            now = time.monotonic()
            if needs_frame or (not paused and now - last_frame >= frame_period):
                frame = _jpeg(runner.render(camera))
                sequence += 1
                _publish(updates, {
                    "status": "paused" if paused else "running",
                    "paused": paused, "camera": camera, "speed": speed,
                    "trial_complete": trial_complete, "trial_limit_s": trial_limit_s,
                    "telemetry": _json_safe(telemetry), "frame": frame,
                    "telemetry_basis": "completed_advance", "frame_t_s": telemetry.get("t_s"),
                    "frame_sequence": sequence, "error": None,
                })
                last_frame = time.monotonic()
                needs_frame = False
            # Max speed is 0. All other values target simulated seconds / wall second.
            delay = 0.02 if paused else max(0.0, quantum / speed - (time.monotonic() - started)) if speed else 0.0
            if delay:
                # Pace accurately at slow targets, but wake immediately for controls.
                try:
                    pending_command = commands.get(timeout=delay)
                except queue.Empty:
                    pass
    except BaseException as exc:
        failure = None
        # A failed body step can leave native and neural clocks beyond the last
        # completed advance. Read only its cached receipt; do not render or
        # reconstruct an observation from potentially invalid physical state.
        diagnostics = getattr(runner, "failure_diagnostics", None)
        if diagnostics is not None:
            try:
                failure = diagnostics()
            except Exception as diagnostic_error:
                exc.add_note("Failure diagnostics unavailable: " + str(diagnostic_error))
        _publish(updates, {"status": "error", "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc(), "telemetry": _json_safe(telemetry),
                           "telemetry_basis": "last_completed_advance" if telemetry else "unavailable",
                           "failure_diagnostics": _json_safe(failure)})
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                traceback.print_exc()
        if stopping:
            _publish(updates, {"status": "stopped"})


def validate_command(command: Any) -> dict[str, Any]:
    if not isinstance(command, dict):
        raise ValueError("Control must be a JSON object.")
    kind = command.get("type")
    if kind == "pause" and isinstance(command.get("paused"), bool):
        return {"type": kind, "paused": command["paused"]}
    if kind == "reset":
        return {"type": kind}
    if kind == "camera" and command.get("camera") in CAMERAS:
        return {"type": kind, "camera": command["camera"]}
    if kind == "ablation" and isinstance(command.get("enabled"), bool):
        return {"type": kind, "enabled": command["enabled"]}
    if kind == "synaptic_output" and command.get("group") == "grooming_sensory" and isinstance(command.get("blocked"), bool):
        return {"type": kind, "group": "grooming_sensory", "blocked": command["blocked"]}
    if kind in ("speed", "stimulus"):
        value = command.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            if kind == "speed" and (value == 0 or 0.05 <= value <= 10):
                return {"type": kind, "value": float(value)}
            if kind == "stimulus" and command.get("name") in ("odor", "light") and 0 <= value <= 2:
                return {"type": kind, "name": command["name"], "value": float(value)}
    raise ValueError("Unsupported control or invalid value.")


class SimulationService:
    def __init__(self, config: dict[str, Any], runner_factory: Callable[..., Any] | None = None):
        viewer = _viewer_settings(config)
        context = mp.get_context("spawn")
        self.commands = context.Queue(maxsize=64)
        self.updates = context.Queue(maxsize=2)
        self.process = context.Process(target=_simulation_worker,
            args=(config, self.commands, self.updates, runner_factory), name="fruitfly-simulation", daemon=True)
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.state: dict[str, Any] = {
            "status": "initializing", "paused": viewer["paused"],
            "camera": viewer["camera"], "speed": viewer["speed"],
            "telemetry": {}, "frame_sequence": 0, "error": None, "updated_at": None,
            "frame_t_s": None, "frame_updated_at": None,
            "telemetry_basis": "unavailable", "failure_diagnostics": None,
            "observed_realtime_factor": None,
        }
        self.frame: bytes | None = None
        self.monitor = threading.Thread(target=self._monitor, name="fruitfly-observer", daemon=True)

    def start(self) -> None:
        self.process.start()
        self.monitor.start()

    def _monitor(self) -> None:
        previous_frame = None
        while not self.stopped.is_set():
            try:
                packet = self.updates.get(timeout=0.25)
            except queue.Empty:
                if self.process.exitcode is not None:
                    with self.lock:
                        if self.state["status"] not in ("error", "stopped"):
                            self.state.update(status="error", error=f"Simulation worker exited (code {self.process.exitcode}).")
                    break
                continue
            with self.lock:
                frame = packet.pop("frame", None)
                trace = packet.pop("traceback", None)
                if frame is not None:
                    self.frame = frame
                    self.state["frame_updated_at"] = time.time()
                    wall_time = time.monotonic()
                    sim_time = packet.get("telemetry", {}).get("t_s")
                    running = packet.get("status") == "running" and isinstance(sim_time, (int, float))
                    factor = None
                    if running and previous_frame is not None:
                        previous_sim, previous_wall = previous_frame
                        if sim_time >= previous_sim and wall_time > previous_wall:
                            factor = (sim_time - previous_sim) / (wall_time - previous_wall)
                    self.state["observed_realtime_factor"] = factor
                    previous_frame = (sim_time, wall_time) if running else None
                self.state.update(packet)
                self.state["updated_at"] = time.time()
            if trace:
                print(trace, flush=True)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            state = dict(self.state)
        state["worker_alive"] = self.process.is_alive()
        state["frame_age_seconds"] = None if state["frame_updated_at"] is None else time.time() - state["frame_updated_at"]
        return state

    def image(self) -> tuple[bytes | None, int]:
        with self.lock:
            return self.frame, self.state["frame_sequence"]

    def command(self, command: Any) -> None:
        validated = validate_command(command)
        if self.stopped.is_set() or not self.process.is_alive() or self.snapshot()["status"] in ("error", "stopped"):
            raise RuntimeError("Simulation worker is not running. See its error and restart the viewer.")
        try:
            self.commands.put_nowait(validated)
        except queue.Full as exc:
            raise RuntimeError("Control queue is full; wait for the simulation to catch up.") from exc

    def close(self) -> None:
        if self.stopped.is_set():
            return
        if self.process.pid is not None:
            try:
                self.commands.put({"type": "stop"}, timeout=0.1)
            except queue.Full:
                pass
            self.process.join(timeout=8)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=3)
        self.stopped.set()
        if self.monitor.is_alive():
            self.monitor.join(timeout=1)
        for channel in (self.commands, self.updates):
            channel.close()
            channel.cancel_join_thread()


def make_handler(service: SimulationService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: Any) -> None:
            pass

        def _local_host(self) -> bool:
            # Origin alone is insufficient if an external hostname is rebound
            # to loopback: both Host and Origin would name the attacker's site.
            port = self.server.server_port
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if port == 80:
                allowed.update(("127.0.0.1", "localhost"))
            if self.headers.get("Host", "").lower() not in allowed:
                self._json(HTTPStatus.FORBIDDEN, {"error": "Use the local viewer hostname."})
                return False
            return True

        def _reply(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body:
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _json(self, status: int, value: Any) -> None:
            self._reply(status, json.dumps(value, allow_nan=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if not self._local_host():
                return
            path = urlsplit(self.path).path
            if path == "/api/state":
                self._json(HTTPStatus.OK, service.snapshot())
            elif path == "/api/frame":
                frame, sequence = service.image()
                self._reply(HTTPStatus.OK if frame else HTTPStatus.NO_CONTENT, frame or b"", "image/jpeg",
                            {"X-Frame-Sequence": str(sequence)})
            else:
                assets = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("style.css", "text/css; charset=utf-8")}
                if path not in assets:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                    return
                filename, mime = assets[path]
                self._reply(HTTPStatus.OK, (WEB_ROOT / filename).read_bytes(), mime,
                    {"Content-Security-Policy": "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"})

        def do_POST(self) -> None:
            if not self._local_host():
                return
            if urlsplit(self.path).path != "/api/control":
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self._json(HTTPStatus.FORBIDDEN, {"error": "Controls require the viewer origin."})
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Use application/json."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Invalid request length.")
                command = json.loads(self.rfile.read(length))
                service.command(command)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            else:
                self._json(HTTPStatus.ACCEPTED, {"accepted": True})
    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, help="JSON simulation configuration")
    parser.add_argument("--paused", action="store_true", help="Initialize without advancing time")
    parser.add_argument("--open", action="store_true", help="Open the viewer in your default browser")
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config else {}
    if not isinstance(config, dict):
        parser.error("Configuration must be a JSON object.")
    if args.paused:
        config.setdefault("viewer", {})["paused"] = True
    service = SimulationService(config)
    server = None
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(service))
        server.daemon_threads = True
        service.start()
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"Fruit fly lab: {url}\nCtrl+C stops the server and simulation worker.", flush=True)
        if args.open:
            import webbrowser
            webbrowser.open(url)
        def request_stop(_signum: int, _frame: Any) -> None:
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, request_stop)
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        service.close()


if __name__ == "__main__":
    main()
