# B2-B3B2A — RealSense runner provisioning checklist

The hardware gate and signed baseline workflows now block benchmark or candidate
generation until the self-hosted runner passes a deterministic provisioning
check. It verifies:

- the `pyrealsense2` package and `rs-enumerate-devices` CLI;
- the scheduled runner contract: `self-hosted`, `linux`, `x64`, `realsense`;
- at least 5 GiB of free space;
- a readable `.bag` recording;
- readable/writable USB device nodes when live USB access is required.

The promotion workflow uses `.bag` playback, so missing USB access is reported
as `WARN`, not a failure. Operators can require physical USB access separately:

```bash
python -m arm_bridge.realsense_runner_check \
  --bag /srv/realsense/reviewed.bag \
  --labels self-hosted,linux,x64,realsense \
  --require-usb \
  --output artifacts/provisioning/report.json \
  --summary artifacts/provisioning/summary.md
```

The command exits `0` only when every required check passes, otherwise `2`.
Motion is never enabled. JSON and Markdown reports are uploaded even when the
workflow is blocked, and the Markdown is also appended to the GitHub job summary.

Runner labels are validated against the workflow's reviewed scheduling contract;
GitHub Actions does not expose the runner's complete server-side label set to a
shell step. GitHub itself enforces those labels before scheduling the job.
