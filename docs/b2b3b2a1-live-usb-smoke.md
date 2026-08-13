# B2-B3B2A1 — Live USB smoke test

The manual **RealSense Live USB Smoke Test** workflow runs only on the trusted
default branch and a `self-hosted, linux, x64, realsense` runner. It verifies:

- readable and writable USB device-node access;
- `rs-enumerate-devices` serial number and firmware version;
- the same identity through `pyrealsense2`;
- 15 aligned 640×480 RGB-D frames with strictly increasing timestamps;
- unchanged dimensions and at least 70% valid depth in every frame.

An optional workflow input locks the test to an expected serial. The workflow
uploads JSON and Markdown evidence even when the capture fails, then exits
non-zero. It checks out without persisted credentials and has read-only
repository permission.

This workflow never imports or starts the Arduino bridge, never arms the robot,
and never sends a motion command. Every report explicitly records
`motion_enabled: false`.
