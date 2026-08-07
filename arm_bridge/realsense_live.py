"""B2-B2A live RGB-D stream with reproducible native filter telemetry."""

from __future__ import annotations

import io
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Protocol

from .core import SafetyError
from .depth_filter_graph import (
    DEFAULT_CONFIG, FILTER_ORDER, FilteredDepth, _config, _decimate,
    _fill_holes, _metrics, _spatial, _temporal,
)
from .librealsense_filters import option_plan
from .realsense_playback import CameraIntrinsics, RGBDFrame


FRESH_FRAME_MS = 1000.0


@dataclass(frozen=True)
class LiveCapture:
    frame: RGBDFrame
    captured_at: float
    color_jpeg: bytes | None = None
    raw_metrics: dict | None = None
    filtered_metrics: dict | None = None
    filter_latency_ms: float = 0.0
    filter_backend: str = "unfiltered"
    verified_native: bool = False


class LiveSource(Protocol):
    name: str
    mode: str
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def read(self) -> LiveCapture: ...


class MockLiveSource:
    """Deterministic live source used by CI and the no-camera preview."""

    name = "RealSense live CI source"
    mode = "mock-live"

    def __init__(self, now: Callable[[], float] = time.monotonic, fail_reads: set[int] | None = None,
                 clock: Callable[[], float] = time.perf_counter):
        self.now = now
        self.fail_reads = fail_reads or set()
        self.read_count = 0
        self.running = False
        self.intrinsics = CameraIntrinsics(8, 6, 7.5, 7.5, 3.5, 2.5)
        self.clock = clock
        self.params = _config(DEFAULT_CONFIG)
        self.previous: FilteredDepth | None = None

    def start(self) -> None:
        self.previous = None
        self.running = True

    def stop(self) -> None:
        self.running = False

    def read(self) -> LiveCapture:
        if not self.running:
            raise SafetyError("live RGB-D source is stopped")
        self.read_count += 1
        if self.read_count in self.fail_reads:
            raise SafetyError("simulated RealSense disconnect")
        depth = 0.55 + (self.read_count % 3) * 0.002
        rows = tuple(tuple(depth for _ in range(8)) for _ in range(6))
        frame = RGBDFrame(
            index=self.read_count - 1,
            timestamp_ms=self.now() * 1000,
            color_asset="/vision/bench-a.svg" if self.read_count % 2 else "/vision/bench-b.svg",
            intrinsics=self.intrinsics,
            depth_m=rows,
        )
        frame.validate()
        started = self.clock()
        decimated = _decimate(frame, self.params["decimation"]["magnitude"])
        spatial = _spatial(decimated, **self.params["spatial"])
        temporal = _temporal(spatial, self.previous, self.params["temporal"]["alpha"])
        filtered = _fill_holes(temporal, self.params["hole_filling"]["passes"])
        self.previous = temporal
        latency = max(0.0, (self.clock() - started) * 1000)
        output = RGBDFrame(
            frame.index, frame.timestamp_ms, frame.color_asset,
            filtered.intrinsics, filtered.depth_m,
        )
        output.validate()
        return LiveCapture(
            output, self.now(), raw_metrics=_metrics(frame.depth_m),
            filtered_metrics=_metrics(filtered.depth_m), filter_latency_ms=round(latency, 3),
            filter_backend="sdk-contract-fixture", verified_native=False,
        )


class RealSenseLiveSource:
    """Lazy pyrealsense2 adapter. It is only constructed with --realsense-live."""

    name = "Intel RealSense live camera"
    mode = "realsense-live"

    def __init__(self, now: Callable[[], float] = time.monotonic):
        try:
            import pyrealsense2 as rs  # type: ignore
        except ImportError as exc:
            raise SafetyError("install the 'realsense' extra for live RGB-D") from exc
        self.rs = rs
        self.now = now
        self.pipeline = None
        self.align = rs.align(rs.stream.color)
        self.sequence = 0
        self.blocks = []
        self.depth_scale = None

    def _set(self, block, option_name: str, value: float) -> None:
        option = getattr(self.rs.option, option_name)
        if not block.supports(option):
            raise SafetyError(f"librealsense live filter does not support {option_name}")
        block.set_option(option, float(value))

    def start(self) -> None:
        if self.pipeline is not None:
            return
        pipeline = self.rs.pipeline()
        config = self.rs.config()
        config.enable_stream(self.rs.stream.depth, 640, 480, self.rs.format.z16, 30)
        config.enable_stream(self.rs.stream.color, 640, 480, self.rs.format.rgb8, 30)
        profile = pipeline.start(config)
        try:
            blocks = [
                self.rs.decimation_filter(), self.rs.spatial_filter(),
                self.rs.temporal_filter(), self.rs.hole_filling_filter(),
            ]
            for block, stage in zip(blocks, option_plan(DEFAULT_CONFIG), strict=True):
                for option_name, value in stage["options"].items():
                    self._set(block, option_name, value)
            self.depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
            self.blocks = blocks
            self.pipeline = pipeline
        except Exception:
            pipeline.stop()
            raise

    def stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
        self.blocks = []
        self.depth_scale = None

    def read(self) -> LiveCapture:
        if self.pipeline is None:
            raise SafetyError("live RGB-D source is stopped")
        try:
            frames = self.align.process(self.pipeline.wait_for_frames(2000))
            color = frames.get_color_frame()
            depth = frames.get_depth_frame()
            if not color or not depth:
                raise SafetyError("live frame is missing aligned color or depth")
            if self.depth_scale is None or not self.blocks:
                raise SafetyError("live native filter graph is not initialized")
            import numpy as np
            raw_array = np.asanyarray(depth.get_data()).astype(np.float32) * self.depth_scale
            raw_rows = tuple(tuple(float(value) for value in row) for row in raw_array)
            started = time.perf_counter()
            filtered = depth
            for block in self.blocks:
                filtered = block.process(filtered)
            latency = (time.perf_counter() - started) * 1000
            intr = filtered.profile.as_video_stream_profile().intrinsics
            camera = CameraIntrinsics(intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy)
            filtered_array = np.asanyarray(filtered.get_data()).astype(np.float32) * self.depth_scale
            rows = tuple(tuple(float(value) for value in row) for row in filtered_array)
            from PIL import Image
            color_intr = color.profile.as_video_stream_profile().intrinsics
            image = Image.frombytes("RGB", (color_intr.width, color_intr.height), bytes(color.get_data()))
            encoded = io.BytesIO()
            image.save(encoded, format="JPEG", quality=82)
            frame = RGBDFrame(self.sequence, frames.get_timestamp(), "/api/realsense/live/color.jpg", camera, rows)
            self.sequence += 1
            frame.validate()
            return LiveCapture(
                frame, self.now(), encoded.getvalue(), _metrics(raw_rows), _metrics(rows),
                round(latency, 3), "librealsense-live-native", True,
            )
        except (RuntimeError, ValueError) as exc:
            raise SafetyError(f"RealSense live read failed: {exc}") from exc


class LiveRGBDContract:
    def __init__(self, source: LiveSource, now: Callable[[], float] = time.monotonic):
        self.source = source
        self.now = now
        self.running = False
        self.connected = False
        self.reconnect_count = 0
        self.last_error: str | None = None
        self.latest: LiveCapture | None = None
        self.raw_frame_times: deque[float] = deque(maxlen=30)
        self.filtered_frame_times: deque[float] = deque(maxlen=30)
        self.lock = threading.RLock()

    def start(self) -> dict:
        with self.lock:
            if not self.running:
                self.source.start()
                self.running = True
                self.connected = True
                self.last_error = None
            return self.status()

    def stop(self) -> dict:
        with self.lock:
            self.source.stop()
            self.running = False
            self.connected = False
            self.raw_frame_times.clear()
            self.filtered_frame_times.clear()
            return self.status()

    def poll(self) -> dict:
        with self.lock:
            if not self.running:
                raise SafetyError("live RGB-D stream must be started before polling")
            try:
                capture = self.source.read()
                capture.frame.validate()
                self.latest = capture
                self.connected = True
                self.last_error = None
                self.raw_frame_times.append(capture.captured_at)
                self.filtered_frame_times.append(self.now())
                return {"ok": True, "frame": self._frame_payload(capture), "status": self.status()}
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)
                self.reconnect_count += 1
                try:
                    self.source.stop()
                    self.source.start()
                except Exception as reconnect_exc:
                    self.last_error = f"{self.last_error}; reconnect failed: {reconnect_exc}"
                return {"ok": False, "error": self.last_error, "status": self.status()}

    def _fps(self, times: deque[float]) -> float:
        if len(times) < 2:
            return 0.0
        span = times[-1] - times[0]
        return 0.0 if span <= 0 else round((len(times) - 1) / span, 1)

    def _age_ms(self) -> float | None:
        if self.latest is None:
            return None
        return round(max(0.0, (self.now() - self.latest.captured_at) * 1000), 1)

    def status(self) -> dict:
        with self.lock:
            age = self._age_ms()
            raw_fps = self._fps(self.raw_frame_times)
            filtered_fps = self._fps(self.filtered_frame_times)
            latest = self.latest
            return {
                "ok": True,
                "running": self.running,
                "connected": self.connected,
                "source": self.source.name,
                "mode": self.source.mode,
                "fps": filtered_fps,
                "raw_fps": raw_fps,
                "filtered_fps": filtered_fps,
                "filter_latency_ms": latest.filter_latency_ms if latest else None,
                "filter_backend": latest.filter_backend if latest else "pending",
                "verified_native": latest.verified_native if latest else False,
                "raw_metrics": latest.raw_metrics if latest else None,
                "filtered_metrics": latest.filtered_metrics if latest else None,
                "frame_age_ms": age,
                "fresh": age is not None and age <= FRESH_FRAME_MS and self.connected,
                "freshness_limit_ms": FRESH_FRAME_MS,
                "reconnect_count": self.reconnect_count,
                "last_error": self.last_error,
                "filters": list(FILTER_ORDER),
                "filter_options": option_plan(DEFAULT_CONFIG),
                "motion_enabled": False,
            }

    def _frame_payload(self, capture: LiveCapture) -> dict:
        frame = capture.frame
        return {
            "index": frame.index,
            "timestamp_ms": frame.timestamp_ms,
            "color_asset": frame.color_asset,
            "depth_unit": "meter",
            "intrinsics": {
                "width": frame.intrinsics.width, "height": frame.intrinsics.height,
                "fx": frame.intrinsics.fx, "fy": frame.intrinsics.fy,
                "ppx": frame.intrinsics.ppx, "ppy": frame.intrinsics.ppy,
            },
        }

    def color_jpeg(self) -> bytes:
        with self.lock:
            if self.latest is None or self.latest.color_jpeg is None:
                raise SafetyError("no live JPEG frame is available")
            return self.latest.color_jpeg


def default_live() -> LiveRGBDContract:
    return LiveRGBDContract(MockLiveSource())
