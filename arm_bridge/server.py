from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import ArmController, MockTransport, SafetyError, SerialTransport


def build_controller(args):
    """Build only the Arduino controller modes implemented by this bridge."""
    robot = getattr(args, "robot", "arduino4")
    if robot != "arduino4":
        raise SafetyError(
            f"robot {robot!r} is not supported by this bridge; "
            "SO-101 is currently a ROS 2 simulation scaffold"
        )

    if getattr(args, "require_startup_checklist", False):
        raise SafetyError(
            "startup-checklist enforcement is not implemented by this controller"
        )

    serial_port = getattr(args, "serial", None)
    allow_real_motion = bool(getattr(args, "allow_real_motion", False))
    if serial_port and not allow_real_motion:
        raise SafetyError("serial control requires explicit --allow-real-motion")
    if allow_real_motion and not serial_port:
        raise SafetyError("--allow-real-motion requires --serial")

    transport = SerialTransport(serial_port) if serial_port else MockTransport()
    return ArmController(transport)


def make_handler(controller: ArmController, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, body: dict):
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _authorized(self) -> bool:
            return not token or self.headers.get("Authorization") == f"Bearer {token}"

        def do_GET(self):
            if self.path in {"/health", "/status"}:
                self._json(200, controller.status())
            else:
                self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path != "/command":
                return self._json(404, {"ok": False, "error": "not found"})
            if not self._authorized():
                return self._json(401, {"ok": False, "error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    raise SafetyError("request body must be 1-4096 bytes")
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise SafetyError("request body must be a JSON object")
                self._json(200, controller.execute(request))
            except (SafetyError, json.JSONDecodeError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self._json(502, {"ok": False, "error": f"hardware error: {exc}"})

        def log_message(self, fmt, *args):
            print(f"[arm-bridge] {self.address_string()} {fmt % args}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="NemoClaw Arduino arm safety bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--robot", choices=("arduino4", "so101"), default="arduino4")
    parser.add_argument("--serial", help="Arduino serial port; omit for safe mock mode")
    parser.add_argument(
        "--allow-real-motion", action="store_true",
        help="explicitly allow serial hardware motion",
    )
    parser.add_argument(
        "--require-startup-checklist", action="store_true",
        help="request checklist enforcement (currently unsupported)",
    )
    args = parser.parse_args()
    try:
        controller = build_controller(args)
    except SafetyError as exc:
        parser.error(str(exc))
    token = os.getenv("ARM_BRIDGE_TOKEN")
    mode = f"serial {args.serial}" if args.serial else "mock"
    print(f"Arm bridge listening on http://{args.host}:{args.port} ({mode})")
    ThreadingHTTPServer(
        (args.host, args.port), make_handler(controller, token)
    ).serve_forever()


if __name__ == "__main__":
    main()
