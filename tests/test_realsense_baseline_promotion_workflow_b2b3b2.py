from pathlib import Path


WORKFLOW = Path(".github/workflows/realsense-baseline-promotion.yml")


def test_candidate_job_has_no_repository_write_permission():
    text = WORKFLOW.read_text()
    capture = text[text.index("capture-candidate:"):text.index("approve-and-promote:")]
    assert "runs-on: [self-hosted, linux, x64, realsense]" in capture
    assert "contents: read" in capture
    assert "contents: write" not in capture
    assert "persist-credentials: false" in capture


def test_promotion_requires_environment_and_signed_attestation():
    text = WORKFLOW.read_text()
    promote = text[text.index("approve-and-promote:"):]
    assert "name: realsense-baseline-promotion" in promote
    assert "id-token: write" in promote
    assert "attestations: write" in promote
    assert "uses: actions/attest@v4" in promote
    assert "gh attestation verify" in promote


def test_promotion_opens_pr_without_direct_default_branch_push():
    text = WORKFLOW.read_text()
    assert "codex/realsense-baseline-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" in text
    assert "gh pr create" in text
    assert "git push origin \"$promotion_branch\"" in text
    assert "git push origin \"$DEFAULT_BRANCH\"" not in text
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in text


def test_candidate_generation_precedes_approval_promotion():
    text = WORKFLOW.read_text()
    assert text.index("--write-baseline") < text.index("environment:")
    assert text.index("arm_bridge.realsense_baseline_promotion") < text.index("actions/attest@v4")
    assert text.index("actions/attest@v4") < text.index("gh pr create")
