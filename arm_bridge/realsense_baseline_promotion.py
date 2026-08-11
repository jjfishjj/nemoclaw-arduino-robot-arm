"""Validate a native RealSense baseline candidate before signed promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .core import SafetyError
from .depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER
from .realsense_benchmark import SCHEMA_VERSION


EXPECTED_WARMUP_FRAMES = 30
EXPECTED_SAMPLE_FRAMES = 120


def validate_baseline_candidate(candidate: dict, artifact_bytes: bytes) -> dict:
    if candidate.get("schema_version") != SCHEMA_VERSION:
        raise SafetyError("baseline candidate schema is unsupported")
    if candidate.get("backend") != "librealsense-bag-native":
        raise SafetyError("baseline candidate backend is not native librealsense")
    if candidate.get("verified_native") is not True:
        raise SafetyError("baseline candidate is not native verified")
    if candidate.get("motion_enabled") is not False:
        raise SafetyError("baseline candidate must explicitly keep motion disabled")
    if candidate.get("warmup_frames") != EXPECTED_WARMUP_FRAMES:
        raise SafetyError("baseline candidate warmup count differs from the reviewed contract")
    if candidate.get("sample_frames") != EXPECTED_SAMPLE_FRAMES:
        raise SafetyError("baseline candidate sample count differs from the reviewed contract")
    if candidate.get("filter_order") != list(FILTER_ORDER) or candidate.get("filter_config") != DEFAULT_CONFIG:
        raise SafetyError("baseline candidate filter graph differs from the reviewed contract")
    recording_sha256 = candidate.get("recording_sha256")
    if not isinstance(recording_sha256, str) or len(recording_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in recording_sha256.lower()
    ):
        raise SafetyError("baseline candidate recording SHA-256 is malformed")
    try:
        metrics = candidate["metrics"]
        values = {
            "latency_p50_ms": metrics["latency_ms"]["p50"],
            "latency_p95_ms": metrics["latency_ms"]["p95"],
            "fps": metrics["fps"],
            "invalid_mean": metrics["invalid_ratio"]["mean"],
            "invalid_p95": metrics["invalid_ratio"]["p95"],
        }
    except (KeyError, TypeError) as exc:
        raise SafetyError("baseline candidate metrics are incomplete") from exc
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values.values()):
        raise SafetyError("baseline candidate metrics must be finite numbers")
    if values["latency_p50_ms"] < 0 or values["latency_p95_ms"] <= 0 or values["fps"] <= 0:
        raise SafetyError("baseline candidate latency and FPS metrics must be positive")
    if values["latency_p50_ms"] > values["latency_p95_ms"]:
        raise SafetyError("baseline candidate latency percentiles are inconsistent")
    if not 0 <= values["invalid_mean"] <= values["invalid_p95"] <= 1:
        raise SafetyError("baseline candidate invalid-depth metrics are inconsistent")
    return {
        "schema_version": 1,
        "status": "VALIDATED",
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "recording_sha256": recording_sha256,
        "backend": candidate["backend"],
        "warmup_frames": candidate["warmup_frames"],
        "sample_frames": candidate["sample_frames"],
        "metrics": values,
        "verified_native": True,
        "motion_enabled": False,
    }


def rejected_receipt(message: str) -> dict:
    return {
        "schema_version": 1,
        "status": "REJECTED",
        "error": message,
        "verified_native": False,
        "motion_enabled": False,
    }


def _write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a native RealSense baseline promotion candidate")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        artifact_bytes = args.candidate.read_bytes()
        candidate = json.loads(artifact_bytes)
        if not isinstance(candidate, dict):
            raise SafetyError("baseline candidate must be a JSON object")
        receipt = validate_baseline_candidate(candidate, artifact_bytes)
        _write_receipt(args.receipt, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
    except (OSError, json.JSONDecodeError, SafetyError) as exc:
        try:
            _write_receipt(args.receipt, rejected_receipt(str(exc)))
        except OSError:
            pass
        parser.error(str(exc))


if __name__ == "__main__":
    main()
