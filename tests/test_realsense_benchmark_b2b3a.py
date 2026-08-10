import json
from copy import deepcopy

from arm_bridge.core import SafetyError
from arm_bridge.realsense_benchmark import (
    DEFAULT_REGRESSION_LIMITS, compare_benchmark, summarize_benchmark,
)


class FixtureRunner:
    backend = "benchmark-fixture"
    verified_native = False
    recording_sha256 = "fixture-sha256"

    def sample(self, warmup_frames, sample_frames, config):
        assert warmup_frames == 2
        return {
            "latencies_ms": [4.0, 6.0, 10.0, 8.0, 5.0][:sample_frames],
            "invalid_ratios": [0.01, 0.02, 0.03, 0.02, 0.01][:sample_frames],
            "elapsed_ms": 50.0,
        }


def baseline():
    return summarize_benchmark(FixtureRunner(), warmup_frames=2, sample_frames=5)


def test_benchmark_excludes_warmup_and_reports_percentiles_fps_and_invalid_ratio():
    report = baseline()
    assert report["warmup_frames"] == 2
    assert report["sample_frames"] == 5
    assert report["metrics"]["latency_ms"] == {"p50": 6.0, "p95": 9.6}
    assert report["metrics"]["fps"] == 100.0
    assert report["metrics"]["invalid_ratio"] == {"mean": 0.018, "p95": 0.028}
    assert report["verified_native"] is False
    assert report["motion_enabled"] is False


def test_comparison_reports_all_regression_reasons():
    old = baseline()
    current = deepcopy(old)
    current["metrics"]["latency_ms"]["p95"] = 12.0
    current["metrics"]["fps"] = 80.0
    current["metrics"]["invalid_ratio"]["mean"] = 0.06
    result = compare_benchmark(current, old, require_native=False)
    assert result["ok"] is False
    assert result["violations"] == list(DEFAULT_REGRESSION_LIMITS)
    assert result["motion_enabled"] is False


def test_comparison_rejects_recording_drift_and_unverified_native_baseline():
    old = baseline()
    current = deepcopy(old)
    current["recording_sha256"] = "different"
    try:
        compare_benchmark(current, old, require_native=False)
    except SafetyError as exc:
        assert "recording_sha256" in str(exc)
    else:
        raise AssertionError("recording drift was accepted")
    try:
        compare_benchmark(old, old)
    except SafetyError as exc:
        assert "not native verified" in str(exc)
    else:
        raise AssertionError("fixture baseline was accepted as native")


def test_committed_fixture_baseline_is_explicitly_not_native():
    value = json.loads(open("benchmarks/realsense-bag-baseline.fixture.json", encoding="utf-8").read())
    assert value["verified_native"] is False
    assert value["recording_sha256"] == "fixture-only-not-a-real-bag"


def test_comparison_rejects_malformed_baseline_metrics():
    old = baseline()
    current = deepcopy(old)
    old["metrics"]["latency_ms"]["p95"] = 0
    try:
        compare_benchmark(current, old, require_native=False)
    except SafetyError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("zero baseline latency was accepted")
