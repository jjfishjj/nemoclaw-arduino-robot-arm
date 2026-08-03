# D2-A · RealSense `.bag` playback

D2-A defines the RGB-D boundary before live camera or robot motion is allowed.
The localhost console can replay a deterministic recording, inspect aligned
color/depth frames, and convert a selected pixel plus depth into meters in
`camera_optical_frame`.

## Safety boundary

- Playback and coordinate conversion never send a bridge command.
- Every frame validates dimensions and camera intrinsics.
- Out-of-frame pixels, invalid frame indexes, and zero/invalid depth fail closed.
- Coordinates use the RealSense optical convention: +X right, +Y down, +Z forward.
- Camera-to-base transformation and real motion remain blocked until D2-C calibration.

## CI fixture and real bags

`arm_bridge/recordings/bench-rgbd.bag.json` is a tiny deterministic companion
fixture that implements the same frame contract without camera hardware. It is
not presented as sensor capture data.

For an actual recording, install `pip install -e '.[realsense]'` and construct
`RealSenseBagPlayback('/absolute/path/capture.bag')`. The SDK import is lazy, so
normal CI does not require `librealsense` or `pyrealsense2`.

## Contract endpoints

- `GET /api/realsense/recording`
- `POST /api/realsense/frame` with `{"index": 0}`
- `POST /api/realsense/deproject` with `{"index": 0, "x": 2, "y": 3}`

All endpoints require the localhost pairing cookie and same-origin POST checks.
