import json
import math
from pathlib import Path


def load_route(path):
    data = json.loads(Path(path).read_text())
    frame_id = data.get("frame_id", "map")
    poses = data.get("poses")
    if not isinstance(frame_id, str) or not frame_id:
        raise ValueError("frame_id must be a non-empty string")
    if not isinstance(poses, list) or not poses:
        raise ValueError("route must contain at least one pose")
    result = []
    for index, pose in enumerate(poses):
        if not isinstance(pose, dict):
            raise ValueError(f"pose {index} must be an object")
        try:
            values = tuple(float(pose[key]) for key in ("x", "y", "yaw"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"pose {index} requires numeric x, y, yaw") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"pose {index} contains a non-finite value")
        result.append(values)
    return frame_id, result


def success_rate(completed, total):
    if total <= 0 or completed < 0 or completed > total:
        raise ValueError("completed and total counts are inconsistent")
    return completed / total
