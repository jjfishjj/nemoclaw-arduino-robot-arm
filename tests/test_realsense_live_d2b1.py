from arm_bridge.realsense_live import LiveRGBDContract, MockLiveSource


def test_live_stream_start_poll_metrics_and_stop():
    clock = [10.0]
    source = MockLiveSource(now=lambda: clock[0])
    live = LiveRGBDContract(source, now=lambda: clock[0])
    assert live.start()["running"] is True
    first = live.poll()
    clock[0] += 0.04
    second = live.poll()
    assert first["frame"]["depth_unit"] == "meter"
    assert second["status"]["fps"] == 25.0
    assert second["status"]["fresh"] is True
    assert second["status"]["filters"] == []
    assert second["status"]["motion_enabled"] is False
    assert live.stop()["running"] is False


def test_stale_frame_and_disconnect_reconnect_are_observable():
    clock = [20.0]
    source = MockLiveSource(now=lambda: clock[0], fail_reads={2})
    live = LiveRGBDContract(source, now=lambda: clock[0])
    live.start()
    live.poll()
    clock[0] += 1.1
    assert live.status()["fresh"] is False
    failed = live.poll()
    assert failed["ok"] is False
    assert failed["status"]["connected"] is False
    assert failed["status"]["reconnect_count"] == 1
    clock[0] += 0.04
    recovered = live.poll()
    assert recovered["ok"] is True
    assert recovered["status"]["connected"] is True


def test_poll_before_start_fails_closed():
    from arm_bridge.core import SafetyError
    try:
        LiveRGBDContract(MockLiveSource()).poll()
    except SafetyError as exc:
        assert "started" in str(exc)
    else:
        raise AssertionError("poll before start was accepted")
