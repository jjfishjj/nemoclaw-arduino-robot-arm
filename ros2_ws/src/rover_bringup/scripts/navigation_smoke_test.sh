#!/usr/bin/env bash
set -euo pipefail

ros2 lifecycle get /controller_server | grep -q active
ros2 lifecycle get /collision_monitor | grep -q active
ros2 lifecycle get /waypoint_follower | grep -q active
timeout 20 ros2 topic echo --once /map >/tmp/rover_map.txt
timeout 20 ros2 topic echo --once /local_costmap/costmap >/tmp/rover_controller_costmap.txt
ros2 action list -t | grep -q "/follow_path.*nav2_msgs/action/FollowPath"
ros2 action list -t | grep -q "/follow_waypoints.*nav2_msgs/action/FollowWaypoints"
ros2 action list -t | grep -q "/navigate_through_poses.*nav2_msgs/action/NavigateThroughPoses"
ros2 service list | grep -q /slam_toolbox/save_map
ros2 service list | grep -q /slam_toolbox/serialize_map
ros2 run rover_navigation follow_mapping_loop
echo "PASS: SLAM map, MPPI action, Collision Monitor, local costmap, and map-save services"
