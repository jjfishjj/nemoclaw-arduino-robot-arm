import math


def densify_polyline(points, spacing=0.10):
    """Return (x, y, yaw) samples with no segment longer than spacing."""
    if len(points) < 2 or spacing <= 0.0:
        raise ValueError("at least two points and positive spacing are required")
    result = []
    for start, end in zip(points, points[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        yaw = math.atan2(dy, dx)
        steps = max(1, math.ceil(length / spacing))
        for index in range(steps):
            ratio = index / steps
            result.append((start[0] + ratio * dx, start[1] + ratio * dy, yaw))
    last_yaw = result[-1][2]
    result.append((points[-1][0], points[-1][1], last_yaw))
    return result


def yaw_quaternion(yaw: float) -> tuple[float, float]:
    if not math.isfinite(yaw):
        raise ValueError("yaw must be finite")
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)
