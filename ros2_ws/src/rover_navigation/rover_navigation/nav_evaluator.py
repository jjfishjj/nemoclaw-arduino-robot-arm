import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import FollowWaypoints
from nav2_msgs.msg import CollisionMonitorState
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path as NavigationPath
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from ros_gz_interfaces.msg import Contacts
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan

from .mission_client import MultiPoseClient
from .mission_math import load_route, success_rate


class NavigationEvaluator(Node):
    def __init__(self):
        super().__init__("rover_navigation_evaluator")
        self.client = ActionClient(self, FollowWaypoints, "/follow_waypoints")
        self.path_length = 0.0
        self.last_position = None
        self.minimum_range = math.inf
        self.latest_range = math.inf
        self.minimum_stop_distance = math.inf
        self.stop_events = 0
        self.slow_events = 0
        self.collision_proxy_events = 0
        self.contact_collision_events = 0
        self.last_contact_time = None
        self.maximum_penetration_depth = 0.0
        self.in_collision_proxy = False
        self.last_action = CollisionMonitorState.DO_NOTHING
        self.current_waypoint = 0
        self.plan_started_at = None
        self.planning_latencies = []
        self.first_sim_time = None
        self.last_sim_time = None
        self.first_clock_wall_time = None
        self.last_clock_wall_time = None
        self.clock_sample_count = 0
        self.create_subscription(Odometry, "/diff_drive_controller/odom", self.on_odom, 10)
        self.create_subscription(LaserScan, "/scan", self.on_scan, qos_profile_sensor_data)
        self.create_subscription(
            CollisionMonitorState, "/collision_monitor_state", self.on_collision_state, 10
        )
        self.create_subscription(Contacts, "/bumper/contacts", self.on_contacts, qos_profile_sensor_data)
        self.create_subscription(NavigationPath, "/plan", self.on_plan, 10)
        self.create_subscription(Clock, "/clock", self.on_clock, qos_profile_sensor_data)

    def on_clock(self, message):
        sim_time = message.clock.sec + message.clock.nanosec / 1_000_000_000
        wall_time = time.monotonic()
        if self.first_sim_time is None:
            self.first_sim_time = sim_time
            self.first_clock_wall_time = wall_time
        self.last_sim_time = sim_time
        self.last_clock_wall_time = wall_time
        self.clock_sample_count += 1

    def on_plan(self, _message):
        if self.plan_started_at is not None:
            self.planning_latencies.append((time.monotonic() - self.plan_started_at) * 1000.0)
            self.plan_started_at = None

    def on_odom(self, message):
        point = message.pose.pose.position
        position = (point.x, point.y)
        if self.last_position is not None:
            self.path_length += math.hypot(
                position[0] - self.last_position[0], position[1] - self.last_position[1]
            )
        self.last_position = position

    def on_scan(self, message):
        valid = [value for value in message.ranges if math.isfinite(value) and value >= message.range_min]
        self.latest_range = min(valid, default=math.inf)
        self.minimum_range = min(self.minimum_range, self.latest_range)
        collision_proxy = self.latest_range <= 0.27
        if collision_proxy and not self.in_collision_proxy:
            self.collision_proxy_events += 1
        self.in_collision_proxy = collision_proxy

    def on_collision_state(self, message):
        if message.action_type != self.last_action:
            if message.action_type == CollisionMonitorState.STOP:
                self.stop_events += 1
                self.minimum_stop_distance = min(self.minimum_stop_distance, self.latest_range)
            elif message.action_type == CollisionMonitorState.SLOWDOWN:
                self.slow_events += 1
        self.last_action = message.action_type

    def on_contacts(self, message):
        if not message.contacts:
            return
        now = time.monotonic()
        if self.last_contact_time is None or now - self.last_contact_time > 0.5:
            self.contact_collision_events += 1
        self.last_contact_time = now
        for contact in message.contacts:
            self.maximum_penetration_depth = max(
                self.maximum_penetration_depth, max(contact.depths, default=0.0)
            )

    def on_feedback(self, message):
        waypoint = int(message.feedback.current_waypoint)
        if waypoint > self.current_waypoint:
            self.current_waypoint = waypoint
            self.plan_started_at = time.monotonic()

    def evaluate(self, poses, timeout):
        if not self.client.wait_for_server(timeout_sec=20.0):
            raise RuntimeError("/follow_waypoints action server unavailable")
        goal = FollowWaypoints.Goal()
        goal.poses = poses
        goal.number_of_loops = 0
        self.plan_started_at = time.monotonic()
        future = self.client.send_goal_async(goal, feedback_callback=self.on_feedback)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError("evaluation patrol was rejected")
        result_future = handle.get_result_async()
        started = time.monotonic()
        while not result_future.done() and time.monotonic() - started < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
        timed_out = not result_future.done()
        if timed_out:
            cancel_future = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, cancel_future, timeout_sec=5.0)
            wrapped = None
        else:
            wrapped = result_future.result()
        elapsed = time.monotonic() - started
        missed = len(wrapped.result.missed_waypoints) if wrapped is not None else len(poses)
        succeeded = wrapped is not None and wrapped.status == GoalStatus.STATUS_SUCCEEDED
        completed = len(poses) if succeeded else max(0, len(poses) - missed)
        finite = lambda value: value if math.isfinite(value) else None
        real_time_factor = None
        if (
            self.first_sim_time is not None and self.last_sim_time is not None
            and self.first_clock_wall_time is not None and self.last_clock_wall_time is not None
        ):
            wall_delta = self.last_clock_wall_time - self.first_clock_wall_time
            if wall_delta > 0.0:
                real_time_factor = (self.last_sim_time - self.first_sim_time) / wall_delta
        mean_planning_latency = (
            sum(self.planning_latencies) / len(self.planning_latencies)
            if self.planning_latencies else None
        )
        gazebo_update_fps = None
        if (
            self.clock_sample_count > 1 and self.first_clock_wall_time is not None
            and self.last_clock_wall_time is not None
        ):
            clock_wall_delta = self.last_clock_wall_time - self.first_clock_wall_time
            if clock_wall_delta > 0.0:
                gazebo_update_fps = (self.clock_sample_count - 1) / clock_wall_delta
        return {
            "schema_version": 3,
            "goal_count": len(poses),
            "completed_goals": completed,
            "navigation_success": succeeded,
            "success_rate": success_rate(completed, len(poses)),
            "timed_out": timed_out,
            "elapsed_seconds": round(elapsed, 3),
            "path_length_m": round(self.path_length, 3),
            "minimum_lidar_range_m": finite(self.minimum_range),
            "minimum_stop_distance_m": finite(self.minimum_stop_distance),
            "collision_monitor_stop_events": self.stop_events,
            "collision_monitor_slow_events": self.slow_events,
            "collision_proxy_events": self.collision_proxy_events,
            "collision_proxy_rate": self.collision_proxy_events / len(poses),
            "collision_definition": "new LaserScan episode at or below 0.27 m",
            "contact_collision_events": self.contact_collision_events,
            "contact_collision_rate": self.contact_collision_events / len(poses),
            "maximum_contact_penetration_m": self.maximum_penetration_depth,
            "contact_collision_definition": "new Gazebo base contact episode after 0.5 s clear gap",
            "real_time_factor": finite(real_time_factor) if real_time_factor is not None else None,
            "gazebo_update_fps": finite(gazebo_update_fps) if gazebo_update_fps is not None else None,
            "gazebo_update_fps_definition": "/clock update samples per wall-clock second",
            "mean_planning_latency_ms": finite(mean_planning_latency) if mean_planning_latency is not None else None,
            "planning_latency_sample_count": len(self.planning_latencies),
            "planning_latency_definition": "FollowWaypoints child-goal start to next /plan publication",
        }


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("route", help="Patrol route JSON")
    parser.add_argument("output", help="Output KPI JSON")
    parser.add_argument("--timeout", type=float, default=300.0)
    options = parser.parse_args(args)
    if options.timeout <= 0.0:
        raise SystemExit("--timeout must be positive")
    frame_id, route = load_route(options.route)
    rclpy.init()
    evaluator = NavigationEvaluator()
    pose_builder = MultiPoseClient(FollowWaypoints, "/unused")
    try:
        report = evaluator.evaluate(pose_builder.make_poses(frame_id, route), options.timeout)
        Path(options.output).parent.mkdir(parents=True, exist_ok=True)
        Path(options.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        pose_builder.destroy_node()
        evaluator.destroy_node()
        rclpy.shutdown()
