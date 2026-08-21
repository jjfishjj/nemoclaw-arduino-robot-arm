from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DeviceRuntimeConfig:
    anomaly_threshold: float = 0.7
    temperature_threshold_c: float = 70


class RuntimeRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, DeviceRuntimeConfig] = {}

    def configure(
        self,
        device_id: str,
        *,
        anomaly_threshold: float,
        temperature_threshold_c: float,
    ) -> None:
        self._devices[device_id] = DeviceRuntimeConfig(
            anomaly_threshold=anomaly_threshold,
            temperature_threshold_c=temperature_threshold_c,
        )

    def get(self, device_id: str) -> DeviceRuntimeConfig:
        return self._devices.get(device_id, DeviceRuntimeConfig())
