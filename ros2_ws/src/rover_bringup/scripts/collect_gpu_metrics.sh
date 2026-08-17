#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: collect_gpu_metrics.sh OUTPUT.csv [INTERVAL_SECONDS]" >&2
  exit 2
fi
output="$1"
interval="${2:-1}"
if ! [[ "$interval" =~ ^[0-9]+([.][0-9]+)?$ ]] || [[ "$interval" == "0" ]]; then
  echo "interval must be a positive number" >&2
  exit 2
fi
if ! command -v nvidia-smi >/dev/null; then
  echo "nvidia-smi is required" >&2
  exit 1
fi

mkdir -p "$(dirname "$output")"
printf '%s\n' 'epoch_seconds,gpu_index,gpu_utilization_percent,memory_used_mib,memory_total_mib,temperature_c,power_draw_w,disk_free_gib' >"$output"

while true; do
  epoch="$(date +%s)"
  disk_free_kib="$(df -Pk "${RUNNER_WORKSPACE:-$PWD}" | awk 'NR==2 {print $4}')"
  disk_free_gib="$(awk -v kib="$disk_free_kib" 'BEGIN {printf "%.3f", kib / 1048576}')"
  while IFS= read -r row; do
    printf '%s,%s,%s\n' "$epoch" "$row" "$disk_free_gib" >>"$output"
  done < <(nvidia-smi \
    --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw \
    --format=csv,noheader,nounits)
  sleep "$interval"
done
