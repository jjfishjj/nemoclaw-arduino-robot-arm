#!/usr/bin/env bash
set -euo pipefail

for node in map_server amcl controller_server planner_server behavior_server bt_navigator waypoint_follower collision_monitor; do
  ros2 lifecycle get "/$node" | grep -q active
done
timeout 20 ros2 topic echo --once /map >/tmp/rover_localized_map.txt
timeout 20 ros2 topic echo --once /amcl_pose >/tmp/rover_amcl_pose.txt
ros2 action list -t | grep -q "/navigate_to_pose.*nav2_msgs/action/NavigateToPose"
ros2 run rover_navigation navigate_to_pose 1.5 1.2 1.57
echo "PASS: saved map loaded, AMCL localized, and NavigateToPose reached its goal"
