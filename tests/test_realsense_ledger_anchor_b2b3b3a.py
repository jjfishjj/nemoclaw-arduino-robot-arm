import json

import pytest

from arm_bridge.core import SafetyError
from arm_bridge.realsense_baseline_ledger import append_entry, write_ledger
from arm_bridge.realsense_ledger_anchor import create_anchor, verify_anchor


def setup_state(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b"trusted baseline\n")
    import hashlib
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
    entries = []
    append_entry(entries, action="PROMOTE", baseline_sha256=digest,
                 occurred_at="2026-08-13T00:00:00Z", actor="reviewer",
                 workflow_run="https://example.test/run/1", reason="reviewed")
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(ledger, entries)
    return ledger, baseline, entries


def test_anchor_binds_ledger_head_length_bytes_and_baseline(tmp_path):
    ledger, baseline, entries = setup_state(tmp_path)
    anchor = create_anchor(ledger, baseline, workflow_run="https://example.test/run/1",
                           commit_sha="a" * 40, occurred_at="2026-08-13T00:00:00Z")
    result = verify_anchor(anchor, ledger, baseline)
    assert anchor["ledger_entries"] == 1
    assert anchor["ledger_head_sha256"] == entries[-1]["entry_sha256"]
    assert result["ok"] is True and result["motion_enabled"] is False


def test_anchor_detects_tail_truncation_replacement_and_baseline_swap(tmp_path):
    ledger, baseline, entries = setup_state(tmp_path)
    append_entry(entries, action="PROMOTE", baseline_sha256=entries[0]["baseline_sha256"],
                 occurred_at="2026-08-13T01:00:00Z", actor="reviewer", workflow_run="run2")
    write_ledger(ledger, entries)
    anchor = create_anchor(ledger, baseline, workflow_run="run", commit_sha="a" * 40,
                           occurred_at="2026-08-13T00:00:00Z")
    write_ledger(ledger, entries[:1])
    with pytest.raises(SafetyError, match="length differs"):
        verify_anchor(anchor, ledger, baseline)
    write_ledger(ledger, entries)
    baseline.write_bytes(b"replacement")
    with pytest.raises(SafetyError, match="baseline differs"):
        verify_anchor(anchor, ledger, baseline)


def test_anchor_rejects_tampered_metadata(tmp_path):
    ledger, baseline, _ = setup_state(tmp_path)
    anchor = create_anchor(ledger, baseline, workflow_run="run", commit_sha="a" * 40,
                           occurred_at="2026-08-13T00:00:00Z")
    anchor["ledger_sha256"] = "b" * 64
    with pytest.raises(SafetyError, match="ledger bytes differ"):
        verify_anchor(anchor, ledger, baseline)
    anchor = create_anchor(ledger, baseline, workflow_run="run", commit_sha="a" * 40,
                           occurred_at="2026-08-13T00:00:00Z")
    anchor["ledger_action"] = "ROLLBACK"
    with pytest.raises(SafetyError, match="action differs"):
        verify_anchor(anchor, ledger, baseline)
