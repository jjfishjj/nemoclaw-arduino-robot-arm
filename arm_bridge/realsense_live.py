"""D2-B1 live RGB-D stream contract with reconnect and freshness metrics."""

from __future__ import annotations

import io
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Protocol

from .core import SafetyError
from .realsense_playback import CameraIntrinsics, RGBDFrame


FRESH_FRAME_MS = 1000.0


@dataclass(frozen=True)
class LiveCapture:
    frame: RGBDFrame
    captured_at: float
    color_jpeg: bytes | None = None


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

    def __init__(self, now: Callable[[], float] = time.monotonic, fail_reads: set[int] | None = None):
        self.now = now
        self.fail_reads = fail_reads or set()
        self.read_count = 0
        self.running = False
        self.intrinsics = CameraIntrinsics(8, 6, 7.5, 7.5, 3.5, 2.5)

    def start(self) -> None:
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
        return LiveCapture(frame, self.now())


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

    def start(self) -> None:
        if self.pipeline is not None:
            return
        pipeline = self.rs.pipeline()
        config = self.rs.config()
        config.enable_stream(self.rs.stream.depth, 640, 480, self.rs.format.z16, 30)
        config.enable_stream(self.rs.stream.color, 640, 480, self.rs.format.rgb8, 30)
        pipeline.start(config)
        self.pipeline = pipeline

    def stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None

    def read(self) -> LiveCapture:
        if self.pipeline is None:
            raise SafetyError("live RGB-D source is stopped")
        try:
            frames = self.align.process(self.pipeline.wait_for_frames(2000))
            color = frames.get_color_frame()
            depth = frames.get_depth_frame()
            if not color or not depth:
                raise SafetyError("live frame is missing aligned color or depth")
            intr = depth.profile.as_video_stream_profile().intrinsics
            camera = CameraIntrinsics(intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy)
            rows = tuple(tuple(depth.get_distance(x, y) for x in range(intr.width)) for y in range(intr.height))
            from PIL import Image
            image = Image.frombytes("RGB", (intr.width, intr.height), bytes(color.get_data()))
            encoded = io.BytesIO()
            image.save(encoded, format="JPEG", quality=82)
            frame = RGBDFrame(self.sequence, frames.get_timestamp(), "/api/realsense/live/color.jpg", camera, rows)
            self.sequence += 1
            frame.validate()
            return LiveCapture(frame, self.now(), encoded.getvalue())
        except RuntimeError as exc:
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
        self.frame_times: deque[float] = deque(maxlen=30)
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
            self.frame_times.clear()
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
                self.frame_times.append(capture.captured_at)
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

    def _fps(self) -> float:
        if len(self.frame_times) < 2:
            return 0.0
        span = self.frame_times[-1] - self.frame_times[0]
        return 0.0 if span <= 0 else round((len(self.frame_times) - 1) / span, 1)

    def _age_ms(self) -> float | None:
        if self.latest is None:
            return None
        return round(max(0.0, (self.now() - self.latest.captured_at) * 1000), 1)

    def status(self) -> dict:
        with self.lock:
            age = self._age_ms()
            return {
                "ok": True,
                "running": self.running,
                "connected": self.connected,
                "source": self.source.name,
                "mode": self.source.mode,
                "fps": self._fps(),
                "frame_age_ms": age,
                "fresh": age is not None and age <= FRESH_FRAME_MS and self.connected,
                "freshness_limit_ms": FRESH_FRAME_MS,
                "reconnect_count": self.reconnect_count,
                "last_error": self.last_error,
                "filters": [],
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
