import json
from pathlib import Path

import pytest

from arm_bridge.core import SafetyError
from arm_bridge.depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER
from arm_bridge.realsense_baseline_ledger import append_entry, artifact_digest, load_ledger, main, write_ledger


def candidate():
    return {
        "schema_version": 1, "backend": "librealsense-bag-native", "verified_native": True,
        "motion_enabled": False, "warmup_frames": 30, "sample_frames": 120,
        "recording_sha256": "a" * 64, "filter_order": list(FILTER_ORDER),
        "filter_config": DEFAULT_CONFIG,
        "metrics": {"latency_ms": {"p50": 5.0, "p95": 8.0}, "fps": 100.0,
                    "invalid_ratio": {"mean": .02, "p95": .03}},
    }


def metadata(action, digest):
    return dict(action=action, baseline_sha256=digest, occurred_at="2026-08-13T00:00:00Z",
                actor="reviewer", workflow_run="https://example.test/run/1", reason="reviewed")


def test_ledger_hash_chain_and_rollback_target():
    entries = []
    digest = "a" * 64
    promoted = append_entry(entries, **metadata("PROMOTE", digest))
    rolled_back = append_entry(entries, **metadata("ROLLBACK", digest))
    assert rolled_back["previous_entry_sha256"] == promoted["entry_sha256"]
    assert rolled_back["sequence"] == 2
    assert rolled_back["motion_enabled"] is False


def test_tampered_chain_and_unknown_rollback_are_rejected(tmp_path):
    entries = []
    append_entry(entries, **metadata("PROMOTE", "a" * 64))
    entries[0]["actor"] = "attacker"
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps(entries[0]) + "\n", encoding="utf-8")
    with pytest.raises(SafetyError, match="digest is invalid"):
        load_ledger(path)
    with pytest.raises(SafetyError, match="never promoted"):
        append_entry([], **metadata("ROLLBACK", "b" * 64))


def test_promote_then_rollback_cli_restores_archived_bytes(tmp_path):
    artifact = tmp_path / "candidate.json"
    artifact.write_text(json.dumps(candidate(), sort_keys=True) + "\n", encoding="utf-8")
    ledger, archive, target = tmp_path / "ledger.jsonl", tmp_path / "archive", tmp_path / "current.json"
    common = ["--ledger", str(ledger), "--archive-dir", str(archive), "--target", str(target),
              "--occurred-at", "2026-08-13T00:00:00Z", "--actor", "reviewer",
              "--workflow-run", "https://example.test/run/1"]
    assert main(["promote", "--artifact", str(artifact), *common]) == 0
    digest = artifact_digest(artifact.read_bytes())
    target.write_text("changed", encoding="utf-8")
    assert main(["rollback", "--digest", digest, "--reason", "regression", *common]) == 0
    assert target.read_bytes() == artifact.read_bytes()
    assert [entry["action"] for entry in load_ledger(ledger)] == ["PROMOTE", "ROLLBACK"]


def test_unknown_rollback_does_not_modify_current_baseline(tmp_path):
    ledger, archive, target = tmp_path / "ledger.jsonl", tmp_path / "archive", tmp_path / "current.json"
    archive.mkdir()
    target.write_text("trusted-current", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["rollback", "--ledger", str(ledger), "--archive-dir", str(archive),
              "--target", str(target), "--digest", "b" * 64,
              "--occurred-at", "2026-08-13T00:00:00Z", "--actor", "reviewer",
              "--workflow-run", "https://example.test/run/2", "--reason", "test"])
    assert target.read_text(encoding="utf-8") == "trusted-current"
