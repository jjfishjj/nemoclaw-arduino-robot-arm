import json
import subprocess
import sys
from copy import deepcopy

from arm_bridge.core import SafetyError
from arm_bridge.librealsense_filters import PARITY_LIMITS
from arm_bridge.realsense_benchmark import DEFAULT_REGRESSION_LIMITS
from arm_bridge.realsense_ci_gate import (
    evaluate_ci_gate, github_annotations, invalid_gate, markdown_summary, write_gate_artifacts,
)


def native_benchmark():
    leaf = {
        "schema_version": 1, "verified_native": True, "motion_enabled": False,
        "recording_sha256": "a" * 64, "sample_frames": 120,
    }
    return {
        "ok": True, "regression": False, "violations": [],
        "deltas": {name: 0.0 for name in DEFAULT_REGRESSION_LIMITS},
        "limits": DEFAULT_REGRESSION_LIMITS,
        "current": deepcopy(leaf), "baseline": deepcopy(leaf),
        "motion_enabled": False,
    }


def native_parity():
    return {
        "verified_native": True, "within_limits": True,
        "native": {"verified_native": True, "motion_enabled": False},
        "deltas": {name: 0.0 for name in PARITY_LIMITS},
        "limits": PARITY_LIMITS, "motion_enabled": False,
        "recording_sha256": "a" * 64,
    }


def test_gate_passes_only_verified_native_reports_within_limits():
    report = evaluate_ci_gate(native_benchmark(), native_parity())
    assert report["status"] == "PASS"
    assert report["ok"] is True
    assert report["verified_native"] is True
    assert report["motion_enabled"] is False
    assert github_annotations(report)[0].startswith("::notice")


def test_gate_aggregates_benchmark_and_parity_failures():
    benchmark = native_benchmark()
    benchmark["violations"] = ["fps_decrease_ratio"]
    benchmark["regression"] = True
    benchmark["ok"] = False
    benchmark["deltas"]["fps_decrease_ratio"] = DEFAULT_REGRESSION_LIMITS["fps_decrease_ratio"] + 0.01
    parity = native_parity()
    parity["deltas"]["roughness_delta_m"] = PARITY_LIMITS["roughness_delta_m"] + 0.001
    parity["within_limits"] = False
    report = evaluate_ci_gate(benchmark, parity)
    assert report["status"] == "FAIL"
    assert report["failures"] == [
        "benchmark:fps_decrease_ratio", "parity:roughness_delta_m",
    ]
    assert len(github_annotations(report)) == 2


def test_gate_rejects_fixture_or_tampered_contract():
    benchmark = native_benchmark()
    benchmark["current"]["verified_native"] = False
    try:
        evaluate_ci_gate(benchmark, native_parity())
    except SafetyError as exc:
        assert "not native verified" in str(exc)
    else:
        raise AssertionError("fixture benchmark was accepted")
    parity = native_parity()
    parity["within_limits"] = False
    try:
        evaluate_ci_gate(native_benchmark(), parity)
    except SafetyError as exc:
        assert "disagrees" in str(exc)
    else:
        raise AssertionError("tampered parity flag was accepted")
    benchmark = native_benchmark()
    benchmark["violations"] = ["fps_decrease_ratio"]
    benchmark["regression"] = True
    benchmark["ok"] = False
    try:
        evaluate_ci_gate(benchmark, native_parity())
    except SafetyError as exc:
        assert "disagree" in str(exc)
    else:
        raise AssertionError("tampered benchmark violations were accepted")
    parity = native_parity()
    parity["recording_sha256"] = "b" * 64
    try:
        evaluate_ci_gate(native_benchmark(), parity)
    except SafetyError as exc:
        assert "differs" in str(exc)
    else:
        raise AssertionError("parity from a different recording was accepted")


def test_invalid_gate_still_writes_json_markdown_and_error_annotation(tmp_path):
    report = invalid_gate("missing\nreport")
    write_gate_artifacts(report, tmp_path)
    saved = json.loads((tmp_path / "gate-report.json").read_text())
    assert saved["status"] == "INVALID"
    assert "Status: INVALID" in (tmp_path / "gate-summary.md").read_text()
    assert "%0A" in github_annotations(report)[0]
    assert "motion remains disabled" in markdown_summary(report)


def test_cli_uses_stable_pass_fail_invalid_exit_codes(tmp_path):
    benchmark_path = tmp_path / "benchmark.json"
    parity_path = tmp_path / "parity.json"
    benchmark_path.write_text(json.dumps(native_benchmark()))
    parity_path.write_text(json.dumps(native_parity()))
    command = [
        sys.executable, "-m", "arm_bridge.realsense_ci_gate",
        "--benchmark", str(benchmark_path), "--parity", str(parity_path),
    ]
    passed = subprocess.run(command + ["--output", str(tmp_path / "pass")], capture_output=True)
    assert passed.returncode == 0

    parity = native_parity()
    parity["deltas"]["mean_depth_delta_m"] = PARITY_LIMITS["mean_depth_delta_m"] + 0.01
    parity["within_limits"] = False
    parity_path.write_text(json.dumps(parity))
    failed = subprocess.run(command + ["--output", str(tmp_path / "fail")], capture_output=True)
    assert failed.returncode == 1

    invalid = subprocess.run(
        command[:-1] + [str(tmp_path / "missing.json"), "--output", str(tmp_path / "invalid")],
        capture_output=True,
    )
    assert invalid.returncode == 2
    assert json.loads((tmp_path / "invalid/gate-report.json").read_text())["status"] == "INVALID"
