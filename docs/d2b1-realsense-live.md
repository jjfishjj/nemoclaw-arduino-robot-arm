# D2-B1 · RealSense live RGB-D

The live contract adds explicit lifecycle and health telemetry before any depth
filtering or robot motion is considered.

## Contract

- Start and stop are explicit, idempotent operations.
- Each poll returns one color/depth-aligned frame plus rolling FPS.
- A frame older than 1000 ms is stale and cannot be described as fresh.
- Read failures set `connected=false`, increment `reconnect_count`, and restart
  the source. A later successful poll makes recovery observable.
- `filters=[]` is intentional in B1; B2 will own filter-chain configuration.
- `motion_enabled=false` is invariant for all live stream responses.

## Backends

The default console uses `MockLiveSource`, which needs no camera and is suitable
for CI. `RealSenseLiveSource` lazily imports `pyrealsense2`, configures aligned
640×480 color/depth at 30 FPS, and publishes a JPEG preview.

Real hardware is opt-in through the console's `--realsense-live` flag. Install
the optional dependency first with `pip install -e '.[realsense]'`.

## Local endpoints

- `GET /api/realsense/live/status`
- `POST /api/realsense/live/start`
- `POST /api/realsense/live/poll`
- `POST /api/realsense/live/stop`
- `GET /api/realsense/live/color.jpg` for the latest physical-camera JPEG
