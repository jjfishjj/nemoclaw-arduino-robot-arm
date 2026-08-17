import sys

import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import FollowWaypoints, NavigateThroughPoses
from rclpy.action import ActionClient
from rclpy.node import Node

from .mission_math import load_route
from .path_math import yaw_quaternion


class MultiPoseClient(Node):
    def __init__(self, action_type, action_name):
        super().__init__("rover_multi_pose_client")
        self.client = ActionClient(self, action_type, action_name)
        self.action_name = action_name

    def make_poses(self, frame_id, route):
        stamp = self.get_clock().now().to_msg()
        result = []
        for x, y, yaw in route:
            pose = PoseStamped()
            pose.header.frame_id = frame_id
            pose.header.stamp = stamp
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation.z, pose.pose.orientation.w = yaw_quaternion(yaw)
            result.append(pose)
        return result

    def execute(self, goal):
        if not self.client.wait_for_server(timeout_sec=20.0):
            raise RuntimeError(f"{self.action_name} action server unavailable")
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError(f"{self.action_name} goal was rejected")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        wrapped = result_future.result()
        return wrapped is not None and wrapped.status == GoalStatus.STATUS_SUCCEEDED


def route_path(args):
    if len(args) > 1:
        raise SystemExit("usage: command [ROUTE.json]")
    if args:
        return args[0]
    return f"{get_package_share_directory('rover_navigation')}/config/patrol_route.json"


def run(action_type, action_name, args=None):
    path = route_path(sys.argv[1:] if args is None else args)
    frame_id, route = load_route(path)
    rclpy.init()
    node = MultiPoseClient(action_type, action_name)
    try:
        goal = action_type.Goal()
        goal.poses = node.make_poses(frame_id, route)
        if not node.execute(goal):
            raise RuntimeError(f"{action_name} did not finish successfully")
        print(f"PASS: {action_name} completed {len(route)} poses")
    finally:
        node.destroy_node()
        rclpy.shutdown()


def waypoint_main(args=None):
    run(FollowWaypoints, "/follow_waypoints", args)


def through_poses_main(args=None):
    run(NavigateThroughPoses, "/navigate_through_poses", args)
