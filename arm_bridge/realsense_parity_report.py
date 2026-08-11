"""Generate a Python/native filter parity report from one RealSense .bag."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import SafetyError
from .librealsense_filters import LibrealsenseBagRunner, NativeParityContract
from .realsense_playback import RealSenseBagPlayback


def generate_parity_report(source, runner, frame_index: int) -> dict:
    if frame_index < 0:
        raise SafetyError("parity frame must be non-negative")
    recording_sha256 = getattr(runner, "recording_sha256", None)
    if not isinstance(recording_sha256, str) or len(recording_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in recording_sha256.lower()
    ):
        raise SafetyError("parity runner is missing a valid recording SHA-256")
    source.frame(frame_index)
    report = NativeParityContract(source, runner).compare(frame_index)
    if report.get("recording_sha256") != recording_sha256:
        raise SafetyError("parity report is missing the recording SHA-256")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Python/native filters on the same .bag frame")
    parser.add_argument("bag", type=Path)
    parser.add_argument("--frame", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = None
    try:
        runner = LibrealsenseBagRunner(args.bag)
        source = RealSenseBagPlayback(args.bag)
        report = generate_parity_report(source, runner, args.frame)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    except SafetyError as exc:
        parser.error(str(exc))
    finally:
        if source is not None:
            source.close()


if __name__ == "__main__":
    main()
