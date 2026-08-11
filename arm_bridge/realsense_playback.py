"""D2-A RealSense bag playback and RGB-D coordinate contracts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .core import SafetyError


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    ppx: float
    ppy: float

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise SafetyError("RGB-D dimensions must be positive")
        if self.fx <= 0 or self.fy <= 0:
            raise SafetyError("camera focal lengths must be positive")


@dataclass(frozen=True)
class RGBDFrame:
    index: int
    timestamp_ms: float
    color_asset: str
    intrinsics: CameraIntrinsics
    depth_m: tuple[tuple[float, ...], ...]

    def validate(self) -> None:
        self.intrinsics.validate()
        if self.index < 0 or not math.isfinite(self.timestamp_ms):
            raise SafetyError("invalid RGB-D frame identity")
        if len(self.depth_m) != self.intrinsics.height:
            raise SafetyError("depth height does not match camera intrinsics")
        if any(len(row) != self.intrinsics.width for row in self.depth_m):
            raise SafetyError("depth width does not match camera intrinsics")

    def deproject(self, pixel_x: int, pixel_y: int) -> dict:
        if not (0 <= pixel_x < self.intrinsics.width and 0 <= pixel_y < self.intrinsics.height):
            raise SafetyError("pixel is outside the aligned RGB-D frame")
        depth = self.depth_m[pixel_y][pixel_x]
        if not math.isfinite(depth) or depth <= 0:
            raise SafetyError("selected pixel has no valid depth")
        x = (pixel_x - self.intrinsics.ppx) / self.intrinsics.fx * depth
        y = (pixel_y - self.intrinsics.ppy) / self.intrinsics.fy * depth
        return {
            "pixel": {"x": pixel_x, "y": pixel_y},
            "camera_m": {"x": round(x, 6), "y": round(y, 6), "z": round(depth, 6)},
            "frame": "camera_optical_frame",
            "convention": "+X right, +Y down, +Z forward",
        }


class PlaybackSource(Protocol):
    @property
    def frame_count(self) -> int: ...
    def frame(self, index: int) -> RGBDFrame: ...


class FixturePlayback:
    """Small deterministic recording that exercises the same contract in CI."""

    def __init__(self, manifest: str | Path):
        value = json.loads(Path(manifest).read_text(encoding="utf-8"))
        intrinsics = CameraIntrinsics(**value["intrinsics"])
        intrinsics.validate()
        self.name = str(value["name"])
        self.bag_name = str(value["bag_name"])
        self._frames = []
        for index, item in enumerate(value["frames"]):
            default_depth = float(item["default_depth_m"])
            rows = [[default_depth for _ in range(intrinsics.width)] for _ in range(intrinsics.height)]
            for sample in item.get("depth_samples", []):
                rows[int(sample["y"])][int(sample["x"])] = float(sample["depth_m"])
            frame = RGBDFrame(
                index=index,
                timestamp_ms=float(item["timestamp_ms"]),
                color_asset=str(item["color_asset"]),
                intrinsics=intrinsics,
                depth_m=tuple(tuple(row) for row in rows),
            )
            frame.validate()
            self._frames.append(frame)
        if not self._frames:
            raise SafetyError("recording must contain at least one RGB-D frame")

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def frame(self, index: int) -> RGBDFrame:
        if not 0 <= index < self.frame_count:
            raise SafetyError("playback frame is outside the recording")
        return self._frames[index]


class RealSenseBagPlayback:
    """Optional adapter for a real .bag; import is delayed so CI needs no SDK."""

    def __init__(self, bag_path: str | Path):
        path = Path(bag_path).expanduser().resolve()
        if path.suffix.lower() != ".bag" or not path.is_file():
            raise SafetyError("RealSense playback requires an existing .bag file")
        try:
            import pyrealsense2 as rs  # type: ignore
        except ImportError as exc:
            raise SafetyError("install the 'realsense' extra to read .bag files") from exc
        self._rs = rs
        self._pipeline = rs.pipeline()
        config = rs.config()
        config.enable_device_from_file(str(path), repeat_playback=False)
        profile = self._pipeline.start(config)
        profile.get_device().as_playback().set_real_time(False)
        self._depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
        self.name = "RealSense bag playback"
        self.bag_name = path.name
        self._frames: list[RGBDFrame] = []

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def read_next(self) -> RGBDFrame:
        try:
            frames = self._pipeline.wait_for_frames(5000)
            aligned = self._rs.align(self._rs.stream.color).process(frames)
            color = aligned.get_color_frame()
            depth = aligned.get_depth_frame()
            if not color or not depth:
                raise SafetyError("bag frame is missing aligned color or depth")
            intr = depth.profile.as_video_stream_profile().intrinsics
            camera = CameraIntrinsics(intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy)
            import numpy as np
            depth_m = np.asanyarray(depth.get_data()).astype(np.float32) * self._depth_scale
            rows = tuple(tuple(float(value) for value in row) for row in depth_m)
            frame = RGBDFrame(len(self._frames), frames.get_timestamp(), "", camera, rows)
            frame.validate()
            self._frames.append(frame)
            return frame
        except RuntimeError as exc:
            raise SafetyError(f"RealSense bag playback ended or failed: {exc}") from exc

    def frame(self, index: int) -> RGBDFrame:
        while len(self._frames) <= index:
            self.read_next()
        return self._frames[index]

    def close(self) -> None:
        self._pipeline.stop()


class PlaybackContract:
    def __init__(self, source: FixturePlayback):
        self.source = source

    def metadata(self) -> dict:
        frame = self.source.frame(0)
        intr = frame.intrinsics
        return {
            "ok": True,
            "mode": "recorded-rgbd",
            "recording": self.source.name,
            "bag_name": self.source.bag_name,
            "frame_count": self.source.frame_count,
            "intrinsics": {
                "width": intr.width, "height": intr.height,
                "fx": intr.fx, "fy": intr.fy, "ppx": intr.ppx, "ppy": intr.ppy,
            },
            "motion_enabled": False,
        }

    def frame(self, index: int) -> dict:
        frame = self.source.frame(index)
        return {
            "ok": True,
            "frame": {
                "index": frame.index,
                "timestamp_ms": frame.timestamp_ms,
                "color_asset": frame.color_asset,
                "depth_unit": "meter",
            },
        }

    def deproject(self, index: int, pixel_x: int, pixel_y: int) -> dict:
        result = self.source.frame(index).deproject(pixel_x, pixel_y)
        return {"ok": True, "frame_index": index, **result, "motion_enabled": False}


def default_playback() -> PlaybackContract:
    manifest = Path(__file__).with_name("recordings") / "bench-rgbd.bag.json"
    return PlaybackContract(FixturePlayback(manifest))
