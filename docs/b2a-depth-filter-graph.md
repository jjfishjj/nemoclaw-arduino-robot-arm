# B2-A · Reproducible depth filter graph

The CI graph always executes `decimation → spatial → temporal → hole_filling`.
Order is part of the contract and cannot be supplied by the browser.

## Default parameters

- Decimation magnitude: 2
- Spatial alpha: 0.5; iterations: 2
- Temporal alpha: 0.4
- Hole-filling passes: 1

Each request replays frames from zero through the selected frame. This warms the
temporal stage deterministically and prevents output from depending on earlier
HTTP requests. The response includes per-stage resolution, invalid-depth ratio,
mean depth, roughness, processing time, and a SHA-256-derived fingerprint.

This Python backend is a test oracle, not a claim of pixel parity with
librealsense. B2-B will map the validated configuration to native RealSense
filters and compare native metrics against this contract.

The graph is read-only and every response keeps `motion_enabled=false`.
