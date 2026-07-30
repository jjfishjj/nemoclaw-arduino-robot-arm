import os

import pytest

from arm_bridge.core import SafetyError
from arm_bridge.secure_server import load_token, validate_c1_host
from scripts.configure_nemoclaw_c1 import render


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


def test_policy_is_exact_post_only_scope():
    policy = render("192.168.1.50", 8765, "/usr/bin/curl")
    assert 'host: 192.168.1.50' in policy
    assert 'allow: { method: POST, path: "/command" }' in policy
    assert "method: GET" not in policy
    assert 'path: "/**"' not in policy
    assert "__BRIDGE_" not in policy
