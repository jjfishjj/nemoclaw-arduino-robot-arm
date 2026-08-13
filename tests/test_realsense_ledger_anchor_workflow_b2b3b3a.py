from pathlib import Path


def test_governance_workflows_verify_previous_and_attest_new_anchor():
    for name in ("realsense-baseline-promotion.yml", "realsense-baseline-rollback.yml"):
        text = Path(".github/workflows", name).read_text()
        assert "attestations: write" in text
        assert "id-token: write" in text
        assert "gh attestation verify \"$ANCHOR\"" in text
        assert "arm_bridge.realsense_ledger_anchor" in text
        assert "uses: actions/attest@v4" in text
        assert "subject-path: ${{ env.ANCHOR }}" in text
        assert text.index("Verify previous signed ledger anchor") < text.index("Attest new ledger anchor")


def test_anchor_is_committed_only_via_review_branch():
    promotion = Path(".github/workflows/realsense-baseline-promotion.yml").read_text()
    rollback = Path(".github/workflows/realsense-baseline-rollback.yml").read_text()
    assert 'git add "$TARGET" "$LEDGER" "$ANCHOR" "$ARCHIVE_DIR"' in promotion
    assert 'git add "$TARGET" "$LEDGER" "$ANCHOR"' in rollback
    assert 'git push origin "$DEFAULT_BRANCH"' not in promotion + rollback
