#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as the future runner user; the script invokes sudo when needed." >&2
  exit 2
fi
if [[ ! -r /etc/os-release ]]; then
  echo "Ubuntu 24.04 is required." >&2
  exit 2
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" || "$(uname -m)" != "x86_64" ]]; then
  echo "This bundle supports Ubuntu 24.04 x86_64 only." >&2
  exit 2
fi
if ! command -v nvidia-smi >/dev/null || ! nvidia-smi >/dev/null; then
  echo "Install and verify the NVIDIA driver before running this script." >&2
  exit 2
fi

sudo apt-get update
sudo apt-get install -y software-properties-common curl ca-certificates gnupg git jq
sudo add-apt-repository -y universe
sudo apt-get update

if [[ ! -f /etc/apt/sources.list.d/ros2.sources ]]; then
  ros_apt_version="$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | jq -r .tag_name)"
  if [[ -z "$ros_apt_version" || "$ros_apt_version" == "null" ]]; then
    echo "Could not resolve the current ros-apt-source release." >&2
    exit 1
  fi
  curl -fsSL -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_apt_version}/ros2-apt-source_${ros_apt_version}.$(. /etc/os-release && echo "$VERSION_CODENAME")_all.deb"
  sudo dpkg -i /tmp/ros2-apt-source.deb
fi

sudo apt-get update
sudo apt-get install -y \
  ros-dev-tools \
  ros-jazzy-desktop \
  ros-jazzy-gz-ros2-control \
  ros-jazzy-ros-gz \
  ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup \
  ros-jazzy-slam-toolbox \
  ros-jazzy-foxglove-bridge \
  ros-jazzy-rosbag2-storage-mcap

if [[ "${INSTALL_NVIDIA_CONTAINER_TOOLKIT:-1}" == "1" ]]; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
  if command -v docker >/dev/null; then
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
  else
    echo "Docker is absent; installed nvidia-container-toolkit without configuring a runtime."
  fi
fi

sudo rosdep init 2>/dev/null || true
rosdep update
echo "Host dependencies installed. Run preflight.sh before registering the runner."
