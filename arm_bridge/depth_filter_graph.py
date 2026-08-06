"""B2-A deterministic depth filter graph for fixture and CI validation."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Callable

from .core import SafetyError
from .realsense_playback import CameraIntrinsics, PlaybackSource, RGBDFrame


FILTER_ORDER = ("decimation", "spatial", "temporal", "hole_filling")
DEFAULT_CONFIG = {
    "decimation": {"magnitude": 2},
    "spatial": {"alpha": 0.5, "iterations": 2},
    "temporal": {"alpha": 0.4},
    "hole_filling": {"passes": 1},
}


@dataclass(frozen=True)
class FilteredDepth:
    depth_m: tuple[tuple[float, ...], ...]
    intrinsics: CameraIntrinsics


def _config(value: dict | None) -> dict:
    source = value or DEFAULT_CONFIG
    if tuple(source) != FILTER_ORDER:
        raise SafetyError("filter graph order must be decimation → spatial → temporal → hole_filling")
    try:
        magnitude = int(source["decimation"]["magnitude"])
        spatial_alpha = float(source["spatial"]["alpha"])
        iterations = int(source["spatial"]["iterations"])
        temporal_alpha = float(source["temporal"]["alpha"])
        passes = int(source["hole_filling"]["passes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SafetyError("filter graph parameters are incomplete") from exc
    if magnitude not in {2, 3, 4}:
        raise SafetyError("decimation magnitude must be 2, 3, or 4")
    if not 0.0 <= spatial_alpha <= 1.0 or not 0.0 <= temporal_alpha <= 1.0:
        raise SafetyError("filter alpha must be between 0 and 1")
    if not 1 <= iterations <= 5 or not 0 <= passes <= 3:
        raise SafetyError("spatial iterations must be 1-5 and hole filling passes 0-3")
    return {
        "decimation": {"magnitude": magnitude},
        "spatial": {"alpha": spatial_alpha, "iterations": iterations},
        "temporal": {"alpha": temporal_alpha},
        "hole_filling": {"passes": passes},
    }


def _metrics(depth: tuple[tuple[float, ...], ...]) -> dict:
    flat = [value for row in depth for value in row]
    valid = [value for value in flat if math.isfinite(value) and value > 0]
    edges = []
    for y, row in enumerate(depth):
        for x, value in enumerate(row):
            if value <= 0:
                continue
            if x + 1 < len(row) and row[x + 1] > 0:
                edges.append(abs(value - row[x + 1]))
            if y + 1 < len(depth) and depth[y + 1][x] > 0:
                edges.append(abs(value - depth[y + 1][x]))
    return {
        "width": len(depth[0]),
        "height": len(depth),
        "invalid_ratio": round(1 - len(valid) / len(flat), 6),
        "mean_depth_m": round(sum(valid) / len(valid), 6) if valid else None,
        "roughness_m": round(sum(edges) / len(edges), 6) if edges else 0.0,
    }


def _decimate(frame: RGBDFrame, magnitude: int) -> FilteredDepth:
    depth = []
    for y in range(0, frame.intrinsics.height, magnitude):
        row = []
        for x in range(0, frame.intrinsics.width, magnitude):
            block = [
                frame.depth_m[yy][xx]
                for yy in range(y, min(y + magnitude, frame.intrinsics.height))
                for xx in range(x, min(x + magnitude, frame.intrinsics.width))
                if frame.depth_m[yy][xx] > 0
            ]
            row.append(sorted(block)[len(block) // 2] if block else 0.0)
        depth.append(tuple(row))
    intr = frame.intrinsics
    scaled = CameraIntrinsics(
        width=len(depth[0]), height=len(depth), fx=intr.fx / magnitude, fy=intr.fy / magnitude,
        ppx=(intr.ppx + 0.5) / magnitude - 0.5, ppy=(intr.ppy + 0.5) / magnitude - 0.5,
    )
    return FilteredDepth(tuple(depth), scaled)


def _spatial(value: FilteredDepth, alpha: float, iterations: int) -> FilteredDepth:
    depth = value.depth_m
    for _ in range(iterations):
        rows = []
        for y, row in enumerate(depth):
            output = []
            for x, center in enumerate(row):
                if center <= 0:
                    output.append(0.0)
                    continue
                neighbors = [
                    depth[yy][xx]
                    for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
                    if 0 <= yy < len(depth) and 0 <= xx < len(row) and depth[yy][xx] > 0
                ]
                mean = sum(neighbors) / len(neighbors) if neighbors else center
                output.append(alpha * center + (1 - alpha) * mean)
            rows.append(tuple(output))
        depth = tuple(rows)
    return FilteredDepth(depth, value.intrinsics)


def _temporal(value: FilteredDepth, previous: FilteredDepth | None, alpha: float) -> FilteredDepth:
    if previous is None or previous.intrinsics != value.intrinsics:
        return value
    rows = []
    for y, row in enumerate(value.depth_m):
        output = []
        for x, current in enumerate(row):
            old = previous.depth_m[y][x]
            if current > 0 and old > 0:
                output.append(alpha * current + (1 - alpha) * old)
            else:
                output.append(current)
        rows.append(tuple(output))
    return FilteredDepth(tuple(rows), value.intrinsics)


def _fill_holes(value: FilteredDepth, passes: int) -> FilteredDepth:
    depth = value.depth_m
    for _ in range(passes):
        rows = []
        for y, row in enumerate(depth):
            output = []
            for x, center in enumerate(row):
                if center > 0:
                    output.append(center)
                    continue
                neighbors = [
                    depth[yy][xx]
                    for yy, xx in ((y, x - 1), (y, x + 1), (y - 1, x), (y + 1, x))
                    if 0 <= yy < len(depth) and 0 <= xx < len(row) and depth[yy][xx] > 0
                ]
                output.append(min(neighbors) if neighbors else 0.0)
            rows.append(tuple(output))
        depth = tuple(rows)
    return FilteredDepth(depth, value.intrinsics)


class FilterGraphContract:
    def __init__(self, clock: Callable[[], float] = time.perf_counter):
        self.clock = clock

    def run(self, source: PlaybackSource, frame_index: int, config: dict | None = None) -> dict:
        params = _config(config)
        if frame_index < 0 or frame_index >= source.frame_count:
            raise SafetyError("filter frame is outside the recording")
        previous = None
        final = None
        stages = None
        elapsed_ms = 0.0
        for index in range(frame_index + 1):
            frame = source.frame(index)
            started = self.clock()
            decimated = _decimate(frame, params["decimation"]["magnitude"])
            spatial = _spatial(decimated, **params["spatial"])
            temporal = _temporal(spatial, previous, params["temporal"]["alpha"])
            filled = _fill_holes(temporal, params["hole_filling"]["passes"])
            elapsed_ms = (self.clock() - started) * 1000
            previous = temporal
            final = filled
            stages = (
                ("decimation", decimated), ("spatial", spatial),
                ("temporal", temporal), ("hole_filling", filled),
            )
        assert final is not None and stages is not None
        serial = [[round(value, 8) for value in row] for row in final.depth_m]
        fingerprint = hashlib.sha256(json.dumps(serial, separators=(",", ":")).encode()).hexdigest()[:16]
        return {
            "ok": True,
            "frame_index": frame_index,
            "order": list(FILTER_ORDER),
            "config": params,
            "stages": [{"name": name, **_metrics(value.depth_m)} for name, value in stages],
            "output": {**_metrics(final.depth_m), "fingerprint": fingerprint},
            "processing_ms": round(elapsed_ms, 3),
            "backend": "deterministic-python",
            "motion_enabled": False,
        }
