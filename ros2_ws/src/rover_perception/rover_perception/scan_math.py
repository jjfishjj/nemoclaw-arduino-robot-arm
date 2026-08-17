import math
from typing import Iterable, Sequence


def forward_ranges(
    ranges: Sequence[float],
    angle_min: float,
    angle_increment: float,
    half_angle: float,
    minimum_valid_range: float,
) -> list[float]:
    """Return finite, physically valid ranges inside the forward sector."""
    values = []
    for index, distance in enumerate(ranges):
        angle = angle_min + index * angle_increment
        if abs(angle) <= half_angle and math.isfinite(distance) and distance >= minimum_valid_range:
            values.append(float(distance))
    return values


def obstacle_detected(values: Iterable[float], detection_range: float) -> tuple[bool, float]:
    values = list(values)
    closest = min(values, default=math.inf)
    return closest < detection_range, closest
