"""B2-B3B aggregate native benchmark/parity reports into a CI gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .core import SafetyError
from .librealsense_filters import PARITY_LIMITS
from .realsense_benchmark import DEFAULT_REGRESSION_LIMITS, SCHEMA_VERSION


GATE_SCHEMA_VERSION = 1


def _require_native(report: dict, name: str) -> None:
    if report.get("verified_native") is not True:
        raise SafetyError(f"{name} is not native verified")
    if report.get("motion_enabled") is not False:
        raise SafetyError(f"{name} must explicitly keep motion disabled")


def evaluate_ci_gate(benchmark: dict, parity: dict) -> dict:
    if benchmark.get("current", {}).get("schema_version") != SCHEMA_VERSION:
        raise SafetyError("benchmark current schema is unsupported")
    if benchmark.get("baseline", {}).get("schema_version") != SCHEMA_VERSION:
        raise SafetyError("benchmark baseline schema is unsupported")
    _require_native(benchmark["current"], "benchmark current")
    _require_native(benchmark["baseline"], "benchmark baseline")
    if benchmark.get("motion_enabled") is not False:
        raise SafetyError("benchmark comparison must explicitly keep motion disabled")
    benchmark_limits = benchmark.get("limits")
    if benchmark_limits != DEFAULT_REGRESSION_LIMITS:
        raise SafetyError("benchmark regression limits differ from the reviewed contract")
    benchmark_violations = benchmark.get("violations")
    if not isinstance(benchmark_violations, list) or any(
        item not in DEFAULT_REGRESSION_LIMITS for item in benchmark_violations
    ):
        raise SafetyError("benchmark violations are malformed")
    benchmark_deltas = benchmark.get("deltas")
    if not isinstance(benchmark_deltas, dict) or set(benchmark_deltas) != set(DEFAULT_REGRESSION_LIMITS) or any(
        not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in benchmark_deltas.values()
    ):
        raise SafetyError("benchmark deltas are malformed")
    expected_benchmark_violations = [
        name for name, value in benchmark_deltas.items() if value > DEFAULT_REGRESSION_LIMITS[name]
    ]
    if benchmark_violations != expected_benchmark_violations:
        raise SafetyError("benchmark violations disagree with deltas")
    if benchmark.get("regression") is not bool(benchmark_violations):
        raise SafetyError("benchmark regression flag disagrees with violations")
    if benchmark.get("ok") is not (not benchmark_violations):
        raise SafetyError("benchmark ok flag disagrees with violations")

    _require_native(parity, "parity report")
    _require_native(parity.get("native", {}), "parity native result")
    recording_sha256 = benchmark["current"].get("recording_sha256")
    if not isinstance(recording_sha256, str) or len(recording_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in recording_sha256.lower()
    ):
        raise SafetyError("benchmark recording SHA-256 is malformed")
    if parity.get("recording_sha256") != recording_sha256:
        raise SafetyError("parity recording SHA-256 differs from benchmark")
    if parity.get("limits") != PARITY_LIMITS:
        raise SafetyError("parity limits differ from the reviewed contract")
    deltas = parity.get("deltas")
    if not isinstance(deltas, dict) or set(deltas) != set(PARITY_LIMITS) or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
        for value in deltas.values()
    ):
        raise SafetyError("parity deltas are malformed")
    parity_violations = [name for name, value in deltas.items() if value > PARITY_LIMITS[name]]
    if parity.get("within_limits") is not (not parity_violations):
        raise SafetyError("parity within_limits flag disagrees with deltas")

    failures = [f"benchmark:{name}" for name in benchmark_violations]
    failures.extend(f"parity:{name}" for name in parity_violations)
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "status": "FAIL" if failures else "PASS",
        "ok": not failures,
        "failures": failures,
        "benchmark": {
            "ok": not benchmark_violations,
            "violations": benchmark_violations,
            "deltas": benchmark_deltas,
            "limits": benchmark_limits,
        },
        "parity": {
            "ok": not parity_violations,
            "violations": parity_violations,
            "deltas": deltas,
            "limits": PARITY_LIMITS,
        },
        "verified_native": True,
        "motion_enabled": False,
    }


def invalid_gate(message: str) -> dict:
    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "status": "INVALID",
        "ok": False,
        "failures": ["input:invalid_or_untrusted"],
        "error": message,
        "verified_native": False,
        "motion_enabled": False,
    }


def markdown_summary(report: dict) -> str:
    lines = [
        "# RealSense Native CI Gate",
        "",
        f"**Status: {report['status']}**",
        "",
        "| Check | Result | Details |",
        "| --- | --- | --- |",
    ]
    if report["status"] == "INVALID":
        lines.append(f"| Input trust | INVALID | {report['error']} |")
    else:
        for name in ("benchmark", "parity"):
            check = report[name]
            detail = ", ".join(check["violations"]) if check["violations"] else "within reviewed limits"
            lines.append(f"| {name.title()} | {'PASS' if check['ok'] else 'FAIL'} | {detail} |")
    lines.extend(["", "Native verification is required. Robot motion remains disabled.", ""])
    return "\n".join(lines)


def github_annotations(report: dict) -> list[str]:
    def escape(value: str) -> str:
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    if report["status"] == "PASS":
        return ["::notice title=RealSense native gate::Benchmark and parity are within reviewed limits"]
    if report["status"] == "INVALID":
        return [f"::error title=RealSense native gate input::{escape(report['error'])}"]
    return [f"::error title=RealSense native regression::{escape(failure)}" for failure in report["failures"]]


def write_gate_artifacts(report: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gate-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "gate-summary.md").write_text(markdown_summary(report), encoding="utf-8")


def _load_report(path: Path, name: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load {name} report: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError(f"{name} report must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate native RealSense benchmark and parity reports")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--parity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-annotations", action="store_true")
    args = parser.parse_args()
    try:
        report = evaluate_ci_gate(
            _load_report(args.benchmark, "benchmark"),
            _load_report(args.parity, "parity"),
        )
        exit_code = 0 if report["ok"] else 1
    except (SafetyError, KeyError, TypeError) as exc:
        report = invalid_gate(str(exc))
        exit_code = 2
    write_gate_artifacts(report, args.output)
    if args.github_annotations:
        for line in github_annotations(report):
            print(line)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
