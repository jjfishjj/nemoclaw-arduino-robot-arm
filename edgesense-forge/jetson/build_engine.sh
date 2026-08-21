#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
model_dir="${project_dir}/models/motor-anomaly-0.2"
onnx_path="${model_dir}/model.onnx"
engine_path="${model_dir}/model.plan"

if ! command -v trtexec >/dev/null 2>&1; then
  echo "ERROR: trtexec was not found. Run this script on Jetson with JetPack/TensorRT installed." >&2
  exit 2
fi

trtexec \
  --onnx="${onnx_path}" \
  --saveEngine="${engine_path}" \
  --minShapes=features:1x2 \
  --optShapes=features:1x2 \
  --maxShapes=features:1x2 \
  --fp16 \
  --skipInference

echo "TensorRT engine created: ${engine_path}"
