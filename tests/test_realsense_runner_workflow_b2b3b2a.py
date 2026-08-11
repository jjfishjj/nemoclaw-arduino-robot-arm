from pathlib import Path


WORKFLOWS = (
    Path(".github/workflows/realsense-baseline-promotion.yml"),
    Path(".github/workflows/realsense-hardware-gate.yml"),
)


def test_checklist_blocks_candidate_generation_and_is_always_uploaded():
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        checklist = text.index("arm_bridge.realsense_runner_check")
        candidate = text.index("arm_bridge.realsense_benchmark")
        assert checklist < candidate
        assert '--labels "self-hosted,linux,x64,realsense"' in text
        assert '--min-free-gib 5' in text
        assert '--summary "$PROVISION_DIR/summary.md" || checklist_status=$?' in text
        assert 'cat "$PROVISION_DIR/summary.md" >> "$GITHUB_STEP_SUMMARY"' in text
        assert 'exit "$checklist_status"' in text
        if workflow.name == "realsense-baseline-promotion.yml":
            upload = text.index("name: Upload runner provisioning report")
            assert "if: always()" in text[upload:upload + 180]
            assert "retention-days: 14" in text[upload:]
        else:
            assert "PROVISION_DIR: artifacts/realsense-hardware-gate/provisioning" in text
            assert "uses: ./.github/actions/realsense-native-gate" in text
