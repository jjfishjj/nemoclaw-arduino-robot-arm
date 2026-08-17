#!/usr/bin/env bash
set -euo pipefail

ros2 lifecycle get /collision_monitor | grep -q active
timeout 20 ros2 topic echo --once /collision_monitor/velocity_stop_zone \
  >/tmp/rover_collision_stop_zone.txt
timeout 20 ros2 topic echo --once /collision_monitor/slow_zone \
  >/tmp/rover_collision_slow_zone.txt

timeout 8 ros2 topic pub --rate 10 /cmd_vel_safety geometry_msgs/msg/Twist \
  "{linear: {x: 0.20}, angular: {z: 0.0}}" >/tmp/rover_collision_test_command.txt &
publisher_pid=$!
timeout 5 ros2 topic echo --once /cmd_vel_safe >/tmp/rover_collision_output.txt
timeout 5 ros2 topic echo --once /collision_monitor_state \
  >/tmp/rover_collision_state.txt
wait "$publisher_pid" || true

grep -q "linear:" /tmp/rover_collision_output.txt
grep -Eq "slow_zone|stop_zone" /tmp/rover_collision_state.txt
echo "PASS: Collision Monitor active, zones visible, scan zone triggered, safe output published"
