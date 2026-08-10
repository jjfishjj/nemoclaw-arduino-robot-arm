# B2-B3B — Native parity CI gate

The gate consumes two JSON inputs: a B2-B3A benchmark comparison and a B2-B1
Python/librealsense parity report. Both current and baseline benchmark results,
and the native parity result, must explicitly be `verified_native: true` and
`motion_enabled: false`.

```bash
python -m arm_bridge.realsense_ci_gate \
  --benchmark artifacts/realsense-benchmark.json \
  --parity artifacts/realsense-parity.json \
  --output artifacts/realsense-native-gate \
  --github-annotations
```

Exit codes are stable CI contracts:

- `0`: native reports are trusted and all checks pass.
- `1`: trusted native reports contain a performance or parity regression.
- `2`: an input is missing, malformed, tampered, or not native verified.

Every outcome writes `gate-report.json` and `gate-summary.md`. Failure output
uses GitHub workflow command annotations. The local composite action at
`.github/actions/realsense-native-gate/action.yml` appends the Markdown to the
job summary, uploads the artifact directory even on failure, and only then
propagates the gate exit code. B2-B3B1 will call this action after hardware
report generation.
