"""Localhost-only web console that keeps the bridge token server-side."""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import SafetyError
from .secure_server import load_token
from .vision_flow import VisionFlow
from .realsense_playback import default_playback
from .realsense_live import LiveRGBDContract, RealSenseLiveSource, default_live
from .depth_filter_graph import FilterGraphContract
from .librealsense_filters import (
    LibrealsenseBagRunner, NativeParityContract, SDKContractFixtureRunner,
)


ASSETS = Path(__file__).with_name("console_assets")
SESSION_TTL_SECONDS = 3600
MAX_BODY_BYTES = 4096


class ConsoleState:
    def __init__(self, bridge_url: str, bridge_token: str, pairing_code: str, live: LiveRGBDContract | None = None, native_runner=None):
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token
        self.pairing_code = pairing_code
        self.pairing_used = False
        self.pairing_attempts = 0
        self.sessions: dict[str, float] = {}
        self.lock = threading.Lock()
        self.vision = VisionFlow()
        self.playback = default_playback()
        self.live = live or default_live()
        self.filters = FilterGraphContract()
        self.native_parity = NativeParityContract(
            self.playback.source, native_runner or SDKContractFixtureRunner(self.playback.source)
        )

    def pair(self, code: str) -> str | None:
        with self.lock:
            if self.pairing_used or self.pairing_attempts >= 8:
                return None
            self.pairing_attempts += 1
            if not secrets.compare_digest(code, self.pairing_code):
                return None
            session = secrets.token_urlsafe(32)
            self.sessions[session] = time.monotonic() + SESSION_TTL_SECONDS
            self.pairing_used = True
            return session

    def authenticated(self, session: str | None) -> bool:
        if not session:
            return False
        with self.lock:
            expires = self.sessions.get(session, 0)
            if expires <= time.monotonic():
                self.sessions.pop(session, None)
                return False
            return True

    def bridge_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.bridge_url + path,
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.bridge_token}",
                **({"Content-Type": "application/json"} if data else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get("error", str(exc))
            except (json.JSONDecodeError, UnicodeDecodeError):
                detail = str(exc)
            raise SafetyError(f"bridge rejected request: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SafetyError(f"bridge unavailable: {exc}") from exc


def make_console_handler(state: ConsoleState, port: int):
    expected_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "ArmConsole/1.0"

        def _json(self, status: int, body: dict, cookie: str | None = None) -> None:
            encoded = json.dumps(body, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _asset(self, name: str, content_type: str) -> None:
            path = ASSETS / name
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'self'",
            )
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _bytes(self, content: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _session(self) -> str | None:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get("arm_console_session")
            return morsel.value if morsel else None

        def _require_session(self) -> bool:
            if state.authenticated(self._session()):
                return True
            self._json(401, {"ok": False, "error": "pairing required"})
            return False

        def _read_json(self) -> dict:
            if self.headers.get_content_type() != "application/json":
                raise SafetyError("Content-Type must be application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise SafetyError("request body must be 1-4096 bytes")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise SafetyError("request body must be a JSON object")
            return value

        def _origin_allowed(self) -> bool:
            return self.headers.get("Origin") in expected_origins

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/":
                return self._asset("index.html", "text/html; charset=utf-8")
            if path == "/app.js":
                return self._asset("app.js", "text/javascript; charset=utf-8")
            if path == "/styles.css":
                return self._asset("styles.css", "text/css; charset=utf-8")
            if path in {"/vision/bench-a.svg", "/vision/bench-b.svg"}:
                return self._asset(path.removeprefix("/"), "image/svg+xml")
            if path == "/api/session":
                return self._json(200, {"ok": True, "paired": state.authenticated(self._session())})
            if path == "/api/status":
                if not self._require_session():
                    return
                try:
                    return self._json(200, state.bridge_request("GET", "/status"))
                except SafetyError as exc:
                    return self._json(502, {"ok": False, "error": str(exc)})
            if path == "/api/realsense/live/status":
                if not self._require_session():
                    return
                return self._json(200, state.live.status())
            if path == "/api/realsense/live/color.jpg":
                if not self._require_session():
                    return
                try:
                    return self._bytes(state.live.color_jpeg(), "image/jpeg")
                except SafetyError as exc:
                    return self._json(404, {"ok": False, "error": str(exc)})
            if path == "/api/realsense/live/depth.png":
                if not self._require_session():
                    return
                query = parse_qs(parsed.query)
                view = query.get("view", [""])[0]
                mask = query.get("mask", ["1"])[0] != "0"
                try:
                    return self._bytes(state.live.depth_visual_png(view, mask), "image/png")
                except SafetyError as exc:
                    return self._json(404, {"ok": False, "error": str(exc)})
            if path == "/api/vision/scenes":
                if not self._require_session():
                    return
                return self._json(200, state.vision.scenes())
            if path == "/api/realsense/recording":
                if not self._require_session():
                    return
                return self._json(200, state.playback.metadata())
            self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if not self._origin_allowed():
                return self._json(403, {"ok": False, "error": "origin rejected"})
            try:
                body = self._read_json()
                if self.path == "/api/pair":
                    session = state.pair(str(body.get("code", "")))
                    if not session:
                        return self._json(401, {"ok": False, "error": "invalid or used pairing code"})
                    cookie = (
                        f"arm_console_session={session}; HttpOnly; SameSite=Strict; "
                        f"Path=/; Max-Age={SESSION_TTL_SECONDS}"
                    )
                    return self._json(200, {"ok": True, "paired": True}, cookie)
                if not self._require_session():
                    return
                if self.path == "/api/vision/select":
                    return self._json(200, state.vision.select(
                        str(body.get("scene_id", "")), str(body.get("object_id", ""))
                    ))
                if self.path == "/api/vision/confirm":
                    return self._json(200, state.vision.confirm(
                        str(body.get("plan_id", "")), body.get("human_confirmed") is True
                    ))
                if self.path == "/api/vision/execute":
                    status = state.bridge_request("GET", "/status")
                    return self._json(200, state.vision.execute(
                        str(body.get("plan_id", "")), status,
                        lambda payload: state.bridge_request("POST", "/command", payload),
                    ))
                if self.path == "/api/realsense/frame":
                    return self._json(200, state.playback.frame(int(body.get("index", -1))))
                if self.path == "/api/realsense/deproject":
                    return self._json(200, state.playback.deproject(
                        int(body.get("index", -1)), int(body.get("x", -1)), int(body.get("y", -1))
                    ))
                if self.path == "/api/realsense/live/start":
                    return self._json(200, state.live.start())
                if self.path == "/api/realsense/live/poll":
                    result = state.live.poll()
                    return self._json(200 if result["ok"] else 503, result)
                if self.path == "/api/realsense/live/stop":
                    return self._json(200, state.live.stop())
                if self.path == "/api/realsense/filters/apply":
                    return self._json(200, state.filters.run(
                        state.playback.source, int(body.get("index", -1)), body.get("config")
                    ))
                if self.path == "/api/realsense/filters/native-compare":
                    return self._json(200, state.native_parity.compare(
                        int(body.get("index", -1)), body.get("config")
                    ))
                if self.path != "/api/command":
                    return self._json(404, {"ok": False, "error": "not found"})
                command = body.get("command")
                if command not in {
                    "startup_check", "arm", "disarm", "move", "home", "stop",
                    "reset_estop", "heartbeat",
                }:
                    raise SafetyError("unsupported console command")
                return self._json(200, state.bridge_request("POST", "/command", body))
            except (SafetyError, json.JSONDecodeError, ValueError) as exc:
                return self._json(400, {"ok": False, "error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            print(f"[arm-console] {self.address_string()} {fmt % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Localhost-only robot arm console")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token-file")
    parser.add_argument("--realsense-live", action="store_true", help="Use a connected RealSense instead of the CI live source")
    parser.add_argument("--realsense-bag", help="Absolute .bag path for native SDK filter comparison")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    try:
        token = load_token(args.token_file)
    except (OSError, SafetyError) as exc:
        parser.error(str(exc))
    pairing_code = f"{secrets.randbelow(1_000_000):06d}"
    live = LiveRGBDContract(RealSenseLiveSource()) if args.realsense_live else default_live()
    native_runner = LibrealsenseBagRunner(args.realsense_bag) if args.realsense_bag else None
    state = ConsoleState(args.bridge_url, token, pairing_code, live, native_runner)
    print(f"Robot arm console: http://127.0.0.1:{args.port}")
    print(f"One-time pairing code: {pairing_code}")
    ThreadingHTTPServer(
        ("127.0.0.1", args.port), make_console_handler(state, args.port)
    ).serve_forever()


if __name__ == "__main__":
    main()
