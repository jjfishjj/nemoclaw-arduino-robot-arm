"""B2-B1 librealsense filter mapping and Python/native parity contract."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from .core import SafetyError
from .depth_filter_graph import FILTER_ORDER, FilterGraphContract, _config, _metrics
from .realsense_playback import PlaybackSource


PARITY_LIMITS = {
    "invalid_ratio_delta": 0.10,
    "mean_depth_delta_m": 0.05,
    "roughness_delta_m": 0.02,
}


def option_plan(config: dict | None) -> list[dict]:
    params = _config(config)
    passes = params["hole_filling"]["passes"]
    if passes > 2:
        raise SafetyError("librealsense hole filling mode must be 0, 1, or 2")
    return [
        {"stage": "decimation", "options": {"filter_magnitude": params["decimation"]["magnitude"]}},
        {"stage": "spatial", "options": {
            "filter_smooth_alpha": params["spatial"]["alpha"],
            "filter_magnitude": params["spatial"]["iterations"],
        }},
        {"stage": "temporal", "options": {"filter_smooth_alpha": params["temporal"]["alpha"]}},
        {"stage": "hole_filling", "options": {"holes_fill": passes}},
    ]


class NativeRunner(Protocol):
    backend: str
    verified_native: bool
    def run(self, frame_index: int, config: dict | None) -> dict: ...


class SDKContractFixtureRunner:
    """CI mapping oracle; deliberately not reported as a native SDK run."""

    backend = "sdk-contract-fixture"
    verified_native = False

    def __init__(self, source: PlaybackSource):
        self.source = source
        self.graph = FilterGraphContract()

    def run(self, frame_index: int, config: dict | None) -> dict:
        plan = option_plan(config)
        result = self.graph.run(self.source, frame_index, config)
        return {
            "backend": self.backend,
            "verified_native": self.verified_native,
            "order": [item["stage"] for item in plan],
            "option_plan": plan,
            "output": result["output"],
            "processing_ms": result["processing_ms"],
        }


class LibrealsenseBagRunner:
    backend = "librealsense-bag-native"
    verified_native = True

    def __init__(self, bag_path: str | Path):
        path = Path(bag_path).expanduser().resolve()
        if path.suffix.lower() != ".bag" or not path.is_file():
            raise SafetyError("native filter comparison requires an existing .bag file")
        try:
            import pyrealsense2 as rs  # type: ignore
        except ImportError as exc:
            raise SafetyError("install the 'realsense' extra for native .bag filters") from exc
        self.rs = rs
        self.path = path

    def _set(self, block, option_name: str, value: float) -> None:
        option = getattr(self.rs.option, option_name)
        if not block.supports(option):
            raise SafetyError(f"librealsense filter does not support {option_name}")
        block.set_option(option, float(value))

    def run(self, frame_index: int, config: dict | None) -> dict:
        if frame_index < 0:
            raise SafetyError("native filter frame must be non-negative")
        plan = option_plan(config)
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
        for block, stage in zip(blocks, plan, strict=True):
            for option_name, value in stage["options"].items():
                self._set(block, option_name, value)
        started = time.perf_counter()
        output = None
        try:
            for _ in range(frame_index + 1):
                aligned = align.process(pipeline.wait_for_frames(5000))
                depth = aligned.get_depth_frame()
                if not depth:
                    raise SafetyError(".bag frame has no depth stream")
                output = depth
                for block in blocks:
                    output = block.process(output)
        except RuntimeError as exc:
            raise SafetyError(f"native .bag playback ended or failed: {exc}") from exc
        finally:
            pipeline.stop()
        assert output is not None
        try:
            import numpy as np
            sensor = profile.get_device().first_depth_sensor()
            depth_m = np.asanyarray(output.get_data(), dtype=np.float32) * sensor.get_depth_scale()
            rows = tuple(tuple(float(value) for value in row) for row in depth_m)
        except Exception as exc:
            raise SafetyError(f"cannot read native filtered depth: {exc}") from exc
        return {
            "backend": self.backend,
            "verified_native": self.verified_native,
            "order": list(FILTER_ORDER),
            "option_plan": plan,
            "output": _metrics(rows),
            "processing_ms": round((time.perf_counter() - started) * 1000, 3),
        }


class NativeParityContract:
    def __init__(self, source: PlaybackSource, runner: NativeRunner):
        self.source = source
        self.runner = runner
        self.oracle = FilterGraphContract()

    def compare(self, frame_index: int, config: dict | None = None) -> dict:
        python = self.oracle.run(self.source, frame_index, config)
        native = self.runner.run(frame_index, config)
        if native["order"] != list(FILTER_ORDER):
            raise SafetyError("native filter order differs from the reviewed contract")
        p, n = python["output"], native["output"]
        deltas = {
            "invalid_ratio_delta": round(abs(p["invalid_ratio"] - n["invalid_ratio"]), 6),
            "mean_depth_delta_m": round(abs((p["mean_depth_m"] or 0) - (n["mean_depth_m"] or 0)), 6),
            "roughness_delta_m": round(abs(p["roughness_m"] - n["roughness_m"]), 6),
        }
        within_limits = all(deltas[key] <= limit for key, limit in PARITY_LIMITS.items())
        return {
            "ok": True,
            "frame_index": frame_index,
            "python": {"backend": python["backend"], "output": p, "processing_ms": python["processing_ms"]},
            "native": native,
            "deltas": deltas,
            "limits": PARITY_LIMITS,
            "within_limits": within_limits,
            "verified_native": native["verified_native"],
            "motion_enabled": False,
        }
