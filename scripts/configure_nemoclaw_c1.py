#!/usr/bin/env python3
"""Render, preview, and optionally apply the narrow C1 NemoClaw policy."""

from __future__ import annotations

import argparse
import ipaddress
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "nemoclaw/policies/arduino-arm-bridge.yaml.template"


def validate_host(value: str) -> str:
    address = ipaddress.ip_address(value)
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise argparse.ArgumentTypeError("use the exact non-loopback host IP")
    return value


def render(host: str, port: int, binary: str) -> str:
    if not binary.startswith("/") or any(c.isspace() for c in binary):
        raise ValueError("request binary must be an absolute path without whitespace")
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__BRIDGE_HOST__", host)
        .replace("__BRIDGE_PORT__", str(port))
        .replace("__REQUEST_BINARY__", binary)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure NemoClaw C1 policy")
    parser.add_argument("sandbox", help="NemoClaw sandbox name")
    parser.add_argument("--host", required=True, type=validate_host)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--request-binary", default="/usr/bin/curl")
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply after a successful dry-run; without this flag only preview",
    )
    parser.add_argument("--output", type=Path, help="Also save rendered policy here")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    try:
        policy = render(args.host, args.port, args.request_binary)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_text(policy, encoding="utf-8")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8") as handle:
        handle.write(policy)
        handle.flush()
        base = [
            "nemoclaw", args.sandbox, "policy", "add",
            "--from-file", handle.name,
        ]
        subprocess.run(base + ["--dry-run"], check=True)
        if args.apply:
            subprocess.run(base + ["--yes"], check=True)
            print("Policy applied. Verify with: nemoclaw", args.sandbox, "policy-list")
        else:
            print("Dry-run passed; rerun with --apply after reviewing the preview.")


if __name__ == "__main__":
    main()
