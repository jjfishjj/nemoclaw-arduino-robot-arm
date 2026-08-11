import json
import subprocess
import sys
from copy import deepcopy

from arm_bridge.core import SafetyError
from arm_bridge.depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER
from arm_bridge.realsense_baseline_promotion import validate_baseline_candidate


def candidate():
    return {
        "schema_version": 1,
        "recording_sha256": "a" * 64,
        "backend": "librealsense-bag-native",
        "verified_native": True,
        "warmup_frames": 30,
        "sample_frames": 120,
        "filter_order": list(FILTER_ORDER),
        "filter_config": deepcopy(DEFAULT_CONFIG),
        "metrics": {
            "latency_ms": {"p50": 5.0, "p95": 8.0},
            "fps": 90.0,
            "invalid_ratio": {"mean": 0.02, "p95": 0.04},
        },
        "motion_enabled": False,
    }


def test_native_candidate_validation_creates_digest_bound_receipt():
    value = candidate()
    encoded = json.dumps(value, sort_keys=True).encode()
    receipt = validate_baseline_candidate(value, encoded)
    assert receipt["status"] == "VALIDATED"
    assert len(receipt["artifact_sha256"]) == 64
    assert receipt["recording_sha256"] == "a" * 64
    assert receipt["verified_native"] is True
    assert receipt["motion_enabled"] is False


def test_promotion_rejects_fixture_motion_and_metric_tampering():
    cases = []
    fixture = candidate(); fixture["verified_native"] = False; cases.append((fixture, "native verified"))
    motion = candidate(); motion["motion_enabled"] = True; cases.append((motion, "motion disabled"))
    percentile = candidate(); percentile["metrics"]["latency_ms"] = {"p50": 9.0, "p95": 8.0}; cases.append((percentile, "percentiles"))
    invalid = candidate(); invalid["metrics"]["invalid_ratio"]["p95"] = 1.1; cases.append((invalid, "invalid-depth"))
    for value, message in cases:
        try:
            validate_baseline_candidate(value, json.dumps(value).encode())
        except SafetyError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"tampered candidate was accepted: {message}")


def test_promotion_rejects_changed_sampling_or_filter_contract():
    samples = candidate(); samples["sample_frames"] = 60
    filters = candidate(); filters["filter_config"]["temporal"]["alpha"] = 0.9
    for value, message in ((samples, "sample count"), (filters, "filter graph")):
        try:
            validate_baseline_candidate(value, json.dumps(value).encode())
        except SafetyError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"changed contract was accepted: {message}")


def test_cli_writes_rejected_receipt_before_failing(tmp_path):
    candidate_path = tmp_path / "candidate.json"
    receipt_path = tmp_path / "receipt.json"
    candidate_path.write_text(json.dumps({"verified_native": False}))
    result = subprocess.run([
        sys.executable, "-m", "arm_bridge.realsense_baseline_promotion",
        "--candidate", str(candidate_path), "--receipt", str(receipt_path),
    ], capture_output=True)
    assert result.returncode == 2
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "REJECTED"
    assert receipt["motion_enabled"] is False
