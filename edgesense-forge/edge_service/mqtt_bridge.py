from __future__ import annotations

import asyncio
import json
import logging
import ssl
from concurrent.futures import Future

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from .hub import WebSocketHub
from .inference import evaluate
from .inference_engines import InferenceManager
from .runtime import RuntimeRegistry
from .schemas import EdgeEvent, Telemetry, ValidationEvent, utc_now
from .storage import EventStore

LOGGER = logging.getLogger(__name__)


class MQTTBridge:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        hub: WebSocketHub,
        registry: RuntimeRegistry,
        inference_manager: InferenceManager,
        store: EventStore,
        username: str | None = None,
        password: str | None = None,
        ca_cert: str | None = None,
        client_cert: str | None = None,
        client_key: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.hub = hub
        self.registry = registry
        self.inference_manager = inference_manager
        self.store = store
        self.connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="edgesense-edge-service")
        self._client.enable_logger(LOGGER)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        if username:
            self._client.username_pw_set(username, password)
        if ca_cert:
            self._client.tls_set(ca_certs=ca_cert, certfile=client_cert, keyfile=client_key,
                                 cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._client.connect_async(self.host, self.port, keepalive=30)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        self.connected = False

    def publish(self, topic: str, payload: dict) -> None:
        info = self._client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=0)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with code {info.rc}")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        self.connected = reason_code == 0
        if self.connected:
            client.subscribe("edgesense/v1/+/telemetry")
            LOGGER.info("Connected to MQTT broker at %s:%s", self.host, self.port)
        else:
            LOGGER.error("MQTT connection rejected: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.connected = False
        LOGGER.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        try:
            raw = json.loads(message.payload.decode("utf-8"))
            telemetry = Telemetry.model_validate(raw)
            config = self.registry.get(telemetry.device_id)
            rule = self.store.get_rule(telemetry.device_id)
            inference = evaluate(
                telemetry,
                manager=self.inference_manager,
                anomaly_threshold=rule["anomaly_threshold"] if rule["updated_at"] else config.anomaly_threshold,
                temperature_threshold_c=rule["temperature_threshold_c"] if rule["updated_at"] else config.temperature_threshold_c,
            )
            event = EdgeEvent(
                received_at=utc_now(),
                topic=message.topic,
                telemetry=telemetry,
                inference=inference,
            )
            payload = event.model_dump(mode="json")
            self.store.save_event(event, create_alert=bool(rule["enabled"]))
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            errors = exc.errors() if isinstance(exc, ValidationError) else [str(exc)]
            event = ValidationEvent(
                received_at=utc_now(),
                topic=message.topic,
                errors=[str(error) for error in errors],
            )
            payload = event.model_dump(mode="json")

        self._schedule_broadcast(payload)

    def _schedule_broadcast(self, payload: dict) -> Future | None:
        if self._loop is None or self._loop.is_closed():
            return None
        return asyncio.run_coroutine_threadsafe(self.hub.broadcast(payload), self._loop)
