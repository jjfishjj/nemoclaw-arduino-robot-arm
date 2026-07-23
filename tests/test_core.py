import pytest

from arm_bridge.core import ArmController, MockTransport, SafetyError


def controller():
    return ArmController(MockTransport(), min_interval=0)


def test_movement_requires_arming():
    with pytest.raises(SafetyError, match="disarmed"):
        controller().execute({"command": "home"})


def test_valid_move_updates_mock_state():
    arm = controller()
    arm.execute({"command": "arm"})
    result = arm.execute({"command": "move", "joints": {"base": 120}, "duration_ms": 500})
    assert result["state"]["base"] == 120


@pytest.mark.parametrize("request", [
    {"command": "move", "joints": {"base": 180}},
    {"command": "move", "joints": {"wrist": 90}},
    {"command": "move", "joints": {"base": 90.5}},
    {"command": "move", "joints": {"base": 90}, "duration_ms": 9999},
])
def test_rejects_unsafe_move(request):
    arm = controller()
    arm.execute({"command": "arm"})
    with pytest.raises(SafetyError):
        arm.execute(request)


def test_stop_disarms():
    arm = controller()
    arm.execute({"command": "arm"})
    arm.execute({"command": "stop"})
    assert arm.status()["armed"] is False

