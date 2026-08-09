import io

from PIL import Image

from arm_bridge.core import SafetyError
from arm_bridge.realsense_live import LiveRGBDContract, MockLiveSource


def test_depth_visual_requires_a_live_frame_and_valid_view():
    live = LiveRGBDContract(MockLiveSource())
    try:
        live.depth_visual_png("raw")
    except SafetyError as exc:
        assert "no live depth frame" in str(exc)
    else:
        raise AssertionError("depth image was available before polling")
    live.start()
    live.poll()
    try:
        live.depth_visual_png("unknown")
    except SafetyError as exc:
        assert "raw or filtered" in str(exc)
    else:
        raise AssertionError("unknown depth view was accepted")


def test_raw_and_filtered_heatmaps_are_png_with_shared_display_size():
    live = LiveRGBDContract(MockLiveSource())
    live.start()
    live.poll()
    raw = Image.open(io.BytesIO(live.depth_visual_png("raw", True)))
    filtered = Image.open(io.BytesIO(live.depth_visual_png("filtered", True)))
    assert raw.format == filtered.format == "PNG"
    assert raw.size == filtered.size == (640, 480)
    assert (255, 0, 170) in set(raw.getdata())
    assert (255, 0, 170) not in set(filtered.getdata())


def test_invalid_mask_can_be_hidden_without_changing_depth_contract():
    live = LiveRGBDContract(MockLiveSource())
    live.start()
    result = live.poll()
    image = Image.open(io.BytesIO(live.depth_visual_png("raw", False)))
    assert (255, 0, 170) not in set(image.getdata())
    assert result["status"]["raw_metrics"]["invalid_ratio"] > 0
    assert result["status"]["motion_enabled"] is False
