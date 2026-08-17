from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SafeCommand:
    linear_x: float
    angular_z: float
    scale: float
    state: str


def filter_velocity(
    linear_x: float,
    angular_z: float,
    closest_range: float,
    scan_fresh: bool,
    command_fresh: bool,
    stop_distance: float,
    slow_distance: float,
    maximum_reverse_speed: float,
    maximum_turn_speed: float,
) -> SafeCommand:
    """Apply a fail-safe front-obstacle policy to a planar velocity command."""
    if not scan_fresh or not command_fresh or not math.isfinite(closest_range):
        return SafeCommand(0.0, 0.0, 0.0, "FAILSAFE")
    if linear_x < 0.0:
        return SafeCommand(max(linear_x, -maximum_reverse_speed), angular_z, 1.0, "ESCAPE")
    if closest_range <= stop_distance:
        turn = max(-maximum_turn_speed, min(maximum_turn_speed, angular_z))
        return SafeCommand(0.0, turn, 0.0, "STOP")
    if closest_range < slow_distance:
        scale = (closest_range - stop_distance) / (slow_distance - stop_distance)
        scale = max(0.0, min(1.0, scale))
        return SafeCommand(linear_x * scale, angular_z * scale, scale, "SLOW")
    return SafeCommand(linear_x, angular_z, 1.0, "CLEAR")
