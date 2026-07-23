from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import ArmController, MockTransport, SafetyError, SerialTransport


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
    parser.add_argument("--serial", help="Arduino serial port; omit for safe mock mode")
    args = parser.parse_args()
    token = os.getenv("ARM_BRIDGE_TOKEN")
    transport = SerialTransport(args.serial) if args.serial else MockTransport()
    mode = f"serial {args.serial}" if args.serial else "mock"
    print(f"Arm bridge listening on http://{args.host}:{args.port} ({mode})")
    ThreadingHTTPServer((args.host, args.port), make_handler(ArmController(transport), token)).serve_forever()


if __name__ == "__main__":
    main()

