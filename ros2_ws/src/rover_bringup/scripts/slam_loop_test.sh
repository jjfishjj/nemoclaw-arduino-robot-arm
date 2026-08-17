#!/usr/bin/env bash
set -euo pipefail

output_prefix="${1:-$PWD/maps/loop_test}"
mkdir -p "$(dirname "$output_prefix")"

timeout 20 ros2 topic echo --once /map >/tmp/rover_slam_map_before.txt
timeout 20 ros2 topic echo --once /slam_toolbox/pose >/tmp/rover_slam_pose_before.txt

# Jazzy slam_toolbox publishes this event when the pose graph accepts a loop.
timeout 240 ros2 topic echo --once /slam_toolbox/loop_closure_event \
  >/tmp/rover_loop_closure_event.txt &
event_pid=$!
ros2 run rover_navigation follow_mapping_loop
wait "$event_pid"

timeout 20 ros2 topic echo --once /map >/tmp/rover_slam_map_after.txt
ros2 run rover_bringup save_slam_map.sh "$output_prefix"
echo "PASS: mapping loop completed, loop closure observed, map and pose graph saved"
