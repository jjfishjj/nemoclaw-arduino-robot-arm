from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    device_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    ts: datetime
    temperature_c: float = Field(ge=-40, le=125)
    accel_rms_g: float = Field(ge=0, le=16)
    sample_rate_hz: int = Field(ge=10, le=400)

    @field_validator("ts")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone")
        return value


class InferenceResult(BaseModel):
    score: float = Field(ge=0, le=1)
    is_anomaly: bool
    reason_codes: list[str]
    engine: Literal["onnxruntime", "tensorrt"]
    latency_ms: float = Field(ge=0)
    model_version: str


class BenchmarkRequest(BaseModel):
    warmup_runs: int = Field(default=20, ge=1, le=500)
    measured_runs: int = Field(default=200, ge=10, le=5000)


class BenchmarkResult(BaseModel):
    engine: str
    model_version: str
    runtime_version: str
    device: str
    host_arch: str
    warmup_runs: int
    measured_runs: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    measured_at: datetime
    evidence: Literal["measured"]


class EdgeEvent(BaseModel):
    type: Literal["telemetry"] = "telemetry"
    received_at: datetime
    topic: str
    telemetry: Telemetry
    inference: InferenceResult


class ValidationEvent(BaseModel):
    type: Literal["validation_error"] = "validation_error"
    received_at: datetime
    topic: str
    errors: list[str]


class SimulatorStartRequest(BaseModel):
    scenario: Literal["normal", "overheat", "vibration"] = "normal"
    device_id: str = Field(default="motor-01", pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    sample_rate_hz: int = Field(default=100, ge=10, le=400)
    anomaly_threshold: float = Field(default=0.7, ge=0.1, le=0.99)
    temperature_threshold_c: float = Field(default=70, ge=20, le=120)


class SimulatorState(BaseModel):
    running: bool
    scenario: str | None = None
    device_id: str | None = None
    publish_count: int = 0


class RuntimeStatus(BaseModel):
    service: Literal["ready", "degraded"]
    mqtt_connected: bool
    websocket_clients: int
    simulator: SimulatorState
    broker: str


class AlertUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
    note: str = Field(default="", max_length=1000)
    actor: str = Field(default="operator", min_length=1, max_length=80)


class AlertRuleUpdate(BaseModel):
    enabled: bool = True
    anomaly_threshold: float = Field(ge=0.1, le=0.99)
    temperature_threshold_c: float = Field(ge=20, le=120)
    retention_days: int = Field(default=30, ge=1, le=3650)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
