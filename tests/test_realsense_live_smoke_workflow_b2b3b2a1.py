from pathlib import Path


def test_live_smoke_workflow_is_manual_read_only_and_motion_free():
    text = Path(".github/workflows/realsense-live-usb-smoke.yml").read_text()
    assert "workflow_dispatch:" in text
    assert "runs-on: [self-hosted, linux, x64, realsense]" in text
    assert "contents: read" in text
    assert "persist-credentials: false" in text
    assert "arm_bridge.realsense_live_smoke" in text
    assert "--frames 15" in text
    assert "--min-valid-depth-ratio 0.70" in text
    assert "arm_bridge.server" not in text
    assert "/api/command" not in text
    assert "upload-artifact@v4" in text
    assert text.index("continue-on-error: true") < text.index("if: always()")
