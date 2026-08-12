from copy import deepcopy
import json

from arm_bridge.core import SafetyError
from arm_bridge.realsense_benchmark import DEFAULT_REGRESSION_LIMITS
from arm_bridge.realsense_benchmark_dashboard import BenchmarkDashboardSource, build_dashboard


def benchmark():
    baseline = {
        "schema_version": 1, "verified_native": True, "motion_enabled": False,
        "recording_sha256": "a" * 64,
        "metrics": {"latency_ms": {"p50": 5.0, "p95": 8.0}, "fps": 100.0, "invalid_ratio": {"mean": .02}},
    }
    current = deepcopy(baseline)
    current["metrics"] = {"latency_ms": {"p50": 5.5, "p95": 9.0}, "fps": 95.0, "invalid_ratio": {"mean": .025}}
    return {"current": current, "baseline": baseline, "violations": [], "limits": DEFAULT_REGRESSION_LIMITS, "motion_enabled": False}


def test_dashboard_exposes_baseline_current_delta_and_health():
    report = build_dashboard(benchmark(), {"status": "PASS", "failures": [], "verified_native": True, "motion_enabled": False})
    assert report["health"] == "HEALTHY"
    assert report["motion_enabled"] is False
    assert [row["key"] for row in report["metrics"]] == ["latency_p50_ms", "latency_p95_ms", "fps", "invalid_ratio"]
    assert report["metrics"][1]["delta_percent"] == 12.5


def test_gate_failure_blocks_and_lists_reasons():
    value = benchmark()
    value["violations"] = ["fps_decrease_ratio"]
    report = build_dashboard(value, {"status": "FAIL", "failures": ["parity:roughness_delta_m"], "verified_native": True, "motion_enabled": False})
    assert report["health"] == "BLOCKED"
    assert report["failures"] == ["benchmark:fps_decrease_ratio", "parity:roughness_delta_m"]


def test_missing_gate_is_degraded_and_missing_report_is_blocked(tmp_path):
    assert build_dashboard(benchmark())["health"] == "DEGRADED"
    assert BenchmarkDashboardSource().report()["health"] == "BLOCKED"
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(benchmark()), encoding="utf-8")
    assert BenchmarkDashboardSource(path).report()["health"] == "DEGRADED"


def test_tampered_motion_contract_is_rejected():
    value = benchmark()
    value["current"]["motion_enabled"] = True
    try:
        build_dashboard(value)
    except SafetyError as exc:
        assert "motion disabled" in str(exc)
    else:
        raise AssertionError("motion-enabled benchmark was accepted")


def test_unverified_gate_blocks_health():
    report = build_dashboard(benchmark(), {"status": "PASS", "failures": [], "verified_native": False, "motion_enabled": False})
    assert report["health"] == "BLOCKED"
    assert "input:not_native_verified" in report["failures"]
