#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
engine_path="${project_dir}/models/motor-anomaly-0.2/model.plan"
output_path="${1:-${project_dir}/data/tensorrt-benchmark.json}"

if ! command -v trtexec >/dev/null 2>&1; then
  echo "ERROR: trtexec was not found. Benchmark must run on Jetson." >&2
  exit 2
fi
if [[ ! -f "${engine_path}" ]]; then
  echo "ERROR: model.plan is missing. Run jetson/build_engine.sh first." >&2
  exit 3
fi

mkdir -p "$(dirname "${output_path}")"
trtexec \
  --loadEngine="${engine_path}" \
  --shapes=features:1x2 \
  --warmUp=1000 \
  --duration=10 \
  --useSpinWait \
  --exportTimes="${output_path}"

echo "Raw TensorRT timing samples exported: ${output_path}"
