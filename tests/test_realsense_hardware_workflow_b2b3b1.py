from pathlib import Path


WORKFLOW = Path(".github/workflows/realsense-hardware-gate.yml")


def test_hardware_workflow_is_manual_trusted_and_realsense_labeled():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "runs-on: [self-hosted, linux, x64, realsense]" in text
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in text
    assert "ref: ${{ github.event.repository.default_branch }}" in text
    assert "persist-credentials: false" in text
    assert "permissions:\n  contents: read" in text


def test_hardware_workflow_generates_both_reports_then_calls_gate_action():
    text = WORKFLOW.read_text()
    benchmark = text.index("arm_bridge.realsense_benchmark")
    parity = text.index("arm_bridge.realsense_parity_report")
    gate = text.index("uses: ./.github/actions/realsense-native-gate")
    assert benchmark < parity < gate
    assert "continue-on-error: true" in text
    assert "if: always()" in text
    assert "upload-artifact" not in text  # the reviewed composite action owns upload ordering


def test_hardware_paths_come_from_repository_variables_not_dispatch_input():
    text = WORKFLOW.read_text()
    assert "vars.REALSENSE_BAG_PATH" in text
    assert "vars.REALSENSE_BASELINE_PATH" in text
    assert "inputs." not in text
