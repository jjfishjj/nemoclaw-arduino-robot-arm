"""Motion-free live USB smoke test for an attached RealSense camera."""

from __future__ import annotations

import argparse
import json
import math
import re
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from .core import SafetyError


SERIAL_RE = re.compile(r"Serial Number\s*:\s*(\S+)", re.IGNORECASE)
FIRMWARE_RE = re.compile(r"Firmware Version\s*:\s*(\S+)", re.IGNORECASE)


class LiveSmokeSource(Protocol):
    serial: str
    firmware: str

    def capture(self, frames: int, timeout_ms: int) -> list[dict]: ...


def parse_enumerate_devices(output: str) -> list[dict]:
    serials = SERIAL_RE.findall(output)
    firmwares = FIRMWARE_RE.findall(output)
    if not serials:
        raise SafetyError("rs-enumerate-devices found no serial number")
    if len(serials) != len(firmwares):
        raise SafetyError("rs-enumerate-devices output is missing firmware version")
    return [{"serial": serial, "firmware": firmware} for serial, firmware in zip(serials, firmwares)]


def readable_usb_nodes(root: Path = Path("/dev/bus/usb")) -> list[str]:
    if not root.is_dir():
        return []
    nodes = []
    for candidate in root.glob("*/*"):
        try:
            if stat.S_ISCHR(candidate.stat().st_mode) and os.access(candidate, os.R_OK | os.W_OK):
                nodes.append(str(candidate))
        except OSError:
            continue
    return nodes


def evaluate_smoke(devices: list[dict], source: LiveSmokeSource, *, frames: int,
                   timeout_ms: int, expected_serial: str = "",
                   min_valid_depth_ratio: float = 0.70) -> dict:
    if frames < 3 or not 0 <= min_valid_depth_ratio <= 1:
        raise SafetyError("smoke test sampling contract is invalid")
    if expected_serial and source.serial != expected_serial:
        raise SafetyError("connected SDK serial does not match the expected serial")
    cli_device = next((device for device in devices if device["serial"] == source.serial), None)
    if not cli_device:
        raise SafetyError("SDK serial is absent from rs-enumerate-devices output")
    if not source.firmware or cli_device["firmware"] != source.firmware:
        raise SafetyError("SDK firmware differs from rs-enumerate-devices output")

    samples = source.capture(frames, timeout_ms)
    if len(samples) != frames:
        raise SafetyError("live smoke capture returned incomplete frames")
    dimensions = {(item.get("color_width"), item.get("color_height"),
                   item.get("depth_width"), item.get("depth_height")) for item in samples}
    if len(dimensions) != 1 or any(not isinstance(value, int) or value <= 0 for value in next(iter(dimensions))):
        raise SafetyError("live smoke frames have invalid or changing dimensions")
    timestamps = [item.get("timestamp_ms") for item in samples]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in timestamps):
        raise SafetyError("live smoke timestamps are invalid")
    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        raise SafetyError("live smoke timestamps are stale or non-monotonic")
    ratios = [item.get("valid_depth_ratio") for item in samples]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1 for value in ratios):
        raise SafetyError("live smoke depth ratios are invalid")
    minimum_ratio = min(ratios)
    if minimum_ratio < min_valid_depth_ratio:
        raise SafetyError("live smoke valid depth ratio is below the reviewed threshold")
    width, height, depth_width, depth_height = next(iter(dimensions))
    return {
        "schema_version": "realsense-live-usb-smoke/v1",
        "status": "PASS", "ok": True,
        "device": {"serial": source.serial, "firmware": source.firmware},
        "frames": frames, "timeout_ms": timeout_ms,
        "color_resolution": [width, height], "depth_resolution": [depth_width, depth_height],
        "duration_ms": round(timestamps[-1] - timestamps[0], 3),
        "valid_depth_ratio": {"minimum": round(minimum_ratio, 6),
                              "mean": round(sum(ratios) / len(ratios), 6)},
        "verified_live_usb": True, "motion_enabled": False,
    }


class LibrealsenseLiveSmokeSource:
    def __init__(self, expected_serial: str = ""):
        try:
            import pyrealsense2 as rs  # type: ignore
        except ImportError as exc:
            raise SafetyError("install the 'realsense' extra for live USB smoke test") from exc
        self.rs = rs
        devices = list(rs.context().query_devices())
        if expected_serial:
            devices = [device for device in devices if device.get_info(rs.camera_info.serial_number) == expected_serial]
        if len(devices) != 1:
            raise SafetyError("live USB smoke test requires exactly one selected RealSense device")
        self.serial = devices[0].get_info(rs.camera_info.serial_number)
        self.firmware = devices[0].get_info(rs.camera_info.firmware_version)

    def capture(self, frames: int, timeout_ms: int) -> list[dict]:
        import numpy as np

        pipeline = self.rs.pipeline()
        config = self.rs.config()
        config.enable_device(self.serial)
        config.enable_stream(self.rs.stream.depth, 640, 480, self.rs.format.z16, 30)
        config.enable_stream(self.rs.stream.color, 640, 480, self.rs.format.bgr8, 30)
        align = self.rs.align(self.rs.stream.color)
        samples = []
        try:
            pipeline.start(config)
            for _ in range(frames):
                aligned = align.process(pipeline.wait_for_frames(timeout_ms))
                color, depth = aligned.get_color_frame(), aligned.get_depth_frame()
                if not color or not depth:
                    raise SafetyError("live USB smoke test received an incomplete RGB-D frame")
                depth_data = np.asanyarray(depth.get_data())
                samples.append({
                    "timestamp_ms": float(aligned.get_timestamp()),
                    "color_width": color.get_width(), "color_height": color.get_height(),
                    "depth_width": depth.get_width(), "depth_height": depth.get_height(),
                    "valid_depth_ratio": float(np.count_nonzero(depth_data) / depth_data.size),
                })
        finally:
            try:
                pipeline.stop()
            except RuntimeError:
                pass
        return samples


def markdown_report(report: dict) -> str:
    if report.get("status") != "PASS":
        return f"## RealSense Live USB Smoke Test\n\n**BLOCKED** — {report.get('error', 'unknown error')}\n\nRobot motion remained disabled.\n"
    device = report["device"]
    return "\n".join([
        "## RealSense Live USB Smoke Test", "", "**PASS**", "",
        f"- Serial: `{device['serial']}`", f"- Firmware: `{device['firmware']}`",
        f"- Frames: {report['frames']}",
        f"- RGB-D: {report['color_resolution'][0]}×{report['color_resolution'][1]}",
        f"- Minimum valid depth: {report['valid_depth_ratio']['minimum'] * 100:.2f}%", "",
        "Robot motion remained disabled.", "",
    ])


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a motion-free RealSense live USB smoke test")
    parser.add_argument("--expected-serial", default="")
    parser.add_argument("--frames", type=int, default=15)
    parser.add_argument("--timeout-ms", type=int, default=3000)
    parser.add_argument("--min-valid-depth-ratio", type=float, default=0.70)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        usb_nodes = readable_usb_nodes()
        if not usb_nodes:
            raise SafetyError("no readable and writable RealSense USB device node is available")
        completed = subprocess.run(["rs-enumerate-devices", "-s"], capture_output=True, text=True, timeout=10)
        if completed.returncode != 0:
            raise SafetyError("rs-enumerate-devices failed")
        devices = parse_enumerate_devices(completed.stdout)
        report = evaluate_smoke(
            devices, LibrealsenseLiveSmokeSource(args.expected_serial), frames=args.frames,
            timeout_ms=args.timeout_ms, expected_serial=args.expected_serial,
            min_valid_depth_ratio=args.min_valid_depth_ratio,
        )
        report["usb_device_nodes"] = len(usb_nodes)
        code = 0
    except (OSError, subprocess.TimeoutExpired, SafetyError) as exc:
        report = {"schema_version": "realsense-live-usb-smoke/v1", "status": "BLOCKED",
                  "ok": False, "error": str(exc), "verified_live_usb": False, "motion_enabled": False}
        code = 2
    _write(args.output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write(args.summary, markdown_report(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
