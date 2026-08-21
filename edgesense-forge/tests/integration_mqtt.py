"""Live integration check; requires Mosquitto and the edge service."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

from paho.mqtt import publish
from websockets.sync.client import connect


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws/events"


def request(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(
        BASE_URL + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method="POST" if body is not None else "GET",
    )
    with urlopen(req, timeout=5) as response:
        return json.load(response)


status = request("/api/status")
assert status["mqtt_connected"] is True, status

with connect(WS_URL, open_timeout=5) as websocket:
    connection_event = json.loads(websocket.recv(timeout=5))
    assert connection_event == {"type": "connection", "status": "connected"}
    started = request(
        "/api/simulator/start",
        {
            "scenario": "vibration",
            "device_id": "integration-motor",
            "sample_rate_hz": 100,
            "anomaly_threshold": 0.7,
            "temperature_threshold_c": 70,
        },
    )
    assert started["running"] is True
    event = json.loads(websocket.recv(timeout=5))
    assert event["type"] == "telemetry", event
    assert event["telemetry"]["device_id"] == "integration-motor", event
    assert event["inference"]["is_anomaly"] is True, event
    assert "VIBRATION_HIGH" in event["inference"]["reason_codes"], event

    publish.single(
        "edgesense/v1/integration-invalid/telemetry",
        payload=json.dumps({"temperature_c": 42}),
        hostname="127.0.0.1",
        port=1883,
    )
    validation_event = json.loads(websocket.recv(timeout=5))
    while validation_event["type"] == "telemetry":
        validation_event = json.loads(websocket.recv(timeout=5))
    assert validation_event["type"] == "validation_error", validation_event
    assert validation_event["errors"], validation_event
    request("/api/simulator/stop", {})

print(json.dumps({
    "mqtt": status["broker"],
    "topic": event["topic"],
    "decision": event["inference"],
    "invalid_payload": validation_event["type"],
}, ensure_ascii=False, indent=2))
