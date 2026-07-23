from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol


JOINT_LIMITS = {
    "base": (10, 170),
    "shoulder": (20, 150),
    "elbow": (15, 165),
    "gripper": (20, 100),
}
HOME = {"base": 90, "shoulder": 90, "elbow": 90, "gripper": 60}


class Transport(Protocol):
    def exchange(self, payload: dict) -> dict: ...


@dataclass
class MockTransport:
    state: dict[str, int] = field(default_factory=lambda: dict(HOME))
    history: list[dict] = field(default_factory=list)

    def exchange(self, payload: dict) -> dict:
        self.history.append(payload)
        if payload["command"] == "move":
            self.state.update(payload["joints"])
        elif payload["command"] == "home":
            self.state = dict(HOME)
        return {"ok": True, "mode": "mock", "state": dict(self.state)}


class SerialTransport:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0):
        import serial

        self.serial = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        time.sleep(2.0)

    def exchange(self, payload: dict) -> dict:
        self.serial.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        line = self.serial.readline()
        if not line:
            raise TimeoutError("Arduino did not respond")
        return json.loads(line.decode())


class SafetyError(ValueError):
    pass


class ArmController:
    def __init__(self, transport: Transport, min_interval: float = 0.25):
        self.transport = transport
        self.min_interval = min_interval
        self.armed = False
        self.last_command_at = 0.0
        self.lock = threading.Lock()

    def status(self) -> dict:
        return {"ok": True, "armed": self.armed, "limits": JOINT_LIMITS}

    def execute(self, request: dict) -> dict:
        command = request.get("command")
        if command == "arm":
            self.armed = True
            return {"ok": True, "armed": True}
        if command == "disarm":
            self.armed = False
            return {"ok": True, "armed": False}
        if command not in {"move", "home", "stop"}:
            raise SafetyError("command must be arm, disarm, move, home, or stop")
        if command in {"move", "home"} and not self.armed:
            raise SafetyError("arm is disarmed; send the arm command first")

        payload = {"command": command}
        if command == "move":
            joints = request.get("joints")
            if not isinstance(joints, dict) or not joints:
                raise SafetyError("move requires a non-empty joints object")
            unknown = set(joints) - set(JOINT_LIMITS)
            if unknown:
                raise SafetyError(f"unknown joints: {', '.join(sorted(unknown))}")
            clean = {}
            for name, value in joints.items():
                if isinstance(value, bool) or not isinstance(value, int):
                    raise SafetyError(f"{name} angle must be an integer")
                low, high = JOINT_LIMITS[name]
                if not low <= value <= high:
                    raise SafetyError(f"{name} must be between {low} and {high}")
                clean[name] = value
            duration_ms = request.get("duration_ms", 800)
            if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or not 100 <= duration_ms <= 5000:
                raise SafetyError("duration_ms must be an integer from 100 to 5000")
            payload.update(joints=clean, duration_ms=duration_ms)

        with self.lock:
            elapsed = time.monotonic() - self.last_command_at
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            response = self.transport.exchange(payload)
            self.last_command_at = time.monotonic()
        if command == "stop":
            self.armed = False
        return response

