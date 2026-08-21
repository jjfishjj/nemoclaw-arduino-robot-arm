from __future__ import annotations

import platform
import statistics
from datetime import datetime, timezone

from .inference_engines import InferenceManager
from .schemas import BenchmarkRequest, BenchmarkResult, Telemetry


def run_benchmark(manager: InferenceManager, request: BenchmarkRequest) -> BenchmarkResult:
    engine = manager.active
    sample = Telemetry(
        schema_version="1.0",
        device_id="benchmark-motor",
        ts=datetime.now(timezone.utc),
        temperature_c=58.0,
        accel_rms_g=0.62,
        sample_rate_hz=100,
    )

    for _ in range(request.warmup_runs):
        engine.predict_score(sample)

    latencies = [engine.predict_score(sample)[1] for _ in range(request.measured_runs)]
    ordered = sorted(latencies)
    return BenchmarkResult(
        engine=engine.name,
        model_version=engine.metadata()["model_version"],
        runtime_version=engine.metadata()["runtime_version"],
        device=engine.metadata()["device"],
        host_arch=platform.machine(),
        warmup_runs=request.warmup_runs,
        measured_runs=request.measured_runs,
        mean_ms=round(statistics.fmean(latencies), 4),
        p50_ms=round(_percentile(ordered, 0.50), 4),
        p95_ms=round(_percentile(ordered, 0.95), 4),
        min_ms=round(ordered[0], 4),
        max_ms=round(ordered[-1], 4),
        measured_at=datetime.now(timezone.utc),
        evidence="measured",
    )


def _percentile(values: list[float], quantile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction
