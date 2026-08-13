import pytest

from arm_bridge.core import SafetyError
from arm_bridge.realsense_live_smoke import evaluate_smoke, parse_enumerate_devices, readable_usb_nodes


CLI = """Device info:\n    Serial Number : 123456\n    Firmware Version : 5.16.0.1\n"""


class Source:
    serial = "123456"
    firmware = "5.16.0.1"

    def capture(self, frames, _timeout_ms):
        return [{"timestamp_ms": index * 33.3, "color_width": 640, "color_height": 480,
                 "depth_width": 640, "depth_height": 480, "valid_depth_ratio": .91}
                for index in range(frames)]


def test_live_smoke_validates_identity_firmware_and_rgbd_frames():
    report = evaluate_smoke(parse_enumerate_devices(CLI), Source(), frames=15, timeout_ms=3000,
                            expected_serial="123456")
    assert report["status"] == "PASS"
    assert report["device"] == {"serial": "123456", "firmware": "5.16.0.1"}
    assert report["valid_depth_ratio"]["minimum"] == .91
    assert report["verified_live_usb"] is True
    assert report["motion_enabled"] is False


def test_identity_firmware_and_depth_fail_closed():
    with pytest.raises(SafetyError, match="expected serial"):
        evaluate_smoke(parse_enumerate_devices(CLI), Source(), frames=3, timeout_ms=1000,
                       expected_serial="wrong")
    source = Source(); source.firmware = "different"
    with pytest.raises(SafetyError, match="firmware differs"):
        evaluate_smoke(parse_enumerate_devices(CLI), source, frames=3, timeout_ms=1000)
    source = Source()
    source.capture = lambda frames, timeout: [{"timestamp_ms": i + 1, "color_width": 640,
        "color_height": 480, "depth_width": 640, "depth_height": 480,
        "valid_depth_ratio": .1} for i in range(frames)]
    with pytest.raises(SafetyError, match="below the reviewed threshold"):
        evaluate_smoke(parse_enumerate_devices(CLI), source, frames=3, timeout_ms=1000)


def test_stale_or_incomplete_frames_are_rejected():
    source = Source()
    source.capture = lambda frames, timeout: Source().capture(frames - 1, timeout)
    with pytest.raises(SafetyError, match="incomplete"):
        evaluate_smoke(parse_enumerate_devices(CLI), source, frames=3, timeout_ms=1000)
    source.capture = lambda frames, timeout: [{"timestamp_ms": 1, "color_width": 640,
        "color_height": 480, "depth_width": 640, "depth_height": 480,
        "valid_depth_ratio": .9} for _ in range(frames)]
    with pytest.raises(SafetyError, match="non-monotonic"):
        evaluate_smoke(parse_enumerate_devices(CLI), source, frames=3, timeout_ms=1000)


def test_cli_parser_rejects_missing_firmware():
    with pytest.raises(SafetyError, match="missing firmware"):
        parse_enumerate_devices("Serial Number : 123456")


def test_missing_usb_tree_has_no_usable_nodes(tmp_path):
    assert readable_usb_nodes(tmp_path / "missing") == []
