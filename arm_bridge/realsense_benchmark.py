"""B2-B3A single-pass librealsense .bag performance benchmark contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Protocol

from .core import SafetyError
from .depth_filter_graph import DEFAULT_CONFIG, FILTER_ORDER, _config
from .librealsense_filters import option_plan


SCHEMA_VERSION = 1
DEFAULT_REGRESSION_LIMITS = {
    "latency_p95_increase_ratio": 0.20,
    "fps_decrease_ratio": 0.10,
    "invalid_ratio_increase": 0.03,
}


class BenchmarkRunner(Protocol):
    backend: str
    verified_native: bool
    recording_sha256: str

    def sample(self, warmup_frames: int, sample_frames: int, config: dict) -> dict: ...


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise SafetyError("benchmark produced no samples")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize_benchmark(runner: BenchmarkRunner, *, warmup_frames: int = 30,
                        sample_frames: int = 120, config: dict | None = None) -> dict:
    if warmup_frames < 0 or sample_frames < 3:
        raise SafetyError("benchmark requires warmup >= 0 and at least 3 sample frames")
    params = _config(config or DEFAULT_CONFIG)
    result = runner.sample(warmup_frames, sample_frames, params)
    latencies = [float(value) for value in result.get("latencies_ms", [])]
    invalid = [float(value) for value in result.get("invalid_ratios", [])]
    elapsed_ms = float(result.get("elapsed_ms", 0))
    if len(latencies) != sample_frames or len(invalid) != sample_frames or elapsed_ms <= 0:
        raise SafetyError("benchmark runner returned incomplete samples")
    if any(value < 0 or not math.isfinite(value) for value in latencies):
        raise SafetyError("benchmark latency samples must be finite and non-negative")
    if any(not 0 <= value <= 1 or not math.isfinite(value) for value in invalid):
        raise SafetyError("benchmark invalid ratios must be finite values between 0 and 1")
    return {
        "schema_version": SCHEMA_VERSION,
        "recording_sha256": runner.recording_sha256,
        "backend": runner.backend,
        "verified_native": runner.verified_native,
        "warmup_frames": warmup_frames,
        "sample_frames": sample_frames,
        "filter_order": list(FILTER_ORDER),
        "filter_config": params,
        "metrics": {
            "latency_ms": {
                "p50": round(_percentile(latencies, 0.50), 3),
                "p95": round(_percentile(latencies, 0.95), 3),
            },
            "fps": round(sample_frames / (elapsed_ms / 1000), 3),
            "invalid_ratio": {
                "mean": round(sum(invalid) / len(invalid), 6),
                "p95": round(_percentile(invalid, 0.95), 6),
            },
        },
        "motion_enabled": False,
    }


def compare_benchmark(current: dict, baseline: dict, limits: dict | None = None,
                      *, require_native: bool = True) -> dict:
    thresholds = {**DEFAULT_REGRESSION_LIMITS, **(limits or {})}
    if set(thresholds) != set(DEFAULT_REGRESSION_LIMITS) or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
        for value in thresholds.values()
    ):
        raise SafetyError("benchmark regression limits are invalid")
    for name, report in (("current", current), ("baseline", baseline)):
        if report.get("schema_version") != SCHEMA_VERSION:
            raise SafetyError(f"{name} benchmark schema is unsupported")
        if require_native and report.get("verified_native") is not True:
            raise SafetyError(f"{name} benchmark is not native verified")
    for field in ("recording_sha256", "filter_order", "filter_config", "sample_frames"):
        if current.get(field) != baseline.get(field):
            raise SafetyError(f"benchmark {field} differs from baseline")
    try:
        c, b = current["metrics"], baseline["metrics"]
        values = (
            c["latency_ms"]["p95"], b["latency_ms"]["p95"], c["fps"], b["fps"],
            c["invalid_ratio"]["mean"], b["invalid_ratio"]["mean"],
        )
    except (KeyError, TypeError) as exc:
        raise SafetyError("benchmark metrics are incomplete") from exc
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise SafetyError("benchmark metrics must be finite numbers")
    if b["latency_ms"]["p95"] <= 0 or b["fps"] <= 0 or c["fps"] <= 0:
        raise SafetyError("benchmark latency and FPS metrics must be positive")
    if not all(0 <= value <= 1 for value in (c["invalid_ratio"]["mean"], b["invalid_ratio"]["mean"])):
        raise SafetyError("benchmark invalid ratio metrics must be between 0 and 1")
    deltas = {
        "latency_p95_increase_ratio": round(c["latency_ms"]["p95"] / b["latency_ms"]["p95"] - 1, 6),
        "fps_decrease_ratio": round(1 - c["fps"] / b["fps"], 6),
        "invalid_ratio_increase": round(c["invalid_ratio"]["mean"] - b["invalid_ratio"]["mean"], 6),
    }
    violations = [name for name, value in deltas.items() if value > thresholds[name]]
    return {
        "ok": not violations,
        "regression": bool(violations),
        "violations": violations,
        "deltas": deltas,
        "limits": thresholds,
        "current": current,
        "baseline": baseline,
        "motion_enabled": False,
    }


class LibrealsenseBagBenchmarkRunner:
    backend = "librealsense-bag-native"
    verified_native = True

    def __init__(self, bag_path: str | Path):
        self.path = Path(bag_path).expanduser().resolve()
        if self.path.suffix.lower() != ".bag" or not self.path.is_file():
            raise SafetyError("benchmark requires an existing .bag recording")
        try:
            import pyrealsense2 as rs  # type: ignore
        except ImportError as exc:
            raise SafetyError("install the 'realsense' extra for native .bag benchmark") from exc
        self.rs = rs
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        self.recording_sha256 = digest.hexdigest()

    def _set(self, block, option_name: str, value: float) -> None:
        option = getattr(self.rs.option, option_name)
        if not block.supports(option):
            raise SafetyError(f"librealsense benchmark filter does not support {option_name}")
        block.set_option(option, float(value))

    def sample(self, warmup_frames: int, sample_frames: int, config: dict) -> dict:
        import numpy as np

        pipeline = self.rs.pipeline()
        cfg = self.rs.config()
        cfg.enable_device_from_file(str(self.path), repeat_playback=False)
        profile = pipeline.start(cfg)
        profile.get_device().as_playback().set_real_time(False)
        align = self.rs.align(self.rs.stream.color)
        blocks = [
            self.rs.decimation_filter(), self.rs.spatial_filter(),
            self.rs.temporal_filter(), self.rs.hole_filling_filter(),
        ]
        for block, stage in zip(blocks, option_plan(config), strict=True):
            for option_name, value in stage["options"].items():
                self._set(block, option_name, value)
        latencies, invalid_ratios = [], []
        measured_started = None
        try:
            for index in range(warmup_frames + sample_frames):
                aligned = align.process(pipeline.wait_for_frames(5000))
                depth = aligned.get_depth_frame()
                if not depth:
                    raise SafetyError(".bag benchmark frame has no depth stream")
                if index == warmup_frames:
                    measured_started = time.perf_counter()
                started = time.perf_counter()
                output = depth
                for block in blocks:
                    output = block.process(output)
                latency_ms = (time.perf_counter() - started) * 1000
                if index >= warmup_frames:
                    values = np.asanyarray(output.get_data())
                    latencies.append(latency_ms)
                    invalid_ratios.append(float(np.count_nonzero(values == 0) / values.size))
        except RuntimeError as exc:
            raise SafetyError(f".bag benchmark ended or failed: {exc}") from exc
        finally:
            measured_ended = time.perf_counter()
            pipeline.stop()
        assert measured_started is not None
        return {
            "latencies_ms": latencies,
            "invalid_ratios": invalid_ratios,
            "elapsed_ms": (measured_ended - measured_started) * 1000,
        }


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load benchmark baseline: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError("benchmark baseline must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark native librealsense filters on a .bag")
    parser.add_argument("bag", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        current = summarize_benchmark(
            LibrealsenseBagBenchmarkRunner(args.bag),
            warmup_frames=args.warmup, sample_frames=args.samples,
        )
        if args.write_baseline:
            args.baseline.parent.mkdir(parents=True, exist_ok=True)
            args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            report = {"ok": True, "baseline_written": str(args.baseline), "current": current}
        else:
            report = compare_benchmark(current, _load_json(args.baseline))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        if report.get("ok") is not True:
            raise SystemExit(2)
    except SafetyError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
