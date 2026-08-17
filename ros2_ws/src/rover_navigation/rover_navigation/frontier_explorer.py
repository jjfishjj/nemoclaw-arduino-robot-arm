import math
import sys

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from tf2_ros import Buffer, TransformException, TransformListener

from .frontier_math import cluster_frontiers, frontier_cells, nearest_free_cell


class FrontierExplorer(Node):
    def __init__(self, maximum_goals):
        super().__init__("rover_frontier_explorer")
        self.maximum_goals = maximum_goals
        self.map_msg = None
        self.blacklist = []
        self.client = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(OccupancyGrid, "/map", self.on_map, 1)

    def on_map(self, message):
        self.map_msg = message

    def grid_to_world(self, gx, gy):
        info = self.map_msg.info
        local_x = (gx + 0.5) * info.resolution
        local_y = (gy + 0.5) * info.resolution
        q = info.origin.orientation
        yaw = 2.0 * math.atan2(q.z, q.w)
        return (
            info.origin.position.x + math.cos(yaw) * local_x - math.sin(yaw) * local_y,
            info.origin.position.y + math.sin(yaw) * local_x + math.cos(yaw) * local_y,
        )

    def robot_position(self):
        try:
            transform = self.tf_buffer.lookup_transform("map", "base_footprint", rclpy.time.Time())
        except TransformException as exc:
            raise RuntimeError(f"map to base transform unavailable: {exc}") from exc
        return transform.transform.translation.x, transform.transform.translation.y

    def choose_frontier(self):
        cells = frontier_cells(self.map_msg.data, self.map_msg.info.width, self.map_msg.info.height)
        clusters = cluster_frontiers(cells, minimum_size=8)
        robot_x, robot_y = self.robot_position()
        candidates = []
        for gx, gy, size in clusters:
            free_cell = nearest_free_cell(
                self.map_msg.data, self.map_msg.info.width, self.map_msg.info.height, gx, gy
            )
            if free_cell is None:
                continue
            x, y = self.grid_to_world(*free_cell)
            if any(math.hypot(x - bx, y - by) < 0.55 for bx, by in self.blacklist):
                continue
            distance = math.hypot(x - robot_x, y - robot_y)
            if distance >= 0.45:
                candidates.append((distance - min(size, 100) * 0.002, x, y))
        return min(candidates, default=None)

    def navigate(self, x, y):
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.w = 1.0
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if handle is None or not handle.accepted:
            return False
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        return result is not None and result.status == GoalStatus.STATUS_SUCCEEDED

    def run(self):
        if not self.client.wait_for_server(timeout_sec=20.0):
            raise RuntimeError("/navigate_to_pose action server unavailable")
        deadline = self.get_clock().now() + Duration(seconds=20.0)
        while self.map_msg is None and self.get_clock().now() < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
        if self.map_msg is None:
            raise RuntimeError("/map was not received")
        completed = 0
        for _ in range(self.maximum_goals):
            target = self.choose_frontier()
            if target is None:
                self.get_logger().info("No reachable frontier candidates remain")
                break
            _, x, y = target
            self.get_logger().info(f"Exploring frontier x={x:.2f}, y={y:.2f}")
            if self.navigate(x, y):
                completed += 1
            else:
                self.blacklist.append((x, y))
        return completed


def main(args=None):
    cli = sys.argv[1:] if args is None else args
    if len(cli) > 1:
        raise SystemExit("usage: ros2 run rover_navigation frontier_explorer [MAX_GOALS]")
    maximum_goals = int(cli[0]) if cli else 12
    if maximum_goals <= 0:
        raise SystemExit("MAX_GOALS must be positive")
    rclpy.init()
    node = FrontierExplorer(maximum_goals)
    try:
        completed = node.run()
        print(f"PASS: frontier exploration completed {completed} navigation goals")
    finally:
        node.destroy_node()
        rclpy.shutdown()
