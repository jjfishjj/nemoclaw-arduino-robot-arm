import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32, String

from .safety_math import filter_velocity
from .scan_math import forward_ranges


class SafetyVelocityFilter(Node):
    def __init__(self) -> None:
        super().__init__("safety_velocity_filter")
        defaults = {
            "input_topic": "/cmd_vel",
            "output_topic": "/cmd_vel_safe",
            "slow_distance": 1.50,
            "stop_distance": 0.85,
            "forward_half_angle": 0.35,
            "minimum_valid_range": 0.12,
            "scan_timeout": 0.35,
            "command_timeout": 0.50,
            "maximum_reverse_speed": 0.15,
            "maximum_turn_speed": 0.60,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        slow = float(self.get_parameter("slow_distance").value)
        stop = float(self.get_parameter("stop_distance").value)
        if slow <= stop:
            raise ValueError("slow_distance must be greater than stop_distance")

        self.last_scan_time = None
        self.last_command_time = None
        self.closest_range = math.inf
        self.command = Twist()
        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        if not input_topic or not output_topic or input_topic == output_topic:
            raise ValueError("input_topic and output_topic must be different non-empty topics")
        self.safe_pub = self.create_publisher(Twist, output_topic, 10)
        self.state_pub = self.create_publisher(String, "/safety_state", 10)
        self.scale_pub = self.create_publisher(Float32, "/safety_speed_scale", 10)
        self.detected_pub = self.create_publisher(Bool, "/obstacle_detected", 10)
        self.closest_pub = self.create_publisher(Float32, "/closest_obstacle_range", 10)
        self.create_subscription(Twist, input_topic, self.on_command, 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_timer(0.05, self.publish_safe_command)

    def on_command(self, command: Twist) -> None:
        self.command = command
        self.last_command_time = self.get_clock().now()

    def on_scan(self, scan: LaserScan) -> None:
        values = forward_ranges(
            scan.ranges, scan.angle_min, scan.angle_increment,
            float(self.get_parameter("forward_half_angle").value),
            float(self.get_parameter("minimum_valid_range").value),
        )
        self.closest_range = min(values, default=math.inf)
        self.last_scan_time = self.get_clock().now()

    def fresh(self, timestamp, timeout_name: str) -> bool:
        if timestamp is None:
            return False
        age = (self.get_clock().now() - timestamp).nanoseconds / 1e9
        return 0.0 <= age <= float(self.get_parameter(timeout_name).value)

    def publish_safe_command(self) -> None:
        result = filter_velocity(
            self.command.linear.x,
            self.command.angular.z,
            self.closest_range,
            self.fresh(self.last_scan_time, "scan_timeout"),
            self.fresh(self.last_command_time, "command_timeout"),
            float(self.get_parameter("stop_distance").value),
            float(self.get_parameter("slow_distance").value),
            float(self.get_parameter("maximum_reverse_speed").value),
            float(self.get_parameter("maximum_turn_speed").value),
        )
        output = Twist()
        output.linear.x = result.linear_x
        output.angular.z = result.angular_z
        self.safe_pub.publish(output)
        self.state_pub.publish(String(data=result.state))
        self.scale_pub.publish(Float32(data=result.scale))
        self.detected_pub.publish(Bool(data=result.state in ("SLOW", "STOP")))
        self.closest_pub.publish(Float32(
            data=self.closest_range if math.isfinite(self.closest_range) else -1.0
        ))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetyVelocityFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
