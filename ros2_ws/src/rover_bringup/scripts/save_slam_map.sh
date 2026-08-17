#!/usr/bin/env bash
set -euo pipefail

prefix="${1:-$PWD/maps/rover_map}"
mkdir -p "$(dirname "$prefix")"

timeout 20 bash -c 'until ros2 service list | grep -q /slam_toolbox/save_map; do sleep 0.2; done'
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: {data: '$prefix'}}"
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '$prefix'}"

echo "Saved occupancy map and serialized pose graph with prefix: $prefix"
