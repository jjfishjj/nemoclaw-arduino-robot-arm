from __future__ import annotations

from .inference_engines import InferenceManager
from .schemas import InferenceResult, Telemetry


def evaluate(
    telemetry: Telemetry,
    *,
    manager: InferenceManager,
    anomaly_threshold: float = 0.7,
    temperature_threshold_c: float = 70,
) -> InferenceResult:
    score, latency_ms, engine, model_version = manager.predict_score(telemetry)
    reasons: list[str] = []
    if telemetry.temperature_c >= temperature_threshold_c:
        reasons.append("TEMP_HIGH")
    if telemetry.accel_rms_g >= 0.8:
        reasons.append("VIBRATION_HIGH")

    is_anomaly = bool(reasons) or score >= anomaly_threshold
    if not reasons:
        reasons.append("SCORE_HIGH" if is_anomaly else "WITHIN_RANGE")

    return InferenceResult(
        score=round(score, 4),
        is_anomaly=is_anomaly,
        reason_codes=reasons,
        engine=engine,
        latency_ms=round(latency_ms, 4),
        model_version=model_version,
    )
