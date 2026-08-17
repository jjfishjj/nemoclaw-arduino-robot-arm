import math

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowPath
from nav_msgs.msg import Path
from rclpy.action import ActionClient
from rclpy.node import Node

from .path_math import densify_polyline


LOOP_POINTS = [
    (0.0, 0.0),
    (0.0, -1.5),
    (1.8, -1.5),
    (1.8, 1.5),
    (0.0, 1.5),
    (0.0, 0.0),
]


class MappingLoopClient(Node):
    def __init__(self) -> None:
        super().__init__("mapping_loop_client")
        self.client = ActionClient(self, FollowPath, "/follow_path")

    def build_path(self) -> Path:
        path = Path()
        path.header.frame_id = "map"
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y, yaw in densify_polyline(LOOP_POINTS):
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation.z = math.sin(yaw / 2.0)
            pose.pose.orientation.w = math.cos(yaw / 2.0)
            path.poses.append(pose)
        return path

    def run(self) -> bool:
        if not self.client.wait_for_server(timeout_sec=15.0):
            raise RuntimeError("/follow_path action server unavailable")
        goal = FollowPath.Goal()
        goal.path = self.build_path()
        goal.controller_id = "FollowPath"
        goal.goal_checker_id = "goal_checker"
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError("MPPI rejected the mapping loop")
        self.get_logger().info(f"MPPI accepted {len(goal.path.poses)} path poses")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        wrapped = result_future.result()
        return wrapped is not None and wrapped.status == GoalStatus.STATUS_SUCCEEDED


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MappingLoopClient()
    try:
        if not node.run():
            raise RuntimeError("mapping loop did not finish successfully")
        print("PASS: MPPI completed the closed mapping path")
    finally:
        node.destroy_node()
        rclpy.shutdown()
