#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: ros2 run rover_bringup run_random_benchmark.sh MAP.yaml [TRIALS] [OUTPUT_DIR]" >&2
  exit 2
fi

map_path="$1"
trials="${2:-5}"
output_dir="${3:-$PWD/reports/random_benchmark}"
if [[ ! -f "$map_path" || "$trials" -le 0 ]]; then
  echo "map must exist and TRIALS must be positive" >&2
  exit 2
fi
mkdir -p "$output_dir" /tmp/rover_waypoint_tasks
description_share="$(ros2 pkg prefix --share rover_description)"
navigation_share="$(ros2 pkg prefix --share rover_navigation)"

reports=()
for ((seed=1; seed<=trials; seed++)); do
  world="$output_dir/world_seed_${seed}.sdf"
  report="$output_dir/trial_${seed}.json"
  log="$output_dir/trial_${seed}.log"
  bag="$output_dir/trial_${seed}_mcap"
  gpu_metrics="$output_dir/trial_${seed}_gpu.csv"
  : >"$log"
  ros2 run rover_navigation randomize_world \
    "$description_share/worlds/rover_test.sdf" "$world" --seed "$seed" --count 8
  touch /tmp/rover_waypoint_tasks/waypoint_2.confirm
  ros2 run rover_bringup collect_gpu_metrics.sh "$gpu_metrics" 1 >>"$log" 2>&1 &
  gpu_pid=$!
  ros2 launch rover_bringup gazebo_localization.launch.py \
    map:="$map_path" world:="$world" headless:=true use_rviz:=false >>"$log" 2>&1 &
  launch_pid=$!
  ready=false
  for _ in {1..90}; do
    if ros2 action list 2>/dev/null | grep -q '^/follow_waypoints$'; then ready=true; break; fi
    sleep 1
  done
  if [[ "$ready" == true ]]; then
    ros2 run rover_bringup record_benchmark_mcap.sh "$bag" >>"$log" 2>&1 &
    bag_pid=$!
    sleep 2
    if kill -0 "$bag_pid" 2>/dev/null; then
      ros2 run rover_navigation nav_evaluator \
        "$navigation_share/config/patrol_route.json" "$report" --timeout 300 || true
    else
      echo "MCAP recorder failed for seed $seed" >>"$log"
    fi
    kill -INT "$bag_pid" 2>/dev/null || true
    wait "$bag_pid" 2>/dev/null || true
  fi
  kill -INT "$launch_pid" 2>/dev/null || true
  wait "$launch_pid" 2>/dev/null || true
  kill -INT "$gpu_pid" 2>/dev/null || true
  wait "$gpu_pid" 2>/dev/null || true
  if [[ -f "$report" ]]; then
    ros2 run rover_navigation performance_report "$report" "$gpu_metrics" "$bag"
    reports+=("$report")
  fi
done

if [[ ${#reports[@]} -eq 0 ]]; then
  echo "No benchmark trial produced a report; inspect $output_dir/trial_*.log" >&2
  exit 1
fi
ros2 run rover_navigation benchmark_summary "$output_dir/summary.json" "${reports[@]}"
ros2 run rover_navigation benchmark_dashboard "$output_dir/dashboard.html" "${reports[@]}"
ros2 run rover_navigation benchmark_gate \
  "$output_dir/summary.json" "$navigation_share/config/benchmark_thresholds.json"
echo "PASS: randomized benchmark, MCAP evidence, dashboard, and CI gate completed"
