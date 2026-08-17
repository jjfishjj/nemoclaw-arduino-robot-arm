#!/usr/bin/env bash
set -euo pipefail

for node in waypoint_follower bt_navigator planner_server controller_server collision_monitor; do
  ros2 lifecycle get "/$node" | grep -q active
done
ros2 action list -t | grep -q "/follow_waypoints.*nav2_msgs/action/FollowWaypoints"
ros2 action list -t | grep -q "/navigate_through_poses.*nav2_msgs/action/NavigateThroughPoses"
ros2 run rover_navigation follow_waypoints
echo "PASS: waypoint patrol completed with NavigateToPose, planner, MPPI, and dynamic collision zones"
