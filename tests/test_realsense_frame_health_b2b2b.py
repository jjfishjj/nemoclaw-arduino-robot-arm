from arm_bridge.realsense_live import FRAME_HEALTH_LIMITS, evaluate_frame_health


def health(**overrides):
    values = {
        "running": True, "connected": True, "sample_count": 3,
        "raw_fps": 2.0, "filtered_fps": 2.0,
        "latency_ms": 10.0, "age_ms": 100.0, "invalid_ratio": 0.02,
    }
    values.update(overrides)
    return evaluate_frame_health(**values)


def test_health_gate_is_healthy_only_when_every_signal_is_within_limits():
    result = health()
    assert result["state"] == "HEALTHY"
    assert result["reasons"] == ["within_limits"]
    assert result["observed"]["fps"] == 2.0


def test_health_gate_degrades_during_warmup_or_soft_limit_violation():
    assert health(sample_count=1)["reasons"] == ["fps_warming_up"]
    result = health(latency_ms=FRAME_HEALTH_LIMITS["healthy"]["max_latency_ms"] + 0.1)
    assert result["state"] == "DEGRADED"
    assert result["reasons"] == ["latency_high"]


def test_health_gate_blocks_stopped_disconnected_and_critical_depth():
    assert health(running=False)["reasons"] == ["stream_stopped"]
    assert health(connected=False)["reasons"] == ["camera_disconnected"]
    result = health(invalid_ratio=FRAME_HEALTH_LIMITS["blocked"]["max_invalid_ratio"] + 0.01)
    assert result["state"] == "BLOCKED"
    assert result["reasons"] == ["invalid_depth_critical"]


def test_health_gate_uses_slower_of_raw_and_filtered_fps():
    result = health(raw_fps=2.0, filtered_fps=0.4)
    assert result["state"] == "BLOCKED"
    assert result["reasons"] == ["fps_critical"]
    assert result["observed"]["fps"] == 0.4
