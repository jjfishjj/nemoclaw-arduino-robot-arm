import json

import pytest

from arm_bridge.core import SafetyError
from arm_bridge.realsense_benchmark_history import create_history_entry, load_history


def reports(status="PASS"):
    benchmark = {"current": {"schema_version": 1, "verified_native": True, "motion_enabled": False,
                 "recording_sha256": "a" * 64,
                 "metrics": {"latency_ms": {"p50": 5, "p95": 8}, "fps": 100}}}
    gate = {"status": status, "failures": [] if status == "PASS" else ["benchmark:fps_decrease_ratio"],
            "verified_native": True, "motion_enabled": False}
    return benchmark, gate


def entry(run_id="1", occurred_at="2026-08-13T00:00:00Z", status="PASS"):
    benchmark, gate = reports(status)
    return create_history_entry(benchmark, gate, run_id=run_id, run_attempt=1,
                                commit_sha="b" * 40, occurred_at=occurred_at)


def test_history_entry_contains_metrics_and_regression_marker():
    value = entry(status="FAIL")
    assert value["metrics"] == {"latency_p50_ms": 5.0, "latency_p95_ms": 8.0, "fps": 100.0}
    assert value["regression"] is True
    assert value["motion_enabled"] is False


def test_unverified_or_motion_enabled_history_is_rejected():
    benchmark, gate = reports()
    gate["verified_native"] = False
    with pytest.raises(SafetyError, match="native motion-disabled gate"):
        create_history_entry(benchmark, gate, run_id="1", run_attempt=1, commit_sha="b" * 40, occurred_at="2026-08-13T00:00:00Z")


def test_load_history_sorts_deduplicates_and_skips_invalid(tmp_path):
    (tmp_path / "late.json").write_text(json.dumps(entry("2", "2026-08-13T02:00:00Z")))
    (tmp_path / "early.json").write_text(json.dumps(entry("1", "2026-08-13T01:00:00Z")))
    (tmp_path / "invalid.json").write_text("{}")
    nested = tmp_path / "rerun"; nested.mkdir()
    (nested / "same-run.json").write_text(json.dumps(entry("2", "2026-08-13T02:00:00Z")))
    assert [item["run_id"] for item in load_history(tmp_path)] == ["1", "2"]
