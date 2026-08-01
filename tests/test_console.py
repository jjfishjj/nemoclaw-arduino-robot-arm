import time

from arm_bridge.console import ConsoleState


def test_pairing_code_is_one_time_and_session_expires():
    state = ConsoleState("http://127.0.0.1:8765", "x" * 32, "123456")
    assert state.pair("000000") is None
    session = state.pair("123456")
    assert session and state.authenticated(session)
    assert state.pair("123456") is None
    state.sessions[session] = time.monotonic() - 1
    assert state.authenticated(session) is False


def test_pairing_locks_after_eight_failed_attempts():
    state = ConsoleState("http://127.0.0.1:8765", "x" * 32, "123456")
    for _ in range(8):
        assert state.pair("000000") is None
    assert state.pair("123456") is None


def test_frontend_never_contains_bridge_token():
    from arm_bridge.console import ASSETS

    content = "".join(path.read_text() for path in ASSETS.iterdir())
    assert "ARM_BRIDGE_TOKEN" not in content
    assert "localStorage" not in content
    assert "sessionStorage" not in content
