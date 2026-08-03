import pytest

from arm_bridge.core import SafetyError
from arm_bridge.realsense_playback import CameraIntrinsics, RGBDFrame, default_playback


def test_fixture_has_aligned_rgbd_metadata_and_no_motion():
    playback = default_playback()
    metadata = playback.metadata()
    assert metadata["mode"] == "recorded-rgbd"
    assert metadata["frame_count"] == 3
    assert metadata["motion_enabled"] is False
    assert playback.frame(2)["frame"]["depth_unit"] == "meter"


def test_deprojects_pixel_depth_to_camera_coordinates():
    result = default_playback().deproject(0, 2, 3)
    assert result["camera_m"] == {"x": -0.0876, "y": 0.0292, "z": 0.438}
    assert result["frame"] == "camera_optical_frame"
    assert result["motion_enabled"] is False


def test_invalid_frame_pixel_and_missing_depth_are_rejected():
    playback = default_playback()
    with pytest.raises(SafetyError, match="outside the recording"):
        playback.frame(3)
    with pytest.raises(SafetyError, match="outside the aligned"):
        playback.deproject(0, 8, 0)
    with pytest.raises(SafetyError, match="no valid depth"):
        playback.deproject(2, 6, 2)


def test_rgbd_dimensions_must_match_intrinsics():
    frame = RGBDFrame(0, 0, "", CameraIntrinsics(2, 2, 1, 1, .5, .5), ((1.0, 1.0),))
    with pytest.raises(SafetyError, match="height"):
        frame.validate()
