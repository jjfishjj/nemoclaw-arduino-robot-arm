#!/usr/bin/env bash
set -euo pipefail

failures=0
warnings=0

pass() { printf 'PASS: %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; warnings=$((warnings + 1)); }
fail() { printf 'FAIL: %s\n' "$*" >&2; failures=$((failures + 1)); }

if [[ "${REQUIRE_EPHEMERAL_RUNNER:-0}" == "1" ]]; then
  if [[ -s /etc/rover-gpu-image-id ]]; then
    image_id="$(tr -d '\r\n' </etc/rover-gpu-image-id)"
    if [[ "$image_id" =~ ^[A-Za-z0-9._-]{8,128}$ ]]; then
      pass "sealed GPU image identity: $image_id"
    else
      fail "/etc/rover-gpu-image-id has an invalid value"
    fi
  else
    fail "ephemeral runner is missing /etc/rover-gpu-image-id"
  fi
  boot_age_seconds="$(cut -d. -f1 /proc/uptime)"
  if [[ "$boot_age_seconds" -le 14400 ]]; then
    pass "ephemeral VM boot age is at most four hours"
  else
    fail "ephemeral VM boot age exceeds four hours"
  fi
fi

if [[ ! -r /etc/os-release ]]; then
  fail "cannot read /etc/os-release (Ubuntu 24.04 is required)"
else
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]; then
    pass "Ubuntu 24.04"
  else
    fail "expected Ubuntu 24.04, found ${PRETTY_NAME:-unknown}"
  fi
fi

case "$(uname -m)" in
  x86_64) pass "x86_64 architecture" ;;
  *) fail "workflow requires x86_64, found $(uname -m)" ;;
esac

if command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader; then
  pass "NVIDIA driver and GPU are visible"
else
  fail "nvidia-smi cannot access an NVIDIA GPU"
fi

if [[ -r /opt/ros/jazzy/setup.bash ]]; then
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  pass "ROS 2 Jazzy environment"
else
  fail "/opt/ros/jazzy/setup.bash is missing"
fi

for command_name in ros2 colcon rosdep gz; do
  if command -v "$command_name" >/dev/null; then
    pass "$command_name is installed"
  else
    fail "$command_name is missing"
  fi
done

required_packages=(
  gz_ros2_control
  ros_gz_sim
  nav2_bringup
  slam_toolbox
  rosbag2_storage_mcap
)
for package_name in "${required_packages[@]}"; do
  if ros2 pkg prefix "$package_name" >/dev/null 2>&1; then
    pass "ROS package $package_name"
  else
    fail "ROS package $package_name is missing"
  fi
done

if command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then
    pass "Docker daemon is accessible without sudo"
    if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q 'nvidia'; then
      pass "NVIDIA Docker runtime is configured"
    else
      warn "Docker is available but its NVIDIA runtime is not configured"
    fi
  else
    warn "Docker is installed but this runner user cannot access the daemon"
  fi
else
  warn "Docker is not installed; native ROS/Gazebo jobs still work"
fi

available_kib="$(df -Pk "${RUNNER_WORKSPACE:-$PWD}" | awk 'NR==2 {print $4}')"
if [[ "$available_kib" -ge 52428800 ]]; then
  pass "at least 50 GiB free in the runner workspace"
else
  fail "less than 50 GiB free in the runner workspace"
fi

memory_kib="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
if [[ "$memory_kib" -ge 15728640 ]]; then
  pass "at least 16 GB system RAM"
else
  fail "less than 16 GB system RAM"
fi

printf 'SUMMARY: %d failure(s), %d warning(s)\n' "$failures" "$warnings"
[[ "$failures" -eq 0 ]]
