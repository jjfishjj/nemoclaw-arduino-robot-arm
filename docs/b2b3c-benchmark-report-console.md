# B2-B3C — Benchmark report console

The localhost console can render the reviewed native benchmark comparison and
CI gate without giving the browser write access to a baseline or robot motion.

```bash
python -m arm_bridge.console \
  --benchmark-report artifacts/realsense-hardware-gate/benchmark.json \
  --gate-report artifacts/realsense-hardware-gate/gate/gate-report.json
```

After local pairing, the report card shows baseline/current values and deltas
for latency P50, latency P95, FPS, and invalid-depth ratio. Health is:

- `HEALTHY`: a native gate report passes;
- `DEGRADED`: benchmark data exists but no gate report was supplied;
- `BLOCKED`: the gate failed/was invalid, the report is missing, or validation
  rejects unsafe or malformed data.

The endpoint is authenticated, localhost-only, cache-disabled, and read-only.
It reloads files from disk on refresh so a newly downloaded CI artifact can be
viewed without restarting the console.
