# B2-B1 · Native librealsense `.bag` filters

B2-B1 maps the reviewed B2-A graph to librealsense SDK options and compares
native output against the deterministic Python oracle.

## Mapping

- decimation magnitude → `filter_magnitude`
- spatial alpha → `filter_smooth_alpha`
- spatial iterations → `filter_magnitude`
- temporal alpha → `filter_smooth_alpha`
- hole-filling passes → native `holes_fill` mode (0–2 only)

Each comparison starts a fresh non-real-time `.bag` pipeline and replays from
frame zero, preserving deterministic temporal warmup. Parity limits are 10%
invalid-depth ratio, 5 cm mean-depth drift, and 2 cm roughness drift.

Without `--realsense-bag /absolute/capture.bag`, the console uses an explicit
`sdk-contract-fixture`. It validates mapping and report shape but always returns
`verified_native=false`. It must never be cited as physical SDK verification.

Native and fixture comparison remain read-only with `motion_enabled=false`.
