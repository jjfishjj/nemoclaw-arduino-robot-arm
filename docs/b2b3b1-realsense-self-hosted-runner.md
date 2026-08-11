# B2-B3B1 — RealSense self-hosted hardware runner

The manual `RealSense Hardware Gate` workflow runs only on a GitHub runner with
the labels `self-hosted`, `linux`, `x64`, and `realsense`. It is not triggered by
pull requests and checkout credentials are not persisted.
The job also refuses non-default refs and explicitly checks out the repository
default branch, preventing a manually selected feature branch from running
unreviewed code on the hardware runner.

Configure these GitHub repository or organization variables before running it:

- `REALSENSE_BAG_PATH`: absolute path to the reviewed `.bag` on the runner.
- `REALSENSE_BASELINE_PATH`: absolute path to its native-verified baseline JSON.

The workflow creates a run-specific virtual environment under `RUNNER_TEMP`,
installs the RealSense extra, runs the B2-B3A benchmark, generates Python/native
parity from the same recording, and calls the B2-B3B composite gate. Benchmark
and parity generation are `continue-on-error` so the final gate can still emit
an `INVALID` report and upload diagnostics when an earlier report is missing.

The parity report is bound to the same `.bag` SHA-256 used by the benchmark.
The workflow uploads reports and summaries but never uploads the recording and
never enables robot motion.
