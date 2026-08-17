#!/usr/bin/env python3
"""Offline structural validation for the self-hosted runner bundle."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "ops/ros_gpu_runner"
WORKFLOW = ROOT / ".github/workflows/ros2-rover-gpu-benchmark.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for name in (
        "preflight.sh", "install_host_dependencies.sh", "register_runner.sh",
        "run_ephemeral_once.sh", "destroy_ephemeral_runner.example.sh",
    ):
        path = OPS / name
        require(path.is_file(), f"missing {name}")
        text = path.read_text()
        require("set -euo pipefail" in text, f"{name} must use strict shell mode")

    register = (OPS / "register_runner.sh").read_text()
    for contract in ("RUNNER_TOKEN", "RUNNER_SHA256", "sha256sum --check", "--labels"):
        require(contract in register, f"registration contract missing: {contract}")
    require("--replace" not in register, "registration must not silently replace a runner")

    workflow = WORKFLOW.read_text()
    for contract in (
        "workflow_dispatch:", "schedule:", "self-hosted", "ros2-jazzy", "gpu", "gazebo",
        "timeout-minutes:", "concurrency:", "preflight.sh", "run_random_benchmark.sh",
        "upload-artifact@v4", "if: always()", "ROVER_BENCHMARK_MAP", "queue-marker:",
        "runner_metrics.json", "ephemeral", "REQUIRE_EPHEMERAL_RUNNER", "image_id", "boot_id",
    ):
        require(contract in workflow, f"workflow contract missing: {contract}")
    require("pull_request:" not in workflow, "GPU runner must not execute pull request code")
    require("push:" not in workflow, "GPU runner must not execute arbitrary pushed branches")
    ephemeral = (OPS / "run_ephemeral_once.sh").read_text()
    for contract in ("EPHEMERAL_RUNNER=1", "EPHEMERAL_LOG_DIR", "EPHEMERAL_TEARDOWN_HOOK"):
        require(contract in ephemeral, f"ephemeral runner contract missing: {contract}")
    preflight = (OPS / "preflight.sh").read_text()
    for contract in ("/etc/rover-gpu-image-id", "/proc/uptime", "14400"):
        require(contract in preflight, f"fresh-image gate missing: {contract}")
    cloud_init = (OPS / "cloud-init.example.yaml").read_text()
    for contract in ("SuccessAction=poweroff", "FailureAction=poweroff", "RuntimeMaxSec=3h"):
        require(contract in cloud_init, f"cloud-init teardown contract missing: {contract}")
    print("PASS: self-hosted ROS/GPU runner bundle contracts agree")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
