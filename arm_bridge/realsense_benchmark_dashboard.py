"""Read-only view model for RealSense benchmark and native gate reports."""

from __future__ import annotations

import json
import math
from pathlib import Path

from .core import SafetyError
from .realsense_benchmark import DEFAULT_REGRESSION_LIMITS, SCHEMA_VERSION
from .realsense_benchmark_history import load_history


METRICS = (
    ("latency_p50_ms", "Latency P50", "ms"),
    ("latency_p95_ms", "Latency P95", "ms"),
    ("fps", "Throughput", "FPS"),
    ("invalid_ratio", "Invalid depth", "%"),
)


def _read_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError(f"{label} must be a JSON object")
    return value


def _metric_values(report: dict, label: str) -> dict[str, float]:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise SafetyError(f"{label} schema is unsupported")
    if report.get("motion_enabled") is not False:
        raise SafetyError(f"{label} must explicitly keep motion disabled")
    try:
        metrics = report["metrics"]
        values = {
            "latency_p50_ms": float(metrics["latency_ms"]["p50"]),
            "latency_p95_ms": float(metrics["latency_ms"]["p95"]),
            "fps": float(metrics["fps"]),
            "invalid_ratio": float(metrics["invalid_ratio"]["mean"]) * 100,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetyError(f"{label} metrics are incomplete") from exc
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise SafetyError(f"{label} metrics must be finite non-negative numbers")
    return values


def build_dashboard(benchmark: dict, gate: dict | None = None) -> dict:
    try:
        current_report, baseline_report = benchmark["current"], benchmark["baseline"]
    except (KeyError, TypeError) as exc:
        raise SafetyError("benchmark comparison is missing current or baseline") from exc
    current = _metric_values(current_report, "current benchmark")
    baseline = _metric_values(baseline_report, "baseline benchmark")
    if benchmark.get("motion_enabled") is not False:
        raise SafetyError("benchmark comparison must explicitly keep motion disabled")
    failures = benchmark.get("violations")
    if not isinstance(failures, list) or any(item not in DEFAULT_REGRESSION_LIMITS for item in failures):
        raise SafetyError("benchmark violations are malformed")

    gate_status = gate.get("status") if gate else None
    if gate_status not in {None, "PASS", "FAIL", "INVALID"}:
        raise SafetyError("gate status is unsupported")
    if gate and gate.get("motion_enabled") is not False:
        raise SafetyError("gate report must explicitly keep motion disabled")
    gate_failures = gate.get("failures", []) if gate else []
    if not isinstance(gate_failures, list) or any(not isinstance(item, str) for item in gate_failures):
        raise SafetyError("gate failures are malformed")
    all_failures = list(dict.fromkeys([*[f"benchmark:{item}" for item in failures], *gate_failures]))
    if gate_status == "INVALID":
        all_failures.append(gate.get("error", "gate input is invalid"))

    native_verified = current_report.get("verified_native") is True and baseline_report.get("verified_native") is True
    if gate and gate.get("verified_native") is not True:
        native_verified = False
    if not native_verified:
        all_failures.append("input:not_native_verified")
    health = (
        "BLOCKED" if gate_status in {"FAIL", "INVALID"} or not native_verified
        else ("DEGRADED" if failures or gate is None else "HEALTHY")
    )
    rows = []
    for key, label, unit in METRICS:
        base, value = baseline[key], current[key]
        delta = value - base
        delta_percent = 0.0 if base == 0 else delta / base * 100
        rows.append({
            "key": key, "label": label, "unit": unit,
            "baseline": round(base, 3), "current": round(value, 3),
            "delta": round(delta, 3), "delta_percent": round(delta_percent, 2),
        })
    return {
        "schema_version": "realsense-benchmark-dashboard/v1",
        "ok": health == "HEALTHY",
        "health": health,
        "gate_status": gate_status or "NOT_LOADED",
        "verified_native": native_verified,
        "motion_enabled": False,
        "recording_sha256": current_report.get("recording_sha256", ""),
        "metrics": rows,
        "failures": all_failures,
        "limits": benchmark.get("limits", DEFAULT_REGRESSION_LIMITS),
    }


class BenchmarkDashboardSource:
    def __init__(self, benchmark_path: str | Path | None = None, gate_path: str | Path | None = None,
                 history_dir: str | Path | None = None):
        self.benchmark_path = Path(benchmark_path).expanduser().resolve() if benchmark_path else None
        self.gate_path = Path(gate_path).expanduser().resolve() if gate_path else None
        self.history_dir = Path(history_dir).expanduser().resolve() if history_dir else None

    def report(self) -> dict:
        if not self.benchmark_path:
            report = {
                "schema_version": "realsense-benchmark-dashboard/v1", "ok": False,
                "health": "BLOCKED", "gate_status": "NOT_LOADED", "verified_native": False,
                "motion_enabled": False, "recording_sha256": "", "metrics": [],
                "failures": ["benchmark report is not configured"], "limits": DEFAULT_REGRESSION_LIMITS,
            }
            report["history"] = load_history(self.history_dir)
            return report
        benchmark = _read_object(self.benchmark_path, "benchmark report")
        gate = _read_object(self.gate_path, "gate report") if self.gate_path else None
        report = build_dashboard(benchmark, gate)
        report["history"] = load_history(self.history_dir)
        return report
