from pathlib import Path


def test_rollback_is_environment_approved_and_pr_only():
    text = Path(".github/workflows/realsense-baseline-rollback.yml").read_text(encoding="utf-8")
    assert "name: realsense-baseline-rollback" in text
    assert "arm_bridge.realsense_baseline_ledger rollback" in text
    assert '--digest "$BASELINE_SHA256"' in text
    assert 'git add "$TARGET" "$LEDGER"' in text
    assert 'git push origin "$rollback_branch"' in text
    assert "gh pr create" in text
    assert 'git push origin "$DEFAULT_BRANCH"' not in text


def test_promotion_archives_digest_and_appends_same_ledger():
    text = Path(".github/workflows/realsense-baseline-promotion.yml").read_text(encoding="utf-8")
    assert "group: realsense-baseline-governance" in text
    assert "arm_bridge.realsense_baseline_ledger promote" in text
    assert 'git add "$TARGET" "$LEDGER" "$ARCHIVE_DIR"' in text
