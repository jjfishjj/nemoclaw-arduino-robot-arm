# B2-B3A — RealSense `.bag` performance baseline

Run the reviewed native filter chain in one sequential playback pass. Warmup
frames initialize librealsense and temporal filter state but are excluded from
all reported statistics.

```bash
python -m arm_bridge.realsense_benchmark recording.bag \
  --baseline benchmarks/my-camera.json --warmup 30 --samples 120 \
  --write-baseline
```

Compare a later run with the same recording, config, and sample count:

```bash
python -m arm_bridge.realsense_benchmark recording.bag \
  --baseline benchmarks/my-camera.json --warmup 30 --samples 120 \
  --output artifacts/realsense-benchmark.json
```

The report contains filter latency P50/P95, end-to-end playback FPS, and mean/
P95 invalid-depth ratio. Default regression limits are:

- P95 latency increase: 20%
- FPS decrease: 10%
- Mean invalid ratio absolute increase: 3 percentage points

Native comparisons fail closed if the baseline is not native verified or if
the `.bag` SHA-256, filter order/config, or sample count differs. The committed
`benchmarks/realsense-bag-baseline.fixture.json` documents the schema for CI but
is deliberately marked `verified_native: false`; replace it only by running the
command against an actual recording. Benchmarking is read-only and never enables
robot motion.
