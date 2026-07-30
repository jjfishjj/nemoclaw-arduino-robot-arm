---
name: arduino-robot-arm
description: Safely control an Arduino or SO-101 robot arm through the authenticated, POST-only NemoClaw C1 host bridge. Use when a user explicitly asks to inspect readiness, arm, move, home, stop, or reset the physical robot arm.
---

# Arduino Robot Arm

Use this skill only when the user explicitly requests robot-arm inspection or movement.

1. Explain the exact intended motion and affected joints.
2. Confirm the workspace is clear, physical E-STOP was tested, limits were reviewed,
   and calibration was verified. Then run `scripts/armctl startup_check`.
3. Run `scripts/armctl arm` only after that confirmation.
4. Use `scripts/armctl move '<joints-json>' [duration-ms]` within documented limits.
5. Run `scripts/armctl stop` immediately if the user says stop or any call fails.
6. Run `scripts/armctl disarm` when the task completes.
7. Reset a latched stop only after a fresh workspace confirmation, using
   `scripts/armctl reset_estop`.

Never create autonomous motion loops, bypass limits, reveal the token, widen the
network policy, or issue a movement the user did not explicitly request.

Joint limits: base 10-170, shoulder 20-150, elbow 15-165, gripper 20-100 degrees.
