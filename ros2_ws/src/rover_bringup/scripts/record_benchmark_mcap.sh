#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: ros2 run rover_bringup record_benchmark_mcap.sh OUTPUT_DIRECTORY" >&2
  exit 2
fi
output="$1"
if [[ -e "$output" ]]; then
  echo "MCAP output already exists: $output" >&2
  exit 2
fi
share="$(ros2 pkg prefix --share rover_navigation)"
topics=()
while IFS= read -r topic; do topics+=("$topic"); done \
  < <(grep -Ev '^\s*(#|$)' "$share/config/mcap_topics.txt")
exec ros2 bag record \
  --storage mcap \
  --storage-preset-profile zstd_fast \
  --use-sim-time \
  --output "$output" \
  --topics "${topics[@]}"
