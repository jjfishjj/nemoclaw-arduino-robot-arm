from types import SimpleNamespace
import sys

import pytest

from arm_bridge.core import ArmController, MockTransport, SafetyError
from arm_bridge.secure_server import load_token, validate_c1_host
from arm_bridge.server import build_controller, main
from scripts.configure_nemoclaw_c1 import render


def controller_args(**overrides):
    values = {
        "robot": "arduino4",
        "serial": None,
        "allow_real_motion": False,
        "require_startup_checklist": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_c1_rejects_short_or_missing_token(monkeypatch):
    monkeypatch.delenv("ARM_BRIDGE_TOKEN", raising=False)
    with pytest.raises(SafetyError, match="at least 32"):
        load_token()
    monkeypatch.setenv("ARM_BRIDGE_TOKEN", "short")
    with pytest.raises(SafetyError, match="at least 32"):
        load_token()


def test_c1_accepts_strong_environment_token(monkeypatch):
    monkeypatch.setenv("ARM_BRIDGE_TOKEN", "a" * 32)
    assert load_token() == "a" * 32


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0", "::1", "ff02::1"])
def test_c1_rejects_unsafe_bind_addresses(host):
    with pytest.raises(SafetyError):
        validate_c1_host(host)


def test_build_controller_defaults_to_mock_mode():
    controller = build_controller(controller_args())

    assert isinstance(controller, ArmController)
    assert isinstance(controller.transport, MockTransport)
    assert controller.status()["armed"] is False


def test_build_controller_requires_explicit_opt_in_for_serial():
    with pytest.raises(SafetyError, match="--allow-real-motion"):
        build_controller(controller_args(serial="/dev/ttyACM0"))


def test_build_controller_requires_serial_when_real_motion_is_allowed():
    with pytest.raises(SafetyError, match="requires --serial"):
        build_controller(controller_args(allow_real_motion=True))


def test_build_controller_uses_serial_only_after_explicit_opt_in(monkeypatch):
    class FakeSerialTransport:
        def __init__(self, port):
            self.port = port

    monkeypatch.setattr("arm_bridge.server.SerialTransport", FakeSerialTransport)
    controller = build_controller(
        controller_args(serial="/dev/ttyACM0", allow_real_motion=True)
    )

    assert isinstance(controller, ArmController)
    assert controller.transport.port == "/dev/ttyACM0"


def test_build_controller_rejects_unimplemented_robot_and_checklist_modes():
    with pytest.raises(SafetyError, match="SO-101 is currently a ROS 2 simulation scaffold"):
        build_controller(controller_args(robot="so101"))
    with pytest.raises(SafetyError, match="startup-checklist enforcement is not implemented"):
        build_controller(controller_args(require_startup_checklist=True))


@pytest.mark.parametrize(
    "cli_args",
    [
        ["--serial", "/dev/ttyACM0"],
        ["--robot", "so101"],
        ["--require-startup-checklist"],
    ],
)
def test_arm_bridge_cli_rejects_unsafe_or_unimplemented_modes(monkeypatch, cli_args):
    monkeypatch.setattr(sys, "argv", ["arm-bridge", *cli_args])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_policy_is_exact_post_only_scope():
    policy = render("192.168.1.50", 8765, "/usr/bin/curl")
    assert "host: 192.168.1.50" in policy
    assert 'allow: { method: POST, path: "/command" }' in policy
    assert "method: GET" not in policy
    assert 'path: "/**"' not in policy
    assert "__BRIDGE_" not in policy
