#!/usr/bin/env bash
set -euo pipefail

timeout 20 ros2 topic echo --once /clock >/tmp/rover_clock.txt
timeout 20 ros2 topic echo --once /scan >/tmp/rover_scan.txt
ros2 topic list | grep -q '^/bumper/contacts$'
ros2 topic list | grep -q '^/camera/image_raw$'
grep -q "frame_id: lidar_link" /tmp/rover_scan.txt
ros2 control list_controllers | tee /tmp/rover_gazebo_controllers.txt
grep -q "joint_state_broadcaster.*active" /tmp/rover_gazebo_controllers.txt
grep -q "diff_drive_controller.*active" /tmp/rover_gazebo_controllers.txt
timeout 20 ros2 topic echo --once /local_costmap/costmap >/tmp/rover_local_costmap.txt
grep -q "frame_id: odom" /tmp/rover_local_costmap.txt

before="$(timeout 10 ros2 topic echo --once /diff_drive_controller/odom)"

# The panel starts inside stop_distance. A forward command must be zeroed.
ros2 topic pub --rate 10 --times 15 /cmd_vel_nav geometry_msgs/msg/Twist \
  "{linear: {x: 0.20}, angular: {z: 0.0}}" >/tmp/rover_forward_pub.txt &
forward_pid=$!
sleep 0.3
safe_forward="$(timeout 10 ros2 topic echo --once /cmd_vel_safe)"
safety_state="$(timeout 10 ros2 topic echo --once /safety_state)"
wait "$forward_pid"
grep -q "x: 0.0" <<<"$safe_forward"
grep -q "data: STOP" <<<"$safety_state"

# Reverse is capped but permitted as an escape maneuver and must change odom.
ros2 topic pub --rate 10 --times 20 /cmd_vel_nav geometry_msgs/msg/Twist \
  "{linear: {x: -0.10}, angular: {z: 0.0}}"
after="$(timeout 10 ros2 topic echo --once /diff_drive_controller/odom)"

# After command input expires, the filter must publish a zero fail-safe command.
sleep 0.7
failsafe_command="$(timeout 10 ros2 topic echo --once /cmd_vel_safe)"
failsafe_state="$(timeout 10 ros2 topic echo --once /safety_state)"
grep -q "x: 0.0" <<<"$failsafe_command"
grep -q "data: FAILSAFE" <<<"$failsafe_state"

printf '%s\n' "$before" >/tmp/rover_odom_before.txt
printf '%s\n' "$after" >/tmp/rover_odom_after.txt
if cmp -s /tmp/rover_odom_before.txt /tmp/rover_odom_after.txt; then
  echo "FAIL: odometry did not change" >&2
  exit 1
fi
ros2 run rover_perception lidar_contract_test
obstacle="$(timeout 10 ros2 topic echo --once /obstacle_detected)"
grep -q "data: true" <<<"$obstacle"
echo "PASS: clock, LiDAR, local costmap, STOP/FAILSAFE filtering, escape motion, controllers, and odometry"
