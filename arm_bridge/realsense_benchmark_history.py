"""Create and load trusted, read-only RealSense benchmark history entries."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import sys

from .core import SafetyError
from .realsense_benchmark import SCHEMA_VERSION


HISTORY_SCHEMA = "realsense-benchmark-history/v1"


def _load(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError(f"{label} must be a JSON object")
    return value


def create_history_entry(benchmark: dict, gate: dict, *, run_id: str, run_attempt: int,
                         commit_sha: str, occurred_at: str) -> dict:
    try:
        current = benchmark["current"]
        metrics = current["metrics"]
        values = {
            "latency_p50_ms": float(metrics["latency_ms"]["p50"]),
            "latency_p95_ms": float(metrics["latency_ms"]["p95"]),
            "fps": float(metrics["fps"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetyError("benchmark history metrics are incomplete") from exc
    if current.get("schema_version") != SCHEMA_VERSION:
        raise SafetyError("benchmark history schema is unsupported")
    if current.get("verified_native") is not True or current.get("motion_enabled") is not False:
        raise SafetyError("benchmark history requires a native motion-disabled result")
    if gate.get("verified_native") is not True or gate.get("motion_enabled") is not False:
        raise SafetyError("benchmark history requires a native motion-disabled gate")
    if gate.get("status") not in {"PASS", "FAIL"}:
        raise SafetyError("benchmark history gate must be PASS or FAIL")
    recording_sha256 = current.get("recording_sha256")
    if not isinstance(recording_sha256, str) or len(recording_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in recording_sha256.lower()
    ):
        raise SafetyError("benchmark history recording digest is malformed")
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise SafetyError("benchmark history metrics must be finite non-negative numbers")
    try:
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SafetyError("benchmark history timestamp is invalid") from exc
    if not run_id or run_attempt < 1 or len(commit_sha) != 40:
        raise SafetyError("benchmark history provenance is malformed")
    failures = gate.get("failures", [])
    if not isinstance(failures, list) or any(not isinstance(item, str) for item in failures):
        raise SafetyError("benchmark history failures are malformed")
    return {
        "schema_version": HISTORY_SCHEMA,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "commit_sha": commit_sha,
        "occurred_at": occurred_at,
        "gate_status": gate["status"],
        "regression": gate["status"] == "FAIL",
        "failures": failures,
        "recording_sha256": recording_sha256,
        "metrics": {key: round(value, 3) for key, value in values.items()},
        "verified_native": True,
        "motion_enabled": False,
    }


def validate_history_entry(entry: dict) -> dict:
    if entry.get("schema_version") != HISTORY_SCHEMA:
        raise SafetyError("history entry schema is unsupported")
    # Rebuild through the same contract using a minimal source representation.
    benchmark = {"current": {
        "schema_version": SCHEMA_VERSION,
        "verified_native": entry.get("verified_native"),
        "motion_enabled": entry.get("motion_enabled"),
        "recording_sha256": entry.get("recording_sha256", ""),
        "metrics": {"latency_ms": {"p50": entry.get("metrics", {}).get("latency_p50_ms"),
                                    "p95": entry.get("metrics", {}).get("latency_p95_ms")},
                    "fps": entry.get("metrics", {}).get("fps")},
    }}
    gate = {"status": entry.get("gate_status"), "failures": entry.get("failures"),
            "verified_native": entry.get("verified_native"), "motion_enabled": entry.get("motion_enabled")}
    rebuilt = create_history_entry(
        benchmark, gate, run_id=entry.get("run_id", ""),
        run_attempt=entry.get("run_attempt", 0), commit_sha=entry.get("commit_sha", ""),
        occurred_at=entry.get("occurred_at", ""),
    )
    if entry != rebuilt:
        raise SafetyError("history entry contains unsupported or inconsistent fields")
    return entry


def load_history(directory: Path | None, limit: int = 30) -> list[dict]:
    if not directory or not directory.is_dir():
        return []
    entries: dict[tuple[str, int], dict] = {}
    for path in directory.rglob("*.json"):
        try:
            entry = validate_history_entry(_load(path, "history entry"))
        except SafetyError:
            continue
        entries[(entry["run_id"], entry["run_attempt"])] = entry
    ordered = sorted(entries.values(), key=lambda item: item["occurred_at"])
    return ordered[-limit:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a trusted RealSense benchmark history entry")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--occurred-at", required=True)
    args = parser.parse_args(argv)
    try:
        entry = create_history_entry(
            _load(args.benchmark, "benchmark report"), _load(args.gate, "gate report"),
            run_id=args.run_id, run_attempt=args.run_attempt,
            commit_sha=args.commit_sha, occurred_at=args.occurred_at,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(entry, indent=2, sort_keys=True))
        return 0
    except SafetyError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
