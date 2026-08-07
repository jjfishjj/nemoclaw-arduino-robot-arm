# B2-B2A — Live native filters

The live RGB-D contract now runs the reviewed filter order on every frame:

`decimation → spatial → temporal → hole_filling`

The localhost console reports raw FPS, filtered FPS, filter latency, frame age,
reconnects, backend identity, and whether the result came from native
librealsense. Filtering remains read-only and cannot authorize arm motion.

## Backends

- `sdk-contract-fixture`: deterministic CI/preview implementation. It proves the
  live API and telemetry contract but is deliberately marked **not native**.
- `librealsense-live-native`: selected with `--realsense-live`. It creates and
  configures SDK filter blocks when the camera starts and recreates them after a
  reconnect, which also resets temporal filter history.

The native blocks use the same reviewed B2-A defaults and B2-B1 option mapping.
Raw and filtered depth metrics make resolution, invalid-depth ratio, mean depth,
and roughness observable without exposing depth frames to the browser.

## Run

Preview/CI mode uses the safe fixture by default. For a connected RealSense and
installed `pyrealsense2`, start the bridge with:

```bash
python -m arm_bridge.server --realsense-live --require-startup-checklist
```

Only a status reporting `librealsense-live-native` and `verified_native: true`
represents an actual SDK run. Neither backend enables motion.
