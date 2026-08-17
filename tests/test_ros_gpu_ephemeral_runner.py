from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_gpu_workflow_requires_ephemeral_fresh_image_evidence():
    text = (ROOT / ".github/workflows/ros2-rover-gpu-benchmark.yml").read_text()
    assert "runs-on: [self-hosted, linux, x64, ros2-jazzy, gpu, gazebo, ephemeral]" in text
    assert 'REQUIRE_EPHEMERAL_RUNNER: "1"' in text
    assert "/etc/rover-gpu-image-id" in text
    assert '"image_id":image' in text and '"boot_id":boot' in text
    assert "pull_request:" not in text and "push:" not in text


def test_runner_is_one_job_and_always_invokes_root_owned_teardown():
    run_once = (ROOT / "ops/ros_gpu_runner/run_ephemeral_once.sh").read_text()
    register = (ROOT / "ops/ros_gpu_runner/register_runner.sh").read_text()
    destroy = (ROOT / "ops/ros_gpu_runner/destroy_ephemeral_runner.example.sh").read_text()
    assert "trap cleanup EXIT" in run_once
    assert "trap 'exit 130' INT" in run_once and "trap 'exit 143' TERM" in run_once
    assert 'sudo "$teardown_hook" "$status"' in run_once
    assert "EPHEMERAL_RUNNER=1" in run_once
    assert "--ephemeral --disableupdate" in register
    assert "unset RUNNER_TOKEN" in register
    assert "/sbin/shutdown -h now" in destroy


def test_cloud_init_has_bounded_lifetime_and_poweroff_actions():
    text = (ROOT / "ops/ros_gpu_runner/cloud-init.example.yaml").read_text()
    assert "EnvironmentFile=/run/secrets/ephemeral-runner.env" in text
    assert "SuccessAction=poweroff" in text
    assert "FailureAction=poweroff" in text
    assert "RuntimeMaxSec=3h" in text
