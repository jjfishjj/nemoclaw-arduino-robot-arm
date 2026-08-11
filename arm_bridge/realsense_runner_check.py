"""Fail-closed provisioning checks for a RealSense self-hosted runner."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Callable


REQUIRED_LABELS = ("self-hosted", "linux", "x64", "realsense")


def _result(name: str, ok: bool, detail: str, *, required: bool = True) -> dict:
    return {"name": name, "ok": ok, "required": required, "detail": detail}


def inspect_runner(
    bag: Path,
    *,
    labels: list[str],
    min_free_gib: float = 5.0,
    require_usb: bool = False,
    which: Callable[[str], str | None] = shutil.which,
    disk_usage: Callable = shutil.disk_usage,
    usb_root: Path = Path("/dev/bus/usb"),
    package_version: Callable[[str], str] = importlib.metadata.version,
) -> dict:
    checks: list[dict] = []

    try:
        version = package_version("pyrealsense2")
        checks.append(_result("librealsense_python", True, f"pyrealsense2 {version}"))
    except importlib.metadata.PackageNotFoundError:
        checks.append(_result("librealsense_python", False, "pyrealsense2 is not installed"))

    cli = which("rs-enumerate-devices")
    checks.append(_result(
        "librealsense_cli", bool(cli),
        f"found {cli}" if cli else "rs-enumerate-devices is not on PATH",
    ))

    normalized = {label.strip().lower() for label in labels if label.strip()}
    missing = [label for label in REQUIRED_LABELS if label not in normalized]
    checks.append(_result(
        "runner_labels", not missing,
        "all required labels present" if not missing else f"missing labels: {', '.join(missing)}",
    ))

    disk_target = bag.parent if bag.parent.exists() else Path.cwd()
    free_gib = disk_usage(disk_target).free / (1024 ** 3)
    checks.append(_result(
        "disk_space", free_gib >= min_free_gib,
        f"{free_gib:.2f} GiB free; minimum {min_free_gib:.2f} GiB",
    ))

    bag_ok = bag.is_file() and bag.suffix.lower() == ".bag" and os.access(bag, os.R_OK)
    detail = f"readable file ({bag.stat().st_size} bytes)" if bag_ok else "must be a readable .bag file"
    checks.append(_result("bag_readable", bag_ok, detail))

    readable_usb = []
    if usb_root.is_dir():
        for candidate in usb_root.glob("*/*"):
            try:
                if stat.S_ISCHR(candidate.stat().st_mode) and os.access(candidate, os.R_OK | os.W_OK):
                    readable_usb.append(str(candidate))
            except OSError:
                continue
    usb_ok = bool(readable_usb)
    usb_detail = (
        f"{len(readable_usb)} readable USB device node(s)"
        if usb_ok else f"no readable USB device nodes under {usb_root}"
    )
    checks.append(_result("usb_permissions", usb_ok, usb_detail, required=require_usb))

    required_failures = [check["name"] for check in checks if check["required"] and not check["ok"]]
    return {
        "schema_version": "realsense-runner-check/v1",
        "ok": not required_failures,
        "motion_enabled": False,
        "bag": str(bag),
        "checks": checks,
        "failures": required_failures,
    }


def markdown_report(report: dict) -> str:
    lines = ["## RealSense runner provisioning", "", "| Check | Required | Status | Detail |", "|---|---:|---:|---|"]
    for check in report["checks"]:
        status = "PASS" if check["ok"] else ("FAIL" if check["required"] else "WARN")
        detail = str(check["detail"]).replace("|", "\\|")
        lines.append(f"| `{check['name']}` | {'yes' if check['required'] else 'no'} | **{status}** | {detail} |")
    lines.extend(["", f"Overall: **{'HEALTHY' if report['ok'] else 'BLOCKED'}**", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a RealSense self-hosted runner")
    parser.add_argument("--bag", type=Path, required=True)
    parser.add_argument("--labels", default="", help="comma-separated runner labels")
    parser.add_argument("--min-free-gib", type=float, default=5.0)
    parser.add_argument("--require-usb", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)

    report = inspect_runner(
        args.bag,
        labels=args.labels.split(","),
        min_free_gib=args.min_free_gib,
        require_usb=args.require_usb,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = markdown_report(report)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(summary, encoding="utf-8")
    print(summary)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
