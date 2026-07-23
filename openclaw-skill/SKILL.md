---
name: arduino-robot-arm
description: Safely control the local Arduino robot arm through an allowlisted HTTP bridge.
---

# Arduino Robot Arm

Use this skill only when the user explicitly requests physical arm movement.

1. Explain the intended joint motion before executing it.
2. Ask the user to confirm that the workspace is clear and the emergency stop is reachable.
3. Arm the controller with `scripts/armctl arm`.
4. Use only `scripts/armctl move` with joint angles inside the documented limits.
5. Run `scripts/armctl stop` immediately if the user says stop or if any call fails.
6. Run `scripts/armctl disarm` when the task is complete.

Never create loops, bypass limits, bind the bridge publicly, or issue movements not explicitly requested.

Joint limits: base 10-170, shoulder 20-150, elbow 15-165, gripper 20-100 degrees.

