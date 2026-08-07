from arm_bridge.depth_filter_graph import FILTER_ORDER
from arm_bridge.realsense_live import LiveRGBDContract, MockLiveSource


def test_live_filter_contract_reports_raw_filtered_telemetry():
    clock = [100.0]
    source = MockLiveSource(now=lambda: clock[0], clock=lambda: clock[0])
    live = LiveRGBDContract(source, now=lambda: clock[0])
    live.start()
    live.poll()
    clock[0] += 0.05
    result = live.poll()

    status = result["status"]
    assert status["raw_fps"] == 20.0
    assert status["filtered_fps"] == 20.0
    assert status["filter_latency_ms"] == 0.0
    assert status["filters"] == list(FILTER_ORDER)
    assert [item["stage"] for item in status["filter_options"]] == list(FILTER_ORDER)
    assert status["filter_backend"] == "sdk-contract-fixture"
    assert status["verified_native"] is False
    assert status["raw_metrics"]["width"] == 8
    assert status["filtered_metrics"]["width"] == 4
    assert status["motion_enabled"] is False


def test_reconnect_restarts_fixture_filter_state():
    clock = [200.0]
    source = MockLiveSource(now=lambda: clock[0], fail_reads={2})
    live = LiveRGBDContract(source, now=lambda: clock[0])
    live.start()
    live.poll()
    assert source.previous is not None

    clock[0] += 0.04
    failed = live.poll()
    assert failed["ok"] is False
    assert source.previous is None

    clock[0] += 0.04
    recovered = live.poll()
    assert recovered["ok"] is True
    assert recovered["status"]["connected"] is True
    assert source.previous is not None
