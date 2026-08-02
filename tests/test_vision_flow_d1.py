import pytest

from arm_bridge.core import SafetyError
from arm_bridge.vision_flow import VisionFlow


def ready_mock_status():
    return {"armed": True, "startup_ready": True, "hardware": {"mode": "mock"}}


def test_select_confirm_execute_named_recipe():
    flow = VisionFlow()
    plan = flow.select("bench-a", "red-cube")["plan"]
    sent = []
    with pytest.raises(SafetyError, match="confirmation"):
        flow.execute(plan["plan_id"], ready_mock_status(), sent.append)
    flow.confirm(plan["plan_id"], True)
    result = flow.execute(plan["plan_id"], ready_mock_status(), lambda command: sent.append(command) or {"ok": True})
    assert result["recipe"] == "pick-red-cube-to-left-bin"
    assert len(sent) == 3
    assert all(command["command"] == "move" for command in sent)


def test_low_confidence_detection_cannot_create_plan():
    with pytest.raises(SafetyError, match="confidence"):
        VisionFlow().select("bench-b", "low-confidence-object")


def test_plan_expires_and_is_single_use():
    clock = [10.0]
    flow = VisionFlow(now=lambda: clock[0])
    plan = flow.select("bench-a", "blue-cylinder")["plan"]
    clock[0] += 301
    with pytest.raises(SafetyError, match="expired"):
        flow.confirm(plan["plan_id"], True)

    plan = flow.select("bench-a", "blue-cylinder")["plan"]
    flow.confirm(plan["plan_id"], True)
    flow.execute(plan["plan_id"], ready_mock_status(), lambda command: {"ok": True})
    with pytest.raises(SafetyError, match="single-use"):
        flow.execute(plan["plan_id"], ready_mock_status(), lambda command: {"ok": True})


def test_real_hardware_execution_is_blocked_in_d1():
    flow = VisionFlow()
    plan = flow.select("bench-a", "red-cube")["plan"]
    flow.confirm(plan["plan_id"], True)
    status = {"armed": True, "startup_ready": True, "hardware": {"mode": "so101"}}
    with pytest.raises(SafetyError, match="mock-only"):
        flow.execute(plan["plan_id"], status, lambda command: {"ok": True})
