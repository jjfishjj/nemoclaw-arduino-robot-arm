#!/usr/bin/env bash
set -euo pipefail

output="${1:-$PWD/reports/navigation_kpi.json}"
share="$(ros2 pkg prefix --share rover_navigation)"
bag="${output%.json}_mcap"
mkdir -p /tmp/rover_waypoint_tasks
touch /tmp/rover_waypoint_tasks/waypoint_2.confirm
ros2 run rover_bringup record_benchmark_mcap.sh "$bag" &
bag_pid=$!
stop_bag() {
  kill -INT "$bag_pid" 2>/dev/null || true
  wait "$bag_pid" 2>/dev/null || true
}
trap stop_bag EXIT
sleep 2
if ! kill -0 "$bag_pid" 2>/dev/null; then
  echo "MCAP recorder failed to start" >&2
  wait "$bag_pid" || true
  exit 1
fi
ros2 run rover_navigation nav_evaluator "$share/config/patrol_route.json" "$output"
stop_bag
trap - EXIT
ros2 run rover_navigation benchmark_dashboard "${output%.json}.html" "$output"
ros2 run rover_navigation benchmark_gate "$output" "$share/config/benchmark_thresholds.json"
echo "PASS: KPI, dashboard, MCAP, and safety gate completed: $output"
