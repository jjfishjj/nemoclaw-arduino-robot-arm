#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] controllers"
ros2 control list_controllers | tee /tmp/rover_controllers.txt
grep -q "joint_state_broadcaster.*active" /tmp/rover_controllers.txt
grep -q "diff_drive_controller.*active" /tmp/rover_controllers.txt

echo "[2/4] hardware interfaces"
ros2 control list_hardware_interfaces | tee /tmp/rover_interfaces.txt
grep -q "left_wheel_joint/velocity.*claimed" /tmp/rover_interfaces.txt
grep -q "right_wheel_joint/velocity.*claimed" /tmp/rover_interfaces.txt

echo "[3/4] publish a bounded command"
ros2 topic pub --once /diff_drive_controller/cmd_vel_unstamped geometry_msgs/msg/Twist \
  "{linear: {x: 0.15}, angular: {z: 0.25}}"
sleep 1

echo "[4/4] verify odometry"
ros2 topic echo --once /diff_drive_controller/odom
echo "Rover mock smoke test passed."
