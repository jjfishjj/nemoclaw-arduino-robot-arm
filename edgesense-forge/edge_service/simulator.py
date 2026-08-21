from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timezone

from .mqtt_bridge import MQTTBridge
from .runtime import RuntimeRegistry
from .schemas import SimulatorStartRequest, SimulatorState


SCENARIOS = {
    "normal": (42.2, 0.18),
    "overheat": (76.4, 0.24),
    "vibration": (48.6, 1.42),
}


class MQTTSimulator:
    def __init__(self, bridge: MQTTBridge, registry: RuntimeRegistry) -> None:
        self.bridge = bridge
        self.registry = registry
        self._task: asyncio.Task | None = None
        self._request: SimulatorStartRequest | None = None
        self._count = 0

    @property
    def state(self) -> SimulatorState:
        return SimulatorState(
            running=self._task is not None and not self._task.done(),
            scenario=self._request.scenario if self._request else None,
            device_id=self._request.device_id if self._request else None,
            publish_count=self._count,
        )

    async def start(self, request: SimulatorStartRequest) -> SimulatorState:
        await self.stop()
        if not self.bridge.connected:
            raise RuntimeError("MQTT broker is not connected")
        self._request = request
        self._count = 0
        self.registry.configure(
            request.device_id,
            anomaly_threshold=request.anomaly_threshold,
            temperature_threshold_c=request.temperature_threshold_c,
        )
        self._task = asyncio.create_task(self._run(request), name="mqtt-simulator")
        return self.state

    async def stop(self) -> SimulatorState:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        return self.state

    async def reset(self) -> SimulatorState:
        await self.stop()
        self._request = None
        self._count = 0
        return self.state

    async def _run(self, request: SimulatorStartRequest) -> None:
        rng = random.Random(42 + list(SCENARIOS).index(request.scenario) * 101)
        base_temperature, base_vibration = SCENARIOS[request.scenario]
        step = 0
        while True:
            wave = math.sin(step / 2.3)
            noise = (rng.random() - 0.5) * 2
            payload = {
                "schema_version": "1.0",
                "device_id": request.device_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "temperature_c": round(base_temperature + wave * 0.8 + noise * 0.35, 1),
                "accel_rms_g": round(max(0, base_vibration + wave * 0.05 + noise * 0.035), 2),
                "sample_rate_hz": request.sample_rate_hz,
            }
            self.bridge.publish(f"edgesense/v1/{request.device_id}/telemetry", payload)
            self._count += 1
            step += 1
            await asyncio.sleep(1)
