import math
import sys

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node

from .path_math import yaw_quaternion


class NavigateClient(Node):
    def __init__(self) -> None:
        super().__init__("rover_navigate_to_pose")
        self.client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

    def run(self, x: float, y: float, yaw: float) -> bool:
        if not all(math.isfinite(value) for value in (x, y, yaw)):
            raise ValueError("x, y, and yaw must be finite")
        if not self.client.wait_for_server(timeout_sec=20.0):
            raise RuntimeError("/navigate_to_pose action server unavailable")
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z, goal.pose.pose.orientation.w = yaw_quaternion(yaw)
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError("NavigateToPose goal was rejected")
        self.get_logger().info(f"Accepted map goal x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        return result is not None and result.status == GoalStatus.STATUS_SUCCEEDED


def main(args=None) -> None:
    cli = sys.argv[1:] if args is None else args
    if len(cli) != 3:
        raise SystemExit("usage: ros2 run rover_navigation navigate_to_pose X Y YAW_RADIANS")
    try:
        x, y, yaw = (float(value) for value in cli)
    except ValueError as exc:
        raise SystemExit(f"invalid numeric goal: {exc}") from exc
    rclpy.init()
    node = NavigateClient()
    try:
        if not node.run(x, y, yaw):
            raise RuntimeError("navigation did not finish successfully")
        print("PASS: NavigateToPose reached the requested map pose")
    finally:
        node.destroy_node()
        rclpy.shutdown()
