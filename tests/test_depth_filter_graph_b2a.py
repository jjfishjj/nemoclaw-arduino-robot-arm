import pytest

from arm_bridge.core import SafetyError
from arm_bridge.depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER, FilterGraphContract
from arm_bridge.realsense_playback import default_playback
from arm_bridge.realsense_playback import CameraIntrinsics, RGBDFrame


def test_filter_graph_is_ordered_and_reproducible():
    source = default_playback().source
    graph = FilterGraphContract()
    first = graph.run(source, 2)
    second = graph.run(source, 2)
    assert first["order"] == list(FILTER_ORDER)
    assert [stage["name"] for stage in first["stages"]] == list(FILTER_ORDER)
    assert first["output"]["fingerprint"] == second["output"]["fingerprint"]
    assert first["output"]["width"] == 4
    assert first["output"]["height"] == 3
    assert first["motion_enabled"] is False


def test_temporal_warmup_changes_later_fixture_output():
    source = default_playback().source
    graph = FilterGraphContract()
    current = graph.run(source, 2)
    assert current["stages"][2]["roughness_m"] <= current["stages"][0]["roughness_m"]


def test_depth_hole_is_only_repaired_by_final_stage():
    class HoleFixture:
        frame_count = 1
        def frame(self, index):
            depth = (
                (0.5, 0.5, 0.6, 0.6),
                (0.5, 0.5, 0.6, 0.6),
                (0.7, 0.7, 0.0, 0.0),
                (0.7, 0.7, 0.0, 0.0),
            )
            return RGBDFrame(index, 0, "", CameraIntrinsics(4, 4, 4, 4, 1.5, 1.5), depth)

    result = FilterGraphContract().run(HoleFixture(), 0)
    assert [stage["invalid_ratio"] for stage in result["stages"][:3]] == [0.25, 0.25, 0.25]
    assert result["stages"][3]["invalid_ratio"] == 0.0


@pytest.mark.parametrize("config,message", [
    ({**DEFAULT_CONFIG, "decimation": {"magnitude": 5}}, "magnitude"),
    ({**DEFAULT_CONFIG, "spatial": {"alpha": 1.2, "iterations": 2}}, "alpha"),
    ({"spatial": DEFAULT_CONFIG["spatial"], "decimation": DEFAULT_CONFIG["decimation"],
      "temporal": DEFAULT_CONFIG["temporal"], "hole_filling": DEFAULT_CONFIG["hole_filling"]}, "order"),
])
def test_invalid_filter_configuration_fails_closed(config, message):
    with pytest.raises(SafetyError, match=message):
        FilterGraphContract().run(default_playback().source, 0, config)
