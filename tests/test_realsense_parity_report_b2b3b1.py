from arm_bridge.core import SafetyError
from arm_bridge.librealsense_filters import SDKContractFixtureRunner
from arm_bridge.realsense_parity_report import generate_parity_report
from arm_bridge.realsense_playback import default_playback


def test_parity_report_loads_target_frame_and_binds_recording_hash():
    source = default_playback().source
    runner = SDKContractFixtureRunner(source)
    runner.recording_sha256 = "a" * 64
    report = generate_parity_report(source, runner, 2)
    assert report["frame_index"] == 2
    assert report["recording_sha256"] == "a" * 64
    assert report["verified_native"] is False
    assert report["motion_enabled"] is False


def test_parity_report_rejects_negative_frame_and_missing_hash():
    source = default_playback().source
    runner = SDKContractFixtureRunner(source)
    try:
        generate_parity_report(source, runner, -1)
    except SafetyError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative parity frame was accepted")
    try:
        generate_parity_report(source, runner, 1)
    except SafetyError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("parity report without recording hash was accepted")
