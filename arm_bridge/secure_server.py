"""C1 entry point: authenticated host bridge reachable from OpenShell only."""

from __future__ import annotations

import argparse
import ipaddress
import os
from http.server import ThreadingHTTPServer
from pathlib import Path

from .core import SafetyError
from .server import build_controller, make_handler


def load_token(token_file: str | None = None) -> str:
    token = os.getenv("ARM_BRIDGE_TOKEN", "").strip()
    if token_file:
        token = Path(token_file).expanduser().read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SafetyError(
            "C1 requires ARM_BRIDGE_TOKEN or --token-file with at least 32 characters"
        )
    return token


def validate_c1_host(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise SafetyError("--host must be an explicit host IPv4/IPv6 address") from exc
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise SafetyError(
            "--host must be the exact non-loopback address reachable by OpenShell"
        )
    return host


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authenticated NemoClaw C1 host bridge"
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-file")
    parser.add_argument("--robot", choices=["arduino4", "so101"], default="arduino4")
    parser.add_argument("--serial", help="Hardware serial port; omit for mock mode")
    parser.add_argument("--robot-id")
    parser.add_argument("--allow-real-motion", action="store_true")
    parser.add_argument("--require-startup-checklist", action="store_true")
    parser.add_argument("--watchdog-timeout", type=float, default=2.0)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    if args.watchdog_timeout <= 0:
        parser.error("--watchdog-timeout must be positive")
    try:
        validate_c1_host(args.host)
        token = load_token(args.token_file)
        controller = build_controller(args)
    except (OSError, SafetyError) as exc:
        parser.error(str(exc))
    mode = f"{args.robot} serial {args.serial}" if args.serial else f"{args.robot} mock"
    print(
        f"C1 bridge listening on http://{args.host}:{args.port} ({mode}); "
        "only authenticated /command requests are accepted"
    )
    ThreadingHTTPServer(
        (args.host, args.port), make_handler(controller, token)
    ).serve_forever()


if __name__ == "__main__":
    main()
