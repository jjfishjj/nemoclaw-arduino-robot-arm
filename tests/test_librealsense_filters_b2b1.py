import pytest

from arm_bridge.core import SafetyError
from arm_bridge.depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER
from arm_bridge.librealsense_filters import NativeParityContract, SDKContractFixtureRunner, option_plan
from arm_bridge.realsense_playback import default_playback


def test_sdk_option_mapping_preserves_order_and_values():
    plan = option_plan(DEFAULT_CONFIG)
    assert [item["stage"] for item in plan] == list(FILTER_ORDER)
    assert plan == [
        {"stage": "decimation", "options": {"filter_magnitude": 2}},
        {"stage": "spatial", "options": {"filter_smooth_alpha": 0.5, "filter_magnitude": 2}},
        {"stage": "temporal", "options": {"filter_smooth_alpha": 0.4}},
        {"stage": "hole_filling", "options": {"holes_fill": 1}},
    ]


def test_fixture_parity_is_explicitly_not_native_verified():
    source = default_playback().source
    report = NativeParityContract(source, SDKContractFixtureRunner(source)).compare(2)
    assert report["within_limits"] is True
    assert report["verified_native"] is False
    assert report["native"]["backend"] == "sdk-contract-fixture"
    assert report["motion_enabled"] is False


def test_native_hole_mode_out_of_range_is_rejected():
    config = {**DEFAULT_CONFIG, "hole_filling": {"passes": 3}}
    with pytest.raises(SafetyError, match="mode"):
        option_plan(config)
