import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32

from .scan_math import forward_ranges, obstacle_detected


class ObstacleDetector(Node):
    def __init__(self) -> None:
        super().__init__("obstacle_detector")
        self.declare_parameter("detection_range", 1.0)
        self.declare_parameter("forward_half_angle", 0.35)
        self.declare_parameter("minimum_valid_range", 0.12)
        self.detected_pub = self.create_publisher(Bool, "/obstacle_detected", 10)
        self.closest_pub = self.create_publisher(Float32, "/closest_obstacle_range", 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)

    def on_scan(self, scan: LaserScan) -> None:
        values = forward_ranges(
            scan.ranges,
            scan.angle_min,
            scan.angle_increment,
            float(self.get_parameter("forward_half_angle").value),
            float(self.get_parameter("minimum_valid_range").value),
        )
        detected, closest = obstacle_detected(
            values, float(self.get_parameter("detection_range").value)
        )
        self.detected_pub.publish(Bool(data=detected))
        self.closest_pub.publish(Float32(data=closest if math.isfinite(closest) else -1.0))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ObstacleDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
